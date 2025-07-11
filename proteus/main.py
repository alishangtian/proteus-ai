"""API主模块"""

import os
import logging
import json
import asyncio
import yaml
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, Any, Optional, Union
from fastapi.responses import RedirectResponse
from fastapi import FastAPI, HTTPException, Request, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from sse_starlette.sse import EventSourceResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from src.agent.terminition import ToolTerminationCondition
from src.utils.logger import setup_logger
from src.agent.prompt.cot_prompt import COT_PROMPT_TEMPLATES
from src.agent.prompt.cot_team_prompt import COT_TEAM_PROMPT_TEMPLATES
from src.agent.prompt.cot_workflow_prompt import COT_WORKFLOW_PROMPT_TEMPLATES
from src.agent.pagentic_team import PagenticTeam, TeamRole
from src.nodes.node_config import NodeConfigManager
from src.agent.agent import Agent, AgentConfiguration
from src.manager.multi_agent_manager import TeamRole, get_multi_agent_manager

from src.agent.prompt.deep_research.coordinator import COORDINATOR_PROMPT_TEMPLATES
from src.agent.prompt.deep_research.planner import PLANNER_PROMPT_TEMPLATES
from src.agent.prompt.deep_research.researcher import RESEARCHER_PROMPT_TEMPLATES
from src.agent.prompt.deep_research.coder import CODER_PROMPT_TEMPLATES
from src.agent.prompt.deep_research.reporter import REPORTER_PROMPT_TEMPLATES

from src.api.events import (
    create_status_event,
    create_workflow_event,
    create_result_event,
    create_answer_event,
    create_complete_event,
    create_error_event,
)
from src.api.utils import convert_node_result
from src.api.llm_api import call_llm_api_stream

# 加载环境变量
from dotenv import load_dotenv

load_dotenv()

# 设置MCP配置文件路径
os.environ["MCP_CONFIG_PATH"] = os.path.join(
    os.path.dirname(__file__), "proteus_mcp_config.json"
)

# 获取日志文件路径
log_file_path = os.getenv("log_file_path", "logs/workflow_engine.log")

# 配置日志
logger = setup_logger(log_file_path)
module_logger = logging.getLogger(__name__)

# 创建全局流管理实例 - 必须优先初始化
from src.api.stream_manager import StreamManager

stream_manager = StreamManager.get_instance()

agent_dict = {}


# 延迟初始化历史服务
def get_history_service():
    """延迟初始化历史服务"""
    from src.api.history_service import HistoryService

    return HistoryService()


# 延迟初始化工作流引擎
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
def get_workflow_service():
    """延迟初始化工作流服务"""
    from src.api.workflow_service import WorkflowService

    return WorkflowService(get_workflow_engine())


# 在启动时注册工作流节点类型 - 改为按需加载
def register_workflow_nodes(workflow_engine, node_manager):
    """注册所有可用的节点类型"""
    import importlib

    # 确保配置已加载
    module_logger.info("开始注册工作流节点类型")

    # 获取配置（会触发懒加载机制）
    node_configs = node_manager.get_all_nodes()

    for node_config in node_configs:
        # 获取节点配置中定义的type
        node_type = node_config.get("type")
        class_name = node_config.get("class_name", node_type)

        if not node_type:
            module_logger.info(f"节点配置未包含type字段，跳过注册")
            continue

        # 从type生成模块名
        module_name = node_type

        try:
            # 动态导入节点模块
            module = importlib.import_module(f"src.nodes.{module_name}")
            node_class = getattr(module, class_name)
            # 使用配置的type注册节点类型
            workflow_engine.register_node_type(node_type, node_class)
            module_logger.info(f"成功注册节点类型: {node_type}")
        except Exception as e:
            module_logger.error(f"注册节点类型 {module_name} 失败: {str(e)}")
            # 不抛出异常，继续注册其他节点
            continue

    module_logger.info("工作流节点类型注册完成")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动逻辑
    from src.agent.task_manager import task_manager

    await task_manager.start()
    yield
    # 关闭逻辑
    loop = asyncio.get_event_loop()
    for task in asyncio.all_tasks(loop):
        if task is not asyncio.current_task(loop):
            task.cancel()
    loop.stop()


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

        module_logger.info(f"request path {path}")

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

app.add_middleware(AuthMiddleware)

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


# 显式添加login.html路由
@app.get("/login.html", response_class=HTMLResponse)
async def serve_login_page():
    """直接返回登录页面"""
    with open(os.path.join(static_path, "login.html"), "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read(), media_type="text/html")


# 创建模板引擎
templates = Jinja2Templates(directory=static_path)


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
    module_logger.debug("收到健康检查请求")
    return ApiResponse(event="health_check", success=True, data={"status": "healthy"})


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
async def get_agent_page(request: Request):
    """返回super-agent交互页面"""
    return templates.TemplateResponse("superagent/index.html", {"request": request})


@app.post("/chat")
async def create_chat(
    text: str = Body(..., embed=True),
    model: str = Body(..., embed=True),
    itecount: int = Body(5, embed=True),
    agentid: str = Body(None, embed=True),
    team_name: str = Body(None, embed=True),
    conversation_id: str = Body(None, embed=True),
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
    chat_id = f"chat-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    stream_manager.create_stream(chat_id, text)

    # 创建并保存历史记录
    from src.api.history_service import ChatHistory

    history_service = get_history_service()
    chat_history = ChatHistory(
        id=chat_id,
        query=text,
        timestamp=datetime.now().isoformat(),
        model=model,
        agentid=agentid,
    )
    history_service.add_history(chat_history)

    agent_model_list = [
        "workflow",
        "super-agent",
        "home",
        "mcp-agent",
        "multi-agent",
        "browser-agent",
        "deep-research",
    ]

    # if model == "workflow":
    #     # 启动工作流异步任务处理用户请求
    #     asyncio.create_task(process_workflow(chat_id, text, agentid))
    # el
    if model in agent_model_list:
        # 启动智能体异步任务处理用户请求
        asyncio.create_task(
            process_agent(
                chat_id,
                text,
                itecount,
                agentid,
                agentmodel=model,
                team_name=team_name,
                conversation_id=conversation_id,
            )
        )
    else:
        raise HTTPException(status_code=400, detail="Invalid model type")

    return {"success": True, "chat_id": chat_id}


@app.get("/stop/{model}/{chat_id}")
async def stop_chat(model: str, chat_id: str):
    agent_model_list = [
        "workflow",
        "super-agent",
        "home",
        "mcp-agent",
        "multi-agent",
        "browser-agent",
        "deep-research",
    ]
    if model == "deep-research":
        multi_agent_manager = get_multi_agent_manager()
        for agent in Agent.get_agents(chat_id):
            await agent.stop()
            multi_agent_manager.unregister_agent(agent.agentcard.agentid)
        await stream_manager.send_message(chat_id, await create_complete_event())
    elif model in agent_model_list:
        await Agent.get_agents(chat_id)[0].stop()
        await stream_manager.send_message(chat_id, await create_complete_event())
    else:
        raise HTTPException(status_code=400, detail="Invalid model type")
    Agent.clear_agents(chat_id)
    module_logger.info(f"[{chat_id}] 已经停止")
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

    return EventSourceResponse(event_generator())


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


async def process_workflow(chat_id: str, text: str, agentid: str = None):
    """处理用户请求的异步函数

    Args:
        chat_id: 聊天会话ID
        text: 用户输入的文本
        agentid: 代理ID(可选)
    """
    module_logger.info(f"[{chat_id}] 开始处理请求: {text[:100]}...")
    try:

        # 获取工作流服务（延迟初始化）
        workflow_service = get_workflow_service()

        # 开始生成工作流
        module_logger.info(f"[{chat_id}] 开始生成工作流")
        await stream_manager.send_message(
            chat_id, await create_status_event("generating", "正在生成工作流...")
        )
        workflow = await workflow_service.generate_workflow(text, chat_id)

        if not workflow or not workflow.get("nodes"):
            # 如果没有生成工作流，直接返回普通回答
            module_logger.info(f"[{chat_id}] 无工作流生成，转为生成普通回答")
            await stream_manager.send_message(
                chat_id, await create_status_event("answering", "正在生成回答...")
            )
            try:
                messages = [
                    {"role": "system", "content": "请根据用户问题提供简洁准确的回答。"},
                    {"role": "user", "content": text},
                ]
                async for chunk in call_llm_api_stream(messages, chat_id):
                    await stream_manager.send_message(
                        chat_id,
                        await create_answer_event(
                            {"event": "answer", "success": True, "data": chunk}
                        ),
                    )
                await stream_manager.send_message(
                    chat_id, await create_complete_event()
                )
            except Exception as e:
                module_logger.error(
                    f"[{chat_id}] 生成回答时发生错误: {str(e)}", exc_info=True
                )
                await stream_manager.send_message(
                    chat_id, await create_error_event("生成回答失败，请稍后重试")
                )
            return

        # 发送工作流定义
        module_logger.info(
            f"[{chat_id}] 工作流生成成功，节点数: {len(workflow.get('nodes', []))}"
        )
        await stream_manager.send_message(
            chat_id, await create_workflow_event(workflow)
        )
        await asyncio.sleep(0.1)  # 添加小延迟使前端显示更流畅

        # 开始执行工作流
        await stream_manager.send_message(
            chat_id, await create_status_event("executing", "正在执行工作流...")
        )
        workflow_id = f"workflow-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        try:
            module_logger.info(f"[{chat_id}] 开始执行工作流: {workflow_id}")
            # 使用流式执行工作流
            # 执行工作流并处理结果流
            # 使用流式执行并实时发送结果
            # 获取工作流引擎（延迟初始化）
            workflow_engine = get_workflow_engine()

            async for node_id, result in workflow_engine.execute_workflow_stream(
                json.dumps(workflow), chat_id, {}
            ):
                module_logger.info(
                    f"[{chat_id}] 节点 {node_id} 执行状态: status={result.status} 执行结果：success={result.success}"
                )
                # 使用工具函数转换结果为可序列化的字典
                result_dict = convert_node_result(node_id, result)
                # 立即发送节点状态更新
                event = await create_result_event(node_id, result_dict)
                await stream_manager.send_message(chat_id, event)
                # 添加小延迟确保前端能够正确接收和处理事件
                await asyncio.sleep(0.01)

            # 获取工作流执行结果并生成说明
            # module_logger.info(f"[{chat_id}] 开始生成执行说明")
            # workflow_results = engine.get_workflow_progress(workflow_id)
            # async for chunk in workflow_service.explain_workflow_result(text, workflow, workflow_results, chat_id):
            #     await stream_manager.send_message(chat_id, await create_explanation_event({
            #         "event": "explanation",
            #         "success": True,
            #         "data": chunk
            #     }))
            await stream_manager.send_message(chat_id, await create_complete_event())
            module_logger.info(f"[{chat_id}] 工作流执行完成")

        except Exception as e:
            error_msg = f"执行工作流失败: {str(e)}"
            module_logger.error(f"[{chat_id}] {error_msg}", exc_info=True)
            await stream_manager.send_message(
                chat_id, await create_error_event(error_msg)
            )

    except Exception as e:
        error_msg = f"处理请求失败: {str(e)}"
        module_logger.error(f"[{chat_id}] {error_msg}", exc_info=True)
        await stream_manager.send_message(chat_id, await create_error_event(error_msg))


async def process_agent(
    chat_id: str,
    text: str,
    itecount: int,
    agentid: str = None,
    agentmodel: str = None,
    team_name: str = None,
    conversation_id: str = None,
):
    """处理Agent请求的异步函数

    Args:
        chat_id: 聊天会话ID
        text: 用户输入的文本
        itecount: 迭代次数
        agentid: 代理ID(可选)
        agentmodel: 代理模型(可选)
    """
    module_logger.info(
        f"[{chat_id}] 开始处理Agent请求: {text[:100]}... (agentid={agentid})"
    )
    team = None
    agent = None
    try:
        if agentmodel == "deep-research":
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
                    role_description=config["role_description"],
                    termination_conditions=termination_conditions,
                    model_name=config["model_name"],
                    max_iterations=itecount,
                    llm_timeout=config.get("llm_timeout", None),
                )

            # 创建团队实例
            team = PagenticTeam(
                team_rules=team_config["team_rules"],
                tools_config=tools_config,
                start_role=getattr(TeamRole, team_config["start_role"]),
            )
            logger.info(f"[{chat_id}] 配置PagenticTeam角色工具")
            await team.register_agents()
            logger.info(f"[{chat_id}] PagenticTeam开始运行")
            await team.run(text, chat_id)
        elif agentmodel == "super-agent":
            # 超级智能体，智能组建team并完成任务
            logger.info(f"[{chat_id}] 开始超级智能体请求")
            prompt_template = COT_TEAM_PROMPT_TEMPLATES
            agent = Agent(
                tools=["team_generator", "team_runner", "user_input"],
                instruction="",
                stream_manager=stream_manager,
                max_iterations=itecount,
                history_service=get_history_service(),
                iteration_retry_delay=int(os.getenv("ITERATION_RETRY_DELAY", 30)),
                model_name="base-model",
                prompt_template=prompt_template,
                role_type=TeamRole.GENERAL_AGENT,
                conversation_id=conversation_id,
            )

            # 调用Agent的run方法，启用stream功能
            await agent.run(text, chat_id)
            from src.api.events import create_complete_event, create_error_event

            await stream_manager.send_message(chat_id, await create_complete_event())
        else:
            # 获取基础工具集合 - 延迟初始化node_manager
            all_tools = NodeConfigManager.get_instance().get_tools()
            prompt_template = COT_PROMPT_TEMPLATES
            if agentmodel == "workflow":
                prompt_template = COT_WORKFLOW_PROMPT_TEMPLATES
                all_tools = NodeConfigManager.get_instance().get_tools(
                    tool_type="workflow"
                )
            # 获取基础工具集合 - 延迟初始化node_manager
            agent = Agent(
                tools=all_tools,
                instruction="",
                stream_manager=stream_manager,
                max_iterations=itecount,
                history_service=get_history_service(),
                iteration_retry_delay=int(os.getenv("ITERATION_RETRY_DELAY", 30)),
                model_name="base-model",
                prompt_template=prompt_template,
                role_type=TeamRole.GENERAL_AGENT,
                conversation_id=conversation_id,
            )

            # 调用Agent的run方法，启用stream功能
            await agent.run(text, chat_id)
            from src.api.events import create_complete_event, create_error_event

            await stream_manager.send_message(chat_id, await create_complete_event())
    except Exception as e:
        from src.api.events import create_error_event

        error_msg = f"处理Agent请求失败: {str(e)}"
        module_logger.error(f"[{chat_id}] {error_msg}", exc_info=True)
        await stream_manager.send_message(chat_id, await create_error_event(error_msg))
        if team is not None:
            await team.stop()


@app.post("/user_input")
async def handle_user_input(
    node_id: str = Body(...), value: Any = Body(...), chat_id: str = Body(...)
):
    """处理用户输入

    Args:
        node_id: 需要用户输入的节点ID
        value: 用户提供的输入值
        chat_id: 聊天会话ID

    Returns:
        dict: 操作结果
    """
    try:
        await Agent.get_agents(chat_id)[0].set_user_input(node_id, value)
        return {"success": True, "message": "User input processed successfully"}
    except ValueError as ve:
        # 处理输入验证错误
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        module_logger.error(f"处理用户输入失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


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
    module_logger.info(f"[{request_id}] 收到执行工作流请求")
    try:
        workflow_id = f"workflow-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # 记录工作流定义
        workflow_json = json.dumps(request.workflow, indent=2)
        module_logger.info(f"[{request_id}] 工作流定义:\n{workflow_json}")

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

        module_logger.info(f"[{request_id}] 工作流执行完成")
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
        module_logger.error(f"[{request_id}] {error_msg}", exc_info=True)
        return ApiResponse(event="workflow_execution", success=False, error=error_msg)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
