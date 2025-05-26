from datetime import datetime
from abc import ABC, abstractmethod
import re
from typing import List, Dict, Any
import asyncio
import contextlib
import logging
import time
import uuid
from string import Template
from functools import wraps, lru_cache
from ..exception.action_bad import ActionBadException
from ..api.llm_api import call_llm_api
from ..api.events import (
    create_action_start_event,
    create_action_complete_event,
    create_tool_progress_event,
    create_tool_retry_event,
    create_agent_start_event,
    create_agent_complete_event,
    create_agent_error_event,
    create_agent_thinking_event,
    create_user_input_required_event,
)
from ..agent.prompt.deep_research.react_loop_prompt import REACT_LOOP_PROMPT
from ..agent.prompt.deep_research.planner_react_loop_prompt import (
    PLANNER_REACT_LOOP_PROMPT,
)
from ..manager.multi_agent_manager import get_multi_agent_manager
from ..api.history_service import HistoryService
from ..manager.mcp_manager import get_mcp_manager
from .parse_xml import ParseXml
from ..api.stream_manager import StreamManager
from .base_agent import (
    AgentError,
    ToolExecutionError,
    ToolNotFoundError,
    LLMAPIError,
    Metrics,
    Cache,
    Tool,
    AgentCard,
    ScratchpadItem,
)
from ..manager.multi_agent_manager import TeamRole, AgentEvent
from .terminition import TerminationCondition, StepLimitTerminationCondition

logger = logging.getLogger(__name__)


class AgentConfiguration:
    """Agent配置类，封装Agent的配置参数

    Attributes:
        role_type (TeamRole): Agent角色类型
        description (str): Agent描述
        prompt_template (str): 提示词模板
        model_name (str): 模型名称
        termination_conditions (List[TerminationCondition]): 终止条件列表
        tools (List[Any]): 工具列表
    """

    def __init__(
        self,
        role_type: TeamRole = None,
        role_description: str = "",
        agent_description: str = "",
        prompt_template: str = "",
        model_name: str = "deepseek-chat",
        termination_conditions: List[TerminationCondition] = None,
        tools: List[Any] = None,
        team_description: str = None,
        max_iterations: int = 50,
        llm_timeout: int = 120,
    ):
        """初始化Agent配置

        Args:
            role_type: Agent角色类型
            description: Agent描述
            prompt_template: 提示词模板
            model_name: 模型名称
            termination_conditions: 终止条件列表，默认为空列表
            tools: 工具列表，默认为空列表
        """
        self.role_type = role_type
        self.role_description = role_description
        self.prompt_template = prompt_template
        self.model_name = model_name
        self.termination_conditions = termination_conditions or []
        self.tools = tools or []
        self.team_description = team_description
        self.agent_description = agent_description
        self.max_iterations = max_iterations
        self.llm_timeout = llm_timeout


def log_execution_time(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = asyncio.get_event_loop().time()
        try:
            result = await func(*args, **kwargs)
            execution_time = asyncio.get_event_loop().time() - start_time
            logger.debug(f"{func.__name__} executed in {execution_time:.2f} seconds")
            return result
        except Exception as e:
            execution_time = asyncio.get_event_loop().time() - start_time
            logger.error(
                f"{func.__name__} failed after {execution_time:.2f} seconds: {str(e)}"
            )
            raise

    return wrapper


class Agent:

    def __init__(
        self,
        tools: List[Any],  # 修改为Any类型以支持多种工具输入
        prompt_template: str,  # 新增提示词模板参数
        instruction: str = "",
        description: str = "",
        team_description: str = "",
        timeout: int = 120,
        llm_timeout: int = 60,
        max_iterations: int = 10,
        iteration_retry_delay: int = 60,
        memory_size: int = 10,
        cache_size: int = 100,
        cache_ttl: int = 3600,
        stream_manager: StreamManager = None,
        history_service: HistoryService = None,
        context: str = None,
        model_name: str = None,
        reasoner_model_name: str = None,
        agentcard: AgentCard = None,
        role_type: TeamRole = None,
        scratchpad_items: List[ScratchpadItem] = None,
        termination_conditions: List[TerminationCondition] = None,  # 新增终止条件列表
    ):
        if role_type is None:
            raise AgentError("role_type must be specified")
        self._is_subscribed = False  # 事件订阅状态标志
        if model_name is None and reasoner_model_name is None:
            raise AgentError("At least one model name must be provided")
        self._pending_user_input = {}  # 存储等待用户输入的状态
        self._user_input_events = {}  # 存储用户输入事件
        if not prompt_template:
            raise AgentError("Prompt template cannot be empty")

        self.tools = tools  # 先直接保存原始工具列表，在_validate_tools中处理
        self.timeout = timeout
        self.llm_timeout = llm_timeout
        self.max_iterations = max_iterations
        self.iteration_retry_delay = iteration_retry_delay
        self.memory_size = memory_size
        self.role_type = role_type
        self._validate_tools()

        self._response_cache = Cache[str](maxsize=cache_size, ttl=cache_ttl)
        self.metrics = Metrics()
        self.scratchpad_items = scratchpad_items if scratchpad_items else []
        self.stream_manager = stream_manager
        self.stopped = False
        self.history_service = history_service
        self.mcp_manager = get_mcp_manager()
        self.context = context
        self.model_name = model_name
        self.reasoner_model_name = reasoner_model_name
        self.instruction = instruction
        self.description = description
        self.team_description = team_description
        self.prompt_template = prompt_template  # 存储提示词模板

        # 初始化agentcard
        if agentcard is None:
            agentid = str(uuid.uuid4())
            self.agentcard = AgentCard(
                name=f"Agent-{agentid[:8]}",
                description=instruction[:100] if instruction else "",
                model=model_name or reasoner_model_name,
                agentid=agentid,
                tags=["planner"],  # 默认planner类型，可在外部修改
            )
        else:
            self.agentcard = agentcard

        # 初始化终止条件
        self.termination_conditions = termination_conditions or []
        # 添加默认的步数限制条件
        if not any(
            isinstance(tc, StepLimitTerminationCondition)
            for tc in self.termination_conditions
        ):
            self.termination_conditions.append(
                StepLimitTerminationCondition(self.max_iterations)
            )

    def _validate_tools(self) -> None:
        """验证并规范化工具列表，支持多种工具输入类型"""
        seen_names = set()
        normalized_tools = {}
        # 延迟导入NodeConfigManager，避免循环导入
        from ..nodes.node_config import NodeConfigManager

        config_manager = NodeConfigManager.get_instance()
        all_tools = config_manager.get_tools()  # 获取所有可用工具
        if not self.tools:  # 如果没有指定工具，则使用所有可用工具
            self.tools = all_tools
        else:
            for tool in self.tools:
                # 处理不同类型的工具输入
                if isinstance(tool, Tool):
                    normalized_tool = tool
                elif callable(tool):
                    normalized_tool = Tool.fromAnything(tool)
                elif isinstance(tool, str):
                    # 字符串类型，通过名称匹配工具
                    matched_tools = [t for t in all_tools if t.name == tool]
                    if not matched_tools:
                        raise ToolNotFoundError(f"Tool not found: {tool}")
                    normalized_tool = matched_tools[0]
                else:
                    raise AgentError(
                        f"Invalid tool type: {type(tool)}. Must be Tool instance, callable or tool name string."
                    )

                # 检查重复名称
                if normalized_tool.name in seen_names:
                    raise AgentError(
                        f"Duplicate tool name found: {normalized_tool.name}"
                    )
                seen_names.add(normalized_tool.name)

                normalized_tools[normalized_tool.name] = normalized_tool

        self.tools = normalized_tools

    def _construct_prompt(self, context: str = None, query: str = None) -> str:
        """构造提示模板，使用缓存优化工具描述生成"""

        @lru_cache(maxsize=1)  # 只缓存最新的工具描述，因为工具列表不经常变化
        def get_tools_description() -> tuple[str, str]:
            """获取工具描述和工具名称列表，只包含name、description、params和outputs字段"""
            tool_names = ", ".join(self.tools.keys())
            tools_desc = []

            for tool in self.tools.values():
                # 直接使用工具的full_description，该描述已在node_config.py中按照新格式构建
                tools_desc.append(tool.full_description)

            return "\n".join(tools_desc), tool_names

        tools_list, tool_names = get_tools_description()
        agent_prompt = None

        # 使用实例字段中的scratchpad_items
        agent_scratchpad = ""
        for i, item in enumerate(self.scratchpad_items[1:], 1):
            agent_scratchpad += item.to_string(index=i)
        if context is not None:
            agent_scratchpad += context
        # 统一提示模板构造
        values = {
            "CURRENT_TIME": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "REACT_LOOP_PROMPT": REACT_LOOP_PROMPT,
            "PLANNER_REACT_LOOP_PROMPT": PLANNER_REACT_LOOP_PROMPT,
            "tools": tools_list,
            "tool_names": tool_names,
            "query": (
                self.scratchpad_items[0].thought if self.scratchpad_items else query
            ),
            "context": agent_scratchpad,
            "max_step_num": self.max_iterations,
            "instruction": self.instruction,
            "role_description": self.description,
            "team_description": self.team_description,
        }
        agent_prompt = Template(self.prompt_template).safe_substitute(values)
        return agent_prompt

    async def _call_model(self, prompt: str, chat_id: str, model_name: str) -> str:
        start_time = time.time()
        try:
            messages = [{"role": "user", "content": prompt}]
            response = await call_llm_api(messages, model_name=model_name)
            return response
        except Exception as e:
            execution_time = time.time() - start_time
            self.metrics.record_call(execution_time, is_error=True)
            raise LLMAPIError(f"LLM API call failed: {str(e)}")

    async def _parse_action(
        self, response_text: str, chat_id: str, query: str = None
    ) -> Dict[str, Any]:
        """解析LLM响应为动作字典，支持更广泛的代码块解析和格式修复."""
        try:
            action_dict = ParseXml().parse_xml_to_dict(response_text, query)
            logger.info(f"Action dict: {action_dict}")
            return action_dict
        except Exception as e:
            error_info = (
                f"Failed to parse action from response:\n {response_text} \n{str(e)}"
            )
            logger.error(error_info)
            return {"thinking": error_info}

    @log_execution_time
    async def set_user_input(self, node_id: str, value: Any) -> None:
        """设置用户输入值

        Args:
            node_id: 节点ID
            value: 用户输入值
        """
        if node_id in self._pending_user_input:
            self._user_input_events[node_id].set()
            self._pending_user_input[node_id] = value
        else:
            raise ValueError(f"No pending user input request for node {node_id}")

    async def wait_for_user_input(
        self, node_id: str, prompt: str, chat_id: str, input_type: str
    ) -> Any:
        """等待用户输入

        Args:
            node_id: 节点ID
            prompt: 提示信息
            chat_id: 聊天会话ID

        Returns:
            Any: 用户输入值
        """
        # 创建用户输入请求事件
        if self.stream_manager:
            event = await create_user_input_required_event(node_id, prompt, input_type)
            await self.stream_manager.send_message(chat_id, event)

        # 设置等待状态
        self._pending_user_input[node_id] = None
        self._user_input_events[node_id] = asyncio.Event()

        # 等待用户输入
        await self._user_input_events[node_id].wait()

        # 获取并清理用户输入状态
        value = self._pending_user_input.pop(node_id)
        self._user_input_events.pop(node_id)

        return value

    async def stop(self) -> None:
        self.stopped = True

    def clear_context(self) -> None:
        """清空agent上下文，包括scratchpad_items和cache信息"""
        self.scratchpad_items.clear()
        logger.info(f"Agent context cleared scratchpad_items:{self.scratchpad_items}")
        self._response_cache.clear()
        logger.info("Agent context cleared")

    async def setup_event_subscriptions(self, agentid: str) -> None:
        """初始化事件订阅
        Args:
            agentid: 代理唯一ID
        """
        if self._is_subscribed:
            return

        try:
            manager = get_multi_agent_manager()
            # 订阅与自身role_type相同的事件
            await manager.subscribe(agentid, self.role_type)
            self._is_subscribed = True
            logger.info(f"Successfully subscribed to events for agent {agentid}")
        except Exception as e:
            logger.error(f"Failed to setup event subscriptions: {str(e)}")
            raise

    async def _handle_event(self, event: AgentEvent) -> None:
        """处理接收到的事件"""
        if not hasattr(event, "role_type") or not hasattr(event, "payload"):
            logger.warning(f"Invalid event format: {event}")
            return

        try:
            # 处理与自身role_type相同的事件
            if event.role_type == self.role_type:
                logger.info(f"Received role-specific event: {event.payload}")
                result = None
                if event.is_result:
                    observation = None
                    thought = None
                    if event.payload.get("result") is not None:
                        observation = event.payload.get("result")
                        thought = event.payload.get("metadata").get("origin_query")
                        self.scratchpad_items.append(
                            ScratchpadItem(observation=observation, thought=thought)
                        )
                    # 执行任务并获取结果
                    result = await self.run(
                        query=None,
                        chat_id=event.chat_id,
                        stream=True,
                        is_result=event.is_result,
                        context=event.payload.get("context"),
                    )
                else:
                    # 清空agent上下文，包括scratchpad_items和cache信息
                    self.clear_context()
                    # 执行任务并获取结果
                    result = await self.run(
                        event.payload.get("task")
                        + ":"
                        + event.payload.get("description"),
                        event.chat_id,
                        stream=True,
                        is_result=event.is_result,
                        context=event.payload.get("context"),
                    )

                logger.info(f"AgentEvent: {event} \n Result: {result}")

                # 当原始事件的is_result为false且result不为none时发送handoff事件，发送结果给父级代理
                if result is not None and event.is_result == False:
                    manager = get_multi_agent_manager()
                    origin_query = (
                        event.payload.get("task")
                        + "\n"
                        + event.payload.get("description")
                    )
                    handoff_event = manager.create_event(
                        chat_id=event.chat_id,
                        role_type=event.sender_role,
                        sender_id=self.agentcard.agentid,
                        sender_role=self.role_type,
                        payload={
                            "result": result,
                            "metadata": {
                                "agent_id": self.agentcard.agentid,
                                "timestamp": datetime.now().isoformat(),
                                "original_event_id": event.event_id,
                                "origin_query": origin_query,
                            },
                        },
                        priority=0,  # 高优先级
                        is_result=True,
                    )
                    await manager.publish_event(handoff_event)
                    logger.info(
                        f"Handoff event sent to {event.sender_id} "
                        f"(original event: {event.event_id})"
                    )
        except Exception as e:
            logger.error(f"Error handling event {event.event_id}: {str(e)}")
            if self.stream_manager and hasattr(event, "sender_id"):
                await self.stream_manager.send_message(
                    event.sender_id, await create_agent_error_event(str(e))
                )

    async def run(
        self,
        query: str,
        chat_id: str,
        stream: bool = True,
        is_result: bool = False,
        context: str = None,
    ) -> str:
        if stream:
            self.stream_manager = StreamManager.get_instance()
        """执行Agent的主要逻辑

        Args:
            query: 用户输入的查询文本
            chat_id: 聊天会话ID，用于隔离不同会话的上下文和缓存
            stream: 是否启用事件流式传输

        Returns:
            str: Agent的响应结果
        """
        if self.stopped:
            # 发送agent结束事件
            if stream:
                event = await create_agent_complete_event("已停止")
                await self.stream_manager.send_message(chat_id, event)
            return
        try:
            # 发送agent开始事件
            if not is_result:
                self.scratchpad_items.append(
                    ScratchpadItem(
                        is_origin_query=True,
                        thought=query,
                    )
                )
            if stream:
                event = await create_agent_start_event(query)
                await self.stream_manager.send_message(chat_id, event)

            # 使用实例字段存储思考和执行过程
            observations: List[str] = []
            iteration_count = 0
            action = None
            thought = None
            observation = None
            final_answer = None
            handoff_flag = False  # 新增handoff标志

            while not handoff_flag:
                # 检查终止条件
                termination_ctx = {
                    "current_step": iteration_count,
                    "current_action": action,
                    "current_thought": thought,
                    "current_observation": observation,
                    "final_answer": final_answer,
                    "error_occurred": False,  # 会在异常处理中更新
                }

                try:
                    if any(
                        tc.should_terminate(self, **termination_ctx)
                        for tc in self.termination_conditions
                    ):
                        logger.info(
                            f"Termination condition met at step {iteration_count}"
                        )
                        break
                except Exception as e:
                    termination_ctx["error_occurred"] = True
                    logger.error(f"Error checking termination conditions: {str(e)}")
                    # 继续执行让ErrorTerminationCondition处理
                if is_result:
                    is_result = False
                    continue
                if self.stopped:
                    # 发送agent结束事件
                    if stream:
                        event = await create_agent_complete_event("已停止")
                        await self.stream_manager.send_message(chat_id, event)
                    return
                iteration_count += 1
                try:
                    prompt = self._construct_prompt(context=context)
                    logger.info(f"Prompt for iteration {iteration_count}: \n{prompt}")
                    model_response = None
                    if self.reasoner_model_name:
                        model_response = await asyncio.wait_for(
                            self._call_model(
                                prompt,
                                chat_id,
                                self.reasoner_model_name,
                            ),
                            timeout=self.llm_timeout,
                        )
                    else:
                        model_response = await asyncio.wait_for(
                            self._call_model(prompt, chat_id, self.model_name),
                            timeout=self.llm_timeout,
                        )
                    logger.info(f"LLM Response : \n{model_response}")
                    if not model_response or not isinstance(model_response, str):
                        raise ValueError(
                            "LLM API call failed response is empty or not str type"
                        )
                    result_dict = None
                    result_dict = await self._parse_action(
                        model_response, chat_id, query
                    )
                    action_dict = result_dict.get("tool", {})
                    action = action_dict.get("name", "")
                    action_input = action_dict.get("params", "")
                    thought = result_dict.get("thinking", {})
                    observation = ""

                    logger.info(f"thinking: {thought}")
                    logger.info(f"action: {action}")

                    # 发送agent思考事件
                    if stream:
                        event = await create_agent_thinking_event(f"{thought}")
                        await self.stream_manager.send_message(chat_id, event)

                    if action == "final_answer":
                        final_answer = action_input
                        break

                    if not action or action not in self.tools:
                        raise ToolNotFoundError(f"Invalid action: {action}")

                    tool = self.tools[action]

                    action_id = str(uuid.uuid4())
                    # 发送动作开始事件
                    if stream:
                        event = await create_action_start_event(
                            action, action_input, action_id
                        )
                        await self.stream_manager.send_message(chat_id, event)

                    retry_count = 0
                    while retry_count <= tool.max_retries:
                        if self.stopped:
                            # 发送agent结束事件
                            if stream:
                                event = await create_agent_complete_event("已停止")
                                await self.stream_manager.send_message(chat_id, event)
                            return
                        try:
                            # 发送工具进度事件
                            if stream:
                                event = await create_tool_progress_event(
                                    action, "running", action_input, action_id
                                )
                                await self.stream_manager.send_message(chat_id, event)
                            if action == "user_input":
                                action_input["chat_id"] = chat_id
                                action_input["node_id"] = f"{chat_id}-{uuid.uuid1()}"
                                action_input["agent"] = self
                            need_history = action_input.get("need_history", False)
                            if action == "chat" and need_history:
                                # 在需要历史记录时才拼接observations
                                observations_str = "\n".join(observations)
                                action_input["history_action_result"] = observations_str
                            if action == "workflow_execute":
                                action_input["chat_id"] = chat_id
                                action_input["stream_manager"] = self.stream_manager
                            if action == "handoff":
                                action_input["sender_id"] = self.agentcard.agentid
                                action_input["sender_role"] = self.role_type
                                action_input["chat_id"] = chat_id
                                if action_input.get("target_role") == "reporter":
                                    agent_scratchpad = ""
                                    for i, item in enumerate(
                                        self.scratchpad_items[1:], 1
                                    ):
                                        if item.action != "handoff":
                                            agent_scratchpad += item.observation
                                    action_input["context"] = agent_scratchpad

                            # 执行工具
                            if action == "browser_agent":
                                # browser_agent需要在主事件循环中执行
                                loop = asyncio.get_running_loop()
                                observation = await loop.run_in_executor(
                                    None, lambda: asyncio.run(tool.run(action_input))
                                )
                            elif tool.is_async:
                                observation = await tool.run(action_input)
                            else:
                                observation = tool.run(action_input)
                            self.metrics.record_tool_usage(action)

                            # 处理handoff特殊逻辑
                            if action == "handoff":
                                handoff_flag = True  # 设置退出标志
                                final_answer = None  # 清空最终答案

                            if action == "chat" and need_history:
                                del action_input["history_action_result"]

                            # 发送动作完成事件
                            if stream:
                                event = await create_action_complete_event(
                                    action, observation, action_id
                                )
                                await self.stream_manager.send_message(chat_id, event)

                            break  # 工具执行成功，退出重试循环

                        except Exception as e:
                            retry_count += 1
                            self.metrics.record_retry()
                            error_msg = str(e)

                            # 发送工具重试事件
                            if stream:
                                event = await create_tool_retry_event(
                                    action, retry_count, tool.max_retries, error_msg
                                )
                                await self.stream_manager.send_message(chat_id, event)

                            if retry_count > tool.max_retries:
                                raise ToolExecutionError(
                                    f"Tool {action} failed after {retry_count} retries: {error_msg}"
                                )

                            await asyncio.sleep(tool.retry_delay)

                    # 将当前迭代的思考和执行过程保存为ScratchpadItem对象
                    scratchpad_item = ScratchpadItem(
                        thought=thought, action=action, observation=observation
                    )
                    self.scratchpad_items.append(scratchpad_item)
                    observations.append(observation)
                except ActionBadException as e:
                    logger.error(f"[{chat_id}] {e.message}")
                    final_answer = e.message
                    break
                except asyncio.TimeoutError:
                    error_msg = (
                        f"Model response timeout after {self.llm_timeout} seconds"
                    )
                    logger.error(f"[{chat_id}] {error_msg}")
                    await asyncio.sleep(self.iteration_retry_delay)
                    continue
                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"[{chat_id}] {error_msg}")
                    # 错误情况下添加一个错误项
                    error_item = ScratchpadItem(
                        thought=error_msg, action="", observation=error_msg
                    )
                    self.scratchpad_items.append(error_item)
                    await asyncio.sleep(self.iteration_retry_delay)
                    continue

            # handoff情况不发送final_answer
            # 当触发终止条件但未获得最终答案时
            if (
                not handoff_flag
                and not final_answer
                and iteration_count >= self.max_iterations
            ):
                error_msg = (
                    f"Failed to get final answer after {self.max_iterations} iterations"
                )
                raise AgentError(error_msg)

            # 发送agent完成事件（handoff不发送）
            if not handoff_flag and stream:
                event = await create_agent_complete_event(final_answer)
                await self.stream_manager.send_message(chat_id, event)

            # handoff情况返回None，其他情况返回final_answer
            return final_answer if not handoff_flag else None
        except Exception as e:
            error_msg = str(e)
            if stream:
                event = await create_agent_error_event(error_msg)
                await self.stream_manager.send_message(chat_id, event)

            # 发布错误事件
            manager = get_multi_agent_manager()
            error_event = manager.create_event(
                chat_id=chat_id,
                role_type=TeamRole.COORDINATOR,
                sender_id=self.agentcard.agentid,
                sender_role=self.role_type,
                priority=1,
                payload={"error": error_msg},
            )
            await manager.publish_event(error_event)
            raise
        finally:
            try:
                # 安全清理资源，仅当有内容时执行
                with contextlib.suppress(AttributeError):
                    if self._pending_user_input:
                        logger.debug(
                            f"Clearing {len(self._pending_user_input)} pending inputs"
                        )
                        self._pending_user_input.clear()

                    if self._user_input_events:
                        logger.debug(
                            f"Clearing {len(self._user_input_events)} input events"
                        )
                        self._user_input_events.clear()

            except Exception as e:
                logger.error(f"资源清理时发生异常: {str(e)}", exc_info=True)
                raise
            finally:
                logger.info(f"Agent execution completed for chat {chat_id}")
