import os
import logging
from typing import Optional, Any, Callable

logger = logging.getLogger(__name__)


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
                return self._span.update(*args, **kwargs)
            except Exception as e:
                logger.warning(f"Span update failed: {e}")
        return self

    def end(self, *args, **kwargs):
        if hasattr(self._span, "end"):
            try:
                return self._span.end(*args, **kwargs)
            except Exception as e:
                logger.warning(f"Span end failed: {e}")
        return self

    def update_trace(self, *args, **kwargs):
        if hasattr(self._span, "update_trace"):
            try:
                return self._span.update_trace(*args, **kwargs)
            except Exception as e:
                logger.warning(f"Span update_trace failed: {e}")
        return self

    def start_as_current_generation(self, *args, **kwargs):
        if hasattr(self._span, "start_as_current_generation"):
            try:
                return self._span.start_as_current_generation(*args, **kwargs)
            except Exception as e:
                logger.warning(f"Start generation failed: {e}")
                return NoopGeneration()
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
        try:
            # Prefer the real span if available
            if self._real and hasattr(self._real, "span"):
                span_obj = getattr(self._real, "span")(*args, **kwargs)
                return SpanWrapper(span_obj)
            # Fallback: if SDK exposes start_as_current_span, use it (context manager)
            if self._real and hasattr(self._real, "start_as_current_span"):
                span_obj = getattr(self._real, "start_as_current_span")(*args, **kwargs)
                return SpanWrapper(span_obj)
        except Exception as e:
            logger.warning(f"Failed to create Langfuse span: {e}")

        # Final fallback: return a no-op span to avoid attribute errors
        return NoopSpan(kwargs.get("name", ""))

    def start_as_current_span(self, *args, **kwargs):
        try:
            if self._real and hasattr(self._real, "start_as_current_span"):
                span_obj = getattr(self._real, "start_as_current_span")(*args, **kwargs)
                return SpanWrapper(span_obj)
        except Exception as e:
            logger.warning(f"Failed to start Langfuse span: {e}")

        return NoopSpan(kwargs.get("name", ""))


class LangfuseWrapper:
    _instance: Optional["LangfuseWrapper"] = None
    _langfuse_instance: Optional[Any] = None
    _langfuse_enabled: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LangfuseWrapper, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        # 检查环境变量以确定是否启用 Langfuse
        self._langfuse_enabled = (
            os.getenv("LANGFUSE_ENABLED", "false").lower() == "true"
        )

        if self._langfuse_enabled:
            try:
                from langfuse import Langfuse

                self._langfuse_instance = Langfuse()
                if self._langfuse_instance.auth_check():
                    logger.info("LangfuseWrapper: Langfuse authentication successful.")
                else:
                    logger.error("LangfuseWrapper: Langfuse authentication failed.")
                    self._langfuse_enabled = False  # 认证失败则禁用
            except ImportError:
                logger.warning(
                    "LangfuseWrapper: langfuse library not found. Langfuse will be disabled."
                )
                self._langfuse_enabled = False
            except Exception as e:
                logger.error(
                    f"LangfuseWrapper: Error initializing Langfuse: {e}. Langfuse will be disabled."
                )
                self._langfuse_enabled = False
        else:
            logger.info("LangfuseWrapper: Langfuse is disabled by configuration.")

    @classmethod
    def get_instance(cls) -> "LangfuseWrapper":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_langfuse_instance(self) -> Optional[Any]:
        # 返回一个适配器对象，确保调用方可以安全使用 .span / .start_as_current_span 等接口
        if self._langfuse_instance:
            return LangfuseAdapter(self._langfuse_instance)
        # 当未初始化真实实例时返回适配器的 no-op 实例，避免外部直接访问 None
        return LangfuseAdapter(None)

    def is_enabled(self) -> bool:
        return self._langfuse_enabled

    def observe_decorator(self, *args, **kwargs) -> Callable:
        if self._langfuse_enabled and self._langfuse_instance:
            try:
                from langfuse import observe

                return observe(*args, **kwargs)
            except ImportError:
                logger.warning(
                    "LangfuseWrapper: langfuse.observe not found, returning no-op decorator."
                )
                return self._no_op_decorator
            except Exception as e:
                logger.error(
                    f"LangfuseWrapper: Error creating observe decorator: {e}, returning no-op decorator."
                )
                return self._no_op_decorator
        return self._no_op_decorator

    def _no_op_decorator(self, func: Callable) -> Callable:
        """一个什么都不做的装饰器，用于Langfuse禁用时"""
        return func


# 在模块级别初始化一次，确保单例模式
langfuse_wrapper = LangfuseWrapper.get_instance()
