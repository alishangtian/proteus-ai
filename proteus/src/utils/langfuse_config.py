"""Langfuse 动态配置管理模块"""

import os
import json
import logging
import threading
from typing import Dict, Any, Optional, Callable, Union
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ObserveConfig:
    """观察配置类"""

    name: Optional[str] = None
    capture_input: bool = True
    capture_output: bool = True
    as_type: Optional[str] = None
    # 以下字段用于存储额外信息，但不会传递给 Langfuse observe 装饰器
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: list = field(default_factory=list)
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    version: Optional[str] = None
    release: Optional[str] = None

    def to_langfuse_dict(self) -> Dict[str, Any]:
        """转换为 Langfuse observe 装饰器支持的参数字典"""
        result = {}
        # 只包含 Langfuse observe 装饰器支持的参数
        langfuse_supported_params = {
            "name",
            "capture_input",
            "capture_output",
            "as_type",
        }

        for key, value in self.__dict__.items():
            if key in langfuse_supported_params and value is not None:
                # 特殊处理 as_type，确保只有 "generation" 值才传递
                if key == "as_type" and value != "generation":
                    continue
                result[key] = value
        return result

    def to_dict(self) -> Dict[str, Any]:
        """转换为完整字典格式（包含所有字段）"""
        result = {}
        for key, value in self.__dict__.items():
            if value is not None:
                if key == "metadata" and not value:
                    continue
                if key == "tags" and not value:
                    continue
                result[key] = value
        return result


class DynamicFieldResolver:
    """动态字段解析器"""

    def __init__(self):
        self._resolvers: Dict[str, Callable] = {
            "timestamp": lambda: datetime.now().isoformat(),
            "env": lambda key: os.getenv(key, ""),
            "random_id": lambda: f"id_{datetime.now().timestamp()}",
            "uuid": lambda: __import__("uuid").uuid4().hex[:8],
            "date": lambda: datetime.now().strftime("%Y-%m-%d"),
            "time": lambda: datetime.now().strftime("%H:%M:%S"),
            "datetime": lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        # 表达式缓存，提高性能
        self._cache: Dict[str, str] = {}
        self._cache_enabled = True

    def register_resolver(self, name: str, resolver: Callable):
        """注册自定义解析器"""
        self._resolvers[name] = resolver
        # 清除缓存，因为解析器发生了变化
        self._cache.clear()

    def enable_cache(self, enabled: bool = True):
        """启用或禁用表达式缓存"""
        self._cache_enabled = enabled
        if not enabled:
            self._cache.clear()

    def clear_cache(self):
        """清除表达式缓存"""
        self._cache.clear()

    def resolve(self, template: str, context: Dict[str, Any] = None) -> str:
        """解析模板字符串中的动态字段

        支持的模板格式：
        - ${timestamp} - 当前时间戳
        - ${env:VAR_NAME} - 环境变量
        - ${context:key} - 上下文变量
        - ${context.key} - 上下文变量（点号语法）
        - ${random_id} - 随机ID
        - ${uuid} - UUID
        - ${date} - 当前日期
        - ${time} - 当前时间
        - ${datetime} - 当前日期时间
        - 支持多个表达式组合，如：${context.query}-${context.chat_id}
        """
        if not template or not isinstance(template, str):
            return str(template) if template is not None else ""

        context = context or {}

        # 生成缓存键（包含模板和上下文的哈希）
        cache_key = None
        if self._cache_enabled:
            # 只对不包含时间相关表达式的模板使用缓存
            if not any(
                time_expr in template
                for time_expr in [
                    "timestamp",
                    "date",
                    "time",
                    "datetime",
                    "random_id",
                    "uuid",
                ]
            ):
                cache_key = f"{template}:{hash(str(sorted(context.items())))}"
                if cache_key in self._cache:
                    return self._cache[cache_key]

        result = template

        # 解析 ${...} 格式的模板
        import re

        pattern = r"\$\{([^}]+)\}"

        def replace_func(match):
            expr = match.group(1).strip()

            try:
                # 处理带冒号的表达式（如 env:VAR_NAME）
                if ":" in expr:
                    resolver_name, param = expr.split(":", 1)
                    resolver_name = resolver_name.strip()
                    param = param.strip()

                    if resolver_name == "env":
                        return os.getenv(param, "")
                    elif resolver_name == "context":
                        return str(context.get(param, ""))
                    elif resolver_name in self._resolvers:
                        try:
                            return str(self._resolvers[resolver_name](param))
                        except Exception as e:
                            logger.warning(f"解析器 '{resolver_name}' 执行失败: {e}")
                            return ""

                # 处理点号语法（如 context.key）
                elif "." in expr:
                    parts = expr.split(".", 1)
                    if len(parts) == 2:
                        namespace, key = parts
                        namespace = namespace.strip()
                        key = key.strip()

                        if namespace == "context":
                            # 支持嵌套访问，如 context.user.name
                            value = context
                            for k in key.split("."):
                                if isinstance(value, dict) and k in value:
                                    value = value[k]
                                else:
                                    return ""
                            return str(value)
                        elif namespace == "env":
                            return os.getenv(key, "")

                # 处理简单表达式
                else:
                    # 首先检查是否是注册的解析器
                    if expr in self._resolvers:
                        try:
                            return str(self._resolvers[expr]())
                        except Exception as e:
                            logger.warning(f"解析器 '{expr}' 执行失败: {e}")
                            return ""
                    # 然后检查上下文
                    elif expr in context:
                        return str(context[expr])
                    # 最后检查环境变量
                    elif expr.isupper():  # 约定：全大写的被视为环境变量
                        return os.getenv(expr, "")

            except Exception as e:
                logger.warning(f"解析表达式 '{expr}' 时发生错误: {e}")

            # 如果无法解析，返回空字符串而不是原始表达式
            logger.debug(f"无法解析表达式: {expr}")
            return ""

        result = re.sub(pattern, replace_func, result)

        # 缓存结果
        if cache_key and self._cache_enabled:
            self._cache[cache_key] = result

        return result

    def validate_template(self, template: str) -> tuple[bool, list[str]]:
        """验证模板字符串的有效性

        Returns:
            tuple: (是否有效, 错误信息列表)
        """
        if not template or not isinstance(template, str):
            return True, []

        import re

        errors = []
        # 修改正则表达式以捕获空表达式
        pattern = r"\$\{([^}]*)\}"

        matches = re.findall(pattern, template)
        for expr in matches:
            expr = expr.strip()

            # 检查表达式格式
            if not expr:
                errors.append("发现空表达式")
                continue

            # 检查冒号语法
            if ":" in expr:
                parts = expr.split(":", 1)
                if len(parts) != 2:
                    errors.append(f"无效的冒号语法: {expr}")
                    continue

                resolver_name, param = parts
                resolver_name = resolver_name.strip()
                param = param.strip()

                if not resolver_name:
                    errors.append(f"解析器名称为空: {expr}")
                if not param:
                    errors.append(f"参数为空: {expr}")

                # 检查已知的解析器
                if (
                    resolver_name not in ["env", "context"]
                    and resolver_name not in self._resolvers
                ):
                    errors.append(f"未知的解析器: {resolver_name}")

            # 检查点号语法
            elif "." in expr:
                parts = expr.split(".", 1)
                if len(parts) != 2:
                    errors.append(f"无效的点号语法: {expr}")
                    continue

                namespace, key = parts
                if not namespace.strip() or not key.strip():
                    errors.append(f"命名空间或键为空: {expr}")

                if namespace.strip() not in ["context", "env"]:
                    errors.append(f"未知的命名空间: {namespace}")

            # 检查简单表达式
            else:
                if expr not in self._resolvers:
                    # 这不是错误，可能是上下文变量或环境变量
                    pass

        return len(errors) == 0, errors

    def get_template_variables(self, template: str) -> list[str]:
        """提取模板中的所有变量

        Returns:
            list: 变量名列表
        """
        if not template or not isinstance(template, str):
            return []

        import re

        variables = []
        pattern = r"\$\{([^}]+)\}"

        matches = re.findall(pattern, template)
        for expr in matches:
            expr = expr.strip()
            variables.append(expr)

        return variables


class LangfuseConfigManager:
    """Langfuse 配置管理器
    
    这是一个单例模式的配置管理器，用于管理 Langfuse 观察配置。
    
    特性：
    - 自动查找默认配置文件
    - 支持动态字段解析
    - 配置合并和验证
    - 单例模式确保全局唯一实例
    
    默认配置文件查找顺序：
    1. 当前目录的同级目录中的 conf/langfuse_config.json
    2. 上级目录的同级目录中的 conf/langfuse_config.json
    3. 当前目录中的 conf/langfuse_config.json
    4. 当前目录中的子目录 */conf/langfuse_config.json (如 proteus/conf/)
    5. 上级目录中的 conf/langfuse_config.json
    
    如果未找到配置文件，将使用内置的默认配置。
    """

    _instance: Optional["LangfuseConfigManager"] = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return

        self._initialized = True
        self._configs: Dict[str, ObserveConfig] = {}
        self._global_config = ObserveConfig()
        self._field_resolver = DynamicFieldResolver()
        self._config_file_path: Optional[Path] = None
        self._auto_reload = False
        self._file_watcher_thread = None

        # 加载默认配置
        self.load_config_from_file()

    def _load_default_config(self):
        """加载默认配置"""
        # 设置全局默认配置
        self._global_config = ObserveConfig(
            capture_input=True,
            capture_output=True,
            metadata={
                "service": "proteus-ai",
                "version": os.getenv("APP_VERSION", "1.0.0"),
                "environment": os.getenv("ENVIRONMENT", "development"),
            },
            tags=["proteus", "ai-agent"],
        )

        # 设置特定函数的配置
        self._configs.update(
            {
                "chat_agent_run": ObserveConfig(
                    name="chat-agent-execution",
                    metadata={
                        "component": "chat_agent",
                        "operation": "run",
                        "timestamp": "${timestamp}",
                    },
                    tags=["chat", "agent", "execution"],
                ),
                "load_tools_with_tracking": ObserveConfig(
                    name="tool-loading",
                    metadata={
                        "component": "tool_manager",
                        "operation": "load",
                    },
                    tags=["tools", "loading"],
                ),
                "execute_tools": ObserveConfig(
                    name="tool-execution",
                    metadata={
                        "component": "tool_executor",
                        "operation": "execute",
                    },
                    tags=["tools", "execution"],
                ),
                "call_llm_api_with_tools_stream": ObserveConfig(
                    name="llm-api-call",
                    metadata={
                        "component": "llm_api",
                        "operation": "stream_call",
                        "model": "${context:model_name}",
                    },
                    tags=["llm", "api", "stream"],
                ),
            }
        )

    def _find_default_config_path(self) -> Optional[Path]:
        """查找默认配置文件路径
        
        查找顺序：
        1. 当前目录的同级目录中的 conf/langfuse_config.json
        2. 上级目录的同级目录中的 conf/langfuse_config.json
        3. 当前目录中的 conf/langfuse_config.json
        4. 当前目录中的子目录 */conf/langfuse_config.json (如 proteus/conf/)
        5. 上级目录中的 conf/langfuse_config.json
        
        Returns:
            找到的配置文件路径，如果未找到则返回 None
        """
        current_dir = Path.cwd()
        config_filename = "langfuse_config.json"
        
        # 候选路径列表
        candidate_paths = []
        
        # 1. 当前目录的同级目录中的 conf/langfuse_config.json
        if current_dir.parent.exists():
            for sibling in current_dir.parent.iterdir():
                if sibling.is_dir() and sibling.name == "conf":
                    candidate_paths.append(sibling / config_filename)
        
        # 2. 上级目录的同级目录中的 conf/langfuse_config.json
        if current_dir.parent.parent.exists():
            for sibling in current_dir.parent.parent.iterdir():
                if sibling.is_dir() and sibling.name == "conf":
                    candidate_paths.append(sibling / config_filename)
        
        # 3. 当前目录中的 conf/langfuse_config.json
        candidate_paths.append(current_dir / "conf" / config_filename)
        
        # 4. 当前目录中的子目录 */conf/langfuse_config.json (如 proteus/conf/)
        try:
            for subdir in current_dir.iterdir():
                if subdir.is_dir():
                    conf_path = subdir / "conf" / config_filename
                    if conf_path.exists():
                        candidate_paths.append(conf_path)
        except (PermissionError, OSError):
            # 忽略权限错误或其他文件系统错误
            pass
        
        # 5. 上级目录中的 conf/langfuse_config.json
        if current_dir.parent.exists():
            candidate_paths.append(current_dir.parent / "conf" / config_filename)
        
        # 查找第一个存在的配置文件
        for path in candidate_paths:
            if path.exists() and path.is_file():
                logger.info(f"找到默认配置文件: {path}")
                return path
        
        logger.warning("未找到默认配置文件，将使用内置默认配置")
        return None

    def load_config_from_file(
        self, config_path: Union[str, Path, None] = None, auto_reload: bool = False
    ):
        """从文件加载配置

        Args:
            config_path: 配置文件路径，如果为 None 则自动查找默认配置文件
            auto_reload: 是否自动重新加载配置文件
        """
        if config_path is None:
            config_path = self._find_default_config_path()
            if config_path is None:
                logger.info("未找到配置文件，使用内置默认配置")
                self._load_default_config()
                return
        
        config_path = Path(config_path)
        if not config_path.exists():
            logger.warning(f"配置文件不存在: {config_path}，使用内置默认配置")
            self._load_default_config()
            return

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)

            # 预处理配置数据，解析静态表达式
            config_data = self._preprocess_config_data(config_data)

            # 加载全局配置
            if "global" in config_data:
                global_data = config_data["global"]
                self._global_config = ObserveConfig(**global_data)

            # 加载函数特定配置
            if "functions" in config_data:
                for func_name, func_config in config_data["functions"].items():
                    self._configs[func_name] = ObserveConfig(**func_config)

            self._config_file_path = config_path
            self._auto_reload = auto_reload

            if auto_reload:
                self._start_file_watcher()

            logger.info(f"成功加载 Langfuse 配置: {config_path}")

        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")

    def save_config_to_file(self, config_path: Union[str, Path]):
        """保存配置到文件"""
        config_path = Path(config_path)

        config_data = {
            "global": self._global_config.__dict__,
            "functions": {
                name: config.__dict__ for name, config in self._configs.items()
            },
        }

        try:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)

            logger.info(f"配置已保存到: {config_path}")

        except Exception as e:
            logger.error(f"保存配置文件失败: {e}")

    def get_config(
        self, function_name: str, context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """获取函数的观察配置（仅返回 Langfuse 支持的参数）

        Args:
            function_name: 函数名称
            context: 上下文信息，用于动态字段解析

        Returns:
            解析后的 Langfuse 支持的配置字典
        """
        # 获取函数特定配置，如果没有则使用全局配置
        func_config = self._configs.get(function_name, self._global_config)

        # 合并全局配置和函数特定配置
        merged_config = ObserveConfig()

        # 先应用全局配置
        for key, value in self._global_config.__dict__.items():
            if value is not None:
                setattr(merged_config, key, value)

        # 再应用函数特定配置（只更新不存在的配置项）
        for key, value in func_config.__dict__.items():
            if value is not None:
                current_value = getattr(merged_config, key, None)

                if key == "metadata":
                    # 合并 metadata，只添加不存在的键
                    merged_metadata = getattr(merged_config, "metadata", {}).copy()
                    for meta_key, meta_value in value.items():
                        if meta_key not in merged_metadata:
                            merged_metadata[meta_key] = meta_value
                    setattr(merged_config, key, merged_metadata)
                elif key == "tags":
                    # 合并 tags，只添加不存在的标签
                    merged_tags = list(getattr(merged_config, "tags", []))
                    for tag in value:
                        if tag not in merged_tags:
                            merged_tags.append(tag)
                    setattr(merged_config, key, merged_tags)
                else:
                    # 只在当前值为 None 或使用默认值时才更新
                    if current_value is None or self._is_default_value(
                        key, current_value
                    ):
                        setattr(merged_config, key, value)

        # 解析动态字段
        resolved_config = self._resolve_dynamic_fields(merged_config, context)

        # 返回 Langfuse 支持的参数
        return resolved_config.to_langfuse_dict()

    def get_full_config(
        self, function_name: str, context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """获取函数的完整观察配置（包含所有字段）

        Args:
            function_name: 函数名称
            context: 上下文信息，用于动态字段解析

        Returns:
            解析后的完整配置字典
        """
        # 获取函数特定配置，如果没有则使用全局配置
        func_config = self._configs.get(function_name, self._global_config)

        # 合并全局配置和函数特定配置
        merged_config = ObserveConfig()

        # 先应用全局配置
        for key, value in self._global_config.__dict__.items():
            if value is not None:
                setattr(merged_config, key, value)

        # 再应用函数特定配置（只更新不存在的配置项）
        for key, value in func_config.__dict__.items():
            if value is not None:
                current_value = getattr(merged_config, key, None)

                if key == "metadata":
                    # 合并 metadata，只添加不存在的键
                    merged_metadata = getattr(merged_config, "metadata", {}).copy()
                    for meta_key, meta_value in value.items():
                        if meta_key not in merged_metadata:
                            merged_metadata[meta_key] = meta_value
                    setattr(merged_config, key, merged_metadata)
                elif key == "tags":
                    # 合并 tags，只添加不存在的标签
                    merged_tags = list(getattr(merged_config, "tags", []))
                    for tag in value:
                        if tag not in merged_tags:
                            merged_tags.append(tag)
                    setattr(merged_config, key, merged_tags)
                else:
                    # 只在当前值为 None 或使用默认值时才更新
                    if current_value is None or self._is_default_value(
                        key, current_value
                    ):
                        setattr(merged_config, key, value)

        # 解析动态字段
        resolved_config = self._resolve_dynamic_fields(merged_config, context)

        # 返回完整配置
        return resolved_config.to_dict()

    def _resolve_dynamic_fields(
        self, config: ObserveConfig, context: Dict[str, Any] = None
    ) -> ObserveConfig:
        """解析配置中的动态字段"""
        resolved_config = ObserveConfig()
        context = context or {}

        for key, value in config.__dict__.items():
            if isinstance(value, str):
                resolved_value = self._field_resolver.resolve(value, context)
                setattr(resolved_config, key, resolved_value)
            elif isinstance(value, dict):
                resolved_dict = {}
                for k, v in value.items():
                    if isinstance(v, str):
                        resolved_dict[k] = self._field_resolver.resolve(v, context)
                    else:
                        resolved_dict[k] = v
                setattr(resolved_config, key, resolved_dict)
            else:
                setattr(resolved_config, key, value)

        return resolved_config

    def _is_default_value(self, key: str, value: Any) -> bool:
        """检查值是否为默认值

        Args:
            key: 配置键名
            value: 当前值

        Returns:
            如果是默认值返回 True，否则返回 False
        """
        # 获取 ObserveConfig 的默认值
        default_config = ObserveConfig()
        default_value = getattr(default_config, key, None)

        # 对于列表和字典类型，检查是否为空
        if isinstance(value, list) and not value:
            return True
        if isinstance(value, dict) and not value:
            return True

        # 比较是否与默认值相同
        return value == default_value

    def update_config(
        self, function_name: str, config: Union[Dict[str, Any], ObserveConfig]
    ):
        """更新函数配置"""
        if isinstance(config, dict):
            config = ObserveConfig(**config)

        self._configs[function_name] = config
        logger.info(f"已更新函数 {function_name} 的配置")

    def update_global_config(self, config: Union[Dict[str, Any], ObserveConfig]):
        """更新全局配置"""
        if isinstance(config, dict):
            config = ObserveConfig(**config)

        self._global_config = config
        logger.info("已更新全局配置")

    def register_field_resolver(self, name: str, resolver: Callable):
        """注册自定义字段解析器"""
        self._field_resolver.register_resolver(name, resolver)
        logger.info(f"已注册字段解析器: {name}")

    def _preprocess_config_data(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """预处理配置数据，解析静态表达式（不依赖运行时上下文的表达式）"""

        def process_value(value):
            if isinstance(value, str):
                # 只解析不依赖上下文的静态表达式
                if "${" in value and not ("context." in value or "context:" in value):
                    try:
                        return self._field_resolver.resolve(value, {})
                    except Exception as e:
                        logger.warning(f"预处理表达式失败: {value}, 错误: {e}")
                        return value
                return value
            elif isinstance(value, dict):
                return {k: process_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [process_value(item) for item in value]
            else:
                return value

        return process_value(config_data)

    def reload_config_from_file(self):
        """重新加载配置文件"""
        if self._config_file_path and self._config_file_path.exists():
            logger.info(f"重新加载配置文件: {self._config_file_path}")
            self.load_config_from_file(self._config_file_path, self._auto_reload)
        else:
            logger.warning("配置文件路径无效，无法重新加载")

    def validate_config(
        self, config_data: Dict[str, Any] = None
    ) -> tuple[bool, list[str]]:
        """验证配置的有效性

        Args:
            config_data: 要验证的配置数据，如果为 None 则验证当前配置

        Returns:
            tuple: (是否有效, 错误信息列表)
        """
        errors = []

        if config_data is None:
            # 验证当前配置
            configs_to_validate = {"global": self._global_config, **self._configs}
        else:
            # 验证提供的配置数据
            configs_to_validate = {}
            if "global" in config_data:
                try:
                    configs_to_validate["global"] = ObserveConfig(
                        **config_data["global"]
                    )
                except Exception as e:
                    errors.append(f"全局配置无效: {e}")

            if "functions" in config_data:
                for func_name, func_config in config_data["functions"].items():
                    try:
                        configs_to_validate[func_name] = ObserveConfig(**func_config)
                    except Exception as e:
                        errors.append(f"函数 '{func_name}' 配置无效: {e}")

        # 验证每个配置中的模板
        for config_name, config_obj in configs_to_validate.items():
            if hasattr(config_obj, "name") and config_obj.name:
                is_valid, template_errors = self._field_resolver.validate_template(
                    config_obj.name
                )
                if not is_valid:
                    for error in template_errors:
                        errors.append(f"配置 '{config_name}' 的名称模板错误: {error}")

        return len(errors) == 0, errors

    def get_config_status(self) -> Dict[str, Any]:
        """获取配置管理器状态信息"""
        return {
            "config_file_path": (
                str(self._config_file_path) if self._config_file_path else None
            ),
            "auto_reload": self._auto_reload,
            "global_config": self._global_config.to_dict(),
            "function_configs": {
                name: config.to_dict() for name, config in self._configs.items()
            },
            "resolver_cache_enabled": self._field_resolver._cache_enabled,
            "resolver_cache_size": len(self._field_resolver._cache),
            "registered_resolvers": list(self._field_resolver._resolvers.keys()),
        }

    def clear_all_caches(self):
        """清除所有缓存"""
        self._field_resolver.clear_cache()
        logger.info("已清除所有缓存")

    def _start_file_watcher(self):
        """启动文件监控（简单实现）"""
        # 这里可以实现文件变化监控，重新加载配置
        # 为了简化，暂时不实现
        # 可以使用 watchdog 库来实现文件监控
        pass

    @classmethod
    def get_instance(cls) -> "LangfuseConfigManager":
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance


# 全局配置管理器实例
config_manager = LangfuseConfigManager.get_instance()
