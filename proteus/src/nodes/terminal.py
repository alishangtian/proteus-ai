"""终端命令执行节点"""

import subprocess
from typing import Dict, Any
from .base import BaseNode


class TerminalNode(BaseNode):
    """终端命令执行节点"""

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        command = str(params["command"])
        shell = params.get("shell", True)

        try:
            # 执行shell命令
            process = subprocess.run(
                command, shell=shell, capture_output=True, text=True
            )

            return {
                "stdout": process.stdout,
                "stderr": process.stderr,
                "return_code": process.returncode,
                "success": process.returncode == 0,
            }
        except Exception as e:
            return {"stdout": "", "stderr": str(e), "return_code": -1, "success": False}

    async def agent_execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行节点并将结果转换为统一格式

        将终端命令执行结果转换为包含命令、状态码和输出信息的文本。

        Args:
            params: 节点参数

        Returns:
            Dict[str, Any]: 执行结果，包含纯文本格式的'result'键
        """
        try:
            execute_result = await self.execute(params)

            # 组织命令执行结果信息
            status = "Success" if execute_result["success"] else "Failed"
            result_text = (
                f"Command execution {status.lower()}:\n"
                f"- Command: {params['command']}\n"
                f"- Status: {status} (return code: {execute_result['return_code']})\n"
            )

            # 添加标准输出（如果有）
            if execute_result["stdout"]:
                result_text += f"\nStandard Output:\n{execute_result['stdout'].strip()}"

            # 添加错误输出（如果有）
            if execute_result["stderr"]:
                result_text += f"\nError Output:\n{execute_result['stderr'].strip()}"

            return {"result": result_text}
        except Exception as e:
            return {"result": f"Error: {str(e)}", "error": str(e)}
