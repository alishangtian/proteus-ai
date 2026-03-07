---
name: multitask-deep-research
version: "3.0.0-optimized"
description: 多任务深度研究基础功能模块 - 提供原子性的文件操作功能，专注文件系统规划与数据组织，供外部系统调用构建自定义研究流程。
user-invocable: true
allowed-tools:
  - python_execute
  - serper_search
  - web_crawler
---

# 多任务深度研究基础功能模块

## 🎯 核心理念

**专注文件操作，不涉研究逻辑**

本技能提供纯粹的**文件系统操作功能**，用于管理多任务研究的目录结构、文件组织和数据记录。所有研究逻辑、决策流程和进度控制均由**外部系统（上帝视角）**负责。

### 设计原则
1. **极简接口** - 6个核心函数，功能明确
2. **文件中心** - 只处理文件创建、读写、组织
3. **标准化响应** - 统一返回格式 `{"ok": bool, "data": {}, "error": ""}`
4. **模板灵活** - 支持自定义文件模板

## 📦 核心功能 (6个函数)

### 1. `init_workspace()` - 初始化工作区
```python
result = init_workspace(
    workspace_path="/app/data/workspace/my_research",
    plan_content="# 研究标题\n\n## 目标",
    template_path=None,  # 可选，使用默认模板
    overwrite=False      # 可选，是否覆盖已存在的工作区
)
```

**功能**: 创建研究目录结构，初始化标准文件

**文件结构**:
```
{workspace_path}/
├── task_plan.md          # 任务规划
├── findings.md           # 总发现记录
├── progress.md           # 总进度日志
├── .workspace_meta.json  # 元数据
├── subtasks/             # 子任务目录
└── reports/              # 报告目录
```

### 2. `add_subtasks()` - 添加子任务
```python
result = add_subtasks(
    workspace_path="/app/data/workspace/my_research",
    subtasks=[
        {
            "id": "literature_review",
            "name": "文献综述",           # 可选
            "description": "收集分析相关文献"  # 可选
        }
    ],
    template_path=None  # 可选，子任务模板路径
)
```

**功能**: 创建子任务目录和文件

**创建的子任务结构**:
```
subtasks/{id}/
├── task_plan.md      # 子任务规划
├── findings.md       # 子任务发现
└── progress.md       # 子任务进度
```

### 3. `log_finding()` - 记录研究发现
```python
result = log_finding(
    workspace_path="/app/data/workspace/my_research",
    target="subtasks/literature_review",  # 或 "root"
    title="关键发现标题",
    content="发现详细内容...",
    metadata={  # 可选
        "category": "技术分析",
        "sources": ["文献1", "报告2"],
        "confidence": "high"
    }
)
```

**功能**: 将研究发现追加到指定文件

**记录格式**:
```markdown
## 发现标题

**时间:** 2026-03-07 12:00:00
**category:** 技术分析
**confidence:** high

发现详细内容...

**sources:**
- 文献1
- 报告2

---
```

### 4. `update_status()` - 更新子任务状态
```python
result = update_status(
    workspace_path="/app/data/workspace/my_research",
    subtask_id="literature_review",
    status="working",  # pending/working/completed
    progress=75,       # 0-100
    note="已完成数据收集"  # 可选
)
```

**功能**: 更新子任务的进度状态

### 5. `check_status()` - 检查工作区状态
```python
result = check_status(
    workspace_path="/app/data/workspace/my_research",
    detailed=True  # 可选，获取详细信息
)
```

**功能**: 检查所有子任务的完成状态和进度

### 6. `generate_summary()` - 生成总结报告
```python
result = generate_summary(
    workspace_path="/app/data/workspace/my_research",
    template_path=None,     # 可选，自定义模板
    output_format="markdown"  # 目前仅支持markdown
)
```

**功能**: 基于所有子任务的发现生成总结报告

## 🔄 标准化响应格式

所有函数返回统一的格式:

```python
{
    "ok": True,      # 操作是否成功
    "data": {        # 成功时的数据
        "workspace_path": "/app/data/workspace/my_research",
        "files_created": [...],
        # 其他函数特定数据
    },
    "error": ""      # 失败时的错误信息
}
```

**使用示例**:
```python
result = init_workspace("/app/data/test")
if result["ok"]:
    print(f"工作区创建成功: {result['data']['workspace_path']}")
else:
    print(f"失败: {result['error']}")
```

## 📄 模板系统

### 默认模板位置
```
/app/.proteus/skills/multitask-deep-research/templates/
├── task_plan.md          # 总任务规划模板
├── findings.md           # 总发现记录模板
├── progress.md           # 总进度日志模板
└── subtask_template/     # 子任务模板目录
    ├── task_plan.md
    ├── findings.md
    └── progress.md
```

### 使用自定义模板
```python
# 使用自定义模板初始化工作区
init_workspace(
    workspace_path="/app/data/custom_project",
    plan_content="# 自定义项目",
    template_path="/path/to/my_templates"
)

# 使用自定义模板添加子任务
add_subtasks(
    workspace_path="/app/data/custom_project",
    subtasks=[...],
    template_path="/path/to/my_subtask_templates"
)
```

### 模板文件格式
模板文件为标准Markdown文件，支持占位符替换:
- `[子任务描述]` → 子任务描述
- `[子任务ID]` → 子任务ID
- `[研究主题]` → 子任务名称

## 🚀 快速开始


> **📁 脚本位置**: 所有脚本文件（`basic_usage.py` 和 `core.py`）均已移至 `scripts/` 目录。可通过 `python scripts/basic_usage.py` 运行示例。

### 1. 基本使用
```python
from scripts.core import init_workspace, add_subtasks, log_finding

# 初始化工作区
result = init_workspace("/app/data/workspace/demo")
if not result["ok"]:
    print(f"失败: {result['error']}")
    exit()

# 添加子任务
add_subtasks(result["data"]["workspace_path"], [
    {"id": "task1", "name": "任务一", "description": "第一个研究任务"},
    {"id": "task2", "name": "任务二", "description": "第二个研究任务"}
])

# 记录研究发现
log_finding(
    workspace_path=result["data"]["workspace_path"],
    target="subtasks/task1",
    title="初步发现",
    content="这是第一个研究发现...",
    metadata={"confidence": "medium"}
)
```

### 2. 完整流程示例
```python
"""
外部研究协调系统示例
控制完整的研究流程，调用基础功能模块
"""

from scripts.core import *

class ResearchCoordinator:
    def __init__(self, project_name):
        self.workspace = f"/app/data/workspace/{project_name}"
        
    def setup_project(self, research_topic):
        # 外部系统决定项目设置
        plan = f"# {research_topic}研究\n\n## 目标: 深入分析{research_topic}"
        return init_workspace(self.workspace, plan)
    
    def plan_tasks(self, task_list):
        # 外部系统决定任务分解
        return add_subtasks(self.workspace, task_list)
    
    def conduct_research(self, research_function):
        """
        执行研究 - 外部系统控制研究逻辑
        
        Args:
            research_function: 外部研究函数，负责具体的搜索、分析等
        """
        # 检查当前状态
        status = check_status(self.workspace, detailed=True)
        
        for subtask_id, info in status["data"].get("subtask_status", {}).items():
            if info["status"] != "completed":
                # 外部系统执行研究
                findings = research_function(subtask_id, info)
                
                # 记录发现
                for finding in findings:
                    log_finding(self.workspace, f"subtasks/{subtask_id}", 
                               finding["title"], finding["content"], finding.get("metadata"))
                
                # 更新状态
                update_status(self.workspace, subtask_id, "working", 50)
    
    def monitor_and_report(self):
        # 外部系统决定监控频率和报告时机
        while True:
            status = check_status(self.workspace)
            if status["data"]["all_completed"]:
                # 生成最终报告
                return generate_summary(self.workspace)
            # 外部系统决定等待时间
            import time
            time.sleep(60)

# 使用示例
coordinator = ResearchCoordinator("ai_research")
coordinator.setup_project("人工智能在医疗中的应用")
coordinator.plan_tasks([
    {"id": "tech", "name": "技术分析"},
    {"id": "market", "name": "市场研究"}
])
```

## 🔧 函数详细说明

### `init_workspace(workspace_path, plan_content, template_path, overwrite)`
**参数**:
- `workspace_path` (str): 工作区目录路径
- `plan_content` (str): 任务规划内容，Markdown格式
- `template_path` (str, optional): 模板路径，None使用默认模板
- `overwrite` (bool): 是否覆盖已存在的工作区，默认False

**返回data内容**:
```python
{
    "workspace_path": "工作区路径",
    "files_created": ["创建的文件列表"],
    "directories": ["创建的目录列表"],
    "metadata": {"created_at": "...", "version": "..."}
}
```

### `add_subtasks(workspace_path, subtasks, template_path)`
**参数**:
- `workspace_path` (str): 工作区目录路径
- `subtasks` (list): 子任务定义列表，每个元素需包含`id`
- `template_path` (str, optional): 子任务模板路径

**返回data内容**:
```python
{
    "subtasks_created": ["创建的子任务ID列表"],
    "subtask_info": {
        "task_id": {"path": "路径", "name": "名称", "description": "描述"}
    },
    "total_created": 创建数量
}
```

### `log_finding(workspace_path, target, title, content, metadata)`
**参数**:
- `workspace_path` (str): 工作区目录路径
- `target` (str): 记录目标，"root"或"subtasks/{id}"
- `title` (str): 发现标题
- `content` (str): 发现内容
- `metadata` (dict, optional): 附加元数据

**返回data内容**:
```python
{
    "file_path": "记录的文件路径",
    "finding_id": "发现唯一ID",
    "timestamp": "记录时间",
    "target": "记录目标",
    "entry_length": 条目长度
}
```

### `update_status(workspace_path, subtask_id, status, progress, note)`
**参数**:
- `workspace_path` (str): 工作区目录路径
- `subtask_id` (str): 子任务ID
- `status` (str): 状态，推荐值: pending/working/completed
- `progress` (int): 进度百分比，0-100
- `note` (str, optional): 状态说明

**返回data内容**:
```python
{
    "subtask_id": "子任务ID",
    "status": "设置的状态",
    "progress": "设置的进度",
    "timestamp": "更新时间"
}
```

### `check_status(workspace_path, detailed)`
**参数**:
- `workspace_path` (str): 工作区目录路径
- `detailed` (bool): 是否返回详细信息

**返回data内容**:
```python
# detailed=False
{
    "all_completed": True/False,
    "overall_progress": 总体进度,
    "subtask_count": 子任务数量,
    "pending_tasks": ["未完成的任务ID列表"],
    "check_time": "检查时间"
}

# detailed=True (额外包含)
{
    "subtask_status": {
        "task_id": {
            "status": "状态",
            "progress": "进度",
            "path": "路径"
        }
    }
}
```

### `generate_summary(workspace_path, template_path, output_format)`
**参数**:
- `workspace_path` (str): 工作区目录路径
- `template_path` (str, optional): 报告模板路径
- `output_format` (str): 输出格式，目前仅支持"markdown"

**返回data内容**:
```python
{
    "report_path": "报告文件路径",
    "summary_link": "便捷链接路径",
    "findings_count": "发现数量",
    "report_length": "报告长度",
    "format": "输出格式"
}
```

## ⚙️ 配置与定制

### 环境变量 (可选)
```bash
# 设置默认工作区根目录
export MULTITASK_WORKSPACE_ROOT=/app/data/research_projects

# 设置默认模板路径
export MULTITASK_TEMPLATE_PATH=/path/to/templates
```

### 自定义模板示例
创建自定义模板目录:
```
/my_templates/
├── task_plan.md
├── findings.md
├── progress.md
└── subtask_template/
    ├── task_plan.md
    ├── findings.md
    └── progress.md
```

在`task_plan.md`中:
```markdown
# [项目标题]

## 基本信息
- **创建时间:** {{timestamp}}
- **负责人:** {{负责人}}

## 研究目标
[填写研究目标]

## 注意事项
[填写注意事项]
```

## 🔍 错误处理

### 常见错误
```python
# 工作区已存在
{"ok": False, "error": "工作区已存在: /path/to/workspace"}

# 工作区不存在
{"ok": False, "error": "工作区不存在: /path/to/workspace"}

# 文件权限错误
{"ok": False, "error": "[Errno 13] Permission denied"}

# 模板不存在
{"ok": False, "error": "模板路径不存在: /path/to/templates"}
```

### 错误处理模式
```python
def safe_operation(operation_func, *args, **kwargs):
    """安全的操作包装器"""
    try:
        result = operation_func(*args, **kwargs)
        if not result["ok"]:
            # 记录错误，决定重试或回退
            log_error(f"操作失败: {result['error']}")
            return None
        return result["data"]
    except Exception as e:
        log_error(f"操作异常: {e}")
        return None
```

## 🔗 集成指南

### 与deep-research技能集成
```python
def enhanced_research_flow(topic, workspace_path, subtask_id):
    """
    结合深度研究技能的研究流程
    """
    # 外部系统调用deep-research技能进行深入研究
    deep_results = external_deep_research(topic)
    
    # 使用本技能记录结果
    for finding in deep_results["findings"]:
        log_finding(
            workspace_path=workspace_path,
            target=f"subtasks/{subtask_id}",
            title=finding["title"],
            content=finding["content"],
            metadata={
                "category": "deep_research",
                "sources": finding.get("sources", []),
                "confidence": finding.get("confidence", "medium")
            }
        )
    
    # 更新状态
    update_status(
        workspace_path=workspace_path,
        subtask_id=subtask_id,
        status="completed",
        progress=100,
        note=f"完成深度研究，发现 {len(deep_results['findings'])} 个结果"
    )
```

### 与planning-with-files技能结合
```python
# 使用planning-with-files的模板
init_workspace(
    workspace_path="/app/data/project",
    plan_content="# 项目规划",
    template_path="/app/.proteus/skills/planning-with-files/templates"
)

# 外部系统负责整合两个技能的工作流
```

## 📁 文件结构约定

### 工作区标准结构
```
{workspace}/
├── task_plan.md          # 总任务规划
├── findings.md           # 总发现记录
├── progress.md           # 总进度日志
├── .workspace_meta.json  # 元数据 (自动生成)
├── subtasks/             # 子任务目录
│   ├── {task_id}/
│   │   ├── task_plan.md  # 子任务规划
│   │   ├── findings.md   # 子任务发现
│   │   └── progress.md   # 子任务进度
│   └── ...
└── reports/              # 报告目录
    ├── summary_*.md      # 生成的报告
    └── latest_summary.md -> summary_*.md  # 便捷链接
```

### 文件命名约定
- 使用小写字母、数字、下划线
- 子任务ID应具有描述性，如`literature_review`, `market_analysis`
- 报告文件使用时间戳: `summary_20260307_143022.md`

## ⚠️ 注意事项

1. **文件权限**: 确保对工作区目录有读写权限
2. **并发访问**: 本功能不处理并发访问，需要调用方协调
3. **路径安全**: 避免使用用户输入直接作为路径
4. **资源清理**: 长期项目应定期清理临时文件
5. **备份策略**: 重要研究建议建立备份机制

## 📝 版本历史

### v3.0.0-optimized (当前)
- 6个极简核心函数
- 标准化响应格式
- 专注文件操作，无研究逻辑
- 增强模板系统

### v2.0.0-simplified
- 基础功能模块设计
- 原子性操作函数
- 文件中心架构

### v1.0.0
- 完整的流程控制设计
- 脚本驱动执行模式

---

**设计哲学**: 本技能提供**基础文件操作功能**，所有研究逻辑、决策流程、进度控制均由**外部系统**负责。这种设计使得技能可以灵活集成到各种不同的研究流程中。
