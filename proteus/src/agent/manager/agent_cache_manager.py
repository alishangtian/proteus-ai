import threading
import logging
from typing import List, Dict
from src.utils.langfuse_wrapper import langfuse_wrapper

logger = logging.getLogger(__name__)


class AgentCacheManager:
    """管理ReactAgent实例的缓存"""

    _agent_cache: Dict[str, List[Any]] = {}  # 使用 Any 来避免循环引用
    _cache_lock = threading.Lock()

    _max_cache_size = 1000
    _cache_cleanup_threshold = 0.8

    @classmethod
    def _cleanup_cache_if_needed(cls) -> None:
        """内存优化：当缓存过大时清理旧的缓存项"""
        if len(cls._agent_cache) > cls._max_cache_size * cls._cache_cleanup_threshold:
            items_to_remove = int(len(cls._agent_cache) * 0.2)
            # 假设列表长度可以作为活跃度的简单指标
            sorted_items = sorted(cls._agent_cache.items(), key=lambda x: len(x[1]))
            for chat_id, _ in sorted_items[:items_to_remove]:
                cls._agent_cache.pop(chat_id, None)
            logger.info(f"清理了 {items_to_remove} 个旧的agent缓存项")

    @classmethod
    @langfuse_wrapper.observe_decorator(
        name="get_agents", capture_input=True, capture_output=True
    )
    def get_agents(cls, chat_id: str) -> List[Any]:
        """获取指定chat_id下的agent列表副本"""
        with cls._cache_lock:
            cls._cleanup_cache_if_needed()
            agents = cls._agent_cache.get(chat_id, [])
            logger.debug(f"Getting {len(agents)} agents for chat {chat_id}")
            return list(agents)

    @classmethod
    @langfuse_wrapper.observe_decorator(
        name="set_agents", capture_input=True, capture_output=True
    )
    def set_agents(cls, chat_id: str, agents: List[Any]) -> None:
        """设置指定chat_id下的agent列表"""
        with cls._cache_lock:
            cls._cleanup_cache_if_needed()
            cls._agent_cache[chat_id] = agents.copy()

    @classmethod
    @langfuse_wrapper.observe_decorator(
        name="clear_agents", capture_input=True, capture_output=True
    )
    def clear_agents(cls, chat_id: str) -> None:
        """清除指定chat_id的agent缓存"""
        with cls._cache_lock:
            cls._agent_cache.pop(chat_id, None)

    @classmethod
    async def register_agent(cls, chat_id: str, agent: Any) -> None:
        """注册当前agent到缓存"""
        with cls._cache_lock:
            if chat_id not in cls._agent_cache:
                cls._agent_cache[chat_id] = []
            if not any(
                a.agentcard.agentid == agent.agentcard.agentid
                for a in cls._agent_cache[chat_id]
            ):
                cls._agent_cache[chat_id].append(agent)
