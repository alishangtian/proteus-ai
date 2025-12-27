from typing import Any, Dict, List, Optional
from proteus.src.nodes.base import BaseNode
from proteus.src.manager.sop_memory_manager import SopMemoryManager
import logging

logger = logging.getLogger(__name__)

class SopMemoryNode(BaseNode):
    """
    SopMemoryNode 节点用于管理和更新 SOP 记忆。
    它封装了 SopMemoryManager 的功能，允许通过节点方式生成、更新或新增 SOP 经验。
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sop_memory_manager = SopMemoryManager()

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行 SOP 记忆的生成或更新操作。

        Args:
            params (Dict[str, Any]): 包含以下键的字典：
                - user_query (str): 用户原始问题。
                - tool_chain (List[Dict[str, Any]]): 工具调用链，每个元素包含 'tool_name' 和 'action_input'。
                - final_result (str): 最终解决结果。
                - problem_type (Optional[str]): 问题类型（可选，如果未提供则自动识别）。
                - is_success (bool): 是否成功解决问题 (可选，默认为True)。
                - user_name (Optional[str]): 用户名，用于记忆隔离 (可选)。
                - model_name (Optional[str]): 用于SOP分析的模型名称 (可选)。

        Returns:
            Dict[str, Any]: 包含操作结果的字典，例如 {"success": True, "message": "SOP memory processed", "sop_experience": "..."}。
        """
        user_query = params.get("user_query")
        tool_chain = params.get("tool_chain")
        final_result = params.get("final_result")
        problem_type = params.get("problem_type")
        is_success = params.get("is_success", True)
        user_name = params.get("user_name")
        model_name = params.get("model_name")

        if not user_query or not final_result:
            return {
                "success": False,
                "error": "user_query 和 final_result 均不能为空。",
            }
        
        # tool_chain 可以为空，表示问题没有通过工具链解决

        try:
            sop_experience = await self.sop_memory_manager.process_sop_memory(
                user_query=user_query,
                tool_chain=tool_chain or [],
                final_result=final_result,
                problem_type=problem_type,
                is_success=is_success,
                user_name=user_name,
                model_name=model_name,
            )

            if sop_experience:
                logger.info(
                    f"SopMemoryNode: SOP 记忆已生成/更新，问题类型: '{problem_type or '自动识别'}', "
                    f"用户: {user_name or 'global'}"
                )
                return {
                    "success": True,
                    "user_query": user_query,
                    "problem_type": problem_type,
                    "user_name": user_name,
                    "sop_experience": sop_experience,
                    "message": "SOP 记忆已生成/更新成功。",
                }
            else:
                logger.info(
                    f"SopMemoryNode: 未生成新的 SOP 记忆，问题类型: '{problem_type or '自动识别'}', "
                    f"用户: {user_name or 'global'}"
                )
                return {
                    "success": False,
                    "user_query": user_query,
                    "problem_type": problem_type,
                    "user_name": user_name,
                    "sop_experience": None,
                    "message": "未生成新的 SOP 记忆。",
                }

        except Exception as e:
            logger.error(f"SopMemoryNode: 处理 SOP 记忆失败: {e}", exc_info=True)
            return {"success": False, "user_query": user_query, "error": str(e)}