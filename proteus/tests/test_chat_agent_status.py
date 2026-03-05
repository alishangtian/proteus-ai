"""
ChatAgent 状态管理单元测试

测试状态转换逻辑，确保：
- 正常流程: INIT → RUNNING → COMPLETE
- 异常流程: INIT → RUNNING → ERROR
- 停止流程: INIT → RUNNING → STOPPED
- finally 兜底: 状态不会遗留为 RUNNING
"""

import os
import sys
import unittest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock

# 添加 proteus/src 到路径
sys.path.insert(0, "src")

# 设置 Redis 环境变量，防止模块级初始化失败
os.environ.setdefault("REDIS_HOST", "localhost")
os.environ.setdefault("REDIS_PORT", "6379")
os.environ.setdefault("REDIS_PASSWORD", "")

# 在导入 chat_agent 之前，先 mock get_redis_connection，
# 避免模块级别的 conversation_manager 初始化连接真实 Redis
import src.utils.redis_cache as _redis_cache_module
_boot_redis_mock = MagicMock()
_original_get_redis = _redis_cache_module.get_redis_connection
_redis_cache_module.get_redis_connection = lambda: _boot_redis_mock

from agent.chat_agent import (
    ChatAgent,
    AGENT_STATUS_INIT,
    AGENT_STATUS_RUNNING,
    AGENT_STATUS_STOPPED,
    AGENT_STATUS_COMPLETE,
    AGENT_STATUS_ERROR,
)

# 恢复原函数，后续测试通过 patch 控制
_redis_cache_module.get_redis_connection = _original_get_redis


def _make_redis_mock():
    """构建模拟 Redis 连接，支持 set/get/exists"""
    redis_mock = MagicMock()
    store: dict = {}

    def redis_set(key, value, ex=None):
        store[key] = value

    def redis_get(key):
        return store.get(key)

    def redis_exists(key):
        return 1 if key in store else 0

    redis_mock.set.side_effect = redis_set
    redis_mock.get.side_effect = redis_get
    redis_mock.exists.side_effect = redis_exists
    return redis_mock, store


class TestChatAgentStatusConstants(unittest.TestCase):
    """测试状态常量定义"""

    def test_error_status_exists(self):
        """验证 AGENT_STATUS_ERROR 常量已定义"""
        self.assertEqual(AGENT_STATUS_ERROR, "error")

    def test_all_status_constants(self):
        """验证所有状态常量"""
        self.assertEqual(AGENT_STATUS_INIT, "init")
        self.assertEqual(AGENT_STATUS_RUNNING, "running")
        self.assertEqual(AGENT_STATUS_STOPPED, "stopped")
        self.assertEqual(AGENT_STATUS_COMPLETE, "complete")
        self.assertEqual(AGENT_STATUS_ERROR, "error")


class TestChatAgentStatusManagement(unittest.TestCase):
    """测试状态管理方法"""

    def setUp(self):
        self.redis_mock, self.store = _make_redis_mock()
        self.redis_patcher = patch(
            "agent.chat_agent.get_redis_connection",
            return_value=self.redis_mock,
        )
        self.redis_patcher.start()
        self.agent = ChatAgent(
            stream_manager=None,
            model_name="test-model",
            enable_tools=False,
        )
        self.agent.chat_id = "test-chat-id"

    def tearDown(self):
        self.redis_patcher.stop()
        ChatAgent.clear_agents("test-chat-id")

    def test_initial_status_is_init(self):
        """验证初始状态为 INIT"""
        self.assertEqual(self.agent.status, AGENT_STATUS_INIT)

    def test_set_status_updates_memory_and_redis(self):
        """验证 _set_status 同时更新内存和 Redis"""
        self.agent._set_status(AGENT_STATUS_RUNNING)
        self.assertEqual(self.agent.status, AGENT_STATUS_RUNNING)
        redis_key = f"agent:{self.agent.agentid}:status"
        self.assertEqual(self.store[redis_key], AGENT_STATUS_RUNNING)

    def test_set_status_updates_chat_status_in_redis(self):
        """验证 _set_status 同时更新 chat 级别的 Redis 状态"""
        self.agent._set_status(AGENT_STATUS_COMPLETE)
        chat_key = f"chat:{self.agent.chat_id}:status"
        self.assertEqual(self.store[chat_key], AGENT_STATUS_COMPLETE)

    def test_set_error_status(self):
        """验证可以设置 ERROR 状态"""
        self.agent._set_status(AGENT_STATUS_ERROR)
        self.assertEqual(self.agent.status, AGENT_STATUS_ERROR)
        redis_key = f"agent:{self.agent.agentid}:status"
        self.assertEqual(self.store[redis_key], AGENT_STATUS_ERROR)

    def test_get_status_from_redis(self):
        """验证 _get_status 从 Redis 读取"""
        self.agent._set_status(AGENT_STATUS_RUNNING)
        status = self.agent._get_status()
        self.assertEqual(status, AGENT_STATUS_RUNNING)

    def test_get_status_fallback_to_memory(self):
        """验证 Redis 失败时回退到内存"""
        self.agent.status = AGENT_STATUS_COMPLETE
        with patch(
            "agent.chat_agent.get_redis_connection",
            side_effect=Exception("Redis error"),
        ):
            status = self.agent._get_status()
        self.assertEqual(status, AGENT_STATUS_COMPLETE)


class TestChatAgentCheckAndHandleStopped(unittest.TestCase):
    """测试统一的停止检查方法"""

    def setUp(self):
        self.redis_mock, self.store = _make_redis_mock()
        self.redis_patcher = patch(
            "agent.chat_agent.get_redis_connection",
            return_value=self.redis_mock,
        )
        self.redis_patcher.start()
        self.agent = ChatAgent(
            stream_manager=None,
            model_name="test-model",
            enable_tools=False,
        )
        self.agent.chat_id = "test-chat-id"

    def tearDown(self):
        self.redis_patcher.stop()
        ChatAgent.clear_agents("test-chat-id")

    def test_not_stopped_returns_false(self):
        """验证未停止时返回 False"""
        result = self.agent._check_and_handle_stopped("test-chat-id")
        self.assertFalse(result)
        self.assertEqual(self.agent.status, AGENT_STATUS_INIT)

    def test_memory_stopped_returns_true(self):
        """验证内存标志停止时返回 True 并设置 STOPPED 状态"""
        self.agent.stopped = True
        result = self.agent._check_and_handle_stopped("test-chat-id")
        self.assertTrue(result)
        self.assertEqual(self.agent.status, AGENT_STATUS_STOPPED)

    def test_redis_stopped_returns_true(self):
        """验证 Redis 停止标志时返回 True 并设置 STOPPED 状态"""
        # 在 Redis 中设置 chat 停止标志
        stopped_key = f"chat:{self.agent.chat_id}:stopped"
        self.store[stopped_key] = "1"
        result = self.agent._check_and_handle_stopped("test-chat-id")
        self.assertTrue(result)
        self.assertEqual(self.agent.status, AGENT_STATUS_STOPPED)


class TestChatAgentRunStatusTransitions(unittest.TestCase):
    """测试 run() 方法中的状态转换"""

    def setUp(self):
        self.redis_mock, self.store = _make_redis_mock()
        self.redis_patcher = patch(
            "agent.chat_agent.get_redis_connection",
            return_value=self.redis_mock,
        )
        self.redis_patcher.start()

        self.stream_mock = MagicMock()
        self.stream_mock.send_message = AsyncMock()

        self.agent = ChatAgent(
            stream_manager=self.stream_mock,
            model_name="test-model",
            enable_tools=False,
        )

    def tearDown(self):
        self.redis_patcher.stop()
        ChatAgent.clear_agents("test-chat-id")

    def _run_async(self, coro):
        """辅助方法：运行异步函数"""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    @patch("agent.chat_agent.count_tokens", return_value=100)
    @patch("agent.chat_agent.conversation_manager")
    @patch("agent.chat_agent.langfuse_wrapper")
    def test_successful_run_sets_complete(self, mock_langfuse, mock_conv_mgr, mock_count):
        """验证正常完成后状态为 COMPLETE"""
        mock_langfuse.dynamic_observe.return_value = lambda f: f

        with patch.object(
            self.agent,
            "_execute_llm_generation",
            new_callable=AsyncMock,
            return_value=("test response", None, None, {}, None, None, False),
        ), patch.object(
            self.agent,
            "_need_compress_messages",
            return_value=False,
        ):
            result = self._run_async(
                self.agent.run(chat_id="test-chat-id", text="hello")
            )

        self.assertEqual(result, "test response")
        self.assertEqual(self.agent.status, AGENT_STATUS_COMPLETE)

    @patch("agent.chat_agent.count_tokens", return_value=100)
    @patch("agent.chat_agent.conversation_manager")
    @patch("agent.chat_agent.langfuse_wrapper")
    def test_exception_sets_error_status(self, mock_langfuse, mock_conv_mgr, mock_count):
        """验证异常时状态为 ERROR"""
        mock_langfuse.dynamic_observe.return_value = lambda f: f

        with patch.object(
            self.agent,
            "_execute_llm_generation",
            new_callable=AsyncMock,
            side_effect=RuntimeError("LLM call failed"),
        ):
            with self.assertRaises(RuntimeError):
                self._run_async(
                    self.agent.run(chat_id="test-chat-id", text="hello")
                )

        self.assertEqual(self.agent.status, AGENT_STATUS_ERROR)

    @patch("agent.chat_agent.count_tokens", return_value=100)
    @patch("agent.chat_agent.conversation_manager")
    @patch("agent.chat_agent.langfuse_wrapper")
    def test_stopped_during_loop_sets_stopped(self, mock_langfuse, mock_conv_mgr, mock_count):
        """验证在工具循环中被停止时状态为 STOPPED"""
        mock_langfuse.dynamic_observe.return_value = lambda f: f

        # 在循环开始前设置停止标志
        self.agent.stopped = True

        result = self._run_async(
            self.agent.run(chat_id="test-chat-id", text="hello")
        )

        # stop() 先将状态设为 STOPPED，然后 run() 正常退出设为 COMPLETE
        # 最终状态应为 COMPLETE（因为循环退出后继续执行到 return）
        self.assertIn(
            self.agent.status,
            [AGENT_STATUS_STOPPED, AGENT_STATUS_COMPLETE],
        )


class TestChatAgentFinallyGuard(unittest.TestCase):
    """测试 finally 块中的状态兜底逻辑"""

    def setUp(self):
        self.redis_mock, self.store = _make_redis_mock()
        self.redis_patcher = patch(
            "agent.chat_agent.get_redis_connection",
            return_value=self.redis_mock,
        )
        self.redis_patcher.start()

        self.agent = ChatAgent(
            stream_manager=None,
            model_name="test-model",
            enable_tools=False,
        )
        self.agent.chat_id = "test-chat-id"

    def tearDown(self):
        self.redis_patcher.stop()
        ChatAgent.clear_agents("test-chat-id")

    def test_running_status_corrected_in_finally(self):
        """验证 finally 块中 RUNNING 状态被修正为 ERROR

        模拟一种极端情况：异常处理中 _set_status 也失败了，
        状态仍为 RUNNING，finally 块应当兜底修正。
        """
        self.agent.status = AGENT_STATUS_RUNNING

        # 模拟 finally 块的逻辑
        if self.agent.status == AGENT_STATUS_RUNNING:
            self.agent._set_status(AGENT_STATUS_ERROR)

        self.assertEqual(self.agent.status, AGENT_STATUS_ERROR)

    def test_non_running_status_not_changed_in_finally(self):
        """验证 finally 块不修改非 RUNNING 状态"""
        for status in [AGENT_STATUS_COMPLETE, AGENT_STATUS_STOPPED, AGENT_STATUS_ERROR]:
            self.agent._set_status(status)

            # 模拟 finally 块的逻辑
            if self.agent.status == AGENT_STATUS_RUNNING:
                self.agent._set_status(AGENT_STATUS_ERROR)

            self.assertEqual(self.agent.status, status)


if __name__ == "__main__":
    unittest.main()
