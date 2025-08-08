from datetime import datetime
from abc import ABC, abstractmethod
import re
from typing import List, Dict, Any
import asyncio
import logging
import time
import uuid
import threading
import json
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
from ..manager.mcp_manager import get_mcp_manager
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
from ..manager.multi_agent_manager import TeamRole
from .terminition import TerminationCondition, StepLimitTerminationCondition
from ..utils.redis_cache import RedisCache
from .common.configuration import AgentConfiguration
from langfuse import observe

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


class ReactAgent:
    _agent_cache: Dict[str, List["ReactAgent"]] = {}
    _cache_lock = threading.Lock()

    @classmethod
    @observe(name="get_agents", capture_input=True, capture_output=True)
    def get_agents(cls, chat_id: str) -> List["ReactAgent"]:
        """获取指定chat_id下的agent列表副本"""
        with cls._cache_lock:
            return list(cls._agent_cache.get(chat_id, []))

    @classmethod
    @observe(name="set_agents", capture_input=True, capture_output=True)
    def set_agents(cls, chat_id: str, agents: List["ReactAgent"]) -> None:
        """设置指定chat_id下的agent列表"""
        with cls._cache_lock:
            cls._agent_cache[chat_id] = agents.copy()

    @classmethod
    @observe(name="clear_agents", capture_input=True, capture_output=True)
    def clear_agents(cls, chat_id: str) -> None:
        """清除指定chat_id的agent缓存"""
        with cls._cache_lock:
            cls._agent_cache.pop(chat_id, None)

    @observe(name="__init__", capture_input=True, capture_output=True)
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
        context: str = None,
        model_name: str = None,
        reasoner_model_name: str = None,
        agentcard: AgentCard = None,
        role_type: TeamRole = None,
        scratchpad_items: List[ScratchpadItem] = None,
        termination_conditions: List[TerminationCondition] = None,  # 新增终止条件列表
        conversation_id: str = None,  # 新增会话ID参数
        langfuse_trace: Any = None,  # Langfuse追踪对象
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
        self.conversation_id = conversation_id

        self.scratchpad_items = scratchpad_items if scratchpad_items else []

        self.stream_manager = stream_manager
        self.stopped = False
        self.mcp_manager = get_mcp_manager()
        self.context = context
        self.model_name = model_name
        self.reasoner_model_name = reasoner_model_name
        self.instruction = instruction
        self.description = description
        self.team_description = team_description
        self.prompt_template = prompt_template  # 存储提示词模板
        self.langfuse_trace = langfuse_trace  # 存储Langfuse追踪对象

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
        # Add step limit termination if missing
        has_step_limit = any(
            isinstance(tc, StepLimitTerminationCondition)
            for tc in self.termination_conditions
        )
        if not has_step_limit:
            self.termination_conditions.append(
                StepLimitTerminationCondition(self.max_iterations)
            )

    def _validate_tools(self) -> None:
        """验证并规范化工具列表"""
        from ..nodes.node_config import NodeConfigManager

        config_manager = NodeConfigManager.get_instance()
        all_tools = config_manager.get_tools()

        if not self.tools:
            self.tools = all_tools
            return

        normalized_tools = {}
        for tool in self.tools:
            if isinstance(tool, Tool):
                normalized_tool = tool
            elif callable(tool):
                # Directly convert callable to Tool
                normalized_tool = Tool.from_callable(tool)
            elif isinstance(tool, str):
                normalized_tool = next((t for t in all_tools if t.name == tool), None)
                if not normalized_tool:
                    raise ToolNotFoundError(f"Tool not found: {tool}")
            else:
                raise AgentError(f"Invalid tool type: {type(tool)}")

            if normalized_tool.name in normalized_tools:
                raise AgentError(f"Duplicate tool name: {normalized_tool.name}")

            normalized_tools[normalized_tool.name] = normalized_tool

        self.tools = normalized_tools

    @observe(
        name="_load_historical_scratchpad_items",
        capture_input=True,
        capture_output=True,
    )
    def _load_historical_scratchpad_items(
        self, conversation_id: str, size: int = 5, expire_hours: int = 12
    ) -> List[ScratchpadItem]:
        """从Redis中加载指定时间内最近size条的历史scratchpad_items

        Args:
            conversation_id: 会话ID，作为Redis中的唯一标识
            size: 要获取的记录数量，默认5条
            expire_hours: 过期时间（小时），默认12小时

        Returns:
            List[ScratchpadItem]: 指定时间内最近size条的历史迭代信息，按时间戳升序排列（先发生的在前）
        """
        try:
            redis_cache = RedisCache()
            redis_key = f"historical_scratchpad:{conversation_id}"

            # 计算过期时间戳
            expire_timestamp = time.time() - (expire_hours * 60 * 60)

            # 删除过期数据
            redis_cache.zremrangebyscore(redis_key, 0, expire_timestamp)

            # 获取总数量
            total_count = redis_cache.zcard(redis_key)
            if total_count == 0:
                logger.info(
                    f"未找到12小时内的历史迭代信息 (conversation_id: {conversation_id})"
                )
                return []

            # 计算起始位置：获取最新的size条记录，但要按时间升序返回
            # 如果总数小于等于size，则获取全部；否则获取最新的size条
            if total_count <= size:
                start_index = 0
                end_index = total_count - 1
            else:
                start_index = total_count - size
                end_index = total_count - 1

            # 从Redis有序集合中获取指定范围的记录（按时间戳升序）
            history_data = redis_cache.zrange(redis_key, start_index, end_index)

            historical_items = []
            for item_json in history_data:
                try:
                    item_dict = json.loads(item_json)
                    scratchpad_item = ScratchpadItem(
                        thought=item_dict.get("thought", ""),
                        action=item_dict.get("action", ""),
                        observation=item_dict.get("observation", ""),
                        is_origin_query=item_dict.get("is_origin_query", False),
                    )
                    historical_items.append(scratchpad_item)
                except (json.JSONDecodeError, Exception) as e:
                    logger.warning(f"解析历史scratchpad_item失败: {e}")
                    continue

            if historical_items:
                logger.info(
                    f"成功加载 {len(historical_items)} 条历史迭代信息 (conversation_id: {conversation_id}, {expire_hours}小时内, 按时间升序)"
                )
            else:
                logger.info(
                    f"未找到{expire_hours}小时内的历史迭代信息 (conversation_id: {conversation_id})"
                )

            return historical_items

        except Exception as e:
            logger.error(f"从Redis加载历史信息失败: {e}")
            return []

    @observe(
        name="_save_conversation_to_redis", capture_input=True, capture_output=True
    )
    def _save_conversation_to_redis(
        self,
        conversation_id: str,
        user_query: str = None,
        assistant_answer: str = None,
        expire_hours: int = 12,
        max_retries: int = 3,
        retry_delay: float = 0.1,
    ):
        """将对话记录保存到Redis有序集合中，使用时间戳作为score
        每次调用只保存一个字段（user或assistant），使用list存储单个键值对

        Args:
            conversation_id: 会话ID
            user_query: 用户问题（与assistant_answer二选一）
            assistant_answer: 助手回答（与user_query二选一）
            expire_hours: 过期时间（小时），默认12小时
            max_retries: 最大重试次数，默认3次
            retry_delay: 重试延迟时间（秒），默认0.1秒
        """
        retry_count = 0
        last_exception = None

        while retry_count <= max_retries:
            try:
                redis_cache = RedisCache()
                redis_key = f"conversation_history:{conversation_id}"
                current_timestamp = time.time()

                # 构造对话记录（每次只保存一个字段）
                record = {}
                if user_query:
                    record = {"user": user_query}
                elif assistant_answer:
                    record = {"assistant": assistant_answer}
                else:
                    raise ValueError("必须提供user_query或assistant_answer")

                # 转换为JSON字符串
                record_json = json.dumps(record, ensure_ascii=False)

                # 添加新记录
                redis_cache.zadd(redis_key, {record_json: current_timestamp})

                # 清理过期数据
                expire_timestamp = current_timestamp - (expire_hours * 60 * 60)
                redis_cache.zremrangebyscore(redis_key, 0, expire_timestamp)

                # 获取当前数量
                total_count = redis_cache.zcard(redis_key)

                # 限制总数量：保留最新的100条
                if total_count > 100:
                    # 删除最旧的（排名从0到total_count-101）的元素
                    redis_cache.zremrangebyrank(redis_key, 0, total_count - 101)

                logger.info(
                    f"成功保存对话记录到Redis (conversation_id: {conversation_id}, "
                    f"timestamp: {current_timestamp}, total_items: {total_count})"
                )
                return  # 成功则直接返回

            except Exception as e:
                last_exception = e
                retry_count += 1
                logger.warning(
                    f"保存到Redis失败 (尝试 {retry_count}/{max_retries}): {str(e)}"
                )
                if retry_count <= max_retries:
                    time.sleep(retry_delay)

        # 所有重试都失败
        logger.error(
            f"保存对话记录到Redis失败 (conversation_id: {conversation_id}): {str(last_exception)}"
        )
        raise last_exception

    @observe(
        name="_save_scratchpad_items_to_redis", capture_input=True, capture_output=True
    )
    def _save_scratchpad_items_to_redis(
        self,
        conversation_id: str,
        scratchpad_items: List[ScratchpadItem],
        expire_hours: int = 12,
    ):
        """将scratchpad items保存到Redis有序集合中，使用时间戳作为score

        Args:
            conversation_id: 会话ID
            scratchpad_items: 要保存的scratchpad items列表
            expire_hours: 过期时间（小时），默认12小时
        """
        try:
            redis_cache = RedisCache()
            redis_key = f"historical_scratchpad:{conversation_id}"
            current_timestamp = time.time()

            # 将每个scratchpad item转换为JSON并保存
            for item in scratchpad_items:
                item_dict = {
                    "thought": item.thought,
                    "action": item.action,
                    "observation": item.observation,
                    "is_origin_query": item.is_origin_query,
                }
                item_json = json.dumps(item_dict, ensure_ascii=False)
                redis_cache.zadd(redis_key, {item_json: current_timestamp})

            # 清理过期数据
            expire_timestamp = current_timestamp - (expire_hours * 60 * 60)
            redis_cache.zremrangebyscore(redis_key, 0, expire_timestamp)

            # 获取当前数量
            total_count = redis_cache.zcard(redis_key)

            # 限制总数量：保留最新的100条
            if total_count > 100:
                redis_cache.zremrangebyrank(redis_key, 0, total_count - 101)

            logger.info(
                f"成功保存{len(scratchpad_items)}条scratchpad items到Redis (conversation_id: {conversation_id})"
            )
        except Exception as e:
            logger.error(
                f"保存scratchpad items到Redis失败 (conversation_id: {conversation_id}): {str(e)}"
            )

    @observe(name="_load_conversation_history", capture_input=True, capture_output=True)
    def _load_conversation_history(
        self, conversation_id: str, size: int = 5, expire_hours: int = 12
    ) -> str:
        """从Redis中加载完整的对话历史记录

        Args:
            conversation_id: 会话ID
            size: 要获取的对话轮次数
            expire_hours: 过期时间(小时)

        Returns:
            str: 格式化的对话历史记录字符串
        """
        try:
            redis_cache = RedisCache()
            redis_key = f"conversation_history:{conversation_id}"

            # 计算过期时间戳
            expire_timestamp = time.time() - (expire_hours * 60 * 60)

            # 删除过期数据
            redis_cache.zremrangebyscore(redis_key, 0, expire_timestamp)

            # 获取总数量
            total_count = redis_cache.zcard(redis_key)
            if total_count == 0:
                logger.info(
                    f"未找到{expire_hours}小时内的对话历史 (conversation_id: {conversation_id})"
                )
                return ""

            # 计算起始位置：获取最新的size*2条记录(每轮对话包含用户和助手各一条)
            if total_count <= size * 2:
                start_index = 0
                end_index = total_count - 1
            else:
                start_index = total_count - size * 2
                end_index = total_count - 1

            # 获取历史记录
            history_data = redis_cache.zrange(redis_key, start_index, end_index)

            # 格式化对话历史
            conversation_history = []
            for item_json in history_data:
                try:
                    item = json.loads(item_json)
                    if "user" in item:
                        conversation_history.append(f"User: {item['user']}")
                    elif "assistant" in item:
                        conversation_history.append(f"Assistant: {item['assistant']}")
                except (json.JSONDecodeError, Exception) as e:
                    logger.warning(f"解析对话历史失败: {e}")
                    continue

            if conversation_history:
                logger.info(
                    f"成功加载 {len(conversation_history)} 条对话历史记录 (conversation_id: {conversation_id})"
                )
                return "\n".join(conversation_history)
            return ""

        except Exception as e:
            logger.error(f"加载对话历史失败: {e}")
            return ""

    @observe(name="_construct_prompt", capture_input=True, capture_output=True)
    def _construct_prompt(
        self,
        query: str = None,
        current_iteration: int = 1,
    ) -> str:
        """构造提示模板，使用缓存优化工具描述生成

        新增conversation字段用于传递连续会话历史
        """

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

        # 使用实例字段中的scratchpad_items，排除is_origin_query的item
        agent_scratchpad = ""
        # 过滤掉is_origin_query=True的项目，只处理实际的执行步骤
        execution_items = [
            item for item in self.scratchpad_items if not item.is_origin_query
        ]
        for i, item in enumerate(execution_items, 1):
            agent_scratchpad += item.to_react_context(index=i) + "\n"

        # 统一提示模板构造
        # query赋值优化：只有当query为None时，才从scratchpad_items中查找is_origin_query为true的item，否则直接使用query
        query_value = query
        values = {
            "CURRENT_TIME": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "tools": tools_list,
            "tool_names": tool_names,
            "query": query_value,
            "context": agent_scratchpad,
            "instructions": self.instruction,
            "conversations": (
                self._load_conversation_history(self.conversation_id)
                if hasattr(self, "conversation_id") and self.conversation_id
                else ""
            ),
            "max_iterations": self.max_iterations,
            "current_iteration": current_iteration,
        }
        agent_prompt = Template(self.prompt_template).safe_substitute(values)
        return agent_prompt

    async def _call_model(self, prompt: str, chat_id: str, model_name: str) -> str:
        if not self.langfuse_trace:
            # 如果没有trace则直接调用LLM
            messages = [{"role": "user", "content": prompt}]
            return await call_llm_api(messages, model_name=model_name)

        try:
            with self.langfuse_trace.start_as_current_span(name="llm-call") as span:
                # 创建嵌套的generation span
                span.update_trace(session_id=chat_id)
                with span.start_as_current_generation(
                    name="generate-response",
                    model=model_name,
                    input={"prompt": prompt},
                    model_parameters={"temperature": 0.7},  # 可以从配置获取实际参数
                    metadata={"chat_id": chat_id},
                ) as generation:
                    start_time = time.time()
                    messages = [{"role": "user", "content": prompt}]
                    response = await call_llm_api(messages, model_name=model_name)

                    # 更新generation信息
                    generation.update(
                        output=response,
                        usage_details={
                            "input_tokens": len(prompt.split()),  # 简单估算
                            "output_tokens": len(response.split()),  # 简单估算
                        },
                        cost_details={"total_cost": 0.0023},  # 可以从配置获取实际成本
                    )

                    # 评分
                    generation.score(name="relevance", value=0.95, data_type="NUMERIC")

                    # 记录执行时间
                    execution_time = time.time() - start_time
                    self.metrics.record_call(execution_time, is_error=False)

                    return response

        except Exception as e:
            execution_time = time.time() - start_time if "start_time" in locals() else 0
            self.metrics.record_call(execution_time, is_error=True)

            if "generation" in locals():
                generation.update(
                    output={"error": str(e)},
                    status_message=f"LLM call failed: {str(e)}",
                    metadata={"execution_time": execution_time},
                )

            raise LLMAPIError(f"LLM API call failed: {str(e)}")

    # Pre-compile regex patterns for performance
    _THOUGHT_PATTERN = re.compile(
        r"Thought[:：]\s*(.*?)(?=\nAction[:：]|\nAnswer[:：]|$)", re.DOTALL
    )
    _ACTION_PATTERN = re.compile(
        r"Action[:：]\s*(.*?)(?=\nAction Input[:：]|$)", re.DOTALL
    )
    _ACTION_INPUT_PATTERN = re.compile(
        r"Action Input[:：]\s*(.*?)(?=\nThought[:：]|\nAction[:：]|\nAnswer[:：]|$)",
        re.DOTALL,
    )
    _ANSWER_PATTERN = re.compile(r"Answer[:：]\s*(.*)", re.DOTALL)

    @observe(name="_parse_action", capture_input=True, capture_output=True)
    async def _parse_action(
        self, response_text: str, chat_id: str, query: str = None
    ) -> Dict[str, Any]:
        """解析LLM响应为动作字典，支持纯文本解析（Action格式和Answer格式）

        优化后的逻辑确保：
        - Thought内容包含Thought标签和下一个Action/Answer标签之间的所有内容
        - Answer内容包含Answer标签之后的所有内容
        """
        try:
            # 预处理：移除包裹文本的```标记
            if response_text.startswith("```") and response_text.endswith("```"):
                response_text = response_text[3:-3].strip()

            # Use pre-compiled patterns
            thought_match = self._THOUGHT_PATTERN.search(response_text)
            action_match = self._ACTION_PATTERN.search(response_text)
            action_input_match = self._ACTION_INPUT_PATTERN.search(response_text)

            # 处理Action格式响应
            if thought_match and action_match and action_input_match:
                action_input_str = action_input_match.group(1).strip()
                try:
                    params = json.loads(action_input_str)
                except json.JSONDecodeError:
                    params = action_input_str

                return {
                    "thinking": thought_match.group(1).strip(),
                    "tool": {
                        "name": action_match.group(1).strip(),
                        "params": params,
                    },
                }

            # 处理Answer格式响应
            answer_match = self._ANSWER_PATTERN.search(response_text)
            if answer_match:
                return {
                    "thinking": thought_match.group(1).strip() if thought_match else "",
                    "tool": {
                        "name": "final_answer",
                        "params": answer_match.group(1).strip(),
                    },
                }

            # 默认返回整个响应作为最终答案
            return {
                "thinking": "",
                "tool": {
                    "name": "final_answer",
                    "params": response_text,
                },
            }
        except Exception as e:
            logger.error(f"解析响应文本失败: {str(e)}\n响应内容: {response_text[:200]}")
            return {"thinking": f"解析错误: {str(e)}"}

    @observe(name="set_user_input", capture_input=True, capture_output=True)
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

    @observe(name="wait_for_user_input", capture_input=True, capture_output=True)
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

    @observe(name="stop", capture_input=True, capture_output=True)
    async def stop(self) -> None:
        self.stopped = True

    @observe(name="clear_context", capture_input=True, capture_output=True)
    def clear_context(self) -> None:
        """清空agent上下文，包括scratchpad_items和cache信息"""
        self.scratchpad_items.clear()
        logger.info(f"Agent context cleared scratchpad_items:{self.scratchpad_items}")
        self._response_cache.clear()
        logger.info("Agent context cleared")

    async def _register_agent(self, chat_id: str) -> None:
        """注册当前agent到缓存"""
        with ReactAgent._cache_lock:
            if chat_id not in ReactAgent._agent_cache:
                ReactAgent._agent_cache[chat_id] = []
            if not any(
                a.agentcard.agentid == self.agentcard.agentid
                for a in ReactAgent._agent_cache[chat_id]
            ):
                ReactAgent._agent_cache[chat_id].append(self)

    @observe(name="_execute_tool", capture_input=True, capture_output=True)
    async def _execute_tool(
        self, tool, action: str, action_input: dict, action_id: str, chat_id: str
    ) -> str:
        """执行工具并处理结果"""
        tool_span = None
        if self.langfuse_trace:
            try:
                tool_span = self.langfuse_trace.span(
                    name=f"tool_{action}",
                    input={
                        "action": action,
                        "input": action_input,
                        "action_id": action_id,
                    },
                    metadata={
                        "chat_id": chat_id,
                        "tool_name": tool.name,
                        "tool_description": tool.description,
                    },
                )
                logger.info(f"Created Langfuse span for tool: {action}")
            except Exception as e:
                logger.error(f"Failed to create tool span: {str(e)}")

        try:
            start_time = time.time()
            if tool.is_async:
                result = await tool.run(action_input)
            else:
                result = tool.run(action_input)

            if tool_span:
                try:
                    tool_span.update(
                        output={"result": result},
                        metadata={"execution_time": time.time() - start_time},
                    )
                    tool_span.end()
                except Exception as e:
                    logger.error(f"Failed to update tool span: {str(e)}")

            return result
        except Exception as e:
            if tool_span:
                try:
                    tool_span.update(
                        output={"error": str(e)},
                        status_message=f"Tool failed: {str(e)}",
                    )
                    tool_span.end()
                except Exception as e:
                    logger.error(f"Failed to update tool span with error: {str(e)}")
            raise ToolExecutionError(f"Tool {action} failed: {str(e)}")

    @observe(name="_handle_termination", capture_input=True, capture_output=True)
    async def _handle_termination(self, ctx: dict) -> bool:
        """检查终止条件"""
        return any(
            tc.should_terminate(self, **ctx) for tc in self.termination_conditions
        )

    @observe(name="_process_llm_response", capture_input=True, capture_output=True)
    async def _process_llm_response(
        self, prompt: str, chat_id: str, context: str = None, query: str = None
    ) -> tuple:
        """处理LLM响应并解析动作"""
        model_response = None
        if self.reasoner_model_name:
            model_response = await asyncio.wait_for(
                self._call_model(prompt, chat_id, self.reasoner_model_name),
                timeout=self.llm_timeout,
            )
        else:
            model_response = await asyncio.wait_for(
                self._call_model(prompt, chat_id, self.model_name),
                timeout=self.llm_timeout,
            )

        logger.info(f"Iteration LLM Response: {model_response}")
        result_dict = await self._parse_action(model_response, chat_id, query)
        return result_dict

    @observe(name="_execute_tool_action", capture_input=True, capture_output=True)
    async def _execute_tool_action(
        self,
        action: str,
        action_input: dict,
        thought: str,
        chat_id: str,
        tool: Tool,
        observations: list,
    ) -> tuple:
        """执行工具动作并处理结果"""
        action_id = str(uuid.uuid4())
        stream = bool(self.stream_manager)

        # 发送工具事件
        if stream:
            start_event = await create_action_start_event(
                action, action_input, action_id
            )
            await self.stream_manager.send_message(chat_id, start_event)

            progress_event = await create_tool_progress_event(
                action, "running", action_input, action_id
            )
            await self.stream_manager.send_message(chat_id, progress_event)

        # 特殊动作处理
        if action == "user_input":
            action_input["chat_id"] = chat_id
            action_input["node_id"] = f"{chat_id}-{uuid.uuid1()}"
            action_input["agent"] = self

        if action == "chat" and action_input.get("need_history", False):
            action_input["history_action_result"] = "\n".join(observations)

        if action == "workflow_execute":
            action_input["chat_id"] = chat_id
            action_input["stream_manager"] = self.stream_manager

        # 执行工具
        observation = ""
        retry_count = 0
        while retry_count <= tool.max_retries:
            if self.stopped:
                return None, True, ""

            try:
                if tool.is_async:
                    observation = await tool.run(action_input)
                else:
                    observation = tool.run(action_input)

                self.metrics.record_tool_usage(action)
                break
            except Exception as e:
                retry_count += 1
                error_msg = str(e)
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

        # 发送完成事件
        if stream:
            event = await create_action_complete_event(action, observation, action_id)
            await self.stream_manager.send_message(chat_id, event)

        # 处理特殊逻辑
        if action == "user_input":
            thought = f"{thought}\n{action_input['prompt']}"

        return observation, thought

    @observe(name="run", capture_input=True, capture_output=True)
    async def run(
        self,
        query: str,
        chat_id: str,
        stream: bool = True,
        is_result: bool = False,
        context: str = None,
    ) -> str:
        await self._register_agent(chat_id)
        """执行Agent主逻辑"""
        span = None
        if self.langfuse_trace:
            try:
                span = self.langfuse_trace.span(
                    name="ReactAgent_run",
                    input={"query": query, "chat_id": chat_id},
                )
                logger.info("Created Langfuse span for ReactAgent execution")
            except Exception as e:
                logger.error(f"Failed to create Langfuse span: {str(e)}")

        if stream:
            self.stream_manager = StreamManager.get_instance()

        if self.stopped:
            if stream and self.stream_manager:
                event = await create_agent_complete_event("已停止")
                await self.stream_manager.send_message(chat_id, event)
            return None

        try:
            # 初始化运行状态
            if not is_result:
                # 清空scratchpad_items列表
                self.scratchpad_items = []
                # 添加初始查询item
                self.scratchpad_items.append(
                    ScratchpadItem(is_origin_query=True, thought=query)
                )
                # 保存用户查询到对话历史
                if self.conversation_id:
                    self._save_conversation_to_redis(
                        self.conversation_id, user_query=query
                    )

            if stream and self.stream_manager:
                event = await create_agent_start_event(query)
                await self.stream_manager.send_message(chat_id, event)

            # 运行主循环
            result = await self._run_main_loop(chat_id, query, context, stream, span)
            if span:
                try:
                    span.update(output={"result": result})
                    span.end()
                    logger.info("Completed Langfuse span for ReactAgent execution")
                except Exception as e:
                    logger.error(f"Failed to update Langfuse span: {str(e)}")
            return result
        except Exception as e:
            error_msg = f"Agent运行失败: {str(e)}"
            logger.error(error_msg)
            if stream and self.stream_manager:
                event = await create_agent_error_event(error_msg)
                await self.stream_manager.send_message(chat_id, event)
            raise
        finally:
            self._cleanup_resources()

    @observe(name="_run_main_loop", capture_input=True, capture_output=True)
    async def _run_main_loop(
        self, chat_id: str, query: str, context: str, stream: bool, span: Any = None
    ) -> str:
        """运行Agent主循环"""
        if span:
            try:
                span.update(
                    status="running",
                    metadata={
                        "chat_id": chat_id,
                        "query": query,
                        "context": context if context else "",
                        "max_iterations": self.max_iterations,
                        "model_name": self.model_name or self.reasoner_model_name,
                    },
                )
            except Exception as e:
                logger.error(f"Failed to update Langfuse span status: {str(e)}")
        observations = []
        iteration_count = 0
        final_answer = None
        last_error = None

        while iteration_count < self.max_iterations:
            if self.stopped:
                break

            iteration_count += 1

            # 检查终止条件
            if await self._check_termination(iteration_count):
                logger.info(f"满足终止条件，迭代次数: {iteration_count}")
                break

            try:
                # 构造并发送提示
                prompt = self._construct_prompt(
                    query=query,
                    current_iteration=iteration_count,
                )
                logger.info(f"Iteration {iteration_count} prompt: {prompt}")

                result_dict = await self._process_llm_response(
                    prompt, chat_id, context, query
                )
                action_dict = result_dict.get("tool", {})
                action = action_dict.get("name", "")
                action_input = action_dict.get("params", {})
                thought = result_dict.get("thinking", "")

                # 发送思考事件
                if stream and self.stream_manager:
                    event = await create_agent_thinking_event(thought)
                    await self.stream_manager.send_message(chat_id, event)

                # 处理最终答案
                if action == "final_answer":
                    final_answer = action_input
                    break

                # 验证工具
                if not action or action not in self.tools:
                    raise ToolNotFoundError(f"无效动作: {action}")

                # 执行工具
                tool = self.tools[action]
                tool_span = None
                if span:
                    try:
                        tool_span = span.span(
                            name=f"tool_{action}",
                            input={"action_input": action_input},
                        )
                    except Exception as e:
                        logger.error(f"Failed to create tool span: {str(e)}")

                observation, thought = await self._execute_tool_action(
                    action, action_input, thought, chat_id, tool, observations
                )

                if tool_span:
                    try:
                        tool_span.update(
                            output={"observation": observation if observation else ""}
                        )
                        tool_span.end()
                    except Exception as e:
                        logger.error(f"Failed to end tool span: {str(e)}")

                # 保存执行记录
                new_item = ScratchpadItem(
                    thought=thought, action=action, observation=observation
                )
                self.scratchpad_items.append(new_item)
                observations.append(observation)

            except ActionBadException as e:
                logger.error(f"[{chat_id}] {e.message}")
                final_answer = e.message
                break
            except asyncio.TimeoutError:
                logger.error(f"[{chat_id}] LLM响应超时")
                await asyncio.sleep(self.iteration_retry_delay)
            except Exception as e:
                last_error = str(e)
                logger.error(f"[{chat_id}] 迭代错误: {last_error}")

                if span:
                    try:
                        span.update(output={"last_error": last_error})
                    except Exception as e:
                        logger.error(f"Failed to update main span with error: {str(e)}")

                error_item = ScratchpadItem(
                    thought=last_error, action="", observation=last_error
                )
                self.scratchpad_items.append(error_item)
                await asyncio.sleep(self.iteration_retry_delay)

        # 处理最终结果
        result = await self._handle_final_result(
            chat_id, stream, final_answer, observations
        )

        return result

    @observe(name="_check_termination", capture_input=True, capture_output=True)
    async def _check_termination(self, iteration_count: int) -> bool:
        """检查终止条件"""
        return any(
            tc.should_terminate(self, current_step=iteration_count)
            for tc in self.termination_conditions
        )

    @observe(name="_handle_final_result", capture_input=True, capture_output=True)
    async def _handle_final_result(
        self,
        chat_id: str,
        stream: bool,
        final_answer: str,
        observations: list,
    ) -> str:
        """处理最终结果"""
        # 发送完成事件
        if stream and self.stream_manager:
            event = await create_agent_complete_event(final_answer or observations[-1])
            await self.stream_manager.send_message(chat_id, event)

        # 保存对话记录
        if self.conversation_id:
            # 保存所有scratchpad items到独立存储
            self._save_scratchpad_items_to_redis(
                self.conversation_id, self.scratchpad_items
            )
            # 保存助手回答到对话历史
            if final_answer:
                self._save_conversation_to_redis(
                    self.conversation_id, assistant_answer=final_answer
                )

        return final_answer

    @observe(name="_cleanup_resources", capture_input=True, capture_output=True)
    def _cleanup_resources(self):
        """清理资源"""
        self._pending_user_input.clear()
        self._user_input_events.clear()

    @observe(name="_send_agent_complete_event", capture_input=True, capture_output=True)
    async def _send_agent_complete_event(self, message: str, chat_id: str) -> None:
        """发送agent完成事件"""
        event = await create_agent_complete_event(message)
        await self.stream_manager.send_message(chat_id, event)
