"""
统一配置管理器 - 加载、验证和管理记忆系统配置
"""

import os
import json
import yaml
import logging
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class ConfigManager:
    """统一配置管理器"""

    # 默认配置（统一格式）
    DEFAULT_CONFIG = {
        # 记忆系统配置
        "memory": {
            # 短期记忆配置
            "short_term": {
                "max_items": 20,
                "persistence": "session",  # session|file
                "auto_summary": True,
                "summary_interval": 10,
            },
            # 中期记忆配置
            "medium_term": {
                "retention_days": 30,
                "summary_interval": 10,
                "compression_enabled": True,
                "storage_format": "jsonl",  # jsonl|json
                "daily_files": True,
            },
            # 长期记忆配置
            "long_term": {
                "database_path": "/app/data/memory/long/memory.db",
                "use_chroma": True,
                "similarity_threshold": 0.7,
                "auto_backup": True,
                "backup_interval_days": 7,
            },
            # 记忆巩固配置
            "consolidation": {
                "enabled": True,
                "interval_hours": 24,
                "short_to_medium_threshold": 0.3,
                "medium_to_long_threshold": 0.7,
                "batch_size": 100,
            },
            # 检索配置
            "retrieval": {
                "default_limit": 10,
                "fusion_strategy": "weighted",  # weighted|hierarchical
                "short_term_weight": 1.2,
                "medium_term_weight": 1.0,
                "long_term_weight": 0.8,
                "enable_semantic_search": True,
            },
            # 清理配置
            "cleanup": {
                "enabled": True,
                "schedule": "daily",  # daily|weekly
                "low_importance_threshold": 0.2,
                "max_age_days": 365,
            },
        },

        # Chroma配置
        "chroma": {
            "persist_directory": "/app/data/memory/chroma",
            "collection_name": "memories",
            "embedding_model": "all-MiniLM-L6-v2",  # 或 "bge-m3", "text-embedding-3-small"
            "create_if_missing": True,
        },

        "embedding": {
            "enabled": True,
            "default_provider": "ollama",  # 只支持ollama
            "providers": {
                "ollama": {
                    "base_url": "http://host.docker.internal:11434",
                    "default_model": "bge-m3",
                    "timeout": 30,
                    "batch_size": 10
                }
            }
        },

        # LLM配置（统一管理）
        "llm": {
            "enabled": True,
            "default_provider": "openai",  # openai|azure|anthropic|cohere|local
            "providers": {
                "openai": {
                    "api_key": "${OPENAI_API_KEY}",
                    "base_url": "https://api.openai.com/v1",
                    "default_model": "gpt-3.5-turbo",
                    "available_models": ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo"],
                    "temperature": 0.3,
                    "max_tokens": 1000,
                    "timeout": 30,
                },
                "azure": {
                    "api_key": "${AZURE_OPENAI_API_KEY}",
                    "api_version": "2024-02-01",
                    "azure_endpoint": "https://your-resource.openai.azure.com/",
                    "deployment_name": "gpt-35-turbo",
                    "temperature": 0.3,
                    "max_tokens": 1000,
                },
                "anthropic": {
                    "api_key": "${ANTHROPIC_API_KEY}",
                    "default_model": "claude-3-haiku-20240307",
                    "available_models": ["claude-3-haiku-20240307", "claude-3-sonnet-20240229", "claude-3-opus-20240229"],
                    "max_tokens": 1000,
                    "temperature": 0.3,
                },
                "local": {
                    "base_url": "http://localhost:8080/v1",
                    "default_model": "local-model",
                    "api_key": "sk-no-key-required",
                    "temperature": 0.3,
                    "max_tokens": 1000,
                    "timeout": 60,
                },
            },
            # 记忆生成配置
            "memory_generation": {
                "auto_generate_scenarios": [
                    "session_summary",
                    "important_content",
                    "user_preference",
                    "contradiction",
                ],
                "strategy": "enhanced",  # basic|enhanced|structured
                "max_generation_length": 500,
                "include_metadata": True,
                "prompt_templates": {
                    "session_summary": "请基于以下对话历史生成一个简洁的会话摘要...",
                    "extract_preferences": "请从以下文本中提取用户的偏好和习惯...",
                    "enhance_memory": "请将以下信息转化为更结构化和易于记忆的形式...",
                },
            },
            # 成本与性能控制
            "rate_limiting": {
                "enabled": True,
                "requests_per_minute": 60,
                "max_tokens_per_minute": 100000,
            },
            # 缓存配置
            "cache": {
                "enabled": True,
                "ttl_seconds": 3600,
                "max_entries": 1000,
            },
            # 降级策略
            "fallback_strategy": {
                "enable_fallback": True,
                "fallback_to_basic": True,
                "log_errors": True,
                "retry_count": 2,
            },
        },

        # 性能配置
        "performance": {
            "cache_enabled": True,
            "cache_size_mb": 100,
            "max_concurrent_queries": 10,
            "query_timeout_seconds": 30,
            "enable_query_optimization": True,
        },

        # 日志配置
        "logging": {
            "level": "INFO",  # DEBUG|INFO|WARNING|ERROR
            "file_enabled": True,
            "file_path": "/app/data/memory/logs/memory_system.log",
            "max_file_size_mb": 100,
            "backup_count": 5,
        },

        # 备份配置
        "backup": {
            "enabled": True,
            "schedule": "0 2 * * *",  # 每天凌晨2点
            "retention_days": 30,
            "compress_backups": True,
            "backup_location": "/app/data/memory/backups",
        },
    }

    @staticmethod
    def load(config_path: Optional[str] = None) -> Dict[str, Any]:
        """
        加载配置

        Args:
            config_path: 配置文件路径，如果为None则使用默认配置

        Returns:
            Dict: 合并后的配置
        """
        # 从默认配置开始
        config = ConfigManager._deep_copy(ConfigManager.DEFAULT_CONFIG)

        # 尝试从文件加载配置
        file_config = ConfigManager._load_from_file(config_path)
        if file_config:
            ConfigManager._deep_merge(config, file_config)

        # 应用环境变量覆盖
        ConfigManager._apply_env_overrides(config)

        # 验证配置
        ConfigManager._validate_config(config)

        logger.info(f"配置加载完成，配置文件: {config_path or '默认配置'}")
        return config

    @staticmethod
    def _load_from_file(config_path: Optional[str]) -> Optional[Dict[str, Any]]:
        """从文件加载配置"""
        if not config_path:
            # 尝试默认路径
            default_paths = [
                "/app/data/memory/config.yaml",
                "/app/data/memory/config.json",
                "./config.yaml",
                "./config.json",
            ]

            for path in default_paths:
                if os.path.exists(path):
                    config_path = path
                    break

        if not config_path or not os.path.exists(config_path):
            return None

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                if config_path.endswith('.json'):
                    return json.load(f)
                elif config_path.endswith('.yaml') or config_path.endswith('.yml'):
                    return yaml.safe_load(f)
                else:
                    # 尝试自动检测格式
                    content = f.read()
                    try:
                        return json.loads(content)
                    except:
                        try:
                            return yaml.safe_load(content)
                        except:
                            logger.warning(f"无法解析配置文件: {config_path}")
                            return None
        except Exception as e:
            logger.warning(f"加载配置文件失败: {config_path} - {e}")
            return None

    @staticmethod
    def _apply_env_overrides(config: Dict[str, Any], prefix: str = "MEMORY_"):
        """应用环境变量覆盖"""
        import os

        def _apply_env_to_dict(env_dict, config_dict, current_key=""):
            for key, value in env_dict.items():
                full_key = f"{current_key}_{key}" if current_key else key
                if isinstance(value, dict):
                    _apply_env_to_dict(value, config_dict.get(key, {}), full_key)
                elif full_key in os.environ:
                    # 尝试转换类型
                    env_value = os.environ[full_key]
                    if isinstance(value, bool):
                        config_dict[key] = env_value.lower() in ("true", "1", "yes")
                    elif isinstance(value, int):
                        config_dict[key] = int(env_value)
                    elif isinstance(value, float):
                        config_dict[key] = float(env_value)
                    else:
                        config_dict[key] = env_value

        # 简化实现：只处理顶级配置项
        for key in config.keys():
            env_key = f"{prefix}{key.upper()}"
            if env_key in os.environ:
                # 这里简化处理，实际应该解析JSON/YAML
                logger.debug(f"环境变量覆盖: {env_key}")

    @staticmethod
    def _deep_merge(target: Dict[str, Any], source: Dict[str, Any]):
        """深度合并字典"""
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                ConfigManager._deep_merge(target[key], value)
            else:
                target[key] = value

    @staticmethod
    def _deep_copy(obj: Dict[str, Any]) -> Dict[str, Any]:
        """深度复制字典"""
        import copy
        return copy.deepcopy(obj)

    @staticmethod
    def _validate_config(config: Dict[str, Any]):
        """验证配置"""
        errors = []

        # 验证记忆配置
        memory_config = config.get("memory", {})

        # 验证短期记忆
        short_term = memory_config.get("short_term", {})
        if short_term.get("max_items", 0) <= 0:
            errors.append("short_term.max_items 必须大于0")

        # 验证中期记忆
        medium_term = memory_config.get("medium_term", {})
        if medium_term.get("retention_days", 0) < 0:
            errors.append("medium_term.retention_days 不能为负数")

        # 验证长期记忆
        long_term = memory_config.get("long_term", {})
        if not long_term.get("database_path"):
            errors.append("long_term.database_path 不能为空")

        # 验证嵌入配置
        embedding_config = config.get("embedding", {})
        if embedding_config.get("enabled", False):
            default_provider = embedding_config.get("default_provider", "")
            providers = embedding_config.get("providers", {})
            if default_provider and default_provider not in providers:
                errors.append(f"embedding.default_provider '{default_provider}' 不存在于 providers 中")

        # 验证LLM配置
        llm_config = config.get("llm", {})
        if llm_config.get("enabled", False):
            default_provider = llm_config.get("default_provider", "")
            providers = llm_config.get("providers", {})
            if default_provider and default_provider not in providers:
                errors.append(f"llm.default_provider '{default_provider}' 不存在于 providers 中")

        if errors:
            logger.warning(f"配置验证警告: {errors}")
            # 不抛出异常，只是记录警告

    @staticmethod
    def save(config: Dict[str, Any], config_path: str):
        """
        保存配置到文件

        Args:
            config: 配置字典
            config_path: 配置文件路径
        """
        try:
            os.makedirs(os.path.dirname(config_path), exist_ok=True)

            if config_path.endswith('.json'):
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, ensure_ascii=False, indent=2)
            else:
                # 默认保存为YAML
                with open(config_path, 'w', encoding='utf-8') as f:
                    yaml.dump(config, f, allow_unicode=True, default_flow_style=False)

            logger.info(f"配置已保存到: {config_path}")
            return True

        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            return False

    @staticmethod
    def get_with_default(config: Dict[str, Any], key_path: str, default: Any = None) -> Any:
        """
        通过点分隔的路径获取配置值

        Args:
            config: 配置字典
            key_path: 点分隔的路径，如 "memory.short_term.max_items"
            default: 默认值

        Returns:
            Any: 配置值或默认值
        """
        keys = key_path.split('.')
        current = config

        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default

        return current


# 使用示例
if __name__ == "__main__":
    # 测试配置加载
    logging.basicConfig(level=logging.INFO)

    config = ConfigManager.load()
    print("默认配置加载成功")

    # 获取特定配置值
    max_items = ConfigManager.get_with_default(config, "memory.short_term.max_items")
    print(f"短期记忆最大项数: {max_items}")

    # 保存配置示例
    ConfigManager.save(config, "/tmp/test_config.yaml")
    print("测试配置已保存")