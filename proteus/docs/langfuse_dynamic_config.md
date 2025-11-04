# Langfuse 动态注解字段配置系统

## 概述

本系统为 Langfuse operator 提供了动态注解字段变更和配置的能力，允许在运行时动态调整追踪参数，支持模板化配置和自定义字段解析器。

## 核心特性

### 1. 动态配置管理
- **运行时配置更新**：无需重启应用即可更新追踪配置
- **函数级配置**：为不同函数设置不同的追踪参数
- **全局配置**：设置默认的全局追踪配置
- **配置继承**：函数配置继承并覆盖全局配置

### 2. 模板化字段解析
- **环境变量解析**：`${env:VAR_NAME}` 
- **上下文变量解析**：`${context:key}`
- **时间戳解析**：`${timestamp}`
- **自定义解析器**：支持注册自定义字段解析器

### 3. 配置文件支持
- **JSON 配置文件**：支持从 JSON 文件加载配置
- **自动重载**：支持配置文件变化时自动重载
- **多路径查找**：自动查找多个可能的配置文件路径

## 快速开始

### 1. 基本使用

```python
from src.utils.langfuse_wrapper import langfuse_wrapper

# 使用动态配置装饰器
@langfuse_wrapper.dynamic_observe()
def my_function(data: str, user_id: str):
    return f"Processed {data} for {user_id}"

# 调用函数，配置会根据函数名和上下文自动应用
result = my_function("test data", "user123")
```

### 2. 自定义配置

```python
# 使用自定义参数
@langfuse_wrapper.dynamic_observe(
    name="custom-processor",
    capture_input=True,
    capture_output=True
)
def custom_function(input_data):
    return process_data(input_data)
```

### 3. 运行时配置更新

```python
# 更新函数特定配置
langfuse_wrapper.update_function_config("my_function", {
    "name": "updated-function-name",
    "metadata": {
        "version": "2.0",
        "updated_at": "${timestamp}"
    },
    "tags": ["updated", "v2"]
})

# 更新全局配置
langfuse_wrapper.update_global_config({
    "metadata": {
        "service": "my-service",
        "environment": "${env:ENVIRONMENT}"
    },
    "tags": ["global", "service"]
})
```

## 配置文件格式

### JSON 配置文件示例

```json
{
  "global": {
    "capture_input": true,
    "capture_output": true,
    "metadata": {
      "service": "proteus-ai",
      "version": "${env:APP_VERSION}",
      "environment": "${env:ENVIRONMENT}"
    },
    "tags": ["proteus", "ai-agent"],
    "session_id": "${context:chat_id}"
  },
  "functions": {
    "chat_agent_run": {
      "name": "chat-execution-${context:model_name}",
      "metadata": {
        "component": "chat_agent",
        "model": "${context:model_name}",
        "timestamp": "${timestamp}"
      },
      "tags": ["chat", "agent"]
    }
  }
}
```

### 配置字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 追踪名称，支持模板 |
| `capture_input` | boolean | 是否捕获输入参数 |
| `capture_output` | boolean | 是否捕获输出结果 |
| `metadata` | object | 元数据字典，支持模板 |
| `tags` | array | 标签列表 |
| `session_id` | string | 会话ID，支持模板 |
| `user_id` | string | 用户ID，支持模板 |
| `version` | string | 版本号 |
| `release` | string | 发布版本 |

## 模板语法

### 内置解析器

| 模板 | 说明 | 示例 |
|------|------|------|
| `${timestamp}` | ISO 格式时间戳 | `2024-01-01T12:00:00.000Z` |
| `${env:VAR_NAME}` | 环境变量 | `${env:APP_VERSION}` |
| `${context:key}` | 上下文变量 | `${context:user_id}` |
| `${request_id}` | 请求ID | `abc12345` |
| `${hostname}` | 主机名 | `server-01` |
| `${process_id}` | 进程ID | `12345` |

### 自定义解析器

```python
# 注册自定义解析器
def get_custom_value():
    return "custom_result"

langfuse_wrapper.register_field_resolver("custom", get_custom_value)

# 在配置中使用
config = {
    "name": "function-${custom}",
    "metadata": {"custom_field": "${custom}"}
}
```

## 初始化和配置

### 自动初始化

```python
# 导入模块时自动初始化
from src.utils.langfuse_init import initialize_langfuse_config

# 手动初始化
initialize_langfuse_config(
    config_file_path="config/langfuse_config.json",
    auto_reload=True
)
```

### 环境变量配置

```bash
# 启用 Langfuse
export LANGFUSE_ENABLED=true

# 应用配置
export APP_VERSION=1.0.0
export ENVIRONMENT=production
export DEPLOYMENT_ID=prod-001

# Langfuse 配置
export LANGFUSE_PUBLIC_KEY=your_public_key
export LANGFUSE_SECRET_KEY=your_secret_key
export LANGFUSE_HOST=https://cloud.langfuse.com
```

## 高级用法

### 1. 条件配置

```python
# 根据环境设置不同配置
import os

if os.getenv("ENVIRONMENT") == "production":
    langfuse_wrapper.update_global_config({
        "capture_input": False,  # 生产环境不捕获输入
        "metadata": {"env": "prod"}
    })
else:
    langfuse_wrapper.update_global_config({
        "capture_input": True,   # 开发环境捕获输入
        "metadata": {"env": "dev"}
    })
```

### 2. 动态标签

```python
# 根据函数参数动态添加标签
@langfuse_wrapper.dynamic_observe()
def process_with_model(data, model_name="default"):
    # 配置中可以使用 ${context:model_name}
    return f"Processed with {model_name}"

# 配置示例
langfuse_wrapper.update_function_config("process_with_model", {
    "tags": ["processing", "${context:model_name}"],
    "metadata": {"model": "${context:model_name}"}
})
```

### 3. 批量配置更新

```python
# 批量更新多个函数配置
function_configs = {
    "function1": {"name": "func1-${timestamp}", "tags": ["batch1"]},
    "function2": {"name": "func2-${timestamp}", "tags": ["batch2"]},
    "function3": {"name": "func3-${timestamp}", "tags": ["batch3"]}
}

for func_name, config in function_configs.items():
    langfuse_wrapper.update_function_config(func_name, config)
```

## 性能考虑

### 1. 配置缓存
- 配置解析结果会被缓存，避免重复解析
- 模板解析只在配置更新时进行

### 2. 异步支持
```python
# 异步函数同样支持动态配置
@langfuse_wrapper.dynamic_observe()
async def async_function(data):
    await asyncio.sleep(0.1)
    return f"Async result: {data}"
```

### 3. 错误处理
- 配置解析失败时会回退到默认配置
- 模板解析错误不会影响函数执行

## 故障排除

### 常见问题

1. **配置不生效**
   - 检查函数名是否正确
   - 确认配置文件格式正确
   - 验证环境变量是否设置

2. **模板解析失败**
   - 检查模板语法是否正确
   - 确认上下文变量是否存在
   - 查看日志中的解析错误信息

3. **性能问题**
   - 避免在高频函数中使用复杂模板
   - 考虑禁用输入/输出捕获
   - 使用静态配置替代动态配置

### 调试模式

```python
import logging

# 启用调试日志
logging.getLogger("src.utils.langfuse_config").setLevel(logging.DEBUG)
logging.getLogger("src.utils.langfuse_wrapper").setLevel(logging.DEBUG)
```

## 最佳实践

1. **配置组织**
   - 使用有意义的函数名和配置名
   - 将相关配置分组管理
   - 定期清理不用的配置

2. **模板使用**
   - 优先使用内置解析器
   - 避免在模板中使用敏感信息
   - 为复杂逻辑创建自定义解析器

3. **环境管理**
   - 为不同环境设置不同的配置文件
   - 使用环境变量控制配置行为
   - 在生产环境中禁用详细追踪

4. **监控和维护**
   - 定期检查配置文件的有效性
   - 监控配置更新的影响
   - 建立配置变更的审计机制

## API 参考

### LangfuseWrapper 方法

```python
# 动态观察装饰器
@langfuse_wrapper.dynamic_observe(name=None, capture_input=True, capture_output=True, **kwargs)

# 配置管理
langfuse_wrapper.update_function_config(function_name: str, config: Dict[str, Any])
langfuse_wrapper.update_global_config(config: Dict[str, Any])
langfuse_wrapper.load_config_from_file(config_path: str, auto_reload: bool = False)
langfuse_wrapper.register_field_resolver(name: str, resolver: Callable)
```

### 配置管理器方法

```python
from src.utils.langfuse_config import config_manager

# 获取配置
config = config_manager.get_config(function_name: str, context: Dict[str, Any] = None)

# 更新配置
config_manager.update_config(function_name: str, config: Union[Dict, ObserveConfig])
config_manager.update_global_config(config: Union[Dict, ObserveConfig])

# 文件操作
config_manager.load_config_from_file(config_path: str, auto_reload: bool = False)
config_manager.save_config_to_file(config_path: str)
```

## 示例项目

完整的使用示例请参考：
- `examples/langfuse_dynamic_config_example.py` - 基本使用示例
- `tests/test_langfuse_dynamic_config.py` - 测试用例
- `config/langfuse_config.json` - 配置文件示例