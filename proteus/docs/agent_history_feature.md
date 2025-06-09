# Agent智能体迭代历史信息功能

## 概述

Agent功能已经优化，在初始化时新增了智能体迭代历史信息参数。该功能能够从Redis中获取最近5轮的历史信息，为Agent提供上下文记忆能力，提升对话连续性和智能化程度。

## 功能特性

### 1. 历史信息自动加载
- 在Agent初始化时，会根据`conversation_id`从Redis中自动加载最近5轮的历史迭代信息
- 历史信息来源于之前保存的`scratchpad_items`
- 支持跨会话的历史信息持久化

### 2. 实时历史信息保存
- Agent每次迭代的思考过程、执行操作和结果都会实时保存到Redis
- 保存格式为JSON，便于序列化和反序列化
- 错误信息也会被记录，便于问题排查

### 3. Redis存储结构
- **存储键格式**: `conversation_history:{conversation_id}`
- **数据结构**: Redis List（按时间倒序，最新的在前面）
- **数据格式**: JSON字符串，包含ScratchpadItem的所有字段

## 类和方法改动

### AgentConfiguration类
新增参数：
```python
conversation_id: str = None           # 会话ID，用于获取历史信息
historical_scratchpad_items: List[ScratchpadItem] = None  # 历史迭代信息
```

### Agent类
新增参数：
```python
conversation_id: str = None  # 会话ID参数
```

新增方法：
```python
def _load_historical_scratchpad_items(self, conversation_id: str) -> List[ScratchpadItem]
    """从Redis中加载最近5轮的历史scratchpad_items"""

def _save_scratchpad_item_to_redis(self, conversation_id: str, item: ScratchpadItem)
    """将scratchpad_item保存到Redis"""
```

### PagenticTeam类
新增参数：
```python
conversation_id: str = None  # 会话ID，用于获取历史迭代信息
```

### TeamRunnerNode类
新增参数：
```python
conversation_id (str, optional): 会话ID，用于获取历史迭代信息
```

## 使用方式

### 1. 基础使用

```python
from src.agent.agent import Agent, AgentConfiguration
from src.manager.multi_agent_manager import TeamRole

# 创建带有历史信息的Agent配置
config = AgentConfiguration(
    role_type=TeamRole.PLANNER,
    prompt_template=your_prompt_template,
    model_name="deepseek-chat",
    conversation_id="your_conversation_id",  # 关键参数
    # 其他参数...
)

# 创建Agent实例
agent = Agent(
    tools=config.tools,
    prompt_template=config.prompt_template,
    conversation_id=config.conversation_id,  # 传递会话ID
    # 其他参数...
)

# 运行Agent
result = await agent.run(query, chat_id)
```

### 2. 团队使用

```python
from src.agent.pagentic_team import PagenticTeam

# 创建团队实例
team = PagenticTeam(
    tools_config=tools_config,
    team_rules=team_rules,
    conversation_id="team_conversation_001"  # 传递会话ID
)

# 运行团队
await team.run(query, chat_id)
```

### 3. 通过TeamRunner使用

```python
# 在调用TeamRunner时传递conversation_id参数
params = {
    "config_path": "deep_research_team.yaml",
    "query": "研究人工智能发展趋势",
    "conversation_id": "research_conversation_001"
}

result = await team_runner.execute(params)
```

## Redis配置

确保以下环境变量已正确配置：

```bash
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=your_password  # 可选
```

## 数据结构

### ScratchpadItem结构
```python
@dataclass
class ScratchpadItem:
    thought: str = ""              # 思考内容
    action: str = ""               # 执行的操作
    observation: str = ""          # 操作结果
    is_origin_query: bool = False  # 是否为原始查询
```

### Redis存储示例
```json
{
    "thought": "用户询问如何学习Python",
    "action": "chat",
    "observation": "我理解了用户的需求，准备制定学习计划",
    "is_origin_query": true
}
```

## 最佳实践

### 1. conversation_id命名规范
- 使用有意义的前缀，如：`user_123_session_001`
- 避免特殊字符，推荐使用字母、数字和下划线
- 保持唯一性，避免不同对话使用相同ID

### 2. 历史信息管理
- 系统自动维护最近5轮历史，无需手动清理
- 长期存储可考虑定期归档机制
- 重要对话可使用专门的conversation_id进行标识

### 3. 异常处理
- Redis连接失败时，Agent仍可正常工作，只是不会加载历史信息
- 历史数据解析失败时，系统会记录警告并跳过损坏的数据
- 建议在生产环境中监控Redis连接状态

## 示例代码

完整的使用示例请参考：`proteus-ai/proteus/examples/agent_with_history_example.py`

## 注意事项

1. **Redis依赖**: 此功能依赖Redis服务，确保Redis正常运行
2. **性能考虑**: 历史信息加载会增加初始化时间，在高并发场景下注意性能影响
3. **数据安全**: conversation_id请避免包含敏感信息
4. **兼容性**: 现有代码无需修改，新参数为可选参数

## 故障排查

### 常见问题

1. **无法加载历史信息**
   - 检查Redis连接配置
   - 确认conversation_id是否正确
   - 查看日志中的错误信息

2. **历史信息不完整**
   - 检查Redis存储是否有数据丢失
   - 确认JSON序列化是否正常

3. **性能问题**
   - 监控Redis响应时间
   - 考虑Redis集群或优化配置

### 日志级别
```python
# 开启DEBUG日志查看详细信息
logging.getLogger("src.agent.agent").setLevel(logging.DEBUG)
```

## 版本历史

- **v1.0.0**: 初始版本，支持基础历史信息功能
- 未来计划：支持历史信息压缩、智能摘要等高级功能

---

更多技术细节请参考源代码注释和相关文档。