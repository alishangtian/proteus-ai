# Chat 模式工具调用使用指南

本文档介绍如何在 Chat 模式下使用工具调用功能。

## 功能概述

Chat 模式现已支持工具调用功能，允许 LLM 模型在对话过程中调用外部工具来完成任务。工具定义自动从 YAML 配置文件中加载，无需手动编写。

## API 接口

### POST /chat

创建新的聊天会话，支持工具调用。

#### 新增参数

- **enable_tools** (bool, 可选): 是否启用工具调用功能，默认为 `false`
- **tool_choice** (List[str], 可选): 指定要使用的工具列表（节点名称），如果不指定则加载所有可用工具

#### 请求示例

```json
{
  "text": "帮我搜索一下北京今天的天气",
  "modul": "chat",
  "model_name": "deepseek-chat",
  "enable_tools": true,
  "tool_choice": ["SerperSearchNode", "WeatherForecastNode"]
}
```

## 工作流程

### 1. 不启用工具调用（默认行为）

```json
{
  "text": "你好，请介绍一下自己",
  "modul": "chat",
  "model_name": "deepseek-chat",
  "enable_tools": false
}
```

模型将直接回答问题，不会调用任何工具。

### 2. 启用所有工具

```json
{
  "text": "帮我搜索最新的AI新闻",
  "modul": "chat",
  "model_name": "deepseek-chat",
  "enable_tools": true
}
```

系统将加载所有可用的工具，模型可以根据需要选择合适的工具调用。

### 3. 指定特定工具

可以使用节点名称（YAML key）或工具类型（type 字段）来指定工具：

```json
{
  "text": "查询杭州的天气并搜索相关新闻",
  "modul": "chat",
  "model_name": "deepseek-chat",
  "enable_tools": true,
  "tool_choice": [
    "SerperSearchNode",
    "WeatherForecastNode"
  ]
}
```

或者使用 type 字段：

```json
{
  "text": "查询杭州的天气并搜索相关新闻",
  "modul": "chat",
  "model_name": "deepseek-chat",
  "enable_tools": true,
  "tool_choice": [
    "serper_search",
    "weather_forecast"
  ]
}
```

系统只会加载指定的工具，模型只能从这些工具中选择。

## 可用工具列表

工具定义来自 [`agent_node_config.yaml`](../src/nodes/agent_node_config.yaml)，常用工具包括：

| 节点名称（Key） | 工具类型（Type） | 描述 |
|----------------|-----------------|------|
| SerperSearchNode | serper_search | Serper搜索引擎，搜索最新信息 |
| WeatherForecastNode | weather_forecast | 通过经纬度获取天气信息 |
| PythonExecuteNode | python_execute | 执行Python代码 |
| FileReadNode | file_read | 读取文件内容 |
| FileWriteNode | file_write | 写入文件 |
| ArxivSearchNode | arxiv_search | 搜索Arxiv论文 |
| SerperWebCrawlerNode | web_crawler | 网页爬虫 |
| ApiCallNode | api_call | 通用API调用 |
| DbQueryNode | db_query | 数据库查询 |
| MCPClientNode | mcp_client | MCP客户端工具调用 |

**注意：** `tool_choice` 参数可以使用节点名称（Key）或工具类型（Type）来指定工具。

完整列表请查看配置文件。

## 前端集成示例

### JavaScript 调用示例

```javascript
// 创建支持工具调用的聊天会话
async function createChatWithTools(userMessage, tools = null) {
  const response = await fetch('/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      text: userMessage,
      modul: 'chat',
      model_name: 'deepseek-chat',
      enable_tools: true,
      tool_choice: tools, // null 表示使用所有工具
      conversation_id: getCurrentConversationId(),
    }),
  });
  
  const data = await response.json();
  return data.chat_id;
}

// 使用示例 - 使用节点名称
const chatId = await createChatWithTools(
  "帮我搜索北京的天气",
  ["SerperSearchNode", "WeatherForecastNode"]
);

// 或者使用工具类型
const chatId2 = await createChatWithTools(
  "帮我搜索北京的天气",
  ["serper_search", "weather_forecast"]
);

// 监听SSE流
const eventSource = new EventSource(`/stream/${chatId}`);
eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('收到消息:', data);
};
```

## 工具调用流程

1. **用户发送请求**
   - 用户通过 `/chat` 接口发送消息
   - 指定 `enable_tools: true` 启用工具调用

2. **系统加载工具**
   - 根据 `tool_choice` 参数加载指定工具
   - 如果未指定，则加载所有可用工具
   - 工具定义自动从 YAML 配置转换为 OpenAI 格式

3. **模型分析并决定**
   - LLM 分析用户请求
   - 决定是否需要调用工具
   - 如果需要，选择合适的工具并生成参数

4. **工具调用信息返回**
   - 系统通过 SSE 流返回工具调用信息
   - 前端可以显示工具调用的详情
   - 格式：`🔧 调用工具: tool_name\n参数: {...}`

5. **保存对话历史**
   - 用户消息、助手回复和工具调用信息都会保存到 Redis
   - 支持会话历史查询和回放

## 响应格式

### 普通内容

```json
{
  "event": "agent_complete",
  "data": {
    "content": "这是模型的回复内容"
  }
}
```

### 工具调用信息

```json
{
  "event": "agent_complete",
  "data": {
    "content": "\n\n🔧 调用工具: serper_search\n参数: {\"query\": \"北京天气\"}\n"
  }
}
```

### 完成事件

```json
{
  "event": "complete",
  "data": {}
}
```

## 对话历史格式

启用工具调用后，对话历史会包含工具调用信息：

```json
{
  "timestamp": 1234567890.123,
  "type": "assistant",
  "content": "根据搜索结果，北京今天天气晴朗...",
  "usage": {
    "prompt_tokens": 100,
    "completion_tokens": 50,
    "total_tokens": 150
  },
  "tool_calls": [
    {
      "id": "call_xxx",
      "type": "function",
      "function": {
        "name": "serper_search",
        "arguments": "{\"query\": \"北京天气\"}"
      }
    }
  ]
}
```

## 注意事项

1. **模型支持**
   - 确保使用的模型支持工具调用功能（如 deepseek-chat）
   - 不支持工具调用的模型会忽略工具定义

2. **工具配置**
   - 工具定义来自 `agent_node_config.yaml`
   - 确保配置文件格式正确
   - 工具的 `description` 和 `parameters` 要清晰准确

3. **性能考虑**
   - 加载所有工具可能会增加 token 消耗
   - 建议根据场景指定必要的工具
   - 使用 `tool_choice` 参数限制工具范围

4. **错误处理**
   - 如果工具加载失败，系统会回退到普通 chat 模式
   - 错误信息会记录到日志中
   - 前端会收到错误事件通知

5. **安全性**
   - 某些工具（如 PythonExecuteNode）可能执行危险操作
   - 建议在生产环境中谨慎启用
   - 可以通过 `tool_choice` 限制可用工具

## 示例场景

### 场景1: 智能搜索助手

```json
{
  "text": "帮我搜索最新的深度学习论文",
  "modul": "chat",
  "enable_tools": true,
  "tool_choice": ["SerperSearchNode", "ArxivSearchNode"]
}
```

模型会自动选择合适的搜索工具来完成任务。

### 场景2: 数据分析助手

```json
{
  "text": "读取sales.csv文件并分析销售趋势",
  "modul": "chat",
  "enable_tools": true,
  "tool_choice": ["FileReadNode", "PythonExecuteNode"]
}
```

模型会先读取文件，然后使用 Python 进行数据分析。

### 场景3: 网页信息提取

```json
{
  "text": "访问https://example.com并提取主要内容",
  "modul": "chat",
  "enable_tools": true,
  "tool_choice": ["SerperWebCrawlerNode"]
}
```

模型会使用网页爬虫工具提取内容。

## 相关文件

- [`main.py`](../main.py) - Chat 模式实现
- [`llm_api.py`](../src/api/llm_api.py) - 工具调用 API
- [`tool_converter.py`](../src/utils/tool_converter.py) - 工具转换器
- [`agent_node_config.yaml`](../src/nodes/agent_node_config.yaml) - 工具配置
- [`TOOL_CALLING_README.md`](../examples/TOOL_CALLING_README.md) - 工具调用详细文档

## 故障排查

### 问题1: 工具未被调用

**可能原因:**
- 模型不支持工具调用
- 工具描述不够清晰
- 用户请求不明确

**解决方案:**
- 使用支持工具调用的模型（如 deepseek-chat）
- 优化工具的 description 字段
- 提供更明确的用户指令

### 问题2: 工具加载失败

**可能原因:**
- YAML 配置文件格式错误
- 工具节点名称不存在
- 文件路径错误

**解决方案:**
- 检查 YAML 配置文件语法
- 确认节点名称正确
- 检查日志获取详细错误信息

### 问题3: Token 消耗过大

**可能原因:**
- 加载了过多工具
- 工具描述过于详细

**解决方案:**
- 使用 `tool_choice` 限制工具数量
- 简化工具描述
- 只在必要时启用工具调用