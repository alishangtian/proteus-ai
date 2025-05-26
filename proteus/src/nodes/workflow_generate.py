from typing import Dict, Any
import logging
import json
import os
from datetime import datetime
from pathlib import Path
from .base import BaseNode
from ..api.workflow_service import WorkflowService
from ..core.engine import WorkflowEngine

logger = logging.getLogger(__name__)


class WorkflowGenerateNode(BaseNode):
    """工作流生成节点 - 接收任务描述文本并生成相应的工作流
    
    参数:
        text (str): 任务描述文本
    
    返回:
        dict: 包含生成状态、错误信息和生成的工作流
    """
    
    def __init__(self):
        """初始化工作流生成节点"""
        super().__init__()
        self.engine = WorkflowEngine()
        self.workflow_service = WorkflowService(self.engine)
        
        # 配置日志记录
        data_path = os.getenv("DATA_PATH", "./data")
        log_dir = Path(data_path) / "workflow_logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # 生成唯一的日志文件名：workflow_gen_YYYYMMDD_HHMMSS_<id>.log
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"workflow_gen_{timestamp}_{id(self)}.log"
        
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
        
        logger.info(f"工作流生成日志将被记录到: {log_file}")
    
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        text = str(params.get("text", "")).strip()
        if not text:
            raise ValueError("text参数不能为空")
        
        try:
            # 生成工作流ID
            workflow_id = f"workflow-{id(self)}"
            
            logger.info(f"开始生成工作流 [workflow_id: {workflow_id}]: {text[:100]}...")
            
            # 使用workflow_service生成工作流
            workflow = await self.workflow_service.generate_workflow(text, workflow_id)
            
            logger.info(f"[workflow_id: {workflow_id}]: \n {workflow}")
            
            if not workflow or not workflow.get("nodes"):
                error_msg = "无法从文本生成有效的工作流"
                logger.error(f"{error_msg}, text: {text}")
                return {"success": False, "error": error_msg, "workflow": {}}
            
            logger.info(f"工作流生成完成 [workflow_id: {workflow_id}]: {text[:100]}...")
            return {
                "success": True,
                "error": None,
                "workflow": workflow,
            }
            
        except Exception as e:
            error_msg = f"生成工作流时发生错误: {str(e)}"
            logger.error(f"{error_msg}, text: {text}")
            return {"success": False, "error": error_msg, "workflow": {}}
    
    async def agent_execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        execution_result = await self.execute(params)
        if not execution_result.get("success"):  # 如果执行失败，则返回错误信息
            return {"result": execution_result.get("error", "")}
        return {
            "result": execution_result.get("workflow", {})
        }