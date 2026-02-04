"""
统一嵌入客户端 - 支持多种嵌入模型提供商
包括Chroma内置模型、Ollama、OpenAI和本地模型
"""

import os
import json
import time
import logging
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingResult:
    """嵌入结果数据类"""
    embedding: List[float]
    model: str
    provider: str
    dimensions: int
    processing_time: float


class EmbeddingClient:
    """统一嵌入客户端 - 支持多种提供商"""
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化嵌入客户端
        
        Args:
            config: 嵌入配置字典
        """
        self.config = config or {}
        self.enabled = self.config.get("enabled", True)
        self.default_provider = self.config.get("default_provider", "ollama")  # 只支持ollama
        self.providers = self.config.get("providers", {})
        
        # 缓存配置
        self.cache_enabled = self.config.get("cache_enabled", True)
        self._embedding_cache = {}
        self._cache_max_size = 1000
        
        # 初始化各提供商客户端
        self._chroma_client = None
        self._ollama_available = False
        self._openai_available = False
        
        self._initialize_providers()
        
        logger.info(f"嵌入客户端初始化完成，启用: {self.enabled}, 默认提供商: {self.default_provider}")
    
    def _initialize_providers(self):
        """初始化各提供商"""
        # 检查Chroma
        try:
            import chromadb
            self._chroma_available = True
        except ImportError:
            self._chroma_available = False
            logger.warning("Chroma未安装，Chroma嵌入功能将不可用")
        
        # 检查Ollama可用性
        self._ollama_available = self._check_ollama_available()
        
        # 检查OpenAI SDK
        try:
            import openai
            self._openai_available = True
        except ImportError:
            self._openai_available = False
            logger.debug("OpenAI SDK未安装，将使用requests调用API")
    
    def _check_ollama_available(self) -> bool:
        """检查Ollama服务是否可用"""
        ollama_config = self.providers.get("ollama", {})
        base_url = ollama_config.get("base_url", "http://host.docker.internal:11434")
        
        try:
            import requests
            response = requests.get(f"{base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def _get_cache_key(self, text: str, provider: str, model: str) -> str:
        """生成缓存键"""
        content = f"{provider}:{model}:{text}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def _get_from_cache(self, cache_key: str) -> Optional[List[float]]:
        """从缓存获取嵌入"""
        if not self.cache_enabled:
            return None
        
        if cache_key in self._embedding_cache:
            cached = self._embedding_cache[cache_key]
            # 简单缓存，没有TTL（可以在配置中添加）
            return cached["embedding"]
        
        return None
    
    def _add_to_cache(self, cache_key: str, embedding: List[float]):
        """添加嵌入到缓存"""
        if not self.cache_enabled:
            return
        
        if len(self._embedding_cache) >= self._cache_max_size:
            # 移除最旧的条目（简化实现）
            keys = list(self._embedding_cache.keys())
            if keys:
                del self._embedding_cache[keys[0]]
        
        self._embedding_cache[cache_key] = {
            "embedding": embedding,
            "timestamp": time.time()
        }
    
    def get_embedding(self, text: str, provider: str = None, 
                     model: str = None, **kwargs) -> EmbeddingResult:
        """
        获取文本的嵌入向量
        
        Args:
            text: 输入文本
            provider: 提供商名称，None使用默认
            model: 模型名称，None使用提供商默认
            **kwargs: 其他参数
            
        Returns:
            EmbeddingResult: 嵌入结果
            
        Raises:
            ValueError: 提供商不可用或请求失败
        """
        if not self.enabled:
            return self._get_simple_embedding(text, "disabled", "simple")
        
        provider = provider or self.default_provider

        # 嵌入模型只支持ollama，不支持其他方式
        if provider != "ollama":
            logger.warning(f"嵌入模型只支持ollama，不支持{provider}，将使用ollama代替")
            provider = "ollama"
            provider_config = self.providers.get(provider, {})
            if not provider_config:
                raise ValueError("嵌入配置中未找到ollama provider，请检查配置")
        provider_config = self.providers.get(provider, {})
        
        if not provider_config:
            raise ValueError(f"嵌入提供商 '{provider}' 未配置")
        
        model = model or provider_config.get("default_model")
        if not model:
            raise ValueError(f"未指定模型且无默认模型 for provider: {provider}")
        
        # 检查缓存
        cache_key = self._get_cache_key(text, provider, model)
        cached_embedding = self._get_from_cache(cache_key)
        if cached_embedding is not None:
            return EmbeddingResult(
                embedding=cached_embedding,
                model=model,
                provider=provider,
                dimensions=len(cached_embedding),
                processing_time=0.0
            )
        
        start_time = time.time()
        
        try:
            # 根据提供商调用相应的方法
            if provider == "chroma":
                embedding = self._get_chroma_embedding(text, model, provider_config, **kwargs)
            elif provider == "ollama":
                embedding = self._get_ollama_embedding(text, model, provider_config, **kwargs)
            elif provider == "openai":
                embedding = self._get_openai_embedding(text, model, provider_config, **kwargs)
            elif provider == "local":
                embedding = self._get_local_embedding(text, model, provider_config, **kwargs)
            else:
                raise ValueError(f"不支持的嵌入提供商: {provider}")
            
            processing_time = time.time() - start_time
            
            # 添加到缓存
            self._add_to_cache(cache_key, embedding)
            
            result = EmbeddingResult(
                embedding=embedding,
                model=model,
                provider=provider,
                dimensions=len(embedding),
                processing_time=processing_time
            )
            
            logger.debug(f"嵌入生成完成: provider={provider}, model={model}, "
                        f"dimensions={len(embedding)}, time={processing_time:.3f}s")
            
            return result
            
        except Exception as e:
            logger.warning(f"嵌入生成失败 (provider={provider}, model={model}): {e}")
            # 降级到简单嵌入
            return self._get_simple_embedding(text, provider, model)
    
    def _get_chroma_embedding(self, text: str, model: str, 
                             config: Dict[str, Any], **kwargs) -> List[float]:
        """使用Chroma内置模型获取嵌入"""
        if not self._chroma_available:
            raise ValueError("Chroma不可用")
        
        try:
            from chromadb.utils import embedding_functions
            
            # 根据模型名称创建嵌入函数
            if model == "all-MiniLM-L6-v2":
                ef = embedding_functions.SentenceTransformerEmbeddingFunction(
                    model_name=model
                )
            elif model.startswith("BAAI/"):
                # BAAI模型
                ef = embedding_functions.SentenceTransformerEmbeddingFunction(
                    model_name=model
                )
            else:
                # 默认使用all-MiniLM-L6-v2
                ef = embedding_functions.SentenceTransformerEmbeddingFunction(
                    model_name="all-MiniLM-L6-v2"
                )
            
            # 生成嵌入
            embedding = ef([text])
            if embedding and len(embedding) > 0:
                return embedding[0]
            else:
                raise ValueError("Chroma嵌入生成返回空结果")
                
        except Exception as e:
            raise ValueError(f"Chroma嵌入失败: {e}")
    
    def _get_ollama_embedding(self, text: str, model: str, 
                             config: Dict[str, Any], **kwargs) -> List[float]:
        """使用Ollama获取嵌入（使用 /api/embed 端点）
        
        Args:
            text: 输入文本
            model: 模型名称
            config: 配置字典
            **kwargs: 其他参数
            
        Returns:
            List[float]: 嵌入向量
            
        Raises:
            ValueError: Ollama服务不可用或请求失败
        """
        if not self._ollama_available:
            raise ValueError("Ollama服务不可用")
        
        base_url = config.get("base_url", "http://host.docker.internal:11434")
        timeout = config.get("timeout", 30)
        batch_size = config.get("batch_size", 10)
        
        try:
            import requests
            
            # 准备请求数据 - 使用 /api/embed 端点，参数名为 input
            data = {
                "model": model,
                "input": text  # 可以是单个字符串或字符串列表
            }
            
            response = requests.post(
                f"{base_url}/api/embed",
                json=data,
                timeout=timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # 检查响应格式
                if "embeddings" not in result:
                    # 尝试兼容旧格式
                    if "embedding" in result:
                        return result["embedding"]
                    else:
                        raise ValueError("Ollama响应格式无效，缺少 'embeddings' 字段")
                
                embeddings = result["embeddings"]
                if not embeddings:
                    raise ValueError("Ollama返回空嵌入向量列表")
                
                # 对于单个文本输入，embeddings 应该是一个包含单个向量的列表
                if len(embeddings) == 1:
                    embedding_vector = embeddings[0]
                    if not embedding_vector:
                        raise ValueError("Ollama返回空嵌入向量")
                    return embedding_vector
                else:
                    # 如果是批量响应但只请求了单个文本，这不应该发生
                    # 但为了健壮性，返回第一个向量
                    logger.warning(f"Ollama返回了 {len(embeddings)} 个向量，但只请求了1个文本")
                    return embeddings[0] if embeddings else []
                    
            else:
                error_text = response.text[:200] if response.text else "无错误信息"
                raise ValueError(f"Ollama API错误 {response.status_code}: {error_text}")
                
        except requests.exceptions.Timeout:
            raise ValueError(f"Ollama请求超时（{timeout}秒）")
        except requests.exceptions.ConnectionError:
            raise ValueError(f"无法连接到Ollama服务: {base_url}")
        except Exception as e:
            raise ValueError(f"Ollama嵌入失败: {e}")
    def _get_openai_embedding(self, text: str, model: str, 
                             config: Dict[str, Any], **kwargs) -> List[float]:
        """使用OpenAI获取嵌入"""
        api_key = config.get("api_key", "")
        base_url = config.get("base_url", "https://api.openai.com/v1")
        timeout = config.get("timeout", 30)
        
        # 处理环境变量
        if api_key.startswith("${") and api_key.endswith("}"):
            env_var = api_key[2:-1]
            api_key = os.environ.get(env_var, "")
        
        if not api_key:
            raise ValueError("OpenAI API密钥未配置")
        
        try:
            import requests
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
            
            data = {
                "model": model,
                "input": text
            }
            
            response = requests.post(
                f"{base_url}/embeddings",
                headers=headers,
                json=data,
                timeout=timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                if "data" in result and len(result["data"]) > 0:
                    return result["data"][0]["embedding"]
                else:
                    raise ValueError("OpenAI返回空嵌入向量")
            else:
                raise ValueError(f"OpenAI API错误: {response.status_code}")
                
        except Exception as e:
            raise ValueError(f"OpenAI嵌入失败: {e}")
    
    def _get_local_embedding(self, text: str, model: str, 
                            config: Dict[str, Any], **kwargs) -> List[float]:
        """使用本地API获取嵌入"""
        base_url = config.get("base_url", "http://localhost:8080/v1")
        api_key = config.get("api_key", "")
        timeout = config.get("timeout", 60)
        
        try:
            import requests
            
            headers = {
                "Content-Type": "application/json"
            }
            
            if api_key and api_key != "sk-no-key-required":
                headers["Authorization"] = f"Bearer {api_key}"
            
            data = {
                "model": model,
                "input": text
            }
            
            response = requests.post(
                f"{base_url}/embeddings",
                headers=headers,
                json=data,
                timeout=timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                if "data" in result and len(result["data"]) > 0:
                    return result["data"][0]["embedding"]
                else:
                    raise ValueError("本地API返回空嵌入向量")
            else:
                raise ValueError(f"本地API错误: {response.status_code}")
                
        except Exception as e:
            raise ValueError(f"本地嵌入失败: {e}")
    
    def _get_simple_embedding(self, text: str, provider: str, model: str) -> EmbeddingResult:
        """生成简单嵌入向量（降级方案）"""
        # 基于词频的简单向量
        words = text.lower().split()
        if not words:
            embedding = [0.0] * 10
        else:
            # 创建有限的词表
            unique_words = list(set(words))
            vocab_size = min(50, len(unique_words))
            
            embedding = [0.0] * vocab_size
            for i in range(vocab_size):
                word = unique_words[i % len(unique_words)]
                embedding[i] = words.count(word) / len(words)
            
            # 归一化
            norm = sum(x**2 for x in embedding) ** 0.5
            if norm > 0:
                embedding = [x / norm for x in embedding]
        
        return EmbeddingResult(
            embedding=embedding,
            model=model,
            provider=provider,
            dimensions=len(embedding),
            processing_time=0.0
        )
    
    def batch_get_embeddings(self, texts: List[str], provider: str = None,
                           model: str = None, **kwargs) -> List[EmbeddingResult]:
        """
        批量获取嵌入向量
        
        Args:
            texts: 文本列表
            provider: 提供商名称
            model: 模型名称
            **kwargs: 其他参数
            
        Returns:
            List[EmbeddingResult]: 嵌入结果列表
        """
        results = []
        for text in texts:
            try:
                result = self.get_embedding(text, provider, model, **kwargs)
                results.append(result)
            except Exception as e:
                logger.warning(f"批量嵌入生成失败 for text '{text[:50]}...': {e}")
                # 添加简单嵌入作为降级
                simple_result = self._get_simple_embedding(text, provider or self.default_provider, model or "simple")
                results.append(simple_result)
        
        return results
    
    def get_provider_info(self) -> Dict[str, Any]:
        """获取提供商信息"""
        info = {
            "enabled": self.enabled,
            "default_provider": self.default_provider,
            "providers": {}
        }
        
        for provider_name, provider_config in self.providers.items():
            info["providers"][provider_name] = {
                "configured": True,
                "default_model": provider_config.get("default_model", "unknown"),
                "available": self._check_provider_available(provider_name)
            }
        
        return info
    
    def _check_provider_available(self, provider: str) -> bool:
        """检查提供商是否可用"""
        if provider == "chroma":
            return self._chroma_available
        elif provider == "ollama":
            return self._ollama_available
        elif provider == "openai":
            # OpenAI总是可用（会有API错误但不影响初始化）
            return True
        elif provider == "local":
            # 本地API假设可用
            return True
        else:
            return False


    def get_chroma_embedding_function(self):
        """返回一个Chroma兼容的嵌入函数
        
        返回的函数符合Chroma嵌入函数接口：
        - 输入: 文本列表 (List[str])
        - 输出: 嵌入向量列表 (List[List[float]])
        """
        from typing import List
        
        class OllamaEmbeddingFunction:
            """Ollama嵌入函数包装类，符合Chroma嵌入函数接口"""
            
            def __init__(self, embedding_client):
                self.embedding_client = embedding_client
                
            def __call__(self, input: List[str]) -> List[List[float]]:
                """为文本列表生成嵌入向量"""
                texts = input
                embeddings = []
                for text in texts:
                    try:
                        result = self.embedding_client.get_embedding(text)
                        embeddings.append(result.embedding)
                    except Exception as e:
                        # 降级方案：生成简单嵌入
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.warning(f"嵌入生成失败，使用降级方案: {e}")
                        # 生成简单嵌入
                        words = text.lower().split()
                        if not words:
                            embedding = [0.0] * 10
                        else:
                            unique_words = list(set(words))
                            vocab_size = min(50, len(unique_words))
                            embedding = [0.0] * vocab_size
                            for i in range(vocab_size):
                                word = unique_words[i % len(unique_words)]
                                embedding[i] = words.count(word) / len(words)
                            # 归一化
                            norm = sum(x**2 for x in embedding) ** 0.5
                            if norm > 0:
                                embedding = [x / norm for x in embedding]
                        embeddings.append(embedding)
                return embeddings
        
        return OllamaEmbeddingFunction(self)


# 使用示例
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # 测试配置
    test_config = {
        "enabled": True,
        "default_provider": "chroma",
        "providers": {
            "chroma": {
                "default_model": "all-MiniLM-L6-v2"
            },
            "ollama": {
                "base_url": "http://host.docker.internal:11434",
                "default_model": "bge-m3"
            }
        }
    }
    
    client = EmbeddingClient(test_config)
    print(f"嵌入客户端初始化: 启用={client.enabled}")
    
    # 获取提供商信息
    info = client.get_provider_info()
    print(f"提供商信息: {info}")
    
    # 测试嵌入生成
    test_text = "这是一个测试文本，用于验证嵌入生成功能"
    try:
        result = client.get_embedding(test_text)
        print(f"嵌入生成测试:")
        print(f"  提供商: {result.provider}")
        print(f"  模型: {result.model}")
        print(f"  维度: {result.dimensions}")
        print(f"  处理时间: {result.processing_time:.3f}s")
        print(f"  嵌入向量 (前5维): {result.embedding[:5]}")
    except Exception as e:
        print(f"嵌入生成失败: {e}")
        # 测试降级方案
        result = client._get_simple_embedding(test_text, "test", "simple")
        print(f"降级嵌入: 维度={result.dimensions}")
    
    print("嵌入客户端测试完成")
