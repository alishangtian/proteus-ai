from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sandbox import execute_python_code, execute_shell_code
from dotenv import load_dotenv
import os,logging

app = FastAPI()

# 加载环境变量
load_dotenv(".env")  # 从上级目录加载.env文件
# 配置日志输出到标准输出和文件
LOG_DIR = os.getenv("LOG_DIR", "/var/log/sandbox")  # 默认日志目录
os.makedirs(LOG_DIR, exist_ok=True)  # 确保目录存在

log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
formatter = logging.Formatter(log_format)

# 创建控制台处理器
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

# 创建文件处理器
log_file = os.path.join(LOG_DIR, "sandbox.log")
file_handler = logging.FileHandler(log_file)
file_handler.setFormatter(formatter)

# 配置根日志记录器
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(console_handler)
root_logger.addHandler(file_handler)

logger = logging.getLogger(__name__)
logger.info("日志系统已初始化，日志文件位于: %s", log_file)

# 获取API Key
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise ValueError("请在.env文件中配置API_KEY")


async def verify_api_key(authorization: str = Header(...)):
    """验证Bearer Token"""
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

    Args:
        request: 包含代码和语言类型的请求体
            code: 要执行的代码
            language: 代码类型(python/shell)

    Returns:
        dict: 包含执行结果的响应
    """
    try:
        if request.language not in ("python", "shell"):
            return {
                "code": 1,
                "stdout": "",
                "stderr": f"Unsupported language: {request.language}. Only 'python' and 'shell' are supported."
            }
            
        if request.language == "shell":
            stdout, stderr = execute_shell_code(request.code)
        else:  # 处理python代码
            stdout, stderr = execute_python_code(request.code)
        logger.info(f"执行结果: {stdout} \n {stderr}")
        return {"code": 0, "stdout": stdout, "stderr": stderr}
    except Exception as e:
        logger.info(f"执行异常: {stdout} \n {stderr} \n {e}")
        return {"code": 1, "stdout": str(e), "stderr": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)