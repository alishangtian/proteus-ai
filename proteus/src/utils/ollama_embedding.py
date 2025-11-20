import requests
import logging
from typing import List, Optional
import json
from typing import Dict

logger = logging.getLogger(__name__)


class OllamaEmbedding:
    """Ollama 嵌入模型管理器

    使用 Ollama 的 bge-m3 模型生成文本嵌入向量
    1024维度
    """

    def __init__(self, base_url: str = "http://127.0.0.1:11434"):
        """初始化 Ollama 嵌入模型管理器

        Args:
            base_url: Ollama 服务地址
        """
        self.base_url = base_url
        self.model_name = "bge-m3"  # 使用 bge-m3 模型
        self.logger = logger

    def get_embedding(self, text: str) -> Optional[List[float]]:
        """获取单个文本的嵌入向量

        Args:
            text: 输入文本

        Returns:
            List[float]: 嵌入向量，如果失败返回 None
        """
        try:
            response = requests.post(
                f"{self.base_url}/api/embeddings",
                json={"model": self.model_name, "prompt": text},
                timeout=30,
            )

            if response.status_code == 200:
                result = response.json()
                embedding = result.get("embedding")
                if embedding:
                    self.logger.info(f"成功生成文本嵌入向量，维度: {len(embedding)}")
                    return embedding
                else:
                    self.logger.error("嵌入向量生成失败：响应中未找到 embedding 字段")
                    return None
            else:
                self.logger.error(
                    f"嵌入向量生成失败：HTTP {response.status_code} - {response.text}"
                )
                return None

        except requests.exceptions.RequestException as e:
            self.logger.error(f"请求 Ollama 服务失败: {e}")
            return None
        except Exception as e:
            self.logger.error(f"生成嵌入向量时发生未知错误: {e}")
            return None

    def get_embeddings_batch(self, texts: List[str]) -> Optional[List[List[float]]]:
        """批量获取文本嵌入向量

        Args:
            texts: 输入文本列表

        Returns:
            List[List[float]]: 嵌入向量列表，如果失败返回 None
        """
        embeddings = []
        for text in texts:
            embedding = self.get_embedding(text)
            if embedding is not None:
                embeddings.append(embedding)
            else:
                # 如果有一个失败，整个批次都视为失败
                self.logger.error(
                    f"批量生成嵌入向量失败，在文本 '{text[:50]}...' 处中断"
                )
                return None

        self.logger.info(f"成功批量生成 {len(embeddings)} 个嵌入向量")
        return embeddings

    def test_connection(self) -> bool:
        """测试与 Ollama 服务的连接

        Returns:
            bool: 连接是否成功
        """
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=10)
            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [model.get("name", "") for model in models]

                if any(self.model_name in name for name in model_names):
                    self.logger.info(
                        f"Ollama 服务连接正常，模型 {self.model_name} 可用"
                    )
                    return True
                else:
                    self.logger.warning(
                        f"Ollama 服务连接正常，但未找到模型 {self.model_name}"
                    )
                    return False
            else:
                self.logger.error(f"Ollama 服务连接失败：HTTP {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            self.logger.error(f"无法连接到 Ollama 服务: {e}")
            return False

    def get_model_info(self) -> Optional[Dict]:
        """获取模型信息

        Returns:
            Dict: 模型信息，如果失败返回 None
        """
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=10)
            if response.status_code == 200:
                models = response.json().get("models", [])
                for model in models:
                    if self.model_name in model.get("name", ""):
                        return model
                return None
            else:
                self.logger.error(f"获取模型信息失败：HTTP {response.status_code}")
                return None
        except requests.exceptions.RequestException as e:
            self.logger.error(f"获取模型信息失败: {e}")
            return None


# 全局嵌入模型实例
_embedding_model = None


def get_embedding_model(base_url: str = "http://127.0.0.1:11434") -> OllamaEmbedding:
    """获取全局嵌入模型实例

    Args:
        base_url: Ollama 服务地址

    Returns:
        OllamaEmbedding: 嵌入模型实例
    """
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = OllamaEmbedding(base_url)
    return _embedding_model


def get_text_embedding(
    text: str, base_url: str = "http://127.0.0.1:11434"
) -> Optional[List[float]]:
    """便捷函数：获取单个文本的嵌入向量

    Args:
        text: 输入文本
        base_url: Ollama 服务地址

    Returns:
        List[float]: 嵌入向量，如果失败返回 None
    """
    model = get_embedding_model(base_url)
    return model.get_embedding(text)


def get_text_embeddings_batch(
    texts: List[str], base_url: str = "http://127.0.0.1:11434"
) -> Optional[List[List[float]]]:
    """便捷函数：批量获取文本嵌入向量

    Args:
        texts: 输入文本列表
        base_url: Ollama 服务地址

    Returns:
        List[List[float]]: 嵌入向量列表，如果失败返回 None
    """
    model = get_embedding_model(base_url)
    return model.get_embeddings_batch(texts)
