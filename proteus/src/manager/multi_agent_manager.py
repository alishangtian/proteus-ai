"""多Agent管理器，负责管理多个Agent实例和它们之间的事件通信"""

import asyncio
import signal
import weakref
from typing import Dict, Optional, Any, Set
from dataclasses import dataclass, field
import logging
from enum import Enum
import uuid
from threading import Lock

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
        self.event_queues: Dict[str, asyncio.Queue] = {}  # 每个agent的事件队列
        self.event_bus = EventBus(self.agents, self.event_queues)  # 初始化事件总线
        self.lock = asyncio.Lock()  # 异步锁
        self._running = False  # 事件循环运行状态
        self._event_loop_task = None  # 事件循环任务引用

    async def _event_loop(self):
        """事件循环的实际实现"""
        logger.info("启动多Agent事件监听循环")
        
        while self._running:
            try:
                # 检查每个agent的事件队列
                for agent_id, queue in list(self.event_queues.items()):
                    if not queue.empty():
                        event = await queue.get()
                        if agent_id in self.agents:  # 确保agent仍然存在
                            agent = self.agents[agent_id]
                            logger.info(
                                f"Agent {agent_id} 事件队列有新事件 \n event: {event}"
                            )
                            if hasattr(agent, "_handle_event"):
                                await agent._handle_event(event)
                            else:
                                logger.warning(
                                    f"Agent {agent_id} 没有实现_handle_event方法"
                                )
                        else:
                            logger.warning(f"Agent {agent_id} 不存在，丢弃事件")

                await asyncio.sleep(0.1)  # 避免CPU占用过高

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
            if not self._event_loop_task.done() and not self._event_loop_task.cancelled():
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

    def register_agent(self, agent_id: str, agent_instance: Any):
        """注册一个agent实例

        Args:
            agent_id: agent唯一标识
            agent_instance: 必须是Agent类型的实例

        Raises:
            TypeError: 如果agent_instance不是Agent类型
        """
        from ..agent.agent import Agent

        if not isinstance(agent_instance, Agent):
            raise TypeError(
                f"agent_instance必须是Agent类型, 实际是{type(agent_instance)}"
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
        """发布事件到消息系统"""
        async with self.lock:
            await self.event_bus.publish(event)
            logger.debug(f"Event {event.event_id} published via event bus")

    async def get_next_event(self, agent_id: str) -> Optional[AgentEvent]:
        """获取指定agent的下一个事件"""
        if agent_id in self.event_queues and not self.event_queues[agent_id].empty():
            return await self.event_queues[agent_id].get()
        return None

    async def subscribe(
        self, agent_id: str, role_type: TeamRole, filters: Optional[Dict] = None
    ):
        """订阅事件"""
        await self.event_bus.subscribe(
            agent_id=agent_id, role_type=role_type, filters=filters
        )
        logger.info(f"Agent {agent_id}({agent_id}) subscribed to {role_type}")

    async def unsubscribe(self, agent_id: str, role_type: TeamRole):
        """取消订阅"""
        await self.event_bus.unsubscribe(agent_id, role_type)
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
