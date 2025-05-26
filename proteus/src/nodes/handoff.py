from typing import Dict, Any
from .base import BaseNode
from ..manager.multi_agent_manager import get_multi_agent_manager
from ..manager.multi_agent_manager import TeamRole, AgentEvent
import logging

logger = logging.getLogger(__name__)


class HandoffNode(BaseNode):
    """工作流交接节点 - 接收并处理handoff事件

    参数:
        task (str): 任务描述，必填
        context (str): 上下文信息，可选
        target_role (str): 任务接收方职责类型，必填（planner/researcher/coder/reporter/coordinator）
        description (str): 任务详细描述，可选

    返回:
        dict: 包含执行状态和事件处理结果
    """

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        required_fields = ["task", "target_role"]
        for field in required_fields:
            if field not in params:
                return {"success": False, "error": f"缺少必填参数: {field}"}

        try:
            TeamRole(params["target_role"])
        except ValueError as e:
            return {
                "success": False,
                "error": str(e),
            }

        event_details = {
            "task": params["task"],
            "context": params.get("context", ""),
            "target_role": params["target_role"],
            "description": params.get("description", ""),
        }

        logger.info(f"Handoff事件已接收: {event_details}")

        # 使用MultiAgentManager发布事件
        manager = get_multi_agent_manager()
        event = manager.create_event(
            role_type=TeamRole(params["target_role"]),
            chat_id=params["chat_id"],
            sender_id=params["sender_id"],
            sender_role=params["sender_role"],
            payload=event_details,
            priority=0,  # 高优先级
        )
        await manager.publish_event(event)

        return {
            "success": True,
            "result": {
                "event": "handoff_processed",
                "details": event_details,
                "event_id": event.event_id,
            },
        }

    async def agent_execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        execution_result = await self.execute(params)
        return {"result": execution_result.get("result", {})}
