"""
_compress_text 压缩策略单元测试

验证三档压缩策略：
- 长度 <= 1000：原样返回
- 长度 1001~5000：调用 LLM 总结
- 长度 > 5000：先间隔提取 30% 行，再调用 LLM 总结
"""

import os
import sys
import unittest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock

sys.path.insert(0, "src")

os.environ.setdefault("REDIS_HOST", "localhost")
os.environ.setdefault("REDIS_PORT", "6379")
os.environ.setdefault("REDIS_PASSWORD", "")

import src.utils.redis_cache as _redis_cache_module

_boot_redis_mock = MagicMock()
_original_get_redis = _redis_cache_module.get_redis_connection
_redis_cache_module.get_redis_connection = lambda: _boot_redis_mock

from agent.chat_agent import ChatAgent, COMPRESS_LLM_LOWER, COMPRESS_LLM_UPPER, COMPRESS_LLM_TARGET

_redis_cache_module.get_redis_connection = _original_get_redis


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_agent():
    redis_mock = MagicMock()
    redis_mock.set = MagicMock()
    redis_mock.get = MagicMock(return_value=None)
    redis_mock.exists = MagicMock(return_value=0)
    with patch("agent.chat_agent.get_redis_connection", return_value=redis_mock):
        return ChatAgent(stream_manager=None, model_name="test-model", enable_tools=False)


class TestCompressTextShort(unittest.TestCase):
    """长度 <= COMPRESS_LLM_LOWER 的文本不压缩"""

    def setUp(self):
        self.agent = _make_agent()

    @patch("agent.chat_agent.get_redis_connection")
    def test_short_text_returned_unchanged(self, _mock_redis):
        text = "x" * COMPRESS_LLM_LOWER
        result = _run(self.agent._compress_text("chat-1", text))
        self.assertEqual(result, text)

    @patch("agent.chat_agent.get_redis_connection")
    def test_empty_text_returned_unchanged(self, _mock_redis):
        result = _run(self.agent._compress_text("chat-1", ""))
        self.assertEqual(result, "")


class TestCompressTextMedium(unittest.TestCase):
    """长度在 (COMPRESS_LLM_LOWER, COMPRESS_LLM_UPPER] 时调用 LLM"""

    def setUp(self):
        self.agent = _make_agent()

    @patch("agent.chat_agent.call_llm_api", new_callable=AsyncMock)
    @patch("agent.chat_agent.get_redis_connection")
    def test_medium_text_calls_llm(self, _mock_redis, mock_llm):
        mock_llm.return_value = ("LLM摘要结果", {})
        text = "x" * (COMPRESS_LLM_LOWER + 1)
        result = _run(self.agent._compress_text("chat-1", text))
        mock_llm.assert_called_once()
        self.assertEqual(result, "LLM摘要结果")

    @patch("agent.chat_agent.call_llm_api", new_callable=AsyncMock)
    @patch("agent.chat_agent.get_redis_connection")
    def test_medium_text_at_upper_boundary_calls_llm(self, _mock_redis, mock_llm):
        mock_llm.return_value = ("摘要", {})
        text = "y" * COMPRESS_LLM_UPPER
        result = _run(self.agent._compress_text("chat-1", text))
        mock_llm.assert_called_once()

    @patch("agent.chat_agent.call_llm_api", new_callable=AsyncMock)
    @patch("agent.chat_agent.get_redis_connection")
    def test_llm_failure_returns_truncated(self, _mock_redis, mock_llm):
        mock_llm.side_effect = Exception("LLM error")
        text = "z" * (COMPRESS_LLM_LOWER + 100)
        result = _run(self.agent._compress_text("chat-1", text))
        self.assertEqual(result, text[:COMPRESS_LLM_TARGET])


class TestCompressTextLong(unittest.TestCase):
    """长度 > COMPRESS_LLM_UPPER 时先间隔提取再 LLM"""

    def setUp(self):
        self.agent = _make_agent()

    @patch("agent.chat_agent.call_llm_api", new_callable=AsyncMock)
    @patch("agent.chat_agent.get_redis_connection")
    def test_long_text_interval_sample_then_llm(self, _mock_redis, mock_llm):
        mock_llm.return_value = ("长文摘要", {})
        # 构造 200 行文本，每行 30 个字符（总字符 200*31 ≈ 6200 > 5000）
        lines = [f"line-{i:04d}-{'x'*25}" for i in range(200)]
        text = "\n".join(lines)
        self.assertGreater(len(text), COMPRESS_LLM_UPPER)

        result = _run(self.agent._compress_text("chat-1", text))
        mock_llm.assert_called_once()
        # 验证传给 LLM 的 prompt 中行数约为 30%（~60 行）
        call_kwargs = mock_llm.call_args
        prompt_msg = call_kwargs[1]["messages"][0]["content"]
        # 抽取后的行数应小于原始行数
        sampled_lines = prompt_msg.split("原始内容：\n", 1)[1].splitlines()
        self.assertLess(len(sampled_lines), 200)
        # 约 30%：允许 ±5 行误差
        self.assertAlmostEqual(len(sampled_lines), 200 * 0.3, delta=10)
        self.assertEqual(result, "长文摘要")

    @patch("agent.chat_agent.call_llm_api", new_callable=AsyncMock)
    @patch("agent.chat_agent.get_redis_connection")
    def test_long_text_single_line_handled(self, _mock_redis, mock_llm):
        """单行超长文本：interval sampling 仍正常（1行取1行=100%）"""
        mock_llm.return_value = ("摘要", {})
        text = "a" * (COMPRESS_LLM_UPPER + 1)  # 单行，无换行
        result = _run(self.agent._compress_text("chat-1", text))
        mock_llm.assert_called_once()
        self.assertEqual(result, "摘要")


class TestCompressMessages(unittest.TestCase):
    """_compress_messages 工具消息压缩集成测试"""

    def setUp(self):
        self.agent = _make_agent()

    def _patch_ctx(self):
        return patch.object(
            self.agent, "_get_context_window_for_model", return_value=100
        )

    @patch("agent.chat_agent.count_tokens", return_value=200)
    @patch("agent.chat_agent.call_llm_api", new_callable=AsyncMock)
    @patch("agent.chat_agent.get_redis_connection")
    def test_tool_message_compressed(self, _mock_redis, mock_llm, mock_tokens):
        mock_llm.return_value = ("工具摘要", {})
        content = "t" * (COMPRESS_LLM_LOWER + 1)
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "tool", "tool_call_id": "id1", "name": "search", "content": content},
        ]
        with self._patch_ctx():
            with patch.object(
                self.agent, "_validate_and_fix_message_chain", side_effect=lambda m, _: m
            ):
                result = _run(self.agent._compress_messages("chat-1", messages, must_compress=True))

        tool_msgs = [m for m in result if m.get("role") == "tool"]
        self.assertEqual(len(tool_msgs), 1)
        self.assertEqual(tool_msgs[0]["content"], "工具摘要")

    @patch("agent.chat_agent.count_tokens", return_value=200)
    @patch("agent.chat_agent.call_llm_api", new_callable=AsyncMock)
    @patch("agent.chat_agent.get_redis_connection")
    def test_short_tool_message_not_compressed(self, _mock_redis, mock_llm, mock_tokens):
        content = "short"
        messages = [
            {"role": "tool", "tool_call_id": "id1", "name": "x", "content": content},
        ]
        with self._patch_ctx():
            with patch.object(
                self.agent, "_validate_and_fix_message_chain", side_effect=lambda m, _: m
            ):
                result = _run(self.agent._compress_messages("chat-1", messages, must_compress=True))

        self.assertEqual(result[0]["content"], content)
        mock_llm.assert_not_called()

    @patch("agent.chat_agent.count_tokens", return_value=200)
    @patch("agent.chat_agent.call_llm_api", new_callable=AsyncMock)
    @patch("agent.chat_agent.get_redis_connection")
    def test_tool_calls_args_compressed(self, _mock_redis, mock_llm, mock_tokens):
        import json
        mock_llm.return_value = ("参数摘要", {})
        long_val = "v" * (COMPRESS_LLM_LOWER + 1)
        args = json.dumps({"query": long_val})
        messages = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "tc1",
                        "type": "function",
                        "function": {"name": "search", "arguments": args},
                    }
                ],
            }
        ]
        with self._patch_ctx():
            with patch.object(
                self.agent, "_validate_and_fix_message_chain", side_effect=lambda m, _: m
            ):
                result = _run(self.agent._compress_messages("chat-1", messages, must_compress=True))

        new_args = json.loads(result[0]["tool_calls"][0]["function"]["arguments"])
        self.assertEqual(new_args["query"], "参数摘要")

    @patch("agent.chat_agent.count_tokens", return_value=200)
    @patch("agent.chat_agent.call_llm_api", new_callable=AsyncMock)
    @patch("agent.chat_agent.get_redis_connection")
    def test_tool_calls_short_args_not_compressed(self, _mock_redis, mock_llm, mock_tokens):
        import json
        args = json.dumps({"query": "short"})
        messages = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "tc1",
                        "type": "function",
                        "function": {"name": "search", "arguments": args},
                    }
                ],
            }
        ]
        with self._patch_ctx():
            with patch.object(
                self.agent, "_validate_and_fix_message_chain", side_effect=lambda m, _: m
            ):
                result = _run(self.agent._compress_messages("chat-1", messages, must_compress=True))

        self.assertEqual(result[0]["tool_calls"][0]["function"]["arguments"], args)
        mock_llm.assert_not_called()

    @patch("agent.chat_agent.count_tokens", return_value=50)
    @patch("agent.chat_agent.get_redis_connection")
    def test_no_compression_when_within_window(self, _mock_redis, mock_tokens):
        messages = [{"role": "user", "content": "hello"}]
        with patch.object(
            self.agent, "_get_context_window_for_model", return_value=100
        ):
            result = _run(self.agent._compress_messages("chat-1", messages))
        self.assertEqual(result, messages)


if __name__ == "__main__":
    unittest.main()
