"""Redis缓存实现"""

import redis
import os
import time
import logging
from typing import Optional, List

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
                    retry_on_timeout=True,
                )
                self._client = redis.Redis(connection_pool=self._pool)
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

    def set(self, key: str, value: str, ex: int = None, ttl: int = None) -> bool:
        """设置缓存值，支持过期时间（ex和ttl参数兼容）"""
        try:
            client = self._get_client()
            # 兼容旧的ttl参数和新的ex参数
            expire_time = ex or ttl
            return client.set(key, value, ex=expire_time)
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

    def lpush(self, key: str, value: str) -> bool:
        """从左侧向列表添加元素"""
        try:
            client = self._get_client()
            client.lpush(key, value)
            return True
        except redis.RedisError as e:
            logger.error(f"列表添加元素失败: {e}")
            return False

    def rpush(self, key: str, *values) -> int:
        """从右侧向列表添加一个或多个元素"""
        try:
            client = self._get_client()
            return client.rpush(key, *values)
        except redis.RedisError as e:
            logger.error(f"列表添加元素失败: {e}")
            return 0

    def lrange(self, key: str, start: int = 0, end: int = -1) -> list:
        """获取列表指定范围的元素"""
        try:
            client = self._get_client()
            return client.lrange(key, start, end)
        except redis.RedisError as e:
            logger.error(f"获取列表元素失败: {e}")
            return []

    def rrange(self, key: str, size: int = 5) -> list:
        """从redis队列的右侧取出最后size个元素"""
        try:
            client = self._get_client()
            # 获取列表长度
            llen = client.llen(key)
            if llen == 0:
                return []

            # 计算从右侧取size个元素的起始位置
            # Redis列表索引从0开始，-1表示最后一个元素
            # 如果size大于列表长度，则取整个列表
            if size >= llen:
                start = 0
                end = -1
            else:
                # 从倒数第size个元素开始到最后一个元素
                start = -(size)
                end = -1

            return client.lrange(key, start, end)
        except redis.RedisError as e:
            logger.error(f"获取列表元素失败: {e}")
            return []

    def hset(self, name: str, key: str, value: str) -> bool:
        """设置哈希表字段值"""
        try:
            client = self._get_client()
            return client.hset(name, key, value)
        except redis.RedisError as e:
            logger.error(f"设置哈希值失败: {e}")
            return False

    def hget(self, name: str, key: str) -> str:
        """获取哈希表字段值"""
        try:
            client = self._get_client()
            return client.hget(name, key)
        except redis.RedisError as e:
            logger.error(f"获取哈希值失败: {e}")
            return None

    def hgetall(self, name: str) -> dict:
        """获取哈希表所有字段值"""
        try:
            client = self._get_client()
            return client.hgetall(name)
        except redis.RedisError as e:
            logger.error(f"获取哈希表失败: {e}")
            return {}

    def zadd(self, key: str, mapping: dict) -> bool:
        """向有序集合添加成员"""
        try:
            client = self._get_client()
            client.zadd(key, mapping)
            return True
        except redis.RedisError as e:
            logger.error(f"向有序集合添加成员失败: {e}")
            return False

    def zrevrange(
        self, key: str, start: int = 0, end: int = -1, withscores: bool = False
    ) -> List:
        """按分数从高到低获取有序集合成员"""
        try:
            client = self._get_client()
            return client.zrevrange(key, start, end, withscores=withscores)
        except redis.RedisError as e:
            logger.error(f"获取有序集合成员失败: {e}")
            return []

    def zrange(
        self, key: str, start: int = 0, end: int = -1, withscores: bool = False
    ) -> List:
        """按分数从低到高获取有序集合成员"""
        try:
            client = self._get_client()
            return client.zrange(key, start, end, withscores=withscores)
        except redis.RedisError as e:
            logger.error(f"获取有序集合成员失败: {e}")
            return []

    def zremrangebyscore(self, key: str, min_score: float, max_score: float) -> int:
        """根据分数范围删除有序集合成员"""
        try:
            client = self._get_client()
            return client.zremrangebyscore(key, min_score, max_score)
        except redis.RedisError as e:
            logger.error(f"删除有序集合成员失败: {e}")
            return 0

    def zcard(self, key: str) -> int:
        """获取有序集合成员数量"""
        try:
            client = self._get_client()
            return client.zcard(key)
        except redis.RedisError as e:
            logger.error(f"获取有序集合数量失败: {e}")
            return 0

    def zremrangebyrank(self, key: str, start: int, end: int) -> int:
        """根据排名范围删除有序集合成员"""
        try:
            client = self._get_client()
            return client.zremrangebyrank(key, start, end)
        except redis.RedisError as e:
            logger.error(f"根据排名删除有序集合成员失败: {e}")
            return 0

    def lpop(self, key: str) -> Optional[str]:
        """从左侧弹出列表元素（非阻塞）"""
        try:
            client = self._get_client()
            return client.lpop(key)
        except redis.RedisError as e:
            logger.error(f"列表弹出元素失败 (lpop): {e}")
            return None

    def rpop(self, key: str) -> Optional[str]:
        """从右侧弹出列表元素（非阻塞）"""
        try:
            client = self._get_client()
            return client.rpop(key)
        except redis.RedisError as e:
            logger.error(f"列表弹出元素失败 (rpop): {e}")
            return None

    def lrem(self, key: str, count: int, value: str) -> int:
        """从列表中移除与 value 匹配的元素，count 指定最多移除的数量（与 redis.lrem 接口一致）"""
        try:
            client = self._get_client()
            return client.lrem(key, count, value)
        except redis.RedisError as e:
            logger.error(f"列表移除元素失败 (lrem): {e}")
            return 0

    def blpop(self, keys, timeout: int = 0):
        """阻塞式地从左侧弹出元素，支持传入单个key或key列表（timeout秒，0为阻塞直到有元素）"""
        try:
            client = self._get_client()
            # redis-py 返回 (key, value) 或 None
            return client.blpop(keys, timeout=timeout)
        except redis.RedisError as e:
            logger.error(f"阻塞式弹出列表元素失败 (blpop): {e}")
            return None

    def exists(self, key: str) -> bool:
        """检查key是否存在"""
        try:
            client = self._get_client()
            return client.exists(key) > 0
        except redis.RedisError as e:
            logger.error(f"检查key存在性失败: {e}")
            return False

    def llen(self, key: str) -> int:
        """获取列表长度"""
        try:
            client = self._get_client()
            return client.llen(key)
        except redis.RedisError as e:
            logger.error(f"获取列表长度失败: {e}")
            return 0

    def expire(self, key: str, time: int) -> bool:
        """设置key的过期时间（秒）"""
        try:
            client = self._get_client()
            return client.expire(key, time)
        except redis.RedisError as e:
            logger.error(f"设置过期时间失败: {e}")
            return False

    def pipeline(self):
        """获取Redis pipeline对象"""
        try:
            client = self._get_client()
            return client.pipeline()
        except redis.RedisError as e:
            logger.error(f"创建pipeline失败: {e}")
            return None


# 全局 Redis 连接管理器实例
_redis_instance = None


def get_redis_connection():
    """获取 Redis 连接实例

    这是一个全局函数，用于获取 Redis 连接实例。
    使用单例模式确保整个应用程序中只有一个 Redis 连接池。

    Returns:
        RedisCache: Redis 缓存实例
    """
    global _redis_instance
    if _redis_instance is None:
        _redis_instance = RedisCache()
    return _redis_instance
