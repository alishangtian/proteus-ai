from datetime import datetime
import re
from typing import List, Dict, Any, Union, Optional
import asyncio
import logging
from pydantic import BaseModel, Field
import time
import uuid
import threading
import json
from string import Template
from functools import wraps, lru_cache
from contextlib import contextmanager
from src.exception.action_bad import ActionBadException
from src.api.llm_api import call_llm_api
from src.utils.langfuse_wrapper import langfuse_wrapper
from src.api.events import (
    create_action_start_event,
    create_action_complete_event,
    create_tool_progress_event,
    create_tool_retry_event,
    create_agent_start_event,
    create_agent_complete_event,
    create_agent_error_event,
    create_agent_thinking_event,
    create_user_input_required_event,
    create_playbook_update_event,
)
from src.manager.mcp_manager import get_mcp_manager
from src.api.stream_manager import StreamManager
from src.agent.base_agent import (
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
from src.manager.multi_agent_manager import TeamRole
from src.agent.terminition import TerminationCondition, StepLimitTerminationCondition
from src.utils.redis_cache import RedisCache, get_redis_connection
from src.utils.langfuse_wrapper import langfuse_wrapper
from src.manager.tool_memory_manager import ToolMemoryManager
from src.manager.conversation_manager import conversation_manager

# import PLAYBOOK_PROMPT
from src.agent.prompt.playbook_prompt_v3 import PLAYBOOK_PROMPT_v3

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


class ToolCall(BaseModel):
    """
    Represents a tool call with its name and parameters.
    """

    tool_name: str = Field(..., description="The name of the tool to call.")
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="The parameters for the tool call."
    )


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
    def set_agents(cls, chat_id: str, agents: List["ReactAgent"]) -> None:
        """设置指定chat_id下的agent列表"""
        with cls._cache_lock:
            cls._cleanup_cache_if_needed()  # 内存优化
            cls._agent_cache[chat_id] = agents.copy()

    @classmethod
    def clear_agents(cls, chat_id: str) -> None:
        """清除指定chat_id的agent缓存"""
        with cls._cache_lock:
            cls._agent_cache.pop(chat_id, None)

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
        conversation_round: int = 5,
        include_fields: List[IncludeFields] = None,  # agent 组装 prompt 时要选择的字段
        user_name: str = None,  # 用户名，用于隔离工具记忆
        tool_memory_enabled: bool = False,  # 传递工具记忆参数
        sop_memory_enabled: bool = False,  # 传递 SOP 记忆参数
        playbook_model_name: str = "deepseek-chat",
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
        self.conversation_round = conversation_round

        self.scratchpad_items = scratchpad_items if scratchpad_items else []

        self.stream_manager = stream_manager
        self.stopped = False
        self.mcp_manager = get_mcp_manager()
        self.context = context
        self.model_name = model_name
        self.playbook_model_name = playbook_model_name
        self.reasoner_model_name = reasoner_model_name
        self.instruction = instruction
        self.description = description
        self.team_description = team_description
        self.prompt_template = prompt_template  # 存储提示词模板
        self.langfuse_trace = (
            langfuse_wrapper.get_langfuse_instance()
        )  # 使用LangfuseWrapper获取追踪对象
        self.include_fields = include_fields  # agent 组装 prompt 时要选择的字段
        self.user_name = user_name  # 用户名，用于工具记忆隔离
        self.tool_memory_enabled = tool_memory_enabled
        self.sop_memory_enabled = sop_memory_enabled

        # 初始化Redis连接管理器
        self._redis_manager = RedisConnectionManager()

        # 初始化工具记忆管理器
        self._tool_memory_manager = ToolMemoryManager(redis_manager=self._redis_manager)

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
                            "playbook": item.playbook,
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

    def _load_conversation_history(
        self, conversation_id: str, expire_hours: int = 12
    ) -> List[Dict[str, str]]:
        """从Redis list中加载完整的对话历史记录，返回数组格式: [{"role":"user"|"assistant","content":"..."}]

        保持原有逻辑：按时间顺序返回最近 size 轮（每轮包含 user 和 assistant 各一条，存储层为 list）
        """
        try:
            redis_cache = get_redis_connection()
            # 使用conversationid作为key的list存储
            redis_key = f"conversation:{conversation_id}"

            # 检查key是否存在
            if not redis_cache.exists(redis_key):
                logger.info(f"未找到对话历史 (conversation_id: {conversation_id})")
                return []

            # 获取list长度
            total_count = redis_cache.llen(redis_key)
            if total_count == 0:
                return []

            # 计算要获取的记录数量：conversation_round*2条记录(每轮对话包含用户和助手各一条)
            records_to_get = min(self.conversation_round * 2, total_count)

            # 从list右端获取最新的records_to_get条记录
            start_index = max(0, total_count - records_to_get)
            end_index = total_count - 1

            # 获取历史记录
            history_data = redis_cache.lrange(redis_key, start_index, end_index)

            # 解析并过滤过期数据，构造返回数组
            conversation_history: List[Dict[str, str]] = []
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
                        conversation_history.append(
                            {"role": "user", "content": content}
                        )
                    elif item_type == "assistant":
                        conversation_history.append(
                            {"role": "assistant", "content": content}
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

    def _construct_prompt(
        self,
        query: str = None,
        current_iteration: int = 1,
        include_fields: List[IncludeFields] = None,
        context: str = None,
        chat_id: str = None,
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
                    tool_desc_parts = []
                    if hasattr(tool, "full_description") and tool.full_description:
                        tool_desc_parts.append(f"{tool.full_description}")
                    else:
                        # 如果没有full_description，则构建基本描述
                        tool_desc_base = f"{tool.name}"
                        if hasattr(tool, "description") and tool.description:
                            tool_desc_base += f" - {tool.description}"
                        tool_desc_parts.append(tool_desc_base)

                    # 附加工具的历史错误记忆（修正后的事实），如果存在
                    if self.tool_memory_enabled and tool.memory:
                        memories_str = f"**使用指引** {tool.memory}\n"
                        tool_desc_parts.append(memories_str)

                    tool_desc = "\n".join(tool_desc_parts)
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

        planner = ""
        for i, item in enumerate(historical_items, 1):
            # 使用完整的observation而不是摘要
            if item.action == "planner":
                planner = item.observation
                continue
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
        if planner:
            # planner是数组结构的字符串，需要格式化为列表结构
            # 示例['1. Access the GitHub repository at https://github.com/humanlayer/12-factor-agents using a web browser or API client.', "2. Review the repository's README.md file to understand its purpose, goals, and key features.", '3. Examine the repository structure, including directories and key files, to infer the architecture and components.', '4. Check the documentation or wiki (if available) for detailed usage instructions, setup, and examples.', '5. Look for contribution guidelines (e.g., CONTRIBUTING.md) to understand how to contribute, including code standards, pull request processes, and issue reporting.', '6. Summarize the findings into a concise overview covering: what it is, goals, usage, architecture, and contribution process.']
            planner = "\n".join(planner)
            planner = f"# 任务规划，请严格按照此规划执行，并在必要时调用 planner 工具更新此规划 \n{planner}\n"
        all_values = {
            "CURRENT_TIME": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "tools": tools_list,
            "tool_names": tool_names,
            "query": query_value,
            "planner": planner,
            "agent_scratchpad": agent_scratchpad or "暂无",
            "context": context or "暂无",
            "instructions": self.instruction or "暂无",
            "max_iterations": self.max_iterations,
            "current_iteration": current_iteration,
            "playbook": (
                self._load_playbook_from_redis(self.conversation_id) if chat_id else ""
            ),
        }

        agent_prompt = Template(self.prompt_template).safe_substitute(all_values)
        return agent_prompt

    @langfuse_wrapper.dynamic_observe()
    async def _call_model(
        self, messages: Union[str, List[Dict[str, str]]], chat_id: str, model_name: str
    ) -> str:
        # 如果 messages 是字符串，则转换为列表
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]
        # 确保从会话历史加载到的 messages 永远是一个列表，防止为 None 或其他非列表类型导致后续错误
        conversation_history = conversation_manager.load_conversation_history(
            self.conversation_id
        )
        if conversation_history is None:
            conversation_history = []
        elif not isinstance(conversation_history, list):
            try:
                conversation_history = list(conversation_history)
            except Exception:
                conversation_history = []
        # 将当前消息添加到会话历史中
        full_messages = conversation_history + messages

        if not langfuse_wrapper.is_enabled():
            # 如果Langfuse未启用，则直接调用LLM
            resp = await call_llm_api(full_messages, model_name=model_name)
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
                    input={"prompt": full_messages},
                    model_parameters={"temperature": 0.7},  # 可以从配置获取实际参数
                    metadata={"chat_id": chat_id},
                ) as generation:
                    start_time = time.time()
                    resp = await call_llm_api(full_messages, model_name=model_name)
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
                        or len(json.dumps(full_messages).split()),
                        "output_tokens": usage.get("completion_tokens")
                        or usage.get("output_tokens")
                        or len(response_text.split()),
                        "total_tokens": usage.get("total_tokens")
                        or (
                            usage.get("prompt_tokens", 0)
                            + usage.get("completion_tokens", 0)
                        )
                        or (
                            len(json.dumps(full_messages).split())
                            + len(response_text.split())
                        ),
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

    async def _parse_action(self, response_text: str) -> Dict[str, Any]:
        """从输入文本中提取结构化 JSON 数据

        功能：
        - 从输入文本中提取结构化的 JSON 数据
        - 支持两种输入格式：
          1. Thought + Action + Action Input 格式
          2. Thought + Answer 格式

        Args:
            response_text: 输入的响应文本

        Returns:
            Dict[str, Any]: 结构化的 JSON 数据，格式为：
            {
                "thinking": "思考过程",
                "tool": {
                    "name": "工具名称",
                    "params": "参数"
                }
            }
        """
        try:
            # 1. 尝试直接解析为JSON（如果输入已经是JSON格式）
            try:
                parsed_json = json.loads(response_text.strip())
                if (
                    isinstance(parsed_json, dict)
                    and "thinking" in parsed_json
                    and "tool" in parsed_json
                ):
                    # 如果 params 字段是字符串，尝试再次解析为JSON对象
                    if isinstance(parsed_json["tool"].get("params"), str):
                        try:
                            parsed_json["tool"]["params"] = json.loads(
                                parsed_json["tool"]["params"]
                            )
                        except json.JSONDecodeError:
                            pass  # 如果不是有效的JSON字符串，则保持原样
                    logger.debug("直接JSON解析成功")
                    return parsed_json
            except json.JSONDecodeError:
                pass

            # 2. 优先使用正则表达式解析
            regex_result = await self._parse_with_regex(response_text)

            # 如果正则表达式解析成功，直接返回结果
            if regex_result and regex_result.get("tool", {}).get("name"):
                logger.debug("正则表达式解析成功")
                return regex_result

            # 3. 当正则表达式解析失败时，使用LLM进行结构化提取
            logger.info("正则表达式解析失败，尝试使用LLM进行解析")
            llm_extracted_result = await self.extract_from_response(response_text)
            if llm_extracted_result:
                return llm_extracted_result

            # 如果所有解析方法都失败，返回一个默认的错误处理结果
            logger.warning(
                f"所有解析方法均失败，无法从响应中提取有效action: {response_text}"
            )
            return {
                "thinking": "无法解析LLM响应，请检查输出格式。",
                "tool": {
                    "name": "final_answer",
                    "params": "无法解析LLM响应，请检查输出格式。",
                },
            }

        except Exception as e:
            logger.error(f"解析action失败: {e}", exc_info=True)
            # 返回默认的错误处理结果
            return {
                "thinking": f"解析错误: {str(e)}",
                "tool": {
                    "name": "final_answer",
                    "params": "解析失败，无法提供有效答案",
                },
            }

    async def extract_from_response(self, response_text: str) -> Dict[str, Any]:
        try:
            # 构建优化的提示词
            extraction_prompt = self._build_extraction_prompt(response_text)

            # 调用LLM进行提取
            model_to_use = self.reasoner_model_name or self.model_name
            if not model_to_use:
                logger.error("没有可用的模型进行LLM提取")
                return {}

            model_response = await call_llm_api(
                [{"role": "user", "content": extraction_prompt}],
                model_name=model_to_use,
            )

            # 处理返回值（可能是tuple或直接是字符串）
            if isinstance(model_response, tuple) and len(model_response) == 2:
                extracted_text = model_response[0]
            else:
                extracted_text = model_response

            # 解析提取的JSON
            try:
                result = json.loads(extracted_text.strip())
                if isinstance(result, dict) and result:
                    # 如果 params 字段是字符串，尝试再次解析为JSON对象
                    if isinstance(result.get("tool", {}).get("params"), str):
                        try:
                            result["tool"]["params"] = json.loads(
                                result["tool"]["params"]
                            )
                        except json.JSONDecodeError:
                            pass  # 如果不是有效的JSON字符串，则保持原样
                    logger.info("LLM解析成功")
                    return result
            except json.JSONDecodeError:
                logger.warning(f"LLM提取的内容不是有效JSON: {extracted_text}")
            return {}
        except Exception as e:
            logger.warning(f"使用LLM提取结构化数据失败: {e}", exc_info=True)
            return {}

    def _build_extraction_prompt(self, response_text: str) -> str:
        """构建优化的LLM提取提示词

        Args:
            response_text: 原始响应文本

        Returns:
            str: 优化后的提示词
        """
        return f"""你是一个专业的文本解析器，专门从AI助手的响应中提取结构化信息。

请从以下文本中提取思考过程和工具调用信息，并严格按照JSON格式输出。

## 输出格式要求：

### 格式一：工具调用模式
如果文本包含 "Action:" 和 "Action Input:"，请输出：
{{
    "thinking": "Thought后面的思考内容",
    "tool": {{
        "name": "Action后面的工具名称",
        "params": Action Input后面的参数（如果参数是JSON格式，请解析为JSON对象；否则保持字符串）
    }}
}}

### 格式二：最终答案模式
如果文本包含 "Answer:"，请输出：
{{
    "thinking": "Thought后面的思考内容",
    "tool": {{
        "name": "final_answer",
        "params": "Answer后面的完整答案内容"
    }}
}}

### 格式三：无法解析
如果文本中没有明确的结构化信息，请输出：
{{}}

## 解析规则：
1. 提取 "Thought:" 后面的内容作为 thinking
2. 如果有 "Action:" 和 "Action Input:"，提取对应内容
3. 如果有 "Answer:"，将工具名设为 "final_answer"，参数为答案内容
4. Action Input 如果是JSON格式，请解析为JSON对象；否则保持字符串格式
5. 只输出JSON，不要包含任何解释文字

## 待解析文本：
{response_text}

请输出解析结果："""

    def _is_json(self, text: str) -> bool:
        """判断字符串是否是有效的JSON"""
        try:
            json.loads(text)
            return True
        except (json.JSONDecodeError, TypeError):
            return False

    async def _format_python_execute_params(self, code_content: str) -> Dict[str, Any]:
        """
        将 Python 代码块格式化为 python_execute 工具所需的参数结构。
        """
        # 检测并去除 Markdown 代码块标识
        markdown_code_block_pattern = r"```(?:python\n)?(.*?)```"
        markdown_match = re.search(markdown_code_block_pattern, code_content, re.DOTALL)

        if markdown_match:
            cleaned_code_content = markdown_match.group(1).strip()
        else:
            cleaned_code_content = await self._parse_params_with_llm(code_content)
            return cleaned_code_content

        return {
            "code": cleaned_code_content,
            "language": "python",
            "enable_network": True,
        }

    async def _parse_with_regex(self, response_text: str) -> Dict[str, Any]:
        """使用正则表达式解析响应文本

        Args:
            response_text: 输入的响应文本

        Returns:
            Dict[str, Any]: 解析后的结构化数据
        """
        try:
            # 尝试从Markdown代码块中提取内容
            markdown_code_block_pattern = r"```(?:[a-zA-Z0-9]+\n)?(.*?)```"
            markdown_match = re.search(
                markdown_code_block_pattern, response_text, re.DOTALL
            )

            # 检查原始响应文本是否完全被代码块包裹
            full_markdown_match = re.fullmatch(
                markdown_code_block_pattern, response_text, re.DOTALL
            )

            if full_markdown_match:
                # 如果整个响应文本都是一个代码块，则直接使用其内容进行解析
                text = full_markdown_match.group(1).strip()
                logger.debug("从完整的Markdown代码块中提取内容进行解析")
            else:
                # 否则，使用原始文本
                text = response_text.strip()

            # 初始化变量
            thinking = ""
            tool_name = ""
            tool_params = ""

            # 优化的正则表达式模式，支持多行内容提取
            # 使用非贪婪匹配和更精确的边界检测
            # 支持中英文冒号，冒号前后可以有 0 个或多个空格
            thought_pattern = (
                r"Thought\s*[:：]\s*(.*?)(?=\n(?:Action|Answer)\s*[:：]|$)"
            )
            action_pattern = r"Action\s*[:：]\s*(.*?)(?=\nAction Input\s*[:：]|$)"
            action_input_pattern = (
                r"Action Input\s*[:：]\s*(.*?)(?=\n(?:Thought|Action|Answer)\s*[:：]|$)"
            )
            answer_pattern = r"Answer\s*[:：]\s*(.*?)(?=\n(?:Thought|Action)\s*[:：]|$)"

            # 提取 Thought - 支持多行内容
            thought_match = re.search(thought_pattern, text, re.DOTALL | re.IGNORECASE)
            if thought_match:
                thinking = thought_match.group(1).strip()
            else:
                # 如果没有匹配到 Thought，则直接返回 final_answer
                logger.warning(f"未匹配到 Thought，直接返回 final_answer: {text}")
                return {
                    "thinking": "未检测到明确的思考过程，直接返回最终答案。",
                    "tool": {"name": "final_answer", "params": text},
                }

            if re.search(answer_pattern, text, re.DOTALL | re.IGNORECASE):
                answer_match = re.search(
                    answer_pattern, text, re.DOTALL | re.IGNORECASE
                )
                tool_name = "final_answer"
                # 提取Answer后的所有内容，包括换行
                tool_params = answer_match.group(1).strip()
            else:
                # 新增：支持方括号格式的Action模式
                # 格式1：Action: tool_name[param1=value1, param2=value2, ...]
                # 格式2：Action: tool_name[{"key": "value", ...}]
                # 使用 DOTALL 标志使 . 能匹配换行符,支持多行JSON
                # 支持中英文冒号，冒号前后可以有 0 个或多个空格
                action_bracket_pattern = r"Action\s*[:：]\s*([^[\s]+)\[(.*?)\]"

                # 首先尝试方括号格式的Action (使用DOTALL支持多行JSON)
                bracket_action_match = re.search(
                    action_bracket_pattern, text, re.DOTALL | re.IGNORECASE
                )
                if bracket_action_match:
                    tool_name = bracket_action_match.group(1).strip()
                    params_str = bracket_action_match.group(2).strip()

                    # 解析方括号中的参数(支持JSON格式和键值对格式)
                    tool_params = self._parse_bracket_params(params_str)
                else:
                    # 提取标准格式的 Action 和 Action Input
                    action_match = re.search(
                        action_pattern, text, re.DOTALL | re.IGNORECASE
                    )
                    if action_match:
                        tool_name = action_match.group(1).strip()

                    action_input_match = re.search(
                        action_input_pattern, text, re.DOTALL | re.IGNORECASE
                    )
                    if action_input_match:
                        # 提取Action Input后的所有内容，包括换行
                        action_input_text = action_input_match.group(1).strip()
                        logger.info(f"尝试处理转义字符 {action_input_text}")

                        # 尝试解析 Action Input 为 JSON，处理转义字符
                        try:
                            # 尝试解析为JSON，如果失败，可能是包含转义字符的字符串
                            tool_params = json.loads(action_input_text)
                        except json.JSONDecodeError as e:
                            logger.error(f"解析失败 异常 {e}")
                            tool_params = action_input_text
                            # 在返回之前，如果工具是 python_execute，则格式化 params
                            if tool_name == "python_execute":
                                tool_params = await self._format_python_execute_params(
                                    tool_params
                                )
                        except Exception as e:
                            # 其他异常，直接使用原始字符串
                            logger.error(f"其他异常，异常 {e}")
                            tool_params = action_input_text
                            # 在返回之前，如果工具是 python_execute，则格式化 params
                            if tool_name == "python_execute":
                                tool_params = await self._format_python_execute_params(
                                    tool_params
                                )
                    else:
                        tool_params = ""

            # 如果没有找到有效的工具名称，尝试更宽松的匹配
            if not tool_name:
                # 尝试更宽松的模式匹配，处理可能的格式变化
                # 支持中英文冒号，冒号前后可以有 0 个或多个空格
                loose_answer_pattern = r"(?:Answer|答案|回答)\s*[:：]\s*(.*)"
                loose_answer_match = re.search(
                    loose_answer_pattern, text, re.DOTALL | re.IGNORECASE
                )
                if loose_answer_match:
                    tool_name = "final_answer"
                    tool_params = loose_answer_match.group(1).strip()
                else:
                    logger.warning(f"无法从文本中提取有效的工具调用: {text}")
                    # 如果仍然没有找到工具名称，并且之前也没有匹配到 Thought，则返回一个默认的 final_answer
                    return {
                        "thinking": "无法从文本中提取有效的工具调用，直接返回最终答案。",
                        "tool": {"name": "final_answer", "params": text},
                    }

            # 如果 tool_params是字符串，尝试使用_parse_params_with_llm解析参数为 json
            if isinstance(tool_params, str) and tool_name == "python_execute":
                parsed_params = await self._parse_params_with_llm(tool_params)
                return parsed_params

            return {
                "thinking": thinking,
                "tool": {"name": tool_name, "params": tool_params},
            }

        except Exception as e:
            logger.error(f"正则表达式解析失败: {e}", exc_info=True)
            return {
                "thinking": f"解析错误: {str(e)}",
                "tool": {
                    "name": "final_answer",
                    "params": "解析失败，无法提供有效答案",
                },
            }

    def _parse_bracket_params(self, params_str: str) -> Dict[str, Any]:
        """解析方括号中的参数字符串

        Args:
            params_str: 参数字符串，支持以下格式：
                1. JSON格式: {"key": "value", "num": 123}
                2. 键值对格式: query=通义 DeepResearch, language=zh, max_results=5

        Returns:
            Dict[str, Any]: 解析后的参数字典
        """
        try:
            if not params_str.strip():
                return {}

            # 优先尝试解析为JSON格式
            # 检查是否以 { 开头，这是JSON对象的标志
            params_str_stripped = params_str.strip()
            if params_str_stripped.startswith("{") and params_str_stripped.endswith(
                "}"
            ):
                try:
                    parsed_json = json.loads(params_str_stripped)
                    if isinstance(parsed_json, dict):
                        logger.info(f"成功解析JSON格式参数: {parsed_json}")
                        return parsed_json
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON解析失败，尝试键值对格式: {e}")
                    # JSON解析失败，继续尝试键值对格式

            # 如果不是JSON格式或JSON解析失败，尝试使用 _is_json 方法检查
            if self._is_json(params_str):
                parsed = json.loads(params_str)
                if isinstance(parsed, dict):
                    return parsed

            # 解析键值对格式
            params = {}
            # 使用正则表达式分割参数，支持包含逗号的值
            # 匹配 key=value 格式，value可以包含空格和特殊字符
            # 改进：处理值中可能包含的等号，例如 "key=value=with=equals"
            param_pattern = r"([^=,]+?)\s*=\s*([^,]*?)(?=,\s*[^=,]+=|$)"

            # 尝试更灵活的匹配，处理可能没有逗号分隔的情况
            matches = re.findall(param_pattern, params_str)
            if not matches and "=" in params_str:  # 如果没有逗号分隔，但有等号
                parts = params_str.split("=", 1)
                if len(parts) == 2:
                    matches = [(parts[0], parts[1])]

            for key, value in matches:
                key = key.strip()
                value = value.strip()

                # 尝试转换数值类型
                if value.isdigit():
                    params[key] = int(value)
                elif value.lower() in ("true", "false"):
                    params[key] = value.lower() == "true"
                elif value.replace(".", "", 1).isdigit():
                    params[key] = float(value)
                else:
                    # 移除可能的引号
                    if (value.startswith('"') and value.endswith('"')) or (
                        value.startswith("'") and value.endswith("'")
                    ):
                        value = value[1:-1]
                    params[key] = value

            return params

        except Exception as e:
            logger.warning(
                f"解析方括号参数失败: {e}, 原始字符串: {params_str}", exc_info=True
            )
            # 如果解析失败，返回原始字符串
            return params_str

    async def _parse_params_with_llm(self, params_str: str) -> Dict[str, Any]:
        """
        使用LLM解析字符串参数为JSON对象。
        """
        try:
            # 构建用于解析参数的提示词
            prompt = f"""你是一个专业的JSON解析器。请将以下字符串解析为JSON对象。
如果输入本身就是有效的JSON字符串，请直接返回该JSON。
如果输入不是JSON，但可以被合理地转换为JSON（例如，键值对形式），请进行转换。
如果无法转换为JSON，请返回一个空字典 {{}}。

请注意：
1. 只输出JSON，不要包含任何解释文字，不要包含任何 md 代码块标签。
2. 如果值是字符串，请确保用双引号括起来。
3. 如果值是布尔值或数字，请直接使用。
4. 当你认为输入的字符串是代码时，需要对代码进行合理的优化，防止存在语法错误

待解析字符串：
{params_str}

请输出解析结果："""

            model_to_use = self.reasoner_model_name or self.model_name
            if not model_to_use:
                logger.error("没有可用的模型进行LLM参数解析")
                return {}

            model_response = await call_llm_api([{"role": "user", "content": prompt}])

            if isinstance(model_response, tuple) and len(model_response) == 2:
                extracted_text = model_response[0]
            else:
                extracted_text = model_response

            try:
                result = json.loads(extracted_text.strip())
                if isinstance(result, dict):
                    logger.info("LLM参数解析成功")
                    return result
            except json.JSONDecodeError:
                logger.warning(f"LLM解析的参数内容不是有效JSON: {extracted_text}")
            return {}
        except Exception as e:
            logger.warning(f"使用LLM解析参数失败: {e}", exc_info=True)
            return {}

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
                        query=task_text,
                        chat_id=chat_id,
                        stream=True,
                        is_result=is_result,  # 保持原始的is_result标志
                        context=payload.get("context"),
                        include_fields=self.include_fields,
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

    async def _handle_termination(self, ctx: dict) -> bool:
        """检查终止条件"""
        return any(
            tc.should_terminate(self, **ctx) for tc in self.termination_conditions
        )

    async def _process_llm_response(
        self, prompt: str, chat_id: str, context: str = None, query: str = None
    ) -> Dict[str, Any]:
        """处理LLM响应并解析动作"""
        model_response = None
        if self.reasoner_model_name:
            model_response = await asyncio.wait_for(
                self._call_model(
                    [{"role": "user", "content": prompt}],
                    chat_id,
                    self.reasoner_model_name,
                ),
                timeout=self.llm_timeout,
            )
        else:
            model_response = await asyncio.wait_for(
                self._call_model(
                    [{"role": "user", "content": prompt}], chat_id, self.model_name
                ),
                timeout=self.llm_timeout,
            )

        logger.info(f"Iteration LLM Response: {model_response}")
        result_dict = await self._parse_action(model_response)

        # 解析格式化字符串，提取 Thought、Action 和 Action Input.
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

    async def _execute_tool_action(
        self,
        action: str,
        action_input: dict,
        thought: str,
        chat_id: str,
        tool: Tool,
        user_query: Optional[str] = None,
    ) -> tuple:
        """执行工具动作并处理结果

        Args:
            action: 工具名称
            action_input: 工具输入参数
            thought: 思考过程
            chat_id: 会话ID
            tool: 工具实例
            user_query: 当前会话的用户输入，用于工具记忆分析
        """
        action_id = str(uuid.uuid4())

        if action == "final_answer":
            return (action_input, thought, action_id)
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

        # 异步处理工具记忆，不阻塞主流程
        # 无论成功或失败都进行记忆总结
        if self.tool_memory_enabled:
            asyncio.create_task(
                self._tool_memory_manager.process_tool_memory(
                    tool_name=action,
                    action_input=action_input,
                    observation=observation,
                    chat_id=chat_id,
                    is_error=(retry_count > tool.max_retries),
                    error_message=(
                        error_msg if (retry_count > tool.max_retries) else None
                    ),
                    user_query=user_query,
                    user_name=self.user_name,
                    model_name=self.reasoner_model_name or self.model_name,
                    conversation_id=self.conversation_id,
                )
            )

        return observation, thought, action_id

    @langfuse_wrapper.dynamic_observe(name="react_agent_run")
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

            if stream and self.stream_manager:
                event = await create_agent_start_event(query)
                await self.stream_manager.send_message(chat_id, event)

            load_playbook = self._load_playbook_from_redis(self.conversation_id)

            # 剧本初始化
            current_playbook = await self._generate_playbook(
                last_playbook=load_playbook,
                tool_result="",
                chat_id=chat_id,
                model_name=self.model_name or self.reasoner_model_name,
                query=query,
            )
            self._save_playbook_to_redis(self.conversation_id, current_playbook)
            # 运行主循环
            result = await self._run_main_loop(
                chat_id,
                query,
                context,
                stream,
                span,
                include_fields=self.include_fields,
            )
            if stream and self.stream_manager and result:
                event = await create_agent_complete_event(result)
                await self.stream_manager.send_message(chat_id, event)
            # 保存用户查询到对话历史
            if self.conversation_id:
                conversation_manager.save_message(
                    self.conversation_id,
                    {
                        "role": "user",
                        "content": query,
                    },
                )
                # self._save_conversation_to_redis(self.conversation_id, user_query=query)
            # 保存结果到对话历史
            if self.conversation_id:
                conversation_manager.save_message(
                    self.conversation_id,
                    {
                        "role": "assistant",
                        "content": result,
                    },
                )
                # self._save_conversation_to_redis(
                #     self.conversation_id, assistant_answer=result
                # )
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
                # 为每个工具加载其历史执行记忆（包括成功和失败的经验）
                if self.tool_memory_enabled:
                    for tool_name, tool_instance in self.tools.items():
                        tool_instance.memory = (
                            await self._tool_memory_manager.load_tool_memory(
                                tool_name, user_name=self.user_name
                            )
                        )

                # 构造并发送提示
                prompt = self._construct_prompt(
                    query=query,
                    current_iteration=iteration_count,
                    include_fields=include_fields,
                    context=context,
                    chat_id=chat_id,
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
                    await self._execute_tool_action(
                        action, action_input, thought, chat_id, None, user_query=query
                    )
                    # last update_playbook
                    # self.update_playbook(chat_id, thought, action, final_answer, query)
                    """更新playbook"""
                    last_playbook = self._load_playbook_from_redis(self.conversation_id)
                    # 生成新的剧本
                    current_playbook = await self._generate_playbook(
                        last_playbook=last_playbook,
                        tool_result=f"thought:{thought}\n action:{action}\n final_answer:{final_answer}",
                        chat_id=chat_id,
                        model_name=self.model_name or self.reasoner_model_name,
                        query=query,
                    )
                    self._save_playbook_to_redis(self.conversation_id, current_playbook)
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
                        action, action_input, thought, chat_id, tool, user_query=query
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

                # 记忆提取现在由 _execute_tool_action 统一异步处理，无需在此处重复
                # 获取上一步的剧本
                last_playbook = self._load_playbook_from_redis(self.conversation_id)

                # 生成新的剧本
                current_playbook = await self._generate_playbook(
                    last_playbook=last_playbook,
                    tool_result=new_item.to_react_context(index=-1),
                    chat_id=chat_id,
                    model_name=self.model_name or self.reasoner_model_name,
                    query=query,
                )
                self._save_playbook_to_redis(self.conversation_id, current_playbook)

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
                # 对于工具未找到错误
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

    def _load_playbook_from_redis(self, conversation_id: str) -> str:
        """从Redis加载剧本"""
        try:
            with self._redis_manager.get_redis_connection() as redis_cache:
                redis_key = f"playbook:{conversation_id}"
                playbook = redis_cache.get(redis_key)
                if playbook:
                    logger.info(
                        f"从Redis加载剧本成功 (conversation_id: {conversation_id})"
                    )
                    return playbook
                return ""
        except Exception as e:
            logger.error(f"从Redis加载剧本失败: {e}")
            return ""

    def _save_playbook_to_redis(
        self, conversation_id: str, playbook: str, expire_hours: int = 12
    ):
        if playbook is None:
            return
        """将剧本保存到Redis"""
        try:
            with self._redis_manager.get_redis_connection() as redis_cache:
                redis_key = f"playbook:{conversation_id}"
                redis_cache.set(redis_key, playbook, ex=expire_hours * 3600)
                logger.info(f"成功保存剧本到Redis (conversation_id: {conversation_id})")
        except Exception as e:
            logger.error(f"保存剧本到Redis失败: {e}")

    async def _generate_playbook(
        self,
        last_playbook: str,
        tool_result: str,
        chat_id: str,
        model_name: str,
        query: str,
    ) -> str:
        """
        基于上一步的剧本和新的工具结果生成新的剧本。
        """
        system_prompt = Template(PLAYBOOK_PROMPT_v3).safe_substitute(
            query=query,
            last_playbook=last_playbook if last_playbook else "无",
            tool_result=tool_result,
            current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

        messages = [{"role": "user", "content": system_prompt}]
        try:
            playbook = await self._call_model(
                messages, chat_id, self.playbook_model_name
            )

            # 生成 playbook 后立即发送 SSE 事件
            if self.stream_manager:
                try:
                    event = await create_playbook_update_event(playbook)
                    await self.stream_manager.send_message(chat_id, event)
                    logger.info(f"[{chat_id}] 已发送 playbook 更新事件")
                except Exception as e:
                    logger.error(f"[{chat_id}] 发送 playbook 更新事件失败: {e}")

            return playbook
        except Exception as e:
            logger.error(f"生成剧本失败: {e}")
            return None

    async def update_playbook(
        self, chat_id: str, thought: str, action: str, final_answer: str, query: str
    ):
        """更新playbook"""
        last_playbook = self._load_playbook_from_redis(self.conversation_id)
        # 生成新的剧本
        current_playbook = await self._generate_playbook(
            last_playbook=last_playbook,
            tool_result=f"thought:{thought}\n action:{action}\n final_answer:{final_answer}",
            chat_id=chat_id,
            model_name=self.model_name or self.reasoner_model_name,
            query=query,
        )
        self._save_playbook_to_redis(self.conversation_id, current_playbook)

    async def _check_termination(self, iteration_count: int) -> bool:
        """检查终止条件"""
        return any(
            tc.should_terminate(self, current_step=iteration_count)
            for tc in self.termination_conditions
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

    async def _send_agent_complete_event(self, message: str, chat_id: str) -> None:
        """发送agent完成事件"""
        event = await create_agent_complete_event(message)
        await self.stream_manager.send_message(chat_id, event)


# Enable runtime dynamic observation for this module (apply to callables defined in this file).
# Adjust include/exclude regexes as needed. Excluding known explicitly-decorated methods to avoid double-wrapping.
from src.utils.dynamic_observer import auto_apply_here

auto_apply_here(
    globals(),
    include=None,
    exclude=[],
    only_in_module=True,
    verbose=False,
)
