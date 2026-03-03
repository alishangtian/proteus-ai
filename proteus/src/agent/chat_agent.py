"""Chat Agent 模块 - 处理纯聊天模式的对话"""

import logging
import time
import os
import threading
import asyncio
import yaml
from pathlib import Path
from string import Template
from datetime import datetime
from typing import Optional, List, Dict, Any, Set
from src.api.stream_manager import StreamManager
from src.api.llm_api import (
    call_llm_api,
    call_llm_api_stream,
    call_llm_api_with_tools_stream,
)
from src.utils.tool_converter import load_tools_from_yaml
from src.utils.langfuse_wrapper import langfuse_wrapper
from src.agent.prompt.chat_agent_mermaid import CHAT_AGENT_SYSTEM_MERMAID

# IMPORT SKILLS_PROMPT_TEMPLATES
from src.agent.prompt.skills_prompt import SKILLS_PROMPT_TEMPLATES
from src.nodes.skills_extract import (
    get_default_skills_dirs,
    scan_multiple_skills_directories,
)
from src.manager.conversation_manager import conversation_manager
import uuid
from src.api.events import (
    create_agent_start_event,
    create_agent_complete_event,
    create_agent_stream_thinking_event,
    create_complete_event,
    create_error_event,
    create_retry_event,
    create_usage_event,
    create_compress_start_event,
    create_compress_complete_event,
)
from src.utils.token_utils import count_tokens
from src.api.model_manager import ModelManager

logger = logging.getLogger(__name__)


class ChatAgent:
    """Chat Agent 类 - 处理纯聊天模式的对话

    该类封装了 chat 模式下的所有逻辑，包括：
    - 流式 LLM 调用
    - 工具调用支持
    - Thinking 内容处理
    - 对话历史管理
    """

    _agent_cache: Dict[str, List["ChatAgent"]] = {}
    _cache_lock = threading.Lock()

    @classmethod
    def get_agents(cls, chat_id: str) -> List["ChatAgent"]:
        """获取指定chat_id下的agent列表副本

        参数:
            chat_id: 聊天会话ID

        返回:
            该chat_id下的agent列表副本(浅拷贝)
        """
        with cls._cache_lock:
            agents = cls._agent_cache.get(chat_id, [])
            logger.info(f"Getting {len(agents)} agents for chat {chat_id}")
            return list(agents)

    @classmethod
    def set_agents(cls, chat_id: str, agents: List["ChatAgent"]) -> None:
        """设置指定chat_id下的agent列表"""
        with cls._cache_lock:
            cls._agent_cache[chat_id] = agents.copy()

    @classmethod
    def clear_agents(cls, chat_id: str) -> None:
        """清除指定chat_id的agent缓存"""
        with cls._cache_lock:
            cls._agent_cache.pop(chat_id, None)

    async def stop(self) -> None:
        """停止 agent：设置停止标志、取消监听任务并从 role_agents 列表移除自身"""
        self.stopped = True
        # 取消所有待处理任务
        if hasattr(self, "_pending_tasks"):
            for task in self._pending_tasks:
                if not task.done():
                    task.cancel()
            self._pending_tasks.clear()
        # 从缓存中移除自身
        if self.chat_id:
            with ChatAgent._cache_lock:
                agents = ChatAgent._agent_cache.get(self.chat_id)
                if agents:
                    # 移除所有 agentid 匹配的 agent（通常只有一个）
                    ChatAgent._agent_cache[self.chat_id] = [
                        a for a in agents if a.agentid != self.agentid
                    ]
                    # 如果列表为空，删除该 chat_id 的条目
                    if not ChatAgent._agent_cache[self.chat_id]:
                        ChatAgent._agent_cache.pop(self.chat_id, None)
        # 清理工具执行器
        if self._tool_executor is not None:
            # ToolExecutor 没有显式的清理方法，但可以置空以帮助垃圾回收
            self._tool_executor = None
        logger.info(f"Agent {self.agentid} 已停止并清理")

    async def _register_agent(self, chat_id: str) -> None:
        """注册当前agent到缓存"""
        self.chat_id = chat_id
        with ChatAgent._cache_lock:
            if chat_id not in ChatAgent._agent_cache:
                ChatAgent._agent_cache[chat_id] = []
            if not any(
                a.agentid == self.agentid for a in ChatAgent._agent_cache[chat_id]
            ):
                ChatAgent._agent_cache[chat_id].append(self)

    def __init__(
        self,
        stream_manager: Optional[StreamManager] = None,
        model_name: Optional[str] = None,
        enable_tools: bool = False,
        tool_choices: Optional[List[str]] = None,
        max_tool_iterations: int = 5,
        conversation_id: Optional[str] = None,
        conversation_round: int = 5,
        enable_tool_memory: bool = True,
        enable_skills_memory: bool = True,
        user_name: Optional[str] = None,
        system_prompt: Optional[str] = None,
        selected_skills: Optional[List[str]] = None,
        agentid: str = None,
        workspace_path: Optional[str] = None,
    ):
        """初始化 ChatAgent

        Args:
            stream_manager: 流管理器实例，可为空（task模式）
            model_name: 模型名称，默认为 "deepseek-chat"
            enable_tools: 是否启用工具调用
            tool_choices: 指定的工具列表
            max_tool_iterations: 最大工具调用迭代次数
            enable_tool_memory: 是否启用工具记忆功能
        """
        self.stream_manager = stream_manager
        self.model_name = model_name or "deepseek-chat"
        self.enable_tools = enable_tools
        self.tool_choices = tool_choices
        self.max_tool_iterations = max_tool_iterations
        self.conversation_id = conversation_id
        self.conversation_round = conversation_round
        self.enable_tool_memory = enable_tool_memory
        self.enable_skills_memory = enable_skills_memory
        # 初始化skills记忆管理器
        self.user_name = user_name
        self.system_prompt = system_prompt or CHAT_AGENT_SYSTEM_MERMAID
        self.selected_skills = selected_skills
        self.agentid = agentid or str(uuid.uuid4())
        self.stopped = False
        # 加载压缩策略配置
        self._compression_strategies = self._load_compression_strategies()
        self.workspace_path = workspace_path
        # 延迟初始化的工具执行器（复用实例，避免每次调用重复创建）
        self._tool_executor = None
        self.chat_id = None  # 将在 _register_agent 中设置
        self._pending_tasks = set()

    def _load_compression_strategies(self) -> Dict[str, Any]:
        """加载压缩策略配置文件"""
        try:
            # 确定配置文件路径
            config_paths = [
                Path("conf/compression_strategies.yaml"),
                Path("/conf/compression_strategies.yaml"),
                Path("docker/volumes/agent/conf/compression_strategies.yaml"),
            ]

            # 尝试从环境变量获取配置目录
            if "PROTEUS_CONFIG_DIR" in os.environ:
                config_paths.insert(
                    0,
                    Path(os.environ["PROTEUS_CONFIG_DIR"])
                    / "compression_strategies.yaml",
                )

            config_path = None
            for path in config_paths:
                if path.exists():
                    config_path = path
                    break

            if config_path is None:
                logger.warning("未找到压缩策略配置文件，使用内置默认策略")
                return self._get_default_strategies()

            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)

            strategies = config.get("strategies", {})
            if not strategies:
                logger.warning("压缩策略配置文件中未找到策略定义，使用默认策略")
                return self._get_default_strategies()

            logger.info(f"成功加载压缩策略配置，共 {len(strategies)} 种策略")
            return strategies

        except Exception as e:
            logger.error(f"加载压缩策略配置文件失败: {str(e)}，使用默认策略")
            return self._get_default_strategies()

    def _get_default_strategies(self) -> Dict[str, Any]:
        """获取内置默认压缩策略"""
        return {
            "debugging": {
                "name": "调试会话压缩",
                "method": "selective_pruning",
                "keep_recent_messages": 5,
                "preserve_tools": ["skills_extract", "code_search", "file_read"],
                "aggressiveness": 0.7,
                "description": "调试会话中工具输出快速过时，优先修剪旧工具输出",
            },
            "code_review": {
                "name": "代码审查压缩",
                "method": "hybrid",
                "keep_recent_messages": 8,
                "preserve_tools": ["code_search", "diff_tool", "lint_tool"],
                "aggressiveness": 0.5,
                "description": "代码审查需要保留文件更改和决策，混合策略平衡",
            },
            "research": {
                "name": "研究分析压缩",
                "method": "summary_compression",
                "keep_recent_messages": 10,
                "preserve_tools": ["web_search", "citation_lookup", "data_analysis"],
                "aggressiveness": 0.3,
                "description": "研究对话需要保留引用和发现，优先摘要压缩",
            },
            "brainstorming": {
                "name": "头脑风暴压缩",
                "method": "summary_compression",
                "keep_recent_messages": 6,
                "preserve_tools": ["mind_map", "whiteboard", "idea_generator"],
                "aggressiveness": 0.4,
                "description": "头脑风暴需要保留创意流，摘要压缩保持连贯性",
            },
            "technical_design": {
                "name": "技术设计压缩",
                "method": "summary_compression",
                "keep_recent_messages": 8,
                "preserve_tools": ["arch_diagram", "spec_writer", "api_designer"],
                "aggressiveness": 0.3,
                "description": "技术设计需要保留规格和决策，摘要压缩最佳",
            },
            "tool_heavy": {
                "name": "工具密集型压缩",
                "method": "selective_pruning",
                "keep_recent_messages": 4,
                "preserve_tools": [
                    "skills_extract",
                    "code_search",
                    "file_read",
                    "web_search",
                ],
                "aggressiveness": 0.6,
                "description": "工具密集型对话，优先修剪旧工具输出",
            },
            "general": {
                "name": "通用压缩",
                "method": "hybrid",
                "keep_recent_messages": 5,
                "preserve_tools": ["skills_extract", "code_search"],
                "aggressiveness": 0.5,
                "description": "通用对话，平衡摘要压缩和选择性修剪",
            },
        }

    @langfuse_wrapper.dynamic_observe(name="chat_agent_run")
    async def run(
        self,
        chat_id: str,
        text: str,
        file_analysis_context: str = "",
    ) -> str:
        """运行 Chat Agent

        Args:
            chat_id: 聊天会话ID
            text: 用户输入文本
            file_analysis_context: 文件分析上下文
            conversation_id: 会话ID（用于保存历史）

        Returns:
            str: 最终响应文本
        """
        logger.info(
            f"[{chat_id}] 开始 chat 模式请求（流式），工具调用: {self.enable_tools}"
        )
        await self._register_agent(chat_id)

        try:
            # 发送 agent_start 事件
            if self.stream_manager:
                event = await create_agent_start_event(text)
                await self.stream_manager.send_message(chat_id, event)

            # 构建消息列表
            messages = []

            # 1. 先加载历史会话（加载所有历史，不限制条数）
            if self.conversation_id:
                # 加载完整的对话历史，不限制消息数量，确保工具调用链完整
                conversation_history = conversation_manager.load_conversation_history(
                    self.conversation_id
                )
                if conversation_history:
                    # 验证消息链完整性
                    conversation_history = self._validate_and_fix_message_chain(
                        conversation_history, chat_id
                    )
                    messages.extend(conversation_history)

            file_added = False
            # 如果messages为空就添加到第一条角色为 system
            all_values = {"CURRENT_TIME": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

            all_values["LANGUAGE"] = os.getenv("LANGUAGE", "中文")

            skills_prompt = ""
            skills_values = {}
            if self.enable_skills_memory:
                skills_values["SELECTED_SKILLS"] = ""
                if self.selected_skills:
                    skills_values["SELECTED_SKILLS"] = (
                        self._build_selected_skills_content(self.selected_skills)
                    )
                skills_prompt = Template(SKILLS_PROMPT_TEMPLATES).safe_substitute(
                    skills_values
                )
            all_values["SKILLS_PROMPT"] = skills_prompt

            if self.workspace_path:
                all_values["WORKSPACE_PATH"] = (
                    f"- WORKSPACE_PATH: {self.workspace_path}"
                )
            else:
                all_values["WORKSPACE_PATH"] = ""

            if not messages:
                system_message = {
                    "role": "system",
                    "content": self.system_prompt,
                }
                if file_analysis_context:
                    system_message["content"] = (
                        f"{system_message['content']} {file_analysis_context}"
                    )
                    file_added = True
                # 立即保存 system 消息到 Redis
                if self.conversation_id:
                    conversation_manager.save_message(
                        conversation_id=self.conversation_id, message=system_message
                    )
                    # self._save_conversation_to_redis(message=system_message)
                    logger.info(f"[{chat_id}] 已保存文件上下文消息到 Redis")
                system_message["content"] = Template(
                    system_message["content"]
                ).safe_substitute(all_values)
                messages.append(system_message)
            else:
                # 包含变量需要替换的 system content 需要进行替换
                system_message = messages[0]
                system_message["content"] = Template(
                    system_message["content"]
                ).safe_substitute(all_values)

            user_message = {
                "role": "user",
                "content": text,
            }

            # 2. 添加文件上下文（如果有）
            if not file_added and file_analysis_context:
                user_message = {
                    "role": "user",
                    "content": f" {file_analysis_context}\n\n请根据文件内容回答用户问题：{text}",
                }

            # 3. 添加当前用户消息
            messages.append(user_message)

            # 立即保存用户消息到 Redis（保存完整的 message 对象）
            if self.conversation_id:
                conversation_manager.save_message(
                    conversation_id=self.conversation_id, message=user_message
                )
                # self._save_conversation_to_redis(message=user_message)
                logger.info(f"[{chat_id}] 已保存用户消息到 Redis")

            # 加载工具（如果启用）
            tools = None
            tool_map = {}
            if self.enable_tools:
                tools, tool_map = await self._load_tools_with_tracking(chat_id)

            # chat 模式下，始终传递 enable_thinking=True，让 API 层根据响应决定
            enable_thinking = True

            logger.info(
                f"[{chat_id}] chat 模式使用模型: {self.model_name}，将根据 API 响应自动处理 thinking 内容"
            )

            # 用于 SOP 记忆的工具调用链记录
            _tool_chain_parts: List[str] = []
            # 后台任务集合，防止 GC 提前回收
            _bg_tasks: Set[asyncio.Task] = set()

            # 工具调用循环
            max_iterations = (
                self.max_tool_iterations if self.enable_tools and tools else 1
            )
            tool_iteration = 0
            final_response_text = ""
            # 标记是否需要保存最终助手消息（仅当最后一轮无工具调用时才保存）
            _save_final_message = False
            while tool_iteration < max_iterations:
                if self.stopped:
                    logger.info(f"[{chat_id}] Agent 已停止，退出工具调用循环")
                    break
                try:
                    # 执行一次 LLM 生成迭代
                    (
                        response_text,
                        thinking_text,
                        tool_calls,
                        accumulated_usage,
                        thinking_type,
                        reasoning_details,
                        need_compress,
                    ) = await self._execute_llm_generation(
                        chat_id=chat_id,
                        messages=messages,
                        # messages=self._filter_messages(
                        #     messages
                        # ),  # 过滤消息，只保留最新的思考消息
                        tools=tools,
                        enable_thinking=enable_thinking,
                        tool_iteration=tool_iteration,
                    )

                    # 检查是否需要压缩

                    if need_compress:
                        logger.info(f"[{chat_id}] 触发消息压缩")
                        original_tokens = count_tokens(messages, model=self.model_name)
                        # 发送压缩开始事件
                        if self.stream_manager:
                            await self.stream_manager.send_message(
                                chat_id,
                                await create_compress_start_event(original_tokens),
                            )

                        # 执行压缩（强制压缩，跳过 token 检查）
                        messages = await self._compress_messages(
                            chat_id, messages, must_compress=True
                        )

                        compressed_tokens = count_tokens(messages)
                        logger.info(
                            f"[{chat_id}] 压缩完成: {original_tokens} -> {compressed_tokens} tokens"
                        )

                        # 发送压缩完成事件
                        if self.stream_manager:
                            await self.stream_manager.send_message(
                                chat_id,
                                await create_compress_complete_event(
                                    original_tokens, compressed_tokens
                                ),
                            )

                        # 压缩后，我们需要重新执行当前迭代，而不是继续往下走
                        # 因为当前的 LLM 调用由于超限失败了，没有产生有效的 response 或 tool_calls
                        logger.info(f"[{chat_id}] 压缩完成，重新执行当前迭代")
                        need_compress = False
                        continue
                    else:
                        if self._need_compress_messages(chat_id, messages):
                            original_tokens = count_tokens(
                                messages, model=self.model_name
                            )
                            logger.info(
                                f"[{chat_id}] 虽然本轮生成未触发压缩，但消息已接近上下限，建议下一轮生成前进行压缩"
                            )
                            if self.stream_manager:
                                await self.stream_manager.send_message(
                                    chat_id,
                                    await create_compress_start_event(original_tokens),
                                )
                            messages = await self._compress_messages(chat_id, messages)
                            compressed_tokens = count_tokens(messages)
                            logger.info(
                                f"[{chat_id}] 压缩完成: {original_tokens} -> {compressed_tokens} tokens"
                            )
                            # 发送压缩完成事件
                            if self.stream_manager:
                                await self.stream_manager.send_message(
                                    chat_id,
                                    await create_compress_complete_event(
                                        original_tokens, compressed_tokens
                                    ),
                                )
                            # 压缩后，继续处理当前响应（LLM 调用已成功）
                            logger.info(f"[{chat_id}] 压缩完成，继续处理当前响应")

                    # 保存最终响应
                    final_response_text = response_text

                    # 如果没有工具调用，说明模型返回了最终答案，退出循环
                    if not tool_calls:
                        logger.info(f"[{chat_id}] 模型返回最终答案，结束工具调用循环")
                        if thinking_text and thinking_type:
                            thought_message = {
                                "role": "assistant",
                                thinking_type: thinking_text,
                                "content": response_text,
                            }
                            messages.append(thought_message)
                        _save_final_message = True
                        break

                    # 执行工具调用
                    tool_messages = await self._execute_tools(
                        chat_id=chat_id,
                        tool_calls=tool_calls,
                        tool_iteration=tool_iteration,
                    )

                    # 将助手消息（包含工具调用）添加到messages
                    assistant_message = {
                        "role": "assistant",
                        "content": response_text,
                        "tool_calls": tool_calls,
                        "reasoning_details": reasoning_details,
                        **(
                            {thinking_type: thinking_text}
                            if thinking_type and thinking_text
                            else {}
                        ),
                    }
                    messages.append(assistant_message)

                    # 立即保存助手消息到 Redis（保存完整的 message 对象）
                    if self.conversation_id:
                        conversation_manager.save_message(
                            conversation_id=self.conversation_id,
                            message=assistant_message,
                        )
                        logger.info(
                            f"[{chat_id}] 已保存助手消息（包含 {len(tool_calls)} 个工具调用）到 Redis"
                        )

                    # 将工具结果添加到messages，并立即保存到 Redis
                    for tool_msg in tool_messages:
                        messages.append(tool_msg)
                        # 立即保存每个工具调用结果到 Redis（保存完整的 message 对象）
                        if self.conversation_id:
                            conversation_manager.save_message(
                                conversation_id=self.conversation_id, message=tool_msg
                            )

                    if self.conversation_id and tool_messages:
                        logger.info(
                            f"[{chat_id}] 已保存 {len(tool_messages)} 个工具调用结果到 Redis"
                        )

                    # 增加迭代计数
                    tool_iteration += 1
                    logger.info(
                        f"[{chat_id}] 完成第 {tool_iteration} 次工具调用，继续下一轮推理"
                    )

                except Exception as e:
                    logger.error(f"[{chat_id}] 压缩消息失败: {str(e)}", exc_info=True)
                    raise e

            # 发送完成事件
            if self.stream_manager:
                await self.stream_manager.send_message(
                    chat_id, await create_complete_event()
                )

            # 仅当最后一轮无工具调用（正常结束循环）时，保存最终助手回答到 Redis
            # （有工具调用时助手消息已在循环中保存，避免重复保存）
            if self.conversation_id and _save_final_message:
                # 构建最终助手消息对象
                final_assistant_message = {
                    "role": "assistant",
                    "content": final_response_text,
                }
                conversation_manager.save_message(
                    self.conversation_id, final_assistant_message
                )
                logger.info(f"[{chat_id}] 已保存最终助手回答到 Redis")

            logger.info(f"[{chat_id}] chat 模式请求完成（流式）")

            return final_response_text

        except Exception as e:
            error_msg = f"chat 模式处理失败: {str(e)}"
            logger.error(f"[{chat_id}] {error_msg}", exc_info=True)

            if self.stream_manager:
                await self.stream_manager.send_message(
                    chat_id, await create_error_event(error_msg)
                )
            raise

    @langfuse_wrapper.dynamic_observe()
    async def _load_tools_with_tracking(
        self, chat_id: str
    ) -> tuple[Optional[List[Dict]], Dict[str, Dict]]:
        """加载工具（带追踪）

        Args:
            chat_id: 聊天会话ID

        Returns:
            tuple: (工具列表, 工具映射字典)
        """
        tools = None
        tool_map = {}

        try:
            if self.tool_choices:
                # 使用指定的工具
                tools = load_tools_from_yaml(node_names=self.tool_choices)
                logger.info(f"[{chat_id}] 加载指定工具: {self.tool_choices}")
            else:
                # 加载所有工具
                tools = load_tools_from_yaml()
                logger.info(f"[{chat_id}] 加载所有可用工具")

            # 构建工具映射
            for tool in tools:
                tool_map[tool["function"]["name"]] = tool

            logger.info(f"[{chat_id}] 成功加载 {len(tools)} 个工具")
        except Exception as e:
            logger.error(f"[{chat_id}] 加载工具失败: {str(e)}")
            tools = None
            raise

        return tools, tool_map

    @langfuse_wrapper.dynamic_observe()
    async def _execute_llm_generation(
        self,
        chat_id: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict]],
        enable_thinking: bool,
        tool_iteration: int,
    ) -> tuple[str, str, Optional[List], Dict]:
        """执行 LLM 生成（带追踪）

        Args:
            chat_id: 聊天会话ID
            messages: 消息列表
            tools: 工具列表
            enable_thinking: 是否启用思考模式
            tool_iteration: 当前迭代次数

        Returns:
            tuple: (响应文本, 思考文本, 工具调用列表, 使用情况)
        """
        response_text = ""
        thinking_text = ""
        thinking_type = ""
        reasoning_details = []
        need_compress = False
        tool_calls = None
        accumulated_usage = {}
        start_time = time.time()

        try:
            langfuse_instance = langfuse_wrapper.get_langfuse_instance()
            with langfuse_instance.start_as_current_span(name="llm-call") as span:
                # 创建嵌套的generation span
                span.update_trace(session_id=chat_id)
                with span.start_as_current_generation(
                    name="generate-response",
                    model=self.model_name,
                    input={"prompt": messages},
                    model_parameters={
                        "temperature": 0.7,
                        "enable_thinking": enable_thinking,
                    },
                    metadata={
                        "chat_id": chat_id,
                        "tool_iteration": tool_iteration,
                        "has_tools": tools is not None,
                    },
                ) as generation:
                    # 根据是否有工具选择不同的API
                    BUFFER_THRESHOLD = int(os.getenv("LLM_BUFFER_THRESHOLD", "50"))
                    thinking_buffer = ""
                    content_buffer = ""

                    if tools:
                        # 使用支持工具调用的流式 API

                        async for chunk in call_llm_api_with_tools_stream(
                            messages=messages,
                            tools=tools,
                            model_name=self.model_name,
                            request_id=chat_id,
                            enable_thinking=enable_thinking,
                        ):
                            chunk_type = chunk.get("type")

                            if chunk_type == "thinking":
                                if chunk.get("is_end"):
                                    if thinking_buffer and self.stream_manager:
                                        event = (
                                            await create_agent_stream_thinking_event(
                                                thinking_buffer
                                            )
                                        )
                                        await self.stream_manager.send_stream(
                                            chat_id, event
                                        )
                                        thinking_buffer = ""
                                    if self.stream_manager:
                                        event = (
                                            await create_agent_stream_thinking_event(
                                                "[THINKING_DONE]"
                                            )
                                        )
                                        await self.stream_manager.send_message(
                                            chat_id, event
                                        )
                                    continue

                                thinking_content = chunk.get("content", "")
                                thinking_text += thinking_content
                                thinking_type = chunk.get("thinking_type")
                                # 累积到缓冲区
                                thinking_buffer += thinking_content

                                # 检查阈值并发送
                                if (
                                    BUFFER_THRESHOLD > 0
                                    and len(thinking_buffer) >= BUFFER_THRESHOLD
                                    and self.stream_manager
                                ):
                                    event = await create_agent_stream_thinking_event(
                                        thinking_buffer
                                    )
                                    await self.stream_manager.send_stream(
                                        chat_id, event
                                    )
                                    thinking_buffer = ""
                                if self.stream_manager and thinking_content:
                                    event = await create_agent_stream_thinking_event(
                                        thinking_content
                                    )
                                    await self.stream_manager.send_message(
                                        chat_id, event, BUFFER_THRESHOLD <= 0
                                    )

                            elif chunk_type == "reasoning_details":
                                reasoning_details = chunk.get("content", [])

                            elif chunk_type == "content":
                                content = chunk.get("content", "")
                                response_text += content
                                # 累积到缓冲区
                                content_buffer += content

                                # 检查阈值并发送
                                if (
                                    BUFFER_THRESHOLD > 0
                                    and len(content_buffer) >= BUFFER_THRESHOLD
                                    and self.stream_manager
                                ):
                                    event = await create_agent_complete_event(
                                        content_buffer
                                    )
                                    await self.stream_manager.send_stream(
                                        chat_id, event
                                    )
                                    content_buffer = ""
                                if self.stream_manager and content:
                                    event = await create_agent_complete_event(content)
                                    await self.stream_manager.send_message(
                                        chat_id, event, BUFFER_THRESHOLD <= 0
                                    )

                            elif chunk_type == "tool_calls":
                                tool_calls = chunk.get("tool_calls", [])
                                logger.info(
                                    f"[{chat_id}] 模型请求调用 {len(tool_calls)} 个工具"
                                )
                                for tool_call in tool_calls:
                                    if tool_call.get("id") is None:
                                        tool_call["id"] = "call_" + str(uuid.uuid4())

                            elif chunk_type == "usage":
                                accumulated_usage = chunk.get("usage", {})
                                logger.info(
                                    f"[{chat_id}] Token 使用情况: {accumulated_usage}"
                                )
                                if self.stream_manager and accumulated_usage:
                                    event = await create_usage_event(accumulated_usage)
                                    await self.stream_manager.send_message(
                                        chat_id, event
                                    )

                            elif chunk_type == "retry":
                                retry_msg = chunk.get("error", "未知错误")
                                logger.error(f"[{chat_id}] 流式调用错误: {retry_msg}")
                                if self.stream_manager:
                                    await self.stream_manager.send_message(
                                        chat_id, await create_retry_event(retry_msg)
                                    )

                            elif chunk_type == "error":
                                logger.error(f"[{chat_id}] chunkInfo:{chunk}")
                                error_type = chunk.get("error_type", "")
                                error_msg = chunk.get("error", "未知错误")
                                if error_type == "token_limit_exceeded":
                                    logger.info(
                                        f"[{chat_id}] 检测到 Token 超限，准备触发压缩: {error_msg}"
                                    )
                                    need_compress = True
                                    # 如果是超限错误，我们中断流式读取，返回 need_compress=True
                                    return (
                                        response_text,
                                        thinking_text,
                                        tool_calls,
                                        accumulated_usage,
                                        thinking_type,
                                        reasoning_details,
                                        need_compress,
                                    )
                                elif error_type == "rate_limit_exceeded":
                                    pass
                                logger.error(f"[{chat_id}] 流式调用错误: {error_msg}")
                                if self.stream_manager:
                                    await self.stream_manager.send_message(
                                        chat_id, await create_error_event(error_msg)
                                    )
                                raise Exception(error_msg)
                    else:
                        # 使用普通的流式 API（不支持工具调用）

                        async for chunk in call_llm_api_stream(
                            messages=messages,
                            model_name=self.model_name,
                            request_id=chat_id,
                            enable_thinking=enable_thinking,
                        ):
                            chunk_type = chunk.get("type")

                            if chunk_type == "thinking":
                                if chunk.get("is_end"):
                                    # 刷新 thinking 缓冲区
                                    if thinking_buffer and self.stream_manager:
                                        event = (
                                            await create_agent_stream_thinking_event(
                                                thinking_buffer
                                            )
                                        )
                                        await self.stream_manager.send_stream(
                                            chat_id, event
                                        )
                                        thinking_buffer = ""
                                    if self.stream_manager:
                                        event = (
                                            await create_agent_stream_thinking_event(
                                                "[THINKING_DONE]"
                                            )
                                        )
                                        await self.stream_manager.send_message(
                                            chat_id, event
                                        )
                                    continue

                                thinking_content = chunk.get("content", "")
                                thinking_text += thinking_content
                                thinking_type = chunk.get("thinking_type")

                                # 累积到缓冲区
                                thinking_buffer += thinking_content

                                # 检查阈值并发送
                                if (
                                    len(thinking_buffer) >= BUFFER_THRESHOLD
                                    and self.stream_manager
                                ):
                                    event = await create_agent_stream_thinking_event(
                                        thinking_buffer
                                    )
                                    await self.stream_manager.send_message(
                                        chat_id, event
                                    )
                                    thinking_buffer = ""

                            elif chunk_type == "content":
                                content = chunk.get("content", "")
                                response_text += content

                                # 累积到缓冲区
                                content_buffer += content

                                # 检查阈值并发送
                                if (
                                    len(content_buffer) >= BUFFER_THRESHOLD
                                    and self.stream_manager
                                ):
                                    event = await create_agent_complete_event(
                                        content_buffer
                                    )
                                    await self.stream_manager.send_message(
                                        chat_id, event
                                    )
                                    content_buffer = ""

                            elif chunk_type == "usage":
                                accumulated_usage = chunk.get("usage", {})
                                logger.info(
                                    f"[{chat_id}] Token 使用情况: {accumulated_usage}"
                                )
                                if self.stream_manager and accumulated_usage:
                                    event = await create_usage_event(accumulated_usage)
                                    await self.stream_manager.send_message(
                                        chat_id, event
                                    )

                            elif chunk_type == "retry":
                                retry_msg = chunk.get("error", "未知错误")
                                logger.error(f"[{chat_id}] 流式调用错误: {retry_msg}")
                                if self.stream_manager:
                                    await self.stream_manager.send_message(
                                        chat_id, await create_retry_event(retry_msg)
                                    )

                            elif chunk_type == "error":
                                logger.error(f"[{chat_id}] chunkInfo:{chunk}")
                                error_type = chunk.get("error_type", "")
                                error_msg = chunk.get("error", "未知错误")
                                if error_type == "token_limit_exceeded":
                                    logger.info(
                                        f"[{chat_id}] 检测到 Token 超限，准备触发压缩: {error_msg}"
                                    )
                                    need_compress = True
                                    return (
                                        response_text,
                                        thinking_text,
                                        tool_calls,
                                        accumulated_usage,
                                        thinking_type,
                                        reasoning_details,
                                        need_compress,
                                    )
                                elif error_type == "rate_limit_exceeded":
                                    pass
                                logger.error(f"[{chat_id}] 流式调用错误: {error_msg}")
                                if self.stream_manager:
                                    await self.stream_manager.send_message(
                                        chat_id, await create_error_event(error_msg)
                                    )
                                raise Exception(error_msg)

                    # 刷新剩余缓冲区
                    if thinking_buffer and self.stream_manager:
                        event = await create_agent_stream_thinking_event(
                            thinking_buffer
                        )
                        await self.stream_manager.send_stream(chat_id, event)
                        thinking_buffer = ""
                    if content_buffer and self.stream_manager:
                        event = await create_agent_complete_event(content_buffer)
                        await self.stream_manager.send_stream(chat_id, event)
                        content_buffer = ""

                    # 计算执行时间
                    execution_time = time.time() - start_time

                    # 构建输出内容
                    output_content = {
                        "response": response_text,
                        "thinking": thinking_text if thinking_text else None,
                        "tool_calls": tool_calls if tool_calls else None,
                    }

                    # 尝试使用真实usage字段，如果没有则使用估算
                    usage_details = {
                        "input_usage": accumulated_usage.get("prompt_tokens", 0),
                        "output_usage": accumulated_usage.get("completion_tokens", 0),
                    }

                    # 更新 generation
                    generation.update(
                        output=output_content,
                        usage_details=usage_details,
                        # cost_details={
                        #     "total_cost": accumulated_usage.get("total_cost", 0.0)
                        # },
                        metadata={"execution_time": execution_time},
                    )

                    # 评分 - 根据是否有工具调用和响应质量评分
                    relevance_score = 0.95 if response_text else 0.5
                    generation.score(
                        name="relevance", value=relevance_score, data_type="NUMERIC"
                    )

                    logger.info(
                        f"[{chat_id}] LLM生成完成 (iteration {tool_iteration}, "
                        f"耗时: {execution_time:.2f}s, tokens: {usage_details['input_usage']+usage_details['output_usage']})"
                    )

            return (
                response_text,
                thinking_text,
                tool_calls,
                accumulated_usage,
                thinking_type,
                reasoning_details,
                need_compress,
            )

        except Exception as e:
            # 检查是否是超限异常（有些异常可能在 call_llm_api 内部抛出）
            error_str = str(e).lower()
            if any(
                kw in error_str
                for kw in [
                    "token_limit_exceeded",
                    "context_length_exceeded",
                    "too many tokens",
                ]
            ):
                logger.warning(f"[{chat_id}] 捕获到超限异常，触发压缩: {str(e)}")
                return (
                    response_text,
                    thinking_text,
                    tool_calls,
                    accumulated_usage,
                    thinking_type,
                    reasoning_details,
                    True,  # need_compress
                )

            execution_time = time.time() - start_time if "start_time" in locals() else 0

            # 尝试更新 generation span 的错误状态
            if "generation" in locals():
                try:
                    if hasattr(generation, "update"):
                        generation.update(
                            output={"error": str(e)},
                            status_message=f"LLM call failed: {str(e)}",
                            metadata={"execution_time": execution_time},
                        )
                except Exception as update_error:
                    logger.warning(f"Failed to update generation span: {update_error}")

            logger.error(f"[{chat_id}] LLM生成失败: {str(e)}", exc_info=True)
            raise

    @langfuse_wrapper.dynamic_observe()
    async def _execute_tools(
        self,
        chat_id: str,
        tool_calls: List[Dict],
        tool_iteration: int,
    ) -> List[Dict[str, Any]]:
        """执行工具调用（带追踪）

        Args:
            chat_id: 聊天会话ID
            tool_calls: 工具调用列表
            tool_iteration: 当前迭代次数

        Returns:
            List[Dict[str, Any]]: 工具执行结果消息列表
        """
        from src.api.tool_executor import ToolExecutor

        if self._tool_executor is None:
            self._tool_executor = ToolExecutor(
                stream_manager=self.stream_manager,
                max_retries=3,
                retry_delay=1.0,
            )
        tool_executor = self._tool_executor

        # 批量执行工具调用并收集结果
        start_time = time.time()
        tool_messages = await tool_executor.execute_tool_calls(
            tool_calls=tool_calls, chat_id=chat_id
        )
        execution_time = time.time() - start_time

        logger.info(
            f"[{chat_id}] 工具执行完成 (iteration {tool_iteration}, 耗时: {execution_time:.2f}s)"
        )

        return tool_messages

    def _validate_and_fix_message_chain(
        self, messages: List[Dict[str, Any]], chat_id: str
    ) -> List[Dict[str, Any]]:
        """
        验证并修复消息链的完整性，确保 tool 消息前面有对应的 assistant 消息（包含 tool_calls）
        支持连续的 tool 消息（工具调用可能一次返回多个工具调用）

        Args:
            messages: 消息列表
            chat_id: 聊天会话ID

        Returns:
            List[Dict[str, Any]]: 修复后的消息列表
        """
        if not messages:
            return messages

        valid_messages = []
        i = 0
        while i < len(messages):
            msg = messages[i]
            role = msg.get("role")

            if role == "tool":
                # tool 消息前面必须有 assistant 消息（包含 tool_calls）
                # 但是可能存在连续的 tool 消息（多个工具调用结果），
                # 因此需要向前查找最近的 assistant 消息，检查其是否包含 tool_calls
                assistant_found = False
                has_tool_calls = False
                # 从 valid_messages 末尾向前搜索
                for prev_msg in reversed(valid_messages):
                    if prev_msg.get("role") == "assistant":
                        assistant_found = True
                        if prev_msg.get("tool_calls"):
                            has_tool_calls = True
                        break
                    # 如果遇到其他 role（如 user、system）则停止搜索？
                    # 实际上中间可能有其他消息，但工具调用链应该是连续的。
                    # 为了简单，我们只检查最近的 assistant 消息。
                    # 如果中间有非 assistant 消息，则说明工具调用链可能被中断，视为无效。
                    if prev_msg.get("role") not in ("tool", "assistant"):
                        break

                if not assistant_found or not has_tool_calls:
                    logger.warning(
                        f"[{chat_id}] 发现孤立的 tool 消息，缺少前置的 assistant 消息或 assistant 没有 tool_calls，将被跳过"
                    )
                    i += 1
                    continue
                # 通过检查，添加该 tool 消息
                valid_messages.append(msg)
                i += 1
                continue

            elif role == "assistant" and msg.get("tool_calls"):
                # assistant 消息包含 tool_calls，它后面应该有 tool 结果消息
                # 如果没有后续的 tool 消息，这是正常的（可能是未完成的调用）
                pass

            # 其他消息（user, system, assistant 无 tool_calls）直接添加
            valid_messages.append(msg)
            i += 1

        if len(valid_messages) < len(messages):
            logger.warning(
                f"[{chat_id}] 消息链修复完成: {len(messages)} -> {len(valid_messages)} 条消息，"
                f"移除了 {len(messages) - len(valid_messages)} 条不完整的消息"
            )

        return valid_messages

    async def _get_current_user_query(self) -> Optional[str]:
        """获取当前用户查询

        Returns:
            Optional[str]: 用户查询文本
        """
        try:
            if not self.conversation_id:
                return None

            # 从Redis加载最近的对话历史
            conversation_history = conversation_manager.load_conversation_history(
                self.conversation_id, max_messages=self.conversation_round * 3
            )
            # conversation_history = self._load_conversation_history()
            if not conversation_history:
                return None

            # 查找最近的用户消息
            for message in reversed(conversation_history):
                if message.get("role") == "user":
                    return message.get("content", "")

            return None
        except Exception as e:
            logger.warning(f"获取当前用户查询失败: {str(e)}")
            return None

    def _build_selected_skills_content(self, selected_skills: List[str]) -> str:
        """构建用户选中的技能列表内容，用于模板替换

        根据 selected_skills 列表，加载对应的技能信息，
        提取 name 和 description 拼接为纯文本格式。

        Args:
            selected_skills: 用户选中的技能名称列表

        Returns:
            str: 格式化的选中技能内容
        """
        if not selected_skills:
            return "暂无选中的技能。"

        # 获取所有技能目录
        skills_dirs = get_default_skills_dirs()
        if not skills_dirs:
            return "技能目录不存在，无法加载选中技能。"

        # 扫描所有技能目录获取完整列表
        all_skills = scan_multiple_skills_directories(skills_dirs)

        # 构建技能名称到技能信息的映射
        skills_map = {skill["name"]: skill for skill in all_skills}

        # 构建选中技能的内容
        skills_content = "**请使用如下技能列表中的技能来完成任务**\n"

        found_count = 0
        not_found_count = 0

        for i, skill_name in enumerate(selected_skills, 1):
            if skill_name in skills_map:
                skill_info = skills_map[skill_name]
                name = skill_info.get("name", skill_name)
                description = skill_info.get("description", "")

                skills_content += f"### {i}. {name}\n"
                if description:
                    skills_content += f"{description}\n"
                skills_content += "\n"
                found_count += 1
            else:
                skills_content += f"### {i}. {skill_name}\n"
                skills_content += "（技能未找到）\n\n"
                not_found_count += 1

        return skills_content

    @langfuse_wrapper.dynamic_observe()
    async def _compress_messages(
        self, chat_id: str, messages: List[Dict[str, Any]], must_compress: bool = False
    ) -> List[Dict[str, Any]]:
        """优化后的消息压缩逻辑，基于 Roo Code 上下文管理机制

        核心改进：
        1. 基于 token 使用率的智能触发（非仅消息数量）
        2. 自适应压缩策略（根据对话类型选择不同压缩强度）
        3. 选择性修剪机制（保护关键工具输出，移除旧工具输出）
        4. 多层压缩策略（摘要压缩、逐条压缩、选择性修剪）

        参数:
            must_compress: 如果为 True，则跳过 token 检查，强制进行压缩
        """
        # 1. 计算当前 token 使用情况
        current_tokens = count_tokens(messages, model=self.model_name)

        # 获取模型上下文窗口大小（默认值：deepseek-chat 131072, deepseek-reasoner 131072）
        context_window = self._get_context_window_for_model()

        # 2. 判断是否需要压缩（使用率超过 80% 或 token 数超过上下文窗口）
        compression_threshold = 0.8  # 80% 使用率触发压缩
        need_compress = current_tokens > context_window * compression_threshold

        # 如果 must_compress 为 True，则跳过 token 检查，强制压缩
        if must_compress:
            logger.info(f"[{chat_id}] 强制压缩模式启动，跳过 token 检查，直接进行压缩")
            need_compress = True
        elif not need_compress and current_tokens <= context_window:
            logger.info(
                f"[{chat_id}] token 使用率正常 ({current_tokens}/{context_window})，无需压缩"
            )
            return messages

        if not must_compress:
            logger.info(
                f"[{chat_id}] 触发消息压缩: token 使用率 {current_tokens}/{context_window} "
                f"({current_tokens/context_window*100:.1f}%)"
            )
        else:
            logger.info(f"[{chat_id}] 强制压缩模式启动，执行压缩")

        # 3. 分析对话类型，选择压缩策略
        conversation_type = self._detect_conversation_type(messages)
        compression_strategy = self._select_compression_strategy(conversation_type)

        logger.info(
            f"[{chat_id}] 检测到对话类型: {conversation_type}, "
            f"使用压缩策略: {compression_strategy['name']}"
        )

        # 4. 根据策略选择压缩方法
        if compression_strategy["method"] == "summary_compression":
            # 智能摘要压缩：保留最近消息，将历史消息压缩为摘要
            compressed_messages = await self._summary_compression(
                chat_id, messages, compression_strategy
            )
        elif compression_strategy["method"] == "selective_pruning":
            # 选择性修剪：移除旧工具输出，保留关键上下文
            compressed_messages = await self._selective_pruning_compression(
                chat_id, messages, compression_strategy
            )
        elif compression_strategy["method"] == "hybrid":
            # 混合策略：先尝试选择性修剪，如果还不够则进行摘要压缩
            compressed_messages = await self._hybrid_compression(
                chat_id, messages, compression_strategy
            )
        else:
            # 回退到原有的逐条压缩
            logger.warning(f"[{chat_id}] 未知压缩策略，回退到逐条压缩")
            compressed_messages = await self._compress_messages_individual(
                chat_id, messages
            )

        # 5. 验证压缩效果
        compressed_tokens = count_tokens(compressed_messages, model=self.model_name)
        compression_ratio = compressed_tokens / max(1, current_tokens)

        logger.info(
            f"[{chat_id}] 压缩完成: {current_tokens} -> {compressed_tokens} tokens "
            f"(压缩率: {compression_ratio*100:.1f}%)"
        )

        # 6. 如果压缩后仍然超过上下文窗口，进行兜底处理
        if compressed_tokens > context_window:
            logger.warning(
                f"[{chat_id}] 压缩后仍超过上下文窗口 ({compressed_tokens}/{context_window})，"
                f"执行兜底压缩"
            )
            # 兜底策略：移除最早的非系统消息，保留最近消息
            compressed_messages = await self._fallback_compression(
                chat_id, compressed_messages, context_window
            )

        # 7. 验证压缩后的消息链完整性，确保 tool 消息有对应的 assistant 消息
        compressed_messages = self._validate_and_fix_message_chain(
            compressed_messages, chat_id
        )

        return compressed_messages

    def _need_compress_messages(
        self, chat_id: str, messages: List[Dict[str, Any]]
    ) -> bool:
        """判断是否需要压缩消息

        参数:
            chat_id: 聊天会话ID
            messages: 消息列表

        返回:
            bool: 如果需要压缩返回 True
        """
        # 1. 计算当前 token 使用情况
        current_tokens = count_tokens(messages, model=self.model_name)

        # 2. 获取模型上下文窗口大小（默认值：deepseek-chat 131072, deepseek-reasoner 131072）
        context_window = self._get_context_window_for_model()

        # 3. 判断是否需要压缩（使用率超过 80%）
        compression_threshold = 0.8  # 80% 使用率触发压缩
        need = current_tokens > context_window * compression_threshold
        if need:
            logger.info(
                f"[{chat_id}] 检测到需要压缩: token 使用率 {current_tokens}/{context_window} "
                f"({current_tokens/context_window*100:.1f}%)"
            )
        return need

    def _get_context_window_for_model(self) -> int:
        """获取当前模型的上下文窗口大小"""
        try:
            model_manager = ModelManager()
            config = model_manager.get_model_config(self.model_name)
            context_length = config.get("context_length", 131072)
            return int(context_length)
        except Exception as e:
            logger.warning(
                f"无法从ModelManager获取模型 {self.model_name} 的上下文窗口，使用默认值8192: {e}"
            )
            # 回退到硬编码映射
            model_context_map = {
                "deepseek-chat": 131072,
                "deepseek-reasoner": 131072,
                "qwen/qwen3-coder": 262144,
                "google/gemini-2.5-flash": 262144,
                "google/gemini-3-flash-preview": 262144,
                "google/gemini-3-pro-preview": 262144,
                "openai/gpt-5-mini": 262144,
                "openai/gpt-5-nano": 262144,
                "anthropic/claude-haiku-4.5": 262144,
            }
            return model_context_map.get(self.model_name, 131072)

    def _detect_conversation_type(self, messages: List[Dict[str, Any]]) -> str:
        """检测对话类型，用于选择压缩策略"""
        if not messages:
            return "general"

        # 提取最近消息的内容进行分析
        recent_messages = messages[-5:] if len(messages) >= 5 else messages
        content = " ".join([msg.get("content", "").lower() for msg in recent_messages])

        # 检测关键词（中英文）
        debugging_keywords = [
            "error",
            "bug",
            "fix",
            "debug",
            "exception",
            "crash",
            "traceback",
            "错误",
            "异常",
            "修复",
            "调试",
            "崩溃",
            "报错",
        ]
        code_review_keywords = [
            "review",
            "comment",
            "suggest",
            "improve",
            "refactor",
            "code quality",
            "代码审查",
            "建议",
            "优化",
            "重构",
            "改进",
        ]
        research_keywords = [
            "research",
            "study",
            "analysis",
            "findings",
            "citation",
            "source",
            "研究",
            "分析",
            "调研",
            "来源",
            "发现",
        ]
        brainstorming_keywords = [
            "idea",
            "brainstorm",
            "design",
            "plan",
            "strategy",
            "concept",
            "想法",
            "头脑风暴",
            "设计",
            "方案",
            "策略",
            "概念",
        ]
        technical_keywords = [
            "architecture",
            "design",
            "spec",
            "requirement",
            "technical",
            "架构",
            "规格",
            "需求",
            "技术",
            "接口",
        ]

        # 工具使用检测
        tool_heavy = any(msg.get("role") == "tool" for msg in messages[-10:])

        # 根据关键词匹配对话类型
        if any(keyword in content for keyword in debugging_keywords):
            return "debugging"
        elif any(keyword in content for keyword in code_review_keywords):
            return "code_review"
        elif any(keyword in content for keyword in research_keywords):
            return "research"
        elif any(keyword in content for keyword in brainstorming_keywords):
            return "brainstorming"
        elif any(keyword in content for keyword in technical_keywords):
            return "technical_design"
        elif tool_heavy:
            return "tool_heavy"
        else:
            return "general"

    def _select_compression_strategy(self, conversation_type: str) -> Dict[str, Any]:
        """根据对话类型选择压缩策略（从配置文件读取）"""
        strategies = self._compression_strategies

        # 如果未加载到策略，使用默认策略
        if not strategies:
            logger.warning("压缩策略未加载，使用内置默认策略")
            strategies = self._get_default_strategies()

        # 获取对应对话类型的策略，如果不存在则使用general策略
        strategy = strategies.get(conversation_type)
        if not strategy:
            logger.warning(
                f"未找到对话类型 '{conversation_type}' 的压缩策略，使用通用策略"
            )
            strategy = strategies.get("general")

        # 如果连general策略都没有，返回一个基本策略
        if not strategy:
            strategy = {
                "name": "默认压缩",
                "method": "hybrid",
                "keep_recent_messages": 5,
                "preserve_tools": ["skills_extract", "code_search"],
                "aggressiveness": 0.5,
                "description": "默认压缩策略",
            }

        return strategy

    async def _summary_compression(
        self, chat_id: str, messages: List[Dict[str, Any]], strategy: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """智能摘要压缩：保留最近消息，将历史消息压缩为摘要"""
        keep_recent = strategy.get("keep_recent_messages", 5)

        # 分离系统消息
        system_messages = [msg for msg in messages if msg.get("role") == "system"]
        other_messages = [msg for msg in messages if msg.get("role") != "system"]

        # 如果消息数量不多，回退到逐条压缩
        if len(other_messages) <= keep_recent:
            logger.info(f"[{chat_id}] 消息数量较少，回退到逐条压缩")
            return await self._compress_messages_individual(chat_id, messages)

        # 保留最近消息
        recent_messages = other_messages[-keep_recent:]
        old_messages = other_messages[:-keep_recent]

        if not old_messages:
            return system_messages + recent_messages

        # 生成旧消息的对话摘要
        try:
            summary_text = await self._generate_conversation_summary(
                chat_id, old_messages
            )
            summary_message = {
                "role": "system",
                "content": f"## 对话摘要（压缩自 {len(old_messages)} 条历史消息）\n{summary_text}",
            }
            compressed_messages = system_messages + [summary_message] + recent_messages
            logger.info(f"[{chat_id}] 摘要压缩完成，替换 {len(old_messages)} 条旧消息")
            return compressed_messages
        except Exception as e:
            logger.error(f"[{chat_id}] 摘要压缩失败，回退到逐条压缩: {str(e)}")
            return await self._compress_messages_individual(chat_id, messages)

    async def _selective_pruning_compression(
        self, chat_id: str, messages: List[Dict[str, Any]], strategy: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """选择性修剪压缩：移除旧工具输出，保留关键上下文"""
        preserved_tools = strategy.get("preserve_tools", [])
        keep_recent = strategy.get("keep_recent_messages", 5)

        compressed_messages = []
        tool_outputs_pruned = 0
        total_tools = 0

        # 扫描消息，处理工具输出
        for i, msg in enumerate(messages):
            role = msg.get("role")

            if role == "tool":
                total_tools += 1
                tool_name = msg.get("name", "")

                # 检查是否应该保留此工具输出
                should_preserve = (
                    tool_name in preserved_tools
                    or i >= len(messages) - keep_recent * 2  # 保留较近的工具输出
                )

                if not should_preserve:
                    # 修剪工具输出：替换为摘要
                    content = msg.get("content", "")
                    if len(content) > 500:
                        summary = await self._get_llm_summary(
                            chat_id,
                            f"你是一个摘要助手。请对以下工具执行结果进行总结，保留以下关键信息：\n- 工具名称\n- 执行状态（成功/失败）\n- 关键发现或结果\n\n请用简洁的语言总结，确保核心内容完整，长度控制在500字符以内。\n\n原始内容：\n{content}",
                            content,
                        )
                        new_msg = msg.copy()
                        new_msg["content"] = f"[修剪后的工具输出] {summary}"
                        compressed_messages.append(new_msg)
                        tool_outputs_pruned += 1
                    else:
                        compressed_messages.append(msg)
                else:
                    compressed_messages.append(msg)
            else:
                # 非工具消息直接保留
                compressed_messages.append(msg)

        if tool_outputs_pruned > 0:
            logger.info(
                f"[{chat_id}] 选择性修剪完成，修剪了 {tool_outputs_pruned}/{total_tools} 个工具输出"
            )

        return compressed_messages

    async def _hybrid_compression(
        self, chat_id: str, messages: List[Dict[str, Any]], strategy: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """混合压缩策略：先尝试选择性修剪，如果还不够则进行摘要压缩"""
        # 第一步：尝试选择性修剪
        pruned_messages = await self._selective_pruning_compression(
            chat_id, messages, strategy
        )

        # 检查修剪后的 token 数
        pruned_tokens = count_tokens(pruned_messages, model=self.model_name)
        context_window = self._get_context_window_for_model()

        # 如果修剪后仍然超过阈值，进行摘要压缩
        if pruned_tokens > context_window * 0.8:
            logger.info(f"[{chat_id}] 选择性修剪后仍需进一步压缩，进行摘要压缩")
            return await self._summary_compression(chat_id, pruned_messages, strategy)

        return pruned_messages

    async def _fallback_compression(
        self, chat_id: str, messages: List[Dict[str, Any]], context_window: int
    ) -> List[Dict[str, Any]]:
        """兜底压缩策略：当其他压缩方法仍无效时使用"""
        logger.warning(f"[{chat_id}] 执行兜底压缩策略")

        # 保留系统消息和最近消息，逐步移除较旧消息
        system_messages = [msg for msg in messages if msg.get("role") == "system"]
        other_messages = [msg for msg in messages if msg.get("role") != "system"]

        if len(other_messages) <= 2:
            # 消息太少，无法进一步压缩
            return messages

        # 尝试逐步移除消息，直到满足上下文窗口
        for keep_count in range(len(other_messages) - 1, 1, -1):
            test_messages = system_messages + other_messages[-keep_count:]
            test_tokens = count_tokens(test_messages, model=self.model_name)

            if test_tokens <= context_window:
                removed_count = len(other_messages) - keep_count
                logger.info(
                    f"[{chat_id}] 兜底压缩移除 {removed_count} 条消息，"
                    f"保留 {keep_count} 条非系统消息"
                )
                return test_messages

        # 如果仍然不行，只保留最后一条非系统消息
        final_messages = (
            system_messages + other_messages[-1:] if other_messages else system_messages
        )
        logger.warning(f"[{chat_id}] 兜底压缩极端情况，仅保留最后一条非系统消息")
        return final_messages

    async def _compress_messages_individual(
        self, chat_id: str, messages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """原有的逐条消息压缩逻辑（作为回退方案）"""
        compressed_messages = []
        trigger_compress = False

        for i, msg in enumerate(messages):
            role = msg.get("role")

            # system 消息不压缩
            if role == "system":
                compressed_messages.append(msg)
                continue

            if role == "tool" and msg.get("name") != "skills_extract":
                # 只压缩 content 字段，长度超过 1000 才压缩
                content = msg.get("content", "")
                if len(content) > 1000:
                    summary = await self._get_llm_summary(
                        chat_id,
                        f"你是一个摘要助手。请对以下工具执行结果进行总结，保留以下关键信息：\n- 工具名称\n- 执行状态（成功/失败）\n- 关键输出数据或错误信息\n- 对后续对话有重要影响的任何发现或结果\n\n请用简洁的语言总结，确保核心内容完整，长度控制在1000字符以内。\n\n原始内容：\n{content}",
                        content,
                    )
                    new_msg = msg.copy()
                    new_msg["content"] = f"{summary}"
                    compressed_messages.append(new_msg)
                    trigger_compress = True
                else:
                    compressed_messages.append(msg)

            elif role == "assistant":
                # 压缩 content 和 reasoning_content 字段
                content = msg.get("content", "")
                reasoning_content = msg.get("reasoning_content", "")
                reasoning = msg.get("reasoning", "")

                compressed = False
                new_msg = msg.copy()

                # 压缩 content 字段
                if len(content) > 2000:
                    summary = await self._get_llm_summary(
                        chat_id,
                        f"你是一个摘要助手。请对以下助手回答进行总结，保留以下关键信息：\n- 主要答案或建议\n- 关键代码片段或技术细节（如有）\n- 重要步骤或推理过程\n- 对用户问题的直接回应\n\n请用简洁的语言总结，确保核心内容完整，长度控制在2000字符以内。\n\n原始内容：\n{content}",
                        content,
                    )
                    new_msg["content"] = f"{summary}"
                    trigger_compress = True
                    compressed = True

                # 压缩 reasoning_content 字段
                if len(reasoning_content) > 500:
                    summary = await self._get_llm_summary(
                        chat_id,
                        f"你是一个摘要助手。请对以下助手思考过程进行总结，保留以下关键信息：\n- 主要推理步骤\n- 关键决策或假设\n- 遇到的问题及解决方案\n- 最终结论或方向\n\n请用简洁的语言总结，确保核心内容完整，长度控制在500字符以内。\n\n原始内容：\n{reasoning_content}",
                        reasoning_content,
                    )
                    # 确定使用哪个字段名
                    new_msg["reasoning_content"] = f"{summary}"
                    trigger_compress = True
                    compressed = True

                if len(reasoning) > 500:
                    summary = await self._get_llm_summary(
                        chat_id,
                        f"你是一个摘要助手。请对以下助手思考过程进行总结，保留以下关键信息：\n- 主要推理步骤\n- 关键决策或假设\n- 遇到的问题及解决方案\n- 最终结论或方向\n\n请用简洁的语言总结，确保核心内容完整，长度控制在500字符以内。\n\n原始内容：\n{reasoning}",
                        reasoning,
                    )
                    # 确定使用哪个字段名
                    new_msg["reasoning"] = f"{summary}"
                    trigger_compress = True
                    compressed = True

                if compressed:
                    compressed_messages.append(new_msg)
                else:
                    compressed_messages.append(msg)

            else:
                # user 消息或其他
                content = msg.get("content", "")
                if len(content) > 500:
                    summary = await self._get_llm_summary(
                        chat_id,
                        f"你是一个摘要助手。请对以下用户提问进行总结，保留以下关键信息：\n- 用户的核心问题或请求\n- 任何约束条件或特殊要求\n- 提到的文件、代码或相关上下文\n- 对后续对话重要的背景信息\n\n请用简洁的语言总结，确保核心内容完整，长度控制在500字符以内。\n\n原始内容：\n{content}",
                        content,
                    )
                    new_msg = msg.copy()
                    new_msg["content"] = f"{summary}"
                    compressed_messages.append(new_msg)
                    trigger_compress = True
                else:
                    compressed_messages.append(msg)

        # 如果整个循环中没有触发任何压缩，说明单条消息都未超过阈值
        # 此时执行兜底策略：移除最早的历史消息（保留 system 和最近的消息）
        if not trigger_compress:
            logger.info(
                f"[{chat_id}] 单条消息未触发压缩阈值，执行兜底策略：移除最早的历史消息"
            )

            # 确保有足够的消息可以移除（至少保留 system 和最后一条消息）
            if len(compressed_messages) > 2:
                # 移除 index 1 的消息（最早的非 system 消息）
                removed_msg = compressed_messages.pop(1)
                logger.info(
                    f"[{chat_id}] 已移除消息: role={removed_msg.get('role')}, content_len={len(removed_msg.get('content', ''))}"
                )
            else:
                logger.warning(
                    f"[{chat_id}] 消息数量太少({len(compressed_messages)})，无法执行移除策略"
                )
                raise Exception(f"[{chat_id}] 消息过短且数量过少，无法压缩")

        return compressed_messages

    async def _get_llm_summary(
        self, chat_id: str, prompt: str, origin_content: str
    ) -> str:
        """调用 LLM 获取摘要"""
        try:
            messages = [{"role": "user", "content": prompt}]
            # 使用非流式 API 获取摘要
            summary, _ = await call_llm_api(
                messages=messages,
                model_name=self.model_name,
                request_id=f"compress-{chat_id}-{int(time.time())}",
                temperature=0.3,
            )
            return summary.strip()
        except Exception as e:
            logger.error(f"[{chat_id}] 获取 LLM 摘要失败: {str(e)}")
            input_max_length = int(os.getenv("INPUT_MAX_LENGTH", 5000))
            return origin_content[:input_max_length]

    async def _generate_conversation_summary(
        self, chat_id: str, messages: List[Dict[str, Any]]
    ) -> str:
        """生成对话摘要，使用提供的结构化提示词"""
        # 将消息列表格式化为文本
        formatted_messages = []
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            # 处理可能的思考内容
            thinking = (
                msg.get("thinking", "")
                or msg.get("reasoning", "")
                or msg.get("reasoning_content", "")
            )
            if thinking:
                content = f"{content}\n（思考：{thinking}）"
            formatted_messages.append(f"{role}: {content}")
        conversation_text = "\n\n".join(formatted_messages)

        # 使用用户提供的提示词模板
        prompt = f"""Your task is to create a detailed summary of the
conversation so far, paying close attention to the user's
explicit requests and your previous actions.
This summary should be thorough in capturing technical
details, code patterns, and architectural decisions that
would be essential for continuing with the conversation and
supporting any continuing tasks.
Your summary should be structured as follows:
Context: The context to continue the conversation with. If
applicable based on the current task, this should include:
1. Previous Conversation: High level details about what was
discussed throughout the entire conversation with the user.
This should be written to allow someone to be able to follow
the general overarching conversation flow.
2. Current Work: Describe in detail what was being worked on
prior to this request to summarize the conversation. Pay
special attention to the more recent messages in the
conversation.
3. Key Technical Concepts: List all important technical
concepts, technologies, coding conventions, and frameworks
discussed, which might be relevant for continuing with this
work.
4. Relevant Files and Code: If applicable, enumerate
specific files and code sections examined, modified, or
created for the task continuation. Pay special attention to
the most recent messages and changes.
5. Problem Solving: Document problems solved thus far and
any ongoing troubleshooting efforts.
6. Pending Tasks and Next Steps: Outline all pending tasks
that you have explicitly been asked to work on, as well as
list the next steps you will take for all outstanding work,
if applicable. Include code snippets where they add clarity.
For any next steps, include direct quotes from the most
recent conversation showing exactly what task you were
working on and where you left off. This should be verbatim
to ensure there's no information loss in context between
tasks.

以下是对话历史：
{conversation_text}

请根据上述要求生成结构化摘要。"""
        try:
            summary, _ = await call_llm_api(
                messages=[{"role": "user", "content": prompt}],
                model_name=self.model_name,
                request_id=f"conversation-summary-{chat_id}-{int(time.time())}",
                temperature=0.3,
            )
            return summary.strip()
        except Exception as e:
            logger.error(f"[{chat_id}] 生成对话摘要失败: {str(e)}")
            # 回退到简单摘要
            return f"对话摘要（{len(messages)}条消息）: " + conversation_text[:1000]


from src.utils.dynamic_observer import auto_apply_here

auto_apply_here(
    globals(),
    include=None,
    exclude=[],
    only_in_module=True,
    verbose=False,
)
