"""API主模块"""

# 加载环境变量
from dotenv import load_dotenv

load_dotenv()

import os
import logging
import json
import asyncio
import yaml
import time
from datetime import datetime
from typing import Dict, Any, Optional, Union, List
from fastapi.responses import RedirectResponse
from fastapi import FastAPI, HTTPException, Request, Body, UploadFile, File
from fastapi.responses import Response
from src.utils.redis_cache import get_redis_connection  # 导入 Redis 连接
import uuid  # 导入 uuid 用于生成唯一 ID
from src.utils.file_parser import parse_file  # 导入文件解析函数
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from fastapi.responses import HTMLResponse
import shutil
from sse_starlette.sse import EventSourceResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from src.utils.logger import setup_logger
from src.agent.chat_agent import ChatAgent, AGENT_STATUS_TTL
from src.tasks.task_processor import TaskProcessor
from src.utils.langfuse_wrapper import langfuse_wrapper
from src.login.login_router import get_user_from_token

language = os.getenv("LANGUAGE", "中文")
# 设置MCP配置文件路径
os.environ["MCP_CONFIG_PATH"] = os.path.join(
    os.path.dirname(__file__), "proteus_mcp_config.json"
)

# 获取日志文件路径
log_file_path = os.getenv("LOG_FILE_PATH", "logs/workflow_engine.log")

# 配置日志
setup_logger(log_file_path)
logger = logging.getLogger(__name__)

# 创建全局流管理实例 - 必须优先初始化
from src.api.stream_manager import StreamManager

stream_manager = StreamManager.get_instance()

agent_dict = {}

agent_model_list = [
    "chat",
    "task",
    "workflow",
    "super-agent",
    "mcp-agent",
    "browser-agent",
    "deep-research",
    "deep-research-multi",
    "codeact-agent",
]


# 在启动时注册工作流节点类型 - 改为按需加载
def register_workflow_nodes(workflow_engine, node_manager):
    """注册所有可用的节点类型"""
    import importlib

    # 确保配置已加载
    logger.info("开始注册工作流节点类型")

    # 获取配置（会触发懒加载机制）
    node_configs = node_manager.get_all_nodes()

    for node_config in node_configs:
        # 获取节点配置中定义的type
        node_type = node_config.get("type")
        class_name = node_config.get("class_name", node_type)

        if not node_type:
            logger.info(f"节点配置未包含type字段，跳过注册")
            continue

        # 从type生成模块名
        module_name = node_type

        try:
            # 动态导入节点模块
            module = importlib.import_module(f"src.nodes.{module_name}")
            node_class = getattr(module, class_name)
            # 使用配置的type注册节点类型
            workflow_engine.register_node_type(node_type, node_class)
            logger.info(f"成功注册节点类型: {node_type}")
        except Exception as e:
            logger.error(f"注册节点类型 {module_name} 失败: {str(e)}")
            # 不抛出异常，继续注册其他节点
            continue

    logger.info("工作流节点类型注册完成")


app = FastAPI(title="Porteus Agent Engine API", version="1.0.0")


class AuthMiddleware:
    """认证中间件，检查用户登录状态"""

    def __init__(self, app):
        self.app = app
        self.exclude_paths = {
            "/register",  # 注册接口
            "/login",  # 登录接口
            "/health",  # 健康检查
            "/static",  # 静态文件
            "/favicon.ico",  # 网站图标
            "/update_nickname",
        }

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        request = Request(scope, receive)
        path = request.url.path

        logger.info(f"request path {path}")

        # 检查是否在排除路径中
        if any(path.startswith(p) for p in self.exclude_paths):
            return await self.app(scope, receive, send)

        # 检查登录状态
        user = await get_current_user(request)
        if not user:
            response = RedirectResponse(url="/login")
            await response(scope, receive, send)
            return

        return await self.app(scope, receive, send)


# 注册中间件
from src.login.login_router import get_current_user


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """认证中间件，检查用户登录状态（使用 FastAPI 的 http middleware 接口）"""
    exclude_paths = {
        "/register",  # 注册接口
        "/login",  # 登录接口
        "/health",  # 健康检查
        "/static",  # 静态文件
        "/favicon.ico",  # 网站图标
        "/newui",  # 新的聊天页面
        "/update_nickname",
        "/reset_password",
        "/token",  # token 获取端点
    }

    path = request.url.path
    logger.info(f"request path {path}")

    # 检查是否在排除路径中
    if any(path.startswith(p) for p in exclude_paths):
        return await call_next(request)

    # 检查登录状态（get_current_user 已支持 Bearer token）
    user = await get_current_user(request)
    if not user:
        return RedirectResponse(url="/login")

    return await call_next(request)


# 注册路由
from src.auth.router import router as l_router
from src.login.login_router import router as login_router

app.include_router(l_router)
app.include_router(login_router)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
    expose_headers=["*"],
)

# 挂载静态文件目录
static_path = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_path), name="static")

# 文件上传目录
UPLOAD_DIRECTORY = os.getenv("UPLOAD_DIRECTORY", "/app/data/uploads")
os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)  # 确保目录存在


# 显式添加login.html路由
@app.get("/login.html", response_class=HTMLResponse)
async def serve_login_page():
    """直接返回登录页面"""
    with open(os.path.join(static_path, "login.html"), "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read(), media_type="text/html")


# 创建模板引擎
templates = Jinja2Templates(directory=static_path)


@app.post("/uploadfile/")
async def create_upload_file(file: UploadFile = File(...)):
    """
    处理文件上传
    """
    try:
        # 生成唯一的文件 ID
        file_id = str(uuid.uuid4())
        # 使用文件 ID 作为存储的文件名，保留原始扩展名
        file_extension = os.path.splitext(file.filename)[1]
        stored_filename = f"{file_id}{file_extension}"
        file_location = os.path.join(UPLOAD_DIRECTORY, stored_filename)

        with open(file_location, "wb+") as file_object:
            shutil.copyfileobj(file.file, file_object)
        logger.info(
            f"文件 '{file.filename}' (存储为 '{stored_filename}') 已成功上传到 '{file_location}'"
        )

        response_data = {
            "id": file_id,
            "filename": file.filename,
            "file_type": file.content_type,
            "message": "文件上传成功",
        }

        # 调用通用文件解析函数
        file_analysis_result = await parse_file(
            file_path=file_location, file_type=file.content_type, file_id=file_id
        )
        if file_analysis_result:
            response_data["file_analysis"] = file_analysis_result
            logger.info(
                f"文件 '{file.filename}' 解析结果: {file_analysis_result[:100]}..."
            )
        else:
            response_data["file_analysis"] = None
            logger.info(
                f"文件 '{file.filename}' 类型 '{file.content_type}' 不支持解析或解析失败。"
            )

        # 将文件 ID、原始文件名、文件类型和解析结果保存到 Redis
        redis_conn = get_redis_connection()
        redis_conn.set(
            f"file_analysis:{file_id}",
            json.dumps(
                {
                    "original_filename": file.filename,
                    "stored_filename": stored_filename,
                    "file_type": file.content_type,
                    "analysis": file_analysis_result,
                },
                ensure_ascii=False,
            ),
            ex=3600,  # 缓存 1 小时
        )

        return response_data
    except Exception as e:
        logger.error(f"文件上传失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"文件上传失败: {str(e)}")


class ApiResponse(BaseModel):
    """统一的API响应模型"""

    event: str = Field(..., description="事件类型")
    success: bool = Field(..., description="操作是否成功")
    data: Optional[Union[Dict[str, Any], str, list]] = Field(
        None, description="响应数据"
    )
    error: Optional[str] = Field(None, description="错误信息")


class WorkflowRequest(BaseModel):
    workflow: Dict[str, Any] = Field(
        ...,
        description="工作流定义，包含nodes和edges",
        example={
            "nodes": [
                {"id": "add1", "type": "add", "params": {"num1": 10, "num2": 20}}
            ],
            "edges": [],
        },
    )
    global_params: Optional[Dict[str, Any]] = Field(
        None, description="全局参数，可在所有节点中访问"
    )


class NodeResultResponse(BaseModel):
    success: bool = Field(..., description="节点执行是否成功")
    data: Optional[Dict[str, Any]] = Field(None, description="节点执行结果数据")
    error: Optional[str] = Field(None, description="错误信息（如果执行失败）")


@app.get("/health", response_model=ApiResponse)
async def health_check():
    """健康检查接口"""
    logger.debug("收到健康检查请求")
    return ApiResponse(event="health_check", success=True, data={"status": "healthy"})


@app.delete("/deletefile/{file_id}")
async def delete_upload_file(file_id: str):
    """
    处理文件删除
    """
    redis_conn = get_redis_connection()
    file_data_str = redis_conn.get(f"file_analysis:{file_id}")

    if not file_data_str:
        raise HTTPException(status_code=404, detail="文件 ID 未找到或已过期")

    file_data = json.loads(file_data_str)
    original_filename = file_data.get("original_filename")
    stored_filename = file_data.get("stored_filename")

    if not stored_filename:
        raise HTTPException(status_code=500, detail="无法从 Redis 获取存储文件名")

    file_location = os.path.join(UPLOAD_DIRECTORY, stored_filename)
    if not os.path.exists(file_location):
        # 如果文件不存在，但 Redis 中有记录，则只删除 Redis 记录
        redis_conn.delete(f"file_analysis:{file_id}")
        logger.warning(
            f"文件 '{original_filename}' (存储为 '{stored_filename}') 不存在，但 Redis 中有记录，已删除 Redis 记录"
        )
        return {
            "id": file_id,
            "filename": original_filename,
            "message": "文件已从 Redis 删除，本地文件不存在",
        }

    try:
        os.remove(file_location)
        redis_conn.delete(f"file_analysis:{file_id}")  # 同时删除 Redis 记录
        logger.info(f"文件 '{original_filename}' (ID: {file_id}) 已成功删除")
        return {"id": file_id, "filename": original_filename, "message": "文件删除成功"}
    except Exception as e:
        logger.error(
            f"文件删除失败 (ID: {file_id}, 文件名: {original_filename}): {str(e)}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"文件删除失败: {str(e)}")


@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    """返回交互页面"""
    user = await get_current_user(request)
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "logged_in": user is not None,
            "user_name": user.user_name if user else "",
            "nick_name": user.nick_name if user else "",
        },
    )


@app.get("/agent-page", response_class=HTMLResponse)
async def get_agent_page(request: Request):
    """返回agent交互页面"""
    return templates.TemplateResponse("agent/agent.html", {"request": request})


@app.get("/super-agent", response_class=HTMLResponse)
async def get_super_agent_page(request: Request):
    """返回super-agent交互页面"""
    return templates.TemplateResponse("superagent/index.html", {"request": request})


@app.get("/newui", response_class=HTMLResponse)
async def get_newui_page(request: Request):
    """返回新的聊天页面"""
    user = await get_current_user(request)
    return templates.TemplateResponse(
        "newui.html",
        {
            "request": request,
            "logged_in": user is not None,
            "user_name": user.user_name if user else "",
            "nick_name": user.nick_name if user else "",
        },
    )


@app.get("/chat/index", response_class=HTMLResponse)
async def get_chat_index_page(request: Request):
    """返回聊天页面索引"""
    user = await get_current_user(request)
    return templates.TemplateResponse(
        "chat.html",
        {
            "request": request,
            "logged_in": user is not None,
            "user_name": user.user_name if user else "",
            "nick_name": user.nick_name if user else "",
        },
    )


@app.get("/knowledge/index", response_class=HTMLResponse)
async def get_knowledge_index_page(request: Request):
    """返回知识库页面索引"""
    user = await get_current_user(request)
    return templates.TemplateResponse(
        "knowledge_base.html",
        {
            "request": request,
            "logged_in": user is not None,
            "user_name": user.user_name if user else "",
            "nick_name": user.nick_name if user else "",
        },
    )


@app.get("/knowledge-base", response_class=HTMLResponse)
async def get_knowledge_base_page(request: Request):
    """返回知识库页面"""
    user = await get_current_user(request)
    return templates.TemplateResponse(
        "knowledge_base.html",
        {
            "request": request,
            "logged_in": user is not None,
            "user_name": user.user_name if user else "",
            "nick_name": user.nick_name if user else "",
        },
    )


@langfuse_wrapper.dynamic_observe(
    name="create_chat",
    capture_input=True,
    capture_output=True,
)
@app.post("/chat")
async def create_chat(
    request: Request,
    query: str = Body(..., embed=True),
    modul: str = Body(..., embed=True),
    model_name: str = Body(None, embed=True),
    itecount: int = Body(5, embed=True),
    agentid: str = Body(None, embed=True),
    team_name: str = Body(None, embed=True),
    conversation_id: str = Body(None, embed=True),
    conversation_round: int = Body(5, embed=True),
    file_ids: Optional[List[str]] = Body(None, embed=True),  # 新增文件 ID 列表参数
    tool_memory_enabled: bool = Body(False, embed=True),  # 新增工具记忆参数
    sop_memory_enabled: bool = Body(False, embed=True),  # 新增工具记忆参数
    enable_tools: bool = Body(False, embed=True),  # 新增工具调用开关
    tool_choices: Optional[List[str]] = Body(None, embed=True),  # 新增工具选择参数
    selected_skills: Optional[List[str]] = Body(None, embed=True),  # 用户选中的技能列表
):
    """创建新的聊天会话

    Args:
        text: 用户输入的文本
        model: 模型类型
        itecount: 迭代次数(默认5)
        agentid: 代理ID(可选)

    Returns:
        dict: 包含chat_id的响应
    """
    # 获取当前登录用户
    user = await get_current_user(request)
    logger.info(f"用户 {user} 创建新的会话")
    user_name = user.user_name if user else None

    chat_id = f"chat-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    stream_manager.create_stream(chat_id, query)

    # 保存 conversation_id 和 chat_id 的关系到 Redis
    if conversation_id:
        redis_conn = get_redis_connection()
        # 使用 List 存储一个 conversation_id 对应的多个 chat_id
        conv_chats_key = f"conversation:{conversation_id}:chats"
        redis_conn.rpush(conv_chats_key, chat_id)
        # redis_conn.expire(conv_chats_key, 7 * 24 * 3600)  # 7天过期

        # 保存反向映射关系
        redis_conn.set(f"chat:{chat_id}:conversation", conversation_id, ex=None)

        # 异步保存会话摘要信息
        asyncio.create_task(
            save_conversation_summary(
                conversation_id=conversation_id,
                chat_id=chat_id,
                initial_question=query,
                user_name=user_name,
                modul=modul,
            )
        )

    # 工具选择列表：如果参数为空则使用默认值
    if tool_choices is None:
        tool_choices = ["serper_search", "web_crawler", "python_execute"]
        if sop_memory_enabled:
            tool_choices.append("skills_extract")
    else:
        # 如果参数已提供，则直接使用，但仍可根据 sop_memory_enabled 添加 skills_extract
        if sop_memory_enabled and "skills_extract" not in tool_choices:
            tool_choices.append("skills_extract")

    if modul in agent_model_list:
        # 启动智能体异步任务处理用户请求，传入 model_name（可能为 None）
        asyncio.create_task(
            process_agent(
                chat_id,
                query,
                itecount,
                agentid,
                agentmodul=modul,
                team_name=team_name,
                conversation_id=conversation_id,
                model_name=model_name,
                conversation_round=conversation_round,
                file_ids=file_ids,  # 传递文件 ID 列表
                user_name=user_name,  # 传递用户名
                tool_memory_enabled=tool_memory_enabled,  # 传递工具记忆参数
                sop_memory_enabled=sop_memory_enabled,  # 传递SOP记忆参数
                enable_tools=enable_tools,  # 传递工具调用开关
                tool_choices=tool_choices,  # 传递工具选择参数
                selected_skills=selected_skills,  # 传递用户选中的技能列表
            )
        )
    else:
        raise HTTPException(status_code=400, detail="Invalid model type")

    return {"success": True, "chat_id": chat_id}


@app.get("/stop/{model}/{chat_id}")
async def stop_chat(model: str, chat_id: str):
    try:
        redis_conn = get_redis_connection()
        redis_conn.set(f"chat:{chat_id}:stopped", "1", ex=AGENT_STATUS_TTL)
        logger.info(f"[{chat_id}] 已直接写入 Redis 停止标志")
    except Exception as e:
        logger.error(f"[{chat_id}] 写入 Redis 停止标志失败: {e}")
    stream_manager.close_stream(chat_id)
    return {"success": True, "chat_id": chat_id}


@app.get("/stream/{chat_id}")
async def stream_request(chat_id: str):
    """建立SSE连接获取响应流

    Args:
        chat_id: 聊天会话ID

    Returns:
        EventSourceResponse: SSE响应
    """

    async def event_generator():
        try:
            async for message in stream_manager.get_messages(chat_id):
                yield message
        except ValueError as e:
            from src.api.events import create_error_event

            yield await create_error_event(f"Stream not found: {str(e)}")

    return EventSourceResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用Nginx缓冲
            "Access-Control-Allow-Origin": "*",  # 如果是跨域
        },
    )


@app.get("/replay/stream/{chat_id}")
async def replay_stream_request(chat_id: str):
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
                # await asyncio.sleep(0.1)  # 小延迟减少CPU使用
        except ValueError as e:
            from src.api.events import create_error_event

            yield await create_error_event(f"Stream not found: {str(e)}")

    return EventSourceResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用Nginx缓冲
            "Access-Control-Allow-Origin": "*",  # 如果是跨域
        },
    )


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


@langfuse_wrapper.dynamic_observe()
async def save_conversation_summary(
    conversation_id: str,
    chat_id: str,
    initial_question: str,
    user_name: str = None,
    modul: str = None,
    final_result: str = None,  # 新增 final_result 参数
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
    processor = TaskProcessor()
    await processor._save_conversation_summary(
        conversation_id=conversation_id,
        chat_id=chat_id,
        initial_question=initial_question,
        user_name=user_name,
        modul=modul,
        final_result=final_result,
    )


@langfuse_wrapper.dynamic_observe()
async def process_agent(
    chat_id: str,
    query: str,
    itecount: int,
    agentid: str = None,
    agentmodul: str = None,
    team_name: str = None,
    conversation_id: str = None,
    model_name: str = None,
    conversation_round: int = 5,
    file_ids: Optional[List[str]] = None,  # 新增文件 ID 列表参数
    user_name: str = None,  # 新增用户名参数
    tool_memory_enabled: bool = False,  # 新增工具记忆参数
    sop_memory_enabled: bool = False,  # 新增 SOP 记忆参数
    enable_tools: bool = False,  # 新增工具调用开关
    tool_choices: Optional[List[str]] = None,  # 新增工具选择参数
    selected_skills: Optional[List[str]] = None,  # 用户选中的技能列表
    workspace_path: Optional[str] = None,  # 新增工作目录路径参数
):
    """处理Agent请求的异步函数

    Args:
        chat_id: 聊天会话ID
        text: 用户输入的文本
        itecount: 迭代次数
        agentid: 代理ID(可选)
        agentmodel: 代理模型(可选)
        user_name: 用户名(可选)，用于工具记忆隔离
    """
    processor = TaskProcessor()
    return await processor.process(
        chat_id=chat_id,
        query=query,
        itecount=itecount,
        agentid=agentid,
        agentmodul=agentmodul,
        team_name=team_name,
        conversation_id=conversation_id,
        model_name=model_name,
        conversation_round=conversation_round,
        file_ids=file_ids,
        user_name=user_name,
        tool_memory_enabled=tool_memory_enabled,
        sop_memory_enabled=sop_memory_enabled,
        enable_tools=enable_tools,
        tool_choices=tool_choices,
        selected_skills=selected_skills,
        workspace_path=workspace_path,
    )


@app.on_event("startup")
async def start_task_consumer():
    """启动任务消费者，从Redis队列中获取任务并异步处理"""
    logger.info("启动任务消费者...")
    asyncio.create_task(consume_tasks())


@langfuse_wrapper.dynamic_observe()
async def consume_tasks():
    """持续消费Redis队列中的任务"""
    from src.utils.redis_cache import get_redis_connection
    import json
    import asyncio

    redis_conn = get_redis_connection()
    queue_key = "task_queue"
    logger.info(f"开始监听队列: {queue_key}")
    while True:
        try:
            # 阻塞式获取任务，使用异步线程避免阻塞事件循环
            item = await asyncio.to_thread(redis_conn.blpop, queue_key, timeout=1)
            if item is None:
                continue
            _, task_json = item
            task_data = json.loads(task_json)
            logger.info(f"接收到任务: {task_data.get('task_id', 'unknown')}")
            # 异步执行任务处理
            asyncio.create_task(process_task(task_data))
        except Exception as e:
            logger.error(f"消费任务时发生错误: {e}", exc_info=True)
            await asyncio.sleep(1)


@langfuse_wrapper.dynamic_observe()
async def process_task(task_data: dict):
    """处理单个任务，调用 TaskProcessor"""
    try:
        # 提取任务类型
        task_type = task_data.get("task_type", "start")

        # 如果是停止任务，则执行停止逻辑
        if task_type == "stop":
            chat_id = task_data.get("chat_id")
            if not chat_id:
                logger.error("停止任务缺少 chat_id")
                return
            # token 验证（可选，但建议保留）
            token = task_data.get("token")
            if token:
                token_user = await get_user_from_token(token)
                if token_user is None:
                    logger.error(f"token 验证失败: {token[:10]}...")
                    raise ValueError("token 验证不通过")
                logger.info(f"从 token 中获取用户: {token_user}")
            try:
                redis_conn = get_redis_connection()
                redis_conn.set(f"chat:{chat_id}:stopped", "1", ex=AGENT_STATUS_TTL)
                logger.info(f"已直接写入 Redis 停止标志: {chat_id}")
            except Exception as e:
                logger.error(f"写入 Redis 停止标志失败: {e}")
            # 停止任务处理完毕，无需继续执行
            return

        # 以下是原有的开始任务处理逻辑
        # 提取任务参数
        task_id = task_data.get("task_id")
        query = task_data.get("query")
        modul = task_data.get("modul", "chat")
        model_name = task_data.get("model_name")
        itecount = task_data.get("itecount", 100)
        agentid = task_data.get("agentid")
        team_name = task_data.get("team_name")
        conversation_id = task_data.get("conversation_id")
        conversation_round = task_data.get("conversation_round", 20)
        file_ids = task_data.get("file_ids")
        user_name = task_data.get("user_name")
        tool_memory_enabled = task_data.get("tool_memory_enabled", False)
        sop_memory_enabled = task_data.get("sop_memory_enabled", True)
        enable_tools = task_data.get("enable_tools", True)
        tool_choices = task_data.get("tool_choices")
        selected_skills = task_data.get("selected_skills")
        token = task_data.get("token")  # 可能需要用于认证
        # token 验证
        if token:
            token_user = await get_user_from_token(token)
            if token_user is None:
                logger.error(f"token 验证失败: {token[:10]}...")
                raise ValueError("token 验证不通过")
            # 使用 token 中的用户信息覆盖 user_name
            user_name = token_user
            logger.info(f"从 token 中获取用户: {user_name}")
        else:
            # 如果没有提供 token，检查 user_name 是否存在
            raise ValueError("token 验证不通过")
        # 获取 chat_id，如果不存在则生成新的
        from datetime import datetime

        chat_id = task_data.get("chat_id")
        if not chat_id:
            chat_id = f"chat-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            logger.warning(f"任务中未提供 chat_id，使用生成的 chat_id: {chat_id}")

        # 保存 conversation_id 和 chat_id 的关系到 Redis（类似 /chat 接口中的逻辑）
        if conversation_id:
            redis_conn = get_redis_connection()
            # 使用 List 存储一个 conversation_id 对应的多个 chat_id
            conv_chats_key = f"conversation:{conversation_id}:chats"
            redis_conn.rpush(conv_chats_key, chat_id)
            # redis_conn.expire(conv_chats_key, 7 * 24 * 3600)  # 7天过期

            # 保存反向映射关系
            redis_conn.set(f"chat:{chat_id}:conversation", conversation_id, ex=None)

            # 标记 chat 为运行中状态
            redis_conn.set(f"chat:{chat_id}:status", "running", ex=AGENT_STATUS_TTL)

            # 异步保存会话摘要信息
            asyncio.create_task(
                save_conversation_summary(
                    conversation_id=conversation_id,
                    chat_id=chat_id,
                    initial_question=query,
                    user_name=user_name,
                    modul=modul,
                )
            )

        if tool_choices is None:
            tool_choices = ["serper_search", "web_crawler", "python_execute"]
            if sop_memory_enabled:
                tool_choices.append("skills_extract")
        else:
            if sop_memory_enabled and "skills_extract" not in tool_choices:
                tool_choices.append("skills_extract")

        # 调用 TaskProcessor
        processor = TaskProcessor()
        await processor.process(
            chat_id=chat_id,
            query=query,
            itecount=itecount,
            agentid=agentid,
            agentmodul=modul,
            team_name=team_name,
            conversation_id=conversation_id,
            model_name=model_name,
            conversation_round=conversation_round,
            file_ids=file_ids,
            user_name=user_name,
            tool_memory_enabled=tool_memory_enabled,
            sop_memory_enabled=sop_memory_enabled,
            enable_tools=enable_tools,
            tool_choices=tool_choices,
            selected_skills=selected_skills,
            workspace_path=None,
        )
        logger.info(f"任务处理完成: {task_id}")
    except Exception as e:
        logger.error(f"处理任务失败: {task_id}, 错误: {e}", exc_info=True)


# 提供模型配置列表接口，供前端下拉使用
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


@app.post("/feedback/{conversation_id}/{chat_id}/{feedback_type}")
async def submit_feedback(
    chat_id: str, conversation_id: str, feedback_type: str, request: Request
):
    """
    处理用户对会话的点赞/点踩反馈
    """
    user = await get_current_user(request)
    user_name = user.user_name if user else "anonymous"

    if feedback_type not in ["like", "dislike"]:
        raise HTTPException(status_code=400, detail="无效的反馈类型")

    try:
        redis_conn = get_redis_connection()
        feedback_key = f"feedback:{conversation_id}:{chat_id}"

        # 存储反馈信息
        feedback_data = {
            "chat_id": chat_id,
            "conversation_id": conversation_id,
            "feedback_type": feedback_type,
            "user_name": user_name,
            "timestamp": datetime.now().isoformat(),
        }

        # 将反馈数据存储到 Redis，可以设置一个过期时间，例如 7 天
        redis_conn.setex(
            feedback_key, 7 * 24 * 3600, json.dumps(feedback_data, ensure_ascii=False)
        )

        logger.info(
            f"用户 {user_name} 对会话 {conversation_id} (chat_id: {chat_id}) 提交了 {feedback_type} 反馈"
        )
        return {"success": True, "message": "反馈提交成功"}
    except Exception as e:
        logger.error(
            f"提交反馈失败 (chat_id: {chat_id}, conversation_id: {conversation_id}, feedback_type: {feedback_type}): {str(e)}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"提交反馈失败: {str(e)}")


@app.get("/conversations")
async def get_conversations(request: Request, limit: int = 50):
    """获取当前用户的会话列表

    Args:
        request: 请求对象
        limit: 返回的会话数量限制（默认50）

    Returns:
        dict: 包含会话列表的响应
    """
    try:
        user = await get_current_user(request)
        user_name = user.user_name if user else "anonymous"

        redis_conn = get_redis_connection()
        user_conversations_key = f"user:{user_name}:conversations"

        # 从有序集合中获取会话ID列表（按时间倒序）
        conversation_ids = redis_conn.zrevrange(user_conversations_key, 0, limit - 1)

        conversations = []
        if not conversation_ids:
            return {"success": True, "conversations": conversations}

        # 使用 pipeline 批量获取会话信息、chat 数量和最新 chat 状态
        pipe = redis_conn.pipeline()
        for conv_id in conversation_ids:
            conv_id_str = (
                conv_id.decode("utf-8") if isinstance(conv_id, bytes) else conv_id
            )
            pipe.hgetall(f"conversation:{conv_id_str}:info")
            pipe.llen(f"conversation:{conv_id_str}:chats")
            pipe.lrange(f"conversation:{conv_id_str}:chats", -1, -1)
        results = pipe.execute()

        # 收集需要查询状态的 chat_id
        chat_status_queries = []
        for i, conv_id in enumerate(conversation_ids):
            last_chat_ids = results[i * 3 + 2]
            if last_chat_ids:
                last_chat_id = (
                    last_chat_ids[0].decode("utf-8")
                    if isinstance(last_chat_ids[0], bytes)
                    else last_chat_ids[0]
                )
                chat_status_queries.append(last_chat_id)
            else:
                chat_status_queries.append(None)

        # 批量获取 chat 状态
        status_pipe = redis_conn.pipeline()
        has_chat_status = []
        for chat_id_val in chat_status_queries:
            if chat_id_val:
                status_pipe.get(f"chat:{chat_id_val}:status")
                has_chat_status.append(True)
            else:
                has_chat_status.append(False)
        status_results_raw = status_pipe.execute() if any(has_chat_status) else []

        # 将 pipeline 结果按索引还原（无 chat_id 的位置补 None）
        status_results = []
        status_iter = iter(status_results_raw)
        for has in has_chat_status:
            if has:
                status_results.append(next(status_iter))
            else:
                status_results.append(None)

        for i, conv_id in enumerate(conversation_ids):
            conv_data = results[i * 3]
            chat_count = results[i * 3 + 1]

            if conv_data:
                # 将字节转换为字符串
                conv_info = {
                    k.decode("utf-8") if isinstance(k, bytes) else k: (
                        v.decode("utf-8") if isinstance(v, bytes) else v
                    )
                    for k, v in conv_data.items()
                }
                conv_info["chat_count"] = chat_count

                # 从批量查询结果中获取 chat 状态
                chat_status = status_results[i]
                if isinstance(chat_status, bytes):
                    chat_status = chat_status.decode("utf-8")
                conv_info["is_running"] = chat_status == "running"

                conversations.append(conv_info)

        return {"success": True, "conversations": conversations}

    except Exception as e:
        logger.error(f"获取会话列表失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取会话列表失败: {str(e)}")


@app.get("/conversations/{conversation_id}")
async def get_conversation_detail(conversation_id: str, request: Request):
    """获取指定会话的详细信息

    Args:
        conversation_id: 会话ID
        request: 请求对象

    Returns:
        dict: 包含会话详细信息的响应
    """
    try:
        user = await get_current_user(request)
        user_name = user.user_name if user else "anonymous"

        redis_conn = get_redis_connection()
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


@app.put("/conversations/{conversation_id}/title")
async def update_conversation_title(
    conversation_id: str, request: Request, title: str = Body(..., embed=True)
):
    """更新会话标题

    Args:
        conversation_id: 会话ID
        request: 请求对象
        title: 新的标题

    Returns:
        dict: 更新结果
    """
    try:
        user = await get_current_user(request)
        user_name = user.user_name if user else "anonymous"

        redis_conn = get_redis_connection()
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
            raise HTTPException(status_code=403, detail="无权修改此会话")

        # 更新会话标题和更新时间
        redis_conn.hset(conversation_key, "title", title)
        redis_conn.hset(conversation_key, "updated_at", datetime.now().isoformat())

        # 更新用户在有序集合中的时间戳，确保按更新时间排序
        user_conversations_key = f"user:{user_name}:conversations"
        timestamp = time.time()
        redis_conn.zadd(user_conversations_key, {conversation_id: timestamp})

        logger.info(f"用户 {user_name} 更新了会话标题: {conversation_id} -> {title}")
        return {"success": True, "message": "会话标题已更新", "title": title}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新会话标题失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"更新会话标题失败: {str(e)}")


@app.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, request: Request):
    """删除指定会话

    Args:
        conversation_id: 会话ID
        request: 请求对象

    Returns:
        dict: 删除结果
    """
    try:
        user = await get_current_user(request)
        user_name = user.user_name if user else "anonymous"

        redis_conn = get_redis_connection()
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

        # 从用户会话列表中移除
        user_conversations_key = f"user:{user_name}:conversations"
        redis_conn.zrem(user_conversations_key, conversation_id)

        logger.info(f"用户 {user_name} 删除了会话 {conversation_id}")
        return {"success": True, "message": "会话已删除"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除会话失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除会话失败: {str(e)}")


@app.get("/app/data/{file_path:path}")
async def get_sandbox_file(file_path: str, request: Request):
    """
    获取 sandbox 目录下的静态页面文件

    Args:
        file_path: 文件路径，相对于 /app/data/ 目录
        request: 请求对象

    Returns:
        文件内容或错误响应
    """
    try:
        base_dir = os.getenv("SANDBOX_DATA_DIR")
        # 构建完整的文件路径
        full_path = os.path.join(base_dir, file_path)

        # 安全检查：确保请求的文件路径在基础目录内
        full_path = os.path.normpath(full_path)
        if not full_path.startswith(os.path.normpath(base_dir)):
            raise HTTPException(status_code=403, detail="禁止访问该路径")

        # 如果请求的是目录，默认返回 index.html
        if os.path.isdir(full_path):
            full_path = os.path.join(full_path, "index.html")

        # 检查文件是否存在
        if not os.path.exists(full_path):
            raise HTTPException(status_code=404, detail=f"文件不存在: {file_path}")

        # 检查是否为文件
        if not os.path.isfile(full_path):
            raise HTTPException(status_code=400, detail="请求的路径不是文件")

        # 根据文件扩展名确定媒体类型
        file_extension = os.path.splitext(full_path)[1].lower()
        media_types = {
            ".html": "text/html",
            ".htm": "text/html",
            ".css": "text/css",
            ".js": "application/javascript",
            ".json": "application/json",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".svg": "image/svg+xml",
            ".txt": "text/plain",
            ".pdf": "application/pdf",
            ".ico": "image/x-icon",
            ".xml": "application/xml",
            ".zip": "application/zip",
            ".mp4": "video/mp4",
            ".mp3": "audio/mpeg",
            ".woff": "font/woff",
            ".woff2": "font/woff2",
            ".ttf": "font/ttf",
        }

        media_type = media_types.get(file_extension, "application/octet-stream")

        # 判断是否为文本文件
        text_extensions = {
            ".html",
            ".htm",
            ".css",
            ".js",
            ".json",
            ".txt",
            ".xml",
            ".svg",
        }
        if file_extension in text_extensions:
            # 读取文本文件
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
            response = Response(content=content, media_type=media_type)
        else:
            # 读取二进制文件
            with open(full_path, "rb") as f:
                content = f.read()
            response = Response(content=content, media_type=media_type)

        # 添加缓存头
        response.headers["Cache-Control"] = "public, max-age=3600"  # 缓存1小时

        logger.info(f"成功返回 sandbox 文件: {file_path} (类型: {media_type})")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取 sandbox 文件失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取文件失败: {str(e)}")


class KnowledgeBaseContent(BaseModel):
    content: str = Field(..., description="要保存到知识库的内容")


@app.post("/knowledge_base/save")
async def save_to_knowledge_base(request: Request, kb_content: KnowledgeBaseContent):
    """
    将内容保存到当前用户的知识库中。
    新的数据结构：
    - 队列（list）保存事件和标题
    - map（hash）保存正文内容
    """
    try:
        user = await get_current_user(request)
        user_name = user.user_name if user else "anonymous"
        nick_name = user.nick_name if user else "匿名用户"  # 获取用户昵称

        redis_conn = get_redis_connection()

        # 导入标题提取工具
        from src.utils.md_title_extractor import (
            extract_title_from_md,
            remove_title_from_content,
        )

        # 提取标题
        title = extract_title_from_md(kb_content.content)
        timestamp = datetime.now().isoformat()

        # 直接从内容中删除标题行，避免重复
        cleaned_content = remove_title_from_content(kb_content.content)

        # 生成唯一ID
        import uuid

        item_id = str(uuid.uuid4())

        # 队列键：保存事件和标题
        knowledge_base_queue_key = f"user:{user_name}:knowledge_base:queue"

        # 映射键：保存正文内容
        knowledge_base_map_key = f"user:{user_name}:knowledge_base:map"

        # 队列条目：包含时间、标题和ID
        queue_item = {
            "id": item_id,
            "timestamp": timestamp,
            "title": title,
            "author": user_name,  # 存储用户名
            "updated_at": timestamp,  # 新增更新时间字段，初始值与创建时间相同
            "likes": 0,
            "dislikes": 0,
        }

        # 映射条目：包含完整内容
        map_item = {
            "id": item_id,
            "timestamp": timestamp,
            "title": title,
            "content": cleaned_content,  # 使用清理后的内容（已移除标题行）
            "author": user_name,  # 存储用户名
            "updated_at": timestamp,  # 新增更新时间字段，初始值与创建时间相同
            "likes": 0,
            "dislikes": 0,
        }

        # 使用pipeline确保原子性操作
        pipeline = redis_conn.pipeline()

        # 将队列条目添加到列表左侧（实现倒序排列）
        pipeline.lpush(
            knowledge_base_queue_key, json.dumps(queue_item, ensure_ascii=False)
        )

        # 将映射条目保存到hash中
        pipeline.hset(
            knowledge_base_map_key, item_id, json.dumps(map_item, ensure_ascii=False)
        )

        # 执行pipeline
        pipeline.execute()

        logger.info(
            f"用户 {user_name} 已将内容保存到知识库。标题: {title}, ID: {item_id}"
        )
        return {
            "success": True,
            "message": "内容已成功保存到知识库。",
            "item_id": item_id,
        }
    except Exception as e:
        logger.error(f"保存知识库失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"保存知识库失败: {str(e)}")


@app.get("/knowledge_base/list")
async def get_knowledge_base_list(request: Request):
    """
    获取当前用户的知识库列表。
    新的数据结构：
    - 从队列获取事件和标题列表
    - 不包含正文内容以提高性能
    - 在查询时返回创建人昵称而不是用户名
    """
    try:
        user = await get_current_user(request)
        user_name = user.user_name if user else "anonymous"
        nick_name = user.nick_name if user else "匿名用户"  # 获取当前用户昵称

        redis_conn = get_redis_connection()
        knowledge_base_queue_key = f"user:{user_name}:knowledge_base:queue"

        # 获取 Redis 队列中所有内容
        kb_items_raw = redis_conn.lrange(knowledge_base_queue_key, 0, -1)

        kb_items = []
        for item_raw in kb_items_raw:
            try:
                item_data = json.loads(item_raw)
                # 在查询时将作者信息替换为昵称
                item_data["author"] = nick_name
                kb_items.append(item_data)
            except json.JSONDecodeError:
                logger.warning(f"解析知识库条目失败: {item_raw}")
                continue

        return {"success": True, "knowledge_base_items": kb_items}
    except Exception as e:
        logger.error(f"获取知识库列表失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取知识库列表失败: {str(e)}")


@app.get("/knowledge_base/item/{item_id}")
async def get_knowledge_base_item(request: Request, item_id: str):
    """
    获取知识库中指定ID的条目完整内容。
    新的数据结构：从映射中获取包含正文的完整内容。
    """
    try:
        user = await get_current_user(request)
        user_name = user.user_name if user else "anonymous"

        redis_conn = get_redis_connection()
        knowledge_base_map_key = f"user:{user_name}:knowledge_base:map"

        # 从映射中获取指定ID的知识库条目
        item_raw = redis_conn.hget(knowledge_base_map_key, item_id)

        if not item_raw:
            raise HTTPException(status_code=404, detail="知识库条目不存在")

        item_data = json.loads(item_raw)

        # 获取用户对该条目的投票
        user_vote_key = f"knowledge_base_vote:{item_id}:{user_name}"
        user_vote = redis_conn.get(user_vote_key)
        if user_vote:
            # 映射后端投票值到前端值
            vote_map = {"like": "up", "dislike": "down"}
            item_data["user_vote"] = vote_map.get(user_vote, None)
        else:
            item_data["user_vote"] = None

        return {"success": True, "knowledge_base_item": item_data}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"获取知识库条目失败 (item_id: {item_id}): {str(e)}", exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"获取知识库条目失败: {str(e)}")


class KnowledgeBaseUpdate(BaseModel):
    title: str = Field(..., description="知识库条目标题")
    content: str = Field(..., description="知识库条目内容")


@app.put("/knowledge_base/item/{item_id}")
async def update_knowledge_base_item(
    request: Request, item_id: str, kb_update: KnowledgeBaseUpdate
):
    """
    更新知识库中指定ID的条目。
    """
    try:
        user = await get_current_user(request)
        user_name = user.user_name if user else "anonymous"
        nick_name = user.nick_name if user else "匿名用户"  # 获取用户昵称

        redis_conn = get_redis_connection()
        knowledge_base_queue_key = f"user:{user_name}:knowledge_base:queue"
        knowledge_base_map_key = f"user:{user_name}:knowledge_base:map"

        # 检查条目是否存在
        existing_item_raw = redis_conn.hget(knowledge_base_map_key, item_id)
        if not existing_item_raw:
            raise HTTPException(status_code=404, detail="知识库条目不存在")

        # 更新映射中的内容
        update_timestamp = datetime.now().isoformat()
        # 保留原有的timestamp（创建时间），只更新updated_at
        existing_item = json.loads(existing_item_raw)
        original_timestamp = existing_item.get("timestamp", update_timestamp)

        map_item = {
            "id": item_id,
            "timestamp": original_timestamp,  # 保持原有的创建时间不变
            "title": kb_update.title,
            "content": kb_update.content,
            "author": user_name,  # 存储用户名
            "nick_name": nick_name,
            "updated_at": update_timestamp,  # 更新时设置新的更新时间
            "likes": existing_item.get("likes", 0),
            "dislikes": existing_item.get("dislikes", 0),
        }

        # 更新队列中的条目信息
        queue_items_raw = redis_conn.lrange(knowledge_base_queue_key, 0, -1)
        updated_queue_items = []

        for item_raw in queue_items_raw:
            try:
                item_data = json.loads(item_raw)
                if item_data.get("id") == item_id:
                    # 更新匹配的条目，保持原有的timestamp（创建时间）不变
                    item_data["title"] = kb_update.title
                    # timestamp保持不变，不更新创建时间
                    item_data["updated_at"] = (
                        update_timestamp  # 更新队列中的更新时间字段
                    )
                updated_queue_items.append(json.dumps(item_data, ensure_ascii=False))
            except json.JSONDecodeError:
                logger.warning(f"解析知识库队列条目失败: {item_raw}")
                updated_queue_items.append(item_raw)  # 保持原样

        # 使用pipeline确保原子性操作
        pipeline = redis_conn.pipeline()

        # 更新映射中的内容
        pipeline.hset(
            knowledge_base_map_key, item_id, json.dumps(map_item, ensure_ascii=False)
        )

        # 重新设置队列（先删除再重新添加）
        pipeline.delete(knowledge_base_queue_key)
        if updated_queue_items:
            pipeline.rpush(knowledge_base_queue_key, *updated_queue_items)

        # 执行pipeline
        pipeline.execute()

        logger.info(
            f"用户 {user_name} 已更新知识库条目。标题: {kb_update.title}, ID: {item_id}"
        )
        return {"success": True, "message": "知识库条目已成功更新", "item_id": item_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"更新知识库条目失败 (item_id: {item_id}): {str(e)}", exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"更新知识库条目失败: {str(e)}")


@app.delete("/knowledge_base/item/{item_id}")
async def delete_knowledge_base_item(request: Request, item_id: str):
    """
    删除知识库中指定ID的条目。
    """
    try:
        user = await get_current_user(request)
        user_name = user.user_name if user else "anonymous"

        redis_conn = get_redis_connection()
        knowledge_base_queue_key = f"user:{user_name}:knowledge_base:queue"
        knowledge_base_map_key = f"user:{user_name}:knowledge_base:map"

        # 检查条目是否存在
        existing_item_raw = redis_conn.hget(knowledge_base_map_key, item_id)
        if not existing_item_raw:
            raise HTTPException(status_code=404, detail="知识库条目不存在")

        # 从映射中删除条目
        redis_conn.hdel(knowledge_base_map_key, item_id)

        # 从队列中删除对应的条目
        queue_items_raw = redis_conn.lrange(knowledge_base_queue_key, 0, -1)
        updated_queue_items = []

        for item_raw in queue_items_raw:
            try:
                item_data = json.loads(item_raw)
                if item_data.get("id") != item_id:
                    # 保留不匹配的条目
                    updated_queue_items.append(
                        json.dumps(item_data, ensure_ascii=False)
                    )
            except json.JSONDecodeError:
                logger.warning(f"解析知识库队列条目失败: {item_raw}")
                updated_queue_items.append(item_raw)  # 保持原样

        # 使用pipeline确保原子性操作
        pipeline = redis_conn.pipeline()

        # 重新设置队列（先删除再重新添加）
        pipeline.delete(knowledge_base_queue_key)
        if updated_queue_items:
            pipeline.rpush(knowledge_base_queue_key, *updated_queue_items)

        # 执行pipeline
        pipeline.execute()

        logger.info(f"用户 {user_name} 已删除知识库条目。ID: {item_id}")
        return {"success": True, "message": "知识库条目已成功删除"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"删除知识库条目失败 (item_id: {item_id}): {str(e)}", exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"删除知识库条目失败: {str(e)}")


class KnowledgeBaseSearch(BaseModel):
    query: str = Field(..., description="搜索查询词")


class KnowledgeBaseVote(BaseModel):
    vote: str = Field(..., description="投票类型，like 或 dislike")


class KnowledgeBaseVoteCompat(BaseModel):
    knowledge_id: str = Field(..., description="知识库条目ID")
    vote: str = Field(..., description="投票类型，up 或 down")


@app.post("/knowledge_base/search")
async def search_knowledge_base(request: Request, search_request: KnowledgeBaseSearch):
    """
    搜索知识库内容。
    支持在标题和内容中搜索关键词。
    """
    try:
        user = await get_current_user(request)
        user_name = user.user_name if user else "anonymous"

        redis_conn = get_redis_connection()
        knowledge_base_map_key = f"user:{user_name}:knowledge_base:map"

        # 获取用户的所有知识库条目
        all_items_raw = redis_conn.hgetall(knowledge_base_map_key)

        if not all_items_raw:
            return {"success": True, "results": []}

        search_query = search_request.query.lower()
        results = []

        for item_id, item_raw in all_items_raw.items():
            try:
                item_data = json.loads(item_raw)
                title = item_data.get("title", "").lower()
                content = item_data.get("content", "").lower()

                # 检查标题或内容是否包含搜索词
                if search_query in title or search_query in content:
                    # 生成内容预览（截取包含关键词的部分）
                    content_preview = _generate_content_preview(
                        item_data.get("content", ""), search_request.query
                    )

                    results.append(
                        {
                            "id": item_id,
                            "title": item_data.get("title", ""),
                            "content_preview": content_preview,
                            "timestamp": item_data.get("timestamp", ""),
                            "updated_at": item_data.get("updated_at", ""),
                            "author": item_data.get("author", ""),
                        }
                    )
            except json.JSONDecodeError:
                logger.warning(f"解析知识库条目失败 (item_id: {item_id}): {item_raw}")
                continue

        # 按更新时间倒序排序
        results.sort(key=lambda x: x.get("updated_at", ""), reverse=True)

        logger.info(
            f"用户 {user_name} 搜索知识库，查询词: '{search_request.query}'，找到 {len(results)} 条结果"
        )
        return {"success": True, "results": results}

    except Exception as e:
        logger.error(f"搜索知识库失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"搜索知识库失败: {str(e)}")


@app.post("/knowledge_base/item/{item_id}/vote")
async def vote_knowledge_base_item(
    request: Request, item_id: str, vote_data: KnowledgeBaseVote
):
    """
    对知识库条目进行点赞/点踩投票。
    每个用户只能投票一次，可以更改投票。
    """
    try:
        user = await get_current_user(request)
        user_name = user.user_name if user else "anonymous"

        if vote_data.vote not in ["like", "dislike"]:
            raise HTTPException(
                status_code=400, detail="投票类型必须是 like 或 dislike"
            )

        redis_conn = get_redis_connection()
        knowledge_base_map_key = f"user:{user_name}:knowledge_base:map"
        knowledge_base_queue_key = f"user:{user_name}:knowledge_base:queue"

        # 获取当前条目
        item_raw = redis_conn.hget(knowledge_base_map_key, item_id)
        if not item_raw:
            raise HTTPException(status_code=404, detail="知识库条目不存在")

        item_data = json.loads(item_raw)
        current_likes = item_data.get("likes", 0)
        current_dislikes = item_data.get("dislikes", 0)

        # 获取用户之前的投票
        user_vote_key = f"knowledge_base_vote:{item_id}:{user_name}"
        previous_vote = redis_conn.get(user_vote_key)
        previous_vote = previous_vote.decode("utf-8") if previous_vote else None

        # 计算新的计数
        new_likes = current_likes
        new_dislikes = current_dislikes

        if previous_vote == vote_data.vote:
            # 相同投票，无需更改
            pass
        else:
            if previous_vote == "like":
                new_likes -= 1
            elif previous_vote == "dislike":
                new_dislikes -= 1

            if vote_data.vote == "like":
                new_likes += 1
            elif vote_data.vote == "dislike":
                new_dislikes += 1

            # 更新用户投票记录
            redis_conn.setex(user_vote_key, 365 * 24 * 3600, vote_data.vote)  # 保存1年

        # 更新映射条目
        item_data["likes"] = new_likes
        item_data["dislikes"] = new_dislikes
        redis_conn.hset(
            knowledge_base_map_key, item_id, json.dumps(item_data, ensure_ascii=False)
        )

        # 更新队列条目
        queue_items_raw = redis_conn.lrange(knowledge_base_queue_key, 0, -1)
        updated = False
        for i, item_raw in enumerate(queue_items_raw):
            try:
                queue_item = json.loads(item_raw)
                if queue_item.get("id") == item_id:
                    queue_item["likes"] = new_likes
                    queue_item["dislikes"] = new_dislikes
                    redis_conn.lset(
                        knowledge_base_queue_key,
                        i,
                        json.dumps(queue_item, ensure_ascii=False),
                    )
                    updated = True
                    break
            except json.JSONDecodeError:
                continue

        logger.info(
            f"用户 {user_name} 对知识库条目 {item_id} 投票: {vote_data.vote}, 新计数: likes={new_likes}, dislikes={new_dislikes}"
        )
        return {
            "success": True,
            "message": "投票成功",
            "likes": new_likes,
            "dislikes": new_dislikes,
            "user_vote": vote_data.vote,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"投票失败 (item_id: {item_id}): {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"投票失败: {str(e)}")


@app.post("/knowledge_base/vote")
async def vote_knowledge_base_compat(
    request: Request, vote_data: KnowledgeBaseVoteCompat
):
    """
    对知识库条目进行点赞/点踩投票（兼容前端命名）。
    每个用户只能投票一次，可以更改投票。
    """
    try:
        user = await get_current_user(request)
        user_name = user.user_name if user else "anonymous"

        # 映射前端 vote 值到后端 vote 值
        vote_map = {"up": "like", "down": "dislike"}
        if vote_data.vote not in vote_map:
            raise HTTPException(status_code=400, detail="投票类型必须是 up 或 down")

        backend_vote = vote_map[vote_data.vote]
        item_id = vote_data.knowledge_id

        redis_conn = get_redis_connection()
        knowledge_base_map_key = f"user:{user_name}:knowledge_base:map"
        knowledge_base_queue_key = f"user:{user_name}:knowledge_base:queue"

        # 获取当前条目
        item_raw = redis_conn.hget(knowledge_base_map_key, item_id)
        if not item_raw:
            raise HTTPException(status_code=404, detail="知识库条目不存在")

        item_data = json.loads(item_raw)
        current_likes = item_data.get("likes", 0)
        current_dislikes = item_data.get("dislikes", 0)

        # 获取用户之前的投票
        user_vote_key = f"knowledge_base_vote:{item_id}:{user_name}"
        previous_vote = redis_conn.get(user_vote_key)
        # previous_vote = previous_vote.decode("utf-8") if previous_vote else None

        # 计算新的计数
        new_likes = current_likes
        new_dislikes = current_dislikes

        if previous_vote == backend_vote:
            # 相同投票，无需更改
            pass
        else:
            if previous_vote == "like":
                new_likes -= 1
            elif previous_vote == "dislike":
                new_dislikes -= 1

            if backend_vote == "like":
                new_likes += 1
            elif backend_vote == "dislike":
                new_dislikes += 1

            # 更新用户投票记录
            redis_conn.set(user_vote_key, backend_vote)  # 保存1年

        # 更新映射条目
        item_data["likes"] = new_likes
        item_data["dislikes"] = new_dislikes
        redis_conn.hset(
            knowledge_base_map_key, item_id, json.dumps(item_data, ensure_ascii=False)
        )

        # 更新队列条目
        queue_items_raw = redis_conn.lrange(knowledge_base_queue_key, 0, -1)
        updated = False
        for i, item_raw in enumerate(queue_items_raw):
            try:
                queue_item = json.loads(item_raw)
                if queue_item.get("id") == item_id:
                    queue_item["likes"] = new_likes
                    queue_item["dislikes"] = new_dislikes
                    redis_conn.lset(
                        knowledge_base_queue_key,
                        i,
                        json.dumps(queue_item, ensure_ascii=False),
                    )
                    updated = True
                    break
            except json.JSONDecodeError:
                continue

        logger.info(
            f"用户 {user_name} 对知识库条目 {item_id} 投票: {vote_data.vote}, 新计数: likes={new_likes}, dislikes={new_dislikes}"
        )
        # 映射回前端字段名
        return {
            "success": True,
            "message": "投票成功",
            "upvotes": new_likes,
            "downvotes": new_dislikes,
            "likes": new_likes,
            "dislikes": new_dislikes,
            "user_vote": vote_data.vote,  # 返回前端投票值
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"投票失败 (item_id: {item_id}): {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"投票失败: {str(e)}")


def _generate_content_preview(
    content: str, search_query: str, max_length: int = 100
) -> str:
    """
    生成内容预览，突出显示搜索关键词。

    Args:
        content: 原始内容
        search_query: 搜索查询词
        max_length: 预览最大长度

    Returns:
        包含关键词的内容预览
    """
    if not content:
        return ""

    content_lower = content.lower()
    query_lower = search_query.lower()

    # 查找关键词位置
    query_index = content_lower.find(query_lower)

    if query_index == -1:
        # 如果没有找到关键词，返回内容开头
        return content[:max_length] + ("..." if len(content) > max_length else "")

    # 计算预览的起始位置，确保关键词在中间位置
    start_pos = max(0, query_index - max_length // 2)
    end_pos = min(len(content), start_pos + max_length)

    # 调整起始位置，确保不会截断在单词中间
    if start_pos > 0:
        # 向前找到最近的空格或换行
        space_before = content.rfind(" ", 0, start_pos)
        if space_before != -1 and space_before > start_pos - 20:
            start_pos = space_before + 1

    # 生成预览文本
    preview = content[start_pos:end_pos]

    # 添加省略号
    if start_pos > 0:
        preview = "..." + preview
    if end_pos < len(content):
        preview = preview + "..."

    return preview


# ===== 任务管理接口 =====
class TaskRequest(BaseModel):
    """任务请求模型"""

    query: str = Field(..., description="任务查询内容")
    workspace_path: str = Field(..., description="工作目录路径")
    model_name: Optional[str] = Field(
        default="deepseek-reasoner", description="模型名称"
    )
    itecount: int = Field(default=200, description="迭代次数")
    agentid: Optional[str] = Field(None, description="代理ID")
    team_name: Optional[str] = Field(None, description="团队名称")
    conversation_id: Optional[str] = Field(None, description="会话ID")
    conversation_round: int = Field(default=5, description="会话轮数")
    file_ids: Optional[List[str]] = Field(None, description="文件ID列表")
    tool_choices: Optional[List[str]] = Field(None, description="工具选择列表")
    selected_skills: Optional[List[str]] = Field(None, description="选中的技能列表")


class TaskResponse(BaseModel):
    """任务响应模型"""

    success: bool = Field(..., description="操作是否成功")
    task_id: str = Field(..., description="生成的任务ID")
    chat_id: str = Field(..., description="关联的聊天ID")
    message: str = Field(..., description="提示信息")


@app.post("/task", response_model=TaskResponse)
async def create_task(request: Request, task_request: TaskRequest):
    """创建新的任务

    新建任务后返回任务ID，任务执行过程使用process_agent异步处理。
    """
    # 获取当前登录用户
    user = await get_current_user(request)
    logger.info(f"用户 {user} 创建新的任务")
    user_name = user.user_name if user else None

    # 生成任务ID和聊天ID
    task_id = f"task-{uuid.uuid4().hex[:8]}"
    chat_id = f"chat-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    # 如果提供了conversation_id，保存关系
    if task_request.conversation_id:
        redis_conn = get_redis_connection()
        conv_chats_key = f"conversation:{task_request.conversation_id}:chats"
        redis_conn.rpush(conv_chats_key, chat_id)
        redis_conn.set(
            f"chat:{chat_id}:conversation", task_request.conversation_id, ex=None
        )

        # 异步保存会话摘要信息
        asyncio.create_task(
            save_conversation_summary(
                conversation_id=task_request.conversation_id,
                chat_id=chat_id,
                initial_question=task_request.query,
                user_name=user_name,
                modul=task_request.modul,
            )
        )

    # 准备工具选择列表（与chat端点类似）：如果参数为空则使用默认值
    if task_request.tool_choices is None:
        tool_choices = [
            "serper_search",
            "web_crawler",
            "python_execute",
            "skills_extract",
        ]
    else:
        tool_choices = task_request.tool_choices

    # 检查模式是否支持
    # 启动智能体异步任务处理用户请求
    asyncio.create_task(
        process_agent(
            chat_id,
            task_request.query,
            task_request.itecount,
            task_request.agentid,
            agentmodul="task",
            team_name=task_request.team_name,
            conversation_id=task_request.conversation_id,
            model_name=task_request.model_name,
            conversation_round=task_request.conversation_round,
            file_ids=task_request.file_ids,
            user_name=user_name,
            tool_memory_enabled=True,
            sop_memory_enabled=True,
            enable_tools=True,
            tool_choices=tool_choices,
            selected_skills=task_request.selected_skills,
            workspace_path=task_request.workspace_path,
        )
    )

    return TaskResponse(
        success=True,
        task_id=task_id,
        chat_id=chat_id,
        message="任务创建成功，已启动异步执行",
    )


# ===== 技能列表接口 =====
@app.get("/skills/list")
async def list_skills():
    """获取可用技能列表

    返回所有配置的技能目录中扫描到的技能列表。
    技能目录包括：
    - 用户目录 ~/.proteus/skills
    - 应用目录 ./proteus/.proteus/skills
    - 项目目录 ./skills
    - 环境变量 PROTEUS_SKILLS_DIR 配置的目录
    """
    try:
        from src.nodes.skills_extract import (
            get_default_skills_dirs,
            scan_multiple_skills_directories,
        )

        skills_dirs = get_default_skills_dirs()
        if not skills_dirs:
            return {
                "success": True,
                "skills": [],
                "count": 0,
                "message": "未配置技能目录",
            }

        skills = scan_multiple_skills_directories(skills_dirs)
        # 按技能名称字母降序排列
        skills.sort(key=lambda x: x["name"].lower(), reverse=False)
        return {
            "success": True,
            "skills": skills,
            "count": len(skills),
            "message": f"成功扫描 {len(skills_dirs)} 个技能目录",
        }
    except Exception as e:
        logger.error(f"获取技能列表失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取技能列表失败: {str(e)}")
