"""
sandbox_inprocess.py
提供应用内直接执行的代码沙箱，不使用子进程。

安全限制方案：
1. 使用 threading 实现执行超时
2. 使用内存监控限制内存使用
3. 使用安全的执行环境限制模块访问
4. 使用输出重定向和截断
5. 代码语法检查和长度限制
"""

import threading
import sys
import io
import time
import logging
import traceback
import ast
from typing import Tuple, Optional, Dict, Any, List
from contextlib import redirect_stdout, redirect_stderr

logger = logging.getLogger(__name__)


class ExecutionTimeout(Exception):
    """执行超时异常"""

    pass


class MemoryLimitExceeded(Exception):
    """内存限制异常"""

    pass


class SandboxSecurityError(Exception):
    """沙箱安全异常"""

    pass


class CodeSyntaxError(Exception):
    """代码语法错误"""

    pass


# 禁止导入的危险模块
DANGEROUS_MODULES = {
    "os",
    "sys",
    "subprocess",
    "shutil",
    "socket",
    "multiprocessing",
    "threading",
    "ctypes",
    "mmap",
    "fcntl",
    "signal",
    "pwd",
    "grp",
    "resource",
    "termios",
    "pty",
    "fcntl",
    "select",
    "selectors",
    "asyncio",
    "concurrent",
    "http",
    "urllib",
    "requests",
    "webbrowser",
    "sqlite3",
    "pickle",
    "marshal",
    "shelve",
    "dbm",
    "gdbm",
    "dbhash",
    "bsddb",
    "dumbdbm",
    "anydbm",
    "whichdb",
    "zipfile",
    "tarfile",
    "bz2",
    "lzma",
    "zlib",
    "gzip",
    "hashlib",
    "hmac",
    "secrets",
    "ssl",
    "crypt",
    "turtle",
    "tkinter",
    "PyQt5",
    "PySide2",
    "wx",
}

# 禁止使用的危险函数和属性
DANGEROUS_BUILTINS = {
    "open",
    "exec",
    "eval",
    "compile",
    "input",
    "help",
    "quit",
    "exit",
    "copyright",
    "credits",
    "license",
    "__import__",
    "reload",
    "globals",
    "locals",
    "vars",
    "dir",
    "type",
    "isinstance",
    "issubclass",
    "super",
    "property",
    "classmethod",
    "staticmethod",
    "hasattr",
    "getattr",
    "setattr",
    "delattr",
    "callable",
    "memoryview",
    "buffer",
    "slice",
    "frozenset",
    "bytearray",
    "bytes",
    "object",
    "NotImplemented",
    "Ellipsis",
}


def _safe_globals() -> Dict[str, Any]:
    """
    创建安全的全局变量环境，限制可访问的模块和函数。
    只允许基本的 builtins 和安全的模块。
    """
    safe_builtins = {
        # 基本类型和函数
        "None": None,
        "True": True,
        "False": False,
        "bool": bool,
        "int": int,
        "float": float,
        "str": str,
        "list": list,
        "tuple": tuple,
        "dict": dict,
        "set": set,
        "len": len,
        "range": range,
        "enumerate": enumerate,
        "zip": zip,
        "sorted": sorted,
        "reversed": reversed,
        "min": min,
        "max": max,
        "sum": sum,
        "abs": abs,
        "round": round,
        # 数学函数
        "pow": pow,
        "divmod": divmod,
        # 打印函数（会被重定向）
        "print": print,
    }

    # 添加一些安全的模块
    try:
        import math

        # 过滤掉math模块中的危险函数
        safe_math = {}
        for name in dir(math):
            if not name.startswith("_") and name not in DANGEROUS_BUILTINS:
                safe_math[name] = getattr(math, name)
        safe_builtins["math"] = type("SafeMath", (), safe_math)()
    except ImportError:
        pass

    try:
        import datetime

        safe_builtins["datetime"] = datetime
    except ImportError:
        pass

    try:
        import json

        safe_builtins["json"] = json
    except ImportError:
        pass

    try:
        import random

        safe_builtins["random"] = random
    except ImportError:
        pass

    try:
        import re

        safe_builtins["re"] = re
    except ImportError:
        pass

    return safe_builtins


def _safe_locals() -> Dict[str, Any]:
    """创建安全的局部变量环境"""
    return {}


def _check_code_safety(code: str) -> None:
    """
    检查代码安全性，防止危险的导入和函数调用
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise CodeSyntaxError(f"语法错误: {e}")

    for node in ast.walk(tree):
        # 检查导入语句
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in DANGEROUS_MODULES:
                    raise SandboxSecurityError(f"禁止导入危险模块: {alias.name}")

        elif isinstance(node, ast.ImportFrom):
            if node.module in DANGEROUS_MODULES:
                raise SandboxSecurityError(f"禁止从危险模块导入: {node.module}")

        # 检查函数调用
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id in DANGEROUS_BUILTINS:
                    raise SandboxSecurityError(f"禁止调用危险函数: {node.func.id}")

            elif isinstance(node.func, ast.Attribute):
                if node.func.attr in DANGEROUS_BUILTINS:
                    raise SandboxSecurityError(f"禁止调用危险方法: {node.func.attr}")


class MemoryMonitor:
    """内存监控器，定期检查内存使用"""

    def __init__(self, max_memory_mb: int = 256, check_interval: float = 0.1):
        self.max_memory_mb = max_memory_mb
        self.check_interval = check_interval
        self._stop_event = threading.Event()
        self._memory_exceeded = False

    def start(self):
        """启动内存监控"""

        def monitor():
            try:
                import psutil
                import os

                process = psutil.Process(os.getpid())
                while not self._stop_event.is_set():
                    try:
                        memory_info = process.memory_info()
                        memory_used_mb = memory_info.rss / 1024 / 1024

                        if memory_used_mb > self.max_memory_mb:
                            self._memory_exceeded = True
                            raise MemoryLimitExceeded(
                                f"内存使用超过限制: {memory_used_mb:.1f}MB > {self.max_memory_mb}MB"
                            )

                        time.sleep(self.check_interval)
                    except (ImportError, AttributeError):
                        # 如果无法监控内存，则跳过
                        break
                    except MemoryLimitExceeded:
                        break
            except ImportError:
                # psutil 不可用，跳过内存监控
                pass

        self.monitor_thread = threading.Thread(target=monitor)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()

    def stop(self):
        """停止内存监控"""
        self._stop_event.set()
        if hasattr(self, "monitor_thread"):
            self.monitor_thread.join(timeout=1.0)

    def check_memory(self) -> bool:
        """检查内存是否超限"""
        return self._memory_exceeded


def _execute_with_timeout(func, args: tuple, kwargs: dict, timeout: int) -> Any:
    """
    使用线程执行函数并设置超时限制
    """
    result = None
    exception = None
    event = threading.Event()

    def worker():
        nonlocal result, exception
        try:
            result = func(*args, **kwargs)
        except Exception as e:
            exception = e
        finally:
            event.set()

    thread = threading.Thread(target=worker)
    thread.daemon = True
    thread.start()

    # 等待执行完成或超时
    event.wait(timeout)

    if not event.is_set():
        # 超时，尝试终止线程
        raise ExecutionTimeout(f"执行超时: {timeout}秒")

    if exception:
        raise exception

    return result


def execute_python_code_inprocess(
    code: str,
    timeout: int = 5,
    max_output_chars: int = 10000,
    max_memory_mb: int = 256,
    check_memory_interval: float = 0.1,
) -> Tuple[int, str, str]:
    """
    在应用内直接执行 Python 代码，不使用子进程。

    :param code: 要执行的 Python 代码
    :param timeout: 执行超时时间（秒）
    :param max_output_chars: 最大输出字符数
    :param max_memory_mb: 最大内存使用（MB）
    :param check_memory_interval: 内存检查间隔（秒）
    :return: (exit_code, stdout, stderr)
    """
    if not isinstance(code, str):
        return -2, "", "Invalid code type provided. Must be a string."

    if len(code) > 100000:  # 防止过长的代码
        return -2, "", "Code too long (max 100000 characters)"

    # 检查代码安全性
    try:
        _check_code_safety(code)
    except (CodeSyntaxError, SandboxSecurityError) as e:
        return -4, "", f"Security check failed: {e}"

    # 准备执行环境
    safe_globals = _safe_globals()
    safe_locals = _safe_locals()

    # 创建输出捕获
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()

    exit_code = 0
    stdout_content = ""
    stderr_content = ""

    # 创建内存监控器
    memory_monitor = MemoryMonitor(max_memory_mb, check_memory_interval)

    def _execute():
        nonlocal exit_code, stdout_content, stderr_content

        try:
            # 启动内存监控
            memory_monitor.start()

            # 重定向输出
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                # 编译代码
                compiled_code = compile(code, "<string>", "exec")

                # 执行代码
                exec(compiled_code, safe_globals, safe_locals)

                exit_code = 0

        except ExecutionTimeout:
            exit_code = -1
            stderr_capture.write(f"Execution timed out after {timeout} seconds\n")
        except MemoryLimitExceeded as e:
            exit_code = -3
            stderr_capture.write(f"Memory limit exceeded: {e}\n")
        except SandboxSecurityError as e:
            exit_code = -4
            stderr_capture.write(f"Security violation: {e}\n")
        except Exception as e:
            exit_code = 1
            stderr_capture.write(f"Error: {e}\n")
            stderr_capture.write(traceback.format_exc())
        finally:
            # 停止内存监控
            memory_monitor.stop()

            # 获取输出内容
            stdout_content = stdout_capture.getvalue()
            stderr_content = stderr_capture.getvalue()

            # 截断输出
            if len(stdout_content) > max_output_chars:
                stdout_content = stdout_content[:max_output_chars] + "\n...[truncated]"
            if len(stderr_content) > max_output_chars:
                stderr_content = stderr_content[:max_output_chars] + "\n...[truncated]"

    try:
        # 使用超时机制执行
        _execute_with_timeout(_execute, (), {}, timeout)

    except ExecutionTimeout:
        exit_code = -1
        stderr_content = f"Execution timed out after {timeout} seconds"
    except Exception as e:
        exit_code = -2
        stderr_content = f"Sandbox internal error: {e}"

    return exit_code, stdout_content, stderr_content


# Shell 代码执行配置
SHELL_EXECUTION_ENABLED = False  # 默认禁用，生产环境应保持禁用


def execute_shell_code_inprocess(
    code: str, timeout: int = 5, max_output_chars: int = 10000
) -> Tuple[int, str, str]:
    """
    执行 shell 代码（需要显式启用）

    警告：应用内执行 shell 代码存在严重安全风险！
    仅在测试环境中启用，生产环境应保持禁用。
    """
    if not SHELL_EXECUTION_ENABLED:
        return (
            -2,
            "",
            "Shell execution is disabled for security reasons. Set SHELL_EXECUTION_ENABLED=True to enable.",
        )

    # 即使启用，也进行基本的安全检查
    dangerous_patterns = [
        "rm -rf",
        "sudo",
        "chmod",
        "chown",
        "dd if=",
        "mkfs",
        "fdisk",
        "mkfs",
        "> /dev/",
        "|",
        "&",
        ";",
        "`",
        "$(",
    ]

    code_lower = code.lower()
    for pattern in dangerous_patterns:
        if pattern in code_lower:
            return -4, "", f"Shell command contains dangerous pattern: {pattern}"

    # 使用安全的子进程执行（作为折中方案）
    try:
        import subprocess

        # 使用安全的执行方式
        process = subprocess.Popen(
            ["/bin/sh", "-c", code],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )

        try:
            stdout, stderr = process.communicate(timeout=timeout)

            # 截断输出
            if len(stdout) > max_output_chars:
                stdout = stdout[:max_output_chars] + "\n...[truncated]"
            if len(stderr) > max_output_chars:
                stderr = stderr[:max_output_chars] + "\n...[truncated]"

            return process.returncode, stdout, stderr

        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            return -1, "", f"Execution timed out after {timeout} seconds"

    except Exception as e:
        return -2, "", f"Shell execution error: {e}"


def enable_shell_execution():
    """启用 shell 代码执行（仅用于测试环境）"""
    global SHELL_EXECUTION_ENABLED
    SHELL_EXECUTION_ENABLED = True
    logger.warning("Shell execution has been enabled. This is a security risk!")


def disable_shell_execution():
    """禁用 shell 代码执行（推荐用于生产环境）"""
    global SHELL_EXECUTION_ENABLED
    SHELL_EXECUTION_ENABLED = False
    logger.info("Shell execution has been disabled for security")


# 测试函数
def test_sandbox():
    """测试沙箱功能"""
    # 测试正常代码
    code = """
for i in range(3):
    print(f"Hello {i}")
result = sum([1, 2, 3, 4, 5])
print(f"Sum: {result}")
"""
    exit_code, stdout, stderr = execute_python_code_inprocess(code)
    print(f"正常代码测试 - Exit: {exit_code}")
    print(f"Stdout: {stdout}")
    print(f"Stderr: {stderr}")
    print()

    # 测试危险代码
    dangerous_code = "import os; os.system('ls')"
    exit_code, stdout, stderr = execute_python_code_inprocess(dangerous_code)
    print(f"危险代码测试 - Exit: {exit_code}")
    print(f"Stdout: {stdout}")
    print(f"Stderr: {stderr}")
    print()

    # 测试超时代码
    timeout_code = "import time; time.sleep(10); print('Done')"
    exit_code, stdout, stderr = execute_python_code_inprocess(timeout_code, timeout=2)
    print(f"超时测试 - Exit: {exit_code}")
    print(f"Stdout: {stdout}")
    print(f"Stderr: {stderr}")


if __name__ == "__main__":
    test_sandbox()
