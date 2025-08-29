"""事件生成模块"""

import json
import time
from typing import Any, Dict


class EventType:
    """事件类型枚举"""

    STATUS = "status"
    WORKFLOW = "workflow"
    NODE_RESULT = "node_result"
    USER_INPUT_REQUIRED = "user_input_required"  # 用户输入请求事件
    EXPLANATION = "explanation"
    ANSWER = "answer"
    COMPLETE = "complete"
    ERROR = "error"
    ACTION_START = "action_start"
    ACTION_END = "action_end"
    ACTION_ERROR = "action_error"
    ACTION_COMPLETE = "action_complete"
    TOOL_PROGRESS = "tool_progress"  # 工具执行进度事件
    TOOL_RETRY = "tool_retry"  # 工具重试事件
    AGENT_START = "agent_start"  # agent开始执行事件
    AGENT_COMPLETE = "agent_complete"  # agent执行完成事件
    AGENT_ERROR = "agent_error"  # agent执行错误事件
    AGENT_THINKING = "agent_thinking"  # agent思考事件
    AGENT_SELECTION = "agent_selection"  # 智能体选择事件
    AGENT_EXECUTION = "agent_execution"  # 智能体执行事件
    AGENT_EVALUATION = "agent_evaluation"  # 智能体结果评估事件


async def create_event(event_type: str, data: Any) -> Dict:
    """统一的事件创建函数

    Args:
        event_type: 事件类型
        data: 事件数据

    Returns:
        Dict: 包含event和data的事件字典
    """
    # 如果data已经是字符串，不需要额外处理
    if isinstance(data, str):
        return {"event": event_type, "data": data}
    # 如果data是字典或其他类型，转换为JSON字符串
    return {"event": event_type, "data": json.dumps(data, ensure_ascii=False)}


async def create_status_event(status: str, message: str) -> Dict:
    """创建状态事件"""
    return await create_event(EventType.STATUS, message)


async def create_workflow_event(workflow: Dict) -> Dict:
    """创建工作流事件"""
    return await create_event(EventType.WORKFLOW, workflow)


async def create_result_event(node_id: str, result: Dict[str, Any]) -> Dict:
    """创建节点结果事件

    Args:
        node_id: 节点ID
        result: 节点执行结果字典，包含success、status、data、error等字段

    Returns:
        Dict: 事件字典
    """
    # 确保result是字典类型
    if not isinstance(result, dict):
        raise TypeError("Result must be a dictionary")

    return await create_event(
        EventType.NODE_RESULT, {**result, "node_id": node_id}  # 确保node_id存在于结果中
    )


async def create_explanation_event(content: str) -> Dict:
    """创建解释说明事件"""
    return await create_event(EventType.EXPLANATION, content)


async def create_answer_event(content: str) -> Dict:
    """创建回答事件"""
    return await create_event(EventType.ANSWER, content)


async def create_complete_event() -> Dict:
    """创建完成事件"""
    return await create_event(EventType.COMPLETE, "执行完成")


async def create_error_event(error_message: str) -> Dict:
    """创建错误事件"""
    return await create_event(EventType.ERROR, error_message)


async def create_action_start_event(
    action: str, action_input: Any, action_id: str = None
) -> Dict:
    """创建动作开始事件"""
    return await create_event(
        EventType.ACTION_START,
        {
            "action": action,
            "action_id": action_id
            or str(time.time()),  # 使用传入的action_id或时间戳作为默认值
            "input": action_input,
            "timestamp": time.time(),
        },
    )


async def create_action_complete_event(
    action: str, result: Any, action_id: str = None
) -> Dict:
    """创建动作完成事件"""
    return await create_event(
        EventType.ACTION_COMPLETE,
        {
            "action": action,
            "action_id": action_id
            or str(time.time()),  # 使用传入的action_id或时间戳作为默认值
            "result": result,
            "timestamp": time.time(),
        },
    )


async def create_tool_progress_event(
    tool: str, status: str, result: Any, action_id: str = None
) -> Dict:
    """创建工具进度事件"""
    return await create_event(
        EventType.TOOL_PROGRESS,
        {
            "tool": tool,
            "action_id": action_id
            or str(time.time()),  # 使用传入的action_id或时间戳作为默认值
            "status": status,
            "result": str(result),
            "timestamp": time.time(),
        },
    )


async def create_tool_retry_event(
    tool: str, attempt: int, max_retries: int, error: str
) -> Dict:
    """创建工具重试事件"""
    return await create_event(
        EventType.TOOL_RETRY,
        {
            "tool": tool,
            "attempt": attempt,
            "max_retries": max_retries,
            "error": error,
            "timestamp": time.time(),
        },
    )


async def create_agent_start_event(query: str) -> Dict:
    """创建agent开始事件"""
    return await create_event(
        EventType.AGENT_START, {"query": query, "timestamp": time.time()}
    )


async def create_agent_complete_event(result: str) -> Dict:
    """创建agent完成事件"""
    return await create_event(
        EventType.AGENT_COMPLETE, {"result": result, "timestamp": time.time()}
    )


async def create_agent_error_event(error: str) -> Dict:
    """创建agent错误事件"""
    return await create_event(
        EventType.AGENT_ERROR, {"error": error, "timestamp": time.time()}
    )


async def create_agent_thinking_event(thought: str) -> Dict:
    """创建agent思考事件"""
    return await create_event(
        EventType.AGENT_THINKING, {"thought": thought, "timestamp": time.time()}
    )


async def create_user_input_required_event(
    node_id: str,
    prompt: str,
    input_type: str = "text",
    default_value: Any = None,
    agent_id: str = None,
    validation: Dict[str, Any] = None,
) -> Dict:
    """创建用户输入请求事件

    Args:
        node_id: 节点ID
        prompt: 提示信息
        input_type: 输入类型，默认为text,可选项为：text,geolocation
        default_value: 默认值
        validation: 验证规则

    Returns:
        Dict: 事件字典
    """
    return await create_event(
        EventType.USER_INPUT_REQUIRED,
        {
            "node_id": node_id,
            "prompt": prompt,
            "input_type": input_type,
            "default_value": default_value,
            "validation": validation or {},
            "agent_id": agent_id,
            "timestamp": time.time(),
        },
    )


async def create_agent_selection_event(
    agent_id: str, agent_name: str, selection_reason: str, agent_task: str
) -> Dict:
    """创建智能体选择事件

    Args:
        agent_id: 智能体ID
        agent_name: 智能体名称
        selection_reason: 选择原因

    Returns:
        Dict: 事件字典
    """
    return await create_event(
        EventType.AGENT_SELECTION,
        {
            "agent_id": agent_id,
            "agent_name": agent_name,
            "selection_reason": selection_reason,
            "timestamp": time.time(),
            "agent_task": agent_task,
        },
    )


async def create_agent_execution_event(
    agent_id: str, agent_name: str, execution_step: str, execution_data: Dict
) -> Dict:
    """创建智能体执行事件

    Args:
        agent_id: 智能体ID
        execution_step: 执行步骤
        execution_data: 执行数据

    Returns:
        Dict: 事件字典
    """
    return await create_event(
        EventType.AGENT_EXECUTION,
        {
            "agent_id": agent_id,
            "execution_step": execution_step,
            "execution_data": execution_data,
            "timestamp": time.time(),
            "agent_name": agent_name,
        },
    )


async def create_agent_evaluation_event(
    agent_id: str, agent_name: str, evaluation_result: Dict, feedback: str = None
) -> Dict:
    """创建智能体结果评估事件

    Args:
        agent_id: 智能体ID
        evaluation_result: 评估结果
        feedback: 反馈意见

    Returns:
        Dict: 事件字典
    """
    return await create_event(
        EventType.AGENT_EVALUATION,
        {
            "agent_id": agent_id,
            "evaluation_result": evaluation_result,
            "feedback": feedback,
            "timestamp": time.time(),
            "agent_name": agent_name,
        },
    )
