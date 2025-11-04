# Langfuse 动态配置系统修复说明

## 问题描述

在实际使用中发现 Langfuse 的 `observe` 装饰器不支持我们配置中的某些参数，导致运行时出现错误：

```
TypeError: LangfuseDecorator.observe() got an unexpected keyword argument 'metadata'
```

## 问题原因

通过分析 Langfuse 源码发现，`observe` 装饰器只支持以下参数：

- `name`: 可选字符串
- `as_type`: 可选，只能是 "generation"
- `capture_input`: 可选布尔值
- `capture_output`: 可选布尔值
- `transform_to_string`: 可选函数

但我们的配置系统包含了额外的字段如 `metadata`, `tags`, `session_id` 等，这些字段 Langfuse 不支持。

## 解决方案

### 1. 修改 ObserveConfig 类

在 `langfuse_config.py` 中添加了 `to_langfuse_dict()` 方法，只返回 Langfuse 支持的参数：

```python
def to_langfuse_dict(self) -> Dict[str, Any]:
    """转换为 Langfuse observe 装饰器支持的参数字典"""
    result = {}
    # 只包含 Langfuse observe 装饰器支持的参数
    langfuse_supported_params = {
        "name", "capture_input", "capture_output", "as_type"
    }
    
    for key, value in self.__dict__.items():
        if key in langfuse_supported_params and value is not None:
            # 特殊处理 as_type，确保只有 "generation" 值才传递
            if key == "as_type" and value != "generation":
                continue
            result[key] = value
    return result
```

### 2. 更新配置管理器

修改 `get_config()` 方法使用 `to_langfuse_dict()` 而不是 `to_dict()`：

```python
def get_config(self, function_name: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    # ... 配置合并逻辑 ...
    
    # 返回 Langfuse 支持的参数
    return resolved_config.to_langfuse_dict()
```

同时添加了 `get_full_config()` 方法用于获取包含所有字段的完整配置。

### 3. 简化配置文件

更新了 `langfuse_config.json`，移除了不支持的字段，只保留 Langfuse 支持的参数：

```json
{
  "global": {
    "capture_input": true,
    "capture_output": true
  },
  "functions": {
    "chat_agent_run": {
      "name": "chat-agent-execution",
      "capture_input": true,
      "capture_output": true
    }
  }
}
```

## 向后兼容性

- 保留了 `to_dict()` 方法用于获取完整配置
- 添加了 `get_full_config()` 方法用于需要所有字段的场景
- 额外字段（如 `metadata`, `tags`）仍然可以在配置中定义，用于其他用途

## 使用方式

### 基本使用（推荐）

```python
from src.utils.langfuse_wrapper import langfuse_wrapper

@langfuse_wrapper.dynamic_observe()
def my_function(data: str):
    return f"Processed: {data}"
```

### 自定义参数

```python
@langfuse_wrapper.dynamic_observe(
    name="custom-function",
    capture_input=True,
    capture_output=True
)
def custom_function(data: str):
    return f"Custom: {data}"
```

### 运行时配置更新

```python
# 只更新 Langfuse 支持的参数
langfuse_wrapper.update_function_config("my_function", {
    "name": "updated-function",
    "capture_input": False,
    "capture_output": True
})
```

## 测试验证

运行以下测试确认修复有效：

```bash
cd proteus-ai/proteus
python -c "
from src.utils.langfuse_wrapper import langfuse_wrapper

@langfuse_wrapper.dynamic_observe()
def test_function(param1: str, param2: int = 10):
    return f'result: {param1}, {param2}'

result = test_function('test', 20)
print(f'测试成功: {result}')
"
```

## 注意事项

1. **参数限制**：只有 Langfuse 支持的参数会被传递给装饰器
2. **as_type 参数**：只有值为 "generation" 时才会传递
3. **额外字段**：`metadata`, `tags` 等字段仍可在配置中定义，但不会传递给 Langfuse
4. **配置文件**：建议使用简化的配置文件格式，避免不支持的字段

## 未来改进

1. 可以考虑使用 Langfuse 的其他 API 来设置 metadata 和 tags
2. 可以在 span 创建后通过 `update()` 方法添加额外信息
3. 可以实现自定义的 span 包装器来支持更多字段

这个修复确保了系统的稳定性，同时保持了动态配置的灵活性。