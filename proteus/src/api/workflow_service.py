"""工作流服务模块"""

import json
import logging
from typing import Dict, Optional, AsyncGenerator
from string import Template
from ..core.engine import WorkflowEngine, NodeResult
from ..nodes.node_config import NodeConfigManager
from .llm_api import call_llm_api, call_llm_api_stream
from ..agent.prompt.workflow_prompt import (
    WORKFLOW_GENERATE_SYSTEM_PROMPT,
    WORKFLOW_GENERATE_USER_PROMPT,
    WORKFLOW_EXPLAIN_SYSTEM_PROMPT
)

# 配置日志记录
logger = logging.getLogger(__name__)

class WorkflowService:
    def __init__(self, engine: WorkflowEngine):
        self.engine = engine
        
    async def generate_workflow(self, text: str, request_id: str = None) -> Dict:
        """生成工作流JSON
        
        Args:
            text: 用户输入文本
            request_id: 请求ID用于日志追踪
            
        Returns:
            Dict: 工作流定义
        """
        node_manager = NodeConfigManager.get_instance()
        node_descriptions = node_manager.get_nodes_description()
        nodes_json_example = node_manager.get_nodes_json_example()
        inference_format = '${node_id.results}'
        
        # 使用Template进行格式化填充
        system_values = {
            "node_descriptions": node_descriptions,
            "inference_format": inference_format
        }
        system_prompt = Template(WORKFLOW_GENERATE_SYSTEM_PROMPT).safe_substitute(system_values)
        
        user_values = {
            "nodes_json_example": nodes_json_example
        }
        user_prompt = Template(WORKFLOW_GENERATE_USER_PROMPT).safe_substitute(user_values)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content":"问题：" + text  + "\n" + user_prompt}
        ]
        
                
        workflow_str = await call_llm_api(messages, request_id)
        try:
            if "```json" in workflow_str:
                workflow_str = workflow_str.split("```json")[1].split("```")[0]
            return json.loads(workflow_str)
        except:
            return {"nodes": [], "edges": []}

    async def explain_workflow_result(
        self,
        original_text: str,
        workflow: Dict,
        results: Optional[Dict[str, NodeResult]],
        request_id: str = None
    ) -> AsyncGenerator[str, None]:
        """解释工作流执行结果（流式）
        
        Args:
            original_text: 用户原始输入
            workflow: 工作流定义
            results: 工作流执行结果
            request_id: 请求ID用于日志追踪
            
        Yields:
            str: 解释内容片段
        """
        workflow_desc = []
        
        if not results:
            yield "工作流执行失败，未能获取执行结果。"
            return
            
        for node in workflow["nodes"]:
            node_id = node["id"]
            node_type = node["type"]
            node_result = results.get(node_id)
            
            if node_result and node_result.success:
                result_data = node_result.data
                workflow_desc.append(f"- {node_type}({node_id}): 成功，输出={result_data}")
            else:
                error = node_result.error if node_result else "未执行"
                workflow_desc.append(f"- {node_type}({node_id}): 失败，错误={error}")
        
        workflow_status = "\n".join(workflow_desc)
        
        # 使用Template进行格式化填充
        system_values = {
            "workflow_status": workflow_status
        }
        system_prompt = Template(WORKFLOW_EXPLAIN_SYSTEM_PROMPT).safe_substitute(system_values)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"{original_text}"}
        ]
        
        async for chunk in call_llm_api_stream(messages, request_id):
            yield chunk
