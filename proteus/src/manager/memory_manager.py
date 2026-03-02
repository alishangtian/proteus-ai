"""
MemoryManager - 三层记忆管理器

三层记忆体系:
1. 短期记忆 (STM): 当前会话上下文窗口 - 由 conversation_manager 管理
2. 中期记忆 (MTM): 工具使用模式 + SOP 模式，存储于 Redis（按用户隔离）
3. 长期记忆 (LTM): 向量数据库（ChromaDB），语义检索，可选
"""

import json
import logging
import time
from typing import Optional, List

logger = logging.getLogger(__name__)

# MTM: 每个用户最多保留的工具记忆条数
TOOL_MEMORY_MAX_ITEMS = int(50)
# MTM: 每个用户最多保留的 SOP 记忆条数
SOP_MEMORY_MAX_ITEMS = int(20)


class MemoryManager:
    """三层记忆管理器

    Layer 1 (STM): 会话对话历史（由 conversation_manager 负责）
    Layer 2 (MTM): 工具记忆 + SOP 记忆，存储于 Redis
    Layer 3 (LTM): 向量数据库（ChromaDB），语义检索（可选）
    """

    def __init__(self, redis_conn, user_name: str):
        """初始化记忆管理器

        Args:
            redis_conn: Redis 连接实例
            user_name: 用户名，用于记忆隔离
        """
        self.redis_conn = redis_conn
        self.user_name = user_name or "anonymous"

    # ──────────────────────────────────────────────
    # MTM: 工具记忆（按工具名称 + 用户隔离）
    # ──────────────────────────────────────────────

    def save_tool_memory(self, tool_name: str, memory_content: str) -> bool:
        """保存工具使用记忆到 Redis MTM

        Args:
            tool_name: 工具名称
            memory_content: 从工具执行中提取的记忆内容

        Returns:
            bool: 保存是否成功
        """
        if not memory_content or not memory_content.strip():
            return False
        try:
            key = f"tool_memory:{self.user_name}:{tool_name}"
            record = json.dumps(
                {
                    "tool_name": tool_name,
                    "content": memory_content.strip(),
                    "timestamp": time.time(),
                },
                ensure_ascii=False,
            )
            self.redis_conn.rpush(key, record)
            # 限制最大条数，移除最旧的记录
            total = self.redis_conn.llen(key)
            if total > TOOL_MEMORY_MAX_ITEMS:
                self.redis_conn.ltrim(key, total - TOOL_MEMORY_MAX_ITEMS, -1)
            logger.info(f"[MemoryManager] 保存工具记忆: {tool_name} (user={self.user_name})")
            return True
        except Exception as e:
            logger.error(f"[MemoryManager] 保存工具记忆失败: {e}")
            return False

    def load_tool_memories(self, tool_name: Optional[str] = None, limit: int = 10) -> str:
        """从 Redis MTM 加载工具记忆

        Args:
            tool_name: 指定工具名称；为 None 时加载所有工具记忆
            limit: 每个工具最多加载的条数

        Returns:
            str: 格式化的工具记忆文本，供注入 system prompt 使用
        """
        try:
            if tool_name:
                keys = [f"tool_memory:{self.user_name}:{tool_name}"]
            else:
                pattern = f"tool_memory:{self.user_name}:*"
                keys = self.redis_conn.keys(pattern)

            if not keys:
                return ""

            sections = []
            for key in keys:
                records_raw = self.redis_conn.lrange(key, -limit, -1)
                if not records_raw:
                    continue
                memories = []
                for raw in records_raw:
                    try:
                        rec = json.loads(raw)
                        memories.append(rec.get("content", ""))
                    except Exception:
                        continue
                if memories:
                    # 提取工具名（key 格式为 tool_memory:{user}:{tool_name}）
                    parts = key.split(":", 2)
                    tname = parts[2] if len(parts) == 3 else key
                    sections.append(f"### 工具 `{tname}` 使用经验\n" + "\n".join(f"- {m}" for m in memories))

            if not sections:
                return ""
            return "## 工具使用记忆（MTM）\n" + "\n\n".join(sections)
        except Exception as e:
            logger.error(f"[MemoryManager] 加载工具记忆失败: {e}")
            return ""

    # ──────────────────────────────────────────────
    # MTM: SOP 记忆（按用户隔离）
    # ──────────────────────────────────────────────

    def save_sop_memory(self, problem_type: str, sop_content: str) -> bool:
        """保存 SOP 记忆到 Redis MTM

        Args:
            problem_type: 问题类型
            sop_content: 从成功解题过程中提取的 SOP 内容

        Returns:
            bool: 保存是否成功
        """
        if not sop_content or not sop_content.strip():
            return False
        try:
            key = f"sop_memory:{self.user_name}"
            record = json.dumps(
                {
                    "problem_type": problem_type,
                    "content": sop_content.strip(),
                    "timestamp": time.time(),
                },
                ensure_ascii=False,
            )
            self.redis_conn.rpush(key, record)
            total = self.redis_conn.llen(key)
            if total > SOP_MEMORY_MAX_ITEMS:
                self.redis_conn.ltrim(key, total - SOP_MEMORY_MAX_ITEMS, -1)
            logger.info(f"[MemoryManager] 保存 SOP 记忆: {problem_type} (user={self.user_name})")
            return True
        except Exception as e:
            logger.error(f"[MemoryManager] 保存 SOP 记忆失败: {e}")
            return False

    def load_sop_memories(self, limit: int = 5) -> str:
        """从 Redis MTM 加载 SOP 记忆

        Args:
            limit: 最多加载的条数

        Returns:
            str: 格式化的 SOP 记忆文本
        """
        try:
            key = f"sop_memory:{self.user_name}"
            records_raw = self.redis_conn.lrange(key, -limit, -1)
            if not records_raw:
                return ""

            memories = []
            for raw in records_raw:
                try:
                    rec = json.loads(raw)
                    ptype = rec.get("problem_type", "")
                    content = rec.get("content", "")
                    if content:
                        memories.append(f"[{ptype}] {content}")
                except Exception:
                    continue

            if not memories:
                return ""
            return "## 解题经验（SOP MTM）\n" + "\n\n".join(f"- {m}" for m in memories)
        except Exception as e:
            logger.error(f"[MemoryManager] 加载 SOP 记忆失败: {e}")
            return ""

    # ──────────────────────────────────────────────
    # LTM: 向量数据库（ChromaDB，可选）
    # ──────────────────────────────────────────────

    def save_ltm(self, content: str, metadata: Optional[dict] = None) -> bool:
        """保存内容到长期记忆（LTM）向量数据库

        Args:
            content: 要存储的内容
            metadata: 可选元数据

        Returns:
            bool: 保存是否成功（ChromaDB 不可用时静默失败）
        """
        if not content or not content.strip():
            return False
        try:
            from src.utils.chrome_vector_db import chromeVectorDB
            import uuid as _uuid

            collection_name = f"ltm_{self.user_name}"
            meta = metadata or {}
            meta.update({"user_name": self.user_name, "timestamp": str(time.time())})
            doc_id = str(_uuid.uuid4())
            chromeVectorDB.add_documents(
                collection_name=collection_name,
                documents=[content.strip()],
                metadatas=[meta],
                ids=[doc_id],
            )
            logger.info(f"[MemoryManager] 保存 LTM 成功 (user={self.user_name}, id={doc_id})")
            return True
        except Exception as e:
            logger.warning(f"[MemoryManager] 保存 LTM 失败（已跳过）: {e}")
            return False

    def query_ltm(self, query: str, n_results: int = 3) -> str:
        """查询长期记忆（LTM）向量数据库

        Args:
            query: 查询文本
            n_results: 返回结果数量

        Returns:
            str: 格式化的 LTM 记忆文本；ChromaDB 不可用时返回空字符串
        """
        if not query:
            return ""
        try:
            from src.utils.chrome_vector_db import chromeVectorDB

            collection_name = f"ltm_{self.user_name}"
            results = chromeVectorDB.query(
                collection_name=collection_name,
                query_texts=[query],
                n_results=n_results,
                where={"user_name": self.user_name},
            )
            docs = results.get("documents", [[]])[0] if results else []
            if not docs:
                return ""
            items = "\n".join(f"- {d}" for d in docs if d)
            return f"## 长期记忆（LTM）\n{items}"
        except Exception as e:
            logger.warning(f"[MemoryManager] 查询 LTM 失败（已跳过）: {e}")
            return ""

    # ──────────────────────────────────────────────
    # 聚合接口：构建完整记忆上下文
    # ──────────────────────────────────────────────

    def build_memory_context(self, query: str = "") -> str:
        """构建完整的三层记忆上下文（MTM + LTM），供注入 system prompt

        STM 部分由 conversation_manager 负责，此处不重复。

        Args:
            query: 当前用户查询，用于 LTM 语义检索

        Returns:
            str: 合并的记忆上下文文本
        """
        parts = []

        # MTM: 工具记忆
        tool_mem = self.load_tool_memories()
        if tool_mem:
            parts.append(tool_mem)

        # MTM: SOP 记忆
        sop_mem = self.load_sop_memories()
        if sop_mem:
            parts.append(sop_mem)

        # LTM: 向量检索（可选，失败时静默忽略）
        if query:
            ltm_mem = self.query_ltm(query)
            if ltm_mem:
                parts.append(ltm_mem)

        if not parts:
            return ""
        return "\n\n".join(parts)


# ──────────────────────────────────────────────
# 工具记忆提取辅助函数（异步）
# ──────────────────────────────────────────────


async def extract_and_save_tool_memory(
    memory_manager: MemoryManager,
    tool_name: str,
    tool_result: str,
    user_query: str,
    execution_status: str,
    param_types: str,
    model_name: str = "deepseek-chat",
) -> None:
    """使用 LLM 提取工具使用模式并保存到 MTM

    Args:
        memory_manager: MemoryManager 实例
        tool_name: 工具名称
        tool_result: 工具执行结果
        user_query: 用户查询
        execution_status: 执行状态（成功/失败）
        param_types: 参数类型描述
        model_name: LLM 模型名称
    """
    try:
        from src.api.llm_api import call_llm_api
        from src.agent.prompt.tool_memory_prompt import TOOL_MEMORY_ANALYSIS_PROMPT
        from string import Template

        context_info = f"工具执行结果摘要（前500字）：\n{tool_result[:500]}" if tool_result else ""
        prompt = Template(TOOL_MEMORY_ANALYSIS_PROMPT).safe_substitute(
            {
                "tool_name": tool_name,
                "execution_status": execution_status,
                "param_types": param_types,
                "user_query": user_query[:300],
                "context_info": context_info,
            }
        )
        messages = [{"role": "user", "content": prompt}]
        memory_content, _ = await call_llm_api(
            messages=messages,
            model_name=model_name,
            request_id=f"tool-mem-{tool_name}-{int(time.time())}",
            temperature=0.3,
        )
        if memory_content and memory_content.strip():
            memory_manager.save_tool_memory(tool_name, memory_content.strip())
    except Exception as e:
        logger.warning(f"[MemoryManager] 提取工具记忆失败（已跳过）: {e}")


async def extract_and_save_sop_memory(
    memory_manager: MemoryManager,
    user_query: str,
    tool_chain: str,
    final_result: str,
    resolution_status: str,
    model_name: str = "deepseek-chat",
) -> None:
    """使用 LLM 提取 SOP 并保存到 MTM

    Args:
        memory_manager: MemoryManager 实例
        user_query: 用户查询
        tool_chain: 工具调用链描述
        final_result: 最终结果
        resolution_status: 解决状态
        model_name: LLM 模型名称
    """
    try:
        from src.api.llm_api import call_llm_api
        from src.agent.prompt.sop_memory_prompt import (
            SOP_MEMORY_ANALYSIS_PROMPT,
            PROBLEM_TYPE_INFERENCE_PROMPT,
        )
        from string import Template

        # 1. 推断问题类型
        type_prompt = Template(PROBLEM_TYPE_INFERENCE_PROMPT).safe_substitute(
            {"user_query": user_query[:300], "tool_chain": tool_chain[:300]}
        )
        problem_type, _ = await call_llm_api(
            messages=[{"role": "user", "content": type_prompt}],
            model_name=model_name,
            request_id=f"sop-type-{int(time.time())}",
            temperature=0.3,
        )
        problem_type = (problem_type or "通用问题").strip()

        # 2. 提取 SOP
        sop_prompt = Template(SOP_MEMORY_ANALYSIS_PROMPT).safe_substitute(
            {
                "user_query": user_query[:300],
                "problem_type": problem_type,
                "tool_chain": tool_chain[:300],
                "final_result": final_result[:500] if final_result else "",
                "resolution_status": resolution_status,
                "context_info": "",
            }
        )
        sop_content, _ = await call_llm_api(
            messages=[{"role": "user", "content": sop_prompt}],
            model_name=model_name,
            request_id=f"sop-mem-{int(time.time())}",
            temperature=0.3,
        )
        if sop_content and sop_content.strip():
            memory_manager.save_sop_memory(problem_type, sop_content.strip())
    except Exception as e:
        logger.warning(f"[MemoryManager] 提取 SOP 记忆失败（已跳过）: {e}")
