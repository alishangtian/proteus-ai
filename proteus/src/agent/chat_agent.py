"""Chat Agent 模块 - 处理纯聊天模式的对话"""

import logging
import json
import time
from typing import Optional, List, Dict, Any
from src.api.stream_manager import StreamManager
from src.api.llm_api import call_llm_api_stream, call_llm_api_with_tools_stream
from src.utils.tool_converter import load_tools_from_yaml
from src.utils.langfuse_wrapper import langfuse_wrapper
from src.utils.redis_cache import get_redis_connection
from src.api.events import (
    create_agent_start_event,
    create_agent_complete_event,
    create_agent_stream_thinking_event,
    create_complete_event,
    create_error_event,
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
    ):
        """初始化 ChatAgent

        Args:
            stream_manager: 流管理器实例
            model_name: 模型名称，默认为 "deepseek-chat"
            enable_tools: 是否启用工具调用
            tool_choices: 指定的工具列表
            max_tool_iterations: 最大工具调用迭代次数
        """
        self.stream_manager = stream_manager
        self.model_name = model_name or "deepseek-chat"
        self.enable_tools = enable_tools
        self.tool_choices = tool_choices
        self.max_tool_iterations = max_tool_iterations
        self.logger = logger
        self.conversation_id = conversation_id
        self.conversation_round = conversation_round

    @langfuse_wrapper.observe_decorator(
        name="load_tools_with_tracking", capture_input=True, capture_output=True
    )
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
                self.logger.info(f"[{chat_id}] 加载指定工具: {self.tool_choices}")
            else:
                # 加载所有工具
                tools = load_tools_from_yaml()
                self.logger.info(f"[{chat_id}] 加载所有可用工具")

            # 构建工具映射
            for tool in tools:
                tool_map[tool["function"]["name"]] = tool

            self.logger.info(f"[{chat_id}] 成功加载 {len(tools)} 个工具")
        except Exception as e:
            self.logger.error(f"[{chat_id}] 加载工具失败: {str(e)}")
            tools = None
            raise

        return tools, tool_map

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
                                if self.stream_manager and thinking_content:
                                    event = await create_agent_stream_thinking_event(
                                        thinking_content
                                    )
                                    await self.stream_manager.send_message(
                                        chat_id, event
                                    )

                            elif chunk_type == "content":
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

                            elif chunk_type == "tool_calls":
                                tool_calls = chunk.get("tool_calls", [])
                                self.logger.info(
                                    f"[{chat_id}] 模型请求调用 {len(tool_calls)} 个工具"
                                )

                            elif chunk_type == "usage":
                                accumulated_usage = chunk.get("usage", {})
                                self.logger.info(
                                    f"[{chat_id}] Token 使用情况: {accumulated_usage}"
                                )

                            elif chunk_type == "error":
                                error_msg = chunk.get("error", "未知错误")
                                self.logger.error(
                                    f"[{chat_id}] 流式调用错误: {error_msg}"
                                )
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
                                if self.stream_manager and thinking_content:
                                    event = await create_agent_stream_thinking_event(
                                        thinking_content
                                    )
                                    await self.stream_manager.send_message(
                                        chat_id, event
                                    )

                            elif chunk_type == "content":
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

                            elif chunk_type == "usage":
                                accumulated_usage = chunk.get("usage", {})
                                self.logger.info(
                                    f"[{chat_id}] Token 使用情况: {accumulated_usage}"
                                )

                            elif chunk_type == "error":
                                error_msg = chunk.get("error", "未知错误")
                                self.logger.error(
                                    f"[{chat_id}] 流式调用错误: {error_msg}"
                                )
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

                    self.logger.info(
                        f"[{chat_id}] LLM生成完成 (iteration {tool_iteration}, "
                        f"耗时: {execution_time:.2f}s, tokens: {usage_details['input_usage']+usage_details['output_usage']})"
                    )

            return response_text, thinking_text, tool_calls, accumulated_usage

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
                    self.logger.warning(
                        f"Failed to update generation span: {update_error}"
                    )

            self.logger.error(f"[{chat_id}] LLM生成失败: {str(e)}", exc_info=True)
            raise

    @langfuse_wrapper.observe_decorator(
        name="execute_tools", capture_input=True, capture_output=True
    )
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

        self.logger.info(
            f"[{chat_id}] 工具执行完成 (iteration {tool_iteration}, 耗时: {execution_time:.2f}s)"
        )

        return tool_messages

    @langfuse_wrapper.observe_decorator(
        name="chat_agent_run", capture_input=True, capture_output=True
    )
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
        self.logger.info(
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
                conversation_history = self._load_conversation_history()
                if conversation_history:
                    messages.extend(conversation_history)

            # 2. 添加文件上下文（如果有）
            if file_analysis_context:
                system_message = {
                    "role": "system",
                    "content": f"用户上传了以下文件内容：\n{file_analysis_context}",
                }
                messages.append(system_message)

                # 立即保存 system 消息到 Redis
                if self.conversation_id:
                    self._save_conversation_to_redis(message=system_message)
                    self.logger.info(f"[{chat_id}] 已保存文件上下文消息到 Redis")

            # 3. 添加当前用户消息
            user_message = {"role": "user", "content": text}
            messages.append(user_message)

            # 立即保存用户消息到 Redis（保存完整的 message 对象）
            if self.conversation_id:
                self._save_conversation_to_redis(message=user_message)
                self.logger.info(f"[{chat_id}] 已保存用户消息到 Redis")

            # 加载工具（如果启用）
            tools = None
            tool_map = {}
            if self.enable_tools:
                tools, tool_map = await self._load_tools_with_tracking(chat_id)

            # chat 模式下，始终传递 enable_thinking=True，让 API 层根据响应决定
            enable_thinking = True

            self.logger.info(
                f"[{chat_id}] chat 模式使用模型: {self.model_name}，将根据 API 响应自动处理 thinking 内容"
            )

            # 工具调用循环
            max_iterations = (
                self.max_tool_iterations if self.enable_tools and tools else 1
            )
            tool_iteration = 0
            final_response_text = ""
            final_thinking_text = ""
            accumulated_usage = {}

            while tool_iteration < max_iterations:
                # 执行一次 LLM 生成迭代
                (
                    response_text,
                    thinking_text,
                    tool_calls,
                    accumulated_usage,
                ) = await self._execute_llm_generation(
                    chat_id=chat_id,
                    messages=messages,
                    tools=tools,
                    enable_thinking=enable_thinking,
                    tool_iteration=tool_iteration,
                )

                # 保存最终响应
                final_response_text = response_text
                final_thinking_text = thinking_text

                # 如果没有工具调用，说明模型返回了最终答案，退出循环
                if not tool_calls:
                    self.logger.info(f"[{chat_id}] 模型返回最终答案，结束工具调用循环")
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
                    "content": response_text if response_text else None,
                    "tool_calls": tool_calls,
                }
                messages.append(assistant_message)

                # 立即保存助手消息到 Redis（保存完整的 message 对象）
                if self.conversation_id:
                    self._save_conversation_to_redis(message=assistant_message)
                    self.logger.info(
                        f"[{chat_id}] 已保存助手消息（包含 {len(tool_calls)} 个工具调用）到 Redis"
                    )

                # 将工具结果添加到messages，并立即保存到 Redis
                for tool_msg in tool_messages:
                    messages.append(tool_msg)
                    # 立即保存每个工具调用结果到 Redis（保存完整的 message 对象）
                    if self.conversation_id:
                        self._save_conversation_to_redis(message=tool_msg)

                if self.conversation_id and tool_messages:
                    self.logger.info(
                        f"[{chat_id}] 已保存 {len(tool_messages)} 个工具调用结果到 Redis"
                    )

                # 增加迭代计数
                tool_iteration += 1
                self.logger.info(
                    f"[{chat_id}] 完成第 {tool_iteration} 次工具调用，继续下一轮推理"
                )

            # 发送完成事件
            if self.stream_manager:
                await self.stream_manager.send_message(
                    chat_id, await create_complete_event()
                )

            # 如果没有工具调用，保存最终的助手回答到 Redis
            # （如果有工具调用，助手消息已经在工具调用循环中保存了）
            if self.conversation_id and tool_iteration == 0:
                # 构建最终助手消息对象
                final_assistant_message = {
                    "role": "assistant",
                    "content": final_response_text,
                }

                self._save_conversation_to_redis(message=final_assistant_message)
                self.logger.info(f"[{chat_id}] 已保存最终助手回答到 Redis")

            self.logger.info(f"[{chat_id}] chat 模式请求完成（流式）")

            return final_response_text

        except Exception as e:
            error_msg = f"chat 模式处理失败: {str(e)}"
            self.logger.error(f"[{chat_id}] {error_msg}", exc_info=True)

            if self.stream_manager:
                await self.stream_manager.send_message(
                    chat_id, await create_error_event(error_msg)
                )
            raise

    @langfuse_wrapper.observe_decorator(
        name="_save_conversation_to_redis", capture_input=True, capture_output=True
    )
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

                self.logger.info(
                    f"成功保存消息到 Redis (conversation_id: {self.conversation_id}, "
                    f"role: {message.get('role')}, timestamp: {current_timestamp}, total_items: {min(total_count, 100)})"
                )
                return {"result": "success"}  # 成功则直接返回

            except Exception as e:
                last_exception = e
                retry_count += 1
                self.logger.warning(
                    f"保存到Redis失败 (尝试 {retry_count}/{max_retries}): {str(e)}"
                )
                if retry_count <= max_retries:
                    time.sleep(retry_delay)

        # 所有重试都失败
        self.logger.error(
            f"保存消息到 Redis 失败 (conversation_id: {self.conversation_id}): {str(last_exception)}"
        )
        raise last_exception

    @langfuse_wrapper.observe_decorator(
        name="_load_conversation_history", capture_input=True, capture_output=True
    )
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
                self.logger.info(
                    f"未找到对话历史 (conversation_id: {self.conversation_id})"
                )
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
                    self.logger.warning(f"解析对话历史失败: {e}")
                    continue

            if conversation_history:
                self.logger.info(
                    f"成功加载 {len(conversation_history)} 条对话历史记录 (conversation_id: {self.conversation_id})"
                )
            return conversation_history

        except Exception as e:
            self.logger.error(f"加载对话历史失败: {e}")
            return []
