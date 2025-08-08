import io
import os
import contextlib
from typing import Tuple

def execute_python_code(code: str) -> Tuple[str, str]:
    """
    执行Python代码并返回结果
    
    Args:
        code: 要执行的Python代码
        
    Returns:
        tuple: (stdout, stderr)
    """
    stdout = io.StringIO()
    stderr = io.StringIO()
    
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exec(code)
        return stdout.getvalue(), stderr.getvalue()
    except Exception as e:
        return "", str(e)

def execute_shell_code(code: str) -> Tuple[str, str]:
    """
    执行Shell代码并返回结果
    
    Args:
        code: 要执行的Shell命令
        
    Returns:
        tuple: (stdout, stderr)
    """
    try:
        # 使用os.popen更安全的方式执行shell命令
        with os.popen(code) as stream:
            output = stream.read()
        return output, ""
    except Exception as e:
        return "", str(e)