"""Chat Agent 模块 - 处理纯聊天模式的对话"""

import json
import logging
import time
import os
import threading
import asyncio
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
from src.utils.redis_cache import get_redis_connection

logger = logging.getLogger(__name__)

# 智能体状态常量
AGENT_STATUS_INIT = "init"
AGENT_STATUS_RUNNING = "running"
AGENT_STATUS_STOPPED = "stopped"
AGENT_STATUS_COMPLETE = "complete"
AGENT_STATUS_ERROR = "error"
# 智能体状态在 Redis 中的默认过期时间（秒）
AGENT_STATUS_TTL = int(os.getenv("AGENT_STATUS_TTL", 86400))
# Agent 状态列表在 Redis 中的键名
AGENT_STATUS_LIST_KEY = "agents:status:list"
# Agent 状态列表的最大长度（保留最近的记录）
AGENT_STATUS_LIST_MAX_LEN = int(os.getenv("AGENT_STATUS_LIST_MAX_LEN", 1000))

# 消息压缩阈值（字符数）
# 长度 <= COMPRESS_LLM_LOWER：不压缩
# 长度在 (COMPRESS_LLM_LOWER, COMPRESS_LLM_UPPER]：LLM 总结压缩到 COMPRESS_LLM_TARGET 左右
# 长度 > COMPRESS_LLM_UPPER：先间隔提取 30% 行，再 LLM 总结压缩
COMPRESS_LLM_LOWER = int(os.getenv("COMPRESS_LLM_LOWER", 1000))
COMPRESS_LLM_UPPER = int(os.getenv("COMPRESS_LLM_UPPER", 5000))
COMPRESS_LLM_TARGET = int(os.getenv("COMPRESS_LLM_TARGET", 500))
# 保持旧名称兼容，供 _fallback_compression 间接使用
COMPRESS_TOOL_OUTPUT_LIMIT = COMPRESS_LLM_LOWER
COMPRESS_TOOL_INPUT_LIMIT = COMPRESS_LLM_LOWER


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
    # 缓存的状态快照，避免在查询时访问正在运行的agent实例
    _status_snapshot_cache: Dict[str, Dict[str, Any]] = {}

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
        cls._agent_cache.pop(chat_id, None)

    @classmethod
    def get_all_agents(cls) -> Dict[str, List["ChatAgent"]]:
        """获取所有缓存中的 agent（按 chat_id 分组）

        返回:
            Dict[str, List[ChatAgent]]: chat_id → agent 列表 的映射副本

        注意: 此方法仅用于维护操作，性能敏感的查询应使用 get_all_agents_status_snapshot()
        """
        with cls._cache_lock:
            return {k: list(v) for k, v in cls._agent_cache.items()}

    @classmethod
    def get_all_agents_status_snapshot(cls) -> List[Dict[str, Any]]:
        """获取所有agent的状态快照（性能优化版本）

        此方法通过读取预先缓存的状态快照来避免在查询时阻塞正在运行的agent。
        快照在agent更新状态时异步更新，因此此方法不会造成锁竞争。

        返回:
            List[Dict[str, Any]]: 所有agent的状态信息列表
        """
        with cls._cache_lock:
            # 快速复制快照字典，最小化锁持有时间
            snapshot = dict(cls._status_snapshot_cache)
        return list(snapshot.values())

    @classmethod
    def _update_status_snapshot(cls, agent_id: str, status_info: Dict[str, Any]) -> None:
        """更新agent的状态快照（内部方法）

        Args:
            agent_id: agent唯一标识
            status_info: 状态信息字典
        """
        with cls._cache_lock:
            cls._status_snapshot_cache[agent_id] = status_info.copy()

    @classmethod
    def _remove_status_snapshot(cls, agent_id: str) -> None:
        """移除agent的状态快照（内部方法）

        Args:
            agent_id: agent唯一标识
        """
        with cls._cache_lock:
            cls._status_snapshot_cache.pop(agent_id, None)

    def get_status_info(self) -> Dict[str, Any]:
        """获取当前 agent 的实时运行状态信息

        返回:
            Dict[str, Any]: 包含运行时间、任务信息、迭代轮次和 token 消耗等
        """
        elapsed = round(time.time() - self.start_time, 2) if self.start_time else 0
        status_info = {
            "agent_id": self.agentid,
            "chat_id": self.chat_id,
            "status": self.status,
            "model_name": self.model_name,
            "elapsed_time": elapsed,
            "task_text": self.task_text,
            "current_iteration": self.current_iteration,
            "max_iterations": self.max_tool_iterations,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "conversation_id": self.conversation_id,
        }
        # 更新状态快照（使用统一的内部方法）
        ChatAgent._update_status_snapshot(self.agentid, status_info)
        return status_info

    def _remove_from_cache(self) -> None:
        """从缓存中移除当前 agent（线程安全），防止内存泄漏"""
        with ChatAgent._cache_lock:
            if self.chat_id and self.chat_id in ChatAgent._agent_cache:
                ChatAgent._agent_cache[self.chat_id] = [
                    a
                    for a in ChatAgent._agent_cache[self.chat_id]
                    if a.agentid != self.agentid
                ]
                if not ChatAgent._agent_cache[self.chat_id]:
                    del ChatAgent._agent_cache[self.chat_id]
            # 同时移除状态快照
            ChatAgent._remove_status_snapshot(self.agentid)
        # 如果 agent 是 stopped/complete/error 状态，保留在 Redis 中供监控页面查看
        # 如果需要删除，应通过专门的删除接口（否则无法在监控页面看到历史记录）
        # 这里不主动删除 Redis 中的记录

    def stop(self) -> None:
        """停止 agent：设置停止标志并从缓存中移除自身，防止内存泄漏"""
        logger.info(f"Agent {self.agentid} 执行停止操作")
        self.stopped = True
        self._set_status(AGENT_STATUS_STOPPED)
        self._remove_from_cache()
        logger.info(f"Agent {self.agentid} 已停止并清理")

    def _chat_stopped_redis_key(self) -> str:
        """返回该会话在 Redis 中的停止标志键名"""
        return f"chat:{self.chat_id}:stopped"

    def _is_stopped(self) -> bool:
        """直接从 Redis 读取停止状态，失败时回退到内存属性"""
        if self.stopped:
            return True
        if not self.chat_id:
            return False
        try:
            redis_conn = get_redis_connection()
            return redis_conn.exists(self._chat_stopped_redis_key()) > 0
        except Exception as e:
            logger.error(f"Agent {self.agentid} 读取停止状态失败: {e}")
            return False

    def _check_and_handle_stopped(self, chat_id: str) -> bool:
        """检查是否需要停止，如果是则执行停止操作并返回 True

        统一的停止检查入口，合并了内存标志和 Redis 状态的检查逻辑，
        避免在工具调用循环中重复编写停止检查代码。

        Args:
            chat_id: 聊天会话ID

        Returns:
            bool: 如果 agent 已停止返回 True，否则返回 False
        """
        if self._is_stopped():
            logger.info(f"[{chat_id}] Agent 已停止，退出工具调用循环")
            self.stop()
            return True
        return False

    def _set_status(self, status: str) -> None:
        """将智能体状态写入 Redis（chat 级别），并更新内存属性和状态快照"""
        self.status = status
        try:
            if self.chat_id:
                redis_conn = get_redis_connection()
                redis_conn.set(
                    f"chat:{self.chat_id}:status", status, ex=AGENT_STATUS_TTL
                )
            logger.info(f"Agent {self.agentid} 状态更新为: {status}")
            # 状态变更时立即更新快照
            self._update_snapshot()
        except Exception as e:
            logger.error(f"Agent {self.agentid} 设置状态失败: {e}")

    def _update_snapshot(self) -> None:
        """更新当前agent的状态快照（内部方法，减少重复代码）"""
        elapsed = round(time.time() - self.start_time, 2) if self.start_time else 0
        status_info = {
            "agent_id": self.agentid,
            "chat_id": self.chat_id,
            "status": self.status,
            "model_name": self.model_name,
            "elapsed_time": elapsed,
            "task_text": self.task_text,
            "current_iteration": self.current_iteration,
            "max_iterations": self.max_tool_iterations,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "conversation_id": self.conversation_id,
            "updated_at": datetime.now().isoformat(),
        }
        ChatAgent._update_status_snapshot(self.agentid, status_info)
        # 同时持久化到 Redis hash（使用 agent_id 作为 field）
        try:
            redis_conn = get_redis_connection()
            # 使用 hash 存储，field 为 agent_id，value 为 json
            member = json.dumps(status_info, ensure_ascii=False)
            redis_conn.hset(AGENT_STATUS_LIST_KEY, self.agentid, member)
            # 设置过期时间
            redis_conn.expire(AGENT_STATUS_LIST_KEY, AGENT_STATUS_TTL)
        except Exception as e:
            logger.error(f"Agent {self.agentid} 持久化状态到 Redis 失败: {e}")

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
        self.status = AGENT_STATUS_INIT
        self.workspace_path = workspace_path
        # 延迟初始化的工具执行器（复用实例，避免每次调用重复创建）
        self._tool_executor = None
        self.chat_id = None  # 将在 _register_agent 中设置
        self._pending_tasks = set()
        # 运行时指标（用于实时状态查询）
        self.start_time: Optional[float] = None  # agent 开始运行的时间戳
        self.current_iteration: int = 0  # 当前工具调用迭代轮次
        self.total_input_tokens: int = 0  # 累计输入 token 消耗
        self.total_output_tokens: int = 0  # 累计输出 token 消耗
        self.task_text: Optional[str] = None  # 用户提交的任务/查询文本

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
        self._set_status(AGENT_STATUS_RUNNING)
        # 记录运行时指标
        self.start_time = time.time()
        self.task_text = text
        self.current_iteration = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0

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
                if self._check_and_handle_stopped(chat_id):
                    break
                try:
                    # 调用前检查：若 token 超过上下文窗口，先执行压缩
                    context_window = self._get_context_window_for_model()
                    pre_tokens = count_tokens(messages, model=self.model_name)
                    if pre_tokens > context_window:
                        logger.info(
                            f"[{chat_id}] 调用前检测到 token 超过上下文窗口 "
                            f"({pre_tokens}/{context_window})，先执行压缩"
                        )
                        if self.stream_manager:
                            await self.stream_manager.send_message(
                                chat_id,
                                await create_compress_start_event(pre_tokens),
                            )
                        messages = await self._compress_messages(
                            chat_id, messages, must_compress=True
                        )
                        compressed_tokens = count_tokens(messages, model=self.model_name)
                        logger.info(
                            f"[{chat_id}] 预压缩完成: {pre_tokens} -> {compressed_tokens} tokens"
                        )
                        if self.stream_manager:
                            await self.stream_manager.send_message(
                                chat_id,
                                await create_compress_complete_event(
                                    pre_tokens, compressed_tokens
                                ),
                            )

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

                    # 累计 token 消耗
                    self.total_input_tokens += accumulated_usage.get("prompt_tokens", 0)
                    self.total_output_tokens += accumulated_usage.get("completion_tokens", 0)
                    # token更新后立即更新快照
                    self._update_snapshot()

                    if self._check_and_handle_stopped(chat_id):
                        break

                    # 检查是否需要压缩（调用报错触发）
                    if need_compress:
                        logger.info(f"[{chat_id}] 触发消息压缩（token_limit_exceeded）")
                        original_tokens = count_tokens(messages, model=self.model_name)
                        # 发送压缩开始事件
                        if self.stream_manager:
                            await self.stream_manager.send_message(
                                chat_id,
                                await create_compress_start_event(original_tokens),
                            )

                        # 执行压缩（强制压缩）；失败时退化为简单消息移除
                        try:
                            messages = await self._compress_messages(
                                chat_id, messages, must_compress=True
                            )
                        except Exception as compress_err:
                            logger.warning(
                                f"[{chat_id}] 压缩失败，退化为简单消息移除: {compress_err}"
                            )
                            messages = await self._fallback_compression(
                                chat_id, messages, self._get_context_window_for_model()
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

                        # 压缩后重新执行当前迭代
                        logger.info(f"[{chat_id}] 压缩完成，重新执行当前迭代")
                        need_compress = False
                        continue

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
                    self.current_iteration = tool_iteration
                    # 迭代更新后立即更新快照
                    self._update_snapshot()
                    logger.info(
                        f"[{chat_id}] 完成第 {tool_iteration} 次工具调用，继续下一轮推理"
                    )

                except Exception as e:
                    logger.error(f"[{chat_id}] 迭代执行失败: {str(e)}", exc_info=True)
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
            self._set_status(AGENT_STATUS_COMPLETE)
            return final_response_text

        except Exception as e:
            error_msg = f"chat 模式处理失败: {str(e)}"
            logger.error(f"[{chat_id}] {error_msg}", exc_info=True)
            self._set_status(AGENT_STATUS_ERROR)

            if self.stream_manager:
                await self.stream_manager.send_message(
                    chat_id, await create_error_event(error_msg)
                )
                await self.stream_manager.send_message(
                    chat_id, await create_complete_event()
                )
            raise
        finally:
            # 确保状态不会遗留为 RUNNING
            if self.status == AGENT_STATUS_RUNNING:
                logger.warning(
                    f"Agent {self.agentid} 状态仍为 RUNNING，自动修正为 ERROR"
                )
                self._set_status(AGENT_STATUS_ERROR)
            # 从缓存中移除当前 agent，防止内存泄漏
            self._remove_from_cache()

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
                                if self.stream_manager:
                                    if chunk.get("is_end"):
                                        if thinking_buffer:
                                            event = await create_agent_stream_thinking_event(
                                                thinking_buffer
                                            )
                                            await self.stream_manager.send_message(
                                                chat_id, event
                                            )
                                            thinking_buffer = ""
                                        done_event = (
                                            await create_agent_stream_thinking_event(
                                                "[THINKING_DONE]"
                                            )
                                        )
                                        await self.stream_manager.send_message(
                                            chat_id, done_event
                                        )
                                        continue

                                thinking_content = chunk.get("content", "")
                                thinking_text += thinking_content
                                thinking_type = chunk.get("thinking_type")
                                # 累积到缓冲区

                                # 检查阈值并发送
                                if self.stream_manager:
                                    if BUFFER_THRESHOLD > 0:
                                        thinking_buffer += thinking_content
                                        if len(thinking_buffer) >= BUFFER_THRESHOLD:
                                            event = await create_agent_stream_thinking_event(
                                                thinking_buffer
                                            )
                                            await self.stream_manager.send_message(
                                                chat_id, event
                                            )
                                            thinking_buffer = ""
                                    else:
                                        if thinking_content:
                                            event = await create_agent_stream_thinking_event(
                                                thinking_content
                                            )
                                            await self.stream_manager.send_message(
                                                chat_id, event
                                            )

                            elif chunk_type == "reasoning_details":
                                reasoning_details = chunk.get("content", [])

                            elif chunk_type == "content":
                                content = chunk.get("content", "")
                                response_text += content
                                # 累积到缓冲区

                                if self.stream_manager:
                                    if BUFFER_THRESHOLD > 0:
                                        content_buffer += content
                                        if len(content_buffer) >= BUFFER_THRESHOLD:
                                            event = await create_agent_complete_event(
                                                content_buffer
                                            )
                                            await self.stream_manager.send_message(
                                                chat_id, event
                                            )
                                            content_buffer = ""
                                    else:
                                        if content:
                                            event = await create_agent_complete_event(
                                                content
                                            )
                                            await self.stream_manager.send_message(
                                                chat_id, event
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
                                if self.stream_manager:
                                    if chunk.get("is_end"):
                                        if thinking_buffer:
                                            event = await create_agent_stream_thinking_event(
                                                thinking_buffer
                                            )
                                            await self.stream_manager.send_message(
                                                chat_id, event
                                            )
                                            thinking_buffer = ""
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

                                # 检查阈值并发送
                                if self.stream_manager:
                                    if BUFFER_THRESHOLD > 0:
                                        thinking_buffer += thinking_content
                                        if len(thinking_buffer) >= BUFFER_THRESHOLD:
                                            event = await create_agent_stream_thinking_event(
                                                thinking_buffer
                                            )
                                            await self.stream_manager.send_message(
                                                chat_id, event
                                            )
                                            thinking_buffer = ""
                                    else:
                                        if thinking_content:
                                            event = await create_agent_stream_thinking_event(
                                                thinking_content
                                            )
                                            await self.stream_manager.send_message(
                                                chat_id, event
                                            )

                            elif chunk_type == "content":
                                content = chunk.get("content", "")
                                response_text += content

                                # 累积到缓冲区

                                if self.stream_manager:
                                    if BUFFER_THRESHOLD > 0:
                                        content_buffer += content
                                        if len(content_buffer) >= BUFFER_THRESHOLD:
                                            event = await create_agent_complete_event(
                                                content_buffer
                                            )
                                            await self.stream_manager.send_message(
                                                chat_id, event
                                            )
                                            content_buffer = ""
                                    else:
                                        if content:
                                            event = await create_agent_complete_event(
                                                content
                                            )
                                            await self.stream_manager.send_message(
                                                chat_id, event
                                            )

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

                    if content_buffer:
                        event = await create_agent_complete_event(content_buffer)
                        await self.stream_manager.send_message(chat_id, event)
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

    async def _compress_text(self, chat_id: str, text: str) -> str:
        """对单段文本按三档策略进行压缩。

        - 长度 <= COMPRESS_LLM_LOWER：原样返回，不压缩。
        - 长度在 (COMPRESS_LLM_LOWER, COMPRESS_LLM_UPPER]：直接 LLM 总结，目标约 COMPRESS_LLM_TARGET 字符。
        - 长度 > COMPRESS_LLM_UPPER：先按间隔提取全文 30% 的行，再 LLM 总结。
        """
        if len(text) <= COMPRESS_LLM_LOWER:
            return text

        if len(text) > COMPRESS_LLM_UPPER:
            # 间隔提取：按行等间隔抽取约 30%
            lines = text.splitlines()
            total = len(lines)
            keep = max(1, int(total * 0.3))
            step = max(1, total // keep)
            sampled = [lines[i] for i in range(0, total, step)]
            text = "\n".join(sampled)
            logger.info(
                f"[{chat_id}] 间隔提取压缩: 原始 {total} 行 → 抽取 {len(sampled)} 行"
            )

        prompt = (
            f"你是一个摘要助手。请对以下内容进行总结压缩，"
            f"保留核心信息，输出长度控制在 {COMPRESS_LLM_TARGET} 字符以内，"
            f"直接输出摘要内容，不要加任何前缀说明。\n\n"
            f"原始内容：\n{text}"
        )
        try:
            summary, _ = await call_llm_api(
                messages=[{"role": "user", "content": prompt}],
                model_name=self.model_name,
                request_id=f"compress-{chat_id}-{int(time.time())}",
                temperature=0.3,
            )
            return summary.strip()
        except Exception as e:
            logger.warning(f"[{chat_id}] LLM 压缩失败，保留原始文本前 {COMPRESS_LLM_TARGET} 字符: {e}")
            return text[:COMPRESS_LLM_TARGET]

    @langfuse_wrapper.dynamic_observe()
    async def _compress_messages(
        self, chat_id: str, messages: List[Dict[str, Any]], must_compress: bool = False
    ) -> List[Dict[str, Any]]:
        """消息压缩：只压缩工具消息的输入（assistant tool_calls）和输出（tool role）。

        触发条件：
        1. must_compress=True（调用报错 token_limit_exceeded 触发）
        2. token 数超过上下文窗口（调用前预检触发）

        压缩策略（三档）：
        - 长度 <= 1000：不压缩
        - 长度 1000~5000：LLM 总结到约 500 字符
        - 长度 > 5000：先间隔提取 30% 行，再 LLM 总结到约 500 字符

        其他消息（system、user、普通 assistant）不做压缩。
        """
        current_tokens = count_tokens(messages, model=self.model_name)
        context_window = self._get_context_window_for_model()

        if not must_compress and current_tokens <= context_window:
            logger.info(
                f"[{chat_id}] token 未超过上下文窗口 ({current_tokens}/{context_window})，无需压缩"
            )
            return messages

        logger.info(
            f"[{chat_id}] 开始压缩工具消息: {current_tokens}/{context_window}"
        )

        # 只压缩工具相关消息，其他消息保持不变
        compressed = []
        for msg in messages:
            role = msg.get("role")
            if role == "tool":
                # 压缩工具输出（三档策略）
                content = msg.get("content", "")
                if isinstance(content, str) and len(content) > COMPRESS_LLM_LOWER:
                    new_content = await self._compress_text(chat_id, content)
                    new_msg = msg.copy()
                    new_msg["content"] = new_content
                    compressed.append(new_msg)
                else:
                    compressed.append(msg)
            elif role == "assistant" and msg.get("tool_calls"):
                # 压缩工具调用参数（arguments 为 JSON 字符串，遍历其中的字符串值并压缩）
                new_tool_calls = []
                for tc in msg.get("tool_calls", []):
                    new_tc = dict(tc)
                    if "function" in new_tc:
                        fn = dict(new_tc["function"])
                        args_str = fn.get("arguments", "")
                        if isinstance(args_str, str) and len(args_str) > COMPRESS_LLM_LOWER:
                            try:
                                args_dict = json.loads(args_str)
                                if isinstance(args_dict, dict):
                                    new_args = {}
                                    for k, v in args_dict.items():
                                        if isinstance(v, str) and len(v) > COMPRESS_LLM_LOWER:
                                            new_args[k] = await self._compress_text(chat_id, v)
                                        else:
                                            new_args[k] = v
                                    fn["arguments"] = json.dumps(new_args, ensure_ascii=False)
                                else:
                                    # 非 dict 结构：整体压缩
                                    fn["arguments"] = await self._compress_text(chat_id, args_str)
                            except (json.JSONDecodeError, Exception) as e:
                                logger.warning(
                                    f"[{chat_id}] 解析 tool_calls arguments 失败，整体压缩: {e}"
                                )
                                fn["arguments"] = await self._compress_text(chat_id, args_str)
                        new_tc["function"] = fn
                    new_tool_calls.append(new_tc)
                new_msg = msg.copy()
                new_msg["tool_calls"] = new_tool_calls
                compressed.append(new_msg)
            else:
                # system、user、普通 assistant 消息不压缩
                compressed.append(msg)

        compressed_tokens = count_tokens(compressed, model=self.model_name)
        logger.info(
            f"[{chat_id}] 工具消息压缩后: {current_tokens} -> {compressed_tokens} tokens"
        )

        # 若压缩后仍超过上下文窗口，执行兜底压缩（移除旧消息）
        if compressed_tokens > context_window:
            logger.warning(
                f"[{chat_id}] 压缩后仍超过上下文窗口 ({compressed_tokens}/{context_window})，"
                f"执行兜底压缩"
            )
            compressed = await self._fallback_compression(
                chat_id, compressed, context_window
            )

        # 验证消息链完整性
        compressed = self._validate_and_fix_message_chain(compressed, chat_id)
        return compressed

    async def _fallback_compression(
        self, chat_id: str, messages: List[Dict[str, Any]], context_window: int
    ) -> List[Dict[str, Any]]:
        """兜底压缩策略：工具消息截断后仍超限时，逐步移除旧消息"""
        logger.warning(f"[{chat_id}] 执行兜底压缩策略")

        system_messages = [msg for msg in messages if msg.get("role") == "system"]
        other_messages = [msg for msg in messages if msg.get("role") != "system"]

        if len(other_messages) <= 2:
            return messages

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

        final_messages = (
            system_messages + other_messages[-1:] if other_messages else system_messages
        )
        logger.warning(f"[{chat_id}] 兜底压缩极端情况，仅保留最后一条非系统消息")
        return final_messages

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


from src.utils.dynamic_observer import auto_apply_here

auto_apply_here(
    globals(),
    include=None,
    exclude=[],
    only_in_module=True,
    verbose=False,
)
