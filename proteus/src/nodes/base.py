"""节点基类定义"""

from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseNode(ABC):
    """节点基类"""
    
    @abstractmethod
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行节点
         
        Args:
            params: 节点参数
            
        Returns:
            Dict[str, Any]: 执行结果，必须包含'result'键
        """
        pass
    
    @abstractmethod
    async def agent_execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """智能体调用节点
         
        Args:
            params: 节点参数
            
        Returns:
            Dict[str, Any]: 执行结果，必须包含'result'键
        """
        pass
