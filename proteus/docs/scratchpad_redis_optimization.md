# Scratchpad Items Redis存取优化说明

## 概述

本次优化针对conversationid存在时从Redis中获取scratchpad_items信息的存取逻辑进行了改进，解决了原有实现中缺少时间管理和数据过期机制的问题。

## 问题分析

### 原有实现的问题
1. **无时间戳管理**: scratchpad_items数据没有有效期，可能导致过期数据堆积
2. **存储结构简单**: 使用Redis List结构，缺乏基于时间的高效查询能力
3. **无自动清理**: 没有自动清理过期数据的机制
4. **查询效率低**: 无法高效地按时间范围筛选数据

### 影响
- Redis存储空间可能无限增长
- 查询性能随数据量增加而下降
- 无法有效控制历史数据的时间范围

## 优化方案

### 1. 存储结构优化
**原有方案**: Redis List
```python
# 原有实现
redis_cache.rpush(redis_key, item_json)
history_data = redis_cache.rrange(redis_key, 5)
```

**优化方案**: Redis Sorted Set (有序集合)
```python
# 新实现
current_timestamp = time.time()
redis_cache.zadd(redis_key, {item_json: current_timestamp})
# 获取最新的size条记录，按时间升序返回（先发生的在前）
history_data = redis_cache.zrange(redis_key, start_index, end_index)
```

### 2. 时间戳管理
- **Score字段**: 使用Unix时间戳作为Sorted Set的score
- **时间精度**: 支持秒级时间精度
- **排序优势**: 自动按时间戳排序，最新数据score最高

### 3. 自动过期清理
```python
# 清理指定时间前的过期数据（默认12小时，可配置）
expire_timestamp = current_timestamp - (expire_hours * 60 * 60)
redis_cache.zremrangebyscore(redis_key, 0, expire_timestamp)
```

### 4. 数量限制机制
```python
# 限制总数量，只保留最新的100条记录
total_count = redis_cache.zcard(redis_key)
if total_count > 100:
    redis_cache.zremrangebyrank(redis_key, 0, total_count - 101)
```

## 新增Redis操作方法

### RedisCache类扩展
在`proteus/src/utils/redis_cache.py`中新增以下方法：

```python
def zadd(self, key: str, mapping: dict) -> bool:
    """向有序集合添加成员"""

def zrevrange(self, key: str, start: int = 0, end: int = -1, withscores: bool = False) -> List:
    """按分数从高到低获取有序集合成员"""

def zrange(self, key: str, start: int = 0, end: int = -1, withscores: bool = False) -> List:
    """按分数从低到高获取有序集合成员"""

def zremrangebyscore(self, key: str, min_score: float, max_score: float) -> int:
    """根据分数范围删除有序集合成员"""

def zcard(self, key: str) -> int:
    """获取有序集合成员数量"""

def zremrangebyrank(self, key: str, start: int, end: int) -> int:
    """根据排名范围删除有序集合成员"""
```

## 优化后的核心方法

### 1. _load_historical_scratchpad_items
```python
def _load_historical_scratchpad_items(self, conversation_id: str, size: int = 5, expire_hours: int = 12) -> List[ScratchpadItem]:
    """从Redis中加载指定时间内最近size条的历史scratchpad_items"""
    # 1. 清理指定时间前的过期数据（默认12小时，可配置）
    # 2. 获取最新的size条记录，按时间升序返回（先发生的在前）
    # 3. 解析并返回ScratchpadItem列表
```

**主要改进**:
- 支持自定义获取数量(`size`参数)
- 支持自定义过期时间(`expire_hours`参数，默认12小时)
- 自动清理过期数据
- 按时间戳升序返回最新数据（先发生的item在前，符合行为和叙事逻辑）

### 2. _save_scratchpad_item_to_redis
```python
def _save_scratchpad_item_to_redis(self, conversation_id: str, item: ScratchpadItem, expire_hours: int = 12):
    """将scratchpad_item保存到Redis有序集合中，使用时间戳作为score"""
    # 1. 转换为JSON格式
    # 2. 使用当前时间戳作为score保存到有序集合
    # 3. 清理过期数据（默认12小时，可配置）
    # 4. 限制总数量
```

**主要改进**:
- 使用时间戳作为score，支持时间范围查询
- 支持自定义过期时间(默认12小时，可配置)
- 自动清理过期数据
- 限制最大存储数量(100条)

## 性能优势

### 1. 查询效率
- **时间复杂度**: O(log(N)) vs 原来的O(N)
- **范围查询**: 支持高效的时间范围查询
- **排序优势**: 数据自动按时间戳排序，返回时按时间升序（符合叙事逻辑）

### 2. 存储管理
- **自动清理**: 定期清理过期数据
- **空间控制**: 限制最大存储数量
- **内存优化**: 减少Redis内存占用

### 3. 扩展性
- **灵活查询**: 支持按时间范围、数量等多维度查询
- **易于维护**: 清晰的数据结构和过期策略

## 配置参数

### 时间设置
- **过期时间**: 默认12小时 (可通过expire_hours参数调整)
- **最大数量**: 100条记录 (可通过修改代码调整)
- **时间精度**: 秒级

### 默认值
- **默认查询数量**: 5条
- **清理频率**: 每次保存时清理
- **排序方式**: 按时间戳升序(先发生的在前，符合行为和叙事逻辑)

## 兼容性

### 向后兼容
- 保持原有方法签名不变
- 新增可选参数使用默认值
- 现有调用代码无需修改

### 数据迁移
- 新旧数据格式兼容
- 自动处理JSON解析异常
- 渐进式数据结构迁移

## 测试验证

### 测试脚本
提供了完整的测试脚本`proteus/test_scratchpad_optimization.py`：

```bash
cd proteus
python test_scratchpad_optimization.py
```

### 测试覆盖
1. **Redis有序集合操作测试**
2. **scratchpad存储优化测试**
3. **时间过滤功能测试**
4. **数量限制功能测试**

## 使用示例

### 基本使用
```python
# 创建Agent时会自动加载历史数据
agent = Agent(
    tools=tools,
    prompt_template=template,
    conversation_id="conv_123"  # 指定会话ID
)

# 运行过程中会自动保存scratchpad_items
result = await agent.run(query="用户问题", chat_id="chat_123")
```

### 自定义查询
```python
# 加载更多历史记录（默认12小时）
historical_items = agent._load_historical_scratchpad_items("conv_123", size=10)

# 加载24小时内的历史记录
historical_items = agent._load_historical_scratchpad_items("conv_123", size=10, expire_hours=24)

# 手动保存特定项目（默认12小时过期）
agent._save_scratchpad_item_to_redis("conv_123", scratchpad_item)

# 手动保存特定项目（自定义过期时间）
agent._save_scratchpad_item_to_redis("conv_123", scratchpad_item, expire_hours=24)
```

## 监控建议

### Redis监控
- 监控有序集合的大小: `ZCARD conversation_history:*`
- 检查过期数据清理效果
- 观察内存使用情况

### 性能监控
- 查询响应时间
- 数据清理频率
- 存储空间占用

## 总结

本次优化通过引入Redis Sorted Set、时间戳管理和自动清理机制，显著改善了scratchpad_items的存取效率和数据管理能力。主要收益包括：

1. **性能提升**: 查询效率从O(N)提升到O(log(N))
2. **存储优化**: 自动清理过期数据，控制存储空间
3. **功能增强**: 支持时间范围查询、灵活的数量控制和可配置的过期时间
4. **参数化配置**: 过期时间可通过参数传递，默认12小时
5. **维护友好**: 自动化的数据管理，减少人工维护成本

这些改进为系统的长期稳定运行和扩展提供了坚实的基础。