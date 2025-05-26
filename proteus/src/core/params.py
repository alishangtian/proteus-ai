import re
from typing import Dict, Any, Optional
from .models import NodeResult

class ParamsProcessor:
    """参数处理器"""
    
    @staticmethod
    def process_params(
        params: Dict[str, Any],
        results: Dict[str, NodeResult],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """处理节点参数，支持嵌套参数和表达式替换
        
        Args:
            params: 原始参数
            results: 已有的执行结果
            context: 上下文变量
            
        Returns:
            Dict[str, Any]: 处理后的参数
        """
        def replace_expression(value: str) -> str:
            """替换字符串中的所有参数表达式"""
            pattern = r'\${([a-zA-Z0-9_]+)(?:\.([a-zA-Z0-9_]+)|\[(\d+)\])*}'
            
            def replace(match):
                full_match = match.group(0)
                expr = match.group(0)[2:-1]  # Remove ${...}
                parts = []
                current_part = ""
                i = 0
                while i < len(expr):
                    if expr[i] == '.':
                        if current_part:
                            parts.append(current_part)
                            current_part = ""
                    elif expr[i] == '[':
                        if current_part:
                            parts.append(current_part)
                            current_part = ""
                        # Extract array index
                        i += 1
                        index = ""
                        while i < len(expr) and expr[i] != ']':
                            index += expr[i]
                            i += 1
                        parts.append(f"[{index}]")
                    else:
                        current_part += expr[i]
                    i += 1
                if current_part:
                    parts.append(current_part)
                
                node_id = parts[0]
                field_parts = parts[1:]
                
                if node_id not in results:
                    raise ValueError(f"引用了未执行的节点: {node_id}")
                if not results[node_id].data:
                    raise ValueError(f"节点 {node_id} 没有返回数据")
                    
                current = results[node_id].data
                for field in field_parts:
                    if field.startswith('[') and field.endswith(']'):
                        # Handle array index
                        index = int(field[1:-1])
                        if not isinstance(current, (list, tuple)):
                            raise ValueError(f"Cannot use array index on non-sequence type: {type(current)}")
                        if index >= len(current):
                            raise ValueError(f"Array index {index} out of range for length {len(current)}")
                        current = current[index]
                    elif isinstance(current, dict):
                        if field not in current:
                            raise ValueError(f"节点 {node_id} 的结果中不存在字段: {field}")
                        current = current[field]
                    elif hasattr(current, field):
                        current = getattr(current, field)
                    else:
                        raise ValueError(f"无法从 {type(current)} 访问字段: {field}")
                return str(current)
                
            return re.sub(pattern, replace, value)
            
        def process_value(value: Any) -> Any:
            """递归处理参数值"""
            if isinstance(value, str):
                # 处理完整的参数引用 (如 "${node1.param}" 或 "${item.field1.field2}")
                if value.startswith("${") and value.endswith("}"):
                    ref_value = value[2:-1]  # Remove ${...}
                    parts = []
                    current_part = ""
                    i = 0
                    while i < len(ref_value):
                        if ref_value[i] == '.':
                            if current_part:
                                parts.append(current_part)
                                current_part = ""
                        elif ref_value[i] == '[':
                            if current_part:
                                parts.append(current_part)
                                current_part = ""
                            # Extract array index
                            i += 1
                            index = ""
                            while i < len(ref_value) and ref_value[i] != ']':
                                index += ref_value[i]
                                i += 1
                            parts.append(f"[{index}]")
                        else:
                            current_part += ref_value[i]
                        i += 1
                    if current_part:
                        parts.append(current_part)
                    
                    if len(parts) > 1:
                        ref_node = parts[0]
                        field_parts = parts[1:]
                    else:
                        ref_node = ref_value
                        field_parts = []

                    # 先检查是否是上下文变量
                    if context and ref_node in context:
                        current = context[ref_node]
                    # 再检查是否是节点引用
                    elif ref_node in results:
                        if not results[ref_node].data:
                            raise ValueError(f"节点 {ref_node} 没有返回数据")
                        current = results[ref_node].data
                    else:
                        raise ValueError(f"引用了未执行的节点或未定义的上下文变量: {ref_node}")
                    
                    # 逐级访问字段
                    for field in field_parts:
                        if field.startswith('[') and field.endswith(']'):
                            # Handle array index
                            index = int(field[1:-1])
                            if not isinstance(current, (list, tuple)):
                                raise ValueError(f"Cannot use array index on non-sequence type: {type(current)}")
                            if index >= len(current):
                                raise ValueError(f"Array index {index} out of range for length {len(current)}")
                            current = current[index]
                        elif isinstance(current, dict):
                            if field not in current:
                                raise ValueError(f"结果中不存在字段: {field}")
                            current = current[field]
                        elif hasattr(current, field):
                            current = getattr(current, field)
                        else:
                            raise ValueError(f"无法从 {type(current)} 访问字段: {field}")
                    return current

                # 处理包含参数表达式的字符串
                elif "${" in value and "}" in value:
                    return replace_expression(value)
                return value
            elif isinstance(value, dict):
                # 检查是否为工作流节点（包含nodes节点）
                if not "nodes" in value:
                    return {k: process_value(v) for k, v in value.items()}
                return value
            elif isinstance(value, list):
                return [process_value(item) for item in value]
            return value
        return {key: process_value(value) for key, value in params.items()}