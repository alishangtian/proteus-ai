from datetime import datetime
from typing import List, Dict, Any, Optional, Union, Callable, TypeVar, Generic
from enum import Enum
from dataclasses import dataclass, field
import time
import uuid
from functools import lru_cache

T = TypeVar("T")


class Cache(Generic[T]):
    """改进的LRU缓存实现，带有TTL和分层缓存支持"""

    def __init__(self, maxsize: int = 100, ttl: int = 3600):
        self.cache: Dict[str, tuple[T, float]] = {}
        self.maxsize = maxsize
        self.ttl = ttl
        self.semantic_cache: Dict[str, tuple[T, float]] = {}  # 语义缓存

    def clear(self) -> None:
        """清空所有缓存数据，包括精确匹配缓存和语义缓存"""
        self.cache.clear()
        self.semantic_cache.clear()

    def get(self, key: str, semantic_key: Optional[str] = None) -> Optional[T]:
        """获取缓存值，支持精确匹配和语义匹配"""
        # 首先尝试精确匹配
        if key in self.cache:
            value, timestamp = self.cache[key]
            if time.time() - timestamp <= self.ttl:
                return value
            del self.cache[key]

        # 如果提供了语义键，尝试语义匹配
        if semantic_key and semantic_key in self.semantic_cache:
            value, timestamp = self.semantic_cache[semantic_key]
            if time.time() - timestamp <= self.ttl:
                return value
            del self.semantic_cache[semantic_key]
        return None

    def set(self, key: str, value: T, semantic_key: Optional[str] = None) -> None:
        """设置缓存值，支持精确缓存和语义缓存"""
        current_time = time.time()

        # 更新精确缓存
        if len(self.cache) >= self.maxsize:
            oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k][1])
            del self.cache[oldest_key]
        self.cache[key] = (value, current_time)

        # 如果提供了语义键，更新语义缓存
        if semantic_key:
            if len(self.semantic_cache) >= self.maxsize:
                oldest_key = min(
                    self.semantic_cache.keys(), key=lambda k: self.semantic_cache[k][1]
                )
                del self.semantic_cache[oldest_key]
            self.semantic_cache[semantic_key] = (value, current_time)


class Metrics:
    """增强的性能指标收集器"""

    def __init__(self):
        self.total_calls = 0
        self.total_time = 0.0
        self.error_count = 0
        self.last_response_time = 0.0
        self.tool_usage: Dict[str, int] = {}
        self.cache_hits = 0
        self.cache_misses = 0
        self.retry_count = 0
        self.semantic_cache_hits = 0

    def record_call(self, execution_time: float, is_error: bool = False):
        self.total_calls += 1
        self.total_time += execution_time
        self.last_response_time = execution_time
        if is_error:
            self.error_count += 1

    def record_tool_usage(self, tool_name: str):
        self.tool_usage[tool_name] = self.tool_usage.get(tool_name, 0) + 1

    def record_cache_access(self, hit: bool, semantic: bool = False):
        if hit:
            self.cache_hits += 1
            if semantic:
                self.semantic_cache_hits += 1
        else:
            self.cache_misses += 1

    def record_retry(self):
        self.retry_count += 1

    @property
    def average_response_time(self) -> float:
        return self.total_time / self.total_calls if self.total_calls > 0 else 0.0

    @property
    def error_rate(self) -> float:
        return self.error_count / self.total_calls if self.total_calls > 0 else 0.0

    @property
    def cache_hit_rate(self) -> float:
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else 0.0

    @property
    def semantic_cache_hit_rate(self) -> float:
        return (
            self.semantic_cache_hits / self.cache_hits if self.cache_hits > 0 else 0.0
        )


class AgentError(Exception):
    """Agent相关错误的基类"""

    pass


class ToolExecutionError(AgentError):
    """工具执行错误"""

    pass


class ToolNotFoundError(AgentError):
    """工具未找到错误"""

    pass


class LLMAPIError(AgentError):
    """LLM API调用错误"""

    pass


@dataclass
class AgentCard:
    """Agent信息卡片，包含基本元数据"""

    name: str = "未命名Agent"
    description: str = ""
    agentid: str = ""
    model: str = ""
    version: str = "1.0.0"
    created_at: str = field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    tags: List[str] = field(default_factory=list)


@dataclass
class IncludeFields(str, Enum):
    """可包含在 prompt 中的字段"""

    THOUGHT = "thought"
    ACTION = "action"
    ACTION_INPUT = "action_input"
    OBSERVATION = "observation"


@dataclass
class ScratchpadItem:
    """表示Agent思考和执行过程的一个步骤

    包含:
        action_input: 可选的动作参数（字符串），当长度超过200时会被截断为前200字符
        tool_execution_id: 工具执行的唯一标识符
        role_type: 可选，记录该条scratchpad所属的角色（用于多角色场景的过滤）
    """

    thought: str = ""
    action: str = ""
    observation: str = ""
    action_input: str = ""
    is_origin_query: bool = False
    tool_execution_id: str = ""
    role_type: str = ""

    def __post_init__(self):
        # 确保 action_input 为字符串并限制长度不超过200
        try:
            if self.action_input is None:
                self.action_input = ""
            else:
                self.action_input = str(self.action_input)
        except Exception:
            self.action_input = ""
        if len(self.action_input) > 200:
            self.action_input = self.action_input[:200]

        # 确保 role_type 为字符串
        try:
            if self.role_type is None:
                self.role_type = ""
            else:
                self.role_type = str(self.role_type)
        except Exception:
            self.role_type = ""

    def to_dict(self) -> Dict[str, str]:
        """将对象转换为字典"""
        return {
            "thought": self.thought,
            "action": self.action,
            "observation": self.observation,
            "action_input": self.action_input,
            "is_origin_query": self.is_origin_query,
            "tool_execution_id": self.tool_execution_id,
            "role_type": self.role_type,
        }

    def to_string(self, index: int = None) -> str:
        """将对象转换为字符串表示，以紧凑的Markdown格式"""
        formatted_observation = self._format_markdown_observation(self.observation)
        param_display = f"\n**参数**: {self.action_input}" if self.action_input else ""

        if index is not None:
            return f"\n{index}.**子任务定义**: {self.thought}\n**工具调用**: {self.action}{param_display}\n**结果**: {formatted_observation}"
        else:
            return f"**子任务描述**: {self.thought}\n**工具调用**: {self.action}{param_display}\n**结果**: {formatted_observation}\n"

    def to_string2(self, index: int = None) -> str:
        """将对象转换为字符串表示，以紧凑的Markdown格式"""
        formatted_observation = self._format_markdown_observation(self.observation)
        param_display = f"\n参数: {self.action_input}" if self.action_input else ""

        if index is not None:
            return f"{index}.思考: {self.thought}\n{index}.动作: {self.action}{param_display}\n{index}.观察: {formatted_observation}\n"
        else:
            return f"思考: {self.thought}\n动作: {self.action}{param_display}\n观察: {formatted_observation}\n"

    def to_react_context(
        self,
        index: int = None,
        use_summary: bool = False,
        include_fields: List[IncludeFields] = None,
    ) -> str:
        """将对象转换为字符串表示，以紧凑的Markdown格式

        Args:
            index: 步骤索引
            use_summary: 保留参数向后兼容，但始终使用完整的observation
            include_fields: 要包含的字段列表，例如 [IncludeFields.THOUGHT, IncludeFields.ACTION, IncludeFields.ACTION_INPUT, IncludeFields.OBSERVATION]
                            如果为 None，则包含所有字段。
        """
        if include_fields is None:
            include_fields = [
                IncludeFields.THOUGHT,
                IncludeFields.ACTION,
                IncludeFields.ACTION_INPUT,
                IncludeFields.OBSERVATION,
            ]

        parts = []
        if IncludeFields.THOUGHT in include_fields and self.thought:
            parts.append(f"Thought :{self.thought}")

        if IncludeFields.ACTION in include_fields and self.action:
            parts.append(f"Action :{self.action}")

        if IncludeFields.ACTION_INPUT in include_fields and self.action_input:
            parts.append(f"Action Input :{self.action_input}")

        if IncludeFields.OBSERVATION in include_fields and self.observation:
            formatted_observation = self._format_markdown_observation(self.observation)
            parts.append(f"Observation :\n    {formatted_observation}")

        return "\n".join(parts) + "\n" if parts else ""

    def _format_markdown_observation(self, text: str) -> str:
        """格式化markdown格式的observation内容

        处理规则:
        1. 标题行的缩进只保留一个tab缩进
        2. 优化其他不符合markdown规范的内容
        """
        if not text:
            return ""

        # 检查是否可能是markdown格式（包含#标题、列表符号等）
        md_indicators = ["#", "- ", "* ", "1. ", "```", "|", "> "]
        is_markdown = any(indicator in text for indicator in md_indicators)

        if not is_markdown:
            return text

        # 处理markdown内容
        lines = text.split("\n")
        formatted_lines = []

        for line in lines:
            stripped = line.lstrip()

            # 处理标题行 (以#开头)
            if stripped.startswith("#"):
                # 标题行只保留一个tab缩进
                formatted_lines.append(f"    {stripped}")

            # 处理代码块 (```)
            elif stripped.startswith("```"):
                formatted_lines.append(f"    {stripped}")

            # 处理列表项 (-, *, 数字.)
            elif any(
                stripped.startswith(prefix)
                for prefix in ["- ", "* ", "1. ", "2. ", "3. "]
            ):
                formatted_lines.append(f"    {stripped}")

            # 处理表格行 (|)
            elif "|" in stripped and stripped.count("|") > 1:
                formatted_lines.append(f"    {stripped}")

            # 处理引用块 (>)
            elif stripped.startswith(">"):
                formatted_lines.append(f"    {stripped}")

            # 其他行保持原有格式
            else:
                # 如果是空行或普通文本，保持适当缩进
                formatted_lines.append(f"    {stripped}" if stripped else "")

        return "\n".join(formatted_lines)


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
            raise AgentError(f"Tool {self.name} 'run' must be callable")
        if self.params:
            self._validate_params()

    def _validate_params(self) -> None:
        for param_name, param_info in self.params.items():
            required_keys = {"type", "description"}
            if not all(key in param_info for key in required_keys):
                raise AgentError(
                    f"Tool {self.name} parameter {param_name} missing required keys: {required_keys}"
                )
