from datetime import datetime
from typing import List, Dict, Any, Optional, Union, TypeVar, Generic
from dataclasses import dataclass, field, asdict
import asyncio
import logging
import time
import json
import os
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
from ..agent.prompt.cot_prompt import COT_PROMPT_TEMPLATES
from ..agent.prompt.cot_mcp_prompt import COT_MCP_PROMPT_TEMPLATES
from ..agent.prompt.cot_browser_use_prompt import COT_BROWSER_USE_PROMPT_TEMPLATES
from ..agent.prompt.cot_workflow_prompt import COT_WORKFLOW_PROMPT_TEMPLATES
from ..api.history_service import HistoryService
from ..manager.mcp_manager import get_mcp_manager, initialize_mcp_manager
from .parse_xml import ParseXml
from .base_agent import (
    AgentError,
    Metrics,
    Cache,
    LLMAPIError,
    Tool,
    ToolExecutionError,
    ToolNotFoundError,
    AgentCard,
    ScratchpadItem,
)

logger = logging.getLogger(__name__)


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


class AgentEngine:
    _instances: Dict[str, "AgentEngine"] = {}  # 存储所有AgentEngine实例

    @classmethod
    def get_instance(cls, chat_id: str) -> Optional["AgentEngine"]:
        """获取指定chat_id对应的Agent实例"""
        return cls._instances.get(chat_id)

    @classmethod
    def register_instance(cls, chat_id: str, instance: "AgentEngine") -> None:
        """注册Agent实例"""
        cls._instances[chat_id] = instance

    @classmethod
    def remove_instance(cls, chat_id: str) -> None:
        """移除Agent实例"""
        if chat_id in cls._instances:
            del cls._instances[chat_id]

    @classmethod
    def stop(self, chat_id: str) -> None:
        self.get_instance(chat_id).stop()

    def __init__(
        self,
        tools: List[Tool],
        instruction: str = "",
        timeout: int = 120,
        llm_timeout: int = 60,
        max_iterations: int = 10,
        iteration_retry_delay: int = 60,
        memory_size: int = 10,
        cache_size: int = 100,
        cache_ttl: int = 3600,
        stream_manager=None,
        history_service: HistoryService = None,
        agentid: str = None,
        agentmodel: str = None,
        context: str = None,
        model_name: str = None,
        reasoner_model_name: str = None,
    ):
        if model_name is None and reasoner_model_name is None:
            raise AgentError("At least one model name must be provided")
        self._pending_user_input = {}  # 存储等待用户输入的状态
        self._user_input_events = {}  # 存储用户输入事件
        if not tools:
            raise AgentError("At least one tool must be provided")

        # 如果有agentid，获取智能体配置
        if agentid:
            from src.agent.agent_manager import AgentManager

            agent_data = AgentManager().get_agent(agentid)
            if agent_data:
                instruction = agent_data.system_prompt or instruction
                # TODO: 根据agent_data.tools过滤/补充工具集合

        self.tools = {tool.name: tool for tool in tools}
        self.instruction = instruction
        self.timeout = timeout
        self.llm_timeout = llm_timeout
        self.max_iterations = max_iterations
        self.iteration_retry_delay = iteration_retry_delay
        self.memory_size = memory_size
        self._validate_tools()

        self._response_cache = Cache[str](maxsize=cache_size, ttl=cache_ttl)
        self.metrics = Metrics()
        self.stream_manager = stream_manager
        self.stopped = False
        self.history_service = history_service
        self.agentid = agentid
        self.mcp_manager = get_mcp_manager()
        self.agentmodel = agentmodel
        self.context = context
        self.model_name = model_name
        self.reasoner_model_name = reasoner_model_name

    def _validate_tools(self) -> None:
        seen_names = set()
        for tool_name, tool in self.tools.items():
            if not isinstance(tool, Tool):
                raise AgentError(
                    f"Invalid tool type: {type(tool)}. Must be Tool instance."
                )
            if tool_name in seen_names:
                raise AgentError(f"Duplicate tool name found: {tool_name}")
            seen_names.add(tool_name)

    def _construct_prompt(
        self, query: str, scratchpad_items: List[ScratchpadItem]
    ) -> str:
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

        # 将scratchpad_items列表中的对象拼接成Markdown列表格式的字符串
        agent_scratchpad = ""
        for i, item in enumerate(scratchpad_items, 1):
            agent_scratchpad += item.to_string(index=i)

        if self.agentmodel == "mcp-agent":
            mcp_tools = get_mcp_manager().get_tools_formated_prompt()
            values = {
                "current_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "instruction": self.instruction if self.instruction else "",
                "tools": tools_list,
                "tool_names": tool_names,
                "query": query,
                "agent_scratchpad": agent_scratchpad,
                "mcp_tools": mcp_tools,
                "context": self.context if self.context else "",
            }
            agent_prompt = Template(COT_MCP_PROMPT_TEMPLATES).safe_substitute(values)
        elif self.agentmodel == "browser-agent":
            values = {
                "current_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "query": query,
                "agent_scratchpad": agent_scratchpad,
                "context": self.context if self.context else "",
            }
            agent_prompt = Template(COT_BROWSER_USE_PROMPT_TEMPLATES).safe_substitute(
                values
            )
        elif self.agentmodel == "workflow":
            values = {
                "current_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "instruction": self.instruction if self.instruction else "",
                "tools": tools_list,
                "tool_names": tool_names,
                "query": query,
                "agent_scratchpad": agent_scratchpad,
                "context": self.context if self.context else "",
            }
            agent_prompt = Template(COT_WORKFLOW_PROMPT_TEMPLATES).safe_substitute(
                values
            )
        else:
            values = {
                "current_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "instruction": self.instruction if self.instruction else "",
                "tools": tools_list,
                "tool_names": tool_names,
                "query": query,
                "agent_scratchpad": agent_scratchpad,
                "context": agent_scratchpad,
            }
            agent_prompt = Template(COT_PROMPT_TEMPLATES).safe_substitute(values)
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

    async def _parse_action(self, response_text: str, chat_id: str) -> Dict[str, Any]:
        """解析LLM响应为动作字典，支持更广泛的代码块解析和格式修复."""
        try:
            action_dict = ParseXml().parse_xml_to_dict(response_text)
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
        if self.agentid:
            self.multi_agent_manager.unregister_agent(self.agentid)
        self.stopped = True

    async def run(self, query: str, chat_id: str, stream: bool = True) -> str:
        # 注册当前实例
        self.register_instance(chat_id, self)

        # 检查并处理待处理事件
        if self.agentid:
            event = await self.multi_agent_manager.get_next_event(self.agentid)
            if event:
                query = f"事件处理: {event.event_type.value}\n事件内容: {event.payload}\n原始查询: {query}"
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
            if stream and self.stream_manager:
                event = await create_agent_complete_event("已停止")
                await self.stream_manager.send_message(chat_id, event)
            return
        try:
            # 发送agent开始事件
            if stream and self.stream_manager:
                event = await create_agent_start_event(query)
                await self.stream_manager.send_message(chat_id, event)

            # 定义列表来存储思考和执行过程对象及观察结果
            scratchpad_items: List[ScratchpadItem] = []
            observations: List[str] = []
            iteration_count = 0
            final_answer = None

            while iteration_count < self.max_iterations:
                if self.stopped:
                    # 发送agent结束事件
                    if stream and self.stream_manager:
                        event = await create_agent_complete_event("已停止")
                        await self.stream_manager.send_message(chat_id, event)
                    return
                iteration_count += 1
                try:
                    if self.agentmodel == "mcp-agent":
                        await initialize_mcp_manager()
                    prompt = self._construct_prompt(query, scratchpad_items)
                    logger.info(f"Prompt for iteration {iteration_count}: \n{prompt}")
                    model_response = await asyncio.wait_for(
                        self._call_model(prompt, chat_id, self.model_name),
                        timeout=self.llm_timeout,
                    )
                    if not model_response or not isinstance(model_response, str):
                        raise ValueError(
                            "LLM API call failed response is empty or not str type"
                        )
                    result_dict = None
                    result_dict = await self._parse_action(model_response, chat_id)
                    action_dict = result_dict.get("tool", {})
                    action = action_dict.get("name", "")
                    action_input = action_dict.get("params", "")
                    thought = result_dict.get("thinking", {})
                    observation = ""

                    logger.info(f"thinking: {thought}")
                    logger.info(f"action: {action}")

                    # 发送agent思考事件
                    if stream and self.stream_manager:
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
                    if stream and self.stream_manager:
                        event = await create_action_start_event(
                            action, action_input, action_id
                        )
                        await self.stream_manager.send_message(chat_id, event)

                    retry_count = 0
                    while retry_count <= tool.max_retries:
                        if self.stopped:
                            # 发送agent结束事件
                            if stream and self.stream_manager:
                                event = await create_agent_complete_event("已停止")
                                await self.stream_manager.send_message(chat_id, event)
                            return
                        try:
                            # 发送工具进度事件
                            if stream and self.stream_manager:
                                event = await create_tool_progress_event(
                                    action, "running", action_input, action_id
                                )
                                await self.stream_manager.send_message(chat_id, event)
                            if action == "user_input":
                                action_input["chat_id"] = chat_id
                                action_input["node_id"] = f"{chat_id}-{uuid.uuid1()}"
                            need_history = action_input.get("need_history", False)
                            if action == "chat" and need_history:
                                # 在需要历史记录时才拼接observations
                                observations_str = "\n".join(observations)
                                action_input["history_action_result"] = observations_str
                            if action == "workflow_execute":
                                action_input["chat_id"] = chat_id
                                action_input["stream_manager"] = self.stream_manager

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

                            if action == "chat" and need_history:
                                del action_input["history_action_result"]

                            # 发送动作完成事件
                            if stream and self.stream_manager:
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
                            if stream and self.stream_manager:
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
                    scratchpad_items.append(scratchpad_item)
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
                    scratchpad_items.append(error_item)
                    await asyncio.sleep(self.iteration_retry_delay)
                    continue

            if not final_answer:
                error_msg = (
                    f"Failed to get final answer after {self.max_iterations} iterations"
                )
                raise AgentError(error_msg)

            # 发送agent完成事件
            if stream and self.stream_manager:
                event = await create_agent_complete_event(final_answer)
                await self.stream_manager.send_message(chat_id, event)

            if self.history_service:
                self.history_service.update_history_summary(chat_id, f"{final_answer}")
            return final_answer

        except Exception as e:
            error_msg = str(e)
            if stream and self.stream_manager:
                event = await create_agent_error_event(error_msg)
                await self.stream_manager.send_message(chat_id, event)
            raise
        finally:
            # 清理实例
            self.remove_instance(chat_id)
