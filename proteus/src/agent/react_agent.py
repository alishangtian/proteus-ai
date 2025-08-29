from datetime import datetime
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
from contextlib import contextmanager
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
    IncludeFields,
)
from ..manager.multi_agent_manager import TeamRole
from .terminition import TerminationCondition, StepLimitTerminationCondition
from ..utils.redis_cache import RedisCache, get_redis_connection
from ..utils.langfuse_wrapper import langfuse_wrapper

logger = logging.getLogger(__name__)


class RetryableRedisError(Exception):
    """可重试的Redis错误"""

    pass


class NonRetryableRedisError(Exception):
    """不可重试的Redis错误"""

    pass


def enhanced_retry_mechanism(
    max_retries: int = 3, base_delay: float = 0.1, max_delay: float = 2.0
):
    """增强的重试装饰器，支持指数退避和错误分类"""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    # 错误分类：某些错误不应该重试
                    if isinstance(e, (ValueError, TypeError, json.JSONDecodeError)):
                        logger.error(f"不可重试的错误: {e}")
                        raise NonRetryableRedisError(f"不可重试的错误: {e}") from e

                    if attempt < max_retries:
                        # 指数退避策略
                        delay = min(base_delay * (2**attempt), max_delay)
                        logger.warning(
                            f"操作失败，{delay:.2f}秒后重试 (尝试 {attempt + 1}/{max_retries}): {e}"
                        )
                        time.sleep(delay)
                    else:
                        logger.error(f"所有重试都失败: {e}")
                        raise RetryableRedisError(
                            f"重试{max_retries}次后仍然失败: {e}"
                        ) from e

            raise last_exception

        return wrapper

    return decorator


class RedisConnectionManager:
    """Redis连接池管理器，提供连接复用和批量操作优化"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            self._redis_cache = None
            self._connection_pool = None
            self._initialized = True

    @contextmanager
    def get_redis_connection(self):
        """获取Redis连接的上下文管理器，增强异常处理"""
        connection_attempts = 0
        max_connection_attempts = 3

        while connection_attempts < max_connection_attempts:
            try:
                if self._redis_cache is None:
                    self._redis_cache = get_redis_connection()
                yield self._redis_cache
                break
            except Exception as e:
                connection_attempts += 1
                logger.error(
                    f"Redis连接错误 (尝试 {connection_attempts}/{max_connection_attempts}): {e}"
                )

                if connection_attempts < max_connection_attempts:
                    # 重新创建连接
                    self._redis_cache = None
                    time.sleep(0.1 * connection_attempts)  # 递增延迟
                else:
                    raise RetryableRedisError(
                        f"Redis连接失败，已尝试{max_connection_attempts}次"
                    ) from e

    def batch_operations(self, operations: List[Dict[str, Any]]) -> List[Any]:
        """批量执行Redis操作

        Args:
            operations: 操作列表，每个操作包含 {'method': str, 'args': tuple, 'kwargs': dict}

        Returns:
            List[Any]: 操作结果列表
        """
        results = []
        with self.get_redis_connection() as redis_conn:
            # 使用pipeline进行批量操作
            pipe = redis_conn.pipeline()
            try:
                for op in operations:
                    method_name = op.get("method")
                    args = op.get("args", ())
                    kwargs = op.get("kwargs", {})

                    if hasattr(pipe, method_name):
                        method = getattr(pipe, method_name)
                        method(*args, **kwargs)
                    else:
                        logger.warning(f"Redis pipeline不支持方法: {method_name}")

                results = pipe.execute()
            except Exception as e:
                logger.error(f"批量Redis操作失败: {e}")
                # 回退到单个操作
                for op in operations:
                    try:
                        method_name = op.get("method")
                        args = op.get("args", ())
                        kwargs = op.get("kwargs", {})

                        if hasattr(redis_conn, method_name):
                            method = getattr(redis_conn, method_name)
                            result = method(*args, **kwargs)
                            results.append(result)
                    except Exception as single_error:
                        logger.error(f"单个Redis操作失败: {single_error}")
                        results.append(None)

        return results


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
    """基于ReAct模式的智能代理实现

    主要功能:
    - 管理工具执行
    - 与LLM交互
    - 处理对话历史
    - 检查终止条件
    - 处理事件流

    属性:
        _agent_cache: 类级别的agent缓存 {chat_id: [agent_list]}
        _cache_lock: 缓存访问锁
    """

    _agent_cache: Dict[str, List["ReactAgent"]] = {}
    _cache_lock = threading.Lock()

    # 内存优化：限制缓存大小
    _max_cache_size = 1000
    _cache_cleanup_threshold = 0.8  # 当缓存达到80%时开始清理

    @classmethod
    def _cleanup_cache_if_needed(cls) -> None:
        """内存优化：当缓存过大时清理旧的缓存项"""
        if len(cls._agent_cache) > cls._max_cache_size * cls._cache_cleanup_threshold:
            # 按最后访问时间排序，删除最旧的20%
            items_to_remove = int(len(cls._agent_cache) * 0.2)
            sorted_items = sorted(cls._agent_cache.items(), key=lambda x: len(x[1]))
            for chat_id, _ in sorted_items[:items_to_remove]:
                cls._agent_cache.pop(chat_id, None)
            logger.info(f"清理了 {items_to_remove} 个旧的agent缓存项")

    @classmethod
    @langfuse_wrapper.observe_decorator(
        name="get_agents", capture_input=True, capture_output=True
    )
    def get_agents(cls, chat_id: str) -> List["ReactAgent"]:
        """获取指定chat_id下的agent列表副本

        参数:
            chat_id: 聊天会话ID

        返回:
            该chat_id下的agent列表副本(浅拷贝)
        """
        with cls._cache_lock:
            cls._cleanup_cache_if_needed()  # 内存优化
            agents = cls._agent_cache.get(chat_id, [])
            logger.debug(f"Getting {len(agents)} agents for chat {chat_id}")
            return list(agents)

    @classmethod
    @langfuse_wrapper.observe_decorator(
        name="set_agents", capture_input=True, capture_output=True
    )
    def set_agents(cls, chat_id: str, agents: List["ReactAgent"]) -> None:
        """设置指定chat_id下的agent列表"""
        with cls._cache_lock:
            cls._cleanup_cache_if_needed()  # 内存优化
            cls._agent_cache[chat_id] = agents.copy()

    @classmethod
    @langfuse_wrapper.observe_decorator(
        name="clear_agents", capture_input=True, capture_output=True
    )
    def clear_agents(cls, chat_id: str) -> None:
        """清除指定chat_id的agent缓存"""
        with cls._cache_lock:
            cls._agent_cache.pop(chat_id, None)

    @langfuse_wrapper.observe_decorator(
        name="__init__", capture_input=True, capture_output=True
    )
    def __init__(
        self,
        tools: Dict[str, Tool],  # 工具字典映射：名称 -> Tool
        prompt_template: str,  # 提示词模板
        instruction: str = "",  # agent指令
        description: str = "",  # agent描述
        team_description: str = "",  # 团队描述
        timeout: int = 120,  # 超时时间(秒)
        llm_timeout: int = 60,  # LLM调用超时时间(秒)
        max_iterations: int = 10,  # 最大迭代次数
        iteration_retry_delay: int = 60,  # 迭代重试延迟(秒)
        scratchpad_memory_size: int = 100,  # 记忆大小
        cache_size: int = 100,  # 缓存大小
        cache_ttl: int = 3600,  # 缓存TTL(秒)
        stream_manager: StreamManager = None,  # 流管理器
        context: str = None,  # 上下文信息
        model_name: str = None,  # 主模型名称
        reasoner_model_name: str = None,  # 推理模型名称
        agentcard: AgentCard = None,  # agent卡片
        role_type: TeamRole = None,  # 角色类型
        scratchpad_items: List[ScratchpadItem] = None,  # 临时存储项
        termination_conditions: List[TerminationCondition] = None,  # 终止条件列表
        conversation_id: str = None,  # 会话ID
        include_fields: List[IncludeFields] = None,  # agent 组装 prompt 时要选择的字段
    ):
        """初始化ReactAgent

        参数:
            tools: 工具字典 {工具名称: Tool实例}
            prompt_template: 提示词模板字符串
            instruction: agent指令描述
            ...其他参数见上方注释...

        异常:
            AgentError: 如果必要参数缺失
        """
        if role_type is None:
            raise AgentError("role_type must be specified")
        self._is_subscribed = False  # 事件订阅状态标志
        if model_name is None and reasoner_model_name is None:
            raise AgentError("At least one model name must be provided")
        self._pending_user_input = {}  # 存储等待用户输入的状态
        self._user_input_events = {}  # 存储用户输入事件
        self._result_queue = asyncio.Queue()  # 新增：用于存储接收到的结果
        self._current_event_sender_role = None  # 当前处理事件的发送者角色
        if not prompt_template:
            raise AgentError("Prompt template cannot be empty")

        self.tools = tools  # 先直接保存原始工具列表，在_validate_tools中处理
        self.timeout = timeout
        self.llm_timeout = llm_timeout
        self.max_iterations = max_iterations
        self.iteration_retry_delay = iteration_retry_delay
        self.scratchpad_memory_size = scratchpad_memory_size
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
        self.langfuse_trace = (
            langfuse_wrapper.get_langfuse_instance()
        )  # 使用LangfuseWrapper获取追踪对象
        self.include_fields = include_fields  # agent 组装 prompt 时要选择的字段

        # 初始化Redis连接管理器
        self._redis_manager = RedisConnectionManager()

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

    def _get_role_based_redis_key(self, key_type: str, conversation_id: str) -> str:
        """生成基于角色的Redis key，提供向后兼容性

        Args:
            key_type: key类型，如 'historical_scratchpad' 或 'conversation_history'
            conversation_id: 会话ID

        Returns:
            str: 格式化的Redis key，格式：{key_type}:{role}:{conversation_id}
        """
        role_value = (
            self.role_type.value
            if hasattr(self.role_type, "value")
            else str(self.role_type)
        )
        return f"{key_type}:{role_value}:{conversation_id}"

    def _get_legacy_redis_key(self, key_type: str, conversation_id: str) -> str:
        """生成旧版本的Redis key，用于向后兼容性检查

        Args:
            key_type: key类型
            conversation_id: 会话ID

        Returns:
            str: 旧版本格式的Redis key，格式：{key_type}:{conversation_id}
        """
        return f"{key_type}:{conversation_id}"

    def _validate_tools(self) -> None:
        """验证并规范化工具列表"""
        from ..nodes.node_config import NodeConfigManager

        config_manager = NodeConfigManager.get_instance()
        all_tools = config_manager.get_tools()

        if not self.tools:
            # Normalize to dict mapping by name
            self.tools = {t.name: t for t in all_tools}
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

    @langfuse_wrapper.observe_decorator(
        name="_load_historical_scratchpad_items",
        capture_input=True,
        capture_output=True,
    )
    def _load_historical_scratchpad_items(
        self, conversation_id: str, size: int = 5, expire_hours: int = 12
    ) -> List[ScratchpadItem]:
        """从Redis list中加载指定时间内最近size条的历史scratchpad_items

        Args:
            conversation_id: 会话ID，作为Redis中的唯一标识
            size: 要获取的记录数量，默认5条
            expire_hours: 过期时间（小时），默认12小时

        Returns:
            List[ScratchpadItem]: 指定时间内最近size条的历史迭代信息，按时间戳升序排列（先发生的在前）
        """
        try:
            # 使用Redis连接管理器
            with self._redis_manager.get_redis_connection() as redis_cache:
                redis_key = f"tools:{conversation_id}"
                # 获取list长度
                total_count = redis_cache.llen(redis_key)
                if total_count == 0:
                    return []

                # 计算要获取的记录数量
                records_to_get = min(size, total_count)

                # 从list右端获取最新的records_to_get条记录
                start_index = max(0, total_count - records_to_get)
                end_index = total_count - 1

                # 获取历史记录
                history_data = redis_cache.lrange(redis_key, start_index, end_index)

            # 解析并过滤过期数据
            historical_items = []
            current_time = time.time()
            expire_timestamp = current_time - (expire_hours * 3600)

            for item_json in history_data:
                try:
                    item_dict = json.loads(item_json)

                    # 检查是否过期
                    item_timestamp = item_dict.get("timestamp", current_time)
                    if item_timestamp < expire_timestamp:
                        continue

                    # 角色过滤：只加载当前角色的记录
                    item_role = item_dict.get("role_type", "")
                    current_role = (
                        self.role_type.value
                        if hasattr(self.role_type, "value")
                        else str(self.role_type)
                    )
                    if item_role and item_role != current_role:
                        continue

                    scratchpad_item = ScratchpadItem(
                        thought=item_dict.get("thought", ""),
                        action=item_dict.get("action", ""),
                        observation=item_dict.get("observation", ""),
                        action_input=item_dict.get("action_input", "") or "",
                        is_origin_query=item_dict.get("is_origin_query", False),
                        tool_execution_id=item_dict.get("tool_execution_id", ""),
                        role_type=item_dict.get("role_type", "") or "",
                    )

                    # 添加其他可能的属性
                    if "tool_execution_id" in item_dict:
                        scratchpad_item.tool_execution_id = item_dict[
                            "tool_execution_id"
                        ]

                    historical_items.append(scratchpad_item)
                except (json.JSONDecodeError, Exception) as e:
                    logger.warning(f"解析历史scratchpad_item失败: {e}")
                    continue

            if historical_items:
                logger.info(
                    f"从Redis list成功加载 {len(historical_items)} 条工具调用历史 (conversation_id: {conversation_id}, {expire_hours}小时内)"
                )
            else:
                logger.info(
                    f"未找到{expire_hours}小时内的工具调用历史 (conversation_id: {conversation_id})"
                )

            return historical_items

        except Exception as e:
            logger.error(f"从Redis加载工具调用历史失败: {e}")
            return []

    @langfuse_wrapper.observe_decorator(
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
        """将对话记录保存到Redis list中，以conversationid为key
        每次调用只保存一个字段（user或assistant），使用list存储

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
                # 使用conversationid作为key的list存储
                redis_key = f"conversation:{conversation_id}"
                current_timestamp = time.time()

                # 构造对话记录（每次只保存一个字段）
                record = {"timestamp": current_timestamp, "type": "", "content": ""}

                if user_query:
                    record["type"] = "user"
                    record["content"] = user_query
                elif assistant_answer:
                    record["type"] = "assistant"
                    record["content"] = assistant_answer
                else:
                    raise ValueError("必须提供user_query或assistant_answer")

                # 转换为JSON字符串并添加到list右端
                record_json = json.dumps(record, ensure_ascii=False)
                redis_cache.rpush(redis_key, record_json)

                # 设置过期时间
                redis_cache.expire(redis_key, expire_hours * 3600)

                # 获取当前数量并限制总数量：保留最新的100条
                total_count = redis_cache.llen(redis_key)
                if total_count > 100:
                    # 从左端删除多余的旧记录
                    excess_count = total_count - 100
                    for _ in range(excess_count):
                        redis_cache.lpop(redis_key)

                logger.info(
                    f"成功保存对话记录到Redis list (conversation_id: {conversation_id}, "
                    f"timestamp: {current_timestamp}, total_items: {min(total_count, 100)})"
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

    @langfuse_wrapper.observe_decorator(
        name="_save_scratchpad_items_to_redis", capture_input=True, capture_output=True
    )
    def _save_scratchpad_items_to_redis(
        self,
        conversation_id: str,
        scratchpad_items: List[ScratchpadItem],
        expire_hours: int = 12,
        max_retries: int = 3,
        retry_delay: float = 0.1,
    ):
        """将scratchpad items保存到Redis list中，以conversationid为key

        Args:
            conversation_id: 会话ID
            scratchpad_items: 要保存的scratchpad items列表
            expire_hours: 过期时间（小时），默认12小时
            max_retries: 最大重试次数，默认3次
            retry_delay: 重试延迟时间（秒），默认0.1秒
        """
        retry_count = 0
        last_exception = None

        while retry_count <= max_retries:
            try:
                # 使用Redis连接管理器
                with self._redis_manager.get_redis_connection() as redis_cache:
                    redis_key = f"tools:{conversation_id}"
                    current_timestamp = time.time()

                    # 批量保存scratchpad items到list
                    items_to_save = []
                    for item in scratchpad_items:
                        item_dict = {
                            "timestamp": current_timestamp,
                            "thought": item.thought,
                            "action": item.action,
                            "observation": item.observation,
                            "action_input": (
                                item.action_input
                                if hasattr(item, "action_input")
                                else ""
                            ),
                            "is_origin_query": item.is_origin_query,
                            "tool_execution_id": getattr(item, "tool_execution_id", ""),
                            "role_type": (
                                self.role_type.value
                                if hasattr(self.role_type, "value")
                                else str(self.role_type)
                            ),
                        }
                        item_json = json.dumps(item_dict, ensure_ascii=False)
                        items_to_save.append(item_json)

                    # 使用批量操作优化
                    if items_to_save:
                        operations = [
                            {"method": "rpush", "args": (redis_key, *items_to_save)},
                            {
                                "method": "expire",
                                "args": (redis_key, expire_hours * 3600),
                            },
                            {"method": "llen", "args": (redis_key,)},
                        ]

                        results = self._redis_manager.batch_operations(operations)
                        total_count = results[2] if len(results) > 2 else 0

                        # 如果超过限制，批量删除旧记录
                        if total_count > 100:
                            excess_count = total_count - 100
                            cleanup_ops = [
                                {"method": "lpop", "args": (redis_key,)}
                                for _ in range(excess_count)
                            ]
                            self._redis_manager.batch_operations(cleanup_ops)

                    logger.info(
                        f"成功保存{len(scratchpad_items)}条工具调用记录到Redis list (conversation_id: {conversation_id}, total_items: {min(total_count, 100)})"
                    )
                    return  # 成功则直接返回

            except Exception as e:
                last_exception = e
                retry_count += 1
                logger.warning(
                    f"保存工具调用记录到Redis失败 (尝试 {retry_count}/{max_retries}): {str(e)}"
                )
                if retry_count <= max_retries:
                    time.sleep(retry_delay)

        # 所有重试都失败
        logger.error(
            f"保存工具调用记录到Redis失败 (conversation_id: {conversation_id}): {str(last_exception)}"
        )

    @langfuse_wrapper.observe_decorator(
        name="_load_conversation_history", capture_input=True, capture_output=True
    )
    def _load_conversation_history(
        self, conversation_id: str, size: int = 5, expire_hours: int = 12
    ) -> str:
        """从Redis list中加载完整的对话历史记录

        Args:
            conversation_id: 会话ID
            size: 要获取的对话轮次数
            expire_hours: 过期时间(小时)

        Returns:
            str: 格式化的对话历史记录字符串
        """
        try:
            redis_cache = get_redis_connection()
            # 使用conversationid作为key的list存储
            redis_key = f"conversation:{conversation_id}"

            # 检查key是否存在
            if not redis_cache.exists(redis_key):
                logger.info(f"未找到对话历史 (conversation_id: {conversation_id})")
                return ""

            # 获取list长度
            total_count = redis_cache.llen(redis_key)
            if total_count == 0:
                return ""

            # 计算要获取的记录数量：size*2条记录(每轮对话包含用户和助手各一条)
            records_to_get = min(size * 2, total_count)

            # 从list右端获取最新的records_to_get条记录
            start_index = max(0, total_count - records_to_get)
            end_index = total_count - 1

            # 获取历史记录
            history_data = redis_cache.lrange(redis_key, start_index, end_index)

            # 格式化对话历史并过滤过期数据
            conversation_history = []
            current_time = time.time()
            expire_timestamp = current_time - (expire_hours * 3600)

            for item_json in history_data:
                try:
                    item = json.loads(item_json)
                    # 检查是否过期
                    item_timestamp = item.get("timestamp", current_time)
                    if item_timestamp < expire_timestamp:
                        continue

                    item_type = item.get("type", "")
                    content = item.get("content", "")

                    if item_type == "user":
                        conversation_history.append(f"User: {content}")
                    elif item_type == "assistant":
                        conversation_history.append(f"Assistant: {content}")
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

    @langfuse_wrapper.observe_decorator(
        name="_construct_prompt", capture_input=True, capture_output=True
    )
    def _construct_prompt(
        self,
        query: str = None,
        current_iteration: int = 1,
        include_fields: List[IncludeFields] = None,
        context: str = None,
    ) -> str:
        """构造提示模板，使用缓存优化工具描述生成

        新增conversation字段用于传递连续会话历史
        """

        @lru_cache(maxsize=32)  # 增大缓存大小，适应更多工具变化
        def get_tools_description() -> tuple[str, str]:
            """获取工具描述和工具名称列表，每个工具前加上编号
            返回:
                tuple: (工具描述字符串, 工具名称列表字符串)
            """
            with self._cache_lock:  # 加锁保证线程安全
                tool_names = ", ".join(sorted(self.tools.keys()))  # 排序保证一致性
                tools_desc = []
                for i, tool in enumerate(
                    sorted(self.tools.values(), key=lambda x: x.name), 1
                ):
                    # 在工具描述前加上编号，格式：[编号] 工具描述
                    if hasattr(tool, "full_description") and tool.full_description:
                        tool_desc = f"[{i:02d}] {tool.full_description}"
                    else:
                        # 如果没有full_description，则构建基本描述
                        tool_desc = f"[{i:02d}] {tool.name}"
                        if hasattr(tool, "description") and tool.description:
                            tool_desc += f" - {tool.description}"
                    tools_desc.append(tool_desc)
                return "\n".join(tools_desc), tool_names

        tools_list, tool_names = get_tools_description()
        agent_prompt = None

        # 从Redis加载agent scratchpad
        agent_scratchpad = ""
        historical_items = []
        if hasattr(self, "conversation_id") and self.conversation_id:
            try:
                # 使用 scratchpad_memory_size 控制回溯的条数
                historical_items = self._load_historical_scratchpad_items(
                    self.conversation_id, size=self.scratchpad_memory_size
                )
            except Exception as e:
                # 如果从Redis加载失败，降级回退到本地的scratchpad_items以保证可用性
                logger.warning(
                    f"从Redis加载scratchpad失败，回退到本地scratchpad_items: {str(e)}"
                )
                historical_items = self.scratchpad_items
        else:
            # 无conversation_id时使用本地内存中的scratchpad_items
            historical_items = self.scratchpad_items

        for i, item in enumerate(historical_items, 1):
            # 使用完整的observation而不是摘要
            agent_scratchpad += (
                item.to_react_context(
                    index=i,
                    use_summary=False,
                    include_fields=include_fields,
                )
                + "\n"
            )

        # 如果没有任何scratchpad内容，使用默认提示 "暂无"
        if not agent_scratchpad or not agent_scratchpad.strip():
            agent_scratchpad = "暂无"

        # 统一提示模板构造
        # query赋值优化：只有当query为None时，才从scratchpad_items中查找is_origin_query为true的item，否则直接使用query
        query_value = query
        all_values = {
            "CURRENT_TIME": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "tools": tools_list,
            "tool_names": tool_names,
            "query": query_value,
            "agent_scratchpad": agent_scratchpad,
            "context": context or "",
            "instructions": self.instruction,
            "conversations": (
                self._load_conversation_history(self.conversation_id)
                if hasattr(self, "conversation_id") and self.conversation_id
                else ""
            ),
            "max_iterations": self.max_iterations,
            "current_iteration": current_iteration,
        }

        agent_prompt = Template(self.prompt_template).safe_substitute(all_values)
        return agent_prompt

    async def _call_model(self, prompt: str, chat_id: str, model_name: str) -> str:
        if not langfuse_wrapper.is_enabled():
            # 如果Langfuse未启用，则直接调用LLM
            messages = [{"role": "user", "content": prompt}]
            resp = await call_llm_api(messages, model_name=model_name)
            # 兼容 llm_api 可能返回 (text, usage) 或 直接返回 text
            if isinstance(resp, tuple) and len(resp) == 2:
                return resp[0]
            return resp

        # Langfuse 启用时，使用 LangfuseWrapper 进行追踪
        try:
            langfuse_instance = langfuse_wrapper.get_langfuse_instance()
            with langfuse_instance.start_as_current_span(name="llm-call") as span:
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
                    resp = await call_llm_api(messages, model_name=model_name)
                    # 兼容返回 (text, usage) 或 text
                    if isinstance(resp, tuple) and len(resp) == 2:
                        response_text, usage = resp
                    else:
                        response_text, usage = resp, {}

                    logger.info(f"usage : ${usage}")

                    # 尝试使用真实usage字段，如果没有则使用之前的估算
                    usage_details = {
                        "input_tokens": usage.get("prompt_tokens")
                        or usage.get("input_tokens")
                        or len(prompt.split()),
                        "output_tokens": usage.get("completion_tokens")
                        or usage.get("output_tokens")
                        or len(response_text.split()),
                        "total_tokens": usage.get("total_tokens")
                        or (
                            usage.get("prompt_tokens", 0)
                            + usage.get("completion_tokens", 0)
                        )
                        or (len(prompt.split()) + len(response_text.split())),
                    }

                    generation.update(
                        output=response_text,
                        usage_details=usage_details,
                        cost_details={"total_cost": usage.get("total_cost", 0.0023)},
                    )

                    # 评分
                    generation.score(name="relevance", value=0.95, data_type="NUMERIC")

                    # 记录执行时间
                    execution_time = time.time() - start_time
                    self.metrics.record_call(execution_time, is_error=False)

                    return response_text

        except Exception as e:
            execution_time = time.time() - start_time if "start_time" in locals() else 0
            self.metrics.record_call(execution_time, is_error=True)

            if "generation" in locals():
                try:
                    if hasattr(generation, "update"):
                        generation.update(
                            output={"error": str(e)},
                            status_message=f"LLM call failed: {str(e)}",
                            metadata={"execution_time": execution_time},
                        )
                except Exception as update_error:
                    logger.warning(f"Failed to update generation span: {update_error}")

            raise LLMAPIError(f"LLM API call failed: {str(e)}")

    # 类级别预编译正则表达式，提升性能
    _THOUGHT_PATTERN = re.compile(
        r"Thought\s*[:：]\s*(.*?)(?=\nAction\s*[:：]|\nAnswer\s*[:：]|$)", re.DOTALL
    )
    _ACTION_PATTERN = re.compile(
        r"Action\s*[:：]\s*(.*?)(?=\nAction Input\s*[:：]|$)", re.DOTALL
    )
    _ACTION_INPUT_PATTERN = re.compile(
        r"Action Input\s*[:：]\s*(.*?)(?=\nThought\s*[:：]|\nAction\s*[:：]|\nAnswer\s*[:：]|$)",
        re.DOTALL,
    )
    _ANSWER_PATTERN = re.compile(r"Answer\s*[:：]\s*(.*)", re.DOTALL)

    @langfuse_wrapper.observe_decorator(
        name="_parse_action", capture_input=True, capture_output=True
    )
    async def _parse_action(
        self, response_text: str, chat_id: str, query: str = None
    ) -> Dict[str, Any]:
        """解析LLM响应为格式化字符串，支持纯文本解析（Action格式和Answer格式）

        优化后返回以下两种格式之一：
        1. 工具调用格式：
           Thought: [推理过程]
           Action: [工具名称]
           Action Input: {JSON参数}

        2. 最终答案格式：
           Thought: [最终推理结论]
           Answer: [最终答案]
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
                thought = thought_match.group(1).strip()
                action = action_match.group(1).strip()
                action_input_str = action_input_match.group(1).strip()

                # 尝试将 action_input 解析为 JSON，解析成功则直接作为 params（dict/list）
                params = None
                logger.info(f"action_input_str: {action_input_str}")
                try:
                    params = json.loads(action_input_str)
                except json.JSONDecodeError:
                    # 有时候模型会使用单引号或其他轻微格式问题，尝试替换单引号再解析
                    try:
                        safe_str = action_input_str.replace("'", '"')
                        params = json.loads(safe_str)
                    except Exception:
                        params = None
                return {
                    "thinking": thought,
                    "tool": {
                        "name": action,
                        "params": params,
                    },
                }

            # 处理Answer格式响应
            answer_match = self._ANSWER_PATTERN.search(response_text)
            if answer_match:
                thought = (
                    thought_match.group(1).strip()
                    if thought_match
                    else "基于以上分析，我可以提供最终答案"
                )
                answer = answer_match.group(1).strip()
                return {
                    "thinking": thought,
                    "tool": {
                        "name": "final_answer",
                        "params": answer,
                    },
                }

            # 默认返回整个响应作为最终答案
            return {
                "thinking": "基于当前信息提供答案",
                "tool": {
                    "name": "final_answer",
                    "params": response_text,
                },
            }

        except Exception as e:
            logger.error(f"解析响应文本失败: {str(e)}\n响应内容: {response_text[:200]}")
            return {
                "thinking": "解析响应时发生错误",
                "tool": {
                    "name": "final_answer",
                    "params": "解析失败，无法提供有效答案",
                },
            }

    @langfuse_wrapper.observe_decorator(
        name="set_user_input", capture_input=True, capture_output=True
    )
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

    @langfuse_wrapper.observe_decorator(
        name="wait_for_user_input", capture_input=True, capture_output=True
    )
    async def wait_for_user_input(
        self, node_id: str, prompt: str, chat_id: str, input_type: str, agent_id: str
    ) -> Any:
        """等待用户输入

        Args:
            node_id: 节点ID
            prompt: 提示信息
            chat_id: 聊天会话ID

        Returns:
            Any: 用户输入值
        """
        logger.info(f"Waiting for user input for node {node_id} agentid: {agent_id}")
        # 创建用户输入请求事件
        if self.stream_manager:
            event = await create_user_input_required_event(
                node_id=node_id,
                prompt=prompt,
                input_type=input_type,
                agent_id=agent_id,
            )
            logger.info(f"create user input required event: {event}")
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

    @langfuse_wrapper.observe_decorator(
        name="stop", capture_input=True, capture_output=True
    )
    async def stop(self) -> None:
        """停止 agent：设置停止标志、取消监听任务并从 role_agents 列表移除自身"""
        self.stopped = True

        # 取消后台监听任务
        try:
            task = getattr(self, "_agent_listener_task", None)
            if task and not task.done():
                task.cancel()
                try:
                    await asyncio.wait_for(task, timeout=1.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    logger.debug("Agent listener task cancelled")
        except Exception as e:
            logger.warning(f"取消 agent listener 任务时出错: {e}")

        # 从 role_agents 列表中移除自身
        try:
            role_key = getattr(self, "_role_agents_key", None) or (
                f"role_agents:{self.role_type.value}"
                if getattr(self, "role_type", None)
                else None
            )
            if role_key:
                try:
                    redis_cache = get_redis_connection()
                    # lrem count=0 表示移除所有匹配项
                    redis_cache.lrem(role_key, 0, self.agentcard.agentid)
                    logger.info(
                        f"Unregistered agent {self.agentcard.agentid} from {role_key}"
                    )
                except Exception as e:
                    logger.warning(f"从 Redis 移除 agent 注册失败: {e}")
        except Exception as e:
            logger.error(f"停止 agent 时处理 role_agents 移除失败: {e}", exc_info=True)

    @langfuse_wrapper.observe_decorator(
        name="clear_context", capture_input=True, capture_output=True
    )
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

    @langfuse_wrapper.observe_decorator(
        name="setup_event_subscriptions", capture_input=True, capture_output=True
    )
    async def setup_event_subscriptions(self, agentid: str) -> None:
        """初始化事件订阅：只监听角色队列 role_queue:{role}，确保只处理与当前角色匹配的事件
        与 handoff 节点保持一致的 key 设计。
        """
        if getattr(self, "_is_subscribed", False):
            return
        try:
            # 标记已订阅并启动监听任务
            self._is_subscribed = True
            loop = asyncio.get_running_loop()
            self._agent_listener_task = loop.create_task(
                self._listen_agent_queue(agentid)
            )

            # 在 Redis 中注册该 agent 到 role_agents:{role}
            try:
                redis_cache = RedisCache()
                role_key = f"role_agents:{self.role_type.value}"
                redis_cache.rpush(role_key, agentid)
                # 记录 key 以便后续取消注册
                self._role_agents_key = role_key
                logger.info(f"Registered agent {agentid} to Redis list {role_key}")
            except Exception as e:
                logger.warning(f"注册 agent 到 role_agents 列表失败: {e}")

            logger.info(
                f"ReactAgent {agentid} subscribed to role_queue:{self.role_type.value}"
            )
        except Exception as e:
            logger.error(f"Failed to setup_event_subscriptions for {agentid}: {e}")
            raise

    async def _listen_agent_queue(self, agentid: str):
        """优化后的队列监听：只支持从和自己角色对应的序列中获取事件数据

        监听策略：
        1. 只监听 role_queue:{role} - 接收与当前角色匹配的任务
        2. 严格的角色验证，确保只处理匹配当前agent角色的事件
        3. 简化事件处理逻辑，提高性能和可靠性

        注意：redis blocking blpop 使用同步 redis-py 会阻塞事件循环。这里将阻塞调用移动到线程池执行以避免阻塞 asyncio 事件循环。
        """
        redis_cache = RedisCache()
        # 只监听当前角色对应的队列
        role_queue_key = f"role_queue:{self.role_type.value}"
        queue_keys = [role_queue_key]

        loop = asyncio.get_running_loop()
        logger.info(
            f"Agent {agentid} (角色: {self.role_type.value}) 开始监听角色队列: {role_queue_key}"
        )

        while not self.stopped:
            try:
                # 将阻塞的 blpop 调用放到线程池中执行，避免阻塞事件循环
                try:
                    blpop_result = await loop.run_in_executor(
                        None, redis_cache.blpop, queue_keys, 1
                    )
                except Exception as ex:
                    logger.warning(f"redis blpop 在线程池执行失败: {ex}")
                    await asyncio.sleep(0.1)
                    continue

                if not blpop_result:
                    await asyncio.sleep(0.01)
                    continue

                queue_key, value = blpop_result
                if not queue_key or not value:
                    continue

                logger.debug(f"Agent {agentid} 从角色队列接收到消息")

                try:
                    event_dict = json.loads(value)
                except Exception as e:
                    logger.error(f"解析队列事件 JSON 失败: {e} value={value}")
                    continue

                # 严格的角色验证：只处理匹配当前agent角色的事件
                event_role = event_dict.get("role_type")

                # 角色匹配验证 - 必须完全匹配当前agent的角色
                if event_role != self.role_type.value:
                    logger.warning(
                        f"Agent {agentid} 收到不匹配的角色事件: {event_role} != {self.role_type.value}，跳过处理"
                    )
                    continue

                logger.debug(f"角色验证通过: {event_role} == {self.role_type.value}")

                sender_id = event_dict.get("sender_id")
                sender_role = event_dict.get("sender_role")
                is_result = event_dict.get("is_result", False)
                payload = event_dict.get("payload", {}) or {}
                chat_id = event_dict.get("chat_id")

                logger.info(
                    f"Agent {agentid} 处理角色匹配事件: is_result={is_result}, sender_role={sender_role}"
                )

                # 优化：统一事件处理流程，接收到后都会去处理事件
                try:
                    # 构建任务文本
                    task_text = ""
                    if is_result:
                        # 对于结果事件，需要特殊处理
                        result_data = payload.get("context")
                        if result_data is not None:

                            # 将结果放到scratchpad中
                            if isinstance(result_data, dict):
                                task_text = f"处理结果: {result_data.get('task', '')}: {result_data.get('description', '')}".strip(
                                    ": "
                                )
                                result_observation = (
                                    f"接收到结果数据: {str(result_data)}"
                                )
                            else:
                                task_text = f"处理结果: {str(result_data)}"
                                result_observation = f"接收到结果: {str(result_data)}"

                            # 创建结果项并添加到scratchpad
                            result_item = ScratchpadItem(
                                thought=f"接收到来自其他agent的结果",
                                action="receive_result",
                                observation=result_observation,
                                action_input=str(result_data),
                                is_origin_query=False,
                                tool_execution_id="",
                                role_type=(
                                    self.role_type.value
                                    if hasattr(self.role_type, "value")
                                    else str(self.role_type)
                                ),
                            )
                            self.scratchpad_items.append(result_item)
                            logger.info(f"Agent {agentid} 将结果添加到scratchpad")
                        else:
                            logger.warning(f"Agent {agentid} 接收到空结果")
                            task_text = "处理空结果事件"
                    else:
                        # 普通任务事件处理
                        if isinstance(payload, dict):
                            task_text = f"{payload.get('task','')}: {payload.get('description','')}".strip(
                                ": "
                            )
                        else:
                            task_text = str(payload)

                    # 统一处理：清空上下文并执行任务
                    logger.info(f"Agent {agentid} 接收到事件并处理: {task_text}")
                    if not is_result:
                        # 只有非结果事件才清空上下文，结果事件需要保留scratchpad中的结果信息
                        self.clear_context()
                    result_value = await self.run(
                        task_text,
                        chat_id,
                        stream=True,
                        is_result=is_result,  # 保持原始的is_result标志
                        context=payload.get("context"),
                    )
                except Exception as e:
                    logger.error(f"执行角色队列事件任务失败: {e}", exc_info=True)
                    result_value = str(e)

                # 如果有发送者且我们产生了结果（非 is_result 原始事件），则发送 handoff 结果回 sender 的 agent_queue
                if sender_id and result_value is not None:
                    await self._send_result_to_sender_queue(
                        sender_role,
                        chat_id,
                        result_value,
                        event_dict.get("event_id"),
                        payload,
                    )

            except Exception as e:
                logger.error(f"队列监听循环异常: {e}", exc_info=True)
                await asyncio.sleep(0.5)

    def _create_tool_span(
        self, action: str, action_input: dict, action_id: str, chat_id: str, tool
    ):
        """创建工具执行的Langfuse span"""
        if not langfuse_wrapper.is_enabled():
            return None

        try:
            langfuse_instance = langfuse_wrapper.get_langfuse_instance()
            span = langfuse_instance.span(
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
            return span
        except Exception as e:
            logger.error(f"Failed to create tool span: {str(e)}")
            return None

    def _update_tool_span(self, span, result, start_time=None, is_error=False):
        """更新工具span状态"""
        if not span:
            return

        try:
            if is_error:
                span.update(
                    output={"error": result},
                    status_message=f"Tool failed: {result}",
                )
            else:
                span.update(
                    output={"result": result},
                    metadata=(
                        {"execution_time": time.time() - start_time}
                        if start_time
                        else None
                    ),
                )
            span.end()
        except Exception as e:
            logger.error(f"Failed to update tool span: {str(e)}")

    @langfuse_wrapper.observe_decorator(
        name="_handle_termination", capture_input=True, capture_output=True
    )
    async def _handle_termination(self, ctx: dict) -> bool:
        """检查终止条件"""
        return any(
            tc.should_terminate(self, **ctx) for tc in self.termination_conditions
        )

    @langfuse_wrapper.observe_decorator(
        name="_process_llm_response", capture_input=True, capture_output=True
    )
    async def _process_llm_response(
        self, prompt: str, chat_id: str, context: str = None, query: str = None
    ) -> Dict[str, Any]:
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

        # 解析格式化字符串，提取 Thought、Action 和 Action Input
        # result_dict = self._parse_formatted_response(parsed_response)
        return result_dict

    def _parse_formatted_response(self, formatted_response: str) -> Dict[str, Any]:
        """解析格式化响应字符串为字典格式

        输入格式:
        Thought: [思考内容]
        Action: [动作名称]
        Action Input: [参数内容]

        返回:
        {
            "thinking": "思考内容",
            "tool": {
                "name": "动作名称",
                "params": 参数内容
            }
        }
        """
        try:
            lines = formatted_response.strip().split("\n")
            thought = ""
            action = ""
            action_input = ""

            for line in lines:
                line = line.strip()
                if line.startswith("Thought:"):
                    thought = line[8:].strip()  # 移除 "Thought:" 前缀
                elif line.startswith("Action:"):
                    action = line[7:].strip()  # 移除 "Action:" 前缀
                elif line.startswith("Action Input:"):
                    action_input = line[13:].strip()  # 移除 "Action Input:" 前缀

            # 解析 action_input，尝试将其转换为适当格式
            if action_input:
                try:
                    # 尝试解析为JSON
                    params = json.loads(action_input)
                except json.JSONDecodeError:
                    # 如果不是JSON，则直接使用字符串
                    params = action_input
            else:
                params = ""

            return {
                "thinking": thought,
                "tool": {
                    "name": action,
                    "params": params,
                },
            }
        except Exception as e:
            logger.error(
                f"解析格式化响应失败: {str(e)}\n响应内容: {formatted_response}"
            )
            return {
                "thinking": f"解析错误: {str(e)}",
                "tool": {
                    "name": "final_answer",
                    "params": "解析失败，无法提供有效答案",
                },
            }

    @langfuse_wrapper.observe_decorator(
        name="_execute_tool_action", capture_input=True, capture_output=True
    )
    async def _execute_tool_action(
        self,
        action: str,
        action_input: dict,
        thought: str,
        chat_id: str,
        tool: Tool,
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
            action_input["agent_id"] = self.agentcard.agentid
            action_input["agent"] = self

        if action == "workflow_execute":
            action_input["chat_id"] = chat_id
            action_input["stream_manager"] = self.stream_manager

        if action == "handoff":
            action_input["chat_id"] = chat_id
            action_input["sender_id"] = (self.agentcard.agentid,)
            action_input["sender_role"] = self.role_type.value

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
                logger.warning(
                    f"工具 {action} 执行失败 (尝试 {retry_count}/{tool.max_retries + 1}): {error_msg}"
                )

                if stream:
                    event = await create_tool_retry_event(
                        action, retry_count, tool.max_retries, error_msg
                    )
                    await self.stream_manager.send_message(chat_id, event)

                if retry_count > tool.max_retries:
                    logger.error(
                        f"工具 {action} 在{retry_count}次重试后仍然失败: {error_msg}"
                    )
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

        return observation, thought, action_id

    @langfuse_wrapper.observe_decorator(
        name="run", capture_input=True, capture_output=True
    )
    async def run(
        self,
        query: str,
        chat_id: str,
        stream: bool = True,
        is_result: bool = False,
        context: str = None,
        include_fields: List[IncludeFields] = None,
    ) -> str:
        await self._register_agent(chat_id)
        """执行Agent主逻辑"""
        span = None
        if langfuse_wrapper.is_enabled():
            try:
                span = langfuse_wrapper.get_langfuse_instance().span(
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
                # 添加初始查询item（将query作为action_input保存，便于后续追踪）
                self.scratchpad_items.append(
                    ScratchpadItem(
                        is_origin_query=True,
                        thought=query,
                        action_input=query,
                        tool_execution_id="",
                        role_type=(
                            self.role_type.value
                            if hasattr(self.role_type, "value")
                            else str(self.role_type)
                        ),
                    )
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
            result = await self._run_main_loop(
                chat_id,
                query,
                context,
                stream,
                span,
                include_fields=include_fields,
            )
            if stream and self.stream_manager and result:
                event = await create_agent_complete_event(result)
                await self.stream_manager.send_message(chat_id, event)
            # 保存结果到对话历史
            if self.conversation_id:
                self._save_conversation_to_redis(
                    self.conversation_id, assistant_answer=result
                )
            if span:
                try:
                    if hasattr(span, "update"):
                        span.update(output={"result": result})
                    if hasattr(span, "end"):
                        span.end()
                    logger.info("Completed Langfuse span for ReactAgent execution")
                except AttributeError:
                    logger.debug("Span does not support update/end methods")
                except Exception as e:
                    logger.warning(f"Failed to update Langfuse span: {str(e)}")
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

    async def _prepare_main_loop(
        self, chat_id: str, query: str, context: str, span: Any
    ) -> None:
        """准备主循环运行环境"""
        if langfuse_wrapper.is_enabled() and span:
            try:
                # 安全的 span 更新，处理不同类型的 span 对象
                if hasattr(span, "update"):
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
                else:
                    logger.debug("Span object does not support update method")
            except AttributeError as e:
                logger.warning(f"Span update method not available: {str(e)}")
            except Exception as e:
                logger.error(f"Failed to update Langfuse span status: {str(e)}")

    @langfuse_wrapper.observe_decorator(
        name="_run_main_loop", capture_input=True, capture_output=True
    )
    async def _run_main_loop(
        self,
        chat_id: str,
        query: str,
        context: str,
        stream: bool,
        span: Any = None,
        include_fields: List[IncludeFields] = None,
    ) -> str:
        """运行Agent主循环"""
        await self._prepare_main_loop(chat_id, query, context, span)

        observations = []
        iteration_count = 0
        final_answer = None
        last_error = None

        while iteration_count < self.max_iterations and not self.stopped:
            if self.stopped:
                return "agent stoped"

            iteration_count += 1

            # 检查终止条件
            if await self._check_termination(iteration_count):
                logger.info(f"满足终止条件，迭代次数: {iteration_count}")
                return "agent terminated"

            try:
                # 构造并发送提示
                prompt = self._construct_prompt(
                    query=query,
                    current_iteration=iteration_count,
                    include_fields=include_fields,
                    context=context,
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
                    # 简化处理：直接使用答案内容，不再处理工具ID相关逻辑
                    if isinstance(action_input, dict) and "answer" in action_input:
                        # 新格式：只取答案部分
                        final_answer = action_input["answer"]
                    else:
                        # 兼容旧格式：直接是答案字符串
                        final_answer = action_input
                    break

                # 验证工具
                if not action or action not in self.tools:
                    raise ToolNotFoundError(f"无效动作: {action}")

                # 执行工具
                tool = self.tools[action]
                tool_span = None
                if langfuse_wrapper.is_enabled():
                    try:
                        tool_span = langfuse_wrapper.get_langfuse_instance().span(
                            name=f"tool_{action}",
                            input={"action_input": action_input},
                        )
                    except Exception as e:
                        logger.error(f"Failed to create tool span: {str(e)}")

                observation, thought, tool_execution_id = (
                    await self._execute_tool_action(
                        action, action_input, thought, chat_id, tool
                    )
                )

                if tool_span:
                    try:
                        if hasattr(tool_span, "update"):
                            tool_span.update(
                                output={
                                    "observation": observation if observation else ""
                                }
                            )
                        if hasattr(tool_span, "end"):
                            tool_span.end()
                    except AttributeError:
                        logger.debug("Tool span does not support update/end methods")
                    except Exception as e:
                        logger.warning(f"Failed to update/end tool span: {str(e)}")

                # 保存执行记录，记录action_input作为param（当为复杂对象时序列化为JSON）
                try:
                    param_str = (
                        json.dumps(action_input, ensure_ascii=False)
                        if isinstance(action_input, (dict, list))
                        else str(action_input)
                    )
                except Exception:
                    param_str = str(action_input)
                new_item = ScratchpadItem(
                    thought=thought,
                    action=action,
                    observation=observation,
                    action_input=param_str,
                    tool_execution_id=tool_execution_id,
                    role_type=(
                        self.role_type.value
                        if hasattr(self.role_type, "value")
                        else str(self.role_type)
                    ),
                )
                self.scratchpad_items.append(new_item)
                observations.append(observation)

                # 每次工具执行后立即保存到Redis
                if self.conversation_id:
                    try:
                        self._save_scratchpad_items_to_redis(
                            self.conversation_id, [new_item]
                        )
                        logger.debug(f"工具执行结果已保存到Redis: {tool_execution_id}")
                    except Exception as e:
                        logger.error(f"保存工具执行结果失败: {str(e)}")

                # 如果当前动作是 handoff，在执行完成并保存后返回 None
                if action == "handoff":
                    logger.info(
                        f"[{chat_id}] Action 'handoff' executed and saved: exiting _run_main_loop and returning None"
                    )
                    return None

            except ActionBadException as e:
                logger.error(
                    f"[{chat_id}] 动作异常 (迭代 {iteration_count}): {e.message}"
                )
                final_answer = e.message
                break
            except asyncio.TimeoutError:
                logger.error(f"[{chat_id}] LLM响应超时 (迭代 {iteration_count})")
                # 超时后重试，但不增加错误记录到scratchpad
                await asyncio.sleep(self.iteration_retry_delay)
                continue
            except ToolNotFoundError as e:
                last_error = str(e)
                logger.error(
                    f"[{chat_id}] 工具未找到 (迭代 {iteration_count}): {last_error}"
                )

                # 对于工具未找到错误，直接终止而不是重试
                final_answer = f"工具执行错误: {last_error}"
                break
            except ToolExecutionError as e:
                last_error = str(e)
                logger.error(
                    f"[{chat_id}] 工具执行错误 (迭代 {iteration_count}): {last_error}"
                )

                if langfuse_wrapper.is_enabled() and span:
                    try:
                        if hasattr(span, "update"):
                            span.update(output={"tool_execution_error": last_error})
                    except AttributeError:
                        logger.debug("Span does not support update method")
                    except Exception as e:
                        logger.warning(
                            f"Failed to update main span with error: {str(e)}"
                        )

                error_item = ScratchpadItem(
                    thought=f"工具执行失败: {last_error}",
                    action="",
                    observation=last_error,
                    action_input=last_error,
                    tool_execution_id="",
                    role_type=(
                        self.role_type.value
                        if hasattr(self.role_type, "value")
                        else str(self.role_type)
                    ),
                )
                self.scratchpad_items.append(error_item)
                await asyncio.sleep(self.iteration_retry_delay)
            except Exception as e:
                last_error = str(e)
                logger.error(
                    f"[{chat_id}] 未知迭代错误 (迭代 {iteration_count}): {last_error}",
                    exc_info=True,
                )

                if langfuse_wrapper.is_enabled() and span:
                    try:
                        if hasattr(span, "update"):
                            span.update(output={"last_error": last_error})
                    except AttributeError:
                        logger.debug("Span does not support update method")
                    except Exception as e:
                        logger.warning(
                            f"Failed to update main span with error: {str(e)}"
                        )

                error_item = ScratchpadItem(
                    thought=f"系统错误: {last_error}",
                    action="",
                    observation=last_error,
                    action_input=last_error,
                    tool_execution_id="",
                    role_type=(
                        self.role_type.value
                        if hasattr(self.role_type, "value")
                        else str(self.role_type)
                    ),
                )
                self.scratchpad_items.append(error_item)
                await asyncio.sleep(self.iteration_retry_delay)
        return final_answer

    @langfuse_wrapper.observe_decorator(
        name="_check_termination", capture_input=True, capture_output=True
    )
    async def _check_termination(self, iteration_count: int) -> bool:
        """检查终止条件"""
        return any(
            tc.should_terminate(self, current_step=iteration_count)
            for tc in self.termination_conditions
        )

    @langfuse_wrapper.observe_decorator(
        name="_cleanup_resources", capture_input=True, capture_output=True
    )
    def _cleanup_resources(self):
        """清理资源和状态"""
        try:
            self._pending_user_input.clear()
            self._user_input_events.clear()
            logger.debug("Agent资源清理完成")
        except Exception as e:
            logger.error(f"清理Agent资源时发生错误: {str(e)}")

    async def _send_result_to_sender_queue(
        self,
        sender_role: str,
        chat_id: str,
        result_value: Any,
        original_event_id: str,
        original_payload: Dict[str, Any],
    ) -> None:
        """将任务执行结果发送回发起者角色对应的队列

        优化策略：
        1. 发送到 sender_role 对应的角色队列 role_queue:{sender_role}
        2. 保持与 handoff 节点一致的事件格式和队列设计
        3. 通过角色队列确保结果能被正确的角色处理
        """
        redis_cache = RedisCache()
        handoff_event = {
            "chat_id": chat_id,
            "priority": 0,
            "event_id": str(uuid.uuid4()),
            "role_type": sender_role,  # 发送到 sender_role 对应的角色队列
            "sender_id": self.agentcard.agentid,
            "sender_role": (
                self.role_type.value
                if hasattr(self.role_type, "value")
                else str(self.role_type)
            ),
            "payload": {
                "context": {  # 使用 context 字段包装结果，与 handoff 节点保持一致
                    "result": result_value,
                    "task": (
                        original_payload.get("task", "")
                        if isinstance(original_payload, dict)
                        else ""
                    ),
                    "description": (
                        original_payload.get("description", "")
                        if isinstance(original_payload, dict)
                        else ""
                    ),
                },
                "metadata": {
                    "agent_id": self.agentcard.agentid,
                    "timestamp": datetime.now().isoformat(),
                    "original_event_id": original_event_id,
                    "origin_query": (
                        (
                            original_payload.get("task", "")
                            + "\n"
                            + original_payload.get("description", "")
                        )
                        if isinstance(original_payload, dict)
                        else ""
                    ),
                },
            },
            "is_result": True,
        }
        try:
            # 发送到 sender_role 对应的角色队列，与 handoff 节点保持一致的设计
            sender_role_queue_key = f"role_queue:{sender_role}"
            redis_cache.rpush(
                sender_role_queue_key,
                json.dumps(handoff_event, ensure_ascii=False),
            )
            logger.info(
                f"Agent {self.agentcard.agentid} 发送结果到角色队列 {sender_role_queue_key} (original event: {original_event_id})"
            )
        except Exception as e:
            logger.error(
                f"将 handoff 结果写入角色队列失败: {e}",
                exc_info=True,
            )

    @langfuse_wrapper.observe_decorator(
        name="_send_agent_complete_event", capture_input=True, capture_output=True
    )
    async def _send_agent_complete_event(self, message: str, chat_id: str) -> None:
        """发送agent完成事件"""
        event = await create_agent_complete_event(message)
        await self.stream_manager.send_message(chat_id, event)
