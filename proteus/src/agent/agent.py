from datetime import datetime
import re
from typing import List, Dict, Any
import asyncio
import contextlib
import logging
import time
import uuid
import threading
import json
from string import Template
from functools import wraps, lru_cache
from types import SimpleNamespace
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
from ..manager.multi_agent_manager import TeamRole, AgentEvent
from .terminition import TerminationCondition, StepLimitTerminationCondition
from ..utils.redis_cache import RedisCache, get_redis_connection
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


class Agent:
    _agent_cache: Dict[str, List["Agent"]] = {}
    _cache_lock = threading.Lock()

    @classmethod
    @observe(name="get_agents", capture_input=True, capture_output=True)
    def get_agents(cls, chat_id: str) -> List["Agent"]:
        """获取指定chat_id下的agent列表副本"""
        with cls._cache_lock:
            return list(cls._agent_cache.get(chat_id, []))

    @classmethod
    @observe(name="set_agents", capture_input=True, capture_output=True)
    def set_agents(cls, chat_id: str, agents: List["Agent"]) -> None:
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

        # 初始化scratchpad_items，包含历史信息
        self.scratchpad_items = scratchpad_items if scratchpad_items else []
        # if conversation_id:
        #     historical_items = self._load_historical_scratchpad_items(conversation_id)
        #     self.scratchpad_items.extend(historical_items)

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

    @observe(name="_validate_tools", capture_input=True, capture_output=True)
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
            redis_cache = get_redis_connection()
            redis_key = f"conversation_history:{conversation_id}"

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
                        tool_execution_id=item_dict.get("tool_execution_id", ""),
                        role_type=item_dict.get("role_type", "") or "",
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
                redis_cache = get_redis_connection()
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

    @observe(name="_load_conversation_history", capture_input=True, capture_output=True)
    def _load_conversation_history(
        self, conversation_id: str, size: int = 5, expire_hours: int = 12
    ) -> List[Dict[str, str]]:
        """从Redis中加载完整的对话历史记录，返回数组格式: [{"role":"user"|"assistant","content":"..."}]

        保持原有逻辑：按时间顺序返回最近 size 轮（每轮包含 user 和 assistant 各一条，存储层为有序集合）
        """
        try:
            redis_cache = get_redis_connection()
            redis_key = f"conversation_history:{conversation_id}"

            # 计算过期时间戳并删除过期数据
            expire_timestamp = time.time() - (expire_hours * 60 * 60)
            redis_cache.zremrangebyscore(redis_key, 0, expire_timestamp)

            # 获取总数量
            total_count = redis_cache.zcard(redis_key)
            if total_count == 0:
                logger.info(
                    f"未找到{expire_hours}小时内的对话历史 (conversation_id: {conversation_id})"
                )
                return []

            # 计算起始位置：获取最新的 size*2 条记录(每轮包含 user 和 assistant 各一条)
            if total_count <= size * 2:
                start_index = 0
                end_index = total_count - 1
            else:
                start_index = total_count - size * 2
                end_index = total_count - 1

            # 获取历史记录（按时间升序）
            history_data = redis_cache.zrange(redis_key, start_index, end_index)

            # 解析并构造返回数组
            conversation_history: List[Dict[str, str]] = []
            for item_json in history_data:
                try:
                    item = json.loads(item_json)
                    if "user" in item:
                        conversation_history.append(
                            {"role": "user", "content": item.get("user", "")}
                        )
                    elif "assistant" in item:
                        conversation_history.append(
                            {"role": "assistant", "content": item.get("assistant", "")}
                        )
                except (json.JSONDecodeError, Exception) as e:
                    logger.warning(f"解析对话历史失败: {e}")
                    continue

            if conversation_history:
                logger.info(
                    f"成功加载 {len(conversation_history)} 条对话历史记录 (conversation_id: {conversation_id})"
                )
            return conversation_history

        except Exception as e:
            logger.error(f"加载对话历史失败: {e}")
            return []

    @observe(name="_construct_prompt", capture_input=True, capture_output=True)
    def _construct_prompt(self, context: str = None, query: str = None) -> str:
        """构造提示模板，使用缓存优化工具描述生成

        新增conversation字段用于传递连续会话历史
        """

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

        # 使用实例字段中的scratchpad_items，排除is_origin_query的item
        agent_scratchpad = ""
        # 过滤掉is_origin_query=True的项目，只处理实际的执行步骤
        execution_items = [
            item for item in self.scratchpad_items if not item.is_origin_query
        ]
        for i, item in enumerate(execution_items, 1):
            agent_scratchpad += item.to_react_context(index=i)
        if context is not None:
            agent_scratchpad += f"{context}"

        # 统一提示模板构造
        # query赋值优化：只有当query为None时，才从scratchpad_items中查找is_origin_query为true的item，否则直接使用query
        query_value = query
        if query is None and self.scratchpad_items:
            for item in self.scratchpad_items:
                if item.is_origin_query:
                    query_value = item.thought
                    break

        values = {
            "CURRENT_TIME": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "REACT_LOOP_PROMPT": REACT_LOOP_PROMPT,
            "PLANNER_REACT_LOOP_PROMPT": PLANNER_REACT_LOOP_PROMPT,
            "tools": tools_list,
            "tool_names": tool_names,
            "query": query_value,
            "context": agent_scratchpad,
            "max_step_num": self.max_iterations,
            "instructions": self.instruction,
            "role_description": self.description,
            "team_description": self.team_description,
            "conversations": (
                self._load_conversation_history(self.conversation_id)
                if hasattr(self, "conversation_id") and self.conversation_id
                else ""
            ),
        }
        agent_prompt = Template(self.prompt_template).safe_substitute(values)
        return agent_prompt

    @observe(name="_call_model", capture_input=True, capture_output=True)
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

    @observe(name="_parse_action", capture_input=True, capture_output=True)
    async def _parse_action(
        self, response_text: str, chat_id: str, query: str = None
    ) -> Dict[str, Any]:
        """解析LLM响应为动作字典，支持纯文本解析（Action格式和Answer格式）."""
        try:
            # 先尝试匹配Action/Action Input格式（支持中英文冒号）
            thought_match = re.search(
                r"Thought[:：]\s*(.*?)(?:\n|$)", response_text, re.DOTALL
            )
            action_match = re.search(
                r"Action[:：]\s*(.*?)(?:\n|$)", response_text, re.DOTALL
            )
            action_input_match = re.search(
                r"Action Input[:：]\s*(.*?)(?:\n|$)", response_text, re.DOTALL
            )

            if thought_match and action_match and action_input_match:
                # 尝试解析 Action Input 为 JSON
                action_input_str = action_input_match.group(1).strip()
                try:
                    # 尝试解析 JSON
                    params = json.loads(action_input_str)
                except json.JSONDecodeError:
                    # 解析失败，保持原字符串
                    params = action_input_str

                # 构建与XML解析结果结构一致的字典（工具调用）
                action_dict = {
                    "thinking": thought_match.group(1).strip(),
                    "tool": {
                        "name": action_match.group(1).strip(),
                        "params": params,  # 使用解析后的对象或原字符串
                    },
                }
                logger.info(f"纯文本解析成功（Action格式）: {action_dict}")
                return action_dict

            # 如果Action格式匹配失败，尝试匹配Answer格式
            thought_match = re.search(
                r"Thought[:：]\s*(.*?)(?:\n|$)", response_text, re.DOTALL
            )
            answer_match = re.search(r"Answer[:：]\s*(.*)", response_text, re.DOTALL)

            if thought_match or answer_match:
                # 构建与XML解析结果结构一致的字典（最终答案）
                action_dict = {
                    "thinking": (
                        thought_match.group(1).strip() if thought_match else ""
                    ),
                    "tool": {
                        "name": "final_answer",
                        "params": (
                            answer_match.group(1).strip() if answer_match else ""
                        ),
                    },
                }
                logger.info(f"纯文本解析成功（Answer格式）: {action_dict}")
                return action_dict

            # 两种格式都无法识别
            error_info = f"无法解析响应文本: {response_text}"
            logger.error(error_info)
            return {"thinking": error_info}
        except Exception as e:
            error_info = f"解析响应文本失败:\n{response_text}\n错误: {str(e)}"
            logger.error(error_info)
            return {"thinking": error_info}

    @log_execution_time
    @observe(name="set_user_input", capture_input=True, capture_output=True)
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
        # 创建用户输入请求事件，使用关键字参数明确传递，避免参数错位导致 agent_id 丢失
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

    @observe(name="setup_event_subscriptions", capture_input=True, capture_output=True)
    async def setup_event_subscriptions(self, agentid: str) -> None:
        """初始化事件订阅：直接监听 Redis 中属于该 agent 的队列 agent_queue:{agentid}"""
        if getattr(self, "_is_subscribed", False):
            return
        try:
            self._is_subscribed = True
            # 启动后台监听任务（监听自己的 agent_queue）
            loop = asyncio.get_running_loop()
            self._agent_listener_task = loop.create_task(
                self._listen_agent_queue(agentid)
            )
            logger.info(f"Agent {agentid} subscribed to agent_queue:{agentid}")
        except Exception as e:
            logger.error(
                f"Failed to setup event subscriptions for agent {agentid}: {str(e)}"
            )
            raise

    async def _listen_agent_queue(self, agentid: str):
        """监听 Redis 中 agent_queue:{agentid}，将 JSON 事件恢复为本地调用（复用 _handle_event 逻辑）"""
        redis_cache = RedisCache()
        agent_key = f"agent_queue:{agentid}"
        while not self.stopped:
            try:
                blpop_result = redis_cache.blpop([agent_key], timeout=1)
                if not blpop_result:
                    await asyncio.sleep(0.01)
                    continue
                key, value = blpop_result
                if not key or not value:
                    continue
                try:
                    event_dict = json.loads(value)
                except Exception as e:
                    logger.error(f"解析 agent_queue 事件 JSON 失败: {e} value={value}")
                    continue

                # 将 dict 转为带属性访问的对象，兼容 _handle_event 的预期结构
                try:
                    sender_role = event_dict.get("sender_role")
                    try:
                        sender_role_enum = (
                            TeamRole(sender_role) if sender_role else None
                        )
                    except Exception:
                        sender_role_enum = None
                    try:
                        role_type_enum = (
                            TeamRole(event_dict.get("role_type"))
                            if event_dict.get("role_type")
                            else None
                        )
                    except Exception:
                        role_type_enum = None

                    event_obj = SimpleNamespace(
                        priority=event_dict.get("priority", 1),
                        chat_id=event_dict.get("chat_id"),
                        event_id=event_dict.get("event_id", str(uuid.uuid4())),
                        role_type=role_type_enum,
                        sender_id=event_dict.get("sender_id"),
                        sender_role=sender_role_enum,
                        payload=event_dict.get("payload"),
                        is_result=event_dict.get("is_result", False),
                    )
                    await self._handle_event(event_obj)
                except Exception as e:
                    logger.error(f"处理 agent_queue 事件失败: {e}", exc_info=True)

            except Exception as e:
                logger.error(f"agent_queue 监听循环异常: {e}", exc_info=True)
                await asyncio.sleep(0.5)

    @observe(name="_handle_event", capture_input=True, capture_output=True)
    async def _handle_event(self, event: AgentEvent) -> None:
        # 注册当前agent到缓存
        with Agent._cache_lock:
            if event.chat_id not in Agent._agent_cache:
                Agent._agent_cache[event.chat_id] = []
            if not any(
                a.agentcard.agentid == self.agentcard.agentid
                for a in Agent._agent_cache[event.chat_id]
            ):
                Agent._agent_cache[event.chat_id].append(self)
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
                            ScratchpadItem(
                                observation=observation,
                                thought=thought,
                                tool_execution_id="",
                                role_type=(
                                    event.sender_role.value
                                    if hasattr(event.sender_role, "value")
                                    else str(event.sender_role)
                                ),
                            )
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
                    origin_query = (
                        event.payload.get("task", "")
                        + "\n"
                        + event.payload.get("description", "")
                    )
                    handoff_event = {
                        "chat_id": event.chat_id,
                        "priority": 0,
                        "event_id": str(uuid.uuid4()),
                        "role_type": (
                            event.sender_role.value
                            if hasattr(event.sender_role, "value")
                            else str(event.sender_role)
                        ),
                        "sender_id": self.agentcard.agentid,
                        "sender_role": (
                            self.role_type.value
                            if hasattr(self.role_type, "value")
                            else str(self.role_type)
                        ),
                        "payload": {
                            "result": result,
                            "metadata": {
                                "agent_id": self.agentcard.agentid,
                                "timestamp": datetime.now().isoformat(),
                                "original_event_id": event.event_id,
                                "origin_query": origin_query,
                            },
                        },
                        "is_result": True,
                    }
                    try:
                        redis_cache = RedisCache()
                        if event.sender_id:
                            redis_cache.rpush(
                                f"agent_queue:{event.sender_id}",
                                json.dumps(handoff_event, ensure_ascii=False),
                            )
                            logger.info(
                                f"Handoff event sent to agent_queue:{event.sender_id} (original event: {event.event_id})"
                            )
                        else:
                            # 如果没有指定sender_id，则尝试将结果发送给对应角色的所有agent
                            role_agents_key = f"role_agents:{event.sender_role.value if hasattr(event.sender_role,'value') else str(event.sender_role)}"
                            agent_ids = redis_cache.lrange(role_agents_key, 0, -1) or []
                            for aid in agent_ids:
                                try:
                                    redis_cache.rpush(
                                        f"agent_queue:{aid}",
                                        json.dumps(handoff_event, ensure_ascii=False),
                                    )
                                except Exception as e:
                                    logger.error(
                                        f"向 agent_queue:{aid} 推送 handoff 失败: {e}",
                                        exc_info=True,
                                    )
                    except Exception as e:
                        logger.error(f"发送 handoff 事件失败: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Error handling event {event.event_id}: {str(e)}")
            if self.stream_manager and hasattr(event, "sender_id"):
                await self.stream_manager.send_message(
                    event.sender_id, await create_agent_error_event(str(e))
                )

    @observe(name="_register_agent", capture_input=True, capture_output=True)
    async def _register_agent(self, chat_id: str) -> None:
        """注册当前agent到缓存"""
        with Agent._cache_lock:
            if chat_id not in Agent._agent_cache:
                Agent._agent_cache[chat_id] = []
            if not any(
                a.agentcard.agentid == self.agentcard.agentid
                for a in Agent._agent_cache[chat_id]
            ):
                Agent._agent_cache[chat_id].append(self)

    @observe(name="_prepare_execution", capture_input=True, capture_output=True)
    async def _prepare_execution(
        self, query: str, chat_id: str, is_result: bool
    ) -> None:
        """准备执行环境"""
        if not is_result:
            origin_query_item = ScratchpadItem(
                is_origin_query=True,
                thought=query,
                tool_execution_id="",
                role_type=(
                    self.role_type.value
                    if hasattr(self.role_type, "value")
                    else str(self.role_type)
                ),
            )
            self.scratchpad_items.append(origin_query_item)
            # 注意：agent.py不直接保存到Redis，统一由React Agent负责

    @observe(name="_execute_tool", capture_input=True, capture_output=True)
    async def _execute_tool(
        self, tool, action: str, action_input: dict, action_id: str, chat_id: str
    ) -> str:
        """执行工具并处理结果"""
        try:
            if tool.is_async:
                return await tool.run(action_input)
            return tool.run(action_input)
        except Exception as e:
            raise ToolExecutionError(f"Tool {action} failed: {str(e)}")

    @observe(name="_handle_termination", capture_input=True, capture_output=True)
    async def _handle_termination(self, ctx: dict) -> bool:
        """检查终止条件"""
        return any(
            tc.should_terminate(self, **ctx) for tc in self.termination_conditions
        )

    @observe(name="run", capture_input=True, capture_output=True)
    async def run(
        self,
        query: str,
        chat_id: str,
        stream: bool = True,
        is_result: bool = False,
        context: str = None,
    ) -> str:
        """执行Agent的主要逻辑

        Args:
            query: 用户输入的查询文本
            chat_id: 聊天会话ID
            stream: 是否启用事件流式传输
            is_result: 是否为结果处理
            context: 上下文信息

        Returns:
            str: Agent的响应结果
        """
        await self._register_agent(chat_id)
        if stream:
            self.stream_manager = StreamManager.get_instance()
        if self.stopped:
            # 发送agent结束事件
            if stream:
                event = await create_agent_complete_event("已停止")
                await self.stream_manager.send_message(chat_id, event)
            return
        try:
            # 发送agent开始事件
            if not is_result:
                origin_query_item = ScratchpadItem(
                    is_origin_query=True,
                    thought=query,
                    tool_execution_id="",
                    role_type=(
                        self.role_type.value
                        if hasattr(self.role_type, "value")
                        else str(self.role_type)
                    ),
                )
                self.scratchpad_items.append(origin_query_item)

                # 如果有conversation_id，将初始查询也保存到Redis
                if self.conversation_id:
                    self._save_conversation_to_redis(
                        self.conversation_id, user_query=query
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
            terminition_flag = False

            while not handoff_flag:
                termination_ctx = {
                    "current_step": iteration_count,
                    "current_action": action,
                    "current_thought": thought,
                    "current_observation": observation,
                    "final_answer": final_answer,
                    "error_occurred": False,
                }

                if await self._handle_termination(termination_ctx):
                    logger.info(f"Termination condition met at step {iteration_count}")
                    terminition_flag = True
                    break
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
                    prompt = self._construct_prompt(context=context, query=query)
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

                    # 发送工具相关事件
                    if stream:
                        # 发送动作开始事件
                        start_event = await create_action_start_event(
                            action, action_input, action_id
                        )
                        await self.stream_manager.send_message(chat_id, start_event)

                        # 发送工具进度事件
                        progress_event = await create_tool_progress_event(
                            action, "running", action_input, action_id
                        )
                        await self.stream_manager.send_message(chat_id, progress_event)

                    retry_count = 0
                    while retry_count <= tool.max_retries:
                        if self.stopped:
                            if stream:
                                event = await create_agent_complete_event("已停止")
                                await self.stream_manager.send_message(chat_id, event)
                            return
                        try:
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
                                    # 过滤掉is_origin_query=True的项目和handoff动作
                                    execution_items = [
                                        item
                                        for item in self.scratchpad_items
                                        if not item.is_origin_query
                                        and item.action != "handoff"
                                    ]
                                    for item in execution_items:
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

                            if action == "user_input":
                                prompt = action_input["prompt"]
                                thought = f"{thought}\n{prompt}"

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
                        thought=thought,
                        action=action,
                        observation=observation,
                        tool_execution_id="",
                        role_type=(
                            self.role_type.value
                            if hasattr(self.role_type, "value")
                            else str(self.role_type)
                        ),
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
                        thought=error_msg,
                        action="",
                        observation=error_msg,
                        tool_execution_id="",
                        role_type=(
                            self.role_type.value
                            if hasattr(self.role_type, "value")
                            else str(self.role_type)
                        ),
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
                and not terminition_flag
            ):
                error_msg = (
                    f"Failed to get final answer after {self.max_iterations} iterations"
                )
                raise AgentError(error_msg)

            # 发送agent完成事件（handoff不发送）
            if not handoff_flag and stream:
                event = await create_agent_complete_event(final_answer)
                await self.stream_manager.send_message(chat_id, event)
            elif terminition_flag and stream:
                event = await create_agent_complete_event(observation)
                await self.stream_manager.send_message(chat_id, event)

            # handoff情况返回None，其他情况返回final_answer
            final_answer = observation if terminition_flag else final_answer
            # 如果有conversation_id，将当前迭代信息保存到Redis
            if self.conversation_id:
                self._save_conversation_to_redis(
                    self.conversation_id, assistant_answer=final_answer
                )
            return final_answer if not handoff_flag else None
        except Exception as e:
            error_msg = str(e)
            if stream:
                event = await create_agent_error_event(error_msg)
                await self.stream_manager.send_message(chat_id, event)

            # 发布错误事件 -> 直接写入 COORDINATOR 角色对应的 agent 列表的 agent_queue
            try:
                redis_cache = RedisCache()
                role_key = f"role_agents:{TeamRole.COORDINATOR.value}"
                agent_ids = redis_cache.lrange(role_key, 0, -1) or []
                error_event = {
                    "chat_id": chat_id,
                    "priority": 1,
                    "event_id": str(uuid.uuid4()),
                    "role_type": TeamRole.COORDINATOR.value,
                    "sender_id": self.agentcard.agentid,
                    "sender_role": (
                        self.role_type.value
                        if hasattr(self.role_type, "value")
                        else str(self.role_type)
                    ),
                    "payload": {"error": error_msg},
                    "is_result": False,
                }
                for aid in agent_ids:
                    try:
                        redis_cache.rpush(
                            f"agent_queue:{aid}",
                            json.dumps(error_event, ensure_ascii=False),
                        )
                    except Exception as e:
                        logger.error(
                            f"向 agent_queue:{aid} 推送 error_event 失败: {e}",
                            exc_info=True,
                        )
            except Exception as e:
                logger.error(f"发布错误事件失败: {e}", exc_info=True)
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

    @observe(name="_send_tool_events", capture_input=True, capture_output=True)
    async def _send_tool_events(
        self, action: str, action_input: dict, action_id: str, chat_id: str
    ) -> None:
        """发送工具相关事件"""
        start_event = await create_action_start_event(action, action_input, action_id)
        await self.stream_manager.send_message(chat_id, start_event)

    @observe(name="_send_tool_progress_event", capture_input=True, capture_output=True)
    async def _send_tool_progress_event(
        self, action: str, action_input: dict, action_id: str, chat_id: str
    ) -> None:
        """发送工具进度事件"""
        progress_event = await create_tool_progress_event(
            action, "running", action_input, action_id
        )
        await self.stream_manager.send_message(chat_id, progress_event)

    @observe(name="_send_agent_complete_event", capture_input=True, capture_output=True)
    async def _send_agent_complete_event(self, message: str, chat_id: str) -> None:
        """发送agent完成事件"""
        event = await create_agent_complete_event(message)
        await self.stream_manager.send_message(chat_id, event)
