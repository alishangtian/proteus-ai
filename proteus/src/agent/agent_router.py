"""智能体路由模块"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import List
import asyncio, uuid, os
from pydantic import BaseModel
from .task_manager import task_manager

from .agent_manager import AgentManager, AgentData
from src.nodes.node_config import NodeConfigManager

router = APIRouter(prefix="/agents", tags=["agents"])
agent_manager = AgentManager()
stream_manager = None  # 将在main.py中被注入
node_manager = None  # 将在main.py中被注入


def init_router(smanager, nmanager):
    """初始化路由，注入stream_manager"""
    global stream_manager
    stream_manager = smanager
    global node_manager
    node_manager = nmanager


class GeneratePromptRequest(BaseModel):
    name: str
    description: str
    tools: List[dict]


@router.post("/generate-prompt")
async def generate_system_prompt(request: GeneratePromptRequest):
    """根据智能体名称和描述生成系统提示词(流式输出)

    参数通过POST请求体传递:
    {
        "name": "智能体名称",
        "description": "智能体描述"
    }
    """
    prompt = f"""根据以下信息生成一个智能体的系统提示词:
智能体名称: {request.name}
智能体描述: {request.description}
可用的工具: {request.tools}

请生成一个专业、清晰的系统提示词，指导该智能体更好的完成任务,可用工具列表只是提醒模型可以使用哪些工具,
不要以工具列表的形式出现在提示词中。"""

    async def generate():
        try:
            messages = [{"role": "user", "content": prompt}]
            async for chunk in call_llm_api_stream(messages):
                yield chunk
                await asyncio.sleep(0.1)  # 控制流式输出速度
        except Exception as e:
            yield f"生成提示词时出错: {str(e)}"

    return StreamingResponse(generate(), media_type="text/plain")


class CreateAgentRequest(BaseModel):
    """创建智能体请求参数"""

    name: str
    description: str
    system_prompt: str
    tools: List[dict]
    config: dict


class UpdateAgentRequest(BaseModel):
    """更新智能体请求参数"""

    name: str
    description: str
    system_prompt: str
    tools: List[dict]
    config: dict


@router.post("/info", response_model=AgentData)
async def create_agent(request: CreateAgentRequest):
    """创建新智能体

    参数通过POST请求体传递:
    {
        "name": "智能体名称",
        "description": "智能体描述",
        "system_prompt": "系统提示词",
        "tools": [工具列表],
        "config": {配置信息}
    }
    """
    try:
        return agent_manager.create_agent(
            name=request.name,
            description=request.description,
            system_prompt=request.system_prompt,
            tools=request.tools,
            config=request.config,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/list", response_model=List[AgentData])
async def list_agents():
    """获取所有智能体列表"""
    return agent_manager.list_agents()


@router.get("/info/{agent_id}", response_model=AgentData)
async def get_agent(agent_id: str):
    """根据ID获取智能体详情"""
    agent = agent_manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.put("/info/{agent_id}", response_model=AgentData)
async def update_agent(agent_id: str, request: UpdateAgentRequest):
    """更新智能体信息

    参数通过PUT请求体传递:
    {
        "name": "智能体名称",
        "description": "智能体描述",
        "system_prompt": "系统提示词",
        "tools": [工具列表],
        "config": {配置信息}
    }
    """
    try:
        return agent_manager.update_agent(
            agent_id=agent_id,
            name=request.name,
            description=request.description,
            system_prompt=request.system_prompt,
            tools=request.tools,
            config=request.config,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/info/{agent_id}")
async def delete_agent(agent_id: str):
    """删除智能体"""
    if not agent_manager.delete_agent(agent_id):
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"message": "Agent deleted successfully"}


@router.get("/nodes/tools")
async def get_node_tools():
    """获取节点工具列表(供前端使用)

    返回格式:
    {
        "success": bool,
        "message": str,
        "data": [
            {
                "id": str,
                "name": str,
                "description": str,
                "icon": str (可选),
                "category": str (可选)
            }
        ]
    }
    """
    try:
        node_manager = NodeConfigManager.get_instance()
        tools = node_manager.get_all_agent_nodes()
        formatted_tools = []

        for tool in tools:
            formatted_tools.append(
                {
                    "id": tool["type"],
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "icon": tool.get("icon", "🛠️"),
                    "category": tool.get("category", "其他"),
                }
            )

        return {"success": True, "message": "获取工具列表成功", "data": formatted_tools}
    except Exception as e:
        import traceback

        traceback.print_exc()
        return {
            "success": False,
            "message": f"获取工具列表失败: {str(e)}",
            "data": None,
        }


@router.delete("/task/{task_id}")
async def cancel_task(task_id: str):
    """取消异步任务

    Args:
        task_id: 要取消的任务ID

    Returns:
        {
            "success": bool,
            "message": str
        }
    """
    success = await task_manager.cancel_task(task_id)
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Task cannot be cancelled (may be already completed or running)",
        )
    return {"success": True, "message": "Task cancelled successfully"}


@router.get("/task/{task_id}")
async def get_task_status(task_id: str):
    """获取异步任务状态

    Args:
        task_id: 任务ID

    Returns:
        {
            "success": bool,
            "task_id": str,
            "status": str,  # pending/running/completed/failed
            "result": any,  # 任务结果(完成时)
            "error": str    # 错误信息(失败时)
        }
    """
    task_info = await task_manager.get_task_status(task_id)
    if not task_info:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "success": True,
        "task_id": task_id,
        "status": task_info["status"],
        "result": task_info.get("result"),
        "error": task_info.get("error"),
    }
