"""API配置模块

提供配置管理和工具函数
"""

import os
import time
import asyncio
from functools import wraps
from typing import Any, Callable, Dict, TypeVar, Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class APIConfig(BaseModel):
    """API配置模型"""

    api_key: str = Field(default=os.getenv("API_KEY", ""), description="LLM API密钥")
    model_name: str = Field(
        default=os.getenv("MODEL_NAME", "deepseek-chat"),
        description="默认使用的模型名称",
    )
    long_context_model: str = Field(
        default=os.getenv("LONG_CONTEXT_MODEL", "deepseek-chat-128k"),
        description="长上下文模型名称",
    )
    context_length_threshold: int = Field(
        default=int(os.getenv("CONTEXT_LENGTH_THRESHOLD", "32000")),
        description="切换到长上下文模型的阈值(字符数)",
    )
    base_url: str = Field(
        default=os.getenv("BASE_URL", "https://api.deepseek.com/v1"),
        description="API基础URL",
    )
    request_timeout: int = Field(
        default=int(os.getenv("REQUEST_TIMEOUT", "30")),
        description="API请求超时时间(秒)",
    )
    max_retries: int = Field(
        default=int(os.getenv("MAX_RETRIES", "3")), description="API请求最大重试次数"
    )
    stream_chunk_size: int = Field(
        default=int(os.getenv("STREAM_CHUNK_SIZE", "1024")),
        description="流式响应的块大小",
    )
    serper_api_key: str = Field(
        default=os.getenv("SERPER_API_KEY", ""), description="Serper API密钥"
    )
    file_write_path: str = Field(
        default=os.getenv("FILE_WRITE_PATH", "./data/file"),
        description="文件写入节点的默认写入路径",
    )
    caiyun_token: str = Field(
        default=os.getenv("CAIYUN_TOKEN", ""), description="彩云api token"
    )
    caiyun_api_version: str = Field(
        default=os.getenv("CAIYUN_API_VERSION", ""), description="彩云api version"
    )
    data_path: str = Field(default=os.getenv("DATA_PATH", ""), description="数据目录")
    llm_retry_count: int = Field(
        default=int(os.getenv("LLM_RETRY_COUNT", 10)), description="模型调用重试次数"
    )
    llm_retry_delay: int = Field(
        default=int(os.getenv("LLM_RETRY_DELAY", 10)), description="模型调用重试延迟"
    )
    tool_retry_count: int = Field(
        default=int(os.getenv("TOOL_RETRY_COUNT", 3)),
        description="工具执行调用重试次数",
    )
    tool_retry_delay: int = Field(
        default=int(os.getenv("TOOL_RETRY_DELAY", 3)), description="工具调用重试延迟"
    )
    iteration_retry_delay: int = Field(
        default=int(os.getenv("ITERATION_RETRY_DELAY", 10)),
        description="智能体迭代调用重试延迟",
    )


# 创建全局配置实例
API_CONFIG = APIConfig().model_dump()

# 类型变量
T = TypeVar("T")
R = TypeVar("R")


def retry_on_error(
    max_retries: Optional[int] = None,
    exceptions: tuple = (Exception,),
    logger: Any = None,
    sleep: Optional[float] = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """重试装饰器

    Args:
        max_retries: 最大重试次数，如果为None则使用配置中的值
        exceptions: 需要重试的异常类型
        logger: 日志记录器
        sleep: 重试前等待的时间(秒)，如果为None则立即重试

    Returns:
        装饰器函数

    Example:
        @retry_on_error(max_retries=3, sleep=1.0)
        async def my_function():
            # 可能失败的操作
            pass
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            retries = max_retries or API_CONFIG["max_retries"]
            last_error = None
            base_sleep = sleep or 1.0

            for attempt in range(retries):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_error = e

                    # 判断错误类型，决定是否值得重试
                    error_str = str(e).lower()
                    is_retryable = any(
                        keyword in error_str
                        for keyword in [
                            "server disconnected",
                            "connection",
                            "network",
                            "timeout",
                            "temporary failure",
                            "service unavailable",
                            "bad gateway",
                            "gateway timeout",
                            "too many requests",
                        ]
                    )

                    if logger:
                        if is_retryable:
                            logger.warning(
                                f"第{attempt + 1}次重试失败 (可重试错误): {str(e)}, "
                                f"剩余重试次数: {retries - attempt - 1}"
                            )
                        else:
                            logger.error(
                                f"第{attempt + 1}次重试失败 (不可重试错误): {str(e)}, "
                                f"剩余重试次数: {retries - attempt - 1}"
                            )

                    if attempt == retries - 1:
                        if logger:
                            logger.error(
                                f"达到最大重试次数({retries}), 最后错误: {str(e)}"
                            )
                        raise last_error

                    # 对于网络相关错误，使用指数退避策略
                    if is_retryable:
                        sleep_time = base_sleep * (2**attempt)  # 指数退避
                        sleep_time = min(sleep_time, 30)  # 最大等待30秒
                        if logger:
                            logger.info(f"等待 {sleep_time:.1f} 秒后重试...")
                        await asyncio.sleep(sleep_time)
                    else:
                        # 非网络错误，短暂等待后重试
                        await asyncio.sleep(base_sleep)

            return None  # 类型检查需要

        return wrapper

    return decorator


def validate_api_config() -> None:
    """验证API配置的必要字段

    Raises:
        ValueError: 当必要的配置项缺失时
    """
    if not API_CONFIG["api_key"]:
        raise ValueError("API密钥未配置! 请在.env文件中设置API_KEY环境变量")

    if not API_CONFIG["base_url"]:
        raise ValueError("API基础URL未配置! 请在.env文件中设置BASE_URL环境变量")


def get_headers() -> Dict[str, str]:
    """获取API请求头

    Returns:
        包含认证信息的请求头字典
    """
    return {
        "Authorization": f"Bearer {API_CONFIG['api_key']}",
        "Content-Type": "application/json",
    }
