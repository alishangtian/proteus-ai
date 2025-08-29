"""多Agent管理器，负责管理多个Agent实例和它们之间的事件通信"""

import asyncio
import signal
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, field
import logging
from enum import Enum
import uuid
from threading import Lock
import json
from ..utils.redis_cache import RedisCache, get_redis_connection

logger = logging.getLogger(__name__)


class TeamRole(Enum):
    """团队职责类型枚举（严格模式）"""

    PLANNER = "planner"  # 规划者：负责任务分解和规划
    RESEARCHER = "researcher"  # 研究者：负责信息收集和研究
    CODER = "coder"  # 编码者：负责代码实现
    REPORTER = "reporter"  # 报告者：负责结果汇总和报告
    COORDINATOR = "coordinator"  # 协调者：负责团队协调
    GENERAL_AGENT = "general_agent"  # 通用智能体
    PRODUCT_MANAGER = "product_manager"  # 产品经理
    TEAM_LEADER = "team_leader"  # 团队领导
    CLEANER = "cleaner"  # 保洁员
    TRANSLATOR = "translator"  # 翻译员
    PAPER_SEARCH_EXPERT = "paper_search_expert"  # 论文查询专家

    @classmethod
    def _missing_(cls, value):
        raise ValueError(f"无效的职责类型: {value}，支持类型: {[e.value for e in cls]}")


@dataclass(order=True)
class AgentEvent:
    """Agent事件数据结构"""

    chat_id: str  # 聊天ID
    priority: int  # 优先级，0为最高
    event_id: str = field(compare=False)  # 事件ID
    role_type: TeamRole = field(compare=False)  # 事件职责类型
    sender_id: str = field(compare=False)  # 发送者ID
    sender_role: TeamRole = field(compare=False)  # 发送者角色
    payload: Any = field(compare=False)  # 事件负载
    is_result: bool = field(compare=False, default=False)  # 是否是结果（默认False）


from collections import defaultdict


class EventBus:
    """事件总线核心组件（线程安全）"""

    def __init__(self, agents: Dict[str, Any], event_queues: Dict[str, asyncio.Queue]):
        self.agents = agents
        self.event_queues = event_queues
        self.subscriptions = defaultdict(list)
        self._lock = asyncio.Lock()
        self._match_cache = {}  # 事件匹配缓存
        self._cache_size = 1000  # 最大缓存条目数

    def _clear_old_cache(self):
        """清理过期的缓存条目"""
        if len(self._match_cache) > self._cache_size:
            # 保留最新的cache_size条目
            self._match_cache = dict(
                list(self._match_cache.items())[-self._cache_size :]
            )

    async def subscribe(
        self, agent_id: str, role_type: TeamRole, filters: Optional[Dict] = None
    ):
        """订阅事件（支持多种路由策略和过滤条件）"""
        async with self._lock:
            self.subscriptions[role_type].append(
                {"agent_id": agent_id, "filters": filters or {}}
            )

    async def unsubscribe(self, agent_id: str, role_type: TeamRole):
        """取消订阅"""
        async with self._lock:
            self.subscriptions[role_type] = [
                sub
                for sub in self.subscriptions[role_type]
                if sub["agent_id"] != agent_id
            ]

    async def publish(self, event: AgentEvent) -> None:
        """发布事件（支持异步处理）

        Args:
            event: 要发布的事件对象

        Raises:
            TypeError: 如果事件类型无效
        """
        if not isinstance(event.role_type, TeamRole):
            logger.error(f"非法职责类型: {type(event.role_type).__name__}")
            raise TypeError("职责类型必须为TeamRole枚举实例")

        async with self._lock:
            # 获取匹配的订阅者
            subscribers = self.subscriptions.get(event.role_type, [])

            # 基于role_type分发事件
            for sub in subscribers:
                if self._apply_filters(event, sub["filters"]):
                    await self._deliver_event(sub["agent_id"], event)

    def _apply_filters(self, event: AgentEvent, filters: Dict) -> bool:
        """应用过滤条件（带缓存优化）

        Args:
            event: 要检查的事件
            filters: 过滤条件字典

        Returns:
            bool: 是否通过所有过滤条件
        """
        if not filters:  # 无过滤条件直接通过
            return True

        # 使用缓存避免重复计算
        cache_key = (event.event_id, frozenset(filters.items()))
        if cache_key in self._match_cache:
            return self._match_cache[cache_key]

        result = all(
            getattr(event, key, None) == value for key, value in filters.items()
        )

        # 更新缓存并清理旧条目
        self._match_cache[cache_key] = result
        self._clear_old_cache()
        return result

    async def _deliver_event(self, agent_id: str, event: AgentEvent):
        """实际事件分发方法"""
        if agent_id in self.event_queues:
            await self.event_queues[agent_id].put(event)
            logger.debug(f"Event {event.event_id} delivered to {agent_id}")


class MultiAgentManager:
    """多Agent管理器（单例模式）"""

    _instance = None
    _lock = Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """初始化管理器状态"""
        self.agents: Dict[str, Any] = {}  # 注册的agent实例
        self.event_queues: Dict[str, asyncio.Queue] = (
            {}
        )  # 每个agent的事件队列，负责接收来自Redis的结果
        # 使用 Redis 列表作为事件总线：role queue 用于发布任务，agent queue 用于接收结果
        self.redis_cache = RedisCache()
        self.subscriptions: Dict[TeamRole, List[Dict[str, Any]]] = (
            {}
        )  # 保留订阅信息（兼容旧API）
        self.lock = asyncio.Lock()  # 异步锁
        self._running = False  # 事件循环运行状态
        self._event_loop_task = None  # 事件循环任务引用

    async def _event_loop(self):
        """事件循环的实际实现（从 Redis 的 role_queue 读取事件并委派给对应本地 agent）"""
        logger.info("启动多Agent Redis role_queue 事件监听循环（集中派发模式）")

        while self._running:
            try:
                # 如果没有任何订阅者，短等待后继续
                if not self.subscriptions:
                    await asyncio.sleep(0.5)
                    continue

                # 构建要监听的 role_queue key 列表（只监听有订阅的 role）
                role_keys = []
                for role in list(self.subscriptions.keys()):
                    try:
                        role_keys.append(f"role_queue:{role.value}")
                    except Exception:
                        # 防御性处理：跳过不可解析的role
                        logger.warning(f"无法解析订阅中的 role: {role}")
                        continue

                if not role_keys:
                    await asyncio.sleep(0.5)
                    continue

                # 阻塞式弹出等待任一 role_queue 有事件（timeout 秒为轮询粒度）
                blpop_result = self.redis_cache.blpop(role_keys, timeout=1)
                if not blpop_result:
                    # 无结果，继续下一轮
                    await asyncio.sleep(0.01)
                    continue

                # redis 返回 (key, value)
                key, value = blpop_result
                if not key or not value:
                    continue

                # 从 key 中反推 role_name
                # key 格式: "role_queue:{role_name}"
                try:
                    role_name = key.split("role_queue:")[-1]
                except Exception:
                    logger.warning(f"无法解析 role_queue key: {key}")
                    continue

                # 解析事件体（保持与现有事件格式兼容）
                try:
                    event_dict = json.loads(value)
                except Exception as e:
                    logger.error(f"解析Redis事件JSON失败: {e} value={value}")
                    continue

                # 找到订阅此 role 的本地 agent 列表
                try:
                    role_enum = TeamRole(role_name)
                except Exception:
                    logger.warning(f"未知的 role 类型: {role_name}")
                    continue

                subscribers = self.subscriptions.get(role_enum, [])
                if not subscribers:
                    logger.warning(
                        f"收到 role_queue:{role_name} 事件但无本地订阅者，事件丢弃: {event_dict.get('event_id')}"
                    )
                    continue

                # 将事件分发给匹配的订阅者（非阻塞：创建任务委派）
                for sub in list(subscribers):
                    agent_id = sub.get("agent_id")
                    filters = sub.get("filters") or {}
                    agent = self.agents.get(agent_id)
                    if not agent:
                        logger.warning(f"订阅者 {agent_id} 不在本地注册，跳过事件投递")
                        continue

                    # 过滤检查（简单字典匹配，兼容旧 filters 结构）
                    if filters:
                        passed = True
                        for k, v in filters.items():
                            if event_dict.get(k) != v:
                                passed = False
                                break
                        if not passed:
                            logger.debug(
                                f"事件 {event_dict.get('event_id')} 未通过订阅者 {agent_id} 的过滤器"
                            )
                            continue

                    # 非阻塞委派给 agent 执行（manager 不等待执行结果）
                    try:
                        asyncio.create_task(
                            self._deliver_to_agent(agent, event_dict, agent_id)
                        )
                    except Exception as e:
                        logger.error(
                            f"无法创建任务将事件派发给 {agent_id}: {e}", exc_info=True
                        )

            except asyncio.CancelledError:
                logger.info("事件循环任务被取消")
                break
            except Exception as e:
                logger.error(f"事件循环异常: {str(e)}", exc_info=True)
                await asyncio.sleep(1)  # 异常后稍作等待

        logger.info("事件循环已停止")

    async def start_event_loop(self):
        """启动事件监听循环"""
        if self._running:
            logger.warning("事件循环已在运行")
            return

        # 如果存在旧的任务，确保它已经被取消
        if self._event_loop_task is not None:
            if (
                not self._event_loop_task.done()
                and not self._event_loop_task.cancelled()
            ):
                self._event_loop_task.cancel()
                try:
                    # 等待任务取消完成
                    await asyncio.wait_for(self._event_loop_task, timeout=2.0)
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    logger.warning("取消旧事件循环任务超时或已被取消")

        self._running = True
        # 创建新的事件循环任务
        self._event_loop_task = asyncio.create_task(self._event_loop())

        # 注册信号处理器以优雅地处理进程终止
        try:
            for sig in (signal.SIGTERM, signal.SIGINT):
                asyncio.get_event_loop().add_signal_handler(
                    sig, lambda: asyncio.create_task(self._handle_shutdown())
                )
            logger.info("已注册信号处理器用于优雅关闭")
        except NotImplementedError:
            # Windows不支持add_signal_handler
            logger.warning("当前平台不支持信号处理器，无法注册优雅关闭处理")

    async def _handle_shutdown(self):
        """处理关闭信号"""
        logger.info("接收到关闭信号，正在停止事件循环...")
        await self.stop_event_loop()

    async def stop_event_loop(self):
        """停止事件监听循环"""
        if not self._running:
            logger.warning("事件循环已经停止")
            return

        self._running = False
        logger.info("停止多Agent事件监听循环")

        # 取消事件循环任务
        if self._event_loop_task is not None and not self._event_loop_task.done():
            self._event_loop_task.cancel()
            try:
                # 等待任务取消完成
                await asyncio.wait_for(self._event_loop_task, timeout=2.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                logger.warning("取消事件循环任务超时或已被取消")

        self._event_loop_task = None

    async def _deliver_to_agent(
        self, agent_instance: Any, event_dict: dict, agent_id: str
    ):
        """将解析好的 event_dict 恢复为 AgentEvent 并投递到本地 agent 的事件队列"""
        try:
            # 尝试构建 AgentEvent（兼容缺少字段的情况）
            sender_role = event_dict.get("sender_role")
            try:
                sender_role_enum = TeamRole(sender_role) if sender_role else None
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
            event = AgentEvent(
                priority=event_dict.get("priority", 1),
                chat_id=event_dict.get("chat_id"),
                event_id=event_dict.get("event_id", str(uuid.uuid4())),
                role_type=role_type_enum,
                sender_id=event_dict.get("sender_id"),
                sender_role=sender_role_enum,
                payload=event_dict.get("payload"),
                is_result=event_dict.get("is_result", False),
            )
            # 确保本地队列存在
            if agent_id in self.event_queues:
                await self.event_queues[agent_id].put(event)
                logger.info(
                    f"Delegated event {event.event_id} to local agent queue {agent_id}"
                )
            else:
                logger.warning(
                    f"本地不存在事件队列 agent_queue:{agent_id}，无法投递事件 {event.event_id}"
                )
        except Exception as e:
            logger.error(f"投递事件到本地 agent 失败: {e}", exc_info=True)

    def register_agent(self, agent_id: str, agent_instance: Any):
        """注册一个agent实例（放宽类型检查，支持ReactAgent/Agent等鸭式对象）

        Args:
            agent_id: agent唯一标识
            agent_instance: agent实例，应包含必要的属性（agentcard 等）
        """
        # 允许多种 agent 实现，只要提供必要属性和方法（duck typing）
        if not hasattr(agent_instance, "agentcard"):
            raise TypeError(
                f"agent_instance 缺少 agentcard 属性, 实际是 {type(agent_instance)}"
            )

        self.agents[agent_id] = agent_instance
        self.event_queues[agent_id] = asyncio.Queue()
        logger.info(f"Agent {agent_id} registered")

    def unregister_agent(self, agent_id: str):
        """注销一个agent实例"""
        if agent_id in self.agents:
            del self.agents[agent_id]
            del self.event_queues[agent_id]
            logger.info(f"Agent {agent_id} unregistered")

    async def publish_event(self, event: AgentEvent):
        """发布事件到 Redis 列表（按 role 分发）"""
        async with self.lock:
            try:
                # 将事件序列化为 JSON，使用角色队列进行分发
                event_dict = {
                    "chat_id": event.chat_id,
                    "priority": event.priority,
                    "event_id": event.event_id,
                    "role_type": (
                        event.role_type.value
                        if isinstance(event.role_type, TeamRole)
                        else str(event.role_type)
                    ),
                    "sender_id": event.sender_id,
                    "sender_role": (
                        event.sender_role.value
                        if isinstance(event.sender_role, TeamRole)
                        else (str(event.sender_role) if event.sender_role else None)
                    ),
                    "payload": event.payload,
                    "is_result": event.is_result,
                }
                role_queue_key = f"role_queue:{event.role_type.value}"
                self.redis_cache.rpush(role_queue_key, json.dumps(event_dict))
                logger.debug(
                    f"Event {event.event_id} pushed to Redis role queue {role_queue_key}"
                )
            except Exception as e:
                logger.error(f"发布事件到Redis失败: {e}", exc_info=True)
                raise

    async def get_next_event(self, agent_id: str) -> Optional[AgentEvent]:
        """获取指定agent的下一个事件"""
        if agent_id in self.event_queues and not self.event_queues[agent_id].empty():
            return await self.event_queues[agent_id].get()
        return None

    async def subscribe(
        self, agent_id: str, role_type: TeamRole, filters: Optional[Dict] = None
    ):
        """订阅事件（兼容旧API） — 实际事件通过Redis role queue分发，订阅在本地记录以便管理"""
        async with self.lock:
            subs = self.subscriptions.get(role_type, [])
            subs.append({"agent_id": agent_id, "filters": filters or {}})
            self.subscriptions[role_type] = subs
            logger.info(f"Agent {agent_id} subscribed to role {role_type}")

    async def unsubscribe(self, agent_id: str, role_type: TeamRole):
        """取消订阅"""
        async with self.lock:
            subs = self.subscriptions.get(role_type, [])
            self.subscriptions[role_type] = [
                s for s in subs if s.get("agent_id") != agent_id
            ]
            logger.info(f"Agent {agent_id} unsubscribed from {role_type}")

    def create_event(
        self,
        chat_id: str,
        role_type: TeamRole,
        sender_id: str,
        sender_role: TeamRole,
        payload: Any,
        priority: int = 1,
        is_result: bool = False,
    ) -> AgentEvent:
        """创建新事件"""
        return AgentEvent(
            priority=priority,
            chat_id=chat_id,
            event_id=str(uuid.uuid4()),
            role_type=role_type,
            sender_id=sender_id,
            sender_role=sender_role,
            payload=payload,
            is_result=is_result,  # 默认值
        )


def get_multi_agent_manager() -> MultiAgentManager:
    """获取多Agent管理器单例"""
    return MultiAgentManager()


# 在模块加载时注册进程退出处理器
import atexit


def cleanup_on_exit():
    """在Python解释器退出时执行清理操作"""
    logger.info("Python解释器退出，清理资源...")
    manager = MultiAgentManager()
    if manager._running:
        # 使用同步方式停止事件循环
        manager._running = False
        manager._event_loop_task = None
        logger.info("已强制停止事件循环")


atexit.register(cleanup_on_exit)
