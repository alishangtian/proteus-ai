"""MPC客户端节点，提供工具和资源访问功能"""

import os
import asyncio
import logging
from typing import Optional, Dict, Any
from contextlib import AsyncExitStack
from mcp import ClientSession
from mcp.client.sse import sse_client
from .base import BaseNode
from ..api.config import API_CONFIG

# 移除顶层导入，避免循环导入
# from ..manager.mcp_manager import get_mcp_manager

logger = logging.getLogger(__name__)


class MCPClientNode(BaseNode):
    """MPC客户端节点，提供工具查询、工具执行、资源查询和资源访问功能"""

    def __init__(self):
        super().__init__()
        # 从API_CONFIG中读取默认服务器URL
        self.default_server_id = os.getenv("MCP_server_id", "")
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()

    async def connect(self, server_name: str = None, max_retries: int = 3):
        """连接到MCP服务器
        Args:
            server_name: 服务器名称
            max_retries: 最大重试次数
        """
        if not server_name:
            raise ValueError("server_name is required")

        # 延迟导入，避免循环导入问题
        from ..manager.mcp_manager import get_mcp_manager
        server_url = get_mcp_manager().get_server_url(server_name)
        
        # 复用connect_server_url的重试逻辑
        result = await self.connect_server_url(server_url, max_retries)
        return {"status": result["status"], "server_name": server_name}

    async def connect_server_url(self, server_url: str = None, max_retries: int = 3):
        """连接到MCP服务器
        Args:
            server_url: 服务器URL
            max_retries: 最大重试次数
        """
        if not server_url:
            raise ValueError("server_url is required")
        
        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"MCPClientNode 连接到 {server_url} (尝试 {attempt}/{max_retries})")
                # 存储上下文管理器以保持连接
                self._streams_context = sse_client(
                    url=server_url,
                    connect_timeout=10.0,
                    read_timeout=30.0
                )
                streams = await self._streams_context.__aenter__()

                self._session_context = ClientSession(*streams)
                self.session = await self._session_context.__aenter__()

                # 初始化会话
                await self.session.initialize()
                return {"status": "connected", "server_url": server_url}
                
            except Exception as e:
                last_error = e
                logger.error(f"连接尝试 {attempt} 失败: {str(e)}")
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)  # 指数退避
                continue

        raise ConnectionError(f"无法连接到MCP服务器 {server_url} (重试 {max_retries} 次后失败): {str(last_error)}")

    async def cleanup(self):
        """清理会话和连接"""
        if hasattr(self, "_session_context") and self._session_context:
            await self._session_context.__aexit__(None, None, None)
        if hasattr(self, "_streams_context") and self._streams_context:
            await self._streams_context.__aexit__(None, None, None)

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行节点操作

        Args:
            params: 包含操作类型和参数的字典
                - operation: 操作类型(tool_query, tool_execute, resource_query, resource_access)
                - server_name: 必选的参数，指定要连接的服务器名称
                - 其他操作特定参数

        Returns:
            操作结果字典
        """
        operation = params.get("operation")
        server_name = params.get("server_name")

        try:
            # 确保已连接
            await self.connect(server_name)
            if operation == "list_tools":
                return await self._tool_query(params)
            elif operation == "use_tool":
                return await self._tool_execute(params)
            elif operation == "list_resources":
                return await self._resource_query(params)
            elif operation == "access_resource":
                return await self._resource_access(params)
            elif operation == "list_prompts":
                return await self._list_prompts(params)
            elif operation == "get_prompt":
                return await self._get_prompt(params)
            else:
                raise ValueError(f"未知操作类型: {operation}")

        except Exception as e:
            raise ValueError(f"执行操作失败: {str(e)}")
        finally:
            await self.cleanup()

    async def execute_server_url(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行节点操作

        Args:
            params: 包含操作类型和参数的字典
                - operation: 操作类型(tool_query, tool_execute, resource_query, resource_access)
                - server_name: 必选的参数，指定要连接的服务器名称
                - 其他操作特定参数

        Returns:
            操作结果字典
        """
        operation = params.get("operation")
        server_url = params.get("server_url")

        try:
            # 确保已连接
            await self.connect_server_url(server_url)
            if operation == "list_tools":
                return await self._tool_query(params)
            elif operation == "use_tool":
                return await self._tool_execute(params)
            elif operation == "list_resources":
                return await self._resource_query(params)
            elif operation == "access_resource":
                return await self._resource_access(params)
            elif operation == "list_prompts":
                return await self._list_prompts(params)
            elif operation == "get_prompt":
                return await self._get_prompt(params)
            else:
                raise ValueError(f"未知操作类型: {operation}")

        except Exception as e:
            raise ValueError(f"执行操作失败: {str(e)}")
        finally:
            await self.cleanup()

    async def _tool_query(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """查询可用工具"""
        response = await self.session.list_tools()
        tools = response.tools
        return {
            "result": "success",
            "tools": [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.inputSchema,
                }
                for tool in tools
            ],
        }

    async def _tool_execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行工具"""
        tool_name = params["tool_name"]
        args = params.get("arguments", {})

        result = await self.session.call_tool(tool_name, args)
        return {
            "result": "success",
            "tool_name": tool_name,
            "output": result.content[0].text if result.content else None,
            "raw_response": result.dict(),
        }

    async def _resource_query(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """查询可用资源"""
        try:
            response = await self.session.list_resources()
            resources = response.resources
            return {
                "result": "success",
                "resources": [
                    {
                        "name": resource.name,
                        "description": resource.description,
                        "uri": resource.uri,
                    }
                    for resource in resources
                ],
            }
        except Exception as e:
            logger.error(f"查询可用资源失败 error: {str(e)}")
            return {"result": "error", "resources": []}

    async def _resource_access(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """访问资源"""
        resource_uri = params["resource_uri"]
        args = params.get("args", {})

        result = await self.session.access_resource(resource_uri, args)
        return {
            "result": "success",
            "resource_uri": resource_uri,
            "content": result.content,
            "raw_response": result.dict(),
        }

    async def _list_prompts(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """列出所有可用prompts"""
        response = await self.session.list_prompts()
        prompts = response.prompts
        logger.info(f"查询可用prompts: {prompts}")
        return {
            "result": "success",
            "prompts": [
                {
                    "id": prompt.id,
                    "name": prompt.name,
                    "description": prompt.description,
                }
                for prompt in prompts
            ],
        }

    async def _get_prompt(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """获取特定prompt详情"""
        prompt_id = params["prompt_id"]
        result = await self.session.get_prompt(prompt_id)
        return {
            "result": "success",
            "prompt": {
                "id": result.id,
                "name": result.name,
                "description": result.description,
                "content": result.content,
                "metadata": result.metadata,
            },
            "raw_response": result.dict(),
        }

    async def _prompt_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """列出可用prompt模板"""
        response = await self.session.list_prompts()
        prompts = response.prompts
        logger.info(f"查询可用prompt模板: {prompts}")
        return {
            "result": "success",
            "prompts": [
                {
                    "id": prompt.id,
                    "name": prompt.name,
                    "description": prompt.description,
                }
                for prompt in prompts
            ],
        }

    async def _prompt_get(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """获取单个prompt模板"""
        prompt_id = params["prompt_id"]
        result = await self.session.get_prompt(prompt_id)
        return {
            "result": "success",
            "content": result.content,
        }

    async def agent_execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行节点并将结果转换为统一格式

        Args:
            params: 节点参数

        Returns:
            Dict[str, Any]: 执行结果
        """
        try:
            result = await self.execute(params)
            return {"result": result}
        except Exception as e:
            return {"result": f"Error: {str(e)}", "error": str(e)}
