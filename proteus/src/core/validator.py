from typing import Dict, List, Type
import networkx as nx
from ..nodes.base import BaseNode

class WorkflowValidator:
    """工作流验证器"""
    
    @staticmethod
    def validate_workflow(workflow: Dict, node_types: Dict[str, Type[BaseNode]]) -> bool:
        """验证工作流的DAG结构
        
        Args:
            workflow: 工作流定义
            node_types: 已注册的节点类型
            
        Returns:
            bool: 是否合法
            
        Raises:
            ValueError: DAG验证失败时抛出，包含具体原因
        """
        nodes = workflow["nodes"]
        edges = workflow.get("edges", [])  # edges字段可选，默认为空列表
            
        # 检查节点ID唯一性
        node_ids = [node["id"] for node in nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("存在重复的节点ID")
            
        # 检查节点类型是否已注册
        for node in nodes:
            if node["type"] not in node_types:
                raise ValueError(f"未注册的节点类型: {node['type']}")
                
        # 构建图并检查是否有环
        G = nx.DiGraph()
        for node in nodes:
            G.add_node(node["id"])
        for edge in edges:
            G.add_edge(edge["from"], edge["to"])
            
        try:
            cycle = nx.find_cycle(G)
            raise ValueError(f"工作流中存在环: {cycle}")
        except nx.NetworkXNoCycle:
            pass
            
        return True
