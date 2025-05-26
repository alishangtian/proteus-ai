from typing import Dict, Any
import logging
import json
import importlib
import os
from datetime import datetime
from pathlib import Path
from src.nodes.base import BaseNode
from src.core.engine import WorkflowEngine
from src.nodes.node_config import NodeConfigManager
from src.api.utils import convert_node_result
from src.api.events import create_result_event

logger = logging.getLogger(__name__)


class WorkflowExecuteNode(BaseNode):
    """工作流执行节点 - 执行已生成的工作流

    参数:
        workflow (dict): 要执行的工作流定义
        workflow_id (str, optional): 工作流ID，如不提供则自动生成

    返回:
        dict: 包含执行状态、错误信息和工作流执行结果
    """

    def __init__(self):
        """初始化工作流执行节点"""
        super().__init__()
        self.engine = WorkflowEngine()

        # 配置日志记录
        data_path = os.getenv("DATA_PATH", "./data")
        log_dir = Path(data_path) / "workflow_logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        # 生成唯一的日志文件名：workflow_exec_YYYYMMDD_HHMMSS_<id>.log
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"workflow_exec_{timestamp}_{id(self)}.log"

        # 创建文件处理器
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.INFO)

        # 设置日志格式
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(formatter)

        # 将处理器添加到logger
        logger.addHandler(file_handler)

        logger.info(f"工作流执行日志将被记录到: {log_file}")

        self._register_nodes()

    def _register_nodes(self):
        """注册所有可用的节点类型"""
        try:
            node_manager = NodeConfigManager.get_instance()
            node_configs = node_manager.node_configs

            for class_name in node_configs.keys():
                node_type = node_configs[class_name].get("type")
                if not node_type:
                    logger.info(f"节点 {class_name} 未配置type字段，跳过注册")
                    continue

                try:
                    module = importlib.import_module(f"src.nodes.{node_type}")
                    node_class = getattr(module, class_name)
                    self.engine.register_node_type(node_type, node_class)
                    logger.info(f"注册节点类型 {node_type} 成功")
                except Exception as e:
                    logger.error(f"注册节点类型 {node_type} 失败: {str(e)}")
                    raise
        except Exception as e:
            logger.error(f"节点注册过程失败: {str(e)}")
            raise

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        workflow = params.get("workflow")
        if not workflow:
            raise ValueError("workflow参数不能为空")

        # 如果传入的是字符串，尝试解析为JSON
        if isinstance(workflow, str):
            try:
                workflow = json.loads(workflow)
            except json.JSONDecodeError:
                raise ValueError("workflow参数必须是有效的JSON字符串或字典")

        # 确保workflow是字典类型
        if not isinstance(workflow, dict):
            raise ValueError("workflow参数必须是字典类型")

        # 检查工作流是否有效
        if not workflow.get("nodes"):
            raise ValueError("工作流必须包含nodes字段")

        workflow_id = params.get("workflow_id", f"workflow-{id(self)}")
        chat_id = params.get("chat_id", workflow_id)  # 用于流式传输的聊天ID
        stream_manager = params.get("stream_manager")  # 从参数中获取stream_manager

        try:
            logger.info(f"开始执行工作流 [workflow_id: {workflow_id}]")

            # 执行工作流并收集所有结果
            final_results = {}
            async for node_id, result in self.engine.execute_workflow_stream(
                json.dumps(workflow), workflow_id, {}
            ):
                logger.info(f"[node_id: {node_id}]: result: \n {result}")

                # 如果有stream_manager，发送节点执行进度和结果
                if stream_manager:
                    # 使用工具函数转换结果为可序列化的字典
                    result_dict = convert_node_result(node_id, result)
                    # 立即发送节点状态更新
                    event = await create_result_event(node_id, result_dict)
                    await stream_manager.send_message(chat_id, event)

                if result.success:
                    final_results[node_id] = result.data

            logger.info(f"工作流执行完成 [workflow_id: {workflow_id}]")
            return {
                "success": True,
                "error": None,
                "content": final_results,
            }

        except Exception as e:
            error_msg = f"执行工作流时发生错误: {str(e)}"
            logger.error(f"{error_msg}")
            return {"success": False, "error": error_msg, "content": ""}

    async def agent_execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行工作流节点的agent_execute方法

        参数:
            params: 执行参数，可能包含以下字段：
                - workflow: 工作流定义
                - workflow_id: 工作流ID
                - chat_id: 聊天会话ID

        返回:
            Dict[str, Any]: 执行结果
        """
        # 从全局上下文获取stream_manager
        execution_result = await self.execute(params)
        if not execution_result.get("success"):  # 如果执行失败，则返回错误信息
            return {"result": execution_result.get("error", "")}
        return {
            "result": execution_result.get("content", ""),
        }
