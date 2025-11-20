"""
Conversation Manager
统一管理对话相关的操作，包括对话历史保存、加载、删除、会话管理等
"""

import json
import time
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from src.utils.redis_cache import get_redis_connection
from src.utils.langfuse_wrapper import langfuse_wrapper
import logging


class ConversationManager:
    """对话管理器，统一处理所有对话相关操作"""

    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        初始化对话管理器

        Args:
            logger: 日志记录器，如果为None则创建默认日志记录器
        """
        self.logger = logger or logging.getLogger(__name__)
        self.redis_conn = get_redis_connection()

    def save_message(self, conversation_id: str, message: Dict[str, Any]) -> bool:
        """
        保存消息到对话历史

        Args:
            conversation_id: 会话ID
            message: 消息对象，包含role、content等字段

        Returns:
            bool: 保存是否成功
        """
        try:
            redis_key = f"conversation:{conversation_id}"
            current_timestamp = time.time()

            # 构建记录
            record = {
                "timestamp": current_timestamp,
                "type": message.get("role", ""),
                "content": message.get("content", ""),
                "message": message,  # 保存完整的message对象
            }

            record_json = json.dumps(record, ensure_ascii=False)

            # 使用list存储，保持消息顺序
            self.redis_conn.rpush(redis_key, record_json)

            self.logger.info(
                f"成功保存消息到对话历史 (conversation_id: {conversation_id}, "
            )
            return record_json

        except Exception as e:
            self.logger.error(
                f"保存消息到对话历史失败 (conversation_id: {conversation_id}): {str(e)}"
            )
            return None

    def load_conversation_history(
        self, conversation_id: str, max_messages: int = 30, expire_hours: int = 0
    ) -> List[Dict[str, Any]]:
        """
        加载对话历史

        Args:
            conversation_id: 会话ID
            max_messages: 最大消息数量
            expire_hours: 过期时间（小时）

        Returns:
            List[Dict[str, Any]]: 对话历史列表
        """
        try:
            redis_key = f"conversation:{conversation_id}"

            if not self.redis_conn.exists(redis_key):
                self.logger.info(f"未找到对话历史 (conversation_id: {conversation_id})")
                return []

            total_count = self.redis_conn.llen(redis_key)
            records_to_get = min(max_messages, total_count)

            # 获取最近的记录
            start_index = max(0, total_count - records_to_get)
            history_data = self.redis_conn.lrange(redis_key, start_index, -1)

            # 解析并过滤过期数据
            conversation_history: List[Dict[str, Any]] = []
            current_time = time.time()
            expire_seconds = expire_hours * 3600

            for record_json in history_data:
                try:
                    record = json.loads(record_json)
                    record_timestamp = record.get("timestamp", 0)

                    if expire_seconds <= 0:
                        # 优先使用完整的message对象
                        message = record.get("message")
                        if message:
                            conversation_history.append(message)
                        else:
                            # 向后兼容旧格式
                            role = record.get("type", "")
                            content = record.get("content", "")
                            if role and content:
                                conversation_history.append(
                                    {"role": role, "content": content}
                                )
                    # 检查是否过期
                    elif current_time - record_timestamp <= expire_seconds:
                        # 优先使用完整的message对象
                        message = record.get("message")
                        if message:
                            conversation_history.append(message)
                        else:
                            # 向后兼容旧格式
                            role = record.get("type", "")
                            content = record.get("content", "")
                            if role and content:
                                conversation_history.append(
                                    {"role": role, "content": content}
                                )
                except (json.JSONDecodeError, Exception) as e:
                    self.logger.warning(f"解析对话记录失败: {str(e)}")
                    continue

            if conversation_history:
                self.logger.info(
                    f"成功加载 {len(conversation_history)} 条对话历史记录 (conversation_id: {conversation_id})"
                )

            return conversation_history

        except Exception as e:
            self.logger.error(
                f"加载对话历史失败 (conversation_id: {conversation_id}): {str(e)}"
            )
            return []

    async def _generate_conversation_title_with_llm(self, initial_question: str) -> str:
        """使用 LLM 生成会话标题

        Args:
            initial_question: 初始问题

        Returns:
            生成的会话标题
        """
        try:
            from src.api.llm_api import call_llm_api
            from src.utils.langfuse_wrapper import langfuse_wrapper

            with langfuse_wrapper.dynamic_observe(name="generate_conversation_title"):
                # 构建提示词，要求生成简洁的标题
                messages = [
                    {
                        "role": "system",
                        "content": "你是一个专业的标题生成助手。请根据用户的问题生成一个简洁、准确的会话标题，不超过20个字。只返回标题文本，不要有任何其他内容。",
                    },
                    {
                        "role": "user",
                        "content": f"请为以下问题生成一个简洁的会话标题：\n\n{initial_question}",
                    },
                ]

                # 调用 LLM API 生成标题
                title, _ = await call_llm_api(
                    messages=messages,
                    request_id=f"title-gen-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    temperature=0.3,  # 使用较低的温度以获得更稳定的输出
                    model_name="deepseek-chat",  # 使用默认模型
                )

                # 清理标题，移除可能的引号和多余空格
                title = title.strip().strip('"').strip("'").strip()

                # 如果标题过长，截断并添加省略号
                if len(title) > 20:
                    title = title[:20] + "..."

                self.logger.info(f"生成会话标题: {title}")
                return title

        except Exception as e:
            # 如果生成失败，回退到简单截取方式
            self.logger.warning(f"使用 LLM 生成标题失败，使用默认方式: {str(e)}")
            return self._generate_conversation_title_simple(initial_question)

    def _generate_conversation_title_simple(self, initial_question: str) -> str:
        """
        生成会话标题（简化版本，截取前20个字符）

        Args:
            initial_question: 初始问题

        Returns:
            str: 生成的会话标题
        """
        if len(initial_question) > 20:
            return initial_question[:20] + "..."
        return initial_question

    async def save_conversation_summary(
        self,
        conversation_id: str,
        chat_id: str,
        initial_question: str,
        user_name: str = "anonymous",
        modul: str = None,
    ) -> bool:
        """异步保存会话摘要信息到 Redis

        Args:
            conversation_id: 会话ID
            chat_id: 聊天ID
            initial_question: 初始问题
            user_name: 用户名
            modul: 模型类型
        """
        try:
            conversation_key = f"conversation:{conversation_id}:info"

            # 使用 LLM 生成会话标题
            title = await self._generate_conversation_title_with_llm(initial_question)

            # 检查会话是否已存在
            if not self.redis_conn.exists(conversation_key):
                # 新建会话：保存完整信息
                conversation_data = {
                    "conversation_id": conversation_id,
                    "title": title,
                    "initial_question": initial_question,
                    "user_name": user_name,
                    "modul": modul or "unknown",
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                    "first_chat_id": chat_id,
                }
                self.redis_conn.hmset(conversation_key, mapping=conversation_data)

                # 添加到用户的会话列表（有序集合，按时间戳排序）
                user_conversations_key = f"user:{user_name}:conversations"
                timestamp = time.time()
                self.redis_conn.zadd(
                    user_conversations_key, {conversation_id: timestamp}
                )
                self.logger.info(f"已创建会话摘要: {conversation_id}, 标题: {title}")
            else:
                # 已存在会话：更新标题和时间戳
                self.redis_conn.hset(conversation_key, "title", title)
                self.redis_conn.hset(
                    conversation_key, "updated_at", datetime.now().isoformat()
                )

                # 更新用户在有序集合中的时间戳，确保按更新时间排序
                user_conversations_key = f"user:{user_name}:conversations"
                timestamp = time.time()
                self.redis_conn.zadd(
                    user_conversations_key, {conversation_id: timestamp}
                )

                self.logger.info(f"已更新会话摘要: {conversation_id}, 新标题: {title}")

            # 保存 conversation_id 和 chat_id 的关系
            conv_chats_key = f"conversation:{conversation_id}:chats"
            self.redis_conn.rpush(conv_chats_key, chat_id)

            # 保存反向映射关系
            self.redis_conn.set(
                f"chat:{chat_id}:conversation", conversation_id, ex=None
            )
            return True
        except Exception as e:
            self.logger.error(f"保存会话摘要失败: {str(e)}", exc_info=True)
            return False

    async def get_user_conversations(
        self, user_name: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        获取用户的会话列表

        Args:
            user_name: 用户名
            limit: 限制数量

        Returns:
            List[Dict[str, Any]]: 会话列表
        """
        try:
            user_conversations_key = f"user:{user_name}:conversations"

            # 从有序集合中获取会话ID列表（按时间倒序）
            conversation_ids = self.redis_conn.zrevrange(
                user_conversations_key, 0, limit - 1
            )

            conversations = []
            for conv_id in conversation_ids:
                conv_id_str = (
                    conv_id.decode("utf-8")
                    if isinstance(conv_id, bytes)
                    else str(conv_id)
                )
                conversation_key = f"conversation:{conv_id_str}:info"
                conv_data = self.redis_conn.hgetall(conversation_key)

                if conv_data:
                    # 转换字节数据为字符串
                    conv_info = {
                        k.decode("utf-8") if isinstance(k, bytes) else k: (
                            v.decode("utf-8") if isinstance(v, bytes) else v
                        )
                        for k, v in conv_data.items()
                    }

                    # 获取该会话的chat数量
                    conv_chats_key = f"conversation:{conv_id_str}:chats"
                    chat_count = self.redis_conn.llen(conv_chats_key)
                    conv_info["chat_count"] = chat_count

                    conversations.append(conv_info)

            return conversations

        except Exception as e:
            self.logger.error(
                f"获取用户会话列表失败 (user_name: {user_name}): {str(e)}"
            )
            return []

    async def get_conversation_detail(
        self, conversation_id: str, user_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        获取会话详细信息

        Args:
            conversation_id: 会话ID
            user_name: 用户名

        Returns:
            Optional[Dict[str, Any]]: 会话详细信息，如果不存在则返回None
        """
        try:
            conversation_key = f"conversation:{conversation_id}:info"
            conv_data = self.redis_conn.hgetall(conversation_key)

            if not conv_data:
                return None

            # 转换字节数据为字符串
            conv_info = {
                k.decode("utf-8") if isinstance(k, bytes) else k: (
                    v.decode("utf-8") if isinstance(v, bytes) else v
                )
                for k, v in conv_data.items()
            }

            # 验证用户权限
            if conv_info.get("user_name") != user_name:
                self.logger.warning(f"用户 {user_name} 无权访问会话 {conversation_id}")
                return None

            # 获取该会话的所有chat_id
            conv_chats_key = f"conversation:{conversation_id}:chats"
            chat_ids = self.redis_conn.lrange(conv_chats_key, 0, -1)
            conv_info["chat_ids"] = [
                chat_id.decode("utf-8") if isinstance(chat_id, bytes) else str(chat_id)
                for chat_id in chat_ids
            ]

            return conv_info

        except Exception as e:
            self.logger.error(
                f"获取会话详情失败 (conversation_id: {conversation_id}): {str(e)}"
            )
            return None

    async def delete_conversation(self, conversation_id: str, user_name: str) -> bool:
        """
        删除会话

        Args:
            conversation_id: 会话ID
            user_name: 用户名

        Returns:
            bool: 删除是否成功
        """
        try:
            conversation_key = f"conversation:{conversation_id}:info"
            conv_data = self.redis_conn.hgetall(conversation_key)

            if not conv_data:
                self.logger.warning(f"会话不存在 (conversation_id: {conversation_id})")
                return False

            # 验证用户权限
            conv_user_name = (
                conv_data.get(b"user_name", b"").decode("utf-8")
                if isinstance(conv_data.get(b"user_name"), bytes)
                else conv_data.get("user_name", "")
            )
            if conv_user_name != user_name:
                self.logger.warning(f"用户 {user_name} 无权删除会话 {conversation_id}")
                return False

            # 删除会话信息
            self.redis_conn.delete(conversation_key)

            # 删除会话的chat列表
            conv_chats_key = f"conversation:{conversation_id}:chats"
            self.redis_conn.delete(conv_chats_key)

            # 删除对话历史
            conversation_history_key = f"conversation:{conversation_id}"
            self.redis_conn.delete(conversation_history_key)

            # 从用户会话列表中移除
            user_conversations_key = f"user:{user_name}:conversations"
            self.redis_conn.zrem(user_conversations_key, conversation_id)

            self.logger.info(f"用户 {user_name} 删除了会话 {conversation_id}")
            return True

        except Exception as e:
            self.logger.error(
                f"删除会话失败 (conversation_id: {conversation_id}): {str(e)}"
            )
            return False

    def clear_conversation_history(self, conversation_id: str) -> bool:
        """
        清空对话历史

        Args:
            conversation_id: 会话ID

        Returns:
            bool: 清空是否成功
        """
        try:
            conversation_key = f"conversation:{conversation_id}"
            self.redis_conn.delete(conversation_key)
            self.logger.info(f"已清空对话历史 (conversation_id: {conversation_id})")
            return True
        except Exception as e:
            self.logger.error(
                f"清空对话历史失败 (conversation_id: {conversation_id}): {str(e)}"
            )
            return False


# 创建全局实例
conversation_manager = ConversationManager()

from src.utils.dynamic_observer import auto_apply_here

auto_apply_here(
    globals(),
    include=None,
    exclude=[],
    only_in_module=True,
    verbose=False,
)
