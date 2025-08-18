# 延迟/容错导入：避免在测试或部分运行环境中因循环/缺失依赖导致包导入失败。
# 在需要时可直接从子模块导入具体类。
try:
    from .engine import WorkflowEngine, NodeBase, NodeResult  # type: ignore
    from .nodes import TextConcatNode, TextReplaceNode, AddNode, MultiplyNode, ChatNode  # type: ignore
except Exception:
    # 如果子模块不可用，保留占位符，导入失败时上层代码应进行容错处理或在需要时再次导入子模块.
    WorkflowEngine = None
    NodeBase = None
    NodeResult = None
    TextConcatNode = None
    TextReplaceNode = None
    AddNode = None
    MultiplyNode = None
    ChatNode = None

__all__ = [
    "WorkflowEngine",
    "NodeBase",
    "NodeResult",
    "TextConcatNode",
    "TextReplaceNode",
    "AddNode",
    "MultiplyNode",
    "ChatNode",
]
