from dataclasses import dataclass, asdict
import json
from typing import Dict, Any, Optional
from .enums import NodeStatus

@dataclass
class NodeResult:
    """节点执行结果"""
    success: bool
    status: NodeStatus
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    
    def to_json(self) -> str:
        """将NodeResult转换为JSON字符串"""
        result_dict = asdict(self)
        result_dict['status'] = result_dict['status'].value
        return result_dict
    
    def to_data(self) -> str:
        """将NodeResult转换为JSON字符串"""
        return self.data