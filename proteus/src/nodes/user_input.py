"""用户输入节点模块

此模块提供了用户输入节点的实现，用于在工作流中获取用户的交互输入。
支持同步和异步操作模式，可以通过普通执行或Agent执行两种方式获取用户输入。
"""

from typing import Any, Dict
from .base import BaseNode
from ..core.enums import NodeStatus
from ..agent.agent_engine import AgentEngine
from ..api.events import create_user_input_required_event


class UserInputNode(BaseNode):

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行节点逻辑，创建用户输入请求事件

        此方法创建一个用户输入请求事件，并返回等待状态。节点状态将设置为RUNNING，
        直到通过set_input方法接收到用户输入。

        Args:
            params: 节点参数，可以包含以下键：
                - input_type: 输入类型(text/number等)
                - default_value: 默认值
                - validation: 输入验证规则

        Returns:
            Dict[str, Any]: 执行结果，包含以下结构：
                {
                    "result": {
                        "success": bool,
                        "status": NodeStatus,
                        "data": {
                            "prompt": str,
                            "waiting_for_input": bool,
                            "event": Dict[str, Any]
                        } | None,
                        "error": str | None
                    }
                }

        Raises:
            Exception: 创建用户输入事件失败时抛出
        """
        try:
            # 验证必要参数
            if not isinstance(self.prompt, str):
                raise ValueError("Prompt must be a string")

            # 更新节点状态
            self.status = NodeStatus.RUNNING

            # 创建用户输入请求事件
            input_event = await create_user_input_required_event(
                node_id=self.id,
                prompt=self.prompt,
                input_type=self.params.get("input_type", "text"),
                default_value=self.params.get("default_value"),
                validation=self.params.get("validation"),
            )

            # 返回等待用户输入的结果
            return {
                "result": {
                    "success": True,
                    "status": self.status.value,  # 将枚举值转换为字符串
                    "data": {
                        "prompt": self.prompt,
                        "waiting_for_input": True,
                        "event": input_event,
                    },
                    "error": None,
                }
            }

        except Exception as e:
            self.status = NodeStatus.FAILED
            return {
                "result": {
                    "success": False,
                    "status": self.status.value,  # 将枚举值转换为字符串
                    "data": None,
                    "error": f"Failed to create user input event: {str(e)}",
                }
            }

    async def agent_execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            chat_id = params["chat_id"]
            node_id = params["node_id"]
            prompt = params["prompt"]
            input_type = params["input_type"]
            agent = params["agent"]
            if not agent:
                raise ValueError("No active agent found")

            # 等待用户输入
            value = await agent.wait_for_user_input(
                node_id, prompt, chat_id, input_type
            )

            return {"result": value}

        except Exception as e:
            self.status = NodeStatus.FAILED
            return {
                "result": {
                    "success": False,
                    "status": self.status.value,  # 将枚举值转换为字符串
                    "data": None,
                    "error": f"Failed to get user input: {str(e)}",
                }
            }