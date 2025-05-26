"""MCP 管理器，负责管理 MCP 服务器连接和资源"""

import os
import json
import logging
from typing import Dict, List, Any, Optional
from ..nodes.mcp_client import MCPClientNode

logger = logging.getLogger(__name__)


class MCPManager:
    """MCP 管理器类，负责从配置文件加载 MCP 服务器列表，
    连接到服务器并获取工具和资源列表"""

    def __init__(self, config_path: str = None):
        """初始化 MCP 管理器

        Args:
            config_path: MCP 配置文件路径，默认为项目根目录下的 mcp.json
        """
        self.config_path = config_path or os.path.join(os.getcwd(), "mcp.json")
        self.servers: Dict[str, Dict[str, Any]] = {}  # 服务器配置信息
        self.tools: Dict[str, List[Dict[str, Any]]] = {}  # 每个服务器的工具列表
        self.resources: Dict[str, List[Dict[str, Any]]] = {}  # 每个服务器的资源列表
        self.client = MCPClientNode()

    def load_config(self) -> Dict[str, Any]:
        """从配置文件加载 MCP 服务器列表

        Returns:
            Dict[str, Any]: 加载的配置信息
        """
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                self.servers = config.get("mcpServers", {})
                logger.info(f"已加载 {len(self.servers)} 个 MCP 服务器配置")
                return config
        except Exception as e:
            logger.error(f"加载 MCP 配置文件失败: {str(e)}")
            return {}

    async def fetch_server_info(
        self, server_name: str, server_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """获取指定服务器的工具和资源列表

        Args:
            server_name: 服务器名称
            server_config: 服务器配置信息

        Returns:
            Dict[str, Any]: 包含工具和资源列表的字典
        """
        server_url = server_config.get("url")

        try:
            # 获取工具列表
            tools_result = await self.client.execute_server_url(
                {"operation": "list_tools", "server_url": server_url}
            )
            tools = tools_result.get("tools", [])
            self.tools[server_name] = tools

            # 获取资源列表
            resources_result = await self.client.execute_server_url(
                {"operation": "list_resources", "server_url": server_url}
            )
            logger.info(f"服务器 {server_name} 资源获取如下: {resources_result}")
            resources = resources_result.get("resources", [])
            self.resources[server_name] = resources

            logger.info(
                f"服务器 {server_name} 信息获取成功: {len(tools)} 个工具, {len(resources)} 个资源"
            )
            return {"tools": tools, "resources": resources}
        except Exception as e:
            logger.error(f"获取服务器 {server_name} 信息失败: {str(e)}")
            self.tools[server_name] = []
            self.resources[server_name] = []
            return {"tools": [], "resources": []}

    async def initialize(self) -> Dict[str, Any]:
        """初始化 MCP 管理器，加载配置并获取所有服务器的工具和资源列表

        Returns:
            Dict[str, Any]: 初始化结果
        """
        self.load_config()
        if not self.servers:
            logger.warning("未找到 MCP 服务器配置")
            return {"status": "error", "message": "未找到 MCP 服务器配置"}

        results = {}
        for server_name, server_config in self.servers.items():
            results[server_name] = await self.fetch_server_info(
                server_name, server_config
            )
        logger.info(f"已获取 {len(results)} 个MCP服务信息")
        return True

    def get_all_tools(self) -> Dict[str, List[Dict[str, Any]]]:
        """获取所有服务器的工具列表

        Returns:
            Dict[str, List[Dict[str, Any]]]: 服务器名称到工具列表的映射
        """
        return self.tools

    def get_all_resources(self) -> Dict[str, List[Dict[str, Any]]]:
        """获取所有服务器的资源列表

        Returns:
            Dict[str, List[Dict[str, Any]]]: 服务器名称到资源列表的映射
        """
        return self.resources

    def get_server_tools(self, server_name: str) -> List[Dict[str, Any]]:
        """获取指定服务器的工具列表

        Args:
            server_name: 服务器名称

        Returns:
            List[Dict[str, Any]]: 工具列表
        """
        return self.tools.get(server_name, [])

    def get_server_resources(self, server_name: str) -> List[Dict[str, Any]]:
        """获取指定服务器的资源列表

        Args:
            server_name: 服务器名称

        Returns:
            List[Dict[str, Any]]: 资源列表
        """
        return self.resources.get(server_name, [])

    def get_tool_by_name(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """根据工具名称获取工具信息

        Args:
            tool_name: 工具名称

        Returns:
            Optional[Dict[str, Any]]: 工具信息，如果未找到则返回 None
        """
        for server_name, tools in self.tools.items():
            for tool in tools:
                if tool.get("name") == tool_name:
                    return {
                        "server_name": server_name,
                        "server_url": self.servers[server_name].get("url"),
                        "tool": tool,
                    }
        return None

    def get_resource_by_uri(self, resource_uri: str) -> Optional[Dict[str, Any]]:
        """根据资源 URI 获取资源信息

        Args:
            resource_uri: 资源 URI

        Returns:
            Optional[Dict[str, Any]]: 资源信息，如果未找到则返回 None
        """
        for server_name, resources in self.resources.items():
            for resource in resources:
                if resource.get("uri") == resource_uri:
                    return {
                        "server_name": server_name,
                        "server_url": self.servers[server_name].get("url"),
                        "resource": resource,
                    }
        return None

    def get_server_url(self, server_name: str) -> Optional[str]:
        """通过服务器名称获取服务器URL

        Args:
            server_name: 服务器名称

        Returns:
            Optional[str]: 服务器URL，如果未找到则返回None
        """
        server_config = self.servers.get(server_name)
        if server_config:
            return server_config.get("url")
        return None

    def get_tools_formated_prompt(self) -> str:
        """生成结构化工具描述（Markdown格式）

        遵循模型最佳实践的结构化格式：
        1. 服务器元数据置于章节开头
        2. 参数使用表格形式展示
        3. 示例代码明确标注JSON类型
        4. 添加工具调用协议说明

        Returns:
            str: 优化后的工具描述文本
        """
        all_tools = self.get_all_tools()
        if not all_tools:
            return "## 可用工具\n当前没有已注册的MCP工具"

        prompt = [
            "# MCP 工具集合\n",
            "## 格式说明\n",
            "1. 每个工具包含：工具名称、工具描述、输入参数\n",
            "2. 输入参数表格中★表示必填参数\n",
            f"## 工具概览（共{sum(len(t) for t in all_tools.values())}个工具）\n"
        ]

        for server_name, tools in all_tools.items():
            if not tools:
                continue

            # 服务器基础信息
            prompt.extend([
                f"\n\n---\n## 服务器名称：{server_name}"
            ])

            for tool in tools:
                tool_name = tool.get("name", "unnamed_tool")
                schema = tool.get("input_schema", {})
                required_params = schema.get("required", [])
                param_table = []

                # 构建参数表格
                for param, detail in schema.get("properties", {}).items():
                    param_table.append(
                        f"| `{param}` | `{detail.get('type', 'string')}` | "
                        f"{'★' if param in required_params else '○'} | "
                        f"{detail.get('description', '暂无描述').replace('\n', ' ')} |"
                    )

                # 工具描述区块
                tool_block = [
                    f"\n### {tool_name}",
                    f"\n#### 功能描述 \n> {tool.get('description', '该工具暂无功能描述')}\n",
                    "#### 参数规范\n（★=必填 ○=可选）",
                    "  | 参数名 | 类型 | 必填 | 说明 |",
                    "  | :--- | :---: | :---: | :--- |"
                ]
                tool_block.extend(["  "+line for line in param_table] if param_table else ["  | - | - | - | --- |"])
                
                prompt.extend(tool_block)

        return "\n".join(prompt)

# 单例模式
_instance = None
_instance_flag = False


def get_mcp_manager(config_path: str = None) -> MCPManager:
    """获取 MCP 管理器单例

    Args:
        config_path: MCP 配置文件路径，默认为项目根目录下的 mcp.json

    Returns:
        MCPManager: MCP 管理器实例
    """
    global _instance
    if _instance is None:
        config_path = os.getenv("MCP_CONFIG_PATH", None)
        logger.info(f"get_mcp_manager 初始化 MCP 管理器 config_path {config_path}")
        _instance = MCPManager(config_path)
    return _instance


async def initialize_mcp_manager(config_path: str = None) -> Dict[str, Any]:
    """初始化 MCP 管理器

    Args:
        config_path: MCP 配置文件路径，默认为项目根目录下的 mcp.json

    Returns:
        Dict[str, Any]: 初始化结果
    """
    manager = get_mcp_manager(config_path)
    global _instance_flag
    if _instance_flag:
        return
    _instance_flag = await manager.initialize()
    return
