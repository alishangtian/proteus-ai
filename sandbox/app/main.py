from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sandbox import execute_python_code, execute_shell_code
from dotenv import load_dotenv
import os, logging

app = FastAPI()

# 加载环境变量
load_dotenv(".env")  # 从上级目录加载.env文件
# 配置日志输出到标准输出和文件
LOG_DIR = os.getenv("LOG_DIR", "./logs")  # 默认日志目录
try:
    os.makedirs(LOG_DIR, exist_ok=True)  # 确保目录存在
except Exception:
    # 如果无法在指定位置创建日志目录，回退到临时目录
    LOG_DIR = "/tmp"
    os.makedirs(LOG_DIR, exist_ok=True)

log_level = os.getenv("LOG_LEVEL", "INFO").upper()
log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
formatter = logging.Formatter(log_format)

# 创建控制台处理器
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

# 创建文件处理器（若无法创建则忽略）
log_file = os.path.join(LOG_DIR, "sandbox.log")
try:
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
except Exception:
    file_handler = None

# 配置根日志记录器，避免重复添加 handler
root_logger = logging.getLogger()
root_logger.setLevel(getattr(logging, log_level, logging.INFO))
if not root_logger.handlers:
    root_logger.addHandler(console_handler)
    if file_handler:
        root_logger.addHandler(file_handler)

logger = logging.getLogger(__name__)
logger.info("日志系统已初始化，日志文件位于: %s", log_file)

# 获取API Key
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise ValueError("请在.env文件中配置API_KEY")


async def verify_api_key(authorization: str = Header(None)):
    """验证Bearer Token"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401, detail="无效的授权格式，请使用Bearer Token"
        )
    token = authorization[7:]  # 去掉"Bearer "前缀
    if token != API_KEY:
        raise HTTPException(status_code=401, detail="无效的API Token")


# 允许跨域请求
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class CodeRequest(BaseModel):
    code: str
    language: str = "python"  # 默认为python代码


@app.post("/v1/sandbox/run")
async def execute_code(
    request: CodeRequest, authorization: str = Depends(verify_api_key)
):
    """
    执行代码并返回结果
    """
    # 基本校验
    max_code_len = int(os.getenv("MAX_CODE_LENGTH", "20000"))
    if not request.code or len(request.code) > max_code_len:
        return {
            "code": 1,
            "stdout": "",
            "stderr": "Code is empty or exceeds maximum allowed length.",
        }

    if request.language not in ("python", "shell"):
        return {
            "code": 1,
            "stdout": "",
            "stderr": f"Unsupported language: {request.language}. Only 'python' and 'shell' are supported.",
        }

    # 从环境读取超时和输出限制
    py_timeout = int(os.getenv("PY_TIMEOUT", "5"))
    sh_timeout = int(os.getenv("SH_TIMEOUT", "5"))
    max_output = int(os.getenv("MAX_OUTPUT", "10000"))

    try:
        if request.language == "shell":
            stdout, stderr = execute_shell_code(
                request.code, timeout=sh_timeout, max_output=max_output
            )
        else:
            stdout, stderr = execute_python_code(
                request.code, timeout=py_timeout, max_output=max_output
            )

        logger.info(
            "执行结果 stdout length=%d stderr length=%d",
            len(stdout or ""),
            len(stderr or ""),
        )
        return {"code": 0, "stdout": stdout, "stderr": stderr}
    except Exception as e:
        logger.exception("执行异常")
        return {"code": 1, "stdout": "", "stderr": str(e)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
