"""Redis缓存实现"""
import redis
import os
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class RedisCache:
    def __init__(self):
        self._pool = None
        self._client = None
        self.max_retries = 3
        self.retry_delay = 1
        self._connect()

    def _connect(self):
        """建立Redis连接"""
        for attempt in range(self.max_retries):
            try:
                self._pool = redis.ConnectionPool(
                    host=os.getenv("REDIS_HOST"),
                    port=int(os.getenv("REDIS_PORT")),
                    db=int(os.getenv("REDIS_DB")),
                    password=os.getenv("REDIS_PASSWORD"),
                    decode_responses=True,
                    health_check_interval=30,
                    socket_keepalive=True,
                    max_connections=20,
                    socket_timeout=5,
                    socket_connect_timeout=5,
                    retry_on_timeout=True
                )
                self._client = redis.Redis(connection_pool=self._pool)
                self._client.ping()
                return
            except (redis.ConnectionError, redis.TimeoutError) as e:
                if attempt == self.max_retries - 1:
                    raise
                logger.warning(f"Redis连接失败，尝试重连({attempt + 1}/{self.max_retries}): {e}")
                time.sleep(self.retry_delay)

    def _get_client(self):
        """获取Redis客户端"""
        try:
            self._client.ping()
            return self._client
        except (redis.ConnectionError, redis.TimeoutError):
            logger.warning("Redis连接丢失，尝试重新连接...")
            self._connect()
            return self._client

    def get(self, key: str) -> Optional[str]:
        """获取缓存值"""
        try:
            client = self._get_client()
            return client.get(key)
        except redis.RedisError as e:
            logger.error(f"获取缓存失败: {e}")
            return None

    def set(self, key: str, value: str, ttl: int) -> bool:
        """设置缓存值"""
        try:
            client = self._get_client()
            client.set(key, value, ex=ttl)
            return True
        except redis.RedisError as e:
            logger.error(f"设置缓存失败: {e}")
            return False

    def delete(self, key: str) -> bool:
        """删除缓存值"""
        try:
            client = self._get_client()
            client.delete(key)
            return True
        except redis.RedisError as e:
            logger.error(f"删除缓存失败: {e}")
            return False