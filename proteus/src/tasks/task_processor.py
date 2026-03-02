"""
任务处理器模块，负责处理异步任务执行。
将 process_agent 功能封装为类，便于管理和测试。
"""

import logging
import json
import asyncio
import time
from typing import Optional, List, Dict, Any
from datetime import datetime

from src.utils.redis_cache import get_redis_connection
from src.agent.chat_agent import ChatAgent
from src.api.stream_manager import StreamManager
from src.utils.langfuse_wrapper import langfuse_wrapper

logger = logging.getLogger(__name__)


async def generate_conversation_title(text_content: str) -> str:
    """根据 Markdown 内容提取第一个一级标题作为会话标题。
    如果不存在一级标题，则使用文本开头截断作为标题。

    Args:
        text_content: 完整的 Markdown 文本内容 (可以是 initial_question 或 final_result)。

    Returns:
        生成的会话标题。
    """
    try:
        logger.info("内容中未检测到一级标题，尝试使用 LLM 生成标题")
        # 如果没有一级标题，回退到原来的 LLM 生成标题逻辑
        # 构建提示词，要求生成简洁的标题
        messages = [
            {
                "role": "system",
                "content": "你是一个专业的标题生成助手。请根据以下内容生成一个简洁、准确的会话标题，不超过25个字。只返回标题文本，不要有任何其他内容。",
            },
            {
                "role": "user",
                "content": f"请为以下内容生成一个简洁的会话标题：\n\n{text_content}",
            },
        ]

        # 调用 LLM API 生成标题
        from src.api.llm_api import call_llm_api

        llm_title, _ = await call_llm_api(
            messages=messages,
            request_id=f"title-gen-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            temperature=0.3,  # 使用较低的温度以获得更稳定的输出
            model_name="deepseek-chat",  # 使用默认模型
        )

        # 清理标题，移除可能的引号和多余空格
        llm_title = llm_title.strip().strip('"').strip("'").strip()

        # 如果标题过长，截断并添加省略号
        if len(llm_title) > 25:
            llm_title = llm_title[:22] + "..."

        logger.info(f"LLM 生成会话标题: {llm_title}")
        return llm_title

    except Exception as e:
        logger.warning(f"生成会话标题失败，回退到简单截断方式: {str(e)}")
        # 如果 LLM 生成也失败，回退到简单截取方式
        fallback_title = (
            text_content[:20] + "..." if len(text_content) > 20 else text_content
        )
        return fallback_title


class TaskProcessor:
    """处理Agent任务的处理器类"""

    def __init__(self, stream_manager: Optional[StreamManager] = None):
        """
        初始化任务处理器

        Args:
            stream_manager: 流管理器实例，如果为 None 则使用全局实例
        """
        self.stream_manager = stream_manager or StreamManager.get_instance()
        self.redis_conn = get_redis_connection()

    async def process(
        self,
        chat_id: str,
        query: str,
        itecount: int,
        agentid: str = None,
        agentmodul: str = None,
        team_name: str = None,
        conversation_id: str = None,
        model_name: str = None,
        conversation_round: int = 5,
        file_ids: Optional[List[str]] = None,
        user_name: str = None,
        tool_memory_enabled: bool = False,
        sop_memory_enabled: bool = False,
        enable_tools: bool = False,
        tool_choices: Optional[List[str]] = None,
        selected_skills: Optional[List[str]] = None,
        workspace_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """处理Agent请求，相当于原来的 process_agent 函数

        Args:
            参数与 process_agent 保持一致

        Returns:
            包含状态和最终结果的字典
        """
        logger.info(
            f"[{chat_id}] 开始处理Agent请求: {query[:100]}... (agentid={agentid}, user_name={user_name}, selected_skills={selected_skills}, workspace_path={workspace_path})"
        )
        team = None
        agent = None
        final_result = None
        try:
            logger.info(f"[{chat_id}] process_agent 接收到的 file_ids: {file_ids}")
            file_analysis_context = ""
            if file_ids:
                for file_id in file_ids:
                    file_data_str = self.redis_conn.get(f"file_analysis:{file_id}")
                    if file_data_str:
                        file_data = json.loads(file_data_str)
                        analysis = file_data.get("analysis")
                        original_filename = file_data.get(
                            "original_filename", "未知文件"
                        )
                        file_type = file_data.get("file_type", "未知类型")

                        if analysis:
                            file_analysis_context += f"\n\n用户上传了文件 '{original_filename}' ({file_type})，其解析内容如下：\n{analysis}"
                        else:
                            file_analysis_context += f"\n\n用户上传了文件 '{original_filename}' ({file_type})，该文件不支持解析，只进行了上传。"
                    else:
                        logger.warning(
                            f"[{chat_id}] Redis 中未找到 file_id: {file_id} 的文件分析数据。"
                        )
                if file_analysis_context:
                    logger.info(
                        f"[{chat_id}] 已将文件解析内容添加到context中。长度: {len(file_analysis_context)}"
                    )
                else:
                    logger.info(f"[{chat_id}] 没有文件解析内容需要添加到文本中。")
            # 确保流存在，以便工具调用事件能够被发送
            if self.stream_manager:
                self.stream_manager.create_stream(chat_id, query)

            if agentmodul == "chat":
                # chat 模式：使用 ChatAgent 类处理
                logger.info(
                    f"[{chat_id}] 开始 chat 模式请求（流式），工具调用: {enable_tools}"
                )

                # 创建 ChatAgent 实例
                chat_agent = ChatAgent(
                    stream_manager=self.stream_manager,
                    model_name=model_name,
                    enable_tools=enable_tools,
                    tool_choices=tool_choices,
                    max_tool_iterations=itecount,
                    conversation_id=conversation_id,
                    conversation_round=conversation_round,
                    user_name=user_name,
                    enable_skills_memory=sop_memory_enabled,
                    enable_tool_memory=tool_memory_enabled,
                    selected_skills=selected_skills,
                    workspace_path=workspace_path,
                )

                # 运行 ChatAgent
                final_result = await chat_agent.run(
                    chat_id=chat_id,
                    text=query,
                    file_analysis_context=file_analysis_context,
                )
            elif agentmodul == "task":
                # task 模式：使用 ChatAgent 类处理，但 stream_manager 为空，不发送流事件
                logger.info(
                    f"[{chat_id}] 开始 task 模式请求（非流式），工具调用: {enable_tools}"
                )

                # 创建 ChatAgent 实例，stream_manager 为 None
                chat_agent = ChatAgent(
                    stream_manager=self.stream_manager,
                    model_name=model_name,
                    enable_tools=enable_tools,
                    tool_choices=tool_choices,
                    max_tool_iterations=itecount,
                    conversation_id=conversation_id,
                    conversation_round=conversation_round,
                    user_name=user_name,
                    enable_skills_memory=sop_memory_enabled,
                    enable_tool_memory=tool_memory_enabled,
                    selected_skills=selected_skills,
                    workspace_path=workspace_path,
                )

                # 运行 ChatAgent
                final_result = await chat_agent.run(
                    chat_id=chat_id,
                    text=query,
                    file_analysis_context=file_analysis_context,
                )
            else:
                await self.stream_manager.send_message(
                    chat_id, await self._create_error_event("工作模式未定义")
                )
        except Exception as e:
            from src.api.events import create_error_event

            error_msg = f"处理Agent请求失败: {str(e)}"
            logger.error(f"[{chat_id}] {error_msg}", exc_info=True)
            # task模式下不发送流事件
            if agentmodul != "task":
                await self.stream_manager.send_message(
                    chat_id, await create_error_event(error_msg)
                )
            if team is not None:
                await team.stop()
        finally:
            # 会话完成后异步更新会话标题 - 仅当 final_result 有内容时才尝试更新，以生成更准确的标题
            if conversation_id and final_result:
                asyncio.create_task(
                    self._save_conversation_summary(
                        conversation_id=conversation_id,
                        chat_id=chat_id,
                        initial_question=query,
                        user_name=user_name,
                        modul=agentmodul,
                        final_result=final_result,
                    )
                )
            return {"status": "success", "final_result": final_result, "text": query}

    async def _create_error_event(self, content: str) -> Dict[str, Any]:
        """创建错误事件"""
        from src.api.events import create_error_event

        return await create_error_event(content)

    async def _save_conversation_summary(
        self,
        conversation_id: str,
        chat_id: str,
        initial_question: str,
        user_name: str = None,
        modul: str = None,
        final_result: str = None,
    ):
        """异步保存会话摘要信息到 Redis

        Args:
            conversation_id: 会话ID
            chat_id: 聊天ID
            initial_question: 初始问题
            user_name: 用户名
            modul: 模型类型
            final_result: 最终的会话结果，如果存在则用于生成标题
        """
        try:
            redis_conn = self.redis_conn
            conversation_key = f"conversation:{conversation_id}:info"
            user_name = user_name or "anonymous"

            # 优先使用 final_result 生成标题，否则使用 initial_question
            title = await generate_conversation_title(final_result or initial_question)

            # 检查会话是否已存在
            if not redis_conn.exists(conversation_key):
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
                redis_conn.hmset(conversation_key, mapping=conversation_data)

                # 添加到用户的会话列表（有序集合，按时间戳排序）
                user_conversations_key = f"user:{user_name}:conversations"
                timestamp = time.time()
                redis_conn.zadd(user_conversations_key, {conversation_id: timestamp})
                logger.info(f"已创建会话摘要: {conversation_id}, 标题: {title}")
            else:
                # 已存在会话：更新标题和时间戳
                redis_conn.hset(conversation_key, "title", title)
                redis_conn.hset(
                    conversation_key, "updated_at", datetime.now().isoformat()
                )

                # 更新用户在有序集合中的时间戳，确保按更新时间排序
                user_conversations_key = f"user:{user_name}:conversations"
                timestamp = time.time()
                redis_conn.zadd(user_conversations_key, {conversation_id: timestamp})

                logger.info(f"已更新会话摘要: {conversation_id}, 新标题: {title}")

        except Exception as e:
            logger.error(f"保存会话摘要失败: {str(e)}", exc_info=True)
