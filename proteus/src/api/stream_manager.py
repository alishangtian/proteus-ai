"""流式响应管理模块"""

import asyncio
import json
from typing import Dict, Optional, AsyncGenerator, List
from datetime import datetime
import logging
from src.utils.redis_cache import RedisCache

logger = logging.getLogger(__name__)

_instance = None
CHAT_META_KEY = "chat_metas"  # 存储chatid与问题的映射


class StreamManager:
    """流式响应管理器(单例)"""

    _instance: Optional["StreamManager"] = None

    def __init__(self):
        if StreamManager._instance is not None:
            raise RuntimeError(
                "StreamManager是单例类，请使用get_instance()方法获取实例"
            )
        self._streams: Dict[str, asyncio.Queue] = {}
        self._redis_client = RedisCache()
        StreamManager._instance = self

    @classmethod
    def get_instance(cls) -> "StreamManager":
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def create_stream(self, chat_id: str, user_query: str = "") -> str:
        """创建新的流式响应队列并记录问题

        Args:
            chat_id: 聊天会话ID
            user_query: 用户原始问题

        Returns:
            str: 返回chat_id
        """
        if chat_id not in self._streams:
            self._streams[chat_id] = asyncio.Queue()
            if user_query:
                self._redis_client.hset(CHAT_META_KEY, chat_id, user_query)
        return chat_id

    async def send_message(
        self, chat_id: str, message: dict, replay: bool = False
    ) -> None:
        """发送消息到指定的流，并存入redis

        Args:
            chat_id: 聊天会话ID
            message: 要发送的消息
        """
        if chat_id in self._streams:
            await self._streams[chat_id].put(message)
            # 同时存入redis，key格式为chat_stream:{chat_id}
            if not replay:
                redis_key = f"chat_stream:{chat_id}"
                self._redis_client.lpush(redis_key, json.dumps(message))

    async def get_messages(self, chat_id: str) -> AsyncGenerator[dict, None]:
        """获取指定流的消息生成器

        Args:
            chat_id: 聊天会话ID

        Yields:
            dict: 消息内容
        """
        if chat_id not in self._streams:
            raise ValueError(f"Stream {chat_id} not found")

        queue = self._streams[chat_id]
        try:
            while True:
                message = await queue.get()
                yield message
                queue.task_done()

                # 如果是完成或错误消息，结束生成器
                if message.get("event") in ["complete", "error"]:
                    break
        finally:
            # 清理资源
            if chat_id in self._streams:
                del self._streams[chat_id]

    def close_stream(self, chat_id: str) -> None:
        """关闭指定的流

        Args:
            chat_id: 聊天会话ID
        """
        if chat_id in self._streams:
            del self._streams[chat_id]

    async def replay_chat(self, chat_id: str) -> None:
        """回放指定chat_id的历史消息

        Args:
            chat_id: 要回放的聊天会话ID
        """
        redis_key = f"chat_stream:{chat_id}"
        messages = self._redis_client.lrange(redis_key, 0, -1)

        if not messages:
            logger.warning(f"No messages found for chat: {chat_id}")
            return

        # 创建临时流用于回放
        self.create_stream(chat_id)

        # 按照原始顺序发送消息(redis lrange返回顺序与原始插入顺序相反)
        for msg in reversed(messages):
            await self.send_message(chat_id, json.loads(msg), True)
            await asyncio.sleep(0.1) 

    def get_all_chats(self) -> dict:
        """获取所有可回放的chatid及其对应的问题

        Returns:
            dict: {chat_id: user_query} 的字典
        """
        return self._redis_client.hgetall(CHAT_META_KEY)
