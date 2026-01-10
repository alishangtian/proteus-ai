"""Chat Agent 模块 - 处理纯聊天模式的对话"""

import logging
import json
import time
import os
from string import Template
from datetime import datetime
from typing import Optional, List, Dict, Any
from src.api.stream_manager import StreamManager
from src.api.llm_api import call_llm_api_stream, call_llm_api_with_tools_stream
from src.utils.tool_converter import load_tools_from_yaml
from src.utils.langfuse_wrapper import langfuse_wrapper
from src.agent.prompt.chat_agent_system_prompt import CHAT_AGENT_SYSTEM_PROMPT
from src.agent.prompt.chat_agent_system_prompt_v2 import CHAT_AGENT_SYSTEM_PROMPT_V2
from src.utils.redis_cache import get_redis_connection
from src.manager.tool_memory_manager import ToolMemoryManager
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
)

logger = logging.getLogger(__name__)


class ChatAgent:
    """Chat Agent 类 - 处理纯聊天模式的对话

    该类封装了 chat 模式下的所有逻辑，包括：
    - 流式 LLM 调用
    - 工具调用支持
    - Thinking 内容处理
    - 对话历史管理
    """

    def __init__(
        self,
        stream_manager: StreamManager,
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
    ):
        """初始化 ChatAgent

        Args:
            stream_manager: 流管理器实例
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

        # 初始化工具记忆管理器
        self.tool_memory_manager = ToolMemoryManager()

        # 初始化skills记忆管理器
        self.user_name = user_name
        self.system_prompt = system_prompt or CHAT_AGENT_SYSTEM_PROMPT_V2

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

        try:
            # 发送 agent_start 事件
            if self.stream_manager:
                event = await create_agent_start_event(text)
                await self.stream_manager.send_message(chat_id, event)

            # 构建消息列表
            messages = []

            # 1. 先加载历史会话
            if self.conversation_id:
                conversation_history = conversation_manager.load_conversation_history(
                    self.conversation_id, max_messages=self.conversation_round * 3
                )
                # conversation_history = self._load_conversation_history()
                if conversation_history:
                    messages.extend(conversation_history)

            # 2. 检索相关skills记忆（如果启用）
            skills_memories = []
            if self.enable_skills_memory:
                skills_memories = await self._retrieve_skills_memories(chat_id, text)
            file_added = False
            # 如果messages为空就添加到第一条角色为 system
            all_values = {"CURRENT_TIME": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

            # 构建skills记忆内容
            skills_memories_content = self._build_skills_memories_content(
                skills_memories
            )
            all_values["SKILLS_MEMORIES"] = skills_memories_content
            all_values["LANGUAGE"] = os.getenv("LANGUAGE", "中文")

            if not messages:
                system_message = {
                    "role": "system",
                    "content": CHAT_AGENT_SYSTEM_PROMPT_V2,
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

            # 工具调用循环
            max_iterations = (
                self.max_tool_iterations if self.enable_tools and tools else 1
            )
            tool_iteration = 0
            while tool_iteration < max_iterations:
                # 执行一次 LLM 生成迭代
                (
                    response_text,
                    thinking_text,
                    tool_calls,
                    accumulated_usage,
                    thinking_type,
                    reasoning_details,
                ) = await self._execute_llm_generation(
                    chat_id=chat_id,
                    messages=self._filter_messages(
                        messages
                    ),  # 过滤消息，只保留最新的思考消息
                    tools=tools,
                    enable_thinking=enable_thinking,
                    tool_iteration=tool_iteration,
                )

                # 保存最终响应
                final_response_text = response_text

                # 如果没有工具调用，说明模型返回了最终答案，退出循环
                if not tool_calls:
                    logger.info(f"[{chat_id}] 模型返回最终答案，结束工具调用循环")
                    if thinking_text:
                        thought_message = {
                            "role": "assistant",
                            thinking_type: thinking_text,
                            "content": response_text,
                        }
                        messages.append(thought_message)
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
                    thinking_type: thinking_text,
                    "content": response_text,
                    "tool_calls": tool_calls,
                    "reasoning_details": reasoning_details,
                }
                messages.append(assistant_message)

                # 立即保存助手消息到 Redis（保存完整的 message 对象）
                if self.conversation_id:
                    conversation_manager.save_message(
                        conversation_id=self.conversation_id, message=assistant_message
                    )
                    # self._save_conversation_to_redis(message=assistant_message)
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
                        # self._save_conversation_to_redis(message=tool_msg)

                if self.conversation_id and tool_messages:
                    logger.info(
                        f"[{chat_id}] 已保存 {len(tool_messages)} 个工具调用结果到 Redis"
                    )

                # 增加迭代计数
                tool_iteration += 1
                logger.info(
                    f"[{chat_id}] 完成第 {tool_iteration} 次工具调用，继续下一轮推理"
                )

            # 发送完成事件
            if self.stream_manager:
                await self.stream_manager.send_message(
                    chat_id, await create_complete_event()
                )

            # 如果没有工具调用，保存最终的助手回答到 Redis
            # （如果有工具调用，助手消息已经在工具调用循环中保存了）
            if self.conversation_id:
                # 构建最终助手消息对象
                final_assistant_message = {
                    "role": "assistant",
                    "content": final_response_text,
                }
                conversation_manager.save_message(
                    self.conversation_id, final_assistant_message
                )
                # self._save_conversation_to_redis(message=final_assistant_message)
                logger.info(f"[{chat_id}] 已保存最终助手回答到 Redis")

            logger.info(f"[{chat_id}] chat 模式请求完成（流式）")

            # 异步处理skills记忆生成（如果启用且成功解决问题）
            if self.enable_skills_memory and final_response_text:
                await self._async_process_skills_memory(
                    chat_id=chat_id,
                    user_query=text,
                    final_result=final_response_text,
                    tool_calls_history=self._get_tool_calls_from_messages(messages),
                    is_success=True,
                )

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

            # 如果启用了工具记忆，为每个工具附加记忆信息
            if self.enable_tool_memory and tools:
                for tool in tools:
                    tool_name = tool["function"]["name"]
                    # 异步加载工具记忆
                    tool_memory = await self.tool_memory_manager.load_tool_memory(
                        tool_name=tool_name, user_name=self.user_name
                    )
                    if tool_memory:
                        # 将工具记忆附加到工具描述中
                        original_description = tool["function"]["description"]
                        enhanced_description = (
                            f"{original_description}\n\n"
                            f"【工具使用经验】{tool_memory}"
                        )
                        tool["function"]["description"] = enhanced_description
                        logger.info(f"[{chat_id}] 为工具 '{tool_name}' 附加了使用经验")

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
        first_content_chunk_sent = False
        has_thinking_content = False
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
                                has_thinking_content = True
                                thinking_content = chunk.get("content", "")
                                thinking_text += thinking_content
                                thinking_type = chunk.get("thinking_type")
                                if self.stream_manager and thinking_content:
                                    event = await create_agent_stream_thinking_event(
                                        thinking_content
                                    )
                                    await self.stream_manager.send_message(
                                        chat_id, event
                                    )

                            if chunk_type == "reasoning_details":
                                reasoning_details = chunk.get("content", [])

                            if chunk_type == "content":
                                if (
                                    not first_content_chunk_sent
                                    and has_thinking_content
                                ):
                                    first_content_chunk_sent = True
                                    if self.stream_manager:
                                        event = (
                                            await create_agent_stream_thinking_event(
                                                "[THINKING_DONE]"
                                            )
                                        )
                                        await self.stream_manager.send_message(
                                            chat_id, event
                                        )
                                content = chunk.get("content", "")
                                response_text += content
                                if self.stream_manager and content:
                                    event = await create_agent_complete_event(content)
                                    await self.stream_manager.send_message(
                                        chat_id, event
                                    )

                            if chunk_type == "tool_calls":
                                if (
                                    not first_content_chunk_sent
                                    and has_thinking_content
                                ):
                                    first_content_chunk_sent = True
                                    if self.stream_manager:
                                        event = (
                                            await create_agent_stream_thinking_event(
                                                "[THINKING_DONE]"
                                            )
                                        )
                                        await self.stream_manager.send_message(
                                            chat_id, event
                                        )
                                tool_calls = chunk.get("tool_calls", [])
                                logger.info(
                                    f"[{chat_id}] 模型请求调用 {len(tool_calls)} 个工具"
                                )
                                for tool_call in tool_calls:
                                    if tool_call.get("id") is None:
                                        tool_call["id"] = "call_" + str(uuid.uuid4())

                            if chunk_type == "usage":
                                if (
                                    not first_content_chunk_sent
                                    and has_thinking_content
                                ):
                                    first_content_chunk_sent = True
                                    if self.stream_manager:
                                        event = (
                                            await create_agent_stream_thinking_event(
                                                "[THINKING_DONE]"
                                            )
                                        )
                                        await self.stream_manager.send_message(
                                            chat_id, event
                                        )
                                accumulated_usage = chunk.get("usage", {})
                                logger.info(
                                    f"[{chat_id}] Token 使用情况: {accumulated_usage}"
                                )
                                if self.stream_manager and accumulated_usage:
                                    event = await create_usage_event(accumulated_usage)
                                    await self.stream_manager.send_message(
                                        chat_id, event
                                    )

                            if chunk_type == "retry":
                                retry_msg = chunk.get("error", "未知错误")
                                logger.error(f"[{chat_id}] 流式调用错误: {retry_msg}")
                                if self.stream_manager:
                                    await self.stream_manager.send_message(
                                        chat_id, await create_retry_event(retry_msg)
                                    )

                            if chunk_type == "error":
                                if (
                                    not first_content_chunk_sent
                                    and has_thinking_content
                                ):
                                    first_content_chunk_sent = True
                                    if self.stream_manager:
                                        event = (
                                            await create_agent_stream_thinking_event(
                                                "[THINKING_DONE]"
                                            )
                                        )
                                        await self.stream_manager.send_message(
                                            chat_id, event
                                        )
                                error_msg = chunk.get("error", "未知错误")
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
                                has_thinking_content = True
                                thinking_content = chunk.get("content", "")
                                thinking_text += thinking_content
                                thinking_type = chunk.get("thinking_type")
                                if self.stream_manager and thinking_content:
                                    event = await create_agent_stream_thinking_event(
                                        thinking_content
                                    )
                                    await self.stream_manager.send_message(
                                        chat_id, event
                                    )

                            if chunk_type == "content":
                                if (
                                    not first_content_chunk_sent
                                    and has_thinking_content
                                ):
                                    first_content_chunk_sent = True
                                    if self.stream_manager:
                                        event = (
                                            await create_agent_stream_thinking_event(
                                                "[THINKING_DONE]"
                                            )
                                        )
                                        await self.stream_manager.send_message(
                                            chat_id, event
                                        )
                                content = chunk.get("content", "")
                                response_text += content
                                if self.stream_manager and content:
                                    event = await create_agent_complete_event(content)
                                    await self.stream_manager.send_message(
                                        chat_id, event
                                    )

                            if chunk_type == "usage":
                                accumulated_usage = chunk.get("usage", {})
                                logger.info(
                                    f"[{chat_id}] Token 使用情况: {accumulated_usage}"
                                )
                                if self.stream_manager and accumulated_usage:
                                    event = await create_usage_event(accumulated_usage)
                                    await self.stream_manager.send_message(
                                        chat_id, event
                                    )

                            if chunk_type == "retry":
                                retry_msg = chunk.get("error", "未知错误")
                                logger.error(f"[{chat_id}] 流式调用错误: {retry_msg}")
                                if self.stream_manager:
                                    await self.stream_manager.send_message(
                                        chat_id, await create_retry_event(retry_msg)
                                    )

                            if chunk_type == "error":
                                error_msg = chunk.get("error", "未知错误")
                                logger.error(f"[{chat_id}] 流式调用错误: {error_msg}")
                                if self.stream_manager:
                                    await self.stream_manager.send_message(
                                        chat_id, await create_error_event(error_msg)
                                    )
                                raise Exception(error_msg)

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
            )

        except Exception as e:
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

        tool_executor = ToolExecutor(
            stream_manager=self.stream_manager,
            max_retries=3,
            retry_delay=1.0,
        )

        # 批量执行工具调用并收集结果
        start_time = time.time()
        tool_messages = await tool_executor.execute_tool_calls(
            tool_calls=tool_calls, chat_id=chat_id
        )
        execution_time = time.time() - start_time

        logger.info(
            f"[{chat_id}] 工具执行完成 (iteration {tool_iteration}, 耗时: {execution_time:.2f}s)"
        )

        # 异步处理工具记忆更新（不阻塞主流程）
        if self.enable_tool_memory:
            await self._async_process_tool_memory(
                chat_id=chat_id,
                tool_calls=tool_calls,
                tool_messages=tool_messages,
                tool_iteration=tool_iteration,
                user_name=self.user_name,
            )

        return tool_messages

    @langfuse_wrapper.dynamic_observe()
    async def _async_process_tool_memory(
        self,
        chat_id: str,
        tool_calls: List[Dict],
        tool_messages: List[Dict[str, Any]],
        tool_iteration: int,
        user_name: str,
    ) -> None:
        """异步处理工具记忆更新

        Args:
            chat_id: 聊天会话ID
            tool_calls: 工具调用列表
            tool_messages: 工具执行结果消息列表
            tool_iteration: 当前迭代次数
        """
        try:
            # 构建工具调用和结果的映射
            tool_results = {}
            for tool_msg in tool_messages:
                if tool_msg.get("role") == "tool":
                    tool_call_id = tool_msg.get("tool_call_id")
                    tool_results[tool_call_id] = {
                        "content": tool_msg.get("content", ""),
                        "name": tool_msg.get("name", ""),
                    }

            # 为每个工具调用异步处理记忆
            for tool_call in tool_calls:
                tool_call_id = tool_call.get("id")
                tool_name = tool_call.get("function", {}).get("name")
                action_input = tool_call.get("function", {}).get("arguments", {})

                # 解析参数
                try:
                    if isinstance(action_input, str):
                        action_input = json.loads(action_input)
                except (json.JSONDecodeError, TypeError):
                    action_input = {}

                # 获取工具执行结果
                tool_result = tool_results.get(tool_call_id, {})
                observation = tool_result.get("content", "")

                # 异步调用工具记忆处理（不阻塞主流程）
                import asyncio

                asyncio.create_task(
                    self._process_single_tool_memory(
                        chat_id=chat_id,
                        tool_name=tool_name,
                        action_input=action_input,
                        observation=observation,
                        tool_iteration=tool_iteration,
                    )
                )

            logger.info(f"[{chat_id}] 已启动 {len(tool_calls)} 个工具的记忆异步处理")

        except Exception as e:
            logger.error(f"[{chat_id}] 异步处理工具记忆失败: {str(e)}", exc_info=True)

    @langfuse_wrapper.dynamic_observe()
    async def _process_single_tool_memory(
        self,
        chat_id: str,
        tool_name: str,
        action_input: Dict[str, Any],
        observation: str,
        is_error: bool = False,
        error_message: str = None,
        tool_iteration: int = 25,
    ) -> str:
        """处理单个工具的记忆更新

        Args:
            chat_id: 聊天会话ID
            tool_name: 工具名称
            action_input: 工具输入参数
            observation: 工具执行结果
            is_error: 是否为错误执行
            error_message: 错误信息
            tool_iteration: 当前迭代次数
        """
        try:
            # 获取当前用户输入（从对话历史中获取）
            user_query = await self._get_current_user_query()

            # 调用工具记忆管理器处理记忆
            result = await self.tool_memory_manager.process_tool_memory(
                tool_name=tool_name,
                action_input=action_input,
                observation=observation,
                chat_id=chat_id,
                is_error=is_error,
                error_message=error_message,
                user_query=user_query,
                model_name=self.model_name,
                conversation_id=self.conversation_id,
                user_name=self.user_name,
            )

            logger.info(
                f"[{chat_id}] 工具 '{tool_name}' 的记忆处理完成 (iteration {tool_iteration})"
            )

            return result

        except Exception as e:
            logger.error(
                f"[{chat_id}] 处理工具 '{tool_name}' 记忆失败: {str(e)}", exc_info=True
            )

    def _filter_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        过滤 messages 列表，只保留最新的一个包含 'reasoning' 或 'reasoning_content' 字段的消息。
        如果原始 messages 列表不包含这些字段的消息，则返回原始列表。
        """
        # 创建可修改的副本
        processed_messages = messages[:]

        # 找到所有包含 'reasoning' 或 'reasoning_content' 字段，且不包含 'tool_calls' 字段的消息的索引
        removable_thinking_message_indices = []
        for i, message in enumerate(processed_messages):
            is_thinking_message = isinstance(message, dict) and any(
                key in message for key in ["reasoning", "reasoning_content"]
            )
            has_tool_calls = (
                isinstance(message, dict)
                and "tool_calls" in message
                and message["tool_calls"] is not None
            )

            if is_thinking_message and not has_tool_calls:
                removable_thinking_message_indices.append(i)

        # 如果可移除的思考消息的数量大于1，则移除最靠前的那个
        if len(removable_thinking_message_indices) > 1:
            first_removable_thinking_message_index = removable_thinking_message_indices[
                0
            ]
            del processed_messages[first_removable_thinking_message_index]
            logger.info(
                f"移除了最靠前的思考消息（不含tool_calls），原索引: {first_removable_thinking_message_index}"
            )

        return processed_messages

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

    @langfuse_wrapper.dynamic_observe()
    def _save_conversation_to_redis(
        self,
        message: Dict[str, Any],
        expire_hours: int = 12,
        max_retries: int = 3,
        retry_delay: float = 0.1,
    ):
        """将完整的 message 对象保存到 Redis list 中，保持与运行时 messages 结构严格一致

        Args:
            message: 完整的消息对象，格式与 messages 列表中的元素完全一致
                    例如: {"role": "user", "content": "..."}
                         {"role": "assistant", "content": "...", "tool_calls": [...]}
                         {"role": "tool", "content": "...", "tool_call_id": "...", "name": "..."}
            expire_hours: 过期时间（小时），默认12小时
            max_retries: 最大重试次数，默认3次
            retry_delay: 重试延迟时间（秒），默认0.1秒
        """
        retry_count = 0
        last_exception = None

        while retry_count <= max_retries:
            try:
                redis_cache = get_redis_connection()
                redis_key = f"conversation:{self.conversation_id}"
                current_timestamp = time.time()

                # 构造记录：保存完整的 message 对象 + 时间戳
                record = {
                    "timestamp": current_timestamp,
                    "message": message,  # 直接保存完整的 message 对象
                }

                # 转换为JSON字符串并添加到list右端
                record_json = json.dumps(record, ensure_ascii=False)
                redis_cache.rpush(redis_key, record_json)

                # 设置过期时间
                redis_cache.expire(redis_key, expire_hours * 3600)

                # 获取当前数量并限制总数量：保留最新的100条
                total_count = redis_cache.llen(redis_key)
                if total_count > 100:
                    # 从左端删除多余的旧记录
                    excess_count = total_count - 100
                    for _ in range(excess_count):
                        redis_cache.lpop(redis_key)

                logger.info(
                    f"成功保存消息到 Redis (conversation_id: {self.conversation_id}, "
                    f"role: {message.get('role')}, timestamp: {current_timestamp}, total_items: {min(total_count, 100)})"
                )
                return {"result": "success"}  # 成功则直接返回

            except Exception as e:
                last_exception = e
                retry_count += 1
                logger.warning(
                    f"保存到Redis失败 (尝试 {retry_count}/{max_retries}): {str(e)}"
                )
                if retry_count <= max_retries:
                    time.sleep(retry_delay)

        # 所有重试都失败
        logger.error(
            f"保存消息到 Redis 失败 (conversation_id: {self.conversation_id}): {str(last_exception)}"
        )
        raise last_exception

    @langfuse_wrapper.dynamic_observe()
    def _load_conversation_history(
        self, expire_hours: int = 12
    ) -> List[Dict[str, Any]]:
        """从 Redis list 中加载完整的对话历史记录，返回与运行时 messages 结构完全一致的数据

        Args:
            expire_hours: 过期时间（小时），默认12小时

        Returns:
            List[Dict[str, Any]]: 对话历史列表，格式与 messages 完全一致
        """
        try:
            redis_cache = get_redis_connection()
            redis_key = f"conversation:{self.conversation_id}"

            # 检查key是否存在
            if not redis_cache.exists(redis_key):
                logger.info(f"未找到对话历史 (conversation_id: {self.conversation_id})")
                return []

            # 获取list长度
            total_count = redis_cache.llen(redis_key)
            if total_count == 0:
                return []

            # 计算要获取的记录数量：获取最近的所有记录（包括工具调用）
            # 由于工具调用会增加额外的记录，这里获取更多的记录
            records_to_get = min(
                self.conversation_round * 6, total_count
            )  # 每轮可能包含多个工具调用

            # 从list右端获取最新的records_to_get条记录
            start_index = max(0, total_count - records_to_get)
            end_index = total_count - 1

            # 获取历史记录
            history_data = redis_cache.lrange(redis_key, start_index, end_index)

            # 解析并过滤过期数据，直接返回完整的 message 对象
            conversation_history: List[Dict[str, Any]] = []
            current_time = time.time()
            expire_timestamp = current_time - (expire_hours * 3600)

            for item_json in history_data:
                try:
                    record = json.loads(item_json)
                    # 检查是否过期
                    record_timestamp = record.get("timestamp", current_time)
                    if record_timestamp < expire_timestamp:
                        continue

                    # 直接获取完整的 message 对象
                    message = record.get("message")
                    if message:
                        conversation_history.append(message)
                except (json.JSONDecodeError, Exception) as e:
                    logger.warning(f"解析对话历史失败: {e}")
                    continue

            if conversation_history:
                logger.info(
                    f"成功加载 {len(conversation_history)} 条对话历史记录 (conversation_id: {self.conversation_id})"
                )
            return conversation_history

        except Exception as e:
            logger.error(f"加载对话历史失败: {e}")
            return []

    @langfuse_wrapper.dynamic_observe()
    def _build_skills_memories_content(
        self, skills_memories: List[Dict[str, Any]]
    ) -> str:
        """构建skills记忆内容，用于模板替换

        根据 skills_manager 的两级召回结构，从返回的 skill 详情中提取：
        - skill_description: 技能描述（简洁说明）
        - skill_detail: 技能详情（详细步骤和注意事项）
        - user_query: 原始用户问题
        - tool_count: 工具调用数量
        - similarity_score: 相似度分数（如果有）

        Args:
            skills_memories: 相关skills记忆列表，来自两级召回的结果

        Returns:
            str: 格式化的skills记忆内容
        """
        if not skills_memories or not self.enable_skills_memory:
            return "暂无相关经验可供参考。"

        # 构建skills记忆标题
        skills_content = ""

        for i, memory in enumerate(skills_memories, 1):
            metadata = memory.get("metadata", {})

            # 提取核心字段
            skill_description = metadata.get("skill_description", "")
            skill_detail = metadata.get("skill_detail", "")
            user_query = metadata.get("user_query", "")
            tool_count = metadata.get("tool_count", 0)

            # 提取相似度分数（两级召回的综合分数）
            similarity_score = memory.get("similarity_score", 0.0)
            first_stage_score = memory.get("first_stage_score", 0.0)
            second_stage_score = memory.get("second_stage_score", 0.0)

            # 跳过无效的记忆
            if not skill_description and not skill_detail:
                continue

            # 构建标题（包含相似度信息）
            skills_content += f"## 技能 {i}: {skill_description}\n"
            skills_content += f"**相似度**: {similarity_score:.2%}"
            if first_stage_score > 0 or second_stage_score > 0:
                skills_content += f" (描述匹配: {first_stage_score:.2%}, 详情匹配: {second_stage_score:.2%})"
            skills_content += "\n\n"

            # 添加原始问题（提供上下文）
            if user_query:
                skills_content += f"**原始问题**: {user_query}\n\n"

            # 添加技能详情（包含具体步骤和注意事项）
            if skill_detail:
                skills_content += f"**执行步骤与要点**:\n{skill_detail}\n\n"
            elif skill_description:
                # 如果没有详情，至少显示描述
                skills_content += f"**技能说明**: {skill_description}\n\n"

            # 添加工具数量信息
            if tool_count > 0:
                skills_content += f"**工具使用**: 涉及 {tool_count} 个工具调用\n\n"

            skills_content += "---\n\n"

        # 添加使用指导
        skills_content += (
            "**💡 使用建议**:\n"
            "1. 参考上述经验中的解决思路和步骤\n"
            "2. 根据当前问题的具体情况灵活调整工具调用链路\n"
            "3. 注意经验中提到的关键参数和注意事项\n"
            "4. 优先考虑相似度较高的经验\n"
        )

        return skills_content

    @langfuse_wrapper.dynamic_observe()
    async def _retrieve_skills_memories(
        self, chat_id: str, user_query: str
    ) -> List[Dict[str, Any]]:
        """检索与用户查询相关的skills记忆

        Args:
            chat_id: 聊天会话ID
            user_query: 用户查询文本

        Returns:
            List[Dict]: 相关skills记忆列表
        """
        try:
            # 使用用户查询作为搜索条件检索相关skills记忆
            skills_memories = await self.skills_manager.search_skills(
                query=user_query,
                n_results=3,  # 返回最相关的3个skills记忆
                user_name=None,  # 暂时使用全局记忆，后续可支持用户隔离
            )

            logger.info(f"[{chat_id}] 检索到 {len(skills_memories)} 个相关skills记忆")
            return skills_memories

        except Exception as e:
            logger.error(f"[{chat_id}] 检索skills记忆失败: {str(e)}", exc_info=True)
            return []

    def _get_tool_calls_from_messages(
        self, messages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """从消息历史中提取工具调用链信息

        Args:
            messages: 消息历史列表

        Returns:
            List[Dict]: 工具调用链信息
        """
        tool_chain = []

        for message in messages:
            if message.get("role") == "assistant" and message.get("tool_calls"):
                for tool_call in message["tool_calls"]:
                    function = tool_call.get("function", {})
                    tool_name = function.get("name", "")
                    arguments = function.get("arguments", "{}")

                    # 解析参数
                    try:
                        if isinstance(arguments, str):
                            action_input = json.loads(arguments)
                        else:
                            action_input = arguments
                    except (json.JSONDecodeError, TypeError):
                        action_input = {}

                    tool_chain.append(
                        {"tool_name": tool_name, "action_input": action_input}
                    )

        return tool_chain

    @langfuse_wrapper.dynamic_observe()
    async def _async_process_skills_memory(
        self,
        chat_id: str,
        user_query: str,
        final_result: str,
        tool_calls_history: List[Dict[str, Any]],
        is_success: bool = True,
    ) -> None:
        """异步处理skills记忆生成和保存

        Args:
            chat_id: 聊天会话ID
            user_query: 用户原始查询
            final_result: 最终结果
            tool_calls_history: 工具调用历史
            is_success: 是否成功解决
        """
        try:
            # 只在成功解决问题且有工具调用时生成skills记忆
            if not is_success or not tool_calls_history:
                return

            # 异步调用skills记忆处理
            import asyncio

            asyncio.create_task(
                self._process_single_skills_memory(
                    chat_id=chat_id,
                    user_query=user_query,
                    tool_chain=tool_calls_history,
                    final_result=final_result,
                )
            )

            logger.info(f"[{chat_id}] 已启动skills记忆异步处理")

        except Exception as e:
            logger.error(f"[{chat_id}] 启动skills记忆处理失败: {str(e)}", exc_info=True)

    @langfuse_wrapper.dynamic_observe()
    async def _process_single_skills_memory(
        self,
        chat_id: str,
        user_query: str,
        tool_chain: List[Dict[str, Any]],
        final_result: str,
    ) -> None:
        """处理单个skills记忆的生成和保存

        Args:
            chat_id: 聊天会话ID
            user_query: 用户原始查询
            tool_chain: 工具调用链
            final_result: 最终结果
            is_success: 是否成功解决
        """
        try:
            # 调用skills记忆管理器处理记忆
            skills_experience = await self.skills_manager.process_and_save_skill(
                user_query=user_query,
                tool_chain=tool_chain,
                final_result=final_result,
                user_name=self.user_name,
                model_name=self.model_name,
            )

            if skills_experience:
                logger.info(
                    f"[{chat_id}] skills记忆生成成功: {skills_experience[:100]}..."
                )
            else:
                logger.info(f"[{chat_id}] 未生成新的skills记忆")

        except Exception as e:
            logger.error(f"[{chat_id}] 处理skills记忆失败: {str(e)}", exc_info=True)


from src.utils.dynamic_observer import auto_apply_here

auto_apply_here(
    globals(),
    include=None,
    exclude=[],
    only_in_module=True,
    verbose=False,
)
