"""Redis存储实现"""

import os
import time
import logging
import redis
from typing import Dict, Optional
from .base import StorageBase

logger = logging.getLogger(__name__)


class RedisStorage(StorageBase):
    """Redis存储实现类"""

    def __init__(self):
        """初始化Redis连接"""
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
                    retry_on_timeout=True,
                )
                self._client = redis.Redis(connection_pool=self._pool)
                # 测试连接是否可用
                self._client.ping()
                return
            except (redis.ConnectionError, redis.TimeoutError) as e:
                if attempt == self.max_retries - 1:
                    raise
                logger.warning(
                    f"Redis连接失败，尝试重连({attempt + 1}/{self.max_retries}): {e}"
                )
                time.sleep(self.retry_delay)

    def _get_client(self):
        """获取Redis客户端，自动处理重连"""
        try:
            # 检查连接是否活跃
            self._client.ping()
            return self._client
        except (redis.ConnectionError, redis.TimeoutError):
            logger.warning("Redis连接丢失，尝试重新连接...")
            self._connect()
            return self._client

    def _get_user_key(self, user_name: str) -> str:
        """获取用户数据的Redis键名"""
        return f"user:{user_name}"

    def _get_session_key(self, session_id: str) -> str:
        """获取会话数据的Redis键名"""
        return f"session:{session_id}"

    def save_user(self, user_name: str, user_data: Dict) -> bool:
        """保存用户数据到Redis"""
        try:
            client = self._get_client()
            user_key = self._get_user_key(user_name)
            client.hmset(user_key, user_data)
            return True
        except redis.RedisError as e:
            logger.error(f"保存用户数据失败: {e}")
            return False

    def get_user(self, user_name: str) -> Optional[Dict]:
        """从Redis获取用户数据"""
        try:
            client = self._get_client()
            user_key = self._get_user_key(user_name)
            user_data = client.hgetall(user_key)
            return user_data if user_data else None
        except redis.RedisError as e:
            logger.error(f"获取用户数据失败: {e}")
            return None

    def get_user_by_email(self, email: str) -> Optional[Dict]:
        """根据邮箱获取用户数据"""
        try:
            client = self._get_client()
            # 遍历所有用户key
            cursor = 0
            while True:
                cursor, keys = client.scan(cursor, match="user:*", count=100)
                for key in keys:
                    try:
                        user_data = client.hgetall(key)
                        if user_data.get("email") == email:
                            return user_data
                    except redis.ResponseError:
                        # 忽略类型错误的key，可能是其他用途的key
                        continue
                if cursor == 0:
                    break
            return None
        except redis.RedisError as e:
            logger.error(f"根据邮箱查找用户失败: {e}")
            return None

    def save_session(self, session_id: str, session_data: Dict) -> bool:
        """保存会话数据到Redis"""
        try:
            client = self._get_client()
            session_key = self._get_session_key(session_id)
            expire_minutes = int(os.getenv("SESSION_EXPIRE_MINUTES", 30))

            client.hmset(session_key, session_data)
            client.expire(session_key, expire_minutes * 60)
            return True
        except redis.RedisError as e:
            logger.error(f"保存会话数据失败: {e}")
            return False

    def get_session(self, session_id: str) -> Optional[Dict]:
        """从Redis获取会话数据"""
        try:
            client = self._get_client()
            session_key = self._get_session_key(session_id)
            session_data = client.hgetall(session_key)
            return session_data if session_data else None
        except redis.RedisError as e:
            logger.error(f"获取会话数据失败: {e}")
            return None

    def delete_session(self, session_id: str) -> bool:
        """从Redis删除会话数据"""
        try:
            client = self._get_client()
            session_key = self._get_session_key(session_id)
            client.delete(session_key)
            return True
        except redis.RedisError as e:
            logger.error(f"删除会话数据失败: {e}")
            return False
