"""
sandbox.py
提供代码执行封装。
- Python 代码在当前进程中通过受限环境执行。
- Shell 代码为保持兼容性，仍在子进程中执行。

注意：
- 直接执行代码本质上存在风险。尽管我们使用 restrictedpy 来限制 Python 环境，
  但仍强烈建议在容器（如 Docker）或虚拟机等强隔离环境中使用此沙箱服务。
- Shell 命令执行依旧危险，请谨慎使用。
"""

import logging
import subprocess
import tempfile
import os
from typing import Tuple, List

logger = logging.getLogger(__name__)


def _truncate_output(s: str, max_chars: int) -> str:
    """截断字符串，如果它超过了最大长度。"""
    if s is None:
        return ""
    if len(s) > max_chars:
        return s[:max_chars] + "\n...[truncated]"
    return s


def execute_python_code(
    code: str, timeout: int = 5, max_output: int = 10000
) -> Tuple[int, str, str]:
    """
    在独立子进程中执行 Python 代码以提高隔离性（不使用 RestrictedPython）。
    - 将代码写入临时文件，然后使用系统的 python3 以 -u 模式运行（不缓存输出）。
    - 通过子进程的超时和输出截断来控制执行。
    :return: (exit_code, stdout, stderr)
             exit_code: 0 成功, -1 超时, -2 沙箱内部错误, 其他为子进程返回码
    """
    if not isinstance(code, str):
        return -2, "", "无效的代码类型，必须是字符串。"

    tmp_path = None
    try:
        # 将代码写入临时文件（避免在主进程中 exec）
        with tempfile.NamedTemporaryFile(
            "w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(code)
            tmp_path = f.name

        # 使用系统 Python 运行临时文件，-u 保证 stdout/stderr 不被缓冲
        cmd = ["/usr/bin/env", "python3", "-u", tmp_path]
        return_code, stdout, stderr = _run_subprocess(
            cmd=cmd,
            timeout=timeout,
            max_output=max_output,
        )

        return return_code, stdout, stderr

    except subprocess.TimeoutExpired:
        logger.warning("Python 代码执行超时 %d 秒", timeout)
        return -1, "", f"执行超时 {timeout} 秒"
    except Exception as e:
        logger.exception("在沙箱中执行 Python 代码时发生异常")
        stderr = _truncate_output(f"沙箱内部错误: {e}", max_output)
        return -2, "", stderr
    finally:
        # 尽力删除临时文件
        try:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass


def _run_subprocess(
    cmd: List[str],
    timeout: int,
    max_output: int,
) -> Tuple[int, str, str]:
    """
    一个统一的子进程执行函数，包含超时、资源限制和输出截断。
    注意：资源限制 (resource) 在此版本中为简化已移除。
    :return: (exit_code, stdout, stderr)
    """
    process = None
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            text=True,
            encoding="utf-8",
            errors="backslashreplace",
        )
        stdout, stderr = process.communicate(timeout=timeout)
        stdout = _truncate_output(stdout, max_output)
        stderr = _truncate_output(stderr, max_output)
        return process.returncode, stdout, stderr

    except subprocess.TimeoutExpired:
        logger.warning("执行超时 %d 秒: %s", timeout, cmd)
        if process:
            process.kill()
            out, err = process.communicate()
            stdout = _truncate_output(out, max_output)
            stderr = _truncate_output(err, max_output)
            stderr += f"\n执行超时 {timeout} 秒"
            return -1, stdout, stderr
        return -1, "", f"执行超时 {timeout} 秒"

    except Exception as e:
        logger.exception("运行子进程时发生异常: %s", cmd)
        return -2, "", f"沙箱内部错误: {e}"


def execute_shell_code(
    code: str, timeout: int = 5, max_output: int = 10000
) -> Tuple[int, str, str]:
    """
    在子进程中执行 shell 命令。
    - 使用 `/bin/sh -c` 来运行命令。
    - **警告**: 依然存在安全风险，依赖于外部的强隔离环境。

    :return: (exit_code, stdout, stderr)
    """
    if not isinstance(code, str):
        return -2, "", "无效的代码类型，必须是字符串。"

    cmd = ["/bin/sh", "-c", code]
    return _run_subprocess(
        cmd=cmd,
        timeout=timeout,
        max_output=max_output,
    )
