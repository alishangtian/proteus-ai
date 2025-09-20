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
                # 根据 agent_data.tools 过滤/补充工具集合
                try:
                    allowed_tools = set(agent_data.tools or [])
                except Exception:
                    allowed_tools = set()
                if allowed_tools:
                    original_tools = dict(self.tools)
                    self.tools = {
                        name: tool
                        for name, tool in original_tools.items()
                        if name in allowed_tools
                    }
                    missing = allowed_tools - set(self.tools.keys())
                    if missing:
                        logger.warning(
                            f"Agent {agentid} 请求的工具不在当前工具集合中: {missing}"
                        )

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

            # 按工具名称排序并为每个工具描述前添加序号，便于阅读
            for i, tool in enumerate(
                sorted(self.tools.values(), key=lambda x: x.name), 1
            ):
                tools_desc.append(f"{i}. {tool.full_description}")

            return "\n".join(tools_desc), tool_names

        tools_list, tool_names = get_tools_description()
        agent_prompt = None

        # 将scratchpad_items列表转换为单个Markdown表格（历史推理链）
        table_lines: List[str] = []
        for i, item in enumerate(scratchpad_items, 1):
            tbl = item.to_react_context_table(index=i)
            lines = [ln for ln in tbl.strip().splitlines() if ln.strip() != ""]
            if i == 1:
                table_lines.extend(lines)
            else:
                # 只追加数据行（最后一行）
                table_lines.append(lines[-1])
        agent_scratchpad = "\n".join(table_lines) + ("\n" if table_lines else "")

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

    # Public convenience wrappers for clearer API and easier testing
    def build_prompt(self, query: str, scratchpad_items: List[ScratchpadItem]) -> str:
        """
        构建模型 prompt 的公共方法（包装内部实现，便于单元测试与外部调用）。

        Args:
            query: 用户查询文本
            scratchpad_items: Scratchpad 条目列表

        Returns:
            agent prompt 字符串
        """
        return self._construct_prompt(query, scratchpad_items)

    async def get_model_response(
        self, prompt: str, chat_id: str, model_name: Optional[str] = None
    ) -> str:
        """
        调用模型并返回模型原始响应（异步）。

        Args:
            prompt: 要发送给模型的 prompt
            chat_id: 会话 id（用于上报/日志）
            model_name: 可选模型名称，默认使用实例的 self.model_name

        Returns:
            模型返回的字符串
        """
        model = model_name or self.model_name
        return await self._call_model(prompt, chat_id, model)

    async def parse_model_response(
        self, response_text: str, chat_id: str
    ) -> Dict[str, Any]:
        """
        解析模型响应为动作字典（异步包装 parse 实现）。

        Args:
            response_text: 模型返回的字符串
            chat_id: 会话 id

        Returns:
            解析后的动作字典
        """
        return await self._parse_action(response_text, chat_id)

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

    async def _execute_tool(
        self,
        tool,
        action: str,
        action_input: Dict[str, Any],
        chat_id: str,
        action_id: str,
        stream: bool,
    ) -> str:
        """
        统一工具执行逻辑（含同步/异步兼容、browser-agent 特殊处理、重试与事件上报）。
        返回观测结果字符串（observation）。
        """
        retry_count = 0
        last_error = None
        while retry_count <= tool.max_retries:
            if self.stopped:
                # 发送agent结束事件
                if stream and self.stream_manager:
                    event = await create_agent_complete_event("已停止")
                    await self.stream_manager.send_message(chat_id, event)
                raise AgentError("Agent stopped")
            try:
                # 发送工具进度事件
                if stream and self.stream_manager:
                    event = await create_tool_progress_event(
                        action, "running", action_input, action_id
                    )
                    await self.stream_manager.send_message(chat_id, event)

                # 特殊action预处理
                if action == "user_input":
                    action_input["chat_id"] = chat_id
                    action_input["node_id"] = f"{chat_id}-{uuid.uuid1()}"
                need_history = action_input.get("need_history", False)
                if action == "chat" and need_history:
                    observations_str = "\n".join(self._gather_observations())
                    action_input["history_action_result"] = observations_str
                if action == "workflow_execute":
                    action_input["chat_id"] = chat_id
                    action_input["stream_manager"] = self.stream_manager

                # 实际执行工具，兼容同步/异步实现
                if action == "browser_agent":
                    # browser_agent 需要在主事件循环外执行，因此使用run_in_executor包装asyncio.run
                    loop = asyncio.get_running_loop()
                    observation = await loop.run_in_executor(
                        None, lambda: asyncio.run(tool.run(action_input))
                    )
                elif getattr(tool, "is_async", False):
                    observation = await tool.run(action_input)
                else:
                    # 同步调用保持兼容
                    observation = tool.run(action_input)

                # 记录度量
                self.metrics.record_tool_usage(action)

                if action == "chat" and need_history:
                    # 清理临时历史字段
                    action_input.pop("history_action_result", None)

                # 发送动作完成事件
                if stream and self.stream_manager:
                    event = await create_action_complete_event(
                        action, observation, action_id
                    )
                    await self.stream_manager.send_message(chat_id, event)

                return observation

            except Exception as e:
                retry_count += 1
                last_error = str(e)
                self.metrics.record_retry()

                # 发送工具重试事件
                if stream and self.stream_manager:
                    event = await create_tool_retry_event(
                        action, retry_count, tool.max_retries, last_error
                    )
                    await self.stream_manager.send_message(chat_id, event)

                if retry_count > tool.max_retries:
                    raise ToolExecutionError(
                        f"Tool {action} failed after {retry_count} retries: {last_error}"
                    )
                await asyncio.sleep(tool.retry_delay)

    def _gather_observations(self) -> List[str]:
        """从当前scratchpad或内部缓存收集观测，用于构建历史上下文（可扩展）。"""
        # 目前仅从最近的scratchpad_items输出观测文本（如果存在）
        try:
            return [
                item.observation
                for item in getattr(self, "_last_observations", [])
                if item.observation
            ]
        except Exception:
            return []

    async def _process_iteration(
        self,
        query: str,
        chat_id: str,
        scratchpad_items: List[ScratchpadItem],
        observations: List[str],
        iteration_count: int,
        stream: bool,
    ) -> tuple[Optional[str], Optional[ScratchpadItem], Optional[str]]:
        """
        将单次迭代的逻辑提取为独立方法，返回 (final_answer, scratchpad_item, observation)
        以便单元测试与重用。
        """
        # 在需要时初始化 mcp 管理器
        if self.agentmodel == "mcp-agent":
            await initialize_mcp_manager()

        # 生成 prompt 并调用模型获取响应
        prompt = self._construct_prompt(query, scratchpad_items)
        logger.info(f"Prompt for iteration {iteration_count}: \n{prompt}")
        model_response = await asyncio.wait_for(
            self._call_model(prompt, chat_id, self.model_name), timeout=self.llm_timeout
        )

        if not model_response or not isinstance(model_response, str):
            raise ValueError("LLM API call failed response is empty or not str type")

        # 解析模型响应为动作结构
        result_dict = await self._parse_action(model_response, chat_id)
        action_dict = result_dict.get("tool", {})
        action = action_dict.get("name", "")
        action_input = action_dict.get("params", {}) or {}
        thought = result_dict.get("thinking", {})

        observation = ""

        logger.info(f"thinking: {thought}")
        logger.info(f"action: {action}")

        # 发送agent思考事件
        if stream and self.stream_manager:
            event = await create_agent_thinking_event(f"{thought}")
            await self.stream_manager.send_message(chat_id, event)

        # 处理 final_answer 快速返回
        if action == "final_answer":
            return action_input, None, None

        # 校验动作
        if not action or action not in self.tools:
            raise ToolNotFoundError(f"Invalid action: {action}")

        tool = self.tools[action]
        action_id = str(uuid.uuid4())

        # 发送动作开始事件
        if stream and self.stream_manager:
            event = await create_action_start_event(action, action_input, action_id)
            await self.stream_manager.send_message(chat_id, event)

        # 使用提取的方法统一执行工具，并返回观测结果
        observation = await self._execute_tool(
            tool=tool,
            action=action,
            action_input=action_input,
            chat_id=chat_id,
            action_id=action_id,
            stream=stream,
        )

        # 将当前迭代的思考和执行过程保存为ScratchpadItem对象
        scratchpad_item = ScratchpadItem(
            thought=thought,
            action=action,
            observation=observation,
            tool_execution_id="",
            role_type="",
        )
        return None, scratchpad_item, observation

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
        self,
        node_id: str,
        prompt: str,
        chat_id: str,
        input_type: str,
        agent_id: str = None,
    ) -> Any:
        """等待用户输入

        Args:
            node_id: 节点ID
            prompt: 提示信息
            chat_id: 聊天会话ID
            agent_id: 智能体ID（可选），用于在事件中标识来源agent

        Returns:
            Any: 用户输入值
        """
        # 创建用户输入请求事件，使用关键字参数明确传递，确保 agent_id 不会被位置参数错位丢失
        if self.stream_manager:
            event = await create_user_input_required_event(
                node_id=node_id,
                prompt=prompt,
                input_type=input_type,
                agent_id=agent_id,
            )
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
                    # 将单次迭代逻辑委派到独立方法，便于测试与维护
                    final_answer_local, scratchpad_item, observation = (
                        await self._process_iteration(
                            query=query,
                            chat_id=chat_id,
                            scratchpad_items=scratchpad_items,
                            observations=observations,
                            iteration_count=iteration_count,
                            stream=stream,
                        )
                    )
                    if scratchpad_item:
                        scratchpad_items.append(scratchpad_item)
                    if observation:
                        observations.append(observation)
                    if final_answer_local:
                        final_answer = final_answer_local
                        break
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
                        thought=error_msg,
                        action="",
                        observation=error_msg,
                        tool_execution_id="",
                        role_type="",
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
