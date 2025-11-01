"""
工具转换模块
将 YAML 节点配置转换为 OpenAI API 工具格式
"""

import yaml
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class ToolConverter:
    """工具转换器，将节点配置转换为 OpenAI 工具格式"""
    
    # Python 类型到 JSON Schema 类型的映射
    TYPE_MAPPING = {
        "str": "string",
        "int": "integer",
        "float": "number",
        "bool": "boolean",
        "dict": "object",
        "list": "array",
        "tuple": "array",
    }
    
    def __init__(self, config_path: str = None):
        """
        初始化工具转换器
        
        Args:
            config_path: YAML 配置文件路径，默认为 src/nodes/agent_node_config.yaml
        """
        if config_path is None:
            # 默认配置文件路径
            config_path = Path(__file__).parent.parent / "nodes" / "agent_node_config.yaml"
        
        self.config_path = Path(config_path)
        self.nodes_config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """加载 YAML 配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            logger.info(f"成功加载配置文件: {self.config_path}")
            return config
        except Exception as e:
            logger.error(f"加载配置文件失败: {str(e)}")
            return {}
    
    def _convert_type(self, python_type: str) -> str:
        """
        将 Python 类型转换为 JSON Schema 类型
        
        Args:
            python_type: Python 类型字符串
            
        Returns:
            JSON Schema 类型字符串
        """
        return self.TYPE_MAPPING.get(python_type, "string")
    
    def _build_parameter_schema(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        构建参数的 JSON Schema
        
        Args:
            params: 节点参数配置
            
        Returns:
            JSON Schema 格式的参数定义
        """
        properties = {}
        required = []
        
        for param_name, param_config in params.items():
            # 获取参数类型
            param_type = param_config.get("type", "str")
            json_type = self._convert_type(param_type)
            
            # 构建参数属性
            param_schema = {
                "type": json_type,
                "description": param_config.get("description", ""),
            }
            
            # 添加默认值（如果存在）
            if "default" in param_config:
                # 注意：OpenAI 工具格式中不直接支持 default，但可以在 description 中说明
                default_value = param_config["default"]
                param_schema["description"] += f" (默认值: {default_value})"
            
            # 添加示例（如果存在）
            if "example" in param_config:
                example = param_config["example"]
                # 某些实现支持 example 字段
                param_schema["example"] = example
            
            # 添加枚举值（如果在 validation 中定义）
            if "validation" in param_config:
                validation = param_config["validation"]
                if "enum" in validation:
                    param_schema["enum"] = validation["enum"]
            
            properties[param_name] = param_schema
            
            # 检查是否为必需参数
            if param_config.get("required", False):
                required.append(param_name)
        
        schema = {
            "type": "object",
            "properties": properties,
        }
        
        if required:
            schema["required"] = required
        
        return schema
    
    def convert_node_to_tool(self, node_name: str, node_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        将单个节点配置转换为 OpenAI 工具格式
        
        Args:
            node_name: 节点名称（YAML中的key）
            node_config: 节点配置
            
        Returns:
            OpenAI 工具格式的字典
        """
        # 使用 type 字段作为函数名（这是实际的工具类型）
        function_name = node_config.get("type")
        if not function_name:
            logger.warning(f"节点 {node_name} 缺少 type 字段，跳过")
            return None
        
        # 获取节点描述
        description = node_config.get("description", node_config.get("name", ""))
        
        # 构建参数 schema
        params = node_config.get("params", {})
        parameters = self._build_parameter_schema(params)
        
        # 构建工具定义
        tool = {
            "type": "function",
            "function": {
                "name": function_name,
                "description": description,
                "parameters": parameters,
            }
        }
        
        return tool
    
    def convert_all_nodes_to_tools(self, exclude_nodes: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        将所有节点配置转换为 OpenAI 工具格式列表
        
        Args:
            exclude_nodes: 要排除的节点名称列表（节点的 key 名称）
            
        Returns:
            OpenAI 工具格式的列表
        """
        if exclude_nodes is None:
            exclude_nodes = []
        
        tools = []
        
        for node_name, node_config in self.nodes_config.items():
            # 跳过被注释的节点（以 # 开头）
            if node_name.startswith("#"):
                continue
            
            # 跳过排除列表中的节点
            if node_name in exclude_nodes:
                continue
            
            try:
                tool = self.convert_node_to_tool(node_name, node_config)
                if tool:  # 只添加非 None 的工具
                    tools.append(tool)
                    logger.debug(f"成功转换节点: {node_name} -> {tool['function']['name']}")
            except Exception as e:
                logger.error(f"转换节点 {node_name} 失败: {str(e)}")
        
        logger.info(f"成功转换 {len(tools)} 个节点为工具定义")
        return tools
    
    def convert_specific_nodes_to_tools(self, node_names: List[str]) -> List[Dict[str, Any]]:
        """
        将指定的节点配置转换为 OpenAI 工具格式列表
        
        支持两种方式指定节点：
        1. 使用节点的 key 名称（如 "SerperSearchNode"）
        2. 使用节点的 type 字段（如 "serper_search"）
        
        Args:
            node_names: 要转换的节点名称列表（可以是 key 或 type）
            
        Returns:
            OpenAI 工具格式的列表
        """
        tools = []
        
        for node_name in node_names:
            found = False
            
            # 首先尝试直接匹配 key
            if node_name in self.nodes_config:
                try:
                    node_config = self.nodes_config[node_name]
                    tool = self.convert_node_to_tool(node_name, node_config)
                    if tool:
                        tools.append(tool)
                        logger.debug(f"成功转换节点（通过key）: {node_name} -> {tool['function']['name']}")
                        found = True
                except Exception as e:
                    logger.error(f"转换节点 {node_name} 失败: {str(e)}")
                    continue
            
            # 如果没找到，尝试通过 type 字段匹配
            if not found:
                for key, config in self.nodes_config.items():
                    if config.get("type") == node_name:
                        try:
                            tool = self.convert_node_to_tool(key, config)
                            if tool:
                                tools.append(tool)
                                logger.debug(f"成功转换节点（通过type）: {key} -> {tool['function']['name']}")
                                found = True
                                break
                        except Exception as e:
                            logger.error(f"转换节点 {key} (type={node_name}) 失败: {str(e)}")
                            continue
            
            if not found:
                logger.warning(f"节点 {node_name} 不存在于配置中（既不是 key 也不是 type）")
        
        logger.info(f"成功转换 {len(tools)} 个指定节点为工具定义")
        return tools
    
    def get_tool_by_name(self, function_name: str) -> Optional[Dict[str, Any]]:
        """
        根据函数名获取对应的工具定义
        
        Args:
            function_name: 函数名（节点类型）
            
        Returns:
            工具定义字典，如果未找到则返回 None
        """
        for node_name, node_config in self.nodes_config.items():
            if node_config.get("type") == function_name:
                return self.convert_node_to_tool(node_name, node_config)
        
        logger.warning(f"未找到函数名为 {function_name} 的工具")
        return None


# 便捷函数
def load_tools_from_yaml(
    config_path: str = None,
    node_names: Optional[List[str]] = None,
    exclude_nodes: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    从 YAML 配置文件加载工具定义
    
    Args:
        config_path: YAML 配置文件路径
        node_names: 要转换的节点名称列表（如果指定，则只转换这些节点）
        exclude_nodes: 要排除的节点名称列表（仅在 node_names 为 None 时有效）
        
    Returns:
        OpenAI 工具格式的列表
    """
    converter = ToolConverter(config_path)
    
    if node_names:
        return converter.convert_specific_nodes_to_tools(node_names)
    else:
        return converter.convert_all_nodes_to_tools(exclude_nodes)


def get_tool_by_function_name(function_name: str, config_path: str = None) -> Optional[Dict[str, Any]]:
    """
    根据函数名获取工具定义
    
    Args:
        function_name: 函数名（节点类型）
        config_path: YAML 配置文件路径
        
    Returns:
        工具定义字典，如果未找到则返回 None
    """
    converter = ToolConverter(config_path)
    return converter.get_tool_by_name(function_name)