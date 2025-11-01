"""工具执行器模块 - 为 chat 模式提供统一的工具执行能力"""

import logging
import asyncio
import uuid
import json
import importlib
from typing import Dict, Any, Optional, List
from ..nodes.node_config import NodeConfigManager
from ..api.events import (
    create_action_start_event,
    create_action_complete_event,
    create_tool_progress_event,
    create_tool_retry_event,
)

logger = logging.getLogger(__name__)


class ToolExecutor:
    """工具执行器 - 参考 react_agent 的工具执行逻辑"""

    def __init__(
        self, stream_manager=None, max_retries: int = 3, retry_delay: float = 1.0
    ):
        """初始化工具执行器

        Args:
            stream_manager: 流管理器，用于发送事件
            max_retries: 最大重试次数
            retry_delay: 重试延迟（秒）
        """
        self.stream_manager = stream_manager
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.node_manager = NodeConfigManager.get_instance()

    async def execute_tool(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        chat_id: str,
        tool_call_id: Optional[str] = None,
    ) -> str:
        """执行单个工具调用

        Args:
            tool_name: 工具名称
            tool_args: 工具参数
            chat_id: 聊天会话ID
            tool_call_id: 工具调用ID（可选）

        Returns:
            工具执行结果（字符串格式）
        """
        if tool_call_id is None:
            tool_call_id = str(uuid.uuid4())

        logger.info(f"[{chat_id}] 开始执行工具: {tool_name}, 参数: {tool_args}")

        # 发送工具开始事件
        if self.stream_manager:
            try:
                start_event = await create_action_start_event(
                    action=tool_name, action_input=tool_args, action_id=tool_call_id
                )
                await self.stream_manager.send_message(chat_id, start_event)

                progress_event = await create_tool_progress_event(
                    tool=tool_name,
                    status="running",
                    result=tool_args,
                    action_id=tool_call_id,
                )
                await self.stream_manager.send_message(chat_id, progress_event)
            except Exception as e:
                logger.warning(f"[{chat_id}] 发送工具开始事件失败: {e}")

        # 获取工具配置
        tool_config = self.node_manager.get_node_info(tool_name)
        if not tool_config:
            error_msg = f"工具 {tool_name} 不存在"
            logger.error(f"[{chat_id}] {error_msg}")
            await self._send_complete_event(chat_id, tool_name, error_msg, tool_call_id)
            return error_msg

        # 执行工具（带重试机制）
        tool_result = await self._execute_with_retry(
            tool_name=tool_name,
            tool_config=tool_config,
            tool_args=tool_args,
            chat_id=chat_id,
            tool_call_id=tool_call_id,
        )

        # 发送工具完成事件
        await self._send_complete_event(chat_id, tool_name, tool_result, tool_call_id)

        logger.info(f"[{chat_id}] 工具 {tool_name} 执行完成")
        return tool_result

    async def _execute_with_retry(
        self,
        tool_name: str,
        tool_config: Dict[str, Any],
        tool_args: Dict[str, Any],
        chat_id: str,
        tool_call_id: str,
    ) -> str:
        """带重试机制的工具执行

        参考 react_agent._execute_tool_action 的重试逻辑
        """
        retry_count = 0
        last_error = None

        while retry_count <= self.max_retries:
            try:
                # 动态导入并执行工具
                # 从配置中获取完整的类路径，例如 "src.nodes.serper_search.SerperSearchNode"
                class_path = tool_config.get("class")
                if not class_path:
                    # 如果没有class配置，尝试使用type作为fallback
                    module_name = tool_config.get("type", tool_name)
                    class_name = tool_name
                    module = importlib.import_module(f"src.nodes.{module_name}")
                    tool_class = getattr(module, class_name)
                else:
                    # 解析类路径，例如 "src.nodes.serper_search.SerperSearchNode"
                    module_path, _, class_name = class_path.rpartition(".")
                    module = importlib.import_module(module_path)
                    tool_class = getattr(module, class_name)
                tool_instance = tool_class()

                # 执行工具
                if hasattr(tool_instance, "execute") and callable(
                    tool_instance.execute
                ):
                    result = await tool_instance.execute(tool_args)
                    # 提取结果
                    if isinstance(result, dict):
                        tool_result = str(result.get("data", result))
                    else:
                        tool_result = str(result)

                    logger.info(f"[{chat_id}] 工具 {tool_name} 执行成功")
                    return tool_result
                else:
                    error_msg = f"工具 {tool_name} 没有 execute 方法"
                    logger.error(f"[{chat_id}] {error_msg}")
                    return error_msg

            except Exception as e:
                retry_count += 1
                last_error = str(e)
                logger.warning(
                    f"[{chat_id}] 工具 {tool_name} 执行失败 "
                    f"(尝试 {retry_count}/{self.max_retries + 1}): {last_error}"
                )

                # 发送重试事件
                if self.stream_manager and retry_count <= self.max_retries:
                    try:
                        retry_event = await create_tool_retry_event(
                            action=tool_name,
                            retry_count=retry_count,
                            max_retries=self.max_retries,
                            error_message=last_error,
                        )
                        await self.stream_manager.send_message(chat_id, retry_event)
                    except Exception as event_error:
                        logger.warning(f"[{chat_id}] 发送重试事件失败: {event_error}")

                # 如果还有重试机会，等待后重试
                if retry_count <= self.max_retries:
                    await asyncio.sleep(self.retry_delay)
                else:
                    # 所有重试都失败
                    error_msg = f"工具 {tool_name} 在 {retry_count} 次重试后仍然失败: {last_error}"
                    logger.error(f"[{chat_id}] {error_msg}")
                    return error_msg

        # 不应该到达这里，但为了安全返回错误
        return f"工具执行错误: {last_error}"

    async def _send_complete_event(
        self, chat_id: str, tool_name: str, result: str, tool_call_id: str
    ):
        """发送工具完成事件"""
        if self.stream_manager:
            try:
                complete_event = await create_action_complete_event(
                    action=tool_name, result=result, action_id=tool_call_id
                )
                await self.stream_manager.send_message(chat_id, complete_event)
            except Exception as e:
                logger.warning(f"[{chat_id}] 发送工具完成事件失败: {e}")

    async def execute_tool_calls(
        self,
        tool_calls: List[Dict[str, Any]],
        chat_id: str,
    ) -> List[Dict[str, str]]:
        """批量执行工具调用

        Args:
            tool_calls: 工具调用列表
            chat_id: 聊天会话ID

        Returns:
            工具消息列表，格式为 [{"role": "tool", "tool_call_id": "...", "content": "..."}]
        """
        tool_messages = []

        for tool_call in tool_calls:
            tool_name = tool_call["function"]["name"]
            tool_call_id = tool_call.get("id", str(uuid.uuid4()))

            try:
                # 解析工具参数
                tool_args = json.loads(tool_call["function"]["arguments"])
            except json.JSONDecodeError:
                tool_args = tool_call["function"]["arguments"]

            # 执行工具
            tool_result = await self.execute_tool(
                tool_name=tool_name,
                tool_args=tool_args,
                chat_id=chat_id,
                tool_call_id=tool_call_id,
            )

            # 构建工具消息
            tool_message = {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": tool_result,
                "name": tool_name,
            }
            tool_messages.append(tool_message)

            logger.info(f"[{chat_id}] 工具结果已添加: {tool_result[:100]}...")

        return tool_messages
