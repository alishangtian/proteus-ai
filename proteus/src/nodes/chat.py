"""LLM Chat Node"""

from typing import Dict, Any
from .base import BaseNode
from ..api.llm_api import call_llm_api


class ChatNode(BaseNode):
    """LLM Chat Node for handling conversations with language models"""

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        if "history_action_result" in params:
            params["user_question"] = params["user_question"] + "\n 参考信息如下：\n" + params["history_action_result"]
        user_question = params["user_question"]
        temperature = float(params.get("temperature", 0.7))
        system_prompt = str(params.get("system_prompt", ""))

        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": user_question})

        try:
            response = await call_llm_api(messages, temperature=temperature)
            return {"response": response}
        except Exception as e:
            raise ValueError(f"LLM API call failed: {str(e)}")

    async def agent_execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行节点并返回response字段

        Args:
            params: 节点参数

        Returns:
            Dict[str, Any]: 执行结果中的response字段
        """
        result = await self.execute(params)
        return {"result": result.get("response", "")}
