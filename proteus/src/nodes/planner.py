"""Task Planner Node"""

from typing import Dict, Any, List
from .base import BaseNode
from ..api.llm_api import call_llm_api


class PlannerNode(BaseNode):
    """Task Planner Node for decomposing questions into executable steps"""

    PLANNER_SYSTEM_PROMPT = (
        "你是一个任务规划专家。请将用户的问题分解为多个可执行的步骤。\n"
        "每个步骤应清晰、具体，且按顺序排列。\n"
        "输出格式为：1. 步骤描述\n2. 步骤描述\n..."
    )

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute planning process

        Args:
            params: Must contain 'user_question' key with the user's question

        Returns:
            Dict with 'steps' key containing list of planning steps
        """
        user_question = params["user_question"]
        temperature = float(
            params.get("temperature", 0.3)
        )  # Lower temp for deterministic planning

        messages = [
            {"role": "system", "content": self.PLANNER_SYSTEM_PROMPT},
            {"role": "user", "content": user_question},
        ]

        try:
            response = await call_llm_api(messages, temperature=temperature)
            # Parse numbered steps from response
            steps = [line.strip() for line in response[0].split("\n") if line.strip()]
            return {"steps": steps}
        except Exception as e:
            raise ValueError(f"Planning failed: {str(e)}")

    async def agent_execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Agent-compatible execution returning steps"""
        result = await self.execute(params)
        return {"result": result.get("steps", [])}
