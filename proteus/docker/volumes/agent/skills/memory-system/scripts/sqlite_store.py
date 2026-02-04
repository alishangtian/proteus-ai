"""
SQLite结构化存储 - 统一架构的核心存储组件
"""

import os
import json
import sqlite3
import hashlib
import logging
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class SQLiteStore:
    """SQLite结构化存储 - 统一架构的核心存储组件"""

    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化SQLite存储

        Args:
            config: 配置字典
        """
        self.config = config or {}
        self.db_path = self.config.get("database_path", "/app/data/memory/long/memory.db")
        self.conn = None
        self._init_db()

        logger.info(f"SQLite存储初始化完成: {self.db_path}")

    def _init_db(self):
        """初始化数据库表结构"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row

        cursor = self.conn.cursor()

        # 创建记忆表 - 使用单行SQL语句避免缩进问题
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS memories ("
            "id TEXT PRIMARY KEY, "
            "content TEXT NOT NULL, "
            "content_hash TEXT, "
            "importance REAL DEFAULT 0.5, "
            "memory_type TEXT DEFAULT 'long_term', "
            "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
            "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
            "last_accessed TIMESTAMP, "
            "access_count INTEGER DEFAULT 0, "
            "metadata TEXT, "
            "tags TEXT, "
            "embedding TEXT, "           # 向量嵌入 (JSON格式)
            "embedding_model TEXT, "     # 嵌入模型名称
            "embedding_provider TEXT, "  # 嵌入提供商
            "embedding_generated_at TIMESTAMP, "
            "CHECK (importance >= 0 AND importance <= 1)"
            ")"
        )

        # 创建索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_memories_created_at ON memories(created_at DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_memories_memory_type ON memories(memory_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_memories_embedding ON memories(embedding) WHERE embedding IS NOT NULL")

        self.conn.commit()
        logger.debug("数据库表结构初始化完成")

    def store(self, memory_id: str, content: str, importance: float = 0.5,
              memory_type: str = "long_term", tags: List[str] = None,
              metadata: Dict = None, embedding: List[float] = None,
              embedding_model: str = None, embedding_provider: str = None) -> bool:
        """
        存储记忆

        Args:
            memory_id: 记忆ID
            content: 记忆内容
            importance: 重要性评分
            memory_type: 记忆类型
            tags: 标签列表
            metadata: 元数据
            embedding: 嵌入向量
            embedding_model: 嵌入模型名称
            embedding_provider: 嵌入提供商

        Returns:
            bool: 是否成功
        """
        try:
            content_hash = hashlib.md5(content.encode("utf-8")).hexdigest()

            cursor = self.conn.cursor()

            # 检查是否已存在
            cursor.execute(
                "SELECT id FROM memories WHERE content_hash = ?",
                (content_hash,)
            )
            if cursor.fetchone():
                logger.debug("记忆内容已存在，跳过存储")
                return False

            # 存储记忆
            metadata_json = json.dumps(metadata) if metadata else None
            tags_json = json.dumps(tags) if tags else None
            embedding_json = json.dumps(embedding) if embedding else None

            # 如果有嵌入向量，设置生成时间
            embedding_generated_at = "CURRENT_TIMESTAMP" if embedding else None

            cursor.execute(
                "INSERT INTO memories "
                "(id, content, content_hash, importance, memory_type, "
                "metadata, tags, embedding, embedding_model, embedding_provider, "
                "embedding_generated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (memory_id, content, content_hash, importance, memory_type,
                 metadata_json, tags_json, embedding_json, embedding_model,
                 embedding_provider, embedding_generated_at)
            )

            self.conn.commit()
            logger.debug(f"记忆存储成功: {memory_id}")
            return True

        except Exception as e:
            logger.error(f"存储记忆失败: {e}")
            return False

    def add_embedding(self, memory_id: str, embedding: List[float], 
                     embedding_model: str = None, embedding_provider: str = None) -> bool:
        """
        为现有记忆添加嵌入向量

        Args:
            memory_id: 记忆ID
            embedding: 嵌入向量
            embedding_model: 嵌入模型名称
            embedding_provider: 嵌入提供商

        Returns:
            bool: 是否成功
        """
        try:
            embedding_json = json.dumps(embedding) if embedding else None

            cursor = self.conn.cursor()
            cursor.execute(
                "UPDATE memories "
                "SET embedding = ?, embedding_model = ?, embedding_provider = ?, "
                "embedding_generated_at = CURRENT_TIMESTAMP "
                "WHERE id = ?",
                (embedding_json, embedding_model, embedding_provider, memory_id)
            )

            self.conn.commit()

            if cursor.rowcount > 0:
                logger.debug(f"嵌入向量添加成功: {memory_id}")
                return True
            else:
                logger.warning(f"记忆不存在: {memory_id}")
                return False

        except Exception as e:
            logger.error(f"添加嵌入向量失败: {e}")
            return False

    def get(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """
        获取记忆

        Args:
            memory_id: 记忆ID

        Returns:
            Optional[Dict]: 记忆信息
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM memories WHERE id = ?", (memory_id,))

            row = cursor.fetchone()
            if row:
                memory = dict(row)

                # 解析元数据和标签
                if memory["metadata"]:
                    try:
                        memory["metadata"] = json.loads(memory["metadata"])
                    except:
                        memory["metadata"] = {}
                else:
                    memory["metadata"] = {}

                if memory["tags"]:
                    try:
                        memory["tags"] = json.loads(memory["tags"])
                    except:
                        memory["tags"] = []
                else:
                    memory["tags"] = []

                # 解析嵌入向量
                if memory["embedding"]:
                    try:
                        memory["embedding"] = json.loads(memory["embedding"])
                    except:
                        memory["embedding"] = None

                # 更新访问信息
                cursor.execute(
                    "UPDATE memories SET last_accessed = CURRENT_TIMESTAMP, access_count = access_count + 1 WHERE id = ?",
                    (memory_id,)
                )

                self.conn.commit()
                return memory
            return None

        except Exception as e:
            logger.error(f"获取记忆失败: {e}")
            return None

    def search(self, query: str = None, memory_types: List[str] = None,
               min_importance: float = 0, limit: int = 10) -> List[Dict[str, Any]]:
        """
        搜索记忆（关键词搜索）

        Args:
            query: 查询关键词
            memory_types: 记忆类型过滤
            min_importance: 最小重要性
            limit: 返回数量限制

        Returns:
            List[Dict]: 记忆列表
        """
        try:
            cursor = self.conn.cursor()

            # 构建查询条件
            conditions = ["importance >= ?"]
            params = [min_importance]

            if query:
                conditions.append("content LIKE ?")
                params.append(f"%{query}%")

            if memory_types:
                placeholders = ", ".join(["?" for _ in memory_types])
                conditions.append(f"memory_type IN ({placeholders})")
                params.extend(memory_types)

            where_clause = " AND ".join(conditions) if conditions else "1=1"
            params.append(limit)

            sql = f"SELECT * FROM memories WHERE {where_clause} ORDER BY importance DESC, created_at DESC LIMIT ?"
            cursor.execute(sql, params)

            rows = cursor.fetchall()
            memories = []
            for row in rows:
                memory = dict(row)

                # 解析元数据和标签
                if memory["metadata"]:
                    try:
                        memory["metadata"] = json.loads(memory["metadata"])
                    except:
                        memory["metadata"] = {}

                if memory["tags"]:
                    try:
                        memory["tags"] = json.loads(memory["tags"])
                    except:
                        memory["tags"] = []

                # 解析嵌入向量
                if memory["embedding"]:
                    try:
                        memory["embedding"] = json.loads(memory["embedding"])
                    except:
                        memory["embedding"] = None

                memories.append(memory)

            return memories

        except Exception as e:
            logger.error(f"搜索记忆失败: {e}")
            return []

    def search_by_similarity(self, query_embedding: List[float], 
                            memory_types: List[str] = None,
                            min_importance: float = 0,
                            limit: int = 10) -> List[Dict[str, Any]]:
        """
        基于向量相似度搜索记忆

        Args:
            query_embedding: 查询向量
            memory_types: 记忆类型过滤
            min_importance: 最小重要性
            limit: 返回数量限制

        Returns:
            List[Dict]: 记忆列表，包含相似度评分
        """
        try:
            # 首先获取所有符合条件的记忆
            cursor = self.conn.cursor()

            conditions = ["importance >= ?", "embedding IS NOT NULL"]
            params = [min_importance]

            if memory_types:
                placeholders = ", ".join(["?" for _ in memory_types])
                conditions.append(f"memory_type IN ({placeholders})")
                params.extend(memory_types)

            where_clause = " AND ".join(conditions) if conditions else "1=1"

            cursor.execute(f"SELECT * FROM memories WHERE {where_clause}", params)

            rows = cursor.fetchall()

            # 计算相似度
            memories_with_similarity = []
            for row in rows:
                memory = dict(row)

                # 解析嵌入向量
                if memory["embedding"]:
                    try:
                        embedding = json.loads(memory["embedding"])
                        similarity = self._cosine_similarity(query_embedding, embedding)

                        # 解析其他字段
                        if memory["metadata"]:
                            try:
                                memory["metadata"] = json.loads(memory["metadata"])
                            except:
                                memory["metadata"] = {}

                        if memory["tags"]:
                            try:
                                memory["tags"] = json.loads(memory["tags"])
                            except:
                                memory["tags"] = []

                        memory["similarity"] = similarity
                        memory["embedding"] = embedding  # 保留原始向量

                        memories_with_similarity.append(memory)
                    except:
                        continue

            # 按相似度排序
            memories_with_similarity.sort(key=lambda x: x["similarity"], reverse=True)

            return memories_with_similarity[:limit]

        except Exception as e:
            logger.error(f"向量相似度搜索失败: {e}")
            return []

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        计算余弦相似度

        Args:
            vec1: 向量1
            vec2: 向量2

        Returns:
            float: 相似度 (0-1)
        """
        if not vec1 or not vec2:
            return 0.0

        # 确保向量长度相同
        min_len = min(len(vec1), len(vec2))
        vec1 = vec1[:min_len]
        vec2 = vec2[:min_len]

        # 计算点积
        dot_product = sum(a * b for a, b in zip(vec1, vec2))

        # 计算范数
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5

        if norm1 == 0 or norm2 == 0:
            return 0.0

        similarity = dot_product / (norm1 * norm2)

        # 确保相似度在0-1范围内
        return max(0.0, min(1.0, similarity))

    def get_recent(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最近记忆"""
        return self.search(limit=limit)

    def update(self, memory_id: str, updates: Dict[str, Any]) -> bool:
        """
        更新记忆

        Args:
            memory_id: 记忆ID
            updates: 更新字段

        Returns:
            bool: 是否成功
        """
        try:
            cursor = self.conn.cursor()

            # 构建SET子句
            set_fields = []
            params = []

            allowed_fields = ["content", "importance", "memory_type", "metadata", "tags", 
                             "embedding", "embedding_model", "embedding_provider"]
            for field, value in updates.items():
                if field in allowed_fields:
                    if field in ["metadata", "tags", "embedding"]:
                        value = json.dumps(value) if value else None
                    set_fields.append(f"{field} = ?")
                    params.append(value)

            if not set_fields:
                logger.warning("没有有效的更新字段")
                return False

            set_fields.append("updated_at = CURRENT_TIMESTAMP")
            params.append(memory_id)

            sql = f"UPDATE memories SET {', '.join(set_fields)} WHERE id = ?"
            cursor.execute(sql, params)

            self.conn.commit()
            return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"更新记忆失败: {e}")
            return False

    def delete(self, memory_id: str) -> bool:
        """
        删除记忆

        Args:
            memory_id: 记忆ID

        Returns:
            bool: 是否成功
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM memories WHERE id = ?", (memory_id,))

            self.conn.commit()
            return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"删除记忆失败: {e}")
            return False

    def count(self, memory_type: str = None) -> int:
        """
        获取记忆数量

        Args:
            memory_type: 记忆类型过滤

        Returns:
            int: 记忆数量
        """
        try:
            cursor = self.conn.cursor()
            if memory_type:
                cursor.execute("SELECT COUNT(*) FROM memories WHERE memory_type = ?", (memory_type,))
            else:
                cursor.execute("SELECT COUNT(*) FROM memories")

            return cursor.fetchone()[0]

        except Exception as e:
            logger.error(f"获取记忆数量失败: {e}")
            return 0

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        try:
            cursor = self.conn.cursor()
            stats = {}

            # 各类型记忆数量
            cursor.execute("SELECT memory_type, COUNT(*) as count FROM memories GROUP BY memory_type")
            for row in cursor.fetchall():
                stats[row["memory_type"]] = row["count"]

            # 嵌入向量统计
            cursor.execute("SELECT COUNT(*) as with_embedding FROM memories WHERE embedding IS NOT NULL")
            stats["with_embedding"] = cursor.fetchone()[0]

            # 访问统计
            cursor.execute("SELECT SUM(access_count) as total_accesses, AVG(importance) as avg_importance FROM memories")
            row = cursor.fetchone()
            if row:
                stats["total_accesses"] = row[0] or 0
                stats["avg_importance"] = row[1] or 0

            return stats

        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {}

    def get_embeddings(self, memory_ids: List[str] = None) -> Dict[str, List[float]]:
        """
        获取嵌入向量

        Args:
            memory_ids: 记忆ID列表，None表示获取所有

        Returns:
            Dict: {memory_id: embedding}
        """
        try:
            cursor = self.conn.cursor()

            if memory_ids:
                placeholders = ", ".join(["?" for _ in memory_ids])
                cursor.execute(f"SELECT id, embedding FROM memories WHERE id IN ({placeholders})", memory_ids)
            else:
                cursor.execute("SELECT id, embedding FROM memories WHERE embedding IS NOT NULL")

            embeddings = {}
            for row in cursor.fetchall():
                memory_id = row["id"]
                embedding_json = row["embedding"]
                if embedding_json:
                    try:
                        embedding = json.loads(embedding_json)
                        embeddings[memory_id] = embedding
                    except:
                        continue

            return embeddings

        except Exception as e:
            logger.error(f"获取嵌入向量失败: {e}")
            return {}

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            self.conn = None


# 兼容性包装器，提供旧版API

    def store_memory(self, memory_id: str, content: str, importance: float = 0.5,
                       memory_type: str = "long_term", tags: List[str] = None,
                       metadata: Dict = None) -> bool:
        """兼容旧版API"""
        return self.store(memory_id, content, importance, memory_type, tags, metadata)

    def get_memory(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """兼容旧版API"""
        return self.get(memory_id)

    def search_memories(self, query: str = None, memory_types: List[str] = None,
                       min_importance: float = 0, limit: int = 10) -> List[Dict[str, Any]]:
        """兼容旧版API"""
        return self.search(query, memory_types, min_importance, limit)

    def get_recent_memories(self, limit: int = 10) -> List[Dict[str, Any]]:
        """兼容旧版API"""
        return self.get_recent(limit)

    def get_memory_count(self, memory_type: str = None) -> int:
        """兼容旧版API"""
        return self.count(memory_type)
class SQLiteStoreCompat(SQLiteStore):
    """兼容旧版API的SQLite存储"""

    def store_memory(self, memory_id: str, content: str, importance: float = 0.5,
                    memory_type: str = "long_term", tags: List[str] = None,
                    metadata: Dict = None) -> bool:
        """兼容旧版API"""
        return self.store(memory_id, content, importance, memory_type, tags, metadata)

    def get_memory(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """兼容旧版API"""
        return self.get(memory_id)

    def search_memories(self, query: str = None, memory_types: List[str] = None,
                       min_importance: float = 0, limit: int = 10) -> List[Dict[str, Any]]:
        """兼容旧版API"""
        return self.search(query, memory_types, min_importance, limit)

    def get_recent_memories(self, limit: int = 10) -> List[Dict[str, Any]]:
        """兼容旧版API"""
        return self.get_recent(limit)

    def get_memory_count(self, memory_type: str = None) -> int:
        """兼容旧版API"""
        return self.count(memory_type)


if __name__ == "__main__":
    import tempfile
    import shutil

    # 简单测试
    test_dir = tempfile.mkdtemp()
    try:
        logging.basicConfig(level=logging.INFO)

        print("测试SQLiteStore...")

        config = {"database_path": os.path.join(test_dir, "test.db")}
        store = SQLiteStore(config)

        # 测试存储
        test_id = "test_mem_001"
        success = store.store(
            memory_id=test_id,
            content="测试SQLite存储功能",
            importance=0.8,
            memory_type="long_term",
            tags=["测试", "SQLite"]
        )
        print(f"存储结果: {success}")

        # 测试添加嵌入向量
        test_embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
        success = store.add_embedding(test_id, test_embedding, "test-model", "test-provider")
        print(f"添加嵌入向量结果: {success}")

        # 测试获取
        memory = store.get(test_id)
        print(f"获取结果: {memory is not None}")

        # 测试向量搜索
        results = store.search_by_similarity(test_embedding)
        print(f"向量搜索结果: {len(results)} 条")

        # 测试统计
        stats = store.get_stats()
        print(f"统计信息: {stats}")

        store.close()
        print("✅ SQLiteStore测试完成")

    finally:
        shutil.rmtree(test_dir)