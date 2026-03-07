"""
Agent 实时状态查询功能单元测试

测试内容：
- ChatAgent 运行时指标初始化
- get_status_info() 返回正确的状态信息
- get_all_agents() 返回所有缓存中的 agent
- 运行时指标在 run() 执行过程中正确更新
"""

import os
import sys
import time
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
    AGENT_STATUS_COMPLETE,
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


class TestChatAgentRuntimeMetrics(unittest.TestCase):
    """测试运行时指标初始化"""

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

    def tearDown(self):
        self.redis_patcher.stop()
        ChatAgent.clear_agents("test-chat-id")

    def test_initial_metrics(self):
        """验证初始运行时指标为默认值"""
        self.assertIsNone(self.agent.start_time)
        self.assertEqual(self.agent.current_iteration, 0)
        self.assertEqual(self.agent.total_input_tokens, 0)
        self.assertEqual(self.agent.total_output_tokens, 0)
        self.assertIsNone(self.agent.task_text)


class TestGetStatusInfo(unittest.TestCase):
    """测试 get_status_info() 方法"""

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
            enable_tools=True,
            max_tool_iterations=10,
            conversation_id="conv-123",
        )
        self.agent.chat_id = "test-chat-id"

    def tearDown(self):
        self.redis_patcher.stop()
        ChatAgent.clear_agents("test-chat-id")

    def test_status_info_before_run(self):
        """验证运行前 get_status_info 返回初始值"""
        info = self.agent.get_status_info()
        self.assertEqual(info["agent_id"], self.agent.agentid)
        self.assertEqual(info["chat_id"], "test-chat-id")
        self.assertEqual(info["status"], AGENT_STATUS_INIT)
        self.assertEqual(info["model_name"], "test-model")
        self.assertEqual(info["elapsed_time"], 0)
        self.assertIsNone(info["task_text"])
        self.assertEqual(info["current_iteration"], 0)
        self.assertEqual(info["max_iterations"], 10)
        self.assertEqual(info["total_input_tokens"], 0)
        self.assertEqual(info["total_output_tokens"], 0)
        self.assertEqual(info["total_tokens"], 0)
        self.assertEqual(info["conversation_id"], "conv-123")

    def test_status_info_with_metrics(self):
        """验证设置指标后 get_status_info 返回正确值"""
        self.agent.start_time = time.time() - 5.0  # 5秒前开始
        self.agent.task_text = "测试查询"
        self.agent.current_iteration = 3
        self.agent.total_input_tokens = 500
        self.agent.total_output_tokens = 200
        self.agent._set_status(AGENT_STATUS_RUNNING)

        info = self.agent.get_status_info()
        self.assertEqual(info["status"], AGENT_STATUS_RUNNING)
        self.assertGreaterEqual(info["elapsed_time"], 4.9)
        self.assertEqual(info["task_text"], "测试查询")
        self.assertEqual(info["current_iteration"], 3)
        self.assertEqual(info["total_input_tokens"], 500)
        self.assertEqual(info["total_output_tokens"], 200)
        self.assertEqual(info["total_tokens"], 700)


class TestGetAllAgents(unittest.TestCase):
    """测试 get_all_agents() 类方法"""

    def setUp(self):
        self.redis_mock, self.store = _make_redis_mock()
        self.redis_patcher = patch(
            "agent.chat_agent.get_redis_connection",
            return_value=self.redis_mock,
        )
        self.redis_patcher.start()

    def tearDown(self):
        self.redis_patcher.stop()
        ChatAgent.clear_agents("chat-1")
        ChatAgent.clear_agents("chat-2")

    def test_empty_cache(self):
        """验证缓存为空时返回空字典"""
        result = ChatAgent.get_all_agents()
        self.assertEqual(result, {})

    def test_multiple_agents(self):
        """验证多个 chat_id 下的 agent 都能返回"""
        agent1 = ChatAgent(stream_manager=None, model_name="m1")
        agent2 = ChatAgent(stream_manager=None, model_name="m2")
        ChatAgent.set_agents("chat-1", [agent1])
        ChatAgent.set_agents("chat-2", [agent2])

        result = ChatAgent.get_all_agents()
        self.assertIn("chat-1", result)
        self.assertIn("chat-2", result)
        self.assertEqual(len(result["chat-1"]), 1)
        self.assertEqual(len(result["chat-2"]), 1)


class TestRunUpdatesMetrics(unittest.TestCase):
    """测试 run() 方法正确更新运行时指标"""

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
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    @patch("agent.chat_agent.count_tokens", return_value=100)
    @patch("agent.chat_agent.conversation_manager")
    @patch("agent.chat_agent.langfuse_wrapper")
    def test_metrics_updated_after_run(self, mock_langfuse, mock_conv_mgr, mock_count):
        """验证 run() 完成后指标已更新"""
        mock_langfuse.dynamic_observe.return_value = lambda f: f

        mock_usage = {"prompt_tokens": 150, "completion_tokens": 80}

        with patch.object(
            self.agent,
            "_execute_llm_generation",
            new_callable=AsyncMock,
            return_value=("response", None, None, mock_usage, None, None, False),
        ), patch.object(
            self.agent,
            "_get_context_window_for_model",
            return_value=131072,
        ):
            result = self._run_async(
                self.agent.run(chat_id="test-chat-id", text="hello world")
            )

        self.assertEqual(result, "response")
        self.assertIsNotNone(self.agent.start_time)
        self.assertEqual(self.agent.task_text, "hello world")
        self.assertEqual(self.agent.total_input_tokens, 150)
        self.assertEqual(self.agent.total_output_tokens, 80)


if __name__ == "__main__":
    unittest.main()
