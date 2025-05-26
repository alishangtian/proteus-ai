"""文件写入节点"""

import os
from typing import Dict, Any
from .base import BaseNode
from ..api.config import API_CONFIG


class FileWriteNode(BaseNode):
    """文件写入节点"""

    def __init__(self):
        super().__init__()
        # 从API_CONFIG中读取默认写入路径
        self.default_write_path = API_CONFIG["file_write_path"]

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        filename = params.get("filename")
        content = params.get("content")
        format = params.get("format", "txt")  # 默认格式为txt
        encoding = params.get("encoding", "utf-8")

        # 构建完整的文件路径，添加文件格式后缀
        if not filename.endswith(f".{format}"):
            filename = f"{filename}.{format}"

        # 使用配置的默认路径构建完整的文件路径
        file_path = os.path.join(self.default_write_path, filename)
        # 默认写入模式
        mode = "w"
        # 确保默认目录存在
        os.makedirs(self.default_write_path, exist_ok=True)

        try:
            with open(file_path, mode, encoding=encoding) as f:
                f.write(content)
            return {
                "result": "success",
                "path": file_path,
                "filename": filename,
                "format": format,
                "bytes_written": len(content.encode(encoding)),
                "encoding": encoding,
                "mode": mode,
            }
        except Exception as e:
            raise ValueError(f"写入文件失败: {str(e)}")

    async def agent_execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行节点并将结果转换为统一格式

        将文件写入结果转换为包含写入状态、路径和大小信息的文本。

        Args:
            params: 节点参数

        Returns:
            Dict[str, Any]: 执行结果，包含纯文本格式的'result'键
        """
        try:
            execute_result = await self.execute(params)
            # 组织写入结果信息
            result_text = (
                f"File written successfully:\n"
                f"- Path: {execute_result['path']}\n"
                f"- Size: {execute_result['bytes_written']} bytes\n"
                f"- Format: {execute_result['format']}\n"
                f"- Encoding: {execute_result['encoding']}"
            )
            return {"result": result_text}
        except Exception as e:
            return {"result": f"Error: {str(e)}", "error": str(e)}
