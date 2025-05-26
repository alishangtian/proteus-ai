"""Python代码执行节点 - 支持函数定义和参数传递"""

import sys, json
import io
import ast
import inspect
import importlib
from typing import Dict, Any, Callable, List
import black
from .base import BaseNode
import logging

logger = logging.getLogger(__name__)


class PythonExecuteLocalNode(BaseNode):
    """Python代码执行节点 - 支持函数定义和参数传递"""

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        # 获取代码参数（函数定义）
        code = str(params.get("code", ""))
        if not code:
            raise ValueError("code参数不能为空")

        # 格式化代码
        try:
            code = black.format_str(code, mode=black.FileMode())
        except Exception as e:
            # 如果格式化失败，记录错误但继续使用原始代码
            stderr_capture = io.StringIO()
            logger.info(f"代码格式化警告: {str(e)}", file=stderr_capture)
            stderr = stderr_capture.getvalue()
            logger.info(f"Code formatting warning: {stderr}", file=sys.stderr)

        # 获取变量参数（函数执行参数）
        variables = params.get("variables", {})
        if isinstance(variables, str):
            try:
                variables = json.loads(variables)
            except json.JSONDecodeError:
                raise ValueError("variables参数必须是字典类型或有效的JSON字符串")
        if not isinstance(variables, dict):
            raise ValueError("variables参数必须是字典类型")

        # 捕获标准输出和标准错误
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        # 保存原始的标准输出和标准错误
        original_stdout = sys.stdout
        original_stderr = sys.stderr

        # 重定向标准输出和标准错误
        sys.stdout = stdout_capture
        sys.stderr = stderr_capture

        result = None
        error = None
        function_name = None
        function_obj = None

        try:
            # 分析代码中的导入语句
            def extract_imports(code: str) -> List[str]:
                try:
                    tree = ast.parse(code)
                    imports = []
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            for name in node.names:
                                imports.append(name.name)
                        elif isinstance(node, ast.ImportFrom):
                            imports.append(node.module)
                    return imports
                except Exception:
                    return []

            # 准备执行环境
            # 分析并导入所需模块
            required_modules = extract_imports(code)
            exec_globals = {
                "__builtins__": __builtins__,
                "__name__": "__main__",
                "__doc__": None,
                "__package__": None,
            }

            # 动态导入模块
            for module_name in required_modules:
                if module_name:
                    try:
                        module = importlib.import_module(module_name)
                        exec_globals[module_name] = module
                    except ImportError as ie:
                        raise ImportError(f"无法导入模块 {module_name}: {str(ie)}")
            exec_locals = {}

            # 确保模块搜索路径正确
            if not sys.path or sys.path[0] != "":
                sys.path.insert(0, "")

            # 执行代码（函数定义）
            try:
                # 编译代码
                compiled_code = compile(code, "<string>", "exec")

                # 执行代码（定义函数）
                exec(compiled_code, exec_globals, exec_locals)

                # 查找定义的函数
                defined_functions = []
                for name, obj in exec_locals.items():
                    if inspect.isfunction(obj) and not name.startswith("_"):
                        defined_functions.append((name, obj))

                if not defined_functions:
                    raise ValueError("代码中未找到函数定义")

                # 如果有多个函数，使用第一个非下划线开头的函数
                function_name, function_obj = defined_functions[0]

                # 检查函数参数
                sig = inspect.signature(function_obj)

                # 调用函数并传递参数
                result = function_obj(**variables)

            except ImportError as ie:
                error = f"模块导入错误: {str(ie)}"
            except Exception as e:
                error = f"执行错误: {str(e)}"
        finally:
            # 恢复标准输出和标准错误
            sys.stdout = original_stdout
            sys.stderr = original_stderr

        # 获取捕获的输出
        stdout = stdout_capture.getvalue()
        stderr = stderr_capture.getvalue()

        # 构建返回结果
        return_data = {
            "result": result,
            "stdout": stdout,
            "stderr": stderr,
            "success": error is None,
            "function_name": function_name,
        }

        # 如果有错误，添加到返回结果中
        if error:
            return_data["error"] = error

        return return_data

    async def agent_execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        execution_result = await self.execute(params)
        stderr = execution_result.get("stderr", None)
        error = execution_result.get("error", None)
        if error is not None:
            return {"result": f"{error}"}
        if stderr is not None and stderr != "":
            return {"result": f"{stderr}"}
        # result = str(execution_result.get("result", "N/A"))
        return {"result": execution_result.get("result", "代码执行结果为空")}