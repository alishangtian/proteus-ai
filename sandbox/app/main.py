import asyncio
import logging
import os
import secrets
import time
from functools import lru_cache

from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

from sandbox import execute_python_code, execute_shell_code


class Settings(BaseSettings):
    """统一管理应用配置，从环境变量加载"""

    API_KEY: str
    LOG_DIR: str = Field("/var/logs/sandbox", description="日志文件存放目录")
    LOG_LEVEL: str = Field("INFO", description="日志级别")
    MAX_CODE_LENGTH: int = Field(20000, description="最大允许代码长度")
    MAX_OUTPUT_LENGTH: int = Field(10000, description="最大允许输出长度")
    PYTHON_EXEC_TIMEOUT: int = Field(30, description="Python代码执行超时时间（秒）")
    SHELL_EXEC_TIMEOUT: int = Field(30, description="Shell脚本执行超时时间（秒）")
    MAX_SAFE_TIMEOUT: int = Field(60, description="最大安全超时时间（秒）")
    DATA_DIR: str = Field("/var/data/sandbox", description="数据文件存放目录")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """获取并缓存配置实例"""
    return Settings()


def setup_logging(settings: Settings):
    """初始化日志系统"""
    log_dir = settings.LOG_DIR
    try:
        os.makedirs(log_dir, exist_ok=True)
    except Exception:
        log_dir = "/tmp"  # 回退到临时目录
        os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, "sandbox.log")
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    formatter = logging.Formatter(log_format)

    # 配置根 logger
    root_logger = logging.getLogger()
    # 清除已有 handlers，防止重复添加
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    root_logger.setLevel(settings.LOG_LEVEL.upper())

    # 添加控制台 handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # 尝试添加文件 handler
    try:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except Exception as e:
        logging.getLogger(__name__).warning(
            "无法创建日志文件处理器: %s", e, exc_info=True
        )

    logging.getLogger(__name__).info("日志系统已初始化，日志文件位于: %s", log_file)


# 初始化应用和配置
settings = get_settings()
setup_logging(settings)
app = FastAPI(title="Code Execution Sandbox API")

# 中间件配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


async def verify_api_key(authorization: str = Header(...)):
    """依赖项：验证 Bearer Token API Key"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401, detail="无效的授权格式，请使用Bearer Token"
        )
    token = authorization.split(" ")[1]
    # 使用 secrets.compare_digest 防止时序攻击
    if not secrets.compare_digest(token, settings.API_KEY):
        raise HTTPException(status_code=401, detail="无效的API Token")


class CodeRequest(BaseModel):
    code: str = Field(
        ..., max_length=settings.MAX_CODE_LENGTH, description="要执行的代码"
    )
    language: str = Field("python", description="代码语言 ('python' 或 'shell')")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "code": "print('Hello, World!')",
                    "language": "python",
                },
                {
                    "code": "echo 'Hello from shell!'",
                    "language": "shell",
                },
            ]
        }
    }


class CodeResponse(BaseModel):
    code: int = Field(..., description="执行退出码")
    stdout: str = Field(..., description="标准输出")
    stderr: str = Field(..., description="标准错误")


logger = logging.getLogger(__name__)


@app.post(
    "/v1/sandbox/run",
    response_model=CodeResponse,
    dependencies=[Depends(verify_api_key)],
    summary="执行代码沙箱",
)
async def execute_code_endpoint(request: CodeRequest):
    """
    在隔离的沙箱环境中安全地执行 Python 或 Shell 代码。
    - **-2**: 输入校验失败或沙箱内部错误
    - **-1**: 执行超时
    - **0**: 执行成功
    - **>0**: 代码本身的运行时错误
    """
    request_id = os.urandom(8).hex()
    logger.info(
        "[%s] 接收到代码执行请求: language=%s, code_length=%d, timeout_limit=%ds",
        request_id,
        request.language,
        len(request.code),
        min(
            (
                settings.PYTHON_EXEC_TIMEOUT
                if request.language == "python"
                else settings.SHELL_EXEC_TIMEOUT
            ),
            settings.MAX_SAFE_TIMEOUT,
        ),
    )

    # 记录代码前100个字符用于调试（不记录敏感信息）
    code_preview = request.code[:100].replace("\n", "\\n")
    if len(request.code) > 100:
        code_preview += "..."
    logger.info("[%s] 代码预览: %s", request_id, code_preview)

    if request.language not in ("python", "shell"):
        logger.error("[%s] 不支持的语言: %s", request_id, request.language)
        return CodeResponse(
            code=-2,
            stdout="",
            stderr=f"不支持的语言: {request.language}. 只支持 'python' 和 'shell'。",
        )

    try:
        start_time = time.time()

        # 使用线程池执行器来运行阻塞的代码执行操作
        if request.language == "shell":
            # Shell 命令继续在线程池中执行以避免阻塞
            exit_code, stdout, stderr = await asyncio.get_event_loop().run_in_executor(
                None,
                execute_shell_code,
                request.code,
                min(settings.SHELL_EXEC_TIMEOUT, settings.MAX_SAFE_TIMEOUT),
                settings.MAX_OUTPUT_LENGTH,
            )
        else:
            # Python 代码现在直接在主线程中同步执行
            exit_code, stdout, stderr = execute_python_code(
                request.code,
                min(settings.PYTHON_EXEC_TIMEOUT, settings.MAX_SAFE_TIMEOUT),
                settings.MAX_OUTPUT_LENGTH,
            )

        execution_time = time.time() - start_time

        logger.info(
            "[%s] 执行完成: language=%s, exit_code=%d, execution_time=%.3fs, stdout_len=%d, stderr_len=%d",
            request_id,
            request.language,
            exit_code,
            execution_time,
            len(stdout),
            len(stderr),
        )

        if stdout:
            logger.info(
                "[%s] 执行完成:  stdout_len=%d, stdout=\n%s",
                request_id,
                len(stdout),
                stdout,
            )
        if stderr:
            logger.info(
                "[%s] 执行完成:  stderr_len=%d, stderr=\n%s",
                request_id,
                len(stderr),
                stderr,
            )

        # 记录详细的执行信息
        if execution_time > 1.0:
            logger.info("[%s] 执行时间较长: %.3f秒", request_id, execution_time)

        if stderr and len(stderr) > 500:
            logger.info("[%s] 截断的 stderr: %s", request_id, stderr[:500])

        # 记录性能指标
        logger.info(
            "[%s] 性能指标 - 执行时间: %.3fs, 输出大小: %d/%d bytes",
            request_id,
            execution_time,
            len(stdout),
            len(stderr),
        )

        return CodeResponse(code=exit_code, stdout=stdout, stderr=stderr)

    except asyncio.TimeoutError:
        error_msg = f"执行超时，超过最大安全时间限制: {settings.MAX_SAFE_TIMEOUT}秒"
        logger.warning("[%s] %s", request_id, error_msg)
        return CodeResponse(code=-1, stdout="", stderr=error_msg)
    except Exception as e:
        error_msg = f"执行环境中发生意外错误: {e}"
        logger.exception("[%s] %s", request_id, error_msg)
        return CodeResponse(code=-2, stdout="", stderr=error_msg)


@app.get("/health", summary="健康检查")
async def health_check():
    """健康检查端点"""
    return {"status": "healthy", "timestamp": time.time()}


@app.get("/", summary="根路径")
async def root():
    """根路径返回API信息"""
    return {
        "message": "Code Execution Sandbox API",
        "version": "1.0.0",
        "docs": "/docs"
    }


if __name__ == "__main__":
    import uvicorn

    # 注意：在生产环境中应使用 Gunicorn 等 ASGI 服务器
    uvicorn.run(app, host="0.0.0.0", port=8000)
