# 多任务深度研究基础功能参考指南

## 📋 函数API参考

### 标准响应格式
所有函数返回统一格式:
```python
{
    "ok": True/False,      # 操作是否成功
    "data": {             # 成功时的返回数据
        # 函数特定数据
    },
    "error": ""           # 失败时的错误信息
}
```

### 1. init_workspace
**功能**: 初始化研究工作区

**函数签名**:
```python
init_workspace(
    workspace_path: str,
    plan_content: str = "# 研究项目\n\n## 目标",
    template_path: Optional[str] = None,
    overwrite: bool = False
) -> Dict[str, Any]
```

**参数说明**:
- `workspace_path`: 工作区目录路径
- `plan_content`: 任务规划内容 (Markdown格式)
- `template_path`: 模板路径，None时使用默认模板
- `overwrite`: 是否覆盖已存在的工作区

**返回data内容**:
```python
{
    "workspace_path": "工作区路径",
    "files_created": ["task_plan.md", "findings.md", ...],
    "directories": ["subtasks/", "reports/"],
    "metadata": {
        "created_at": "2026-03-07T12:00:00",
        "template_used": "/path/to/templates",
        "version": "3.0.0-optimized"
    }
}
```

### 2. add_subtasks
**功能**: 添加子任务到工作区

**函数签名**:
```python
add_subtasks(
    workspace_path: str,
    subtasks: List[Dict[str, Any]],
    template_path: Optional[str] = None
) -> Dict[str, Any]
```

**参数说明**:
- `workspace_path`: 工作区目录路径
- `subtasks`: 子任务定义列表，每个元素至少包含`id`
- `template_path`: 子任务模板路径

**子任务定义格式**:
```python
{
    "id": "literature_review",      # 必需，唯一标识
    "name": "文献综述",             # 可选，显示名称
    "description": "收集分析相关文献"  # 可选，描述
}
```

**返回data内容**:
```python
{
    "subtasks_created": ["task1", "task2"],
    "subtask_info": {
        "task1": {
            "path": "/path/to/subtasks/task1",
            "name": "任务一",
            "description": "描述"
        }
    },
    "total_created": 2
}
```

### 3. log_finding
**功能**: 记录研究发现

**函数签名**:
```python
log_finding(
    workspace_path: str,
    target: str,                    # "root" 或 "subtasks/{id}"
    title: str,
    content: str,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]
```

**参数说明**:
- `workspace_path`: 工作区目录路径
- `target`: 记录目标，"root"表示总发现，否则为"subtasks/{id}"
- `title`: 发现标题
- `content`: 发现内容
- `metadata`: 附加元数据

**metadata示例**:
```python
{
    "category": "技术分析",
    "sources": ["文献1", "报告2"],
    "confidence": "high",
    "tags": ["AI", "医疗"]
}
```

**返回data内容**:
```python
{
    "file_path": "/path/to/findings.md",
    "finding_id": "finding_1709798400",
    "timestamp": "2026-03-07 12:00:00",
    "target": "subtasks/literature_review",
    "entry_length": 250
}
```

### 4. update_status
**功能**: 更新子任务状态

**函数签名**:
```python
update_status(
    workspace_path: str,
    subtask_id: str,
    status: str,           # 推荐: pending/working/completed
    progress: int = 0,     # 0-100
    note: str = ""
) -> Dict[str, Any]
```

**参数说明**:
- `workspace_path`: 工作区目录路径
- `subtask_id`: 子任务ID
- `status`: 状态值
- `progress`: 进度百分比
- `note`: 状态说明

**返回data内容**:
```python
{
    "subtask_id": "literature_review",
    "status": "working",
    "progress": 75,
    "timestamp": "2026-03-07T12:00:00"
}
```

### 5. check_status
**功能**: 检查工作区状态

**函数签名**:
```python
check_status(
    workspace_path: str,
    detailed: bool = False
) -> Dict[str, Any]
```

**参数说明**:
- `workspace_path`: 工作区目录路径
- `detailed`: 是否返回详细信息

**返回data内容 (detailed=False)**:
```python
{
    "all_completed": False,
    "overall_progress": 42.5,
    "subtask_count": 4,
    "pending_tasks": ["task1", "task3"],
    "check_time": "2026-03-07T12:00:00"
}
```

**返回data内容 (detailed=True)**:
```python
{
    # 包含上述所有字段，外加:
    "subtask_status": {
        "task1": {
            "status": "pending",
            "progress": 0,
            "path": "/path/to/subtasks/task1"
        },
        "task2": {
            "status": "completed",
            "progress": 100,
            "path": "/path/to/subtasks/task2"
        }
    }
}
```

### 6. generate_summary
**功能**: 生成总结报告

**函数签名**:
```python
generate_summary(
    workspace_path: str,
    template_path: Optional[str] = None,
    output_format: str = "markdown"
) -> Dict[str, Any]
```

**参数说明**:
- `workspace_path`: 工作区目录路径
- `template_path`: 报告模板路径
- `output_format`: 输出格式 (目前仅支持"markdown")

**返回data内容**:
```python
{
    "report_path": "/path/to/reports/summary_20260307_120000.md",
    "summary_link": "/path/to/workspace/latest_summary.md",
    "findings_count": 15,
    "report_length": 2048,
    "format": "markdown"
}
```

## 📁 文件结构约定

### 工作区标准结构
```
{workspace}/
├── task_plan.md              # 总任务规划
├── findings.md               # 总发现记录  
├── progress.md               # 总进度日志
├── .workspace_meta.json      # 元数据 (自动生成)
├── subtasks/                 # 子任务目录
│   ├── {task_id}/
│   │   ├── task_plan.md      # 子任务规划
│   │   ├── findings.md       # 子任务发现
│   │   └── progress.md       # 子任务进度
│   └── ...
└── reports/                  # 报告目录
    ├── summary_*.md          # 生成的报告
    └── latest_summary.md     # 便捷链接
```

### 文件格式规范

#### 发现记录格式
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

#### 状态文件格式
```markdown
**状态:** working
**进度:** 75%
**最后更新:** 2026-03-07 12:00:00

## 说明
- 12:00: 已完成数据收集
- 12:30: 开始数据分析
```

## ⚙️ 模板系统

### 默认模板位置
```
/app/.proteus/skills/multitask-deep-research/templates/
├── task_plan.md              # 总任务规划模板
├── findings.md               # 总发现记录模板
├── progress.md               # 总进度日志模板
└── subtask_template/         # 子任务模板目录
    ├── task_plan.md
    ├── findings.md
    └── progress.md
```

### 占位符支持
模板文件支持以下占位符 (仅限子任务模板):
- `[子任务描述]` → 替换为子任务描述
- `[子任务ID]` → 替换为子任务ID
- `[研究主题]` → 替换为子任务名称

### 自定义模板示例
```
/my_custom_templates/
├── task_plan.md          # 自定义总规划模板
├── findings.md           # 自定义发现模板
├── progress.md           # 自定义进度模板
└── subtask_template/     # 自定义子任务模板目录
```

使用自定义模板:
```python
init_workspace(
    workspace_path="/app/data/custom_project",
    plan_content="# 项目",
    template_path="/my_custom_templates"
)
```

## 🔧 最佳实践

### 1. 错误处理模式
```python
def safe_operation(operation_func, *args, **kwargs):
    """安全的操作包装器"""
    result = operation_func(*args, **kwargs)
    
    if not result["ok"]:
        # 记录错误，根据错误类型决定处理策略
        error = result["error"]
        
        if "已存在" in error:
            # 工作区已存在，可以选择使用现有工作区
            return {"ok": True, "data": {"workspace_path": args[0]}, "error": ""}
        elif "权限" in error:
            # 权限错误，可能需要调整权限或路径
            raise PermissionError(error)
        else:
            # 其他错误，记录并返回
            print(f"操作失败: {error}")
            return result
    
    return result
```

### 2. 批量操作模式
```python
def batch_create_subtasks(workspace_path, task_definitions, batch_size=5):
    """批量创建子任务，避免资源竞争"""
    results = []
    
    for i in range(0, len(task_definitions), batch_size):
        batch = task_definitions[i:i+batch_size]
        result = add_subtasks(workspace_path, batch)
        results.append(result)
        
        if not result["ok"]:
            print(f"批次 {i//batch_size + 1} 失败: {result['error']}")
    
    return results
```

### 3. 状态监控模式
```python
def monitor_with_retry(workspace_path, max_attempts=3, interval=60):
    """带重试的状态监控"""
    for attempt in range(max_attempts):
        result = check_status(workspace_path)
        
        if result["ok"]:
            return result["data"]
        
        print(f"监控尝试 {attempt + 1} 失败: {result['error']}")
        
        if attempt < max_attempts - 1:
            import time
            time.sleep(interval)
    
    raise Exception(f"状态监控失败: {workspace_path}")
```

### 4. 资源清理模式
```python
import shutil
from pathlib import Path

def cleanup_old_reports(workspace_path, keep_last=5):
    """清理旧的报告文件，保留最新的几个"""
    reports_dir = Path(workspace_path) / "reports"
    
    if not reports_dir.exists():
        return
    
    # 获取所有报告文件，按修改时间排序
    report_files = sorted(
        reports_dir.glob("summary_*.md"),
        key=lambda x: x.stat().st_mtime,
        reverse=True
    )
    
    # 删除旧文件
    for report_file in report_files[keep_last:]:
        report_file.unlink()
        print(f"清理旧报告: {report_file.name}")
    
    return len(report_files) - keep_last
```

## ⚠️ 常见问题

### Q1: 工作区已存在怎么办？
**A**: 使用 `overwrite=True` 参数覆盖，或使用现有工作区:
```python
# 选项1: 覆盖
init_workspace("/path/to/workspace", "# 新规划", overwrite=True)

# 选项2: 使用现有
result = init_workspace("/path/to/workspace", "# 规划")
if not result["ok"] and "已存在" in result["error"]:
    # 使用现有工作区
    workspace_path = "/path/to/workspace"
```

### Q2: 如何自定义发现记录格式？
**A**: 创建自定义的 `findings.md` 模板:
```markdown
# 研究发现

## 模板说明
按此格式记录发现...

---
```

### Q3: 并发访问如何处理？
**A**: 本模块不处理并发，建议:
1. 外部系统协调并发访问
2. 使用文件锁机制
3. 批量操作减少冲突

### Q4: 如何备份研究数据？
**A**: 建议外部系统实现备份策略:
```python
import shutil
from datetime import datetime

def backup_workspace(workspace_path, backup_root):
    """备份工作区"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{Path(workspace_path).name}_{timestamp}"
    backup_path = Path(backup_root) / backup_name
    
    shutil.copytree(workspace_path, backup_path)
    return backup_path
```

## 🔗 集成建议

### 与环境变量集成
```python
import os
from scripts.core import init_workspace

# 从环境变量读取配置
workspace_root = os.getenv("RESEARCH_WORKSPACE_ROOT", "/app/data/workspace")
template_path = os.getenv("RESEARCH_TEMPLATE_PATH")

def create_project_from_env(project_name, plan_content):
    """从环境变量创建项目"""
    workspace_path = f"{workspace_root}/{project_name}"
    return init_workspace(workspace_path, plan_content, template_path)
```

### 与配置管理系统集成
```python
import yaml  # 或 json, toml

def load_research_config(config_file):
    """从配置文件加载研究配置"""
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)
    
    return {
        "workspace_path": config["workspace"],
        "plan_content": config["plan"],
        "subtasks": config.get("subtasks", [])
    }
```

## 📊 性能考虑

### 文件操作优化
1. **批量写入**: 多个发现可以批量记录
2. **缓存读取**: 频繁读取的状态可以缓存
3. **增量更新**: 只更新变化的部分

### 内存使用
1. **流式处理**: 大文件使用流式读写
2. **分块处理**: 大量数据分块处理

### 磁盘空间
1. **定期清理**: 清理临时文件和旧报告
2. **压缩存储**: 可选的数据压缩

## 📝 版本兼容性

### 升级到v3.0.0
从v2.0.0升级:
1. 函数名变更: `create_workspace` → `init_workspace` 等
2. 响应格式变更: `{"success": bool}` → `{"ok": bool}`
3. 参数简化: 移除非必要的复杂参数

### 向后兼容
如需向后兼容，可创建适配层:
```python
# 适配层示例
def create_workspace_v2(path, content, **kwargs):
    """v2.0.0兼容函数"""
    result = init_workspace(path, content, **kwargs)
    return {
        "success": result["ok"],
        "workspace_path": result["data"].get("workspace_path"),
        "error": result["error"]
    }
```

---

**核心原则**: 本模块只负责**文件操作**，所有**研究逻辑**由外部系统控制。
如需扩展功能，建议在外部系统中实现，或创建新的独立模块。
