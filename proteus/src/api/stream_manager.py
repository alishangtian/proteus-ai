"""流式响应管理模块"""

import asyncio
import json
from typing import Dict, Optional, AsyncGenerator, List
from datetime import datetime
import logging
from src.utils.redis_cache import RedisCache, get_redis_connection
from src.utils.langfuse_wrapper import langfuse_wrapper
from src.api.events import create_agent_start_event, create_complete_event


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
        self, chat_id: str, message: dict, replay: bool = True
    ) -> None:
        """发送消息到指定的流，并存入redis

        Args:
            chat_id: 聊天会话ID
            message: 要发送的消息
        """
        if chat_id in self._streams:
            await self._streams[chat_id].put(message)
            # 同时存入redis，key格式为chat_stream:{chat_id}
            if replay:
                # 异步保存会话摘要信息
                asyncio.create_task(self.send_to_redis(chat_id, message))

    async def send_stream(self, chat_id: str, message: dict) -> None:
        """发送消息到指定的流，并存入redis
        Args:
            chat_id: 聊天会话ID
            message: 要发送的消息
        """
        if chat_id in self._streams:
            asyncio.create_task(self.send_to_redis(chat_id, message))

    async def send_to_redis(self, chat_id: str, message: dict) -> None:
        redis_key = f"chat_stream:{chat_id}"  #  全量式replay
        redis_key_b = f"chat_stream_b:{chat_id}"  # 阻塞式replay
        self._redis_client.lpush(redis_key, json.dumps(message))
        self._redis_client.lpush(redis_key_b, json.dumps(message))

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
            try:
                # 向队列推送完成事件，使 get_messages 生成器能正常退出
                self._streams[chat_id].put_nowait(
                    {"event": "complete", "data": "stream_closed"}
                )
            except asyncio.QueueFull:
                pass
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

        chat_status = self._redis_client.get(f"chat:{chat_id}:status")
        if isinstance(chat_status, bytes):
            chat_status = chat_status.decode("utf-8")

        # 获取用户查询用于agent_start事件
        user_query = self._redis_client.hget(CHAT_META_KEY, chat_id)
        if user_query is None:
            user_query = ""

        # 解析消息
        parsed_messages = [json.loads(msg) for msg in messages]
        # 按时间顺序排列（从旧到新）
        time_ordered = list(reversed(parsed_messages))

        # 检查第一条消息是否为agent_start
        first_event = time_ordered[0].get("event") if time_ordered else None
        if first_event != "agent_start":
            # 添加agent_start事件
            agent_start_event = await create_agent_start_event(user_query)
            # 创建临时流用于回放
            self.create_stream(chat_id)
            await self.send_message(chat_id, agent_start_event, True)
            await asyncio.sleep(0.001)
        else:
            # 创建临时流用于回放
            self.create_stream(chat_id)

        # 回放所有消息
        for message in time_ordered:
            await self.send_message(chat_id, message, True)
            await asyncio.sleep(0.001)

        # 检查最后一条消息是否为complete或error
        last_event = time_ordered[-1].get("event") if time_ordered else None
        if last_event not in ("complete", "error"):
            # 非运行中的chat或状态异常的chat，追加complete事件使回放正常结束
            complete_event = await create_complete_event()
            # 如果chat_status不是running，同时将complete事件持久化到redis
            persist = chat_status != "running"
            await self.send_message(chat_id, complete_event, persist)
            if persist and chat_status != "complete":
                # 更新状态为complete
                self._redis_client.set(f"chat:{chat_id}:status", "complete")
            await asyncio.sleep(0.001)

    def get_all_chats(self) -> dict:
        """获取所有可回放的chatid及其对应的问题

        Returns:
            dict: {chat_id: user_query} 的字典
        """
        return self._redis_client.hgetall(CHAT_META_KEY)
