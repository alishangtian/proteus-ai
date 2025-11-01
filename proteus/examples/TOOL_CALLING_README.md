# 工具调用 API 使用指南

本文档介绍如何使用 `llm_api.py` 中新增的工具调用功能，以及如何使用工具转换器将 YAML 节点配置转换为 OpenAI 工具格式。

## 功能概述

新增了两个支持工具调用的 API 函数：

1. **`call_llm_api_with_tools`** - 非流式工具调用
2. **`call_llm_api_with_tools_stream`** - 流式工具调用

这两个函数都支持 OpenAI 工具调用规范，可以让 LLM 模型调用外部工具来完成任务。

## 函数签名

### 非流式调用

```python
async def call_llm_api_with_tools(
    messages: List[Dict[str, str]],
    tools: List[Dict] = None,
    request_id: str = None,
    temperature: float = 0.1,
    model_name: str = None,
) -> Tuple[Dict, Dict]:
    """
    返回:
        - message_dict: 完整的消息对象，包含 content 和可能的 tool_calls
        - usage_dict: token 使用信息
    """
```

### 流式调用

```python
async def call_llm_api_with_tools_stream(
    messages: List[Dict[str, str]],
    tools: List[Dict] = None,
    request_id: str = None,
    temperature: float = 0.1,
    model_name: str = None,
) -> AsyncGenerator[Dict[str, Union[str, Dict, List]], None]:
    """
    生成器返回:
        - type: 'content' | 'tool_calls' | 'usage' | 'error'
        - content: 文本内容（当type为content时）
        - tool_calls: 工具调用列表（当type为tool_calls时）
        - usage: token使用信息（当type为usage时）
        - error: 错误信息（当type为error时）
    """
```

## 工具定义格式

工具定义遵循 OpenAI 的规范：

```python
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get weather of a location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The city and state, e.g. San Francisco, CA",
                    }
                },
                "required": ["location"]
            },
        }
    },
]
```

## 使用示例

### 非流式调用示例

```python
import asyncio
from src.api.llm_api import call_llm_api_with_tools

async def example():
    # 定义工具
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get weather of a location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "城市和省份，例如：杭州, 浙江",
                        }
                    },
                    "required": ["location"]
                },
            }
        },
    ]
    
    # 第一轮对话
    messages = [{"role": "user", "content": "杭州天气怎么样？"}]
    message, usage = await call_llm_api_with_tools(
        messages=messages,
        tools=tools,
        request_id="req-001",
        model_name="deepseek-chat"
    )
    
    # 检查是否有工具调用
    if message.get('tool_calls'):
        tool_call = message['tool_calls'][0]
        
        # 将模型响应添加到消息历史
        messages.append(message)
        
        # 执行工具并添加结果
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call['id'],
            "content": "24℃"
        })
        
        # 第二轮对话
        message, usage = await call_llm_api_with_tools(
            messages=messages,
            tools=tools,
            request_id="req-002",
            model_name="deepseek-chat"
        )
        
        print(f"最终回复: {message.get('content')}")

asyncio.run(example())
```

### 流式调用示例

```python
import asyncio
from src.api.llm_api import call_llm_api_with_tools_stream

async def example_stream():
    tools = [...]  # 同上
    
    messages = [{"role": "user", "content": "北京天气怎么样？"}]
    
    # 收集响应
    full_content = ""
    tool_calls = None
    
    async for chunk in call_llm_api_with_tools_stream(
        messages=messages,
        tools=tools,
        request_id="req-stream-001",
        model_name="deepseek-chat"
    ):
        if chunk["type"] == "content":
            content = chunk["content"]
            full_content += content
            print(content, end="", flush=True)
        
        elif chunk["type"] == "tool_calls":
            tool_calls = chunk["tool_calls"]
            print(f"\n工具调用: {tool_calls}")
        
        elif chunk["type"] == "usage":
            print(f"\nToken使用: {chunk['usage']}")
        
        elif chunk["type"] == "error":
            print(f"\n错误: {chunk['error']}")
    
    # 处理工具调用
    if tool_calls:
        # 构建消息
        messages.append({
            "role": "assistant",
            "content": full_content if full_content else None,
            "tool_calls": tool_calls
        })
        
        # 添加工具结果
        messages.append({
            "role": "tool",
            "tool_call_id": tool_calls[0]['id'],
            "content": "15℃, 晴天"
        })
        
        # 继续对话...

asyncio.run(example_stream())
```

## 完整工作流程

1. **用户提问** → 发送包含用户消息和工具定义的请求
2. **模型响应** → 模型决定是否需要调用工具
   - 如果需要：返回 `tool_calls`
   - 如果不需要：直接返回 `content`
3. **执行工具** → 根据 `tool_calls` 执行相应的工具函数
4. **返回结果** → 将工具执行结果添加到消息历史
5. **最终回复** → 再次调用 API，模型基于工具结果生成最终回复

## 消息格式说明

### 用户消息
```python
{"role": "user", "content": "用户的问题"}
```

### 助手消息（带工具调用）
```python
{
    "role": "assistant",
    "content": None,  # 可能为空
    "tool_calls": [
        {
            "id": "call_xxx",
            "type": "function",
            "function": {
                "name": "get_weather",
                "arguments": '{"location": "杭州, 浙江"}'
            }
        }
    ]
}
```

### 工具消息
```python
{
    "role": "tool",
    "tool_call_id": "call_xxx",
    "content": "24℃"
}
```

## 注意事项

1. **模型支持**：确保使用的模型支持工具调用功能（如 deepseek-chat）
2. **工具定义**：工具的 `description` 和 `parameters` 要清晰准确，帮助模型理解何时调用
3. **错误处理**：始终检查响应中的 `error` 类型，妥善处理异常情况
4. **消息历史**：保持完整的消息历史，包括工具调用和结果
5. **流式处理**：流式调用时需要累积 `tool_calls` 的各个部分

## 运行示例

```bash
cd proteus-ai/proteus
python examples/tool_calling_example.py
```

## 工具转换器使用

### 概述

项目提供了 [`ToolConverter`](../src/utils/tool_converter.py) 类，可以自动将 YAML 节点配置转换为 OpenAI 工具格式，无需手动编写工具定义。

### 基本用法

```python
from src.utils.tool_converter import load_tools_from_yaml

# 方式1: 转换所有节点
tools = load_tools_from_yaml()

# 方式2: 只转换指定节点
tools = load_tools_from_yaml(
    node_names=["SerperSearchNode", "WeatherForecastNode"]
)

# 方式3: 排除某些节点
tools = load_tools_from_yaml(
    exclude_nodes=["UserInputNode", "HandoffNode"]
)
```

### 高级用法

```python
from src.utils.tool_converter import ToolConverter

# 创建转换器实例
converter = ToolConverter()

# 转换所有节点
all_tools = converter.convert_all_nodes_to_tools()

# 转换指定节点
specific_tools = converter.convert_specific_nodes_to_tools(
    ["SerperSearchNode", "ArxivSearchNode"]
)

# 根据函数名获取单个工具
tool = converter.get_tool_by_name("serper_search")
```

### 结合 LLM API 使用

```python
import asyncio
from src.utils.tool_converter import load_tools_from_yaml
from src.api.llm_api import call_llm_api_with_tools

async def example():
    # 加载工具
    tools = load_tools_from_yaml(
        node_names=["SerperSearchNode", "WeatherForecastNode"]
    )
    
    # 调用 API
    messages = [{"role": "user", "content": "北京天气怎么样？"}]
    message, usage = await call_llm_api_with_tools(
        messages=messages,
        tools=tools,
        model_name="deepseek-chat"
    )
    
    # 处理响应...

asyncio.run(example())
```

### YAML 配置格式

工具转换器会自动解析 [`agent_node_config.yaml`](../src/nodes/agent_node_config.yaml) 中的节点定义：

```yaml
SerperSearchNode:
  type: "serper_search"
  name: "Serper搜索引擎"
  description: "Serper搜索引擎节点，可以搜索最新信息"
  params:
    query:
      type: "str"
      required: true
      description: "搜索关键词"
      example: "人工智能最新进展"
    max_results:
      type: "int"
      required: false
      default: 10
      description: "最大搜索结果数量"
```

转换后的 OpenAI 工具格式：

```json
{
  "type": "function",
  "function": {
    "name": "serper_search",
    "description": "Serper搜索引擎节点，可以搜索最新信息",
    "parameters": {
      "type": "object",
      "properties": {
        "query": {
          "type": "string",
          "description": "搜索关键词",
          "example": "人工智能最新进展"
        },
        "max_results": {
          "type": "integer",
          "description": "最大搜索结果数量 (默认值: 10)"
        }
      },
      "required": ["query"]
    }
  }
}
```

### 类型映射

工具转换器会自动将 Python 类型映射到 JSON Schema 类型：

| Python 类型 | JSON Schema 类型 |
|------------|-----------------|
| str        | string          |
| int        | integer         |
| float      | number          |
| bool       | boolean         |
| dict       | object          |
| list       | array           |
| tuple      | array           |

## 相关文件

- [`llm_api.py`](../src/api/llm_api.py) - API 实现
- [`tool_converter.py`](../src/utils/tool_converter.py) - 工具转换器实现
- [`agent_node_config.yaml`](../src/nodes/agent_node_config.yaml) - 节点配置文件
- [`tool_calling_example.py`](./tool_calling_example.py) - 工具调用示例
- [`tool_converter_example.py`](./tool_converter_example.py) - 工具转换器示例