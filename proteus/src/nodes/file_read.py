"""文件读取节点"""

import os
from typing import Dict, Any
from .base import BaseNode


class FileReadNode(BaseNode):
    """文件读取节点"""

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        file_path = str(params["path"])
        encoding = str(params.get("encoding", "utf-8"))

        if not os.path.exists(file_path):
            raise ValueError(f"文件不存在: {file_path}")

        try:
            with open(file_path, "r", encoding=encoding) as f:
                content = f.read()
            return {"result": content, "path": file_path, "encoding": encoding}
        except Exception as e:
            raise ValueError(f"读取文件失败: {str(e)}")

    async def agent_execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行节点并返回result字段

        Args:
            params: 节点参数

        Returns:
            Dict[str, Any]: 执行结果中的result字段
        """
        result = await self.execute(params)
        return {"result": result.get("result", "")}
