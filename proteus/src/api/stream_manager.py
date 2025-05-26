"""流式响应管理模块"""

import asyncio
from typing import Dict, Optional, AsyncGenerator
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

_instance = None

class StreamManager:
    """流式响应管理器(单例)"""
    _instance: Optional['StreamManager'] = None
    def __init__(self):
        if StreamManager._instance is not None:
            raise RuntimeError("StreamManager是单例类，请使用get_instance()方法获取实例")
        self._streams: Dict[str, asyncio.Queue] = {}
        StreamManager._instance = self
    
    @classmethod
    def get_instance(cls) -> 'StreamManager':
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
        
    def create_stream(self, chat_id: str) -> str:
        """创建新的流式响应队列
        
        Args:
            chat_id: 聊天会话ID
            
        Returns:
            str: 返回chat_id
        """
        if chat_id not in self._streams:
            self._streams[chat_id] = asyncio.Queue()
        return chat_id
        
    async def send_message(self, chat_id: str, message: dict) -> None:
        """发送消息到指定的流
        
        Args:
            chat_id: 聊天会话ID
            message: 要发送的消息
        """
        if chat_id in self._streams:
            await self._streams[chat_id].put(message)
            
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
