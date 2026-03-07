"""
Agent 运行监控页面单元测试

测试内容：
- 监控页面 HTML 文件存在且包含必要元素
- 监控页面调用的 /agents/status API 返回正确格式
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# 添加 proteus/src 到路径
sys.path.insert(0, "src")

# 设置 Redis 环境变量，防止模块级初始化失败
os.environ.setdefault("REDIS_HOST", "localhost")
os.environ.setdefault("REDIS_PORT", "6379")
os.environ.setdefault("REDIS_PASSWORD", "")

# 在导入 chat_agent 之前，先 mock get_redis_connection
import src.utils.redis_cache as _redis_cache_module
_boot_redis_mock = MagicMock()
_original_get_redis = _redis_cache_module.get_redis_connection
_redis_cache_module.get_redis_connection = lambda: _boot_redis_mock

from agent.chat_agent import ChatAgent, AGENT_STATUS_RUNNING

# 恢复原函数
_redis_cache_module.get_redis_connection = _original_get_redis


def _make_redis_mock():
    """构建模拟 Redis 连接"""
    redis_mock = MagicMock()
    store = {}

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


class TestMonitorPageExists(unittest.TestCase):
    """测试监控页面模板文件存在"""

    def test_monitor_html_exists(self):
        """验证 monitor.html 文件存在"""
        static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
        monitor_path = os.path.join(static_dir, "monitor.html")
        self.assertTrue(os.path.exists(monitor_path), "monitor.html 文件不存在")

    def test_monitor_html_contains_key_elements(self):
        """验证 monitor.html 包含关键页面元素"""
        static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
        monitor_path = os.path.join(static_dir, "monitor.html")
        with open(monitor_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("Agent 运行监控", content)
        # 使用新的按会话分组接口
        self.assertIn("/agents/by_conversation", content)
        self.assertIn("autoRefresh", content)
        self.assertIn("totalCount", content)
        self.assertIn("runningCount", content)


class TestMonitorStatusData(unittest.TestCase):
    """测试监控页面依赖的 agent 状态数据"""

    def setUp(self):
        self.redis_mock, self.store = _make_redis_mock()
        self.redis_patcher = patch(
            "agent.chat_agent.get_redis_connection",
            return_value=self.redis_mock,
        )
        self.redis_patcher.start()

    def tearDown(self):
        self.redis_patcher.stop()
        ChatAgent.clear_agents("monitor-test-1")
        ChatAgent.clear_agents("monitor-test-2")

    def test_status_info_contains_monitor_fields(self):
        """验证 get_status_info 包含监控页面所需的所有字段"""
        agent = ChatAgent(
            stream_manager=None,
            model_name="test-model",
            enable_tools=True,
            max_tool_iterations=5,
        )
        agent.chat_id = "monitor-test-1"
        agent._set_status(AGENT_STATUS_RUNNING)

        info = agent.get_status_info()
        required_fields = [
            "agent_id", "chat_id", "status", "model_name",
            "elapsed_time", "task_text", "current_iteration",
            "max_iterations", "total_input_tokens",
            "total_output_tokens", "total_tokens",
        ]
        for field in required_fields:
            self.assertIn(field, info, f"缺少监控字段: {field}")

    def test_all_agents_returns_multiple_chat_agents(self):
        """验证 get_all_agents 返回多个 chat 的 agent 用于监控展示"""
        agent1 = ChatAgent(stream_manager=None, model_name="model-a")
        agent2 = ChatAgent(stream_manager=None, model_name="model-b")
        ChatAgent.set_agents("monitor-test-1", [agent1])
        ChatAgent.set_agents("monitor-test-2", [agent2])

        all_agents = ChatAgent.get_all_agents()
        self.assertIn("monitor-test-1", all_agents)
        self.assertIn("monitor-test-2", all_agents)

        # 验证可以展平为监控列表
        agents_info = []
        for chat_id, agents in all_agents.items():
            for agent in agents:
                agents_info.append(agent.get_status_info())
        self.assertEqual(len(agents_info), 2)


if __name__ == "__main__":
    unittest.main()
