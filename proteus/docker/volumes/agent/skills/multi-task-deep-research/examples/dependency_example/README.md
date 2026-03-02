# 依赖关系管理示例

此示例展示多任务深度研究技能中的依赖关系管理功能。

## 示例场景：市场研究项目

假设我们要进行一个市场研究项目，包含以下子任务：

1. **市场分析** - 分析目标市场的基本情况
2. **竞品分析** - 分析主要竞争对手（依赖市场分析）
3. **用户研究** - 研究目标用户需求（依赖市场分析）
4. **战略规划** - 制定市场进入战略（依赖所有前三项分析）

## 依赖关系图

```
市场分析
    ├── 竞品分析
    ├── 用户研究
    └── 战略规划 (依赖所有三个)
```

## 创建带有依赖关系的任务

```python
from scripts.init_multi_task import init_multi_task_research

subtasks = [
    {
        "name": "市场分析",
        "description": "分析目标市场规模、增长趋势、细分市场",
        "dependencies": [],  # 无依赖
        "query": "2025年AI教育市场规模、增长趋势、主要细分市场分析"
    },
    {
        "name": "竞品分析", 
        "description": "分析主要竞争对手的产品、定价、市场份额",
        "dependencies": ["市场分析"],  # 依赖市场分析
        "query": "AI教育领域主要竞争对手分析：产品特点、定价策略、市场份额"
    },
    {
        "name": "用户研究",
        "description": "研究目标用户需求、痛点、购买行为",
        "dependencies": ["市场分析"],  # 依赖市场分析
        "query": "AI教育产品目标用户需求分析：用户画像、痛点、购买决策因素"
    },
    {
        "name": "战略规划",
        "description": "基于分析制定市场进入战略",
        "dependencies": ["市场分析", "竞品分析", "用户研究"],  # 依赖所有前三项
        "query": "基于市场、竞品和用户分析，制定AI教育产品市场进入战略"
    }
]

# 初始化任务
task_dir = init_multi_task_research(
    task_name="AI教育产品市场研究",
    task_description="全面研究AI教育产品市场，为新产品上市提供决策支持",
    subtasks=subtasks,
    auto_start_subtasks=False  # 手动控制启动
)
```

## 启动顺序

根据依赖关系，任务启动顺序为：
1. 市场分析 (无依赖)
2. 竞品分析 (依赖市场分析)
3. 用户研究 (依赖市场分析)
4. 战略规划 (依赖所有前三项)

## 启动命令

```bash
# 顺序启动模式 (默认)
python /app/.proteus/skills/multi-task-deep-research/scripts/start_subtasks.py /app/data/tasks/AI教育产品市场研究

# 顺序等待模式 (每个任务完成后才启动下一个)
python /app/.proteus/skills/multi-task-deep-research/scripts/start_subtasks.py /app/data/tasks/AI教育产品市场研究 --wait
```

## 监控依赖状态

```bash
python /app/.proteus/skills/multi-task-deep-research/scripts/monitor_tasks.py /app/data/tasks/AI教育产品市场研究
```

## 预期输出

监控工具将显示：
- 任务按依赖关系排序
- 依赖任务的状态检查
- 无效依赖警告（如有）
- 任务进度和完成状态

## 关键特性

1. **自动拓扑排序**：系统自动计算依赖执行顺序
2. **循环依赖检测**：检测并警告循环依赖
3. **依赖状态验证**：检查依赖任务是否完成
4. **灵活启动模式**：支持等待或不等待依赖完成
5. **详细状态监控**：实时显示依赖关系和任务状态

## 注意事项

1. 确保依赖的任务名称正确
2. 避免创建循环依赖
3. 对于需要前序任务输出的情况，使用`--wait`模式
4. 定期使用监控工具检查依赖状态
