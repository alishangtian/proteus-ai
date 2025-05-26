"""工具函数模块"""

from typing import Any, Dict, Optional
import json
from datetime import datetime
from pydantic import BaseModel, Field

class ApiResponse(BaseModel):
    """API标准响应格式"""
    event: str
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

def ensure_serializable(obj: Any) -> Any:
    """确保对象是可JSON序列化的
    
    Args:
        obj: 任意Python对象
        
    Returns:
        转换后的可JSON序列化对象
    """
    if obj is None:
        return None
    elif isinstance(obj, (str, int, float, bool)):
        return obj
    elif isinstance(obj, (list, tuple)):
        return [ensure_serializable(item) for item in obj]
    elif isinstance(obj, dict):
        return {str(k): ensure_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, datetime):
        return obj.isoformat()
    else:
        # 对于其他类型，尝试转换为字符串
        try:
            return str(obj)
        except:
            return None

def convert_node_result(node_id: str, result: Any) -> Dict:
    """转换节点结果为可序列化的字典
    
    Args:
        node_id: 节点ID
        result: 节点执行结果
        
    Returns:
        Dict: 可序列化的结果字典
    """
    return {
        "node_id": node_id,
        "success": result.success,
        "status": result.status.value,
        "data": ensure_serializable(result.data) if result.success else None,
        "error": str(result.error) if result.error else None
    }
