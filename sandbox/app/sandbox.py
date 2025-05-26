import subprocess
import tempfile
import os
from typing import Tuple

def execute_python_code(code: str) -> Tuple[str, str]:
    """
    执行Python代码并返回结果
    
    Args:
        code: 要执行的Python代码
        
    Returns:
        tuple: (stdout, stderr)
    """
    with tempfile.NamedTemporaryFile(suffix='.py', delete=False) as tmp:
        tmp.write(code.encode('utf-8'))
        tmp_path = tmp.name
    
    try:
        result = subprocess.run(
            ['python', tmp_path],
            capture_output=True,
            text=True,
            timeout=10  # 10秒超时
        )
        return result.stdout, result.stderr
    finally:
        os.unlink(tmp_path)  # 清理临时文件