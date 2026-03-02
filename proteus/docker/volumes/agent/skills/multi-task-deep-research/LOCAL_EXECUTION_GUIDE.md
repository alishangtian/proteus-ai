# 本地执行指南

## 概述
本文档提供在没有外部任务API的情况下使用多任务深度研究技能的替代方案。默认的`start_subtasks.py`脚本依赖于外部任务启动API (`https://127.0.0.1/task`)，如果该API不可用，可以使用以下替代方法。

## 方法一：手动执行模式

### 步骤1: 初始化研究项目
```python
from scripts.init_multi_task import init_multi_task_research

# 初始化项目（不自动启动）
task_dir = init_multi_task_research(
    task_name="您的研究主题",
    task_description="详细研究描述",
    subtasks=[
        {
            "name": "子任务1名称",
            "description": "子任务1描述",
            "dependencies": [],
            "query": "具体研究查询"
        },
        {
            "name": "子任务2名称", 
            "description": "子任务2描述",
            "dependencies": ["子任务1名称"],
            "query": "具体研究查询"
        }
    ],
    auto_start_subtasks=False,  # 重要：禁用自动启动
    task_folder_name="您的项目文件夹"
)
```

### 步骤2: 手动执行子任务
每个子任务位于`sub_tasks/[子任务目录]`中，包含以下文件：
- `task_plan.md` - 子任务规划
- `findings.md` - 研究发现（开始时为空）
- `progress.md` - 进度跟踪

**手动执行流程：**
1. 进入子任务目录
2. 阅读`task_plan.md`了解研究目标
3. 使用可用的工具（serper_search, web_crawler, python_execute）进行研究
4. 将研究发现写入`findings.md`
5. 更新`progress.md`中的进度状态

### 步骤3: 监控进度
```bash
python scripts/monitor_tasks.py /app/data/tasks/您的项目文件夹
```

### 步骤4: 整合结果
```bash
python scripts/integrate_results.py /app/data/tasks/您的项目文件夹
```

## 方法二：简化本地执行脚本

我们提供了一个简化的本地执行脚本 `local_research_runner.py`，它可以手动启动研究任务：

```python
# local_research_runner.py 使用示例
python local_research_runner.py /app/data/tasks/您的项目文件夹 --subtask "子任务1名称"
```

## 方法三：使用深度研究技能作为引擎

如果您已安装了`deep-research`技能，可以使用它作为研究引擎：

```python
# 在子任务目录中运行深度研究
import subprocess
import os

task_dir = "/app/data/tasks/您的项目"
subtask_dir = os.path.join(task_dir, "sub_tasks", "子任务目录")

# 读取研究查询
config_path = os.path.join(task_dir, "task_config.json")
with open(config_path, 'r') as f:
    config = json.load(f)

for subtask in config['subtasks']:
    if subtask['directory'] == '子任务目录':
        research_query = subtask['query']
        break

# 使用deep-research技能执行研究（需根据实际接口调整）
print(f"执行研究: {research_query}")
# 这里需要调用deep-research技能的实际接口
```

## 故障排除

### 问题1: API连接失败
**症状**: `start_subtasks.py`报连接错误
**解决方案**: 
1. 确认任务API服务是否运行 (`https://127.0.0.1/task`)
2. 检查`task_config.json`中的`api_config`设置
3. 使用手动执行模式（方法一）

### 问题2: 认证失败
**症状**: API返回401或403错误
**解决方案**:
1. 检查`auth_token`是否正确
2. 使用本地执行模式绕过API

### 问题3: 子任务进度不更新
**症状**: 监控显示子任务状态不变
**解决方案**:
1. 手动更新子任务的`progress.md`文件
2. 运行`monitor_tasks.py`重新计算进度

## 最佳实践

1. **先测试后扩展**: 先创建小型测试项目验证工作流程
2. **定期备份**: 定期备份`task_config.json`和重要发现
3. **增量执行**: 先完成一个子任务，验证流程后再扩展
4. **文档记录**: 在`master_task_plan.md`中记录所有手动步骤

## 高级配置

### 自定义研究模板
您可以通过修改`templates/`目录下的模板文件来自定义：
- `sub_task_template.md` - 子任务规划模板
- `master_task_plan.md` - 主任务规划模板
- `master_findings.md` - 研究发现整合模板

### 质量保证检查
即使手动执行，也应遵循质量保证流程：
1. 每个子任务完成后进行质量检查
2. 确保研究发现有可靠来源支持
3. 使用多源验证关键发现
4. 在`master_findings.md`中记录质量控制过程

---

*最后更新: 2026-02-26*
*技能版本: multi-task-deep-research v1.2.0*