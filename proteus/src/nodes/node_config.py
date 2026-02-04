"""节点配置管理模块"""

import yaml
import os
import json
import logging
from typing import Dict, Optional, List, Type, Any
import threading

# 延迟导入Tool，避免循环导入
from src.nodes.base import BaseNode

logger = logging.getLogger(__name__)


class NodeConfigManager:
    """节点配置管理类（线程安全单例模式）"""

    _instance = None
    _lock = threading.Lock()
    _initialized = False

    @classmethod
    def get_instance(cls) -> "NodeConfigManager":
        """获取单例实例"""
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = cls()
        return cls._instance

    def __init__(
        self,
        agent_config_path: str = None,
    ):
        # 如果已经初始化过，直接返回，保证单例
        if self.__class__._initialized:
            return

        # 初始化基础配置参数
        self.agent_config_path = agent_config_path
        self._node_types: Dict[str, Type[BaseNode]] = {}
        self._tools_cache: Dict[tuple, List[Any]] = {}  # 新增工具缓存

        # 设置默认配置文件路径
        self._set_default_paths()

        # 直接加载所有配置
        self.agent_node_configs = self._load_agent_config()
        # 直接注册节点类型
        self._register_node_types()
        # 标记为已初始化
        self.__class__._initialized = True

    def _set_default_paths(self):
        """设置默认配置文件路径"""
        current_dir = os.path.dirname(os.path.abspath(__file__))

        if self.agent_config_path is None:
            agent_nodes_config_path = os.path.join(
                current_dir, "../nodes/agent_node_config.yaml"
            )
            if os.path.exists(agent_nodes_config_path):
                self.agent_config_path = agent_nodes_config_path

    # 移除_ensure_configs_loaded和_ensure_nodes_registered方法，因为不再需要懒加载

    def _register_node_types(self):
        """注册所有节点类型"""
        import importlib
        from importlib.util import find_spec
        from pathlib import Path

        self._module_cache = {}
        registered_count = 0
        failed_count = 0

        for config_key, config in self.agent_node_configs.items():
            try:
                node_type = config.get("type")
                class_path = config.get("class")

                # 校验必要字段
                if not node_type or not class_path:
                    logger.warning(
                        f"节点配置 {config_key} 缺少必要字段(type或class)，跳过注册"
                    )
                    continue
                # 解析类路径
                module_path, _, class_name = class_path.rpartition(".")
                if not module_path:
                    raise ImportError(f"无效的class路径格式: {class_path}")

                # 动态导入模块
                if module_path not in self._module_cache:
                    try:
                        module = importlib.import_module(module_path)
                        self._module_cache[module_path] = module
                    except ImportError as e:
                        raise ImportError(f"无法导入模块 {module_path}: {str(e)}")

                # 获取节点类
                module = self._module_cache[module_path]
                node_class = getattr(module, class_name, None)
                if not node_class:
                    raise AttributeError(
                        f"模块 {module_path} 中没有找到类 {class_name}"
                    )

                # 验证节点类
                if not issubclass(node_class, BaseNode):
                    raise TypeError(f"类 {class_name} 不是BaseNode的子类")

                # 注册节点类型
                self.register_node_type(node_type, node_class)
                registered_count += 1

            except ImportError as ie:
                logger.error(
                    f"导入节点模块 {class_name} 失败: {str(ie)}", exc_info=True
                )
                failed_count += 1
                continue
            except AttributeError as ae:
                logger.error(f"获取节点类 {class_name} 失败: {str(ae)}", exc_info=True)
                failed_count += 1
                continue
            except TypeError as te:
                logger.error(f"节点类验证失败 {class_name}: {str(te)}", exc_info=True)
                failed_count += 1
                continue
            except Exception as e:
                logger.error(
                    f"注册节点类型 {class_name} 时发生意外错误: {str(e)}", exc_info=True
                )
                failed_count += 1
                continue

        logger.info(
            f"节点类型注册完成 - 成功: {registered_count}, 失败: {failed_count}"
        )
        if failed_count > 0:
            logger.warning(
                f"有 {failed_count} 个节点类型注册失败，请检查日志获取详细信息"
            )
            # 节点配置变更时清空缓存
            if hasattr(self, "_tools_cache"):
                self._tools_cache.clear()
                logger.info("节点配置变更，已清空工具缓存")

    # 移除重复的get_instance方法

    def _load_config(self) -> Dict:
        """加载节点配置"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f)
                    return config
            logger.warning(f"配置文件 {self.config_path} 不存在，返回空配置")
            return {}
        except Exception as e:
            logger.error(f"加载节点配置失败: {str(e)}", exc_info=True)
            return {}

    def _load_agent_config(self) -> Dict:
        """加载代理节点配置"""
        try:
            if os.path.exists(self.agent_config_path):
                with open(self.agent_config_path, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f)
                    return config
            logger.warning(f"代理配置文件 {self.agent_config_path} 不存在，返回空配置")
            return {}
        except Exception as e:
            logger.error(f"加载代理节点配置失败: {str(e)}", exc_info=True)
            return {}

    def get_node_info(self, node_type: str) -> Optional[Dict]:
        """
        获取节点配置信息

        Args:
            node_type: 节点类型

        Returns:
            节点配置信息，如果节点不存在则返回None
        """

        # 遍历配置查找匹配的节点类型
        for config in self.agent_node_configs.values():
            if isinstance(config, dict) and config.get("type") == node_type:
                return config
        return None

    def get_all_agent_nodes(self) -> List[Dict]:
        """
        获取所有节点的配置信息

        Returns:
            所有节点的配置信息列表
        """
        # 配置已在初始化时加载

        nodes = []
        for class_name, config in self.agent_node_configs.items():
            # 确保配置是字典类型
            if not isinstance(config, dict):
                logger.warning(f"节点 {class_name} 的配置无效")
                continue
            # 直接使用配置中的type字段
            nodes.append(config)
        return nodes

    def register_node_type(self, type_name: str, node_class):
        """注册节点类型

        Args:
            type_name: 节点类型名称
            node_class: 节点类
        """
        self._node_types[type_name] = node_class

    def get_tools(self, tool_type: str = "agent") -> List[Any]:
        """
        将现有节点转换为Agent可用的工具列表

        Returns:
            List[Any]: Tool对象列表，每个Tool包含name、description、parameters、outputs和run方法
        """
        # 初始化工具缓存
        if not hasattr(self, "_tools_cache"):
            self._tools_cache = {}

        # 延迟导入Tool类，避免循环导入
        from src.agent.base_agent import Tool

        tools = []
        nodes = []
        if tool_type == "agent":
            nodes = self.get_all_agent_nodes()

        tools = []
        for node_info in nodes:
            node_type = node_info.get("type")

            # 检查缓存
            cache_key = (node_type, tool_type)
            if cache_key in self._tools_cache:
                tools.append(self._tools_cache[cache_key])
                continue
            description = node_info.get("description", "No description available")
            # 获取参数信息
            params = node_info.get("params", {})
            param_descriptions = []
            for param_name, param_info in params.items():
                if isinstance(param_info, dict):
                    param_type = param_info.get("type", "unknown")
                    required = param_info.get("required", False)
                    default = param_info.get("default", None)
                    param_desc = param_info.get("description", "No description")

                    param_str = f"- {param_name} ({param_type})"
                    if required:
                        param_str += " [Required]"
                    else:
                        param_str += f" [Optional, Default: {default}]"
                    param_str += f": {param_desc}"
                    param_descriptions.append(param_str)

            # 获取输出信息
            outputs = node_info.get("output", {})
            output_descriptions = []
            for output_name, output_desc in outputs.items():
                output_descriptions.append(f"- {output_name}: {output_desc}")

            # 组合完整描述，按照新的格式要求
            full_description = f"## {node_type}\n"
            full_description += f"**Description**: {description}\n"

            if param_descriptions:
                full_description += (
                    "**Parameters**:\n" + "\n".join(param_descriptions) + "\n\n"
                )

            if output_descriptions:
                full_description += (
                    "**Outputs**:\n" + "\n".join(output_descriptions) + "\n"
                )

            # 获取节点类
            node_class = self._node_types.get(node_type)
            if not node_class:
                logger.error(f"节点类型 {node_type} 未注册，跳过")
                continue

            if node_type == "loop_node":
                node_class.init_engine(node_class, self.engine)

            # 创建一个闭包来保存node_class和node_info
            def create_tool_runner(node_class, node_info):
                async def run(input_text: str) -> str:
                    try:
                        node_instance = node_class()
                        result = await node_instance.agent_execute(input_text)
                        return result["result"]
                    except Exception as e:
                        return f"Error executing node: {str(e)}"

                return run

            # 获取参数和输出定义
            params = node_info.get("params", {})
            outputs = node_info.get("output", {})
            try:
                tool = Tool(
                    name=node_type,  # 使用节点类型作为工具名称
                    description=description,  # 只使用基本描述
                    run=create_tool_runner(node_class, node_info),
                    is_async=True,
                    params=params,  # 直接传递参数定义
                    outputs=outputs,  # 直接传递输出定义
                    full_description=full_description,  # 完整描述包含参数和输出信息
                    max_retries=os.getenv("tool_retry_count", 0),
                    retry_delay=os.getenv("tool_retry_delay", 1.0),
                )
                tools.append(tool)
                self._tools_cache[cache_key] = tool
            except Exception as e:
                logger.error(f"创建工具 {node_type} 失败: {str(e)}", exc_info=True)

        return tools
