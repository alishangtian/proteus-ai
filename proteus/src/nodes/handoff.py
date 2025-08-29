from typing import Dict, Any
from .base import BaseNode
from ..manager.multi_agent_manager import TeamRole
from ..utils.redis_cache import RedisCache, get_redis_connection
import logging
import uuid
import json

logger = logging.getLogger(__name__)


class HandoffNode(BaseNode):
    """工作流交接节点 - 接收并处理handoff事件

    优化后的实现：事件直接发送到角色队列，由MultiAgentManager负责分发给订阅该角色的agent，
    不再需要区分具体的agent实例。

    参数:
        task (str): 任务描述，必填
        context (str): 上下文信息，可选
        target_role (str): 任务接收方职责类型，必填（planner/researcher/coder/reporter/coordinator等）
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

        # 将事件直接写入目标角色对应的 role_queue（优化：不区分具体agent）
        try:
            redis_cache = RedisCache()
            role_queue_key = f"role_queue:{params['target_role']}"

            event_obj = {
                "chat_id": params.get("chat_id"),
                "priority": 0,
                "event_id": str(uuid.uuid4()),
                "role_type": params["target_role"],
                "sender_id": params.get("sender_id"),
                "sender_role": params.get("sender_role"),
                "payload": event_details,
                "is_result": params.get("is_result"),
            }

            # 直接推送到角色队列，由MultiAgentManager负责分发给订阅该角色的agent
            redis_cache.rpush(
                role_queue_key,
                json.dumps(event_obj, ensure_ascii=False),
            )

            logger.info(
                f"事件已推送到角色队列: {role_queue_key}, event_id: {event_obj['event_id']}"
            )

            return {
                "success": True,
                "result": {
                    "event": "handoff_processed",
                    "details": event_details,
                    "target_role_queue": role_queue_key,
                    "event_id": event_obj["event_id"],
                },
            }
        except Exception as e:
            logger.error(f"Handoff 事件处理失败: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def agent_execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        execution_result = await self.execute(params)
        return {"result": execution_result.get("result", {})}
