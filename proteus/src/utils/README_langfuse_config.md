# Langfuse 配置管理器使用说明

## 概述

`LangfuseConfigManager` 是一个用于管理 Langfuse 观察配置的单例模式配置管理器。它支持自动查找默认配置文件、动态字段解析、配置合并和验证等功能。

## 主要特性

- **自动配置文件发现**: 无需手动指定配置文件路径，系统会自动查找默认配置文件
- **动态字段解析**: 支持在配置中使用动态表达式，如时间戳、环境变量等
- **配置合并**: 全局配置与函数特定配置的智能合并
- **单例模式**: 确保全局唯一实例，避免重复初始化
- **配置验证**: 自动验证配置的有效性

## 默认配置文件查找顺序

系统会按以下顺序查找 `langfuse_config.json` 配置文件：

1. **当前目录的同级目录中的 conf/langfuse_config.json**
   - 例如：`/project/sibling_dir/conf/langfuse_config.json`

2. **上级目录的同级目录中的 conf/langfuse_config.json**
   - 例如：`/parent_sibling/conf/langfuse_config.json`

3. **当前目录中的 conf/langfuse_config.json**
   - 例如：`/current_dir/conf/langfuse_config.json`

4. **当前目录中的子目录 */conf/langfuse_config.json**
   - 例如：`/current_dir/proteus/conf/langfuse_config.json`

5. **上级目录中的 conf/langfuse_config.json**
   - 例如：`/parent_dir/conf/langfuse_config.json`

如果未找到任何配置文件，系统将使用内置的默认配置。

## 使用方法

### 基本使用

```python
from utils.langfuse_config import LangfuseConfigManager

# 获取配置管理器实例（自动加载默认配置）
config_manager = LangfuseConfigManager()

# 获取函数的 Langfuse 配置
config = config_manager.get_config("chat_agent_run")

# 获取函数的完整配置（包含所有字段）
full_config = config_manager.get_full_config("chat_agent_run")
```

### 手动指定配置文件

```python
# 手动加载指定的配置文件
config_manager.load_config_from_file("/path/to/custom_config.json")

# 启用自动重载
config_manager.load_config_from_file("/path/to/config.json", auto_reload=True)
```

### 动态上下文

```python
# 使用动态上下文解析配置
context = {
    "query": "用户查询",
    "chat_id": "chat_123",
    "model_name": "gpt-4"
}

config = config_manager.get_config("process_agent", context)
```

### 配置验证

```python
# 验证当前配置
is_valid, errors = config_manager.validate_config()
if not is_valid:
    print("配置错误:", errors)
```

### 获取配置状态

```python
# 获取配置管理器状态
status = config_manager.get_config_status()
print(f"配置文件路径: {status['config_file_path']}")
print(f"函数配置数量: {len(status['function_configs'])}")
```

## 配置文件格式

配置文件采用 JSON 格式，包含全局配置和函数特定配置：

```json
{
  "global": {
    "capture_input": true,
    "capture_output": true,
    "metadata": {
      "service": "proteus-ai",
      "version": "1.0.0"
    },
    "tags": ["proteus", "ai-agent"]
  },
  "functions": {
    "chat_agent_run": {
      "name": "chat-agent-execution",
      "capture_input": true,
      "capture_output": true,
      "metadata": {
        "component": "chat_agent",
        "operation": "run"
      }
    },
    "process_agent": {
      "name": "${context.query}-${context.chat_id}",
      "capture_input": true,
      "capture_output": true
    }
  }
}
```

## 动态字段表达式

配置中支持以下动态表达式：

- `${timestamp}` - 当前时间戳
- `${env:VAR_NAME}` - 环境变量
- `${context:key}` 或 `${context.key}` - 上下文变量
- `${random_id}` - 随机ID
- `${uuid}` - UUID
- `${date}` - 当前日期
- `${time}` - 当前时间
- `${datetime}` - 当前日期时间

## 注意事项

1. **单例模式**: `LangfuseConfigManager` 使用单例模式，多次实例化会返回同一个对象
2. **线程安全**: 配置管理器的初始化是线程安全的
3. **配置合并**: 函数特定配置会与全局配置合并，函数配置优先级更高
4. **错误处理**: 配置文件加载失败时会自动回退到内置默认配置

## 示例项目结构

```
project/
├── proteus/
│   ├── conf/
│   │   └── langfuse_config.json  ← 会被自动发现
│   └── src/
│       └── utils/
│           └── langfuse_config.py
└── main.py
```

在这种结构下，从 `project/` 目录运行程序时，配置管理器会自动找到 `proteus/conf/langfuse_config.json` 配置文件。