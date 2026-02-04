"""
统一LLM客户端 - 支持多种LLM提供商，用于记忆生成和增强
"""

import os
import json
import time
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    """LLM配置数据类"""
    enabled: bool = False
    default_provider: str = "openai"
    timeout: int = 30
    temperature: float = 0.3
    max_tokens: int = 1000


class LLMClient:
    """统一LLM客户端 - 支持多种提供商"""
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化LLM客户端
        
        Args:
            config: LLM配置字典
        """
        self.config = config or {}
        self.enabled = self.config.get("enabled", False)
        self.default_provider = self.config.get("default_provider", "openai")
        
        # 提供商配置
        self.providers = self.config.get("providers", {})
        
        # 记忆生成配置
        self.generation_config = self.config.get("memory_generation", {})
        self.auto_scenarios = self.generation_config.get("auto_generate_scenarios", [])
        self.prompt_templates = self.generation_config.get("prompt_templates", {})
        
        # 性能配置
        self.rate_limiting = self.config.get("rate_limiting", {})
        self.cache_config = self.config.get("cache", {})
        
        # 降级策略
        self.fallback_config = self.config.get("fallback_strategy", {})
        
        # 请求缓存（简化实现）
        self._cache = {}
        
        logger.info(f"LLM客户端初始化完成，启用: {self.enabled}, 默认提供商: {self.default_provider}")
    
    def get_provider_config(self, provider: str = None) -> Dict[str, Any]:
        """
        获取提供商配置
        
        Args:
            provider: 提供商名称，None使用默认
            
        Returns:
            Dict: 提供商配置
        """
        provider = provider or self.default_provider
        return self.providers.get(provider, {})
    
    def _resolve_env_vars(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """解析环境变量引用"""
        resolved = {}
        for key, value in config.items():
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                env_var = value[2:-1]
                resolved[key] = os.environ.get(env_var, "")
            elif isinstance(value, dict):
                resolved[key] = self._resolve_env_vars(value)
            else:
                resolved[key] = value
        return resolved
    
    def _get_from_cache(self, cache_key: str) -> Optional[str]:
        """从缓存获取结果"""
        if not self.cache_config.get("enabled", True):
            return None
        
        if cache_key in self._cache:
            cached_item = self._cache[cache_key]
            ttl = self.cache_config.get("ttl_seconds", 3600)
            if time.time() - cached_item["timestamp"] < ttl:
                logger.debug(f"缓存命中: {cache_key}")
                return cached_item["response"]
        
        return None
    
    def _add_to_cache(self, cache_key: str, response: str):
        """添加到缓存"""
        if not self.cache_config.get("enabled", True):
            return
        
        max_entries = self.cache_config.get("max_entries", 1000)
        if len(self._cache) >= max_entries:
            # 移除最旧的条目
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k]["timestamp"])
            del self._cache[oldest_key]
        
        self._cache[cache_key] = {
            "response": response,
            "timestamp": time.time()
        }
    
    def make_request(self, provider: str, model: str, messages: List[Dict[str, str]], 
                    **kwargs) -> Dict[str, Any]:
        """
        向LLM API发送请求
        
        Args:
            provider: 提供商名称
            model: 模型名称
            messages: 消息列表
            **kwargs: 其他参数
            
        Returns:
            Dict: 响应数据
            
        Raises:
            ValueError: 配置不完整或请求失败
        """
        if not self.enabled:
            raise ValueError("LLM功能未启用")
        
        provider_config = self.get_provider_config(provider)
        if not provider_config:
            raise ValueError(f"LLM提供商 '{provider}' 未配置")
        
        # 解析环境变量
        resolved_config = self._resolve_env_vars(provider_config)
        
        # 检查必要配置
        required_fields = ["api_key", "base_url"]
        for field in required_fields:
            if not resolved_config.get(field):
                if self.fallback_config.get("enable_fallback", True):
                    logger.warning(f"LLM提供商 {provider} 缺少 {field}，使用降级策略")
                    raise ValueError(f"LLM提供商 {provider} 缺少 {field}")
                else:
                    raise ValueError(f"LLM提供商 {provider} 缺少必要的 {field} 配置")
        
        # 构建请求
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {resolved_config['api_key']}"
        }
        
        data = {
            "model": model,
            "messages": messages,
            "temperature": kwargs.get("temperature", resolved_config.get("temperature", 0.3)),
            "max_tokens": kwargs.get("max_tokens", resolved_config.get("max_tokens", 1000))
        }
        
        # 添加可选参数
        for key in ["top_p", "frequency_penalty", "presence_penalty", "stream"]:
            if key in kwargs:
                data[key] = kwargs[key]
            elif key in resolved_config:
                data[key] = resolved_config[key]
        
        # Ollama特殊处理
        if provider == "ollama":
            # 使用Ollama原生API端点
            api_endpoint = f"{resolved_config['base_url']}/api/chat"
            # Ollama使用不同的请求格式
            ollama_data = {
                "model": model,
                "messages": messages,
                "stream": False
            }
            # 添加可选参数
            for key in ["temperature", "max_tokens", "top_p", "frequency_penalty", "presence_penalty"]:
                if key in data:
                    ollama_data[key] = data[key]
            data = ollama_data
        else:
            # 其他提供商使用OpenAI兼容API
            api_endpoint = f"{resolved_config['base_url']}/chat/completions"

        try:
            import requests
            
            timeout = kwargs.get("timeout", resolved_config.get("timeout", 30))
            
            response = requests.post(
                f"{resolved_config['base_url']}/chat/completions",
                headers=headers,
                json=data,
                timeout=timeout
            )
            response.raise_for_status()
            result = response.json()
            
            return result
            
        except ImportError:
            logger.error("requests库未安装，无法调用LLM API")
            raise
        except Exception as e:
            logger.error(f"LLM API调用失败: {e}")
            
            # 检查是否应该重试
            retry_count = self.fallback_config.get("retry_count", 0)
            if retry_count > 0 and kwargs.get('_retry_count', 0) < retry_count:
                logger.info(f"重试LLM请求 ({kwargs.get('_retry_count', 0) + 1}/{retry_count})")
                kwargs['_retry_count'] = kwargs.get('_retry_count', 0) + 1
                time.sleep(1)  # 简单退避
                return self.make_request(provider, model, messages, **kwargs)
            
            raise
    
    def generate(self, prompt: str, provider: str = None, 
                model: str = None, **kwargs) -> str:
        """
        使用LLM生成文本
        
        Args:
            prompt: 提示词
            provider: LLM提供商，None使用默认
            model: 模型名称，None使用提供商默认
            **kwargs: 其他参数
            
        Returns:
            str: 生成的文本
            
        Raises:
            ValueError: LLM功能未启用或请求失败
        """
        if not self.enabled:
            raise ValueError("LLM功能未启用")
        
        # 检查缓存
        cache_key = f"{provider or self.default_provider}:{model or 'default'}:{hash(prompt)}"
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached
        
        provider = provider or self.default_provider
        provider_config = self.get_provider_config(provider)
        
        if not provider_config:
            raise ValueError(f"LLM提供商 '{provider}' 未配置")
        
        model = model or provider_config.get("default_model")
        if not model:
            raise ValueError(f"未指定模型且无默认模型 for provider: {provider}")
        
        messages = [{"role": "user", "content": prompt}]
        
        try:
            result = self.make_request(provider, model, messages, **kwargs)
            # 根据不同提供商解析响应
            if provider == "ollama":
                # Ollama原生API格式
                response_text = result.get("message", {}).get("content", "")
            else:
                # OpenAI兼容格式
                response_text = result["choices"][0]["message"]["content"]
            
            # 缓存结果
            self._add_to_cache(cache_key, response_text)
            
            return response_text
            
        except Exception as e:
            if self.fallback_config.get("fallback_to_basic", True):
                logger.warning(f"LLM生成失败，返回原始提示词: {e}")
                return prompt
            else:
                raise
    
    def enhance_memory(self, raw_content: str, importance: float = 0.5, 
                      tags: List[str] = None, **kwargs) -> Dict[str, Any]:
        """
        使用LLM增强记忆内容
        
        Args:
            raw_content: 原始记忆内容
            importance: 当前重要性评分
            tags: 当前标签列表
            **kwargs: 其他参数传递给generate
            
        Returns:
            Dict: 增强后的记忆信息
        """
        if not self.enabled:
            return {
                "content": raw_content,
                "importance": importance,
                "tags": tags or [],
                "metadata": {"enhanced": False}
            }
        
        # 获取或创建提示词模板
        template = self.prompt_templates.get("enhance_memory")
        if not template:
            template = """请优化以下记忆内容，使其更清晰、结构化：

原始内容: {raw_content}
当前重要性评分: {importance}
当前标签: {tags}

请以JSON格式返回包含以下字段的结果：
1. "content": 优化后的内容（更清晰、简洁）
2. "importance": 建议的重要性评分（0.0-1.0）
3. "tags": 建议的标签列表
4. "entities": 关键实体列表（人物、地点、事物等）
5. "summary": 简短摘要（可选）

请确保返回有效的JSON格式。"""
        
        tags_str = ", ".join(tags or [])
        prompt = template.format(
            raw_content=raw_content, 
            importance=importance, 
            tags=tags_str
        )
        
        try:
            response = self.generate(prompt, **kwargs)
            
            # 尝试解析JSON响应
            try:
                # 清理响应，提取JSON部分
                response = response.strip()
                
                # 查找JSON开始和结束
                json_start = response.find('{')
                json_end = response.rfind('}') + 1
                
                if json_start >= 0 and json_end > json_start:
                    json_str = response[json_start:json_end]
                    enhanced = json.loads(json_str)
                else:
                    # 如果不是有效的JSON，尝试直接解析
                    enhanced = json.loads(response)
                
                # 验证必需字段
                if "content" not in enhanced:
                    enhanced["content"] = raw_content
                
                if "importance" not in enhanced:
                    enhanced["importance"] = importance
                else:
                    # 确保重要性在有效范围内
                    enhanced["importance"] = max(0.0, min(1.0, float(enhanced["importance"])))
                
                if "tags" not in enhanced:
                    enhanced["tags"] = tags or []
                elif isinstance(enhanced["tags"], str):
                    # 如果是字符串，转换为列表
                    enhanced["tags"] = [tag.strip() for tag in enhanced["tags"].split(",") if tag.strip()]
                
                if "entities" not in enhanced:
                    enhanced["entities"] = []
                
                # 添加元数据
                enhanced["metadata"] = enhanced.get("metadata", {})
                enhanced["metadata"]["llm_enhanced"] = True
                enhanced["metadata"]["enhancement_timestamp"] = time.time()
                enhanced["metadata"]["original_content"] = raw_content
                
                return enhanced
                
            except (json.JSONDecodeError, ValueError) as e:
                # 如果不是有效的JSON，使用响应作为内容
                logger.warning(f"LLM响应不是有效的JSON，使用文本作为内容: {e}")
                return {
                    "content": response,
                    "importance": importance,
                    "tags": tags or [],
                    "entities": [],
                    "metadata": {
                        "llm_enhanced": True,
                        "enhancement_timestamp": time.time(),
                        "original_content": raw_content,
                        "json_parse_error": str(e)
                    }
                }
                
        except Exception as e:
            logger.warning(f"记忆增强失败，使用原始内容: {e}")
            return {
                "content": raw_content,
                "importance": importance,
                "tags": tags or [],
                "entities": [],
                "metadata": {
                    "enhanced": False, 
                    "error": str(e),
                    "error_timestamp": time.time()
                }
            }
    
    def generate_session_summary(self, conversation_history: List[Dict[str, str]], 
                               **kwargs) -> str:
        """
        生成会话摘要
        
        Args:
            conversation_history: 对话历史
            **kwargs: 其他参数
            
        Returns:
            str: 会话摘要
        """
        if not self.enabled:
            return "LLM功能未启用，无法生成会话摘要"
        
        template = self.prompt_templates.get("session_summary")
        if not template:
            template = """请基于以下对话历史生成一个简洁的会话摘要：

对话历史:
{conversation_history}

请提取：
1. 主要讨论的主题
2. 用户表达的重要观点或偏好
3. 需要记住的关键信息
4. 任何待办事项或后续行动

摘要应该简洁、有条理，便于未来检索。"""
        
        # 格式化对话历史
        formatted_history = []
        for item in conversation_history:
            role = item.get("role", "unknown")
            content = item.get("content", "")
            formatted_history.append(f"{role}: {content}")
        
        history_text = "\n".join(formatted_history)
        prompt = template.format(conversation_history=history_text)
        
        try:
            return self.generate(prompt, **kwargs)
        except Exception as e:
            logger.warning(f"生成会话摘要失败: {e}")
            return "会话摘要生成失败"
    
    def should_auto_enhance(self, importance: float, content: str) -> bool:
        """
        判断是否应该自动增强记忆
        
        Args:
            importance: 记忆重要性
            content: 记忆内容
            
        Returns:
            bool: 是否应该自动增强
        """
        if not self.enabled:
            return False
        
        # 检查自动增强场景
        scenarios = self.auto_scenarios
        
        # 高重要性内容
        if importance >= 0.7 and "important_content" in scenarios:
            return True
        
        # 包含偏好关键词
        preference_keywords = ["喜欢", "不喜欢", "偏好", "习惯", "经常", "总是", "从不"]
        if any(keyword in content for keyword in preference_keywords) and "user_preference" in scenarios:
            return True
        
        # 其他判断条件可以在这里添加
        
        return False


# 使用示例
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # 测试配置
    test_config = {
        "enabled": True,
        "default_provider": "openai",
        "providers": {
            "openai": {
                "api_key": "${OPENAI_API_KEY}",
                "base_url": "https://api.openai.com/v1",
                "default_model": "gpt-3.5-turbo",
                "temperature": 0.3,
                "max_tokens": 500
            }
        },
        "memory_generation": {
            "auto_generate_scenarios": ["important_content", "user_preference"]
        }
    }
    
    client = LLMClient(test_config)
    print(f"LLM客户端初始化: 启用={client.enabled}")
    
    if client.enabled:
        # 测试记忆增强
        test_content = "用户喜欢喝黑咖啡，每天早上都要喝一杯"
        enhanced = client.enhance_memory(test_content, importance=0.8, tags=["偏好", "饮食"])
        print(f"记忆增强测试:")
        print(f"  原始内容: {test_content}")
        print(f"  增强内容: {enhanced.get('content', 'N/A')[:50]}...")
        print(f"  建议重要性: {enhanced.get('importance', 'N/A')}")
        print(f"  建议标签: {enhanced.get('tags', [])}")
    
    print("LLM客户端测试完成")
