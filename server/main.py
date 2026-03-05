"""
轻量级 Conversation 访问 WebServer
仅提供对话相关接口和任务提交功能。
鉴权方式：Bearer Token (beartoken 模式)
"""

import os
import logging
import json
import asyncio
import yaml
import redis
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Depends
from sse_starlette.sse import EventSourceResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from src.utils.logger import setup_logger
from src.manager.stream_manager import StreamManager
from src.manager.redis_manager import get_redis_client
from src.langfuse.langfuse_wrapper import langfuse_wrapper

# 加载环境变量
load_dotenv()

# 获取日志文件路径
log_file_path = os.getenv("LOG_FILE", "logs/server.log")

# Agent 状态键 TTL（秒），默认 1 天
AGENT_STATUS_TTL = int(os.getenv("AGENT_STATUS_TTL", 86400))

# 配置日志
setup_logger(log_file_path)
logger = logging.getLogger(__name__)

# 创建 FastAPI 应用
app = FastAPI(title="Conversation API Server", version="1.0.0")

# 添加 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 认证相关函数
def get_token_key(token: str) -> str:
    """获取 token 的 Redis 键名"""
    return f"token:{token}"


def get_session_key(session_id: str) -> str:
    """获取 session 的 Redis 键名"""
    return f"session:{session_id}"


def get_user_key(user_name: str) -> str:
    """获取 user 的 Redis 键名"""
    return f"user:{user_name}"


async def get_current_user(request: Request) -> Optional[Dict[str, Any]]:
    """
    获取当前登录用户，仅支持 Bearer Token 鉴权
    返回包含 user_name 和 nick_name 的字典，未认证则返回 None
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        logger.warning("请求未提供 Bearer Token")
        return None

    token = auth_header[7:].strip()
    if not token:
        logger.warning("Bearer Token 为空")
        return None

    logger.info(f"从 Authorization 头获取到 token: {token[:10]}...")

    redis_client = get_redis_client()

    # 使用 token 验证
    token_key = get_token_key(token)
    try:
        session_data = redis_client.hgetall(token_key)
        if not session_data:
            logger.warning(f"token 无效或已过期: {token[:10]}...")
            return None
    except redis.RedisError as e:
        logger.error(f"获取 token 数据失败: {e}")
        return None

    user_name = session_data.get("user_name")
    if not user_name:
        return None

    # 获取用户数据以获取昵称
    user_key = get_user_key(user_name)
    try:
        user_data = redis_client.hgetall(user_key)
    except redis.RedisError as e:
        logger.error(f"获取用户数据失败: {e}")
        return None

    if not user_data:
        return None

    nick_name = user_data.get("nick_name", user_name)

    return {
        "user_name": user_name,
        "nick_name": nick_name,
        "expires": session_data.get("expires", ""),
    }


# 依赖项：需要认证的用户
async def require_auth(user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="未认证")
    return user


# 中间件：可选，这里我们使用依赖项进行认证，也可以添加全局中间件
# 为了简单，我们不在中间件中强制认证，而是在每个端点使用依赖项


# 健康检查端点
@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


# 对话相关端点


@app.get("/conversations")
async def get_conversations(
    request: Request, limit: int = 50, user: dict = Depends(require_auth)
):
    """获取当前用户的会话列表

    Args:
        request: 请求对象
        limit: 返回的会话数量限制（默认50）

    Returns:
        dict: 包含会话列表的响应
    """
    try:
        user_name = user["user_name"]
        redis_conn = get_redis_client()
        user_conversations_key = f"user:{user_name}:conversations"

        # 从有序集合中获取会话ID列表（按时间倒序）
        conversation_ids = redis_conn.zrevrange(user_conversations_key, 0, limit - 1)

        conversations = []
        for conv_id in conversation_ids:
            conv_id_str = (
                conv_id.decode("utf-8") if isinstance(conv_id, bytes) else conv_id
            )
            conversation_key = f"conversation:{conv_id_str}:info"
            conv_data = redis_conn.hgetall(conversation_key)

            if conv_data:
                # 将字节转换为字符串
                conv_info = {
                    k.decode("utf-8") if isinstance(k, bytes) else k: (
                        v.decode("utf-8") if isinstance(v, bytes) else v
                    )
                    for k, v in conv_data.items()
                }

                # 获取该会话的chat数量，并检查最新chat是否正在运行
                conv_chats_key = f"conversation:{conv_id_str}:chats"
                chat_count = redis_conn.llen(conv_chats_key)
                conv_info["chat_count"] = chat_count

                # 检查最新 chat 的运行状态
                last_chat_ids = redis_conn.lrange(conv_chats_key, -1, -1)
                is_running = False
                if last_chat_ids:
                    last_chat_id = (
                        last_chat_ids[0].decode("utf-8")
                        if isinstance(last_chat_ids[0], bytes)
                        else last_chat_ids[0]
                    )
                    chat_status = redis_conn.get(f"chat:{last_chat_id}:status")
                    if isinstance(chat_status, bytes):
                        chat_status = chat_status.decode("utf-8")
                    is_running = chat_status == "running"
                conv_info["is_running"] = is_running

                conversations.append(conv_info)

        return {"success": True, "conversations": conversations}

    except Exception as e:
        logger.error(f"获取会话列表失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取会话列表失败: {str(e)}")


@app.get("/models")
async def list_models():
    """返回 conf/models_config.yaml 中定义的模型名列表

    从当前文件所在目录开始，向上递归查找最近的 conf/models_config.yaml 文件。
    如果到达文件系统根目录仍未找到，返回空的模型列表（而不是 500 错误）。
    """
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        found_path = None
        while True:
            candidate = os.path.join(current_dir, "conf", "models_config.yaml")
            if os.path.exists(candidate):
                found_path = candidate
                break
            parent_dir = os.path.dirname(current_dir)
            if parent_dir == current_dir:
                # 已到达文件系统根目录，停止查找
                break
            current_dir = parent_dir

        if not found_path:
            logger.warning("未找到 models_config.yaml，返回空模型列表")
            return {"success": True, "models": []}

        with open(found_path, "r", encoding="utf-8") as f:
            models_cfg = yaml.safe_load(f)

        model_keys = list(models_cfg.keys()) if isinstance(models_cfg, dict) else []
        return {"success": True, "models": model_keys}
    except Exception as e:
        logger.error(f"读取模型配置失败: {e}", exc_info=True)
        # 发生不可预期错误时返回 500
        raise HTTPException(status_code=500, detail=str(e))


# 任务提交相关模型
class SubmitTaskRequest(BaseModel):
    query: str = Field(..., description="用户输入的文本")
    modul: str = Field("chat", description="模型类型，如 chat, task 等")
    model_name: Optional[str] = Field(None, description="模型名称")
    itecount: int = Field(100, description="迭代次数")
    agentid: Optional[str] = Field(None, description="代理ID")
    team_name: Optional[str] = Field(None, description="团队名称")
    conversation_id: str = Field(..., min_length=1, description="会话ID")
    conversation_round: int = Field(20, description="会话轮次")
    file_ids: Optional[List[str]] = Field(None, description="文件ID列表")
    tool_memory_enabled: bool = Field(False, description="是否启用工具记忆")
    sop_memory_enabled: bool = Field(True, description="是否启用SOP记忆")
    enable_tools: bool = Field(True, description="是否启用工具调用")
    tool_choices: Optional[List[str]] = Field(None, description="工具选择列表")
    selected_skills: Optional[List[str]] = Field(None, description="用户选中的技能列表")
    chat_id: str = Field(..., min_length=1, description="关联的聊天ID")
    task_type: str = Field(
        "start", description="任务类型：start（开始任务）、stop（停止任务）等"
    )


@langfuse_wrapper.dynamic_observe("submit_task")
@app.post("/submit_task")
async def submit_task(
    request: SubmitTaskRequest,
    http_request: Request,
    user: dict = Depends(require_auth),
):
    """提交任务到 Redis 队列，参数与 /chat 接口保持一致

    从 Authorization 头提取 Bearer token 并存入任务信息。
    """
    try:
        # 获取 token
        auth_header = http_request.headers.get("Authorization")
        token = None
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()

        if not token:
            raise HTTPException(status_code=400, detail="未提供 Bearer token")

        # 生成唯一任务ID
        task_id = f"task-{uuid.uuid4().hex[:8]}"
        # 构建任务负载
        request.enable_tools = True  # 强制启用工具调用
        request.sop_memory_enabled = True  # 强制启用SOP记忆
        request.itecount = 100  # 强制迭代次数为100
        request.conversation_round = 20  # 强制会话轮次为20
        task_payload = {
            **request.dict(),
            "token": token,
            "user_name": user["user_name"],
            "submitted_at": datetime.now().isoformat(),
            "task_id": task_id,
        }

        logger.info(f"提交任务: {task_payload}")

        # 推送到 Redis 队列
        redis_conn = get_redis_client()
        queue_key = "task_queue"
        redis_conn.rpush(queue_key, json.dumps(task_payload))
        logger.info(
            f"任务已提交: {task_payload['conversation_id'] or 'new'} by {user['user_name']}, task_id={task_id}"
        )

        return {
            "success": True,
            "message": "任务已提交到队列",
            "task_id": task_id,
            "conversation_id": request.conversation_id,
            "chat_id": request.chat_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"提交任务失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"提交任务失败: {str(e)}")


@app.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str, request: Request, user: dict = Depends(require_auth)
):
    """删除指定会话及其所有相关数据

    Args:
        conversation_id: 会话ID
        request: 请求对象

    Returns:
        dict: 包含操作结果的响应
    """
    try:
        user_name = user["user_name"]
        redis_conn = get_redis_client()
        conversation_key = f"conversation:{conversation_id}:info"
        conv_data = redis_conn.hgetall(conversation_key)

        if not conv_data:
            raise HTTPException(status_code=404, detail="会话不存在")

        # 将字节转换为字符串
        conv_info = {
            k.decode("utf-8") if isinstance(k, bytes) else k: (
                v.decode("utf-8") if isinstance(v, bytes) else v
            )
            for k, v in conv_data.items()
        }

        # 验证用户权限
        if conv_info.get("user_name") != user_name:
            raise HTTPException(status_code=403, detail="无权删除此会话")

        # 删除会话信息
        redis_conn.delete(conversation_key)

        # 删除会话的chat列表
        conv_chats_key = f"conversation:{conversation_id}:chats"
        redis_conn.delete(conv_chats_key)

        # 删除对话历史
        conversation_history_key = f"conversation:{conversation_id}"
        redis_conn.delete(conversation_history_key)

        # 从用户会话列表中移除
        user_conversations_key = f"user:{user_name}:conversations"
        redis_conn.zrem(user_conversations_key, conversation_id)

        logger.info(f"用户 {user_name} 删除了会话 {conversation_id}")
        return {
            "success": True,
            "message": "会话已删除",
            "conversation_id": conversation_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除会话失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除会话失败: {str(e)}")


@app.get("/conversations/{conversation_id}")
async def get_conversation_detail(
    conversation_id: str, request: Request, user: dict = Depends(require_auth)
):
    """获取指定会话的详细信息

    Args:
        conversation_id: 会话ID
        request: 请求对象

    Returns:
        dict: 包含会话详细信息的响应
    """
    try:
        user_name = user["user_name"]
        redis_conn = get_redis_client()
        conversation_key = f"conversation:{conversation_id}:info"
        conv_data = redis_conn.hgetall(conversation_key)

        if not conv_data:
            raise HTTPException(status_code=404, detail="会话不存在")

        # 将字节转换为字符串
        conv_info = {
            k.decode("utf-8") if isinstance(k, bytes) else k: (
                v.decode("utf-8") if isinstance(v, bytes) else v
            )
            for k, v in conv_data.items()
        }

        # 验证用户权限
        if conv_info.get("user_name") != user_name:
            raise HTTPException(status_code=403, detail="无权访问此会话")

        # 获取该会话的所有chat_id
        conv_chats_key = f"conversation:{conversation_id}:chats"
        chat_ids = redis_conn.lrange(conv_chats_key, 0, -1)
        conv_info["chat_ids"] = [
            chat_id.decode("utf-8") if isinstance(chat_id, bytes) else chat_id
            for chat_id in chat_ids
        ]

        return {"success": True, "conversation": conv_info}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取会话详情失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取会话详情失败: {str(e)}")


stream_manager = StreamManager.get_instance()


@app.get("/replay/stream/{chat_id}")
async def replay_stream_request(chat_id: str, user: dict = Depends(require_auth)):
    """建立SSE连接获取响应流

    Args:
        chat_id: 聊天会话ID

    Returns:
        EventSourceResponse: SSE响应
    """
    asyncio.create_task(stream_manager.replay_chat(chat_id))

    async def event_generator():
        try:
            async for message in stream_manager.get_messages(chat_id):
                yield message
        except ValueError as e:
            yield {"event": "error", "data": f"Stream not found: {str(e)}"}

    return EventSourceResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        },
    )


class StopRequest(BaseModel):
    conversation_id: str = Field(..., min_length=1, description="会话ID")
    chat_id: str = Field(..., min_length=1, description="聊天ID")


@app.post("/stop")
async def stop_chat(
    http_request: Request,
    request: StopRequest,
    user: dict = Depends(require_auth),
):
    """停止指定会话和聊天的流式响应，并向任务队列发送停止任务

    Args:
        http_request: 原始请求对象，用于提取 Authorization 头
        request: 包含 conversation_id 和 chat_id 的请求体
        user: 当前认证用户

    Returns:
        dict: 成功或失败响应
    """
    try:
        # 获取流管理器实例
        stream_manager = StreamManager.get_instance()

        # 关闭流（如果存在）
        stream_manager.close_stream(request.chat_id)

        # 清理Redis中的相关数据
        redis_conn = get_redis_client()

        # 直接写入停止标志，让正在运行的 Agent 立即感知并停止
        try:
            redis_conn.set(f"chat:{request.chat_id}:stopped", "1", ex=AGENT_STATUS_TTL)
            logger.info(f"已直接写入 Redis 停止标志: {request.chat_id}")
        except Exception as e:
            logger.error(f"写入 Redis 停止标志失败: {e}")
        blocking_key = f"chat_stream_b:{request.chat_id}"

        # 向阻塞队列发送完成事件，以便消费者正常退出
        completion_message = json.dumps(
            {"event": "complete", "data": "stopped by user"}
        )
        redis_conn.lpush(blocking_key, completion_message)

        # # 构建停止任务负载，推送到任务队列
        # auth_header = http_request.headers.get("Authorization")
        # token = None
        # if auth_header and auth_header.startswith("Bearer "):
        #     token = auth_header[7:].strip()

        # if not token:
        #     raise HTTPException(status_code=400, detail="未提供 Bearer token")

        # task_id = f"task-stop-{uuid.uuid4().hex[:8]}"
        # task_payload = {
        #     "query": "",  # 停止任务无需查询文本
        #     "modul": "chat",
        #     "model_name": None,
        #     "itecount": 100,
        #     "agentid": None,
        #     "team_name": None,
        #     "conversation_id": request.conversation_id,
        #     "conversation_round": 20,
        #     "file_ids": None,
        #     "tool_memory_enabled": False,
        #     "sop_memory_enabled": True,
        #     "enable_tools": True,
        #     "tool_choices": None,
        #     "selected_skills": None,
        #     "chat_id": request.chat_id,
        #     "task_type": "stop",
        #     "token": token,
        #     "user_name": user["user_name"],
        #     "submitted_at": datetime.now().isoformat(),
        #     "task_id": task_id,
        # }

        # # 推送到 Redis 任务队列
        # queue_key = "task_queue"
        # redis_conn.rpush(queue_key, json.dumps(task_payload))
        # logger.info(
        #     f"已向任务队列发送停止任务: conversation_id={request.conversation_id}, chat_id={request.chat_id}, task_id={task_id}"
        # )

        logger.info(
            f"已停止聊天: conversation_id={request.conversation_id}, chat_id={request.chat_id}, user={user['user_name']}"
        )

        return {
            "success": True,
            "message": "聊天已停止，停止任务已发送",
            "conversation_id": request.conversation_id,
            "chat_id": request.chat_id,
            "task_id": "",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"停止聊天失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"停止聊天失败: {str(e)}")


@app.get("/stream/blocking/{chat_id}")
async def stream_blocking_queue(chat_id: str, user: dict = Depends(require_auth)):
    """从阻塞队列中消费消息并以SSE形式发送

    Args:
        chat_id: 聊天会话ID，用于构造Redis键（chat_stream_b:{chat_id}）

    Returns:
        EventSourceResponse: SSE响应
    """
    stream_manager = StreamManager.get_instance()
    redis_key = f"chat_stream_b:{chat_id}"

    async def event_generator():
        try:
            async for message in stream_manager.consume_blocking_queue(redis_key):
                logger.info(f"SSE发送消息: {message}")
                yield message
        except asyncio.CancelledError:
            logger.info(f"SSE连接已关闭: {chat_id}")
        except Exception as e:
            logger.error(f"SSE流错误: {e}")
            yield {"event": "error", "data": str(e)}

    return EventSourceResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        },
    )
