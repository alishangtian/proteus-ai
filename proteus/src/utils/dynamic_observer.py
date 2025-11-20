# -*- coding: utf-8 -*-
"""
Runtime dynamic observer injector.

用途:
- 在运行时为模块内未显式使用 langfuse_wrapper.dynamic_observe() 的函数/方法自动添加该装饰器能力。
- 支持按正则白名单/黑名单过滤、只作用于定义在目标模块内的对象、处理普通函数、实例方法、静态方法、类方法、async 函数。
- 提供显式在模块末尾调用的便捷函数 `auto_apply_here`，以及可安装的 import-hook `install_import_hook`。

使用示例:
    # 模块末尾（显式触发）
    from src.utils.dynamic_observer import auto_apply_here
    auto_apply_here(globals(), include=[r"^clear_agents$"], verbose=True)

    # 或者在应用入口安装 import hook（导入时自动应用）
    from src.utils.dynamic_observer import install_import_hook
    install_import_hook("proteus_ai.proteus.src.agent", include=[r"^ReactAgent\."], verbose=True)
"""
import re
import sys
import importlib
import importlib.abc
import importlib.util
import inspect
import logging
from typing import Optional, Sequence, Pattern

from src.utils.langfuse_wrapper import langfuse_wrapper

logger = logging.getLogger(__name__)

# attribute marks used to avoid double-wrapping
_DEFAULT_MARK = "__dynamic_observer_wrapped__"
_LANGFUSE_MARK = "__langfuse_dynamic_observed__"


def _compile_patterns(patterns: Optional[Sequence[str]]) -> Optional[Sequence[Pattern]]:
    if not patterns:
        return None
    return [re.compile(p) for p in patterns]


def _matches_any(name: str, patterns: Optional[Sequence[Pattern]]) -> bool:
    if not patterns:
        return False
    return any(p.search(name) for p in patterns)


def _already_wrapped(func) -> bool:
    """
    Detect whether a callable has already been observed/wrapped.

    Checks:
    - marker set by this injector (_DEFAULT_MARK)
    - marker set by langfuse_wrapper dynamic_observe (_LANGFUSE_MARK)
    - markers on the __wrapped__ chain (in case decorators use functools.wraps)
    """
    try:
        # direct markers
        if getattr(func, _DEFAULT_MARK, False) or getattr(func, _LANGFUSE_MARK, False):
            return True
        # check __wrapped__ chain
        seen = set()
        current = getattr(func, "__wrapped__", None)
        while current and id(current) not in seen:
            seen.add(id(current))
            if getattr(current, _DEFAULT_MARK, False) or getattr(current, _LANGFUSE_MARK, False):
                return True
            current = getattr(current, "__wrapped__", None)
    except Exception:
        # best-effort: any failure => conservatively assume not wrapped
        logger.debug("dynamic_observer: error while checking wrapped state for %r", func, exc_info=True)
    return False


def _mark_wrapped(func) -> None:
    """
    Best-effort mark a callable as wrapped so future checks can detect it.
    Also attempts to mark __wrapped__ underlying function if present.
    """
    try:
        setattr(func, _DEFAULT_MARK, True)
    except Exception:
        logger.debug("Unable to set %s on %r", _DEFAULT_MARK, func, exc_info=True)
    try:
        setattr(func, _LANGFUSE_MARK, True)
    except Exception:
        logger.debug("Unable to set %s on %r", _LANGFUSE_MARK, func, exc_info=True)
    # try to mark underlying original function if available
    try:
        underlying = getattr(func, "__wrapped__", None)
        if underlying:
            try:
                setattr(underlying, _DEFAULT_MARK, True)
            except Exception:
                logger.debug("Unable to set %s on underlying %r", _DEFAULT_MARK, underlying, exc_info=True)
            try:
                setattr(underlying, _LANGFUSE_MARK, True)
            except Exception:
                logger.debug("Unable to set %s on underlying %r", _LANGFUSE_MARK, underlying, exc_info=True)
    except Exception:
        logger.debug("dynamic_observer: failed to mark underlying wrapped function for %r", func, exc_info=True)


def _wrap_callable(func):
    """
    Apply langfuse_wrapper.dynamic_observe() to a callable if not already wrapped.
    This function is idempotent (uses marker attribute).
    """
    # only wrap python functions / coroutine functions
    if not (inspect.isfunction(func) or inspect.ismethod(func) or inspect.iscoroutinefunction(func)):
        return func
    if _already_wrapped(func):
        return func
    try:
        wrapped = langfuse_wrapper.dynamic_observe()(func)
        # mark both original and wrapped for future idempotency checks
        _mark_wrapped(wrapped)
        _mark_wrapped(func)
        return wrapped
    except Exception:
        logger.exception("failed to apply dynamic_observe to %r", func)
        return func


def apply_to_module(module_or_name, include: Optional[Sequence[str]] = None, exclude: Optional[Sequence[str]] = None, only_in_module: bool = True, verbose: bool = False):
    """
    Scan the given module and apply dynamic_observe to eligible callables.

    Args:
        module_or_name: module object or module import path string
        include: sequence of regex strings - if provided, only names matching any include pattern are considered
        exclude: sequence of regex strings - names matching any exclude pattern are skipped
        only_in_module: when True, only wrap functions/methods whose __module__ equals the module's name
        verbose: enable logging
    Returns:
        True on completion
    """
    include_p = _compile_patterns(include)
    exclude_p = _compile_patterns(exclude)

    if isinstance(module_or_name, str):
        module = importlib.import_module(module_or_name)
    else:
        module = module_or_name

    module_name = getattr(module, "__name__", None)
    if module_name is None:
        raise RuntimeError("invalid module provided")

    if verbose:
        logger.info("dynamic_observer: applying to module %s", module_name)

    # Wrap top-level functions defined in the module
    for name in dir(module):
        if name.startswith("__"):
            continue
        try:
            attr = getattr(module, name)
        except Exception:
            continue

        # top-level function
        if inspect.isfunction(attr):
            if only_in_module and getattr(attr, "__module__", None) != module_name:
                continue
            fullname = f"{module_name}.{name}"
            if include_p and not _matches_any(name, include_p) and not _matches_any(fullname, include_p):
                continue
            if exclude_p and (_matches_any(name, exclude_p) or _matches_any(fullname, exclude_p)):
                continue
            if _already_wrapped(attr):
                if verbose:
                    logger.debug("dynamic_observer: skip already wrapped function %s", fullname)
                continue
            new = _wrap_callable(attr)
            if new is not attr:
                setattr(module, name, new)
                if verbose:
                    logger.info("dynamic_observer: wrapped function %s", fullname)

        # classes defined in this module
        elif inspect.isclass(attr):
            if only_in_module and getattr(attr, "__module__", None) != module_name:
                continue
            cls = attr
            for k, v in list(cls.__dict__.items()):
                if k.startswith("__"):
                    continue
                try:
                    full_name = f"{module_name}.{cls.__name__}.{k}"
                    # staticmethod
                    if isinstance(v, staticmethod):
                        func = v.__func__
                        if _already_wrapped(func):
                            continue
                        if include_p and not (_matches_any(k, include_p) or _matches_any(full_name, include_p)):
                            continue
                        if exclude_p and (_matches_any(k, exclude_p) or _matches_any(full_name, exclude_p)):
                            continue
                        new = _wrap_callable(func)
                        if new is not func:
                            setattr(cls, k, staticmethod(new))
                            if verbose:
                                logger.info("dynamic_observer: wrapped staticmethod %s", full_name)
                    # classmethod
                    elif isinstance(v, classmethod):
                        func = v.__func__
                        if _already_wrapped(func):
                            continue
                        if include_p and not (_matches_any(k, include_p) or _matches_any(full_name, include_p)):
                            continue
                        if exclude_p and (_matches_any(k, exclude_p) or _matches_any(full_name, exclude_p)):
                            continue
                        new = _wrap_callable(func)
                        if new is not func:
                            setattr(cls, k, classmethod(new))
                            if verbose:
                                logger.info("dynamic_observer: wrapped classmethod %s", full_name)
                    # regular function (instance method)
                    elif inspect.isfunction(v):
                        func = v
                        if _already_wrapped(func):
                            continue
                        if include_p and not (_matches_any(k, include_p) or _matches_any(full_name, include_p)):
                            continue
                        if exclude_p and (_matches_any(k, exclude_p) or _matches_any(full_name, exclude_p)):
                            continue
                        new = _wrap_callable(func)
                        if new is not func:
                            setattr(cls, k, new)
                            if verbose:
                                logger.info("dynamic_observer: wrapped method %s", full_name)
                except Exception:
                    logger.exception("dynamic_observer: failed processing %s.%s", cls.__name__, k)

    return True


# ------------ import hook support (optional) ------------
class _ObserverLoaderWrapper(importlib.abc.Loader):
    """
    Loader wrapper that delegates to original loader and then applies wrappers
    after module execution.
    """

    def __init__(self, original_loader, include_p, exclude_p, only_in_module, verbose):
        self.original_loader = original_loader
        self.include_p = include_p
        self.exclude_p = exclude_p
        self.only_in_module = only_in_module
        self.verbose = verbose

    def create_module(self, spec):
        creat = getattr(self.original_loader, "create_module", None)
        if creat:
            return creat(spec)
        return None

    def exec_module(self, module):
        exec_mod = getattr(self.original_loader, "exec_module", None)
        if exec_mod:
            exec_mod(module)
        else:
            # legacy loaders
            load_mod = getattr(self.original_loader, "load_module", None)
            if load_mod:
                load_mod(module.__name__)
        # apply wrapper after module loaded
        try:
            # patterns were compiled to regex objects; extract patterns strings for apply_to_module
            include = [p.pattern for p in (self.include_p or [])]
            exclude = [p.pattern for p in (self.exclude_p or [])]
            apply_to_module(module, include=include, exclude=exclude, only_in_module=self.only_in_module, verbose=self.verbose)
        except Exception:
            logger.exception("dynamic_observer: failed to apply to module %s", getattr(module, "__name__", "<unknown>"))


class _ObserverFinder(importlib.abc.MetaPathFinder):
    def __init__(self, target_prefix: str, include_p, exclude_p, only_in_module: bool, verbose: bool):
        self.target_prefix = target_prefix
        self.include_p = include_p
        self.exclude_p = exclude_p
        self.only_in_module = only_in_module
        self.verbose = verbose

    def find_spec(self, fullname, path, target=None):
        if not fullname.startswith(self.target_prefix):
            return None
        # find original spec
        try:
            spec = importlib.util.find_spec(fullname)
        except Exception:
            return None
        if not spec or not spec.loader:
            return None
        # wrap loader
        spec.loader = _ObserverLoaderWrapper(spec.loader, self.include_p, self.exclude_p, self.only_in_module, self.verbose)
        return spec


_installed_finders = {}


def install_import_hook(package_prefix: str, include: Optional[Sequence[str]] = None, exclude: Optional[Sequence[str]] = None, only_in_module: bool = True, verbose: bool = False):
    """
    Install an import hook that will apply dynamic_observe to modules whose
    fullname starts with package_prefix.
    """
    include_p = _compile_patterns(include)
    exclude_p = _compile_patterns(exclude)
    finder = _ObserverFinder(package_prefix, include_p, exclude_p, only_in_module, verbose)
    # insert at front to catch imports early
    sys.meta_path.insert(0, finder)
    _installed_finders[package_prefix] = finder
    if verbose:
        logger.info("dynamic_observer: installed import hook for %s", package_prefix)


def uninstall_import_hook(package_prefix: str):
    finder = _installed_finders.pop(package_prefix, None)
    if finder and finder in sys.meta_path:
        sys.meta_path.remove(finder)
        logger.info("dynamic_observer: removed import hook for %s", package_prefix)


# convenience helper for module-local explicit call
def auto_apply_here(globals_dict, include: Optional[Sequence[str]] = None, exclude: Optional[Sequence[str]] = None, only_in_module: bool = True, verbose: bool = False):
    """
    Convenience function to be placed at the bottom of a module:

        from src.utils.dynamic_observer import auto_apply_here
        auto_apply_here(globals(), include=[r'^clear_agents$'], verbose=True)

    `globals_dict` should be the module's globals() mapping.
    """
    module_name = globals_dict.get("__name__")
    if not module_name:
        raise RuntimeError("auto_apply_here requires module globals()")
    module = sys.modules.get(module_name)
    if not module:
        module = importlib.import_module(module_name)
    return apply_to_module(module, include=include, exclude=exclude, only_in_module=only_in_module, verbose=verbose)