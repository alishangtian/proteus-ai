"""
技能使用记录器 - 提供自动记录功能
"""

import time
import functools
from typing import Callable, Any

# 尝试相对导入，如果失败则尝试绝对导入
try:
    from .monitor import SkillUsageMonitor
except ImportError:
    # 如果相对导入失败，尝试直接导入
    import sys
    import os
    # 添加当前目录到路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    
    try:
        from monitor import SkillUsageMonitor
    except ImportError:
        # 最后尝试从文件直接导入
        import importlib.util
        spec = importlib.util.spec_from_file_location("monitor", os.path.join(current_dir, "monitor.py"))
        monitor_module = importlib.util.module_from_spec(spec)
        sys.modules["monitor"] = monitor_module
        spec.loader.exec_module(monitor_module)
        SkillUsageMonitor = monitor_module.SkillUsageMonitor

# 全局监控实例
_monitor_instance = None

def get_monitor() -> SkillUsageMonitor:
    """获取全局监控实例"""
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = SkillUsageMonitor()
    return _monitor_instance

def record_skill_usage(skill_name: str = None, **kwargs):
    """
    记录技能使用的装饰器或函数
    
    用法1: 作为装饰器
    ```python
    @record_skill_usage("my-skill")
    def execute_skill():
        # 技能逻辑
        pass
    ```
    
    用法2: 作为函数
    ```python
    record_skill_usage("my-skill", context_length=1000, success=True)
    ```
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **wrapper_kwargs):
            # 记录开始时间
            start_time = time.time()
            success = True
            error_message = ""
            
            try:
                # 执行原函数
                result = func(*args, **wrapper_kwargs)
                return result
            except Exception as e:
                success = False
                error_message = str(e)
                raise
            finally:
                # 获取技能名称
                actual_skill_name = skill_name
                if actual_skill_name is None:
                    actual_skill_name = func.__name__
                
                # 估算上下文长度
                context_length = kwargs.get('context_length', 0)
                if context_length == 0 and args:
                    # 简单估算：将参数转换为字符串的长度
                    context_length = len(str(args)) + len(str(wrapper_kwargs))
                
                # 记录使用
                monitor = get_monitor()
                monitor.record_usage(
                    actual_skill_name,
                    context_length=context_length,
                    success=success,
                    error_message=error_message,
                    execution_time=time.time() - start_time,
                    metadata=kwargs.get('metadata')
                )
        
        return wrapper
    
    # 如果直接调用函数（不是作为装饰器），立即记录
    if skill_name is not None and callable(skill_name):
        # 实际上是装饰器调用：@record_skill_usage
        func = skill_name
        skill_name = func.__name__
        return decorator(func)
    elif skill_name is not None and not callable(skill_name):
        # 直接记录使用
        monitor = get_monitor()
        return monitor.record_usage(skill_name, **kwargs)
    else:
        # 返回装饰器
        return decorator

def auto_record_skill_usage(func: Callable = None, **kwargs):
    """
    自动记录技能使用的装饰器（自动使用函数名作为技能名）
    """
    if func is None:
        return lambda f: record_skill_usage(f.__name__, **kwargs)(f)
    return record_skill_usage(func.__name__, **kwargs)(func)

class SkillUsageTracker:
    """技能使用跟踪器（上下文管理器）"""
    
    def __init__(self, skill_name: str, **kwargs):
        self.skill_name = skill_name
        self.kwargs = kwargs
        self.start_time = None
        self.success = True
        self.error_message = ""
        self.metadata = kwargs.get('metadata', {})
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # 计算执行时间
        execution_time = time.time() - self.start_time
        
        # 检查是否有异常
        if exc_type is not None:
            self.success = False
            self.error_message = str(exc_val) if exc_val else str(exc_type)
        
        # 记录使用
        monitor = get_monitor()
        monitor.record_usage(
            self.skill_name,
            context_length=self.kwargs.get('context_length', 0),
            success=self.success,
            error_message=self.error_message,
            execution_time=execution_time,
            metadata=self.metadata
        )
        
        # 不抑制异常
        return False
    
    def add_metadata(self, metadata: dict):
        """添加额外元数据"""
        self.metadata.update(metadata)

def track_skill_usage(skill_name: str, **kwargs):
    """
    跟踪技能使用的上下文管理器
    
    用法:
    ```python
    with track_skill_usage("my-skill") as tracker:
        # 执行技能逻辑
        tracker.add_metadata({"custom": "data"})
    ```
    """
    return SkillUsageTracker(skill_name, **kwargs)

def record_usage_now(skill_name: str, **kwargs) -> bool:
    """立即记录技能使用"""
    monitor = get_monitor()
    return monitor.record_usage(skill_name, **kwargs)

def record_successful_usage(skill_name: str, **kwargs) -> bool:
    """记录成功的技能使用"""
    kwargs['success'] = True
    return record_usage_now(skill_name, **kwargs)

def record_failed_usage(skill_name: str, error_message: str = "", **kwargs) -> bool:
    """记录失败的技能使用"""
    kwargs['success'] = False
    kwargs['error_message'] = error_message
    return record_usage_now(skill_name, **kwargs)
