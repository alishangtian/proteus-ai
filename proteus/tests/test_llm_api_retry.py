"""
LLM API 网络重试逻辑单元测试

测试要点：
- 指数退避延迟计算正确性
- 网络错误识别准确性
- 连接器创建（首次 vs 重试）
- NETWORK_EXCEPTIONS 元组包含所有预期异常类型
"""

import unittest
import asyncio
import sys
import os
from unittest.mock import MagicMock

# 添加 proteus/src 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Mock langfuse 和其他不可用的依赖，避免 ModuleNotFoundError
sys.modules.setdefault("langfuse", MagicMock())
sys.modules.setdefault("langfuse.decorators", MagicMock())
sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("redis", MagicMock())

# Mock langfuse_config 和 langfuse_wrapper
import src.utils.langfuse_config as _langfuse_config
_langfuse_config.LangfuseConfigManager = MagicMock()
import src.utils.langfuse_wrapper as _langfuse_wrapper
_mock_wrapper = MagicMock()
_mock_wrapper.dynamic_observe = lambda: lambda f: f
_langfuse_wrapper.langfuse_wrapper = _mock_wrapper

import aiohttp
from api.llm_api import (
    _calculate_retry_delay,
    _is_network_error,
    _create_connector,
    NETWORK_EXCEPTIONS,
    NETWORK_ERROR_KEYWORDS,
)


class TestCalculateRetryDelay(unittest.TestCase):
    """测试指数退避延迟计算"""

    def test_first_attempt_delay(self):
        """首次重试延迟应基于 base_delay"""
        delay = _calculate_retry_delay(0, base_delay=1.0, max_delay=30.0)
        # attempt=0: delay = 1.0 * 2^0 = 1.0, jitter in [0, 0.5]
        self.assertGreaterEqual(delay, 1.0)
        self.assertLessEqual(delay, 1.5)

    def test_second_attempt_delay(self):
        """第二次重试延迟应指数增长"""
        delay = _calculate_retry_delay(1, base_delay=1.0, max_delay=30.0)
        # attempt=1: delay = 1.0 * 2^1 = 2.0, jitter in [0, 1.0]
        self.assertGreaterEqual(delay, 2.0)
        self.assertLessEqual(delay, 3.0)

    def test_third_attempt_delay(self):
        """第三次重试延迟应继续指数增长"""
        delay = _calculate_retry_delay(2, base_delay=1.0, max_delay=30.0)
        # attempt=2: delay = 1.0 * 2^2 = 4.0, jitter in [0, 2.0]
        self.assertGreaterEqual(delay, 4.0)
        self.assertLessEqual(delay, 6.0)

    def test_max_delay_cap(self):
        """延迟应被 max_delay 封顶"""
        delay = _calculate_retry_delay(10, base_delay=1.0, max_delay=30.0)
        # 2^10 = 1024, 但 min(1024, 30) = 30, jitter in [0, 15]
        self.assertGreaterEqual(delay, 30.0)
        self.assertLessEqual(delay, 45.0)

    def test_delay_always_positive(self):
        """延迟始终为正数"""
        for attempt in range(20):
            delay = _calculate_retry_delay(attempt)
            self.assertGreater(delay, 0)

    def test_custom_base_delay(self):
        """自定义基础延迟"""
        delay = _calculate_retry_delay(0, base_delay=2.0, max_delay=60.0)
        # attempt=0: delay = 2.0 * 2^0 = 2.0, jitter in [0, 1.0]
        self.assertGreaterEqual(delay, 2.0)
        self.assertLessEqual(delay, 3.0)


class TestIsNetworkError(unittest.TestCase):
    """测试网络错误识别"""

    def test_connection_error(self):
        self.assertTrue(_is_network_error(Exception("Connection refused")))

    def test_timeout_error(self):
        self.assertTrue(_is_network_error(Exception("Request timeout occurred")))

    def test_disconnected_error(self):
        self.assertTrue(_is_network_error(Exception("Server disconnected")))

    def test_network_unreachable(self):
        self.assertTrue(_is_network_error(Exception("Network is unreachable")))

    def test_connection_reset(self):
        self.assertTrue(_is_network_error(Exception("Connection reset by peer")))

    def test_non_network_error(self):
        self.assertFalse(_is_network_error(Exception("Invalid JSON format")))

    def test_non_network_value_error(self):
        self.assertFalse(_is_network_error(ValueError("API调用失败: bad request")))

    def test_case_insensitive(self):
        self.assertTrue(_is_network_error(Exception("CONNECTION REFUSED")))


class TestCreateConnector(unittest.TestCase):
    """测试连接器创建"""

    def test_first_attempt_uses_dns_cache(self):
        """首次尝试应使用 DNS 缓存"""
        async def _test():
            conn = _create_connector(force_dns_refresh=False)
            self.assertIsInstance(conn, aiohttp.TCPConnector)
            self.assertTrue(conn._use_dns_cache)
            await conn.close()
        asyncio.run(_test())

    def test_retry_disables_dns_cache(self):
        """重试时应禁用 DNS 缓存"""
        async def _test():
            conn = _create_connector(force_dns_refresh=True)
            self.assertIsInstance(conn, aiohttp.TCPConnector)
            self.assertFalse(conn._use_dns_cache)
            await conn.close()
        asyncio.run(_test())

    def test_retry_forces_close(self):
        """重试时应强制关闭旧连接"""
        async def _test():
            conn = _create_connector(force_dns_refresh=True)
            self.assertTrue(conn._force_close)
            await conn.close()
        asyncio.run(_test())


class TestNetworkExceptions(unittest.TestCase):
    """测试 NETWORK_EXCEPTIONS 元组包含所有预期的异常类型"""

    def test_contains_timeout(self):
        self.assertIn(asyncio.TimeoutError, NETWORK_EXCEPTIONS)

    def test_contains_connection_error(self):
        self.assertIn(ConnectionError, NETWORK_EXCEPTIONS)

    def test_contains_os_error(self):
        self.assertIn(OSError, NETWORK_EXCEPTIONS)

    def test_contains_client_connection_error(self):
        self.assertIn(aiohttp.ClientConnectionError, NETWORK_EXCEPTIONS)

    def test_contains_server_disconnected(self):
        self.assertIn(aiohttp.ServerDisconnectedError, NETWORK_EXCEPTIONS)

    def test_contains_client_error(self):
        self.assertIn(aiohttp.ClientError, NETWORK_EXCEPTIONS)

    def test_contains_client_payload_error(self):
        self.assertIn(aiohttp.ClientPayloadError, NETWORK_EXCEPTIONS)


if __name__ == "__main__":
    unittest.main()
