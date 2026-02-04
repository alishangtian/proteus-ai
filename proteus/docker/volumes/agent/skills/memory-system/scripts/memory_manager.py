import json

"""
统一记忆管理器 - 为AI智能体提供三层记忆管理的统一入口点
版本: 2.1 (SQLite向量化存储版)

特点:
1. 单一切入口，使用简单
2. SQLite统一存储结构化数据和向量数据
3. 自动降级，确保可用性
4. 向后兼容，平滑升级
"""

import os
import shutil
import logging
import time
import uuid
from collections import deque
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class MemoryManager:
    """统一记忆管理器 - 主入口类"""

    def __init__(self, config_path=None, storage_base="/app/data/memory"):
        """
        初始化记忆管理器

        Args:
            config_path: 配置文件路径
            storage_base: 存储根目录
        """
        self.storage_base = storage_base
        self.short_term_buffer = deque(maxlen=20)

        # 创建目录
        os.makedirs(os.path.join(storage_base, "medium"), exist_ok=True)

        # 检查系统是否已初始化
        self._check_initialization()

        os.makedirs(os.path.join(storage_base, "long"), exist_ok=True)

        # 加载配置
        self.config = self._load_config(config_path)

        # 初始化组件
        self._init_components()

        # 初始化AOF日志
        self.aof_log_path = os.path.join(self.storage_base, "logs", "memory_aof.log")
        self.aof_max_size = 100 * 1024 * 1024  # 100MB
        self._init_aof_log()

        logger.info(f"记忆管理器初始化完成")

    def _load_config(self, config_path):
        """加载配置"""
        # 如果提供了配置路径，尝试加载
        if config_path and os.path.exists(config_path):
            try:
                import yaml

                with open(config_path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f)
            except Exception as e:
                logger.warning(f"加载配置文件失败: {e}")

        # 如果没有提供配置路径，尝试从默认位置加载
        default_paths = [
            os.path.join(self.storage_base, "config.yaml"),
            "/app/data/memory/config.yaml",
            os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "assets/templates/config.yaml",
            ),
        ]

        for config_path in default_paths:
            if os.path.exists(config_path):
                try:
                    import yaml

                    with open(config_path, "r", encoding="utf-8") as f:
                        logger.info(f"从默认位置加载配置: {config_path}")
                        return yaml.safe_load(f)
                except Exception as e:
                    logger.warning(f"加载配置文件失败 ({config_path}): {e}")

        logger.warning("未找到配置文件，使用空配置")
        return {}

    def _init_components(self):
        """初始化组件"""
        self.llm_client = None
        self.embedding_client = None
        self.sqlite_store = None
        self.chroma_client = None

        # 读取配置
        self.use_embedding = (
            self.config.get("memory", {})
            .get("long_term", {})
            .get("use_embedding", True)
        )
        self.use_chroma = (
            self.config.get("memory", {}).get("long_term", {}).get("use_chroma", True)
        )
        self.embedding_threshold = (
            self.config.get("memory", {})
            .get("long_term", {})
            .get("embedding_threshold", 0.5)
        )

        # 尝试初始化LLM客户端
        try:
            from llm_client import LLMClient

            llm_config = self.config.get("llm", {})
            self.llm_client = LLMClient(llm_config)
            logger.info(
                f"LLM客户端: {'已启用' if self.llm_client.enabled else '未启用'}"
            )
        except ImportError as e:
            logger.debug(f"LLM客户端不可用: {e}")

        # 尝试初始化嵌入客户端
        try:
            from embedding_client import EmbeddingClient

            embedding_config = self.config.get("embedding", {})
            self.embedding_client = EmbeddingClient(embedding_config)
            logger.info(
                f"嵌入客户端: {'已启用' if self.embedding_client.enabled else '未启用'}"
            )
        except ImportError as e:
            logger.debug(f"嵌入客户端不可用: {e}")

        # 初始化SQLite存储
        try:
            from sqlite_store import SQLiteStore

            db_path = (
                self.config.get("memory", {})
                .get("long_term", {})
                .get(
                    "database_path",
                    os.path.join(self.storage_base, "long", "memory.db"),
                )
            )
            sqlite_config = {"database_path": db_path}
            self.sqlite_store = SQLiteStore(sqlite_config)
            logger.info(f"SQLite存储初始化完成: {db_path}")
        except ImportError as e:
            logger.debug(f"SQLite存储不可用: {e}")

        # 初始化Chroma客户端（如果启用）
        if self.use_chroma:
            try:
                from chroma_client import ChromaClient

                chroma_config = self.config.get("chroma", {})
                self.chroma_client = ChromaClient(chroma_config, self.embedding_client)
                # 初始化连接
                if self.chroma_client.initialize():
                    logger.info(
                        f"Chroma客户端初始化成功，集合: {self.chroma_client.collection_name}"
                    )
                else:
                    logger.warning("Chroma客户端初始化失败")
                    self.chroma_client = None
            except ImportError as e:
                logger.debug(f"Chroma客户端不可用: {e}")
                self.chroma_client = None
            except Exception as e:
                logger.warning(f"Chroma客户端初始化异常: {e}")
                self.chroma_client = None

    def store(
        self, content, memory_type="auto", importance=0.5, tags=None, metadata=None
    ):
        """
        存储记忆

        Args:
            content: 记忆内容
            memory_type: 记忆类型 (auto|short_term|medium_term|long_term)
            importance: 重要性评分 (0.0-1.0)
            tags: 标签列表
            metadata: 元数据

        Returns:
            str: 记忆ID
        """
        # 自动判断记忆类型
        if memory_type == "auto":
            if importance >= 0.7:
                memory_type = "long_term"
            elif importance >= 0.3:
                memory_type = "medium_term"
            else:
                memory_type = "short_term"

        # 生成记忆ID
        memory_id = f"{memory_type[0]}tm_{uuid.uuid4().hex[:8]}"

        # 存储到相应层
        if memory_type == "short_term":
            self._store_short_term(memory_id, content, importance, tags, metadata)

        elif memory_type == "medium_term":
            self._store_medium_term(memory_id, content, importance, tags, metadata)

        elif memory_type == "long_term":
        self._store_long_term(memory_id, content, importance, tags, metadata)
        logger.debug(f"存储记忆: id={memory_id}, type={memory_type}")

        # 记录到AOF日志
        try:
            log_data = {
                "content": content,
                "memory_type": memory_type,
                "importance": importance,
                "tags": tags or [],
                "metadata": metadata or {},
            }
            self._log_to_aof("STORE", memory_id, log_data)
            logger.debug(f"存储记忆并记录AOF日志: {memory_id}")
        except Exception as e:
            logger.warning(f"AOF日志记录失败: {e}")
        return memory_id

    def retrieve(self, query=None, memory_types=None, limit=10, use_semantic=True):
        """
        检索记忆

        Args:
            query: 搜索查询
            memory_types: 记忆类型列表
            limit: 返回数量
            use_semantic: 是否使用语义搜索

        Returns:
            List[Dict]: 记忆列表
        """
        if memory_types is None:
            memory_types = ["short_term", "medium_term", "long_term"]

        results = []

        # 分层检索
        if "short_term" in memory_types:
            results.extend(self._retrieve_short_term(query, limit))

        if "medium_term" in memory_types:
            results.extend(self._retrieve_medium_term(query, limit))

        if "long_term" in memory_types:
            results.extend(self._retrieve_long_term(query, limit, use_semantic))

        # 去重和排序
        return self._deduplicate_and_sort(results, limit)

    def get_current_context(self, window_size=10):
        """获取当前上下文"""
        return list(self.short_term_buffer)[-window_size:]

    def get_stats(self):
        """获取统计信息"""
        short_term_count = len(self.short_term_buffer)
        medium_term_count = self._count_medium_term()
        long_term_count = 0
        embedding_count = 0

        if self.sqlite_store:
            long_term_count = self.sqlite_store.count("long_term")
            stats = self.sqlite_store.get_stats()
            embedding_count = stats.get("with_embedding", 0)

        return {
            "short_term": short_term_count,
            "medium_term": medium_term_count,
            "long_term": long_term_count,
            "with_embedding": embedding_count,
            "total": short_term_count + medium_term_count + long_term_count,
        }

    # ==================== 存储实现 ====================

    def _store_short_term(self, memory_id, content, importance, tags, metadata):
        """存储短期记忆"""
        self.short_term_buffer.append(
            {
                "id": memory_id,
                "content": content,
                "importance": importance,
                "tags": tags or [],
                "metadata": metadata or {},
                "timestamp": time.time(),
                "memory_type": "short_term",
            }
        )

    def _store_medium_term(self, memory_id, content, importance, tags, metadata):
        """存储中期记忆"""
        date_str = datetime.now().strftime("%Y-%m-%d")
        filepath = os.path.join(self.storage_base, "medium", f"{date_str}.jsonl")

        memory_item = {
            "id": memory_id,
            "content": content,
            "importance": importance,
            "tags": tags or [],
            "metadata": metadata or {},
            "created_at": time.time(),
            "memory_type": "medium_term",
        }

        with open(filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(memory_item, ensure_ascii=False) + "\n")

    def _store_long_term(self, memory_id, content, importance, tags, metadata):
        """存储长期记忆"""
        # 优先使用SQLite存储结构化数据
        if self.sqlite_store:
            import json

            try:
                # 检查是否需要生成嵌入向量
                embedding = None
                embedding_model = None
                embedding_provider = None

                if (
                    self.use_embedding
                    and self.embedding_client
                    and self.embedding_client.enabled
                    and importance >= self.embedding_threshold
                ):
                    try:
                        # 生成嵌入向量
                        embedding_result = self.embedding_client.get_embedding(content)
                        embedding = embedding_result.embedding
                        embedding_model = embedding_result.model
                        embedding_provider = embedding_result.provider
                        logger.debug(
                            f"为记忆生成嵌入向量: {memory_id}, 模型: {embedding_model}"
                        )
                    except Exception as e:
                        logger.warning(f"生成嵌入向量失败: {e}")

                # 存储结构化数据到SQLite
                success = self.sqlite_store.store_memory(
                    memory_id=memory_id,
                    content=content,
                    importance=importance,
                    memory_type="long_term",
                    tags=tags,
                    metadata=metadata,
                )

                # 如果有嵌入向量，存储到向量数据库
                if success and embedding:
                    # 优先存储到Chroma
                    if self.use_chroma and self.chroma_client:
                        try:
                            # 存储到Chroma
                            self.chroma_client.add_embeddings(
                                vectors=[embedding],
                                ids=[memory_id],
                                metadatas=[
                                    {
                                        "content": content,
                                        "importance": importance,
                                        "memory_type": "long_term",
                                        "tags": json.dumps(tags) if tags else "",
                                        "embedding_model": embedding_model,
                                        "embedding_provider": embedding_provider,
                                    }
                                ],
                                documents=[content],
                            )
                            logger.debug(f"嵌入向量已存储到Chroma: {memory_id}")
                        except Exception as e:
                            logger.warning(f"Chroma存储失败: {e}")
                            # 降级到SQLite存储嵌入向量
                            if self.sqlite_store:
                                try:
                                    self.sqlite_store.add_embedding(
                                        memory_id=memory_id,
                                        embedding=embedding,
                                        embedding_model=embedding_model,
                                        embedding_provider=embedding_provider,
                                    )
                                    logger.debug(
                                        f"嵌入向量降级存储到SQLite: {memory_id}"
                                    )
                                except Exception as e2:
                                    logger.warning(f"SQLite嵌入向量存储失败: {e2}")
                    else:
                        # Chroma不可用，存储到SQLite
                        try:
                            self.sqlite_store.add_embedding(
                                memory_id=memory_id,
                                embedding=embedding,
                                embedding_model=embedding_model,
                                embedding_provider=embedding_provider,
                            )
                            logger.debug(f"嵌入向量存储到SQLite: {memory_id}")
                        except Exception as e:
                            logger.warning(f"SQLite嵌入向量存储失败: {e}")

                if success:
                    return
            except Exception as e:
                logger.warning(f"SQLite存储失败: {e}")

        # 降级到JSON
        self._store_long_term_json(memory_id, content, importance, tags, metadata)

    def _store_long_term_json(self, memory_id, content, importance, tags, metadata):
        """降级存储到JSON文件"""
        filepath = os.path.join(self.storage_base, "long", "memories.json")

        memory_item = {
            "id": memory_id,
            "content": content,
            "importance": importance,
            "tags": tags or [],
            "metadata": metadata or {},
            "created_at": datetime.now().isoformat(),
            "memory_type": "long_term",
        }

        try:
            memories = []
            if os.path.exists(filepath):
                with open(filepath, "r", encoding="utf-8") as f:
                    try:
                        memories = json.load(f)
                    except:
                        memories = []

            memories.append(memory_item)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(memories, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"JSON存储失败: {e}")

    # ==================== 检索实现 ====================

    def _retrieve_short_term(self, query, limit):
        """检索短期记忆"""
        results = []
        for memory in list(self.short_term_buffer)[-limit * 2 :]:
            if not query or query.lower() in memory.get("content", "").lower():
                memory["relevance"] = 0.8
                memory["search_type"] = "keyword"
                results.append(memory)
        return results[:limit]

    def _retrieve_medium_term(self, query, limit):
        """检索中期记忆"""
        results = []
        for i in range(3):  # 最近3天
            date = datetime.now() - timedelta(days=i)
            filepath = os.path.join(
                self.storage_base, "medium", f"{date.strftime('%Y-%m-%d')}.jsonl"
            )

            if not os.path.exists(filepath):
                continue

            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        memory = json.loads(line.strip())
                        if (
                            not query
                            or query.lower() in memory.get("content", "").lower()
                        ):
                            memory["relevance"] = 0.7
                            memory["search_type"] = "keyword"
                            results.append(memory)
                    except:
                        continue

        return sorted(results, key=lambda x: x.get("importance", 0), reverse=True)[
            :limit
        ]

    def _retrieve_long_term(self, query, limit, use_semantic):
        """检索长期记忆"""
        results = []

        if not query:
            # 无查询时返回最近记忆
            if self.sqlite_store:
                results.extend(self.sqlite_store.get_recent_memories(limit))
            return results

        # 关键词搜索
        if self.sqlite_store:
            keyword_results = self.sqlite_store.search_memories(
                query=query, memory_types=["long_term"], limit=limit
            )
            for result in keyword_results:
                result["relevance"] = 0.6
                result["search_type"] = "keyword"
            results.extend(keyword_results)

        # 语义搜索
        if use_semantic and self.embedding_client and self.embedding_client.enabled:
            semantic_results = self._semantic_search(query, limit)
            results.extend(semantic_results)

        return results

    def _semantic_search(self, query, limit):
        """语义搜索 - 优先使用Chroma向量存储，降级到SQLite"""
        if not self.embedding_client:
            return []

        try:
            # 生成查询嵌入
            embedding_result = self.embedding_client.get_embedding(query)
            query_embedding = embedding_result.embedding

            # 优先使用Chroma进行向量搜索
            if self.use_chroma and self.chroma_client:
                try:
                    # 使用Chroma搜索
                    chroma_results = self.chroma_client.search(
                        query_vector=query_embedding, n_results=limit
                    )

                    # 从Chroma结果中获取记忆ID
                    memory_ids = []
                    if chroma_results and "ids" in chroma_results:
                        memory_ids = chroma_results["ids"][0]  # 第一组结果

                    # 从SQLite获取完整的记忆数据
                    semantic_results = []
                    for memory_id in memory_ids:
                        if self.sqlite_store:
                            memory = self.sqlite_store.get_memory(memory_id)
                            if memory:
                                memory["relevance"] = 0.9
                                memory["search_type"] = "semantic_chroma"
                                semantic_results.append(memory)

                    # 如果从Chroma获取到结果，直接返回
                    if semantic_results:
                        return semantic_results
                except Exception as e:
                    logger.warning(f"Chroma语义搜索失败: {e}")
                    # 降级到SQLite搜索

            # Chroma不可用或失败，使用SQLite向量搜索
            if self.sqlite_store:
                semantic_results = self.sqlite_store.search_by_similarity(
                    query_embedding=query_embedding,
                    memory_types=["long_term"],
                    limit=limit,
                )

                for result in semantic_results:
                    result["relevance"] = 0.8
                    result["search_type"] = "semantic_sqlite"

                return semantic_results
            else:
                return []

        except Exception as e:
            logger.warning(f"语义搜索失败: {e}")
            return []

    def _deduplicate_and_sort(self, results, limit):
        """去重和排序"""
        seen_ids = set()
        deduplicated = []

        for result in results:
            memory_id = result.get("id")
            if memory_id and memory_id not in seen_ids:
                seen_ids.add(memory_id)
                deduplicated.append(result)

        # 按相关性和重要性排序
        return sorted(
            deduplicated,
            key=lambda x: (x.get("relevance", 0), x.get("importance", 0)),
            reverse=True,
        )[:limit]

    # ==================== 统计方法 ====================

    def _count_medium_term(self):
        """计算中期记忆数量"""
        count = 0
        medium_dir = os.path.join(self.storage_base, "medium")

        if os.path.exists(medium_dir):
            for filename in os.listdir(medium_dir):
                if filename.endswith(".jsonl"):
                    filepath = os.path.join(medium_dir, filename)
                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            count += sum(1 for line in f if line.strip())
                    except:
                        pass

        return count

    def _check_initialization(self):
        """检查记忆系统是否已正确初始化"""
        init_flag = os.path.join(self.storage_base, ".initialized")

        if not os.path.exists(init_flag):
            logger.warning(
                f"记忆系统未初始化！请先运行初始化脚本:\n"
                f"  python /app/.proteus/skills/memory-system/scripts/init_memory_system.py"
            )
            logger.warning(f"初始化标志文件不存在: {init_flag}")
            # 不抛出异常，允许只读操作
        else:
            logger.debug(f"记忆系统已初始化: {init_flag}")

    def _init_aof_log(self):
        """初始化AOF日志文件"""
        try:
            log_dir = os.path.dirname(self.aof_log_path)
            os.makedirs(log_dir, exist_ok=True)

            # 检查日志文件大小，如果超过限制则轮转
            if os.path.exists(self.aof_log_path):
                size = os.path.getsize(self.aof_log_path)
                if size > self.aof_max_size:
                    self._rotate_aof_log()

            logger.debug(f"AOF日志初始化完成: {self.aof_log_path}")
        except Exception as e:
            logger.warning(f"AOF日志初始化失败: {e}")

    def _rotate_aof_log(self):
        """轮转AOF日志文件"""
        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            rotated_path = f"{self.aof_log_path}.{timestamp}.bak"
            shutil.move(self.aof_log_path, rotated_path)
            logger.info(f"AOF日志轮转: {self.aof_log_path} -> {rotated_path}")
        except Exception as e:
            logger.warning(f"AOF日志轮转失败: {e}")

    def _log_to_aof(self, operation, memory_id, data):
        """记录操作到AOF日志"""
        try:
            timestamp = datetime.now().isoformat()
            log_entry = {
                "op": operation,
                "id": memory_id,
                "timestamp": timestamp,
                "data": data,
            }

            # 将日志条目转换为JSON字符串
            log_line = json.dumps(log_entry, ensure_ascii=False)

            # 追加到日志文件
            with open(self.aof_log_path, "a", encoding="utf-8") as f:
                f.write(log_line + "\n")

            logger.debug(f"AOF日志记录: {operation} {memory_id}")
        except Exception as e:
            logger.warning(f"AOF日志记录失败: {e}")

    def close(self):
        """关闭资源"""
        if self.sqlite_store:
            self.sqlite_store.close()
        logger.info("记忆管理器资源已关闭")


# ==================== 使用示例 ====================

if __name__ == "__main__":
    # 示例使用
    mm = MemoryManager()

    print("=== 记忆管理器示例 ===")

    # 存储记忆
    memory_id = mm.store(
        content="用户喜欢喝黑咖啡", importance=0.8, tags=["饮食", "偏好"]
    )
    print(f"存储记忆: {memory_id}")

    # 检索记忆
    memories = mm.retrieve(query="咖啡")
    print(f"检索到 {len(memories)} 条记忆")

    # 获取统计
    stats = mm.get_stats()
    print(f"统计: {stats}")

    # 清理
    mm.close()
    print("示例完成")
