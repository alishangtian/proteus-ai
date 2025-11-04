"""API主模块"""

import os
import logging
import json
import asyncio
import yaml
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, Any, Optional, Union, List
from fastapi.responses import RedirectResponse
from fastapi import FastAPI, HTTPException, Request, Body, UploadFile, File
from src.api.llm_api import call_llm_api_stream, call_llm_api_with_tools_stream
from src.utils.redis_cache import get_redis_connection  # 导入 Redis 连接
from src.utils.tool_converter import load_tools_from_yaml
import uuid  # 导入 uuid 用于生成唯一 ID
from src.utils.file_parser import parse_file  # 导入文件解析函数
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# 导入extract_tasks_and_completion
from src.utils.extract_playbook import PlaybookExtractor

from fastapi.responses import HTMLResponse
import shutil
from sse_starlette.sse import EventSourceResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from src.agent.terminition import ToolTerminationCondition
from src.utils.logger import setup_logger
from src.agent.prompt.react_playbook_prompt_v2 import REACT_PLAYBOOK_PROMPT_v2
from src.agent.prompt.react_playbook_prompt_v3 import REACT_PLAYBOOK_PROMPT_v3
from src.agent.prompt.cot_team_prompt import COT_TEAM_PROMPT_TEMPLATES
from src.agent.prompt.cot_browser_use_prompt import COT_BROWSER_USE_PROMPT_TEMPLATES
from src.agent.pagentic_team import PagenticTeam, TeamRole
from src.agent.agent import Agent
from src.agent.react_agent import ReactAgent
from src.agent.chat_agent import ChatAgent
from src.agent.common.configuration import AgentConfiguration
from src.agent.base_agent import IncludeFields
from src.manager.multi_agent_manager import get_multi_agent_manager
from src.utils.langfuse_wrapper import langfuse_wrapper
from src.api.events import (
    create_complete_event,
    create_agent_complete_event,
    create_agent_stream_thinking_event,
)

# 加载环境变量
from dotenv import load_dotenv

load_dotenv()
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
    "workflow",
    "super-agent",
    "mcp-agent",
    "browser-agent",
    "deep-research",
    "deep-research-multi",
    "codeact-agent",
]


# 延迟初始化工作流引擎
@langfuse_wrapper.observe_decorator(
    name="get_workflow_engine", capture_input=True, capture_output=True
)
def get_workflow_engine():
    """延迟初始化工作流引擎"""
    from src.core.engine import WorkflowEngine
    from src.api.utils import convert_node_result

    workflow_engine = WorkflowEngine()

    # 注册节点状态回调
    def node_status_callback(workflow_id: str, node_id: str, result):
        """处理节点状态变化的回调函数"""
        return convert_node_result(node_id, result)

    workflow_engine.register_node_callback(node_status_callback)
    return workflow_engine


# 延迟初始化工作流服务
@langfuse_wrapper.observe_decorator(
    name="get_workflow_service", capture_input=True, capture_output=True
)
def get_workflow_service():
    """延迟初始化工作流服务"""
    from src.api.workflow_service import WorkflowService

    return WorkflowService(get_workflow_engine())


# 在启动时注册工作流节点类型 - 改为按需加载
@langfuse_wrapper.observe_decorator(
    name="register_workflow_nodes", capture_input=True, capture_output=True
)
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动逻辑
    from src.agent.task_manager import task_manager

    await task_manager.start()
    try:
        yield
    finally:
        # 关闭逻辑：取消除当前任务之外的所有任务，并等待它们完成（忽略异常）
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


app = FastAPI(title="Workflow Engine API", version="1.0.0", lifespan=lifespan)


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
    }

    path = request.url.path
    logger.info(f"request path {path}")

    # 检查是否在排除路径中
    if any(path.startswith(p) for p in exclude_paths):
        return await call_next(request)

    # 检查登录状态（get_current_user 在文件中已延迟导入）
    user = await get_current_user(request)
    if not user:
        return RedirectResponse(url="/login")

    return await call_next(request)


# 注册路由
from src.auth.router import router as l_router
from src.api.history.history_router import router as h_router
from src.agent.agent_router import router as a_router
import src.agent.agent_router as agent_router

app.include_router(a_router)
app.include_router(l_router)
app.include_router(h_router)

# 初始化agent路由，注入stream_manager，但不立即注入node_manager
# 这样可以避免在应用启动时就加载node_manager
agent_router.init_router(smanager=stream_manager, nmanager=None)

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
UPLOAD_DIRECTORY = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)  # 确保目录存在


# 显式添加login.html路由
@app.get("/login.html", response_class=HTMLResponse)
async def serve_login_page():
    """直接返回登录页面"""
    with open(os.path.join(static_path, "login.html"), "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read(), media_type="text/html")


# 创建模板引擎
templates = Jinja2Templates(directory=static_path)


@langfuse_wrapper.dynamic_observe()
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


@langfuse_wrapper.observe_decorator(
    name="health_check", capture_input=True, capture_output=True
)
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
            "username": user.username if user else "",
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
            "username": user.username if user else "",
        },
    )


@langfuse_wrapper.dynamic_observe()
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
    username = user.username if user else None

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
                username=username,
                modul=modul,
            )
        )

    tool_choices = ["serper_search", "web_crawler", "python_execute"]

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
                username=username,  # 传递用户名
                tool_memory_enabled=tool_memory_enabled,  # 传递工具记忆参数
                sop_memory_enabled=sop_memory_enabled,  # 传递SOP记忆参数
                enable_tools=enable_tools,  # 传递工具调用开关
                tool_choices=tool_choices,  # 传递工具选择参数
            )
        )
    else:
        raise HTTPException(status_code=400, detail="Invalid model type")

    return {"success": True, "chat_id": chat_id}


@langfuse_wrapper.observe_decorator(
    name="stop_chat", capture_input=True, capture_output=True
)
@app.get("/stop/{model}/{chat_id}")
async def stop_chat(model: str, chat_id: str):
    if model == "deep-research":
        # 优化后的 deep-research 停止逻辑
        await _stop_deep_research_team(chat_id)
        await stream_manager.send_message(chat_id, await create_complete_event())
    elif model in agent_model_list:
        # 其他模型的停止逻辑保持不变
        agents = ReactAgent.get_agents(chat_id)
        if agents:
            await agents[0].stop()
        await stream_manager.send_message(chat_id, await create_complete_event())
    else:
        raise HTTPException(status_code=400, detail="Invalid model type")

    # 清理 agent 缓存
    ReactAgent.clear_agents(chat_id)

    logger.info(f"[{chat_id}] 已经停止")
    return {"success": True, "chat_id": chat_id}


@langfuse_wrapper.observe_decorator(
    name="_stop_deep_research_team", capture_input=True, capture_output=True
)
async def _stop_deep_research_team(chat_id: str):
    """停止 deep-research team 下的所有 agents

    Args:
        chat_id: 聊天会话ID
    """
    try:
        # 1. 从 Redis 获取 team 中的所有 agents
        team_agents = await _get_team_agents(chat_id)

        # 2. 从内存缓存获取 agents（作为备用）
        cached_agents = Agent.get_agents(chat_id)
        cached_react_agents = ReactAgent.get_agents(chat_id)

        # 3. 合并所有需要停止的 agents
        agents_to_stop = []

        # 添加缓存中的 agents
        agents_to_stop.extend(cached_agents)
        agents_to_stop.extend(cached_react_agents)

        # 4. 停止所有 agents
        multi_agent_manager = get_multi_agent_manager()
        stopped_agent_ids = set()

        for agent in agents_to_stop:
            if (
                hasattr(agent, "agentcard")
                and agent.agentcard.agentid not in stopped_agent_ids
            ):
                try:
                    await agent.stop()
                    multi_agent_manager.unregister_agent(agent.agentcard.agentid)
                    stopped_agent_ids.add(agent.agentcard.agentid)
                    logger.info(f"[{chat_id}] 已停止 agent: {agent.agentcard.agentid}")
                except Exception as e:
                    logger.error(
                        f"[{chat_id}] 停止 agent {agent.agentcard.agentid} 失败: {e}"
                    )

        # 5. 根据 Redis 中的 team agents 信息，尝试停止可能遗漏的 agents
        for team_agent_info in team_agents:
            agent_id = team_agent_info.get("agent_id")
            if agent_id and agent_id not in stopped_agent_ids:
                try:
                    # 尝试从 multi_agent_manager 注销
                    multi_agent_manager.unregister_agent(agent_id)
                    logger.info(f"[{chat_id}] 从 Redis 信息注销 agent: {agent_id}")
                except Exception as e:
                    logger.warning(f"[{chat_id}] 注销 agent {agent_id} 失败: {e}")

        # 6. 清理 team 绑定关系
        await _cleanup_team_binding(chat_id)

        logger.info(
            f"[{chat_id}] deep-research team 停止完成，共停止 {len(stopped_agent_ids)} 个 agents"
        )

    except Exception as e:
        logger.error(
            f"[{chat_id}] 停止 deep-research team 失败: {str(e)}", exc_info=True
        )
        # 即使出错也要尝试清理
        try:
            await _cleanup_team_binding(chat_id)
        except Exception:
            pass


@langfuse_wrapper.observe_decorator(
    name="stream_request", capture_input=True, capture_output=True
)
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

    return EventSourceResponse(event_generator())


@langfuse_wrapper.observe_decorator(
    name="replay_stream_request", capture_input=True, capture_output=True
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
        except ValueError as e:
            from src.api.events import create_error_event

            yield await create_error_event(f"Stream not found: {str(e)}")

    return EventSourceResponse(event_generator())


@langfuse_wrapper.observe_decorator(
    name="_register_team_binding", capture_input=True, capture_output=True
)
async def _register_team_binding(chat_id: str, team_name: str, agentmodel: str):
    """注册 team 和 chatid 的绑定关系到 Redis

    Args:
        chat_id: 聊天会话ID
        team_name: 团队名称
        agentmodel: 代理模型类型
    """
    try:
        from src.utils.redis_cache import RedisCache, get_redis_connection

        redis_cache = get_redis_connection()

        # 存储 team 绑定信息
        team_info = {
            "team_name": team_name,
            "agentmodel": agentmodel,
            "created_at": datetime.now().isoformat(),
            "status": "active",
        }

        # 设置 team 绑定关系，过期时间 24 小时
        team_binding_key = f"team_binding:{chat_id}"
        redis_cache.setex(
            team_binding_key, 24 * 3600, json.dumps(team_info, ensure_ascii=False)
        )

        # 初始化 team agents 列表
        team_agents_key = f"team_agents:{chat_id}"
        redis_cache.delete(team_agents_key)  # 清空可能存在的旧数据

        logger.info(f"[{chat_id}] 已注册 team 绑定关系: {team_name} ({agentmodel})")

    except Exception as e:
        logger.error(f"[{chat_id}] 注册 team 绑定关系失败: {str(e)}", exc_info=True)


@langfuse_wrapper.observe_decorator(
    name="_register_team_agent", capture_input=True, capture_output=True
)
async def _register_team_agent(chat_id: str, agent_id: str, role_type: str):
    """注册 team 中的 agent 到 Redis

    Args:
        chat_id: 聊天会话ID
        agent_id: agent ID
        role_type: agent 角色类型
    """
    try:
        from src.utils.redis_cache import RedisCache, get_redis_connection

        redis_cache = get_redis_connection()

        # 添加 agent 到 team agents 列表
        team_agents_key = f"team_agents:{chat_id}"
        agent_info = {
            "agent_id": agent_id,
            "role_type": role_type,
            "registered_at": datetime.now().isoformat(),
        }
        redis_cache.rpush(team_agents_key, json.dumps(agent_info, ensure_ascii=False))

        # 设置过期时间 24 小时
        redis_cache.expire(team_agents_key, 24 * 3600)

        logger.info(f"[{chat_id}] 已注册 team agent: {agent_id} ({role_type})")

    except Exception as e:
        logger.error(f"[{chat_id}] 注册 team agent 失败: {str(e)}", exc_info=True)


@langfuse_wrapper.observe_decorator(
    name="_get_team_agents", capture_input=True, capture_output=True
)
async def _get_team_agents(chat_id: str):
    """获取 team 中的所有 agents

    Args:
        chat_id: 聊天会话ID

    Returns:
        List[Dict]: agent 信息列表
    """
    try:
        from src.utils.redis_cache import RedisCache, get_redis_connection

        redis_cache = get_redis_connection()

        team_agents_key = f"team_agents:{chat_id}"
        agent_data_list = redis_cache.lrange(team_agents_key, 0, -1)

        agents = []
        for agent_data in agent_data_list:
            try:
                agent_info = json.loads(agent_data)
                agents.append(agent_info)
            except json.JSONDecodeError as e:
                logger.warning(f"[{chat_id}] 解析 agent 信息失败: {e}")
                continue

        logger.info(f"[{chat_id}] 获取到 {len(agents)} 个 team agents")
        return agents

    except Exception as e:
        logger.error(f"[{chat_id}] 获取 team agents 失败: {str(e)}", exc_info=True)
        return []


@langfuse_wrapper.observe_decorator(
    name="_cleanup_team_binding", capture_input=True, capture_output=True
)
async def _cleanup_team_binding(chat_id: str):
    """清理 team 绑定关系

    Args:
        chat_id: 聊天会话ID
    """
    try:
        from src.utils.redis_cache import RedisCache, get_redis_connection

        redis_cache = get_redis_connection()

        # 删除 team 绑定信息
        team_binding_key = f"team_binding:{chat_id}"
        team_agents_key = f"team_agents:{chat_id}"

        redis_cache.delete(team_binding_key)
        redis_cache.delete(team_agents_key)

        logger.info(f"[{chat_id}] 已清理 team 绑定关系")

    except Exception as e:
        logger.error(f"[{chat_id}] 清理 team 绑定关系失败: {str(e)}", exc_info=True)


@langfuse_wrapper.observe_decorator(
    name="generate_conversation_title", capture_input=True, capture_output=True
)
async def generate_conversation_title(initial_question: str) -> str:
    """使用 LLM 生成会话标题

    Args:
        initial_question: 初始问题

    Returns:
        生成的会话标题
    """
    try:
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
        from src.api.llm_api import call_llm_api

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

        logger.info(f"生成会话标题: {title}")
        return title

    except Exception as e:
        # 如果生成失败，回退到简单截取方式
        logger.warning(f"使用 LLM 生成标题失败，使用默认方式: {str(e)}")
        fallback_title = (
            initial_question[:15] + "..."
            if len(initial_question) > 15
            else initial_question
        )
        return fallback_title


@langfuse_wrapper.observe_decorator(
    name="save_conversation_summary", capture_input=True, capture_output=True
)
async def save_conversation_summary(
    conversation_id: str,
    chat_id: str,
    initial_question: str,
    username: str = None,
    modul: str = None,
):
    """异步保存会话摘要信息到 Redis

    Args:
        conversation_id: 会话ID
        chat_id: 聊天ID
        initial_question: 初始问题
        username: 用户名
        modul: 模型类型
    """
    try:
        redis_conn = get_redis_connection()
        conversation_key = f"conversation:{conversation_id}:info"
        username = username or "anonymous"

        # 使用 LLM 生成会话标题
        title = await generate_conversation_title(initial_question)

        # 检查会话是否已存在
        if not redis_conn.exists(conversation_key):
            # 新建会话：保存完整信息
            conversation_data = {
                "conversation_id": conversation_id,
                "title": title,
                "initial_question": initial_question,
                "username": username,
                "modul": modul or "unknown",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "first_chat_id": chat_id,
            }
            redis_conn.hmset(conversation_key, mapping=conversation_data)

            # 添加到用户的会话列表（有序集合，按时间戳排序）
            user_conversations_key = f"user:{username}:conversations"
            timestamp = time.time()
            redis_conn.zadd(user_conversations_key, {conversation_id: timestamp})
            logger.info(f"已创建会话摘要: {conversation_id}, 标题: {title}")
        else:
            # 已存在会话：更新标题和时间戳
            redis_conn.hset(conversation_key, "title", title)
            redis_conn.hset(conversation_key, "updated_at", datetime.now().isoformat())

            # 更新用户在有序集合中的时间戳，确保按更新时间排序
            user_conversations_key = f"user:{username}:conversations"
            timestamp = time.time()
            redis_conn.zadd(user_conversations_key, {conversation_id: timestamp})

            logger.info(f"已更新会话摘要: {conversation_id}, 新标题: {title}")

    except Exception as e:
        logger.error(f"保存会话摘要失败: {str(e)}", exc_info=True)


# @langfuse_wrapper.observe_decorator(
#     name="process_agent", capture_input=True, capture_output=True
# )
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
    username: str = None,  # 新增用户名参数
    tool_memory_enabled: bool = False,  # 新增工具记忆参数
    sop_memory_enabled: bool = False,  # 新增 SOP 记忆参数
    enable_tools: bool = False,  # 新增工具调用开关
    tool_choices: Optional[List[str]] = None,  # 新增工具选择参数
):
    """处理Agent请求的异步函数

    Args:
        chat_id: 聊天会话ID
        text: 用户输入的文本
        itecount: 迭代次数
        agentid: 代理ID(可选)
        agentmodel: 代理模型(可选)
        username: 用户名(可选)，用于工具记忆隔离
    """
    logger.info(
        f"[{chat_id}] 开始处理Agent请求: {query[:100]}... (agentid={agentid}, username={username})"
    )
    team = None
    agent = None
    final_result = None
    try:
        logger.info(f"[{chat_id}] process_agent 接收到的 file_ids: {file_ids}")
        file_analysis_context = ""
        if file_ids:
            redis_conn = get_redis_connection()
            for file_id in file_ids:
                file_data_str = redis_conn.get(f"file_analysis:{file_id}")
                if file_data_str:
                    file_data = json.loads(file_data_str)
                    analysis = file_data.get("analysis")
                    original_filename = file_data.get("original_filename", "未知文件")
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

        if agentmodul == "chat":
            # chat 模式：使用 ChatAgent 类处理
            logger.info(
                f"[{chat_id}] 开始 chat 模式请求（流式），工具调用: {enable_tools}"
            )

            # 创建 ChatAgent 实例
            chat_agent = ChatAgent(
                stream_manager=stream_manager,
                model_name=model_name,
                enable_tools=enable_tools,
                tool_choices=tool_choices,
                max_tool_iterations=itecount,
                conversation_id=conversation_id,
                conversation_round=conversation_round,
            )

            # 运行 ChatAgent
            final_result = await chat_agent.run(
                chat_id=chat_id,
                text=query,
                file_analysis_context=file_analysis_context,
            )
        elif agentmodul == "deep-research-multi":
            # 建立 team 和 chatid 的绑定关系
            await _register_team_binding(
                chat_id, team_name or "deep_research", agentmodul
            )

            # 递归查找配置文件
            def find_config_dir(filename):
                """递归查找配置文件目录"""
                current_dir = os.path.dirname(os.path.abspath(__file__))
                while True:
                    conf_path = os.path.join(current_dir, "conf", filename)
                    if os.path.exists(conf_path):
                        return conf_path
                    parent_dir = os.path.dirname(current_dir)
                    if parent_dir == current_dir:  # 到达根目录
                        break
                    current_dir = parent_dir
                return None

            # 查找配置文件
            # 确定团队名称，如果未提供则使用默认值
            final_team_name = team_name or "deep_research"
            config_file = f"{final_team_name}_team.yaml"
            config_path = find_config_dir(config_file)
            if not config_path:
                raise FileNotFoundError(f"找不到配置文件: {config_file}")

            logger.info(
                f"[{chat_id}] 团队: {final_team_name}, 找到配置文件: {config_path}"
            )

            # 加载YAML配置
            with open(config_path, "r", encoding="utf-8") as f:
                team_config = yaml.safe_load(f)

            # 构建tools_config字典
            tools_config = {}
            termination_map = {"ToolTerminationCondition": ToolTerminationCondition}

            for role_name, config in team_config["roles"].items():
                termination_conditions = []
                for tc in config["termination_conditions"]:
                    tc_class = termination_map[tc["type"]]
                    termination_conditions.append(
                        tc_class(**{k: v for k, v in tc.items() if k != "type"})
                    )

                tools_config[getattr(TeamRole, role_name)] = AgentConfiguration(
                    tools=config["tools"],
                    prompt_template=globals()[config["prompt_template"]],
                    agent_description=config["agent_description"],
                    agent_instruction=globals()[config["agent_instruction"]],
                    termination_conditions=termination_conditions,
                    model_name=config["model_name"],
                    max_iterations=itecount,
                    llm_timeout=config.get("llm_timeout", None),
                    conversation_id=conversation_id,
                    conversation_round=conversation_round,
                    tool_memory_enabled=tool_memory_enabled,  # 传递工具记忆参数
                    sop_memory_enabled=sop_memory_enabled,  # 传递 SOP 记忆参数
                )

            # 创建团队实例
            team = PagenticTeam(
                team_rules=team_config["team_rules"],
                tools_config=tools_config,
                start_role=getattr(TeamRole, team_config["start_role"]),
                conversation_round=conversation_round,
                username=username,
                tool_memory_enabled=tool_memory_enabled,  # 传递工具记忆参数
                sop_memory_enabled=sop_memory_enabled,  # 传递 SOP 记忆参数
            )
            logger.info(f"[{chat_id}] 配置PagenticTeam角色工具")
            await team.register_agents(chat_id)
            logger.info(f"[{chat_id}] PagenticTeam开始运行")
            final_result = await team.run(query, chat_id)
        elif agentmodul == "super-agent":
            # 超级智能体，智能组建team并完成任务
            logger.info(f"[{chat_id}] 开始超级智能体请求")
            prompt_template = COT_TEAM_PROMPT_TEMPLATES
            agent = ReactAgent(
                tools=["team_generator", "team_runner", "user_input"],
                instruction="",
                stream_manager=stream_manager,
                max_iterations=itecount,
                iteration_retry_delay=int(os.getenv("ITERATION_RETRY_DELAY", 30)),
                model_name=model_name,
                prompt_template=prompt_template,
                role_type=TeamRole.GENERAL_AGENT,
                conversation_id=conversation_id,
                conversation_round=conversation_round,
                username=username,
                tool_memory_enabled=tool_memory_enabled,  # 传递工具记忆参数
                sop_memory_enabled=sop_memory_enabled,  # 传递 SOP 记忆参数
            )

            # 调用Agent的run方法，启用stream功能
            result = await agent.run(query, chat_id)
            await stream_manager.send_message(chat_id, await create_complete_event())
        elif agentmodul == "codeact-agent":

            # CodeAct Agent模式：只允许使用python_execute和user_input工具
            all_tools = [
                "python_execute",
                "user_input",
            ]
            prompt_template = REACT_PLAYBOOK_PROMPT_v2
            include_fields = [IncludeFields.ACTION_INPUT, IncludeFields.OBSERVATION]

            # 创建详细的instruction
            explanation = """
                你是一个CodeAct Agent，主要使用Python代码执行工具(python_execute)来完成用户请求的任务。
                你可以使用Python代码进行任何计算、数据获取和处理。
                在编写代码时，请确保代码安全且只执行必要的操作。"""

            # 获取基础工具集合 - 延迟初始化node_manager
            agent = ReactAgent(
                tools=all_tools,
                instruction=explanation,
                stream_manager=stream_manager,
                max_iterations=itecount,
                iteration_retry_delay=int(os.getenv("ITERATION_RETRY_DELAY", 30)),
                model_name=model_name,
                prompt_template=prompt_template,
                role_type=TeamRole.GENERAL_AGENT,
                conversation_id=conversation_id,
                include_fields=include_fields,
                conversation_round=conversation_round,
                username=username,
                tool_memory_enabled=tool_memory_enabled,  # 传递工具记忆参数
                sop_memory_enabled=sop_memory_enabled,  # 传递 SOP 记忆参数
            )

            # 调用Agent的run方法，启用stream功能
            final_result = await agent.run(
                query, chat_id, context=file_analysis_context
            )
            await stream_manager.send_message(chat_id, await create_complete_event())
        elif agentmodul == "browser-agent":
            prompt_template = COT_BROWSER_USE_PROMPT_TEMPLATES
            agent = ReactAgent(
                tools=[
                    "browser_agent",
                    "python_execute",
                    "user_input",
                    "serper_search",
                    "web_crawler",
                ],
                instruction="",
                stream_manager=stream_manager,
                max_iterations=itecount,
                iteration_retry_delay=int(os.getenv("ITERATION_RETRY_DELAY", 30)),
                model_name=model_name,
                prompt_template=prompt_template,
                role_type=TeamRole.GENERAL_AGENT,
                conversation_id=conversation_id,
                conversation_round=conversation_round,
                username=username,
                tool_memory_enabled=tool_memory_enabled,  # 传递工具记忆参数
                sop_memory_enabled=sop_memory_enabled,  # 传递 SOP 记忆参数
            )
            # 调用Agent的run方法，启用stream功能
            final_result = await agent.run(query, chat_id)
            await stream_manager.send_message(chat_id, await create_complete_event())
        elif agentmodul == "deep-research":
            all_tools = [
                "python_execute",
                "serper_search",
                "web_crawler",
                "user_input",
            ]
            prompt_template = REACT_PLAYBOOK_PROMPT_v3
            # 获取基础工具集合 - 延迟初始化node_manager
            agent = ReactAgent(
                tools=all_tools,
                instruction="",
                stream_manager=stream_manager,
                max_iterations=itecount,
                iteration_retry_delay=int(os.getenv("ITERATION_RETRY_DELAY", 30)),
                model_name=model_name,
                prompt_template=prompt_template,
                role_type=TeamRole.GENERAL_AGENT,
                conversation_id=conversation_id,
                conversation_round=conversation_round,
                username=username,
                tool_memory_enabled=tool_memory_enabled,  # 传递工具记忆参数
                sop_memory_enabled=sop_memory_enabled,  # 传递 SOP 记忆参数
            )

            # 调用Agent的run方法，启用stream功能
            final_result = await agent.run(
                query, chat_id, context=file_analysis_context
            )
            await stream_manager.send_message(chat_id, await create_complete_event())
        else:
            await stream_manager.send_message(
                chat_id, await create_error_event("工作模式未定义")
            )
    except Exception as e:
        from src.api.events import create_error_event

        error_msg = f"处理Agent请求失败: {str(e)}"
        logger.error(f"[{chat_id}] {error_msg}", exc_info=True)
        await stream_manager.send_message(chat_id, await create_error_event(error_msg))
        if team is not None:
            await team.stop()
    finally:
        return {"status": "success", "final_result": final_result, "text": query}


@langfuse_wrapper.observe_decorator(
    name="handle_user_input", capture_input=True, capture_output=True
)
@app.post("/user_input")
async def handle_user_input(
    node_id: str = Body(...),
    value: Any = Body(...),
    chat_id: str = Body(...),
    agent_id: str = Body(...),
):
    """处理用户输入（使用 agent_id 进行过滤，优先精确匹配）

    行为：
    - 从 ReactAgent 缓存中获取 chat_id 对应的 agent 列表
    - 使用 agent_id 精确匹配目标 agent；若找到则向该 agent 发送输入
    - 如果未找到匹配且仅存在一个 agent，则回退到该唯一 agent（向后兼容）
    - 否则返回 400 错误提示未找到匹配 agent
    """
    try:
        agents = ReactAgent.get_agents(chat_id)
        if not agents:
            raise HTTPException(
                status_code=400, detail=f"No agents found for chat_id {chat_id}"
            )

        target_agent = None
        # 尝试使用 agent_id 精确匹配
        if agent_id:
            for a in agents:
                try:
                    if (
                        getattr(a, "agentcard", None)
                        and getattr(a.agentcard, "agentid", None) == agent_id
                    ):
                        target_agent = a
                        break
                except Exception:
                    continue

        # 回退策略：若没有匹配且只有一个 agent，则使用该 agent（兼容旧行为）
        if target_agent is None:
            if len(agents) == 1:
                target_agent = agents[0]
                logger.info(
                    f"[{chat_id}] agent_id {agent_id} 未命中，回退到唯一 agent {getattr(target_agent.agentcard, 'agentid', 'unknown')}"
                )
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"No matching agent for agent_id {agent_id} in chat {chat_id}",
                )

        await target_agent.set_user_input(node_id, value)
        return {"success": True, "message": "User input processed successfully"}
    except ValueError as ve:
        # 处理输入验证错误（例如没有等待的 user input）
        raise HTTPException(status_code=400, detail=str(ve))
    except HTTPException:
        # 重新抛出已知的 HTTPException
        raise
    except Exception as e:
        logger.error(f"处理用户输入失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@langfuse_wrapper.observe_decorator(
    name="execute_workflow", capture_input=True, capture_output=True
)
@app.post("/execute_workflow", response_model=ApiResponse)
async def execute_workflow(request: WorkflowRequest):
    """
    执行工作流

    根据提供的工作流定义执行工作流，返回统一的事件格式

    Args:
        request: 包含工作流定义的请求

    Returns:
        ApiResponse: 包含工作流执行结果的统一响应
    """
    request_id = f"req-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    logger.info(f"[{request_id}] 收到执行工作流请求")
    try:
        workflow_id = f"workflow-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # 记录工作流定义
        workflow_json = json.dumps(request.workflow, indent=2)
        logger.info(f"[{request_id}] 工作流定义:\n{workflow_json}")

        # 发送工作流事件
        workflow_event = await create_workflow_event(request.workflow)

        # 使用流式执行工作流
        events = []
        # 获取工作流引擎（延迟初始化）
        workflow_engine = get_workflow_engine()
        from src.api.events import (
            create_workflow_event,
            create_result_event,
            create_complete_event,
        )
        from src.api.utils import convert_node_result

        async for node_id, result in workflow_engine.execute_workflow_stream(
            json.dumps(request.workflow), workflow_id, request.global_params or {}
        ):
            # 使用工具函数转换结果为可序列化的字典
            result_dict = convert_node_result(node_id, result)
            node_event = await create_result_event(node_id, result_dict)
            events.append(node_event)

        # 生成完成事件
        complete_event = await create_complete_event()
        events.append(complete_event)

        logger.info(f"[{request_id}] 工作流执行完成")
        return ApiResponse(
            event="workflow_execution",
            success=True,
            data={
                "workflow": workflow_event["data"],
                "events": [event["data"] for event in events],
            },
        )
    except Exception as e:
        error_msg = f"执行工作流失败: {str(e)}"
        logger.error(f"[{request_id}] {error_msg}", exc_info=True)
        return ApiResponse(event="workflow_execution", success=False, error=error_msg)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)


# 提供模型配置列表接口，供前端下拉使用
@langfuse_wrapper.observe_decorator(
    name="list_models", capture_input=True, capture_output=True
)
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


@app.get("/playbook/{chat_id}")
async def get_playbook(chat_id: str):
    """
    根据 chat_id 获取剧本，并只提取规划和完成部分的内容。
    """
    try:
        redis_conn = get_redis_connection()
        playbook_key = f"playbook:{chat_id}"
        playbook_content = redis_conn.get(playbook_key)

        if not playbook_content:
            return {"success": True, "chat_id": chat_id, "playbook": ""}

        # 提取任务规划与完成度部分
        extracted_tasks = PlaybookExtractor.extract_tasks_and_completion(
            playbook_content
        )

        # 将提取到的任务转换为更友好的格式
        formatted_tasks = []
        for task in extracted_tasks:
            formatted_tasks.append(f"- [状态: {task['status']}] {task['description']}")

        extracted_content = {
            "tasks_and_completion": formatted_tasks if formatted_tasks else "无"
        }

        return {"success": True, "chat_id": chat_id, "playbook": extracted_content}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取剧本失败 (chat_id: {chat_id}): {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取剧本失败: {str(e)}")


@app.post("/feedback/{conversation_id}/{chat_id}/{feedback_type}")
async def submit_feedback(
    chat_id: str, conversation_id: str, feedback_type: str, request: Request
):
    """
    处理用户对会话的点赞/点踩反馈
    """
    user = await get_current_user(request)
    username = user.username if user else "anonymous"

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
            "username": username,
            "timestamp": datetime.now().isoformat(),
        }

        # 将反馈数据存储到 Redis，可以设置一个过期时间，例如 7 天
        redis_conn.setex(
            feedback_key, 7 * 24 * 3600, json.dumps(feedback_data, ensure_ascii=False)
        )

        logger.info(
            f"用户 {username} 对会话 {conversation_id} (chat_id: {chat_id}) 提交了 {feedback_type} 反馈"
        )
        return {"success": True, "message": "反馈提交成功"}
    except Exception as e:
        logger.error(
            f"提交反馈失败 (chat_id: {chat_id}, conversation_id: {conversation_id}, feedback_type: {feedback_type}): {str(e)}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"提交反馈失败: {str(e)}")


@langfuse_wrapper.observe_decorator(
    name="get_conversations", capture_input=True, capture_output=True
)
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
        username = user.username if user else "anonymous"

        redis_conn = get_redis_connection()
        user_conversations_key = f"user:{username}:conversations"

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

                # 获取该会话的chat数量
                conv_chats_key = f"conversation:{conv_id_str}:chats"
                chat_count = redis_conn.llen(conv_chats_key)
                conv_info["chat_count"] = chat_count

                conversations.append(conv_info)

        return {"success": True, "conversations": conversations}

    except Exception as e:
        logger.error(f"获取会话列表失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取会话列表失败: {str(e)}")


@langfuse_wrapper.observe_decorator(
    name="get_conversation_detail", capture_input=True, capture_output=True
)
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
        username = user.username if user else "anonymous"

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
        if conv_info.get("username") != username:
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


@langfuse_wrapper.observe_decorator(
    name="delete_conversation", capture_input=True, capture_output=True
)
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
        username = user.username if user else "anonymous"

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
        if conv_info.get("username") != username:
            raise HTTPException(status_code=403, detail="无权删除此会话")

        # 删除会话信息
        redis_conn.delete(conversation_key)

        # 删除会话的chat列表
        conv_chats_key = f"conversation:{conversation_id}:chats"
        redis_conn.delete(conv_chats_key)

        # 从用户会话列表中移除
        user_conversations_key = f"user:{username}:conversations"
        redis_conn.zrem(user_conversations_key, conversation_id)

        logger.info(f"用户 {username} 删除了会话 {conversation_id}")
        return {"success": True, "message": "会话已删除"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除会话失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除会话失败: {str(e)}")
