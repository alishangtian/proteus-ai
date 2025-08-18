"""
sandbox.py
提供安全性更高的代码执行封装 — 将 Python 和 Shell 代码在子进程中执行，
并使用进程资源限制、超时与输出截断来降低滥用风险。

注意：
- 仍然存在安全风险：允许任意 shell 或 python 代码执行本质上就是危险的。
  应把该服务仅在受信网络/环境中使用，或进一步使用容器/namespace等隔离措施。
- 该文件使用 Unix-specific 的 resource 限制（适用于 macOS / Linux）。
"""

from typing import Tuple
import subprocess
import tempfile
import sys
import os
import shlex
import logging

# 尝试导入 resource 模块以设置进程限制（仅在 Unix-like 系统可用）
try:
    import resource
except Exception:
    resource = None  # 在不支持的系统上将不会设置 RLIMIT

logger = logging.getLogger(__name__)


def _set_limits(max_cpu_seconds: int = 2, max_memory_bytes: int = 256 * 1024 * 1024):
    """
    返回一个在子进程 preexec_fn 中调用的函数，用来设置进程的资源限制。
    仅在 Unix-like 系统可用（依赖 resource 模块）。
    """

    def _inner():
        if resource is None:
            return
        try:
            # 限制 CPU 时间（秒）
            resource.setrlimit(resource.RLIMIT_CPU, (max_cpu_seconds, max_cpu_seconds))
        except Exception:
            pass
        try:
            # 限制地址空间（近似内存上限）
            resource.setrlimit(resource.RLIMIT_AS, (max_memory_bytes, max_memory_bytes))
        except Exception:
            pass
        try:
            # 限制可创建文件大小（防止生成超大文件）
            resource.setrlimit(
                resource.RLIMIT_FSIZE, (10 * 1024 * 1024, 10 * 1024 * 1024)
            )
        except Exception:
            pass

    return _inner


def _truncate_output(s: str, max_chars: int) -> str:
    if s is None:
        return ""
    if len(s) <= max_chars:
        return s
    return s[:max_chars] + "\n...[truncated]"


def execute_python_code(
    code: str, timeout: int = 5, max_output: int = 10000
) -> Tuple[str, str]:
    """
    在子进程中执行 Python 代码，返回 (stdout, stderr)。
    - 使用临时文件保存代码并通过当前运行的 Python 解释器执行。
    - 使用 resource 限制 CPU 和内存（仅 Unix）。
    - 使用 timeout 控制最大执行时间。
    - 截断超长输出以避免 OOM / 日志膨胀。
    """
    if not isinstance(code, str):
        return "", "invalid code type"

    tmp = None
    try:
        tmp = tempfile.NamedTemporaryFile(
            suffix=".py", delete=False, mode="w", encoding="utf-8"
        )
        tmp.write(code)
        tmp.flush()
        tmp.close()

        cmd = [sys.executable or "python3", tmp.name]

        # 最小化环境变量，避免子进程凭借主进程敏感环境运行
        allowed_env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "LANG": os.environ.get("LANG", "en_US.UTF-8"),
        }

        completed = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            env=allowed_env,
            preexec_fn=_set_limits(
                max_cpu_seconds=timeout + 1, max_memory_bytes=256 * 1024 * 1024
            ),
        )
        stdout = _truncate_output(completed.stdout, max_output)
        stderr = _truncate_output(completed.stderr, max_output)
        return stdout, stderr
    except subprocess.TimeoutExpired:
        logger.warning("Python code execution timed out after %s seconds", timeout)
        return "", f"Execution timed out after {timeout} seconds"
    except Exception as e:
        logger.exception("Exception while running python code")
        return "", str(e)
    finally:
        if tmp is not None:
            try:
                os.unlink(tmp.name)
            except Exception:
                pass


def execute_shell_code(
    code: str, timeout: int = 5, max_output: int = 10000
) -> Tuple[str, str]:
    """
    在子进程中执行 shell 命令并返回 (stdout, stderr)。
    - 使用 /bin/sh -c 来运行命令（保留 shell 特性）。
    - 设置超时、输出截断与进程资源限制以减少风险。
    - 使用尽量精简的环境变量。
    """
    if not isinstance(code, str):
        return "", "invalid code type"

    # 简单防护：拒绝一些明显危险的关键词（仅作第一层防护，不可靠）
    forbidden_tokens = ["&", ";;", "|", "rm -rf", "mkfs", "dd ", ">:"]  # 例子
    for t in forbidden_tokens:
        if t in code:
            return "", f"Forbidden token detected in shell code: {t}"

    cmd = ["/bin/sh", "-c", code]

    allowed_env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "LANG": os.environ.get("LANG", "en_US.UTF-8"),
    }

    try:
        completed = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            env=allowed_env,
            preexec_fn=_set_limits(
                max_cpu_seconds=timeout + 1, max_memory_bytes=128 * 1024 * 1024
            ),
            shell=False,
        )
        stdout = _truncate_output(completed.stdout, max_output)
        stderr = _truncate_output(completed.stderr, max_output)
        return stdout, stderr
    except subprocess.TimeoutExpired:
        logger.warning("Shell command timed out after %s seconds", timeout)
        return "", f"Execution timed out after {timeout} seconds"
    except Exception as e:
        logger.exception("Exception while running shell code")
        return "", str(e)
