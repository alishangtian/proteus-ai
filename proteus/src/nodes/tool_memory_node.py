from typing import Any, Dict, Optional
from proteus.src.nodes.base import BaseNode
from proteus.src.manager.tool_memory_manager import ToolMemoryManager
import logging

logger = logging.getLogger(__name__)

class ToolMemoryNode(BaseNode):
    """
    ToolMemoryNode 节点用于管理和更新工具记忆。
    它封装了 ToolMemoryManager 的功能，允许通过节点方式更新特定工具的经验反馈。
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tool_memory_manager = ToolMemoryManager()

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行工具记忆更新操作。

        Args:
            params (Dict[str, Any]): 包含以下键的字典：
                - tool_name (str): 要更新记忆的工具名称。
                - tool_memory (str): 工具使用经验的详细描述。
                - user_name (Optional[str]): 用户名，用于隔离不同用户的工具记忆 (可选)。
                - is_error (bool): 是否是错误执行，用于区分成功或失败的经验 (可选，默认为False)。
                - error_message (Optional[str]): 如果 is_error 为 True，提供错误信息 (可选)。

        Returns:
            Dict[str, Any]: 包含操作结果的字典，例如 {"success": True, "message": "Memory updated", "new_memory": "..."}。
        """
        tool_name = params.get("tool_name")
        tool_memory_content = params.get("tool_memory")
        user_name = params.get("user_name")
        is_error = params.get("is_error", False)
        error_message = params.get("error_message")

        if not tool_name or not tool_memory_content:
            return {
                "success": False,
                "error": "tool_name 和 tool_memory 均不能为空。",
            }

        try:
            # 直接调用 ToolMemoryManager 的保存方法，这里不再进行LLM分析，而是直接保存传入的记忆内容
            await self.tool_memory_manager.save_tool_memory(
                tool_name=tool_name,
                tool_memory=tool_memory_content,
                user_name=user_name,
            )

            # 更新后，重新加载最新的记忆以确认并返回
            updated_memory = await self.tool_memory_manager.load_tool_memory(
                tool_name=tool_name, user_name=user_name
            )

            logger.info(
                f"ToolMemoryNode: 工具 '{tool_name}' 的记忆已更新 "
                f"(user: {user_name or 'global'}, is_error: {is_error})"
            )
            return {
                "success": True,
                "tool_name": tool_name,
                "user_name": user_name,
                "new_memory": updated_memory,
                "message": f"工具 '{tool_name}' 的记忆已更新。",
            }
        except Exception as e:
            logger.error(f"ToolMemoryNode: 更新工具 '{tool_name}' 记忆失败: {e}", exc_info=True)
            return {"success": False, "tool_name": tool_name, "error": str(e)}