import chromadb
import logging
from typing import List, Dict, Any, Optional

from src.utils.ollama_embedding import get_embedding_model

logger = logging.getLogger(__name__)


class CustomEmbeddingFunction:
    """自定义嵌入函数，使用 Ollama bge-m3 模型

    为了兼容 ChromaDB 的 embedding 接口，提供 embed_query 和 embed_documents 方法，
    同时保留 __call__ 作为向后兼容入口。
    """

    def __init__(self, ollama_url: str = "http://127.0.0.1:11434"):
        """初始化自定义嵌入函数

        Args:
            ollama_url: Ollama 服务地址
        """
        self.embedding_model = get_embedding_model(ollama_url)
        self.logger = logger

    def _embed_single(self, text: str) -> List[float]:
        """为单条文本生成嵌入，封装异常处理"""
        try:
            embedding = self.embedding_model.get_embedding(text)
            if embedding is not None:
                return embedding
            else:
                self.logger.warning(f"文本嵌入失败，使用零向量占位: {text[:50]}...")
        except Exception as e:
            self.logger.error(f"嵌入过程中发生错误，使用零向量占位: {e}")
        # 假设 bge-m3 的维度是 1024，实际使用时需要根据模型调整或动态检测
        return [0.0] * 1024

    def __call__(self, input: List[str]) -> List[List[float]]:
        """为文本列表生成嵌入向量（兼容之前的调用）"""
        return [self._embed_single(text) for text in input]

    # ChromaDB expects these methods on the embedding function object
    def embed_query(self, input: List[str]) -> List[List[float]]:
        """为查询文本生成嵌入（用于 query 请求）"""
        return self.__call__(input)

    def embed_documents(self, input: List[str]) -> List[List[float]]:
        """为 documents 生成嵌入（用于 add / upsert 等操作）"""
        return self.__call__(input)

    def name(self) -> str:
        """返回嵌入函数名称，用于ChromaDB兼容性"""
        return "custom_ollama_bge_m3"


class ChromeVectorDB:
    """Chrome 向量数据库管理器

    使用 ChromaDB 作为向量存储，集成 Ollama bge-m3 嵌入模型
    """

    def __init__(
        self,
        persist_directory: str = "./chroma_db",
        ollama_url: str = "http://127.0.0.1:11434",
    ):
        """初始化 Chrome 向量数据库

        Args:
            persist_directory: 数据库持久化目录
            ollama_url: Ollama 服务地址
        """
        self.client = chromadb.PersistentClient(path=persist_directory)
        self.embedding_function = CustomEmbeddingFunction(ollama_url)
        self.logger = logger

    def create_collection(self, collection_name: str, metadata: Optional[Dict] = None):
        """创建或获取集合

        Args:
            collection_name: 集合名称
            metadata: 集合元数据

        Returns:
            chromadb.Collection: 集合对象
        """
        try:
            collection = self.client.get_or_create_collection(
                name=collection_name,
                metadata=metadata or {"hnsw:space": "cosine"},
                embedding_function=self.embedding_function,
            )
            self.logger.info(f"成功创建/获取集合: {collection_name}")
            return collection
        except Exception as e:
            self.logger.error(f"创建集合失败: {e}")
            raise

    def add_documents(
        self,
        collection_name: str,
        documents: List[str],
        metadatas: List[Dict[str, Any]],
        ids: Optional[List[str]] = None,
    ):
        """向集合添加文档

        Args:
            collection_name: 集合名称
            documents: 文档列表
            metadatas: 元数据列表
            ids: 文档ID列表，如果为None则自动生成
        """
        try:
            collection = self.create_collection(collection_name)

            if ids is None:
                import uuid

                ids = [str(uuid.uuid4()) for _ in documents]

            collection.add(documents=documents, metadatas=metadatas, ids=ids)
            self.logger.info(
                f"成功向集合 {collection_name} 添加 {len(documents)} 个文档"
            )
        except Exception as e:
            self.logger.error(f"添加文档失败: {e}")
            raise

    def query(
        self,
        collection_name: str,
        query_texts: List[str],
        n_results: int = 5,
        where: Optional[Dict] = None,
        ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """查询相似文档

        Args:
            collection_name: 集合名称
            query_texts: 查询文本列表
            n_results: 返回结果数量
            where: 过滤条件（基于 metadata）
            ids: 可选的文档 id 列表，用于限制检索范围（比方说基于第一阶段候选的 id）

        Returns:
            Dict: 查询结果，包含文档、距离、元数据等信息
        """
        try:
            collection = self.create_collection(collection_name)

            # 把 ids 和 where 都传给 collection.query（chromadb 支持 ids 限制）
            # 如果 ids 不为空，会把检索限制在指定 id 集合内（适用于第二阶段精排）
            results = collection.query(
                query_texts=query_texts, n_results=n_results, where=where, ids=ids
            )

            num_results = 0
            if results and "documents" in results and results["documents"]:
                try:
                    num_results = len(results["documents"][0])
                except Exception:
                    # 如果返回格式不同，降级处理
                    num_results = sum(len(d) for d in results.get("documents", []))

            self.logger.info(
                f"查询集合 {collection_name} 返回 {num_results} 个结果"
            )
            return results
        except Exception as e:
            self.logger.error(f"查询失败: {e}")
            raise

    def get_collection_info(self, collection_name: str) -> Dict[str, Any]:
        """获取集合信息

        Args:
            collection_name: 集合名称

        Returns:
            Dict: 集合信息
        """
        try:
            collection = self.create_collection(collection_name)
            count = collection.count()

            return {
                "name": collection_name,
                "count": count,
                "metadata": collection.metadata,
            }
        except Exception as e:
            self.logger.error(f"获取集合信息失败: {e}")
            raise

    def delete_collection(self, collection_name: str):
        """删除集合

        Args:
            collection_name: 集合名称
        """
        try:
            self.client.delete_collection(collection_name)
            self.logger.info(f"成功删除集合: {collection_name}")
        except Exception as e:
            self.logger.error(f"删除集合失败: {e}")
            raise

    def delete_documents(self, collection_name: str, ids: List[str]):
        """删除指定文档

        Args:
            collection_name: 集合名称
            ids: 要删除的文档ID列表
        """
        try:
            collection = self.create_collection(collection_name)
            collection.delete(ids=ids)
            self.logger.info(f"成功从集合 {collection_name} 删除 {len(ids)} 个文档")
        except Exception as e:
            self.logger.error(f"删除文档失败: {e}")
            raise

    def test_embedding_function(self, text: str = "测试文本") -> bool:
        """测试嵌入函数是否正常工作

        Args:
            text: 测试文本

        Returns:
            bool: 嵌入函数是否正常工作
        """
        texts = [text]
        try:
            embedding = self.embedding_function.__call__(texts)
            if embedding and len(embedding) > 0:
                self.logger.info(f"嵌入函数测试成功，向量维度: {len(embedding)}")
                return True
            else:
                self.logger.error("嵌入函数测试失败：未生成有效向量")
                return False
        except Exception as e:
            self.logger.error(f"嵌入函数测试失败: {e}")
            return False


chromeVectorDB = ChromeVectorDB()
