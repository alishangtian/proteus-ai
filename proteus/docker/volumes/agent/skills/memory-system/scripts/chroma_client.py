"""
Chroma向量数据库客户端封装
提供向量存储和检索功能，与SQLite结构化存储配合使用
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class ChromaClient:
    """Chroma向量数据库客户端"""
    
    def __init__(self, config: Dict[str, Any] = None, embedding_client=None):
        """
        初始化Chroma客户端
        
        Args:
            config: Chroma配置字典，包含持久化路径等
            embedding_client: 嵌入客户端实例，用于生成嵌入向量
        """
        self.config = config or {}
        self.embedding_client = embedding_client
        self.persist_directory = self.config.get(
            "persist_directory", 
            "/app/data/memory/chroma"
        )
        self.collection_name = self.config.get(
            "collection_name", 
            "memories"
        )
        self.embedding_function = None
        self.client = None
        self.collection = None
        
        logger.info(f"Chroma客户端初始化，持久化目录: {self.persist_directory}")
        
    def initialize(self, embedding_function=None):
        """
        初始化Chroma连接和集合

        Args:
            embedding_function: 嵌入函数，如果不提供则使用默认
        """
        try:
            import chromadb
            from chromadb.config import Settings

            # 创建客户端
            self.client = chromadb.PersistentClient(
                path=self.persist_directory,
                settings=Settings(anonymized_telemetry=False)
            )

            # 设置嵌入函数
            self.embedding_function = embedding_function
            if embedding_function is None:
                # 尝试使用embedding_client获取自定义嵌入函数
                if self.embedding_client is not None:
                    try:
                        # 获取Chroma兼容的嵌入函数
                        self.embedding_function = self.embedding_client.get_chroma_embedding_function()
                        logger.info(f"使用Ollama嵌入函数 (通过embedding_client)")
                    except Exception as e:
                        logger.warning(f"无法从embedding_client获取嵌入函数: {e}")
                        self.embedding_function = None
                
                # 如果仍然没有嵌入函数，尝试使用默认的sentence-transformers
                if self.embedding_function is None:
                    try:
                        from chromadb.utils import embedding_functions
                        self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
                            model_name="all-MiniLM-L6-v2"
                        )
                        logger.info(f"使用默认SentenceTransformer嵌入函数: all-MiniLM-L6-v2")
                    except ImportError:
                        logger.warning("sentence-transformers未安装，使用默认嵌入函数")
                        self.embedding_function = None

            # 获取或创建集合
            try:
                self.collection = self.client.get_collection(
                    name=self.collection_name,
                    embedding_function=self.embedding_function
                )
                logger.info(f"加载现有集合: {self.collection_name}")
            except Exception:
                self.collection = self.client.create_collection(
                    name=self.collection_name,
                    embedding_function=self.embedding_function,
                    metadata={"description": "AI记忆向量存储"}
                )
                logger.info(f"创建新集合: {self.collection_name}")

            logger.info(f"Chroma初始化成功，集合: {self.collection_name}")
            return True

        except ImportError as e:
            logger.error(f"Chroma库未安装: {e}")
            raise
        except Exception as e:
            logger.error(f"Chroma初始化失败: {e}")
            raise
    
    def add_embeddings(self, vectors: List[List[float]], 
                       ids: List[str],
                       metadatas: Optional[List[Dict]] = None,
                       documents: Optional[List[str]] = None) -> bool:
        """
        添加向量到Chroma
        
        Args:
            vectors: 向量列表
            ids: 向量ID列表（对应记忆ID）
            metadatas: 元数据列表
            documents: 原始文本列表
            
        Returns:
            bool: 是否成功
        """
        if not self.collection:
            self.initialize()
        
        try:
            # 如果提供了向量，直接使用
            if vectors and len(vectors) > 0:
                self.collection.add(
                    embeddings=vectors,
                    ids=ids,
                    metadatas=metadatas,
                    documents=documents
                )
            # 如果没有提供向量但提供了文档，让Chroma生成嵌入
            elif documents and len(documents) > 0:
                self.collection.add(
                    ids=ids,
                    metadatas=metadatas,
                    documents=documents
                )
            else:
                logger.warning("既没有提供向量也没有提供文档，无法添加")
                return False
            
            logger.info(f"添加了 {len(ids)} 个向量到Chroma")
            return True
            
        except Exception as e:
            logger.error(f"添加向量失败: {e}")
            return False
    
    def search(self, query_vector: List[float], 
               n_results: int = 10,
               where: Optional[Dict] = None,
               where_document: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """
        向量相似性搜索
        
        Args:
            query_vector: 查询向量
            n_results: 返回结果数量
            where: 元数据过滤条件
            where_document: 文档内容过滤条件
            
        Returns:
            List[Dict]: 搜索结果，包含id, distance, metadata, document等
        """
        if not self.collection:
            self.initialize()
        
        try:
            # 使用query_embeddings参数进行搜索
            results = self.collection.query(
                query_embeddings=[query_vector],
                n_results=n_results,
                where=where,
                where_document=where_document
            )
            
            # 转换结果格式
            formatted_results = []
            if results and "ids" in results and len(results["ids"]) > 0:
                for i in range(len(results["ids"][0])):
                    formatted_results.append({
                        "id": results["ids"][0][i],
                        "distance": results["distances"][0][i] if "distances" in results else None,
                        "metadata": results["metadatas"][0][i] if "metadatas" in results else {},
                        "document": results["documents"][0][i] if "documents" in results else None,
                    })
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"向量搜索失败: {e}")
            return []
    
    def search_by_text(self, query_text: str, 
                      n_results: int = 10,
                      where: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """
        通过文本进行语义搜索（Chroma自动生成嵌入）
        
        Args:
            query_text: 查询文本
            n_results: 返回结果数量
            where: 元数据过滤条件
            
        Returns:
            List[Dict]: 搜索结果
        """
        if not self.collection:
            self.initialize()
        
        # 检查是否有嵌入函数，如果没有则无法进行文本搜索
        if self.embedding_function is None:
            logger.warning("无法进行文本搜索：未设置嵌入函数")
            return []
        
        try:
            results = self.collection.query(
                query_texts=[query_text],
                n_results=n_results,
                where=where
            )
            
            formatted_results = []
            if results and "ids" in results and len(results["ids"]) > 0:
                for i in range(len(results["ids"][0])):
                    formatted_results.append({
                        "id": results["ids"][0][i],
                        "distance": results["distances"][0][i] if "distances" in results else None,
                        "metadata": results["metadatas"][0][i] if "metadatas" in results else {},
                        "document": results["documents"][0][i] if "documents" in results else None,
                    })
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"文本搜索失败: {e}")
            return []
    
    def get_by_ids(self, ids: List[str]) -> List[Dict[str, Any]]:
        """
        通过ID获取向量
        
        Args:
            ids: 向量ID列表
            
        Returns:
            List[Dict]: 向量信息
        """
        if not self.collection:
            self.initialize()
        
        try:
            results = self.collection.get(ids=ids)
            
            formatted_results = []
            if results and "ids" in results and len(results["ids"]) > 0:
                for i in range(len(results["ids"])):
                    formatted_results.append({
                        "id": results["ids"][i],
                        "metadata": results["metadatas"][i] if "metadatas" in results else {},
                        "document": results["documents"][i] if "documents" in results else None,
                        "embedding": results["embeddings"][i] if "embeddings" in results else None,
                    })
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"获取向量失败: {e}")
            return []
    
    def update_metadata(self, id: str, metadata: Dict[str, Any]) -> bool:
        """
        更新向量的元数据
        
        Args:
            id: 向量ID
            metadata: 新的元数据
            
        Returns:
            bool: 是否成功
        """
        if not self.collection:
            self.initialize()
        
        try:
            self.collection.update(
                ids=[id],
                metadatas=[metadata]
            )
            return True
            
        except Exception as e:
            logger.error(f"更新元数据失败: {e}")
            return False
    
    def delete(self, ids: List[str]) -> bool:
        """
        删除向量
        
        Args:
            ids: 要删除的向量ID列表
            
        Returns:
            bool: 是否成功
        """
        if not self.collection:
            self.initialize()
        
        try:
            self.collection.delete(ids=ids)
            logger.info(f"删除了 {len(ids)} 个向量")
            return True
            
        except Exception as e:
            logger.error(f"删除向量失败: {e}")
            return False
    
    def count(self) -> int:
        """
        获取集合中的向量数量
        
        Returns:
            int: 向量数量
        """
        if not self.collection:
            self.initialize()
        
        try:
            return self.collection.count()
        except Exception as e:
            logger.error(f"获取向量数量失败: {e}")
            return 0
    
    def get_collection_info(self) -> Dict[str, Any]:
        """
        获取集合信息
        
        Returns:
            Dict: 集合信息
        """
        if not self.collection:
            self.initialize()
        
        try:
            return {
                "name": self.collection.name,
                "count": self.collection.count(),
                "metadata": self.collection.metadata
            }
        except Exception as e:
            logger.error(f"获取集合信息失败: {e}")
            return {}
    
    def reset_collection(self) -> bool:
        """
        重置集合（删除所有数据）
        
        Returns:
            bool: 是否成功
        """
        try:
            self.client.delete_collection(name=self.collection_name)
            self.collection = None
            self.initialize()
            logger.info("集合已重置")
            return True
            
        except Exception as e:
            logger.error(f"重置集合失败: {e}")
            return False


# 默认配置
DEFAULT_CHROMA_CONFIG = {
    "persist_directory": "/app/data/memory/chroma",
    "collection_name": "memories",
    "embedding_model": "all-MiniLM-L6-v2",
    "create_if_missing": True
}


def create_chroma_client(config: Dict = None) -> ChromaClient:
    """
    创建Chroma客户端实例
    
    Args:
        config: 配置字典
        
    Returns:
        ChromaClient: 客户端实例
    """
    final_config = DEFAULT_CHROMA_CONFIG.copy()
    if config:
        final_config.update(config)
    
    client = ChromaClient(final_config)
    client.initialize()
    return client


if __name__ == "__main__":
    # 测试代码
    import sys
    
    logging.basicConfig(level=logging.INFO)
    
    try:
        client = create_chroma_client()
        print(f"Chroma客户端创建成功")
        print(f"集合信息: {client.get_collection_info()}")
        
        # 测试添加
        test_ids = ["test_1", "test_2"]
        test_docs = ["这是一个测试记忆", "另一个测试记忆"]
        
        success = client.add_embeddings(
            vectors=[],  # 不提供向量，让Chroma生成
            ids=test_ids,
            documents=test_docs,
            metadatas=[{"importance": 0.5}, {"importance": 0.8}]
        )
        
        if success:
            print(f"添加测试数据成功，当前向量数量: {client.count()}")
            
            # 测试搜索
            results = client.search_by_text("测试记忆", n_results=5)
            print(f"文本搜索结果: {len(results)} 条")
            
            # 清理测试数据
            client.delete(test_ids)
            print(f"清理测试数据，当前向量数量: {client.count()}")
        
    except ImportError as e:
        print(f"需要安装Chroma: {e}")
        print("运行: pip install chromadb")
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
