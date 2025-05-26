from typing import Dict, Any
import logging
import json
import importlib
import os
from datetime import datetime
from pathlib import Path
from .base import BaseNode
from ..core.engine import WorkflowEngine
from ..api.workflow_service import WorkflowService
from .node_config import NodeConfigManager

workflow_logger = logging.getLogger(__name__)
logger = logging.getLogger(__name__)


class WorkflowNode(BaseNode):
    """工作流节点 - 接收任务描述文本并执行相应的工作流

    参数:
        text (str): 任务描述文本

    返回:
        dict: 包含执行状态、错误信息和工作流执行结果
    """

    def __init__(self):
        """初始化工作流节点"""
        super().__init__()
        self.engine = WorkflowEngine()
        self.workflow_service = WorkflowService(self.engine)

        # 配置日志记录
        data_path = os.getenv("DATA_PATH", "./data")
        log_dir = Path(data_path) / "workflow_logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        # 生成唯一的日志文件名：workflow_YYYYMMDD_HHMMSS_<id>.log
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"workflow_{timestamp}_{id(self)}.log"

        # 创建文件处理器
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.INFO)

        # 设置日志格式
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(formatter)

        # 将处理器添加到logger
        workflow_logger.addHandler(file_handler)

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
        text = str(params.get("text", "")).strip()
        if not text:
            raise ValueError("text参数不能为空")

        try:
            # 生成工作流ID
            workflow_id = f"workflow-{id(self)}"

            logger.info(f"开始处理任务 [workflow_id: {workflow_id}]: {text[:100]}...")

            # 使用workflow_service生成工作流
            workflow = await self.workflow_service.generate_workflow(text, workflow_id)

            workflow_logger.info(f"[workflow_id: {workflow_id}]: \n {workflow}")

            if not workflow or not workflow.get("nodes"):
                error_msg = "无法从文本生成有效的工作流"
                logger.error(f"{error_msg}, text: {text}")
                return {"success": False, "error": error_msg, "content": ""}

            # 执行工作流并收集所有结果
            final_results = {}
            async for node_id, result in self.engine.execute_workflow_stream(
                json.dumps(workflow), workflow_id, {}
            ):
                workflow_logger.info(f"[node_id: {node_id}]: result: \n {result}")
                if result.success:
                    final_results[node_id] = result.data

            logger.info(f"任务执行完成 [workflow_id: {workflow_id}]: {text[:100]}...")
            return {
                "success": True,
                "error": None,
                "content": final_results,
                "workflow": workflow,
            }

        except Exception as e:
            error_msg = f"执行工作流时发生错误: {str(e)}"
            logger.error(f"{error_msg}, text: {text}")
            return {"success": False, "error": error_msg, "content": ""}

    async def agent_execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        execution_result = await self.execute(params)
        if not execution_result.get("success"):  # 如果执行失败，则返回错误信息
            return {"result": execution_result.get("error", "")}
        return {
            "result": execution_result.get("content", ""),
            "workflow": execution_result.get("workflow", {}),
        }
