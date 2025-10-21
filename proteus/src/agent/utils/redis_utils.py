import time
import threading
import json
import logging
from functools import wraps
from contextlib import contextmanager
from ..utils.redis_cache import RedisCache, get_redis_connection

logger = logging.getLogger(__name__)


class RetryableRedisError(Exception):
    """可重试的Redis错误"""

    pass


class NonRetryableRedisError(Exception):
    """不可重试的Redis错误"""

    pass


def enhanced_retry_mechanism(
    max_retries: int = 3, base_delay: float = 0.1, max_delay: float = 2.0
):
    """增强的重试装饰器，支持指数退避和错误分类"""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    # 错误分类：某些错误不应该重试
                    if isinstance(e, (ValueError, TypeError, json.JSONDecodeError)):
                        logger.error(f"不可重试的错误: {e}")
                        raise NonRetryableRedisError(f"不可重试的错误: {e}") from e

                    if attempt < max_retries:
                        # 指数退避策略
                        delay = min(base_delay * (2**attempt), max_delay)
                        logger.warning(
                            f"操作失败，{delay:.2f}秒后重试 (尝试 {attempt + 1}/{max_retries}): {e}"
                        )
                        time.sleep(delay)
                    else:
                        logger.error(f"所有重试都失败: {e}")
                        raise RetryableRedisError(
                            f"重试{max_retries}次后仍然失败: {e}"
                        ) from e

            raise last_exception

        return wrapper

    return decorator


class RedisConnectionManager:
    """Redis连接池管理器，提供连接复用和批量操作优化"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            self._redis_cache = None
            self._connection_pool = None
            self._initialized = True

    @contextmanager
    def get_redis_connection(self):
        """获取Redis连接的上下文管理器，增强异常处理"""
        connection_attempts = 0
        max_connection_attempts = 3

        while connection_attempts < max_connection_attempts:
            try:
                if self._redis_cache is None:
                    self._redis_cache = get_redis_connection()
                yield self._redis_cache
                break
            except Exception as e:
                connection_attempts += 1
                logger.error(
                    f"Redis连接错误 (尝试 {connection_attempts}/{max_connection_attempts}): {e}"
                )

                if connection_attempts < max_connection_attempts:
                    # 重新创建连接
                    self._redis_cache = None
                    time.sleep(0.1 * connection_attempts)  # 递增延迟
                else:
                    raise RetryableRedisError(
                        f"Redis连接失败，已尝试{max_connection_attempts}次"
                    ) from e

    def batch_operations(self, operations: list[dict[str, any]]) -> list[any]:
        """批量执行Redis操作

        Args:
            operations: 操作列表，每个操作包含 {'method': str, 'args': tuple, 'kwargs': dict}

        Returns:
            List[Any]: 操作结果列表
        """
        results = []
        with self.get_redis_connection() as redis_conn:
            # 使用pipeline进行批量操作
            pipe = redis_conn.pipeline()
            try:
                for op in operations:
                    method_name = op.get("method")
                    args = op.get("args", ())
                    kwargs = op.get("kwargs", {})

                    if hasattr(pipe, method_name):
                        method = getattr(pipe, method_name)
                        method(*args, **kwargs)
                    else:
                        logger.warning(f"Redis pipeline不支持方法: {method_name}")

                results = pipe.execute()
            except Exception as e:
                logger.error(f"批量Redis操作失败: {e}")
                # 回退到单个操作
                for op in operations:
                    try:
                        method_name = op.get("method")
                        args = op.get("args", ())
                        kwargs = op.get("kwargs", {})

                        if hasattr(redis_conn, method_name):
                            method = getattr(redis_conn, method_name)
                            result = method(*args, **kwargs)
                            results.append(result)
                    except Exception as single_error:
                        logger.error(f"单个Redis操作失败: {single_error}")
                        results.append(None)

        return results