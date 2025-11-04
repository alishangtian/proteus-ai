import os
import logging
import functools
import inspect
import sys
from typing import Optional, Any, Callable, Dict
from src.utils.langfuse_config import LangfuseConfigManager

# 配置专用的 logger，确保日志能够正常输出
logger = logging.getLogger(__name__)
if not logger.handlers:
    # 创建控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)

    # 创建格式化器
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - [%(process)d:%(threadName)s] - [%(filename)s:%(lineno)d] - %(message)s"
    )
    console_handler.setFormatter(formatter)

    # 添加处理器到 logger
    logger.addHandler(console_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = True


class NoopGeneration:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def update(self, *args, **kwargs):
        return None

    def end(self, *args, **kwargs):
        return None

    def score(self, *args, **kwargs):
        return None


class NoopSpan:
    def __init__(self, name: str = ""):
        self.name = name

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def update(self, *args, **kwargs):
        return self

    def end(self, *args, **kwargs):
        return self

    def update_trace(self, *args, **kwargs):
        return self

    def start_as_current_generation(self, *args, **kwargs):
        return NoopGeneration()

    def start_as_current_span(self, *args, **kwargs):
        return NoopSpan(kwargs.get("name", ""))


class SpanWrapper:
    """包装 Langfuse span，提供统一的接口"""

    def __init__(self, span_obj):
        self._span = span_obj
        self._is_context_manager = hasattr(span_obj, "__enter__") and hasattr(
            span_obj, "__exit__"
        )

    def __enter__(self):
        if self._is_context_manager:
            return SpanWrapper(self._span.__enter__())
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._is_context_manager:
            return self._span.__exit__(exc_type, exc_val, exc_tb)
        return False

    def update(self, *args, **kwargs):
        if hasattr(self._span, "update"):
            try:
                logger.debug(
                    f"SpanWrapper: 正在更新 span，参数: args={args}, kwargs={kwargs}"
                )
                result = self._span.update(*args, **kwargs)
                logger.debug(f"SpanWrapper: span 更新成功")
                return result
            except Exception as e:
                logger.warning(f"SpanWrapper: span 更新失败: {e}")
        else:
            logger.debug(f"SpanWrapper: span 对象没有 update 方法")
        return self

    def end(self, *args, **kwargs):
        if hasattr(self._span, "end"):
            try:
                logger.debug(
                    f"SpanWrapper: 正在结束 span，参数: args={args}, kwargs={kwargs}"
                )
                result = self._span.end(*args, **kwargs)
                logger.debug(f"SpanWrapper: span 已成功结束")
                return result
            except Exception as e:
                logger.error(f"SpanWrapper: span 结束失败: {e}")
        else:
            logger.debug(f"SpanWrapper: span 对象没有 end 方法")
        return self

    def update_trace(self, *args, **kwargs):
        if hasattr(self._span, "update_trace"):
            try:
                logger.debug(
                    f"SpanWrapper: 正在更新 trace，参数: args={args}, kwargs={kwargs}"
                )
                result = self._span.update_trace(*args, **kwargs)
                logger.debug(f"SpanWrapper: trace 更新成功")
                return result
            except Exception as e:
                logger.warning(f"SpanWrapper: trace 更新失败: {e}")
        else:
            logger.debug(f"SpanWrapper: span 对象没有 update_trace 方法")
        return self

    def start_as_current_generation(self, *args, **kwargs):
        if hasattr(self._span, "start_as_current_generation"):
            try:
                logger.debug(
                    f"SpanWrapper: 正在启动 generation，参数: args={args}, kwargs={kwargs}"
                )
                result = self._span.start_as_current_generation(*args, **kwargs)
                logger.debug(f"SpanWrapper: generation 启动成功")
                return result
            except Exception as e:
                logger.error(f"SpanWrapper: generation 启动失败: {e}")
                return NoopGeneration()
        else:
            logger.debug(
                f"SpanWrapper: span 对象没有 start_as_current_generation 方法，返回 NoopGeneration"
            )
        return NoopGeneration()

    def __getattr__(self, name):
        # 代理其他属性访问
        return getattr(self._span, name)


class LangfuseAdapter:
    """
    Adapter that wraps the real Langfuse SDK instance (if present).
    It exposes a stable small API used by the codebase:
      - span(...)
      - start_as_current_span(...)
    and delegates any other attribute access to the real instance if available.
    If the real instance doesn't provide the expected APIs, adapter returns no-op
    span/generation objects so the application won't crash.
    """

    def __init__(self, real_instance: Optional[Any]):
        self._real = real_instance

    def __getattr__(self, item):
        if self._real and hasattr(self._real, item):
            return getattr(self._real, item)
        raise AttributeError(item)

    def span(self, *args, **kwargs):
        span_name = kwargs.get("name", "unnamed_span")
        logger.debug(
            f"LangfuseAdapter: 尝试创建 span '{span_name}'，参数: args={args}, kwargs={kwargs}"
        )

        try:
            # Prefer the real span if available
            if self._real and hasattr(self._real, "span"):
                logger.debug(f"LangfuseAdapter: 使用真实 Langfuse 实例的 span 方法")
                span_obj = getattr(self._real, "span")(*args, **kwargs)
                logger.debug(f"LangfuseAdapter: 成功创建真实 span '{span_name}'")
                return SpanWrapper(span_obj)
            # Fallback: if SDK exposes start_as_current_span, use it (context manager)
            if self._real and hasattr(self._real, "start_as_current_span"):
                logger.debug(
                    f"LangfuseAdapter: 使用 start_as_current_span 方法作为备选"
                )
                span_obj = getattr(self._real, "start_as_current_span")(*args, **kwargs)
                logger.debug(
                    f"LangfuseAdapter: 成功通过 start_as_current_span 创建 span '{span_name}'"
                )
                return SpanWrapper(span_obj)
        except Exception as e:
            logger.error(f"LangfuseAdapter: 创建 Langfuse span '{span_name}' 失败: {e}")

        # Final fallback: return a no-op span to avoid attribute errors
        logger.warning(
            f"LangfuseAdapter: 返回 NoopSpan '{span_name}'，Langfuse 实例不可用"
        )
        return NoopSpan(span_name)

    def start_as_current_span(self, *args, **kwargs):
        span_name = kwargs.get("name", "unnamed_span")
        logger.debug(
            f"LangfuseAdapter: 尝试启动当前 span '{span_name}'，参数: args={args}, kwargs={kwargs}"
        )

        try:
            if self._real and hasattr(self._real, "start_as_current_span"):
                logger.debug(
                    f"LangfuseAdapter: 使用真实 Langfuse 实例的 start_as_current_span 方法"
                )
                span_obj = getattr(self._real, "start_as_current_span")(*args, **kwargs)
                logger.debug(f"LangfuseAdapter: 成功启动当前 span '{span_name}'")
                return SpanWrapper(span_obj)
        except Exception as e:
            logger.error(f"LangfuseAdapter: 启动 Langfuse span '{span_name}' 失败: {e}")

        logger.warning(
            f"LangfuseAdapter: 返回 NoopSpan '{span_name}'，Langfuse 实例不可用"
        )
        return NoopSpan(span_name)


class LangfuseWrapper:
    _instance: Optional["LangfuseWrapper"] = None
    _langfuse_instance: Optional[Any] = None
    _langfuse_enabled: bool = False
    _config_manager: Optional["LangfuseConfigManager"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LangfuseWrapper, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """初始化 LangfuseWrapper"""
        # 检查环境变量以确定是否启用 Langfuse
        self._langfuse_enabled = (
            os.getenv("LANGFUSE_ENABLED", "false").lower() == "true"
        )

        logger.debug(f"LangfuseWrapper: Langfuse 启用状态: {self._langfuse_enabled}")

        # 初始化配置管理器
        self._config_manager = None
        try:
            from .langfuse_config import config_manager

            self._config_manager = config_manager
            logger.debug("LangfuseWrapper: 配置管理器初始化成功")
        except ImportError as e:
            logger.warning(f"LangfuseWrapper: 无法导入配置管理器: {e}")
        except Exception as e:
            logger.error(f"LangfuseWrapper: 配置管理器初始化失败: {e}")

        # 初始化 Langfuse 实例
        self._langfuse_instance = None
        logger.debug("LangfuseWrapper: 开始初始化 Langfuse 实例...")

        if self._langfuse_enabled:
            try:
                logger.debug("LangfuseWrapper: 尝试导入 langfuse 库...")
                from langfuse import Langfuse

                # 检查必要的环境变量
                required_env_vars = [
                    "LANGFUSE_SECRET_KEY",
                    "LANGFUSE_PUBLIC_KEY",
                    "LANGFUSE_HOST",
                ]
                logger.debug(
                    f"LangfuseWrapper: 检查必要的环境变量: {required_env_vars}"
                )

                missing_vars = [var for var in required_env_vars if not os.getenv(var)]
                available_vars = [var for var in required_env_vars if os.getenv(var)]

                logger.debug(f"LangfuseWrapper: 可用环境变量: {available_vars}")
                if missing_vars:
                    logger.warning(
                        f"LangfuseWrapper: 缺少必要的环境变量: {missing_vars}，Langfuse 将被禁用"
                    )
                    self._langfuse_enabled = False
                    return

                logger.debug(
                    "LangfuseWrapper: 所有必要环境变量已设置，创建 Langfuse 实例..."
                )
                self._langfuse_instance = Langfuse()
                logger.debug("LangfuseWrapper: Langfuse 实例创建成功，开始认证检查...")

                # 验证认证
                if self._langfuse_instance.auth_check():
                    logger.debug("LangfuseWrapper: Langfuse 认证成功，实例可用")
                    logger.debug(
                        f"LangfuseWrapper: Langfuse 实例类型: {type(self._langfuse_instance)}"
                    )
                else:
                    logger.error("LangfuseWrapper: Langfuse 认证失败，将被禁用")
                    self._langfuse_enabled = False
                    self._langfuse_instance = None

            except ImportError as e:
                logger.warning(
                    f"LangfuseWrapper: langfuse 库未找到: {e}，Langfuse 将被禁用"
                )
                self._langfuse_enabled = False
            except Exception as e:
                logger.error(
                    f"LangfuseWrapper: 初始化 Langfuse 失败: {e}，Langfuse 将被禁用"
                )
                logger.debug(f"LangfuseWrapper: 异常详情: {type(e).__name__}: {str(e)}")
                self._langfuse_enabled = False
                self._langfuse_instance = None
        else:
            logger.debug("LangfuseWrapper: Langfuse 已通过配置禁用")

    @classmethod
    def get_instance(cls) -> "LangfuseWrapper":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_langfuse_instance(self) -> Optional[Any]:
        # 返回一个适配器对象，确保调用方可以安全使用 .span / .start_as_current_span 等接口
        if self._langfuse_instance:
            logger.debug("LangfuseWrapper: 返回真实 Langfuse 实例的适配器")
            return LangfuseAdapter(self._langfuse_instance)
        # 当未初始化真实实例时返回适配器的 no-op 实例，避免外部直接访问 None
        logger.debug("LangfuseWrapper: 返回 NoOp 适配器，Langfuse 实例不可用")
        return LangfuseAdapter(None)

    def is_enabled(self) -> bool:
        return self._langfuse_enabled

    def observe_decorator(self, *args, **kwargs) -> Callable:
        """创建观察装饰器，支持动态配置"""
        if not self._langfuse_enabled or not self._langfuse_instance:
            logger.debug(
                "LangfuseWrapper: Langfuse 未启用或实例未初始化，返回空操作装饰器"
            )
            return self._no_op_decorator

        try:
            from langfuse import observe

            # 如果没有提供参数，使用动态配置装饰器
            if not args and not kwargs:
                logger.debug("LangfuseWrapper: 使用动态配置装饰器")
                return self.dynamic_observe()

            # 否则使用传统的静态配置
            logger.debug(
                f"LangfuseWrapper: 使用静态配置装饰器，参数: args={args}, kwargs={kwargs}"
            )
            return observe(*args, **kwargs)

        except ImportError:
            logger.warning("LangfuseWrapper: langfuse.observe 未找到，返回空操作装饰器")
            return self._no_op_decorator
        except Exception as e:
            logger.error(f"LangfuseWrapper: 创建观察装饰器失败: {e}，返回空操作装饰器")
            return self._no_op_decorator

    def _build_context(
        self, func: Callable, args: tuple, kwargs: dict
    ) -> Dict[str, Any]:
        """构建函数调用上下文"""
        logger.debug(f"_build_context: 开始为函数 '{func.__name__}' 构建上下文")
        context = {}

        try:
            # 获取函数签名
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()

            logger.debug(
                f"_build_context: 函数签名绑定成功，参数数量: {len(bound_args.arguments)}"
            )

            # 提取有用的上下文信息
            for param_name, param_value in bound_args.arguments.items():
                if isinstance(param_value, (str, int, float, bool)):
                    context[param_name] = param_value
                    logger.debug(
                        f"_build_context: 添加基础类型参数 '{param_name}': {param_value}"
                    )
                elif hasattr(param_value, "__class__"):
                    type_name = param_value.__class__.__name__
                    context[f"{param_name}_type"] = type_name
                    logger.debug(
                        f"_build_context: 添加类型信息 '{param_name}_type': {type_name}"
                    )

            # 添加函数元信息
            func_meta = {
                "function_name": func.__name__,
                "module_name": func.__module__,
                "class_name": (
                    getattr(func, "__qualname__", "").split(".")[0]
                    if "." in getattr(func, "__qualname__", "")
                    else None
                ),
            }
            context.update(func_meta)
            logger.debug(f"_build_context: 添加函数元信息: {func_meta}")

            logger.debug(f"_build_context: 上下文构建完成，包含 {len(context)} 个字段")

        except Exception as e:
            logger.error(f"_build_context: 构建上下文失败: {e}")
            logger.debug(f"_build_context: 异常详情: {type(e).__name__}: {str(e)}")

        return context

    def dynamic_observe(
        self,
        name: Optional[str] = None,
        capture_input: bool = True,
        capture_output: bool = True,
        **kwargs,
    ) -> Callable:
        """动态观察装饰器，支持运行时配置和动态trace名称"""

        def decorator(func: Callable) -> Callable:
            if not self._langfuse_enabled or not self._langfuse_instance:
                logger.debug(f"Langfuse 未启用，跳过装饰器应用于函数: {func.__name__}")
                return func

            try:
                from langfuse import observe
            except ImportError:
                logger.warning("langfuse.observe 导入失败，返回原函数")
                return func

            # 缓存装饰器和配置
            _cached_decorator = None
            _last_config_hash = None
            _last_resolved_name = None

            @functools.wraps(func)
            def wrapper(*args, **wrapper_kwargs):
                nonlocal _cached_decorator, _last_config_hash, _last_resolved_name

                try:
                    logger.debug(
                        f"dynamic_observe: 开始处理函数 '{func.__name__}' 的调用"
                    )

                    # 构建上下文信息
                    context = self._build_context(func, args, wrapper_kwargs)
                    logger.debug(f"dynamic_observe: 构建的上下文信息: {context}")

                    user_config = None
                    config = None

                    # 添加全局trace上下文
                    if hasattr(self, "_trace_context"):
                        context.update(self._trace_context)
                        logger.debug(
                            f"dynamic_observe: 添加全局trace上下文后: {context}"
                        )

                    # 解析动态名称（如果提供了模板）
                    resolved_name = name or func.__name__
                    if name and "${" in name:
                        logger.debug(
                            f"dynamic_observe: 检测到模板名称 '{name}'，开始解析..."
                        )
                        if self._config_manager and hasattr(
                            self._config_manager, "_field_resolver"
                        ):
                            logger.debug("dynamic_observe: 使用配置管理器的字段解析器")
                            resolved_name = (
                                self._config_manager._field_resolver.resolve(
                                    name, context
                                )
                            )
                        else:
                            logger.debug("dynamic_observe: 使用简单模板替换")
                            # 简单的模板替换
                            import re

                            pattern = r"\$\{([^}]+)\}"

                            def replace_func(match):
                                expr = match.group(1).strip()
                                if "." in expr:
                                    parts = expr.split(".", 1)
                                    if len(parts) == 2 and parts[0] == "context":
                                        key = parts[1]
                                        return str(context.get(key, ""))
                                elif expr in context:
                                    return str(context[expr])
                                return ""

                            resolved_name = re.sub(pattern, replace_func, name)

                        logger.debug(
                            f"dynamic_observe: 模板名称解析完成: '{name}' -> '{resolved_name}'"
                        )

                    # 获取动态配置
                    if self._config_manager:
                        logger.debug("dynamic_observe: 使用配置管理器获取动态配置")
                        # 首先尝试使用函数名获取配置
                        config = self._config_manager.get_config(func.__name__, context)

                        # 如果解析后的名称不同，也尝试获取该名称的配置
                        if resolved_name != func.__name__:
                            resolved_config = self._config_manager.get_config(
                                resolved_name, context
                            )
                            logger.debug(
                                f"获取解析后的名称的配置 resolved_config: {resolved_config}"
                            )
                            # 合并配置，优先使用解析后名称的配置
                            for key, value in resolved_config.items():
                                if value is not None:
                                    config[key] = value

                        logger.debug(
                            f"dynamic_observe: 从配置管理器获取的配置: {config}"
                        )

                        # 合并用户提供的参数（用户参数优先级最高）
                        user_config = {
                            **config,
                            **kwargs,
                        }

                        logger.debug(f"dynamic_observe: 最终使用的配置: {user_config}")
                    else:
                        user_config = {
                            "name": resolved_name,
                            "capture_input": capture_input,
                            "capture_output": capture_output,
                            **kwargs,
                        }
                        logger.debug(f"dynamic_observe: 使用默认配置: {user_config}")

                    # 计算配置哈希，检查是否需要重新创建装饰器
                    config_hash = hash(str(sorted(user_config.items())))
                    name_changed = _last_resolved_name != resolved_name

                    if (
                        _cached_decorator is None
                        or _last_config_hash != config_hash
                        or name_changed
                    ):

                        logger.debug(
                            f"dynamic_observe: 配置或名称发生变化，重新创建 observe 装饰器"
                        )
                        logger.debug(
                            f"dynamic_observe: 配置变化: {_last_config_hash != config_hash}"
                        )
                        logger.debug(
                            f"dynamic_observe: 名称变化: {name_changed} ('{_last_resolved_name}' -> '{resolved_name}')"
                        )

                        _cached_decorator = observe(**user_config)
                        _last_config_hash = config_hash
                        _last_resolved_name = resolved_name

                        logger.debug(
                            f"dynamic_observe: 为函数 '{func.__name__}' 创建新的 observe 装饰器，配置: {user_config}"
                        )
                    else:
                        logger.debug(
                            f"dynamic_observe: 使用缓存的装饰器，配置和名称均未变化"
                        )

                    # 直接调用原函数，让 observe 装饰器处理追踪
                    logger.debug(
                        f"dynamic_observe: 开始执行被装饰的函数 '{func.__name__}'"
                    )
                    result = _cached_decorator(func)(*args, **wrapper_kwargs)
                    logger.debug(f"dynamic_observe: 函数 '{func.__name__}' 执行完成")
                    return result

                except Exception as e:
                    logger.error(
                        f"dynamic_observe: 装饰器执行失败 (函数: {func.__name__}): {e}，回退到原函数"
                    )
                    logger.debug(
                        f"dynamic_observe: 异常详情: {type(e).__name__}: {str(e)}"
                    )
                    return func(*args, **wrapper_kwargs)

            return wrapper

        return decorator

    def load_config_from_file(self, config_path: str, auto_reload: bool = False):
        """从文件加载配置"""
        logger.debug(
            f"load_config_from_file: 尝试从文件加载配置: {config_path}, auto_reload={auto_reload}"
        )

        if self._config_manager:
            try:
                self._config_manager.load_config_from_file(config_path, auto_reload)
                logger.debug(f"load_config_from_file: 配置文件加载成功: {config_path}")
            except Exception as e:
                logger.error(f"load_config_from_file: 加载配置文件失败: {e}")
        else:
            logger.warning(
                "load_config_from_file: 配置管理器未初始化，无法加载配置文件"
            )

    def update_function_config(self, function_name: str, config: Dict[str, Any]):
        """更新函数配置"""
        logger.debug(
            f"update_function_config: 更新函数 '{function_name}' 的配置: {config}"
        )

        if self._config_manager:
            try:
                self._config_manager.update_config(function_name, config)
                logger.debug(
                    f"update_function_config: 函数 '{function_name}' 配置更新成功"
                )
            except Exception as e:
                logger.error(f"update_function_config: 更新函数配置失败: {e}")
        else:
            logger.warning("update_function_config: 配置管理器未初始化，无法更新配置")

    def update_global_config(self, config: Dict[str, Any]):
        """更新全局配置"""
        logger.debug(f"update_global_config: 更新全局配置: {config}")

        if self._config_manager:
            try:
                self._config_manager.update_global_config(config)
                logger.debug("update_global_config: 全局配置更新成功")
            except Exception as e:
                logger.error(f"update_global_config: 更新全局配置失败: {e}")
        else:
            logger.warning("update_global_config: 配置管理器未初始化，无法更新全局配置")

    def register_field_resolver(self, name: str, resolver: Callable):
        """注册自定义字段解析器"""
        if self._config_manager:
            self._config_manager.register_field_resolver(name, resolver)
        else:
            logger.warning("配置管理器未初始化，无法注册字段解析器")

    def _no_op_decorator(self, func: Callable) -> Callable:
        """一个什么都不做的装饰器，用于Langfuse禁用时"""
        logger.debug(f"LangfuseWrapper: 对函数 {func.__name__} 应用空操作装饰器")
        return func

    def get_status(self) -> dict:
        """获取 LangfuseWrapper 的状态信息"""
        return {
            "enabled": self._langfuse_enabled,
            "instance_initialized": self._langfuse_instance is not None,
            "config_manager_available": self._config_manager is not None,
            "environment_vars": {
                "LANGFUSE_ENABLED": os.getenv("LANGFUSE_ENABLED"),
                "LANGFUSE_SECRET_KEY": (
                    "***" if os.getenv("LANGFUSE_SECRET_KEY") else None
                ),
                "LANGFUSE_PUBLIC_KEY": (
                    "***" if os.getenv("LANGFUSE_PUBLIC_KEY") else None
                ),
                "LANGFUSE_HOST": os.getenv("LANGFUSE_HOST"),
            },
        }

    def update_trace_name(self, trace_name: str, **context_vars):
        """动态更新当前trace的名称

        Args:
            trace_name: 新的trace名称，支持模板变量
            **context_vars: 用于模板替换的上下文变量
        """
        if not self._langfuse_enabled or not self._langfuse_instance:
            logger.debug("Langfuse 未启用，跳过trace名称更新")
            return

        try:
            # 解析模板变量
            if self._config_manager and self._config_manager._field_resolver:
                resolved_name = self._config_manager._field_resolver.resolve(
                    trace_name, context_vars
                )
            else:
                # 简单的模板替换
                resolved_name = trace_name
                for key, value in context_vars.items():
                    resolved_name = resolved_name.replace(f"${{{key}}}", str(value))
                    resolved_name = resolved_name.replace(
                        f"${{context.{key}}}", str(value)
                    )

            # 更新当前trace名称
            if hasattr(self._langfuse_instance, "update_current_trace"):
                self._langfuse_instance.update_current_trace(name=resolved_name)
                logger.debug(f"已更新trace名称为: {resolved_name}")
            else:
                logger.warning("当前Langfuse版本不支持动态更新trace名称")

        except Exception as e:
            logger.warning(f"更新trace名称失败: {e}")

    def set_trace_context(self, **context_vars):
        """设置trace上下文变量，用于后续的动态名称解析

        Args:
            **context_vars: 上下文变量
        """
        logger.debug(f"set_trace_context: 设置trace上下文变量: {context_vars}")

        if not hasattr(self, "_trace_context"):
            self._trace_context = {}
            logger.debug("set_trace_context: 初始化 _trace_context 字典")

        old_context = self._trace_context.copy()
        self._trace_context.update(context_vars)

        logger.debug(f"set_trace_context: trace上下文已更新")
        logger.debug(f"set_trace_context: 更新前: {old_context}")
        logger.debug(f"set_trace_context: 更新后: {self._trace_context}")

    def get_trace_context(self) -> dict:
        """获取当前trace上下文变量"""
        return getattr(self, "_trace_context", {})

    def clear_trace_context(self):
        """清除trace上下文变量"""
        logger.debug("clear_trace_context: 开始清除trace上下文变量")

        if hasattr(self, "_trace_context"):
            old_context = self._trace_context.copy()
            self._trace_context.clear()
            logger.debug("clear_trace_context: trace上下文已清除")
            logger.debug(f"clear_trace_context: 已清除的上下文: {old_context}")
        else:
            logger.debug("clear_trace_context: 没有找到 _trace_context，无需清除")

    def validate_template(self, template: str) -> tuple[bool, list[str]]:
        """验证模板字符串的有效性

        Args:
            template: 要验证的模板字符串

        Returns:
            tuple: (是否有效, 错误信息列表)
        """
        if self._config_manager and hasattr(self._config_manager, "_field_resolver"):
            return self._config_manager._field_resolver.validate_template(template)
        else:
            logger.warning("配置管理器未初始化，无法验证模板")
            return True, []

    def get_template_variables(self, template: str) -> list[str]:
        """提取模板中的所有变量

        Args:
            template: 模板字符串

        Returns:
            list: 变量名列表
        """
        if self._config_manager and hasattr(self._config_manager, "_field_resolver"):
            return self._config_manager._field_resolver.get_template_variables(template)
        else:
            logger.warning("配置管理器未初始化，无法提取模板变量")
            return []

    def reload_config(self):
        """重新加载配置文件"""
        if self._config_manager:
            try:
                self._config_manager.reload_config_from_file()
                logger.debug("配置文件重新加载成功")
            except Exception as e:
                logger.error(f"重新加载配置文件失败: {e}")
        else:
            logger.warning("配置管理器未初始化，无法重新加载配置")

    def validate_current_config(self) -> tuple[bool, list[str]]:
        """验证当前配置的有效性

        Returns:
            tuple: (是否有效, 错误信息列表)
        """
        if self._config_manager:
            try:
                return self._config_manager.validate_config()
            except Exception as e:
                logger.error(f"验证配置失败: {e}")
                return False, [f"配置验证异常: {e}"]
        else:
            logger.warning("配置管理器未初始化，无法验证配置")
            return True, []

    def clear_all_caches(self):
        """清除所有缓存"""
        if self._config_manager:
            self._config_manager.clear_all_caches()

        # 清除trace上下文
        self.clear_trace_context()

        logger.debug("已清除所有缓存和上下文")

    def get_config_status(self) -> dict:
        """获取配置状态信息"""
        status = self.get_status()

        if self._config_manager:
            try:
                config_status = self._config_manager.get_config_status()
                status["config_manager"] = config_status
            except Exception as e:
                logger.error(f"获取配置管理器状态失败: {e}")
                status["config_manager"] = {"error": str(e)}
        else:
            status["config_manager"] = None

        return status

    def resolve_template_with_context(self, template: str, context: dict = None) -> str:
        """使用指定上下文解析模板

        Args:
            template: 模板字符串
            context: 上下文变量

        Returns:
            str: 解析后的字符串
        """
        if not self._config_manager:
            logger.warning("配置管理器未初始化，无法解析模板")
            return template

        try:
            # 合并全局trace上下文和提供的上下文
            merged_context = {}
            if hasattr(self, "_trace_context"):
                merged_context.update(self._trace_context)
            if context:
                merged_context.update(context)

            return self._config_manager._field_resolver.resolve(
                template, merged_context
            )
        except Exception as e:
            logger.error(f"解析模板失败: {e}")
            return template


# 在模块级别初始化一次，确保单例模式
logger.debug("langfuse_wrapper: 开始初始化模块级别的 LangfuseWrapper 实例")
langfuse_wrapper = LangfuseWrapper.get_instance()
logger.debug("langfuse_wrapper: 模块级别的 LangfuseWrapper 实例初始化完成")
