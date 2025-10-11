"""Python代码执行节点 - 支持函数定义和参数传递"""

import sys, json, os
import io
from typing import Dict, Any
import black
import httpx
from .base import BaseNode
import logging

logger = logging.getLogger(__name__)

SANDBOX_HOST = os.getenv("SANDBOX_HOST", "http://127.0.0.1")
SANDBOX_PORT = int(os.getenv("SANDBOX_PORT", "8000"))
SANDBOX_ERQUEST_TIMEOUT = float(os.getenv("SANDBOX_ERQUEST_TIMEOUT", 3600))
SANDBOX_API_KEY = os.getenv(
    "SANDBOX_API_KEY", "El0/osJhMJnaQMCYiyOAOD4WGgJb4vbiMhQgf7g1DXgHxz10KuWodvQr"
)
if "http://" not in SANDBOX_HOST:
    SANDBOX_HOST = "http://" + SANDBOX_HOST
SANDBOX_API_URL = f"{SANDBOX_HOST}:{SANDBOX_PORT}/v1/sandbox/run"


class PythonExecuteNode(BaseNode):
    """Python代码执行节点 - 支持函数定义和参数传递"""

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        # 获取代码参数（函数定义）
        code = str(params.get("code", ""))
        if not code:
            raise ValueError("code参数不能为空")

        # 获取语言类型，默认为python3
        language = str(params.get("language", "python")).lower()
        if language not in ["python", "shell"]:
            raise ValueError("language参数必须是python或shell")

        # 获取是否启用网络访问
        enable_network = params.get("enable_network", True)

        # 格式化代码
        # try:
        #     code = black.format_str(code, mode=black.FileMode())
        # except Exception as e:
        #     # 如果格式化失败，记录错误但继续使用原始代码
        #     logger.warning(f"代码格式化警告: {str(e)}")

        # 获取变量参数（函数执行参数）
        variables = params.get("variables", {})
        if isinstance(variables, str):
            try:
                variables = json.loads(variables)
            except json.JSONDecodeError:
                raise ValueError("variables参数必须是字典类型或有效的JSON字符串")
        if not isinstance(variables, dict):
            raise ValueError("variables参数必须是字典类型")

        try:
            # 将变量注入代码环境（仅对python3有效）
            if language == "python" and variables:
                # 生成变量定义代码
                var_code = "\n".join([f"{k} = {repr(v)}" for k, v in variables.items()])
                # 将变量定义添加到原始代码前面
                code = f"{var_code}\n{code}"

            logger.info(f"虚拟环境API请求参数code: {code}")

            # 调用虚拟环境API执行代码
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {SANDBOX_API_KEY}",
            }

            payload = {
                "code": code,
                "language": language,
                "enable_network": enable_network,
            }

            logger.info(f"虚拟环境API请求参数payload: {payload}")

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    SANDBOX_API_URL,
                    headers=headers,
                    json=payload,
                    timeout=SANDBOX_ERQUEST_TIMEOUT,
                )
                logger.info(f"虚拟环境API返回结果: {response.json()}")
                response.raise_for_status()
                api_result = response.json()

            # 处理API返回结果
            if api_result.get("code") != 0:
                error_msg = api_result.get("stderr", "虚拟环境执行失败")
                return {
                    "result": None,
                    "stdout": "",
                    "stderr": error_msg,
                    "success": False,
                    "error": error_msg,
                }

            return {
                "result": api_result.get("stdout", ""),
                "stdout": api_result.get("stdout", ""),
                "stderr": api_result.get("stderr", ""),
                "success": True,
                "function_name": None,  # 虚拟环境执行不返回函数名
            }

        except httpx.HTTPStatusError as e:
            error = f"虚拟环境API请求失败: {str(e)}"
            logger.error(error)
            return {
                "result": None,
                "stdout": "",
                "stderr": error,
                "success": False,
                "error": error,
            }
        except Exception as e:
            error = f"虚拟环境执行错误: {str(e)}"
            logger.error(error)
            return {
                "result": None,
                "stdout": "",
                "stderr": error,
                "success": False,
                "error": error,
            }

    async def agent_execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        execution_result = await self.execute(params)
        success = execution_result.get("success", False)
        stderr = execution_result.get("stderr", None)
        error = execution_result.get("error", None)
        stdout = execution_result.get("stdout", None)
        if not success:
            return {"result": f"{stderr}\n{error}"}
        return {"result": stdout or "代码执行结果为空"}
