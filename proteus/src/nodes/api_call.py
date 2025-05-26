"""API调用节点实现"""

import aiohttp
from typing import Dict, Any
from .base import BaseNode


class ApiCallNode(BaseNode):
    """API调用节点，支持Bearer Token认证"""

    async def agent_execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """智能体调用API节点

        Args:
            params: 节点参数，包含:
                - url: API地址
                - method: HTTP方法(GET, POST, PUT, DELETE等)
                - headers: 请求头(可选)
                - body: 请求体(可选)
                - bearer_token: Bearer Token(可选)

        Returns:
            Dict[str, Any]: API响应的data字段
        """
        result = await self.execute(params)
        return {"result": result.get("data", {})}

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行API调用

        Args:
            params: 节点参数，包含:
                - url: API地址
                - method: HTTP方法(GET, POST, PUT, DELETE等)
                - headers: 请求头(可选)
                - body: 请求体(可选)
                - bearer_token: Bearer Token(可选)

        Returns:
            Dict[str, Any]: 执行结果，包含:
                - status: HTTP状态码
                - success: 是否成功
                - data: 响应数据
                - headers: 响应头
                - error: 错误信息(如果有)
        """
        url = params["url"]
        method = params["method"].upper()
        headers = params.get("headers", {})
        body = params.get("body")
        bearer_token = params.get("bearer_token")

        if bearer_token:
            headers["Authorization"] = f"Bearer {bearer_token}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method=method, url=url, headers=headers, json=body if body else None
                ) as response:
                    data = await response.json()
                    return {
                        "status": response.status,
                        "success": response.status < 400,
                        "data": data,
                        "headers": dict(response.headers),
                        "error": None,
                    }
        except Exception as e:
            return {
                "status": None,
                "success": False,
                "data": None,
                "headers": None,
                "error": str(e),
            }
