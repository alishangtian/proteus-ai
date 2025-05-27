"""节点配置管理模块"""

import yaml
import os
import json
import logging
from typing import Dict, Optional, List, Type, Any, Callable
import threading
# 延迟导入Tool，避免循环导入
from .base import BaseNode
from ..core.engine import WorkflowEngine
from ..api.config import API_CONFIG

logger = logging.getLogger(__name__)

class NodeConfigManager:
    """节点配置管理类（线程安全单例模式）"""
    
    _instance = None
    _lock = threading.Lock()
    _initialized = False

    @classmethod
    def get_instance(cls) -> 'NodeConfigManager':
        """获取单例实例"""
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = cls()
        return cls._instance

    def __init__(
        self,
        config_path: str = None,
        agent_config_path: str = None,
        workflow_config_path: str = None,
        engine: WorkflowEngine = None,
    ):
        # 如果已经初始化过，直接返回，保证单例
        if self.__class__._initialized:
            return
        
        # 初始化基础配置参数
        self.config_path = config_path
        self.agent_config_path = agent_config_path
        self.workflow_config_path = workflow_config_path
        self.engine = engine
        self._node_types: Dict[str, Type[BaseNode]] = {}
        self._tools_cache: Dict[tuple, List[Any]] = {}  # 新增工具缓存
        
        # 设置默认配置文件路径
        self._set_default_paths()
        
        # 直接加载所有配置
        self.node_configs = self._load_config()
        self.agent_node_configs = self._load_agent_config()
        self.workflow_node_configs = self._load_workflow_config()
        # 直接注册节点类型
        self._register_node_types()
        # 标记为已初始化
        self.__class__._initialized = True

    def _set_default_paths(self):
        """设置默认配置文件路径"""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        if self.config_path is None:
            nodes_config_path = os.path.join(current_dir, "../nodes/node_config.yaml")
            if os.path.exists(nodes_config_path):
                self.config_path = nodes_config_path
        
        if self.agent_config_path is None:
            agent_nodes_config_path = os.path.join(
                current_dir, "../nodes/agent_node_config.yaml"
            )
            if os.path.exists(agent_nodes_config_path):
                self.agent_config_path = agent_nodes_config_path
        
        if self.workflow_config_path is None:
            workflow_nodes_config_path = os.path.join(
                current_dir, "../nodes/workflow_node_config.yaml"
            )
            if os.path.exists(workflow_nodes_config_path):
                self.workflow_config_path = workflow_nodes_config_path

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
                    logger.warning(f"节点配置 {config_key} 缺少必要字段(type或class)，跳过注册")
                    continue                
                # 解析类路径
                module_path, _, class_name = class_path.rpartition('.')
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
                    raise AttributeError(f"模块 {module_path} 中没有找到类 {class_name}")
                
                # 验证节点类
                if not issubclass(node_class, BaseNode):
                    raise TypeError(f"类 {class_name} 不是BaseNode的子类")
                
                # 注册节点类型
                self.register_node_type(node_type, node_class)
                registered_count += 1
                
            except ImportError as ie:
                logger.error(f"导入节点模块 {class_name} 失败: {str(ie)}", exc_info=True)
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
                logger.error(f"注册节点类型 {class_name} 时发生意外错误: {str(e)}", exc_info=True)
                failed_count += 1
                continue
        
        logger.info(f"节点类型注册完成 - 成功: {registered_count}, 失败: {failed_count}")
        if failed_count > 0:
            logger.warning(f"有 {failed_count} 个节点类型注册失败，请检查日志获取详细信息")
            # 节点配置变更时清空缓存
            if hasattr(self, '_tools_cache'):
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

    def _load_workflow_config(self) -> Dict:
        """加载工作流节点配置"""
        try:
            if os.path.exists(self.workflow_config_path):
                with open(self.workflow_config_path, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f)
                    return config
            logger.warning(f"工作流配置文件 {self.workflow_config_path} 不存在，返回空配置")
            return {}
        except Exception as e:
            logger.error(f"加载工作流节点配置失败: {str(e)}", exc_info=True)
            return {}

    def get_node_info(self, node_type: str) -> Optional[Dict]:
        """
        获取节点配置信息

        Args:
            node_type: 节点类型

        Returns:
            节点配置信息，如果节点不存在则返回None
        """
        # 配置已在初始化时加载
        
        # 遍历配置查找匹配的节点类型
        for config in self.node_configs.values():
            if isinstance(config, dict) and config.get("type") == node_type:
                return config
        return None

    def get_all_nodes(self) -> List[Dict]:
        """
        获取所有节点的配置信息

        Returns:
            所有节点的配置信息列表
        """
        # 配置已在初始化时加载
        
        nodes = []
        for class_name, config in self.node_configs.items():
            # 确保配置是字典类型
            if not isinstance(config, dict):
                logger.warning(f"节点 {class_name} 的配置无效")
                continue
            # 直接使用配置中的type字段
            nodes.append(config)
        return nodes

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

    def get_all_workflow_nodes(self) -> List[Dict]:
        """
        获取所有workflow节点的配置信息

        Returns:
            所有节点的配置信息列表
        """
        # 配置已在初始化时加载
        
        nodes = []
        for class_name, config in self.workflow_node_configs.items():
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
        if not hasattr(self, '_tools_cache'):
            self._tools_cache = {}
        
        # 延迟导入Tool类，避免循环导入
        from ..agent.base_agent import Tool
        
        tools = []
        nodes = []
        if tool_type == "agent":
            nodes = self.get_all_agent_nodes()
        elif tool_type == "workflow":
            nodes = self.get_all_workflow_nodes()
            logger.info(f"获取w工作流节点 {nodes}")

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
            full_description += f"**Description**: {description}\n\n"
            
            if param_descriptions:
                full_description += "**Parameters**:\n" + "\n".join(param_descriptions) + "\n\n"
            
            if output_descriptions:
                full_description += "**Outputs**:\n" + "\n".join(output_descriptions) + "\n\n"
            
            # 使用代码块格式包装Usage部分
            full_description += "**Usage**:\n```xml\n"
            full_description += f"<{node_type}>\n"
            
            for param_name, param_info in params.items():
                if isinstance(param_info, dict):
                    param_example = param_info.get("example")
                    full_description += f"  <{param_name}>{param_example}</{param_name}>\n"
            
            full_description += f"</{node_type}>\n```\n"

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
                    max_retries=API_CONFIG["tool_retry_count"],
                    retry_delay=API_CONFIG["tool_retry_delay"],
                )
                tools.append(tool)
                self._tools_cache[cache_key] = tool
            except Exception as e:
                logger.error(f"创建工具 {node_type} 失败: {str(e)}", exc_info=True)
                
        return tools

    def get_nodes_description(self) -> str:
        """
        获取所有节点的描述信息，以清晰、结构化的方式展示每个节点的功能和配置

        Returns:
            str: 格式化的节点描述字符串
        """
        # 配置已在初始化时加载
        
        try:
            node_descriptions = []
            for node in self.get_all_nodes():
                try:
                    node_type = node.get("type", "unknown")
                    name = node.get("name", node_type)
                    description = node.get("description", "No description available")
                    params = node.get("params", {})
                    output = node.get("output", {})
                    config = node.get("config", {})

                    # 构建节点基本信息
                    node_desc = [
                        f"Node: {name}",
                        f"Type: {node_type}",
                        "-" * 50,
                        "Description:",
                        f"  {description}",
                        "",
                    ]

                    # 构建配置信息（如果有）
                    if config:
                        node_desc.extend(
                            [
                                "Configuration:",
                                *[f"  {key}: {value}" for key, value in config.items()],
                                "",
                            ]
                        )

                    # 构建输入参数描述
                    param_desc = []
                    for param_name, param_info in params.items():
                        if not isinstance(param_info, dict):
                            continue

                        param_type = param_info.get("type", "unknown")
                        required = param_info.get("required", False)
                        default = param_info.get("default", None)
                        param_description = param_info.get(
                            "description", "No description"
                        )

                        # 构建格式化的参数描述
                        param_str = [f"  {param_name}:", f"    Type: {param_type}"]

                        # 添加必填/可选状态
                        if not required:
                            param_str.append(f"    Optional: Yes (Default: {default})")
                        else:
                            param_str.append("    Required: Yes")

                        # 添加参数描述（支持多行）
                        desc_lines = param_description.split("\n")
                        param_str.append("    Description:")
                        param_str.extend(
                            [f"      {line.strip()}" for line in desc_lines]
                        )

                        param_desc.extend(param_str)

                    # 添加输入参数部分
                    if param_desc:
                        node_desc.extend(["Input Parameters:", *param_desc, ""])

                    # 添加输出参数部分
                    if output:
                        node_desc.extend(
                            [
                                "Output Parameters:",
                                *[
                                    f"  {key}:\n    Description: {value}"
                                    for key, value in output.items()
                                ],
                                "",
                            ]
                        )

                    # 添加分隔线
                    node_desc.append("=" * 80 + "\n")

                    node_descriptions.append("\n".join(node_desc))
                except Exception as e:
                    print(
                        f"处理节点 {node.get('type', 'unknown')} 描述时出错: {str(e)}"
                    )
                    continue

            return "\n".join(node_descriptions)
        except Exception as e:
            print(f"生成节点描述时出错: {str(e)}")
            return "获取节点描述失败"

    def get_nodes_json_example(self) -> str:
        """
        获取节点配置的JSON示例，展示一个实际的工作流场景

        Returns:
            str: JSON格式的工作流示例
        """
        # 配置已在初始化时加载
        workflow_json = {
            "nodes": [
                # 第一层：搜索相关论文
                {
                    "id": "arxiv_search",
                    "type": "arxiv_search",
                    "params": {"query": "Large Language Models recent advances"},
                },
                # 第二层：循环处理搜索结果
                {
                    "id": "loop_papers",
                    "type": "loop_node",
                    "params": {
                        "array": "${arxiv_search.results}",
                        "workflow_json": {
                            "nodes": [
                                # 获取每篇论文的PDF内容
                                {
                                    "id": "crawler",
                                    "type": "web_crawler",
                                    "params": {"url": "${item.pdf_url}"},
                                },
                                # 使用AI分析论文内容
                                {
                                    "id": "paper_analysis",
                                    "type": "chat",
                                    "params": {
                                        "system_prompt": "You are a research assistant. Analyze the given paper and extract key findings and contributions.",
                                        "user_question": "Please analyze this paper and provide key findings:\n${crawler.content}",
                                        "temperature": 0.3,
                                    },
                                },
                                # 保存分析结果到文件
                                {
                                    "id": "save_analysis",
                                    "type": "file_write",
                                    "params": {
                                        "filename": "${item.entry_id}",
                                        "content": "Title: ${item.title}\nAuthors: ${item.authors}\nAnalysis:\n${paper_analysis.response}",
                                        "format": "txt",
                                    },
                                },
                            ],
                            "edges": [
                                {"from": "crawler", "to": "paper_analysis"},
                                {"from": "paper_analysis", "to": "save_analysis"},
                            ],
                        },
                    },
                },
                # 第三层：数据库操作
                {
                    "id": "db_save",
                    "type": "db_execute",
                    "params": {
                        "host": "localhost",
                        "database": "research_db",
                        "user": "researcher",
                        "password": "password123",
                        "statement": "INSERT INTO paper_analysis (paper_id, title, authors, analysis) VALUES (?, ?, ?, ?)",
                        "parameters": [
                            "${item.entry_id}",
                            "${item.title}",
                            "${item.authors}",
                            "${paper_analysis.response}",
                        ],
                    },
                },
                # 第四层：执行Python代码进行数据分析
                {
                    "id": "data_analysis",
                    "type": "python_execute",
                    "params": {
                        "code": """
                        import pandas as pd
                        import numpy as np
                        
                        def analyze_results(data):
                            # 进行数据分析
                            df = pd.DataFrame(data)
                            summary = {
                                'total_papers': len(df),
                                'avg_length': df['analysis'].str.len().mean(),
                                'key_topics': df['analysis'].str.lower().str.findall(r'\\w+').explode().value_counts().head(10).to_dict()
                            }
                            return summary
                        """,
                        "variables": {"data": "${loop_papers.results}"},
                        "timeout": 60,
                    },
                },
            ],
            "edges": [
                {"from": "arxiv_search", "to": "loop_papers"},
                {"from": "loop_papers", "to": "db_save"},
                {"from": "db_save", "to": "data_analysis"},
            ],
        }
        return json.dumps(workflow_json, indent=2, ensure_ascii=False)
