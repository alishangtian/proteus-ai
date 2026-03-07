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
from fastapi import FastAPI, HTTPException, Request, Depends, WebSocket, WebSocketDisconnect
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


async def get_ws_user(websocket: WebSocket) -> Optional[Dict[str, Any]]:
    """从 WebSocket 握手头中验证 Bearer Token"""
    auth_header = websocket.headers.get("Authorization") or websocket.headers.get("authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    token = auth_header[7:].strip()
    if not token:
        return None
    redis_client = get_redis_client()
    token_key = get_token_key(token)
    try:
        session_data = redis_client.hgetall(token_key)
        if not session_data:
            return None
    except redis.RedisError as e:
        logger.error(f"WebSocket auth Redis 错误: {e}")
        return None
    user_name = session_data.get("user_name")
    if not user_name:
        return None
    user_key = get_user_key(user_name)
    try:
        user_data = redis_client.hgetall(user_key)
    except redis.RedisError as e:
        logger.error(f"WebSocket auth 获取用户数据失败: {e}")
        return None
    if not user_data:
        return None
    nick_name = user_data.get("nick_name", user_name)
    return {
        "user_name": user_name,
        "nick_name": nick_name,
        "expires": session_data.get("expires", ""),
    }


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


@app.websocket("/replay/stream/{chat_id}")
async def replay_stream_request(websocket: WebSocket, chat_id: str):
    """建立WebSocket连接获取回放流

    Args:
        chat_id: 聊天会话ID
    """
    # 鉴权
    user = await get_ws_user(websocket)
    if not user:
        await websocket.close(code=4001, reason="未认证")
        return

    await websocket.accept()
    # 提前创建回放流队列，避免 replay_chat 任务产生消息前 get_messages 尚未建立队列而导致消息丢失
    stream_manager.create_stream(chat_id, queue_key_prefix="replay_stream")
    asyncio.create_task(
        stream_manager.replay_chat(chat_id, queue_key_prefix="replay_stream")
    )
    try:
        async for message in stream_manager.get_messages(
            chat_id, queue_key_prefix="replay_stream"
        ):
            await websocket.send_text(json.dumps(message, ensure_ascii=False))
            if message.get("event") in ["complete", "error"]:
                break
    except WebSocketDisconnect:
        pass
    except ValueError as e:
        error_event = {"event": "error", "data": f"Stream not found: {str(e)}"}
        try:
            await websocket.send_text(json.dumps(error_event, ensure_ascii=False))
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


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


@app.websocket("/stream/blocking/{chat_id}")
async def stream_blocking_queue(websocket: WebSocket, chat_id: str):
    """通过 WebSocket 从阻塞队列中消费消息并推送

    Args:
        chat_id: 聊天会话ID，用于构造Redis键（chat_stream_b:{chat_id}）
    """
    # 鉴权
    user = await get_ws_user(websocket)
    if not user:
        await websocket.close(code=4001, reason="未认证")
        return

    await websocket.accept()
    redis_key = f"chat_stream_b:{chat_id}"
    try:
        async for message in stream_manager.consume_blocking_queue(redis_key):
            logger.info(f"WebSocket发送消息: {message}")
            await websocket.send_text(json.dumps(message, ensure_ascii=False))
            if message.get("event") in ["complete", "error"]:
                break
    except WebSocketDisconnect:
        logger.info(f"WebSocket连接已关闭: {chat_id}")
    except asyncio.CancelledError:
        logger.info(f"WebSocket流已取消: {chat_id}")
    except Exception as e:
        logger.error(f"WebSocket流错误: {e}")
        error_event = {"event": "error", "data": str(e)}
        try:
            await websocket.send_text(json.dumps(error_event, ensure_ascii=False))
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


# ==================== 知识库相关端点 ====================

# Agent 状态列表在 Redis 中的键名（与 proteus/main.py 中 AGENT_STATUS_LIST_KEY 保持一致）
AGENT_STATUS_LIST_KEY = "agents:status:list"


def _extract_kb_title(content: str) -> str:
    """从内容中提取知识库条目标题（第一行 Markdown 标题或前 50 字符）"""
    lines = content.strip().split("\n")
    title = lines[0].lstrip("#").strip() if lines else ""
    return title if title else content[:50].strip()


class KnowledgeBaseContent(BaseModel):
    content: str = Field(..., description="知识库内容（Markdown 格式）")


class KnowledgeBaseUpdate(BaseModel):
    content: str = Field(..., description="更新后的知识库内容（Markdown 格式）")
    title: Optional[str] = Field(None, description="更新后的标题")


@app.post("/knowledge_base/save")
async def save_to_knowledge_base(
    kb_content: KnowledgeBaseContent, user: dict = Depends(require_auth)
):
    """保存内容到知识库"""
    try:
        user_name = user["user_name"]
        redis_conn = get_redis_client()

        item_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        title = _extract_kb_title(kb_content.content)

        queue_item = json.dumps(
            {
                "id": item_id,
                "timestamp": now,
                "updated_at": now,
                "title": title,
                "author": user_name,
                "likes": 0,
                "dislikes": 0,
            },
            ensure_ascii=False,
        )
        map_item = json.dumps(
            {
                "id": item_id,
                "timestamp": now,
                "updated_at": now,
                "title": title,
                "author": user_name,
                "likes": 0,
                "dislikes": 0,
                "content": kb_content.content,
            },
            ensure_ascii=False,
        )

        queue_key = f"user:{user_name}:knowledge_base:queue"
        map_key = f"user:{user_name}:knowledge_base:map"

        pipe = redis_conn.pipeline()
        pipe.lpush(queue_key, queue_item)
        pipe.hset(map_key, item_id, map_item)
        pipe.execute()

        logger.info(f"用户 {user_name} 保存了知识库条目 {item_id}")
        return {"success": True, "message": "保存成功", "item_id": item_id}
    except Exception as e:
        logger.error(f"保存知识库失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"保存知识库失败: {str(e)}")


@app.get("/knowledge_base/list")
async def get_knowledge_base_list(user: dict = Depends(require_auth)):
    """获取当前用户的知识库列表"""
    try:
        user_name = user["user_name"]
        redis_conn = get_redis_client()
        queue_key = f"user:{user_name}:knowledge_base:queue"
        raw_items = redis_conn.lrange(queue_key, 0, -1)

        items = []
        for raw in raw_items:
            try:
                item = json.loads(
                    raw.decode("utf-8") if isinstance(raw, bytes) else raw
                )
                items.append(item)
            except Exception:
                continue

        return {"success": True, "knowledge_base_items": items}
    except Exception as e:
        logger.error(f"获取知识库列表失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取知识库列表失败: {str(e)}")


@app.get("/knowledge_base/item/{item_id}")
async def get_knowledge_base_item(item_id: str, user: dict = Depends(require_auth)):
    """获取指定知识库条目的完整内容"""
    try:
        user_name = user["user_name"]
        redis_conn = get_redis_client()
        map_key = f"user:{user_name}:knowledge_base:map"
        raw = redis_conn.hget(map_key, item_id)
        if not raw:
            raise HTTPException(status_code=404, detail="知识库条目不存在")

        item = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
        return {"success": True, "knowledge_base_item": item}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取知识库条目失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取知识库条目失败: {str(e)}")


@app.put("/knowledge_base/item/{item_id}")
async def update_knowledge_base_item(
    item_id: str,
    kb_update: KnowledgeBaseUpdate,
    user: dict = Depends(require_auth),
):
    """更新指定知识库条目"""
    try:
        user_name = user["user_name"]
        redis_conn = get_redis_client()
        map_key = f"user:{user_name}:knowledge_base:map"
        queue_key = f"user:{user_name}:knowledge_base:queue"

        raw = redis_conn.hget(map_key, item_id)
        if not raw:
            raise HTTPException(status_code=404, detail="知识库条目不存在")

        existing = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
        now = datetime.now().isoformat()

        new_title = kb_update.title if kb_update.title else _extract_kb_title(kb_update.content)

        existing.update(
            {
                "content": kb_update.content,
                "title": new_title,
                "updated_at": now,
            }
        )

        raw_queue = redis_conn.lrange(queue_key, 0, -1)
        new_queue = []
        for r in raw_queue:
            try:
                q_item = json.loads(r.decode("utf-8") if isinstance(r, bytes) else r)
                if q_item.get("id") == item_id:
                    q_item["title"] = new_title
                    q_item["updated_at"] = now
                new_queue.append(json.dumps(q_item, ensure_ascii=False))
            except Exception:
                # Skip malformed items rather than appending raw bytes
                logger.warning(f"跳过格式错误的知识库队列条目")
                continue

        pipe = redis_conn.pipeline()
        pipe.hset(map_key, item_id, json.dumps(existing, ensure_ascii=False))
        pipe.delete(queue_key)
        for q in new_queue:
            pipe.rpush(queue_key, q)
        pipe.execute()

        logger.info(f"用户 {user_name} 更新了知识库条目 {item_id}")
        return {"success": True, "message": "更新成功", "item_id": item_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新知识库条目失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"更新知识库条目失败: {str(e)}")


@app.delete("/knowledge_base/item/{item_id}")
async def delete_knowledge_base_item(item_id: str, user: dict = Depends(require_auth)):
    """删除指定知识库条目"""
    try:
        user_name = user["user_name"]
        redis_conn = get_redis_client()
        map_key = f"user:{user_name}:knowledge_base:map"
        queue_key = f"user:{user_name}:knowledge_base:queue"

        raw = redis_conn.hget(map_key, item_id)
        if not raw:
            raise HTTPException(status_code=404, detail="知识库条目不存在")

        raw_queue = redis_conn.lrange(queue_key, 0, -1)
        new_queue = []
        for r in raw_queue:
            try:
                q_item = json.loads(r.decode("utf-8") if isinstance(r, bytes) else r)
                if q_item.get("id") != item_id:
                    new_queue.append(json.dumps(q_item, ensure_ascii=False))
            except Exception:
                pass

        pipe = redis_conn.pipeline()
        pipe.hdel(map_key, item_id)
        pipe.delete(queue_key)
        for q in new_queue:
            pipe.rpush(queue_key, q)
        pipe.execute()

        logger.info(f"用户 {user_name} 删除了知识库条目 {item_id}")
        return {"success": True, "message": "删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除知识库条目失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除知识库条目失败: {str(e)}")


# ==================== Agent 监控相关端点 ====================


@app.get("/agents/status")
async def get_all_agents_status(
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    user: dict = Depends(require_auth),
):
    """获取所有 Agent 的运行状态（分页）

    Args:
        page: 页码，从 1 开始
        page_size: 每页数量
        status: 可选，按状态过滤（running/complete/stopped/error/init）
    """
    try:
        redis_conn = get_redis_client()
        raw_all = redis_conn.hgetall(AGENT_STATUS_LIST_KEY)

        agents = []
        for _, v in raw_all.items():
            try:
                info = json.loads(v.decode("utf-8") if isinstance(v, bytes) else v)
                agents.append(info)
            except Exception:
                continue

        if status:
            agents = [a for a in agents if a.get("status") == status]

        agents.sort(key=lambda x: x.get("updated_at", ""), reverse=True)

        total = len(agents)
        total_pages = max(1, (total + page_size - 1) // page_size)
        start = (page - 1) * page_size
        end = start + page_size
        page_agents = agents[start:end]

        return {
            "success": True,
            "data": page_agents,
            "message": f"共 {total} 条记录，第 {page}/{total_pages} 页",
        }
    except Exception as e:
        logger.error(f"获取 Agent 状态列表失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取 Agent 状态列表失败: {str(e)}")


@app.post("/agents/{agent_id}/stop")
async def stop_agent(agent_id: str, user: dict = Depends(require_auth)):
    """停止指定 Agent"""
    try:
        redis_conn = get_redis_client()
        raw = redis_conn.hget(AGENT_STATUS_LIST_KEY, agent_id)
        if not raw:
            raise HTTPException(status_code=404, detail="Agent 不存在")

        info = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
        if info.get("status") != "running":
            raise HTTPException(status_code=400, detail="Agent 未在运行中")

        chat_id = info.get("chat_id", agent_id)
        redis_conn.set(f"chat:{chat_id}:stopped", "1", ex=AGENT_STATUS_TTL)

        info["status"] = "stopped"
        info["updated_at"] = datetime.now().isoformat()
        redis_conn.hset(AGENT_STATUS_LIST_KEY, agent_id, json.dumps(info, ensure_ascii=False))

        logger.info(f"用户 {user['user_name']} 停止了 Agent {agent_id}")
        return {"success": True, "message": "Agent 已停止"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"停止 Agent 失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"停止 Agent 失败: {str(e)}")


@app.delete("/agents/{agent_id}")
async def delete_agent(agent_id: str, user: dict = Depends(require_auth)):
    """删除指定 Agent 记录"""
    try:
        redis_conn = get_redis_client()
        raw = redis_conn.hget(AGENT_STATUS_LIST_KEY, agent_id)
        if not raw:
            raise HTTPException(status_code=404, detail="Agent 不存在")

        info = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
        if info.get("status") == "running":
            raise HTTPException(status_code=400, detail="Agent 正在运行中，无法删除")

        redis_conn.hdel(AGENT_STATUS_LIST_KEY, agent_id)
        logger.info(f"用户 {user['user_name']} 删除了 Agent 记录 {agent_id}")
        return {"success": True, "message": "Agent 记录已删除"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除 Agent 记录失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除 Agent 记录失败: {str(e)}")
