from typing import Dict, Any, Optional, Callable, TypeVar
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class Tool:
    name: str
    description: str
    run: Callable
    is_async: bool = False
    params: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    outputs: Dict[str, str] = field(default_factory=dict)
    full_description: str = ""  # 完整描述
    max_retries: int = 0  # 新增：最大重试次数
    retry_delay: float = 1.0  # 新增：重试延迟（秒）
    memory: Optional[str] = None  # 新增：工具的历史记忆

    @classmethod
    def fromAnything(cls, func: Callable, **kwargs) -> "Tool":
        """从任意可调用对象创建工具实例

        优化版本：只需提供可执行函数即可初始化工具
        自动提取函数名、参数信息、文档字符串等元数据
        """
        import inspect

        # 获取函数基本信息
        tool_name = func.__name__
        sig = inspect.signature(func)

        # 自动生成参数描述
        params = {}
        for name, param in sig.parameters.items():
            if name == "self":
                continue
            params[name] = {
                "type": (
                    param.annotation
                    if param.annotation != inspect.Parameter.empty
                    else str
                ),
                "description": f"{name}参数",
                "required": param.default == inspect.Parameter.empty,
            }

        # 处理文档字符串
        doc = inspect.getdoc(func) or ""
        short_desc = doc.split("\n")[0].strip() if doc else f"执行 {tool_name} 操作"
        full_desc = doc if doc else short_desc

        return cls(
            name=tool_name,
            description=short_desc,
            full_description=full_desc,
            run=func,
            is_async=inspect.iscoroutinefunction(func),
            params=params,
            **kwargs,
        )

    def __post_init__(self):
        if not callable(self.run):
            raise Exception(f"Tool {self.name} 'run' must be callable")
        if self.params:
            self._validate_params()

    def _validate_params(self) -> None:
        for param_name, param_info in self.params.items():
            required_keys = {"type", "description"}
            if not all(key in param_info for key in required_keys):
                raise Exception(
                    f"Tool {self.name} parameter {param_name} missing required keys: {required_keys}"
                )
