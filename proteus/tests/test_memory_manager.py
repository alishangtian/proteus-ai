"""
三层记忆管理器单元测试
"""
import json
import sys
import time
import unittest
from unittest.mock import MagicMock, patch, call

# 添加 proteus/src 到路径，避免依赖 FastAPI 等启动依赖
sys.path.insert(0, "src")

from manager.memory_manager import MemoryManager, TOOL_MEMORY_MAX_ITEMS, SOP_MEMORY_MAX_ITEMS


def _make_redis_mock():
    """构建模拟 Redis 连接，支持 rpush/lrange/llen/ltrim/keys"""
    redis_mock = MagicMock()
    store: dict = {}

    def rpush(key, *values):
        store.setdefault(key, [])
        for v in values:
            store[key].append(v)
        return len(store[key])

    def lrange(key, start, end):
        items = store.get(key, [])
        if end == -1:
            end = len(items)
        return items[start:end]

    def llen(key):
        return len(store.get(key, []))

    def ltrim(key, start, end):
        items = store.get(key, [])
        if end == -1:
            end = len(items)
        store[key] = items[start : end + 1]

    def keys(pattern):
        prefix = pattern.rstrip("*")
        return [k for k in store.keys() if k.startswith(prefix)]

    def exists(key):
        return key in store

    redis_mock.rpush.side_effect = rpush
    redis_mock.lrange.side_effect = lrange
    redis_mock.llen.side_effect = llen
    redis_mock.ltrim.side_effect = ltrim
    redis_mock.keys.side_effect = keys
    redis_mock.exists.side_effect = exists
    return redis_mock, store


class TestMemoryManagerMTM(unittest.TestCase):
    """测试 MTM (Redis) 记忆存储和加载"""

    def setUp(self):
        self.redis_mock, self.store = _make_redis_mock()
        self.mm = MemoryManager(self.redis_mock, user_name="testuser")

    # ── 工具记忆 ──

    def test_save_tool_memory_basic(self):
        result = self.mm.save_tool_memory("serper_search", "适合搜索网络信息")
        self.assertTrue(result)
        key = "tool_memory:testuser:serper_search"
        self.assertIn(key, self.store)
        record = json.loads(self.store[key][0])
        self.assertEqual(record["tool_name"], "serper_search")
        self.assertEqual(record["content"], "适合搜索网络信息")

    def test_save_tool_memory_empty_skipped(self):
        result = self.mm.save_tool_memory("serper_search", "")
        self.assertFalse(result)
        key = "tool_memory:testuser:serper_search"
        self.assertNotIn(key, self.store)

    def test_save_tool_memory_whitespace_only_skipped(self):
        result = self.mm.save_tool_memory("serper_search", "   \n  ")
        self.assertFalse(result)

    def test_load_tool_memories_empty(self):
        result = self.mm.load_tool_memories()
        self.assertEqual(result, "")

    def test_load_tool_memories_with_data(self):
        self.mm.save_tool_memory("web_crawler", "适合抓取网页内容")
        result = self.mm.load_tool_memories(tool_name="web_crawler")
        self.assertIn("web_crawler", result)
        self.assertIn("适合抓取网页内容", result)
        self.assertIn("工具使用记忆", result)

    def test_load_all_tool_memories(self):
        self.mm.save_tool_memory("tool_a", "经验A")
        self.mm.save_tool_memory("tool_b", "经验B")
        result = self.mm.load_tool_memories()
        self.assertIn("工具使用记忆", result)
        self.assertIn("经验A", result)
        self.assertIn("经验B", result)

    def test_tool_memory_max_items_limit(self):
        """验证超过最大条数时旧记录被修剪"""
        # 添加超过上限的记录
        for i in range(TOOL_MEMORY_MAX_ITEMS + 5):
            self.mm.save_tool_memory("my_tool", f"经验{i}")
        key = "tool_memory:testuser:my_tool"
        self.assertLessEqual(len(self.store[key]), TOOL_MEMORY_MAX_ITEMS)

    # ── SOP 记忆 ──

    def test_save_sop_memory_basic(self):
        result = self.mm.save_sop_memory("信息检索类问题", "先搜索再整合")
        self.assertTrue(result)
        key = "sop_memory:testuser"
        self.assertIn(key, self.store)
        record = json.loads(self.store[key][0])
        self.assertEqual(record["problem_type"], "信息检索类问题")
        self.assertEqual(record["content"], "先搜索再整合")

    def test_save_sop_memory_empty_skipped(self):
        result = self.mm.save_sop_memory("代码问题", "")
        self.assertFalse(result)

    def test_load_sop_memories_empty(self):
        result = self.mm.load_sop_memories()
        self.assertEqual(result, "")

    def test_load_sop_memories_with_data(self):
        self.mm.save_sop_memory("代码类问题", "先定位问题再修复")
        result = self.mm.load_sop_memories()
        self.assertIn("SOP", result)
        self.assertIn("代码类问题", result)
        self.assertIn("先定位问题再修复", result)

    def test_sop_memory_max_items_limit(self):
        for i in range(SOP_MEMORY_MAX_ITEMS + 5):
            self.mm.save_sop_memory("通用问题", f"经验{i}")
        key = "sop_memory:testuser"
        self.assertLessEqual(len(self.store[key]), SOP_MEMORY_MAX_ITEMS)

    # ── 用户隔离 ──

    def test_user_isolation(self):
        mm_other = MemoryManager(self.redis_mock, user_name="otheruser")
        self.mm.save_tool_memory("search", "用户A的经验")
        mm_other.save_tool_memory("search", "用户B的经验")

        result_a = self.mm.load_tool_memories(tool_name="search")
        result_b = mm_other.load_tool_memories(tool_name="search")

        self.assertIn("用户A的经验", result_a)
        self.assertNotIn("用户B的经验", result_a)
        self.assertIn("用户B的经验", result_b)
        self.assertNotIn("用户A的经验", result_b)

    # ── build_memory_context ──

    def test_build_memory_context_empty(self):
        result = self.mm.build_memory_context(query="什么是Python")
        self.assertEqual(result, "")

    def test_build_memory_context_with_mtm(self):
        self.mm.save_tool_memory("python_execute", "用于执行Python代码")
        self.mm.save_sop_memory("代码类问题", "先分析再执行")
        result = self.mm.build_memory_context(query="执行Python代码")
        self.assertIn("工具使用记忆", result)
        self.assertIn("SOP", result)


class TestMemoryManagerLTM(unittest.TestCase):
    """测试 LTM (ChromaDB) - 静默降级行为"""

    def setUp(self):
        self.redis_mock, _ = _make_redis_mock()
        self.mm = MemoryManager(self.redis_mock, user_name="testuser")

    def test_save_ltm_graceful_degradation(self):
        """ChromaDB 不可用时 save_ltm 应静默失败（返回 False）"""
        # save_ltm with empty content always returns False without touching chromadb
        result = self.mm.save_ltm("")
        self.assertFalse(result)
        # When chromadb raises an exception, save_ltm should return False
        result_empty = self.mm.save_ltm("   ")
        self.assertFalse(result_empty)

    def test_query_ltm_graceful_degradation(self):
        """ChromaDB 不可用时 query_ltm 应返回空字符串"""
        # Empty query always returns ""
        result = self.mm.query_ltm("")
        self.assertEqual(result, "")

    def test_save_ltm_empty_content_skipped(self):
        result = self.mm.save_ltm("")
        self.assertFalse(result)

    def test_query_ltm_empty_query(self):
        result = self.mm.query_ltm("")
        self.assertEqual(result, "")


class TestPromptTemplateSubstitution(unittest.TestCase):
    """验证 prompt 模板使用 .format_map() 正确替换变量（回归测试：fix Template vs format_map 冲突）"""

    def test_tool_memory_prompt_substitution(self):
        """TOOL_MEMORY_ANALYSIS_PROMPT 使用 .format_map() 后不含原始变量名"""
        from agent.prompt.tool_memory_prompt import TOOL_MEMORY_ANALYSIS_PROMPT

        result = TOOL_MEMORY_ANALYSIS_PROMPT.format_map({
            "tool_name": "serper_search",
            "execution_status": "成功",
            "param_types": "str",
            "user_query": "search for python",
            "context_info": "result snippet",
        })
        self.assertNotIn("{tool_name}", result)
        self.assertNotIn("{execution_status}", result)
        self.assertIn("serper_search", result)
        self.assertIn("成功", result)

    def test_sop_memory_prompt_substitution(self):
        """SOP_MEMORY_ANALYSIS_PROMPT 使用 .format_map() 后不含原始变量名"""
        from agent.prompt.sop_memory_prompt import SOP_MEMORY_ANALYSIS_PROMPT

        result = SOP_MEMORY_ANALYSIS_PROMPT.format_map({
            "user_query": "how to search",
            "problem_type": "信息检索类问题",
            "tool_chain": "serper_search->web_crawler",
            "final_result": "got the answer",
            "resolution_status": "成功",
            "context_info": "",
        })
        self.assertNotIn("{user_query}", result)
        self.assertNotIn("{tool_chain}", result)
        self.assertIn("信息检索类问题", result)

    def test_problem_type_prompt_substitution(self):
        """PROBLEM_TYPE_INFERENCE_PROMPT 使用 .format_map() 后不含原始变量名"""
        from agent.prompt.sop_memory_prompt import PROBLEM_TYPE_INFERENCE_PROMPT

        result = PROBLEM_TYPE_INFERENCE_PROMPT.format_map({
            "user_query": "what is python",
            "tool_chain": "serper_search",
        })
        self.assertNotIn("{user_query}", result)
        self.assertNotIn("{tool_chain}", result)
        self.assertIn("what is python", result)


if __name__ == "__main__":
    unittest.main()
