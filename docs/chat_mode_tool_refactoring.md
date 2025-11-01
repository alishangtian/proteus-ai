# Chat 模式工具调用重构说明

## 概述

本次重构将 `agentmodul == "chat"` 模式下的工具调用逻辑重构为参考 `react_agent` 的实现方式，提供统一、健壮的工具执行能力。

## 重构目标

1. **统一工具执行逻辑**：创建独立的 `ToolExecutor` 类，封装工具匹配和执行逻辑
2. **增强错误处理**：添加完整的重试机制，参考 react_agent 的实现
3. **完善事件通知**：发送工具执行的完整生命周期事件（开始、进度、重试、完成）
4. **提高代码复用性**：将工具执行逻辑从 main.py 中抽离，便于维护和测试

## 核心变更

### 1. 新增 `ToolExecutor` 类

**文件**: [`src/api/tool_executor.py`](proteus-ai/proteus/src/api/tool_executor.py)

**主要功能**:
- `execute_tool()`: 执行单个工具调用，包含完整的重试机制
- `execute_tool_calls()`: 批量执行多个工具调用
- `_execute_with_retry()`: 带重试的工具执行逻辑（参考 react_agent）
- `_send_complete_event()`: 发送工具完成事件

**关键特性**:
```python
class ToolExecutor:
    def __init__(self, stream_manager=None, max_retries: int = 3, retry_delay: float = 1.0):
        """
        Args:
            stream_manager: 流管理器，用于发送事件
            max_retries: 最大重试次数（默认3次，与 react_agent 一致）
            retry_delay: 重试延迟（默认1秒）
        """
```

### 2. 重构 main.py 中的 chat 模式

**文件**: [`main.py`](proteus-ai/proteus/main.py:1277-1300)

**变更前**（行 1277-1362）:
- 直接在 process_agent 函数中处理工具执行
- 手动管理工具导入、执行、错误处理
- 没有重试机制
- 事件发送不完整

**变更后**（行 1277-1300）:
```python
# 使用 ToolExecutor 执行工具调用
from src.api.tool_executor import ToolExecutor

# 创建工具执行器实例
tool_executor = ToolExecutor(
    stream_manager=stream_manager,
    max_retries=3,  # 最大重试次数
    retry_delay=1.0  # 重试延迟（秒）
)

# 将助手消息（包含工具调用）添加到messages
assistant_message = {
    "role": "assistant",
    "content": response_text if response_text else None,
    "tool_calls": tool_calls
}
messages.append(assistant_message)

# 批量执行工具调用并收集结果
tool_messages = await tool_executor.execute_tool_calls(
    tool_calls=tool_calls,
    chat_id=chat_id
)

# 将工具结果添加到messages
messages.extend(tool_messages)
```

## 与 React Agent 的对比

### React Agent 的工具执行流程

参考 [`react_agent.py:2013-2131`](proteus-ai/proteus/src/agent/react_agent.py:2013-2131)：

```python
async def _execute_tool_action(self, action, action_input, thought, chat_id, tool, user_query):
    # 1. 生成工具执行ID
    action_id = str(uuid.uuid4())
    
    # 2. 发送工具开始事件
    if stream:
        start_event = await create_action_start_event(...)
        progress_event = await create_tool_progress_event(...)
    
    # 3. 执行工具（带重试）
    retry_count = 0
    while retry_count <= tool.max_retries:
        try:
            if tool.is_async:
                observation = await tool.run(action_input)
            else:
                observation = tool.run(action_input)
            break
        except Exception as e:
            retry_count += 1
            # 发送重试事件
            if stream:
                event = await create_tool_retry_event(...)
            if retry_count > tool.max_retries:
                raise ToolExecutionError(...)
            await asyncio.sleep(tool.retry_delay)
    
    # 4. 发送完成事件
    if stream:
        event = await create_action_complete_event(...)
    
    return observation, thought, action_id
```

### ToolExecutor 的实现

我们的 `ToolExecutor` 采用了相同的设计模式：

1. **重试机制**：与 react_agent 一致的重试逻辑
2. **事件发送**：完整的生命周期事件（开始、进度、重试、完成）
3. **错误处理**：统一的异常捕获和错误消息格式
4. **工具匹配**：通过 `NodeConfigManager` 获取工具配置

## 优势

### 1. 代码简化
- **重构前**: 85 行工具执行代码
- **重构后**: 23 行（减少 73%）

### 2. 功能增强
- ✅ 添加重试机制（最多3次重试）
- ✅ 完整的事件通知（开始、进度、重试、完成）
- ✅ 统一的错误处理
- ✅ 更好的日志记录

### 3. 可维护性
- 工具执行逻辑集中在 `ToolExecutor` 类中
- 易于测试和调试
- 便于未来扩展（如添加工具记忆、性能监控等）

### 4. 一致性
- Chat 模式和 React Agent 模式使用相似的工具执行流程
- 统一的事件格式和错误处理

## 使用示例

### Chat 模式中的工具调用

```python
# 1. 加载工具定义
tools = load_tools_from_yaml(node_names=["serper_search", "web_crawler"])

# 2. 调用 LLM（带工具）
async for chunk in call_llm_api_with_tools_stream(
    messages=messages,
    tools=tools,
    model_name="deepseek-chat",
    request_id=chat_id,
):
    if chunk.get("type") == "tool_calls":
        tool_calls = chunk.get("tool_calls", [])
        
        # 3. 使用 ToolExecutor 执行工具
        tool_executor = ToolExecutor(stream_manager=stream_manager)
        tool_messages = await tool_executor.execute_tool_calls(
            tool_calls=tool_calls,
            chat_id=chat_id
        )
        
        # 4. 将结果添加到对话历史
        messages.extend(tool_messages)
```

## 测试建议

### 1. 单元测试
```python
# 测试 ToolExecutor 的基本功能
async def test_tool_executor_basic():
    executor = ToolExecutor(max_retries=3, retry_delay=0.1)
    result = await executor.execute_tool(
        tool_name="serper_search",
        tool_args={"query": "test"},
        chat_id="test-chat-id"
    )
    assert result is not None

# 测试重试机制
async def test_tool_executor_retry():
    executor = ToolExecutor(max_retries=2, retry_delay=0.1)
    # 模拟工具失败
    # 验证重试次数和错误消息
```

### 2. 集成测试
```python
# 测试 chat 模式的完整工具调用流程
async def test_chat_mode_with_tools():
    # 1. 创建 chat 会话
    # 2. 发送需要工具调用的请求
    # 3. 验证工具被正确执行
    # 4. 验证结果被正确返回
```

### 3. 手动测试
1. 启动服务：`python main.py`
2. 访问 chat 界面
3. 发送需要工具调用的请求，例如：
   - "搜索最新的 AI 新闻"（触发 serper_search）
   - "爬取 https://example.com 的内容"（触发 web_crawler）
4. 验证：
   - 工具执行事件正确发送
   - 重试机制在工具失败时生效
   - 最终结果正确返回

## 配置说明

### 工具重试配置

可以在创建 `ToolExecutor` 时自定义重试参数：

```python
tool_executor = ToolExecutor(
    stream_manager=stream_manager,
    max_retries=5,      # 增加重试次数
    retry_delay=2.0     # 增加重试延迟
)
```

### 工具定义

工具定义保持不变，仍然使用 YAML 配置：

```yaml
# src/nodes/agent_node_config.yaml
- name: serper_search
  type: serper_search
  class_name: SerperSearch
  description: "搜索引擎工具"
  # ... 其他配置
```

## 迁移指南

如果你有自定义的工具执行逻辑，可以按以下步骤迁移：

1. **创建 ToolExecutor 实例**
   ```python
   from src.api.tool_executor import ToolExecutor
   executor = ToolExecutor(stream_manager=your_stream_manager)
   ```

2. **替换工具执行代码**
   ```python
   # 旧代码
   for tool_call in tool_calls:
       # ... 手动执行工具 ...
   
   # 新代码
   tool_messages = await executor.execute_tool_calls(tool_calls, chat_id)
   messages.extend(tool_messages)
   ```

3. **移除手动的事件发送代码**
   - `ToolExecutor` 会自动发送所有必要的事件

## 未来扩展

基于当前的 `ToolExecutor` 架构，可以轻松添加以下功能：

1. **工具记忆**：参考 react_agent 的 `_process_tool_memory()`
2. **工具性能监控**：记录工具执行时间、成功率等
3. **工具权限控制**：基于用户角色限制工具访问
4. **工具缓存**：缓存工具执行结果，避免重复调用
5. **并行工具执行**：同时执行多个独立的工具调用

## 总结

本次重构成功地将 chat 模式的工具调用逻辑重构为参考 react_agent 的实现方式，实现了：

- ✅ 统一的工具执行接口
- ✅ 完整的重试机制
- ✅ 健壮的错误处理
- ✅ 完善的事件通知
- ✅ 更好的代码可维护性

这为后续的功能扩展和优化奠定了良好的基础。