# 多任务深度研究基础功能使用示例

## 🎯 新版本核心变化

本技能已重构为**v3.0.0-optimized**版本，主要优化：

1. **6个极简函数**：`init_workspace`, `add_subtasks`, `log_finding`, `update_status`, `check_status`, `generate_summary`
2. **标准化响应**：所有函数返回 `{"ok": bool, "data": {}, "error": ""}`
3. **专注文件操作**：无研究逻辑，只处理文件系统
4. **灵活模板**：支持自定义模板路径

## 🚀 快速开始

### 1. 基础使用
```python
from scripts.core import init_workspace, add_subtasks, log_finding

# 初始化工作区
result = init_workspace("/app/data/workspace/my_research", "# AI医疗研究")
if not result["ok"]:
    print(f"失败: {result['error']}")
    exit()

workspace_path = result["data"]["workspace_path"]
print(f"工作区创建成功: {workspace_path}")

# 添加子任务
add_subtasks(workspace_path, [
    {"id": "tech_analysis", "name": "技术分析", "description": "分析AI医疗技术"},
    {"id": "market_research", "name": "市场研究", "description": "研究市场现状"}
])

# 记录研究发现
log_finding(
    workspace_path=workspace_path,
    target="subtasks/tech_analysis",
    title="深度学习诊断准确率",
    content="最新研究表明，基于深度学习的医学影像诊断准确率达到95%以上...",
    metadata={
        "category": "技术突破",
        "sources": ["Nature Medicine, 2026"],
        "confidence": "high"
    }
)
```

### 2. 完整研究流程示例
```python
"""
外部研究协调系统示例
展示如何用基础功能模块构建完整研究流程
"""

from scripts.core import *
import time

class ResearchManager:
    def __init__(self, project_name):
        self.workspace = f"/app/data/workspace/{project_name}"
        
    def setup(self, topic, subtasks):
        """设置研究项目 - 外部系统决策"""
        # 创建项目规划
        plan = f"# {topic}深度研究\n\n## 目标: 全面分析{topic}的现状与趋势"
        
        # 初始化工作区
        result = init_workspace(self.workspace, plan)
        if not result["ok"]:
            raise Exception(f"项目设置失败: {result['error']}")
        
        # 添加子任务
        add_subtasks(self.workspace, subtasks)
        
        print(f"项目设置完成: {self.workspace}")
        return result["data"]
    
    def execute_research(self, research_strategy):
        """
        执行研究 - 外部系统控制研究逻辑
        
        Args:
            research_strategy: 外部研究策略函数
                             接收(subtask_id, subtask_info)，返回研究发现
        """
        print("开始研究执行...")
        
        # 获取当前状态
        status = check_status(self.workspace, detailed=True)
        
        for subtask_id, info in status["data"].get("subtask_status", {}).items():
            if info["status"] != "completed":
                print(f"处理子任务: {subtask_id}")
                
                # 外部系统执行研究策略
                findings = research_strategy(subtask_id, info)
                
                # 记录发现
                for finding in findings:
                    log_finding(
                        self.workspace,
                        f"subtasks/{subtask_id}",
                        finding["title"],
                        finding["content"],
                        finding.get("metadata", {})
                    )
                
                # 更新状态
                update_status(
                    self.workspace,
                    subtask_id,
                    "working",
                    50,
                    f"已记录 {len(findings)} 个发现"
                )
        
        print("研究执行完成")
    
    def monitor_progress(self, check_interval=60):
        """监控进度 - 外部系统决定监控逻辑"""
        print("开始监控研究进度...")
        
        while True:
            status = check_status(self.workspace)
            data = status["data"]
            
            print(f"进度: {data['overall_progress']}% | "
                  f"完成: {data['all_completed']} | "
                  f"待处理: {len(data['pending_tasks'])}")
            
            if data["all_completed"]:
                print("所有任务完成，生成总结报告...")
                report = generate_summary(self.workspace)
                print(f"报告生成: {report['data']['report_path']}")
                break
            
            # 外部系统决定等待时间
            time.sleep(check_interval)
    
    def generate_final_output(self, template_path=None):
        """生成最终输出 - 外部系统决定输出时机"""
        return generate_summary(self.workspace, template_path)

# 使用示例
if __name__ == "__main__":
    # 创建研究管理器
    manager = ResearchManager("ai_healthcare_2026")
    
    # 设置项目 (外部系统决策)
    manager.setup(
        topic="人工智能在医疗保健中的应用",
        subtasks=[
            {"id": "imaging", "name": "医学影像AI", "description": "分析AI在医学影像中的应用"},
            {"id": "drug_discovery", "name": "药物研发AI", "description": "研究AI加速药物研发"},
            {"id": "health_management", "name": "健康管理AI", "description": "分析AI在健康管理中的作用"}
        ]
    )
    
    # 定义外部研究策略
    def custom_research_strategy(subtask_id, subtask_info):
        """外部研究策略 - 这里可以集成各种研究工具"""
        findings = []
        
        if subtask_id == "imaging":
            findings.append({
                "title": "深度学习在癌症早期检测中的突破",
                "content": "最新研究显示，基于深度学习的癌症早期检测系统在敏感性和特异性上均超过传统方法...",
                "metadata": {
                    "category": "技术突破",
                    "sources": ["Nature Medicine, 2026", "IEEE Transactions"],
                    "confidence": "high"
                }
            })
        
        return findings
    
    # 执行研究
    manager.execute_research(custom_research_strategy)
    
    # 监控进度 (在实际应用中可能是异步的)
    # manager.monitor_progress(check_interval=30)
    
    # 生成报告
    result = manager.generate_final_output()
    if result["ok"]:
        print(f"✅ 研究完成! 报告: {result['data']['report_path']}")
```

## 🔧 函数组合示例

### 示例1: 仅使用文件结构功能
```python
# 只需要创建文件结构，后续逻辑完全由外部系统控制
from scripts.core import init_workspace, add_subtasks

# 创建最小化项目结构
init_workspace("/app/data/workspace/minimal", "# 最小化项目")

# 添加骨架子任务
add_subtasks("/app/data/workspace/minimal", [
    {"id": "phase1", "name": "第一阶段"},
    {"id": "phase2", "name": "第二阶段"}
])

print("文件结构创建完成，外部系统负责所有后续逻辑")
```

### 示例2: 批量项目初始化
```python
from scripts.core import init_workspace
import concurrent.futures

# 批量创建多个研究项目
projects = [
    {"name": "cloud_trends", "topic": "云计算趋势2026"},
    {"name": "ai_ethics", "topic": "AI伦理与治理"},
    {"name": "quantum_computing", "topic": "量子计算进展"}
]

def create_project(project):
    plan = f"# {project['topic']}\n\n研究项目"
    return init_workspace(f"/app/data/workspace/{project['name']}", plan)

# 并行初始化
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
    futures = [executor.submit(create_project, p) for p in projects]
    results = [f.result() for f in futures]

success_count = sum(1 for r in results if r["ok"])
print(f"成功创建 {success_count}/{len(projects)} 个项目")
```

### 示例3: 自动化状态检查与报告
```python
from scripts.core import check_status, generate_summary
import schedule
import time

def automated_monitor(workspace_path):
    """自动化监控 - 外部系统控制调度逻辑"""
    
    def check_and_report():
        status = check_status(workspace_path)
        if status["data"]["all_completed"]:
            report = generate_summary(workspace_path)
            print(f"✅ 任务完成，报告生成: {report['data']['report_path']}")
            return True
        else:
            print(f"⏳ 进度: {status['data']['overall_progress']}%")
            return False
    
    # 每5分钟检查一次
    schedule.every(5).minutes.do(check_and_report)
    
    print(f"开始监控: {workspace_path}")
    while True:
        schedule.run_pending()
        time.sleep(60)

# 使用
# automated_monitor("/app/data/workspace/my_research")
```

## 📊 状态管理示例

### 状态流转控制
```python
from scripts.core import check_status, update_status

def manage_subtask_workflow(workspace_path, subtask_id):
    """管理子任务工作流 - 外部系统控制状态流转"""
    
    # 检查当前状态
    status = check_status(workspace_path, detailed=True)
    current = status["data"]["subtask_status"].get(subtask_id, {})
    
    # 外部系统根据业务逻辑决定状态流转
    if current.get("status") == "pending":
        # 开始任务
        update_status(workspace_path, subtask_id, "working", 0, "任务开始")
        
        # 外部系统执行研究...
        # research_results = external_research_function()
        
        # 记录发现后更新进度
        update_status(workspace_path, subtask_id, "working", 50, "研究进行中")
        
        # 完成研究
        update_status(workspace_path, subtask_id, "completed", 100, "研究完成")
    
    return check_status(workspace_path)
```

### 进度追踪面板
```python
from scripts.core import check_status
from datetime import datetime

class ProgressDashboard:
    """研究进度仪表板 - 外部系统展示层"""
    
    def __init__(self, workspace_path):
        self.workspace = workspace_path
    
    def display_summary(self):
        """显示进度摘要"""
        status = check_status(self.workspace)
        data = status["data"]
        
        print("=" * 50)
        print(f"研究进度仪表板 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("=" * 50)
        print(f"📊 总体进度: {data['overall_progress']}%")
        print(f"✅ 全部完成: {'是' if data['all_completed'] else '否'}")
        print(f"📁 子任务数: {data['subtask_count']}")
        print(f"⏳ 待处理任务: {len(data['pending_tasks'])}")
        print("-" * 50)
    
    def display_details(self):
        """显示详细状态"""
        status = check_status(self.workspace, detailed=True)
        
        if "subtask_status" in status["data"]:
            print("子任务详情:")
            print("-" * 50)
            for task_id, info in status["data"]["subtask_status"].items():
                icon = "✅" if info["status"] == "completed" else "⏳"
                print(f"{icon} {task_id}: {info['status']} ({info['progress']}%)")
            print("-" * 50)

# 使用
dashboard = ProgressDashboard("/app/data/workspace/my_research")
dashboard.display_summary()
dashboard.display_details()
```

## 🔗 集成示例

### 与deep-research技能集成
```python
def integrated_deep_research(workspace_path, subtask_id, research_question):
    """
    集成深度研究技能的研究流程
    """
    # 外部系统调用deep-research技能
    # deep_results = deep_research_skill.analyze(research_question)
    
    # 模拟深度研究结果
    deep_results = {
        "findings": [
            {
                "title": "技术深度分析结果",
                "content": "经过深度分析发现...",
                "sources": ["学术论文1", "行业报告2"],
                "confidence": "high"
            }
        ]
    }
    
    from scripts.core import log_finding, update_status
    
    # 记录深度研究发现
    for finding in deep_results["findings"]:
        log_finding(
            workspace_path,
            f"subtasks/{subtask_id}",
            finding["title"],
            finding["content"],
            {
                "category": "deep_research",
                "sources": finding.get("sources", []),
                "confidence": finding.get("confidence", "medium")
            }
        )
    
    # 更新状态
    update_status(
        workspace_path,
        subtask_id,
        "completed",
        100,
        f"完成深度研究，发现 {len(deep_results['findings'])} 个结果"
    )
    
    return len(deep_results["findings"])
```

### 与外部API集成
```python
import requests
from scripts.core import log_finding

def research_with_external_api(workspace_path, subtask_id, api_endpoint, query):
    """
    结合外部API的研究流程
    """
    # 调用外部API
    # response = requests.get(api_endpoint, params={"q": query})
    # data = response.json()
    
    # 模拟API响应
    data = {
        "results": [
            {"title": "API发现1", "content": "从API获取的数据..."},
            {"title": "API发现2", "content": "另一个发现..."}
        ]
    }
    
    # 记录API获取的发现
    for result in data["results"]:
        log_finding(
            workspace_path,
            f"subtasks/{subtask_id}",
            result["title"],
            result["content"],
            {"source": api_endpoint, "type": "api_data"}
        )
    
    return len(data["results"])
```

## 🎯 最佳实践

### 1. 错误处理模式
```python
from scripts.core import init_workspace

def safe_init_workspace(path, plan, max_retries=3):
    """安全的工作区初始化，支持重试"""
    for attempt in range(max_retries):
        result = init_workspace(path, plan, overwrite=(attempt > 0))
        
        if result["ok"]:
            return result["data"]
        
        print(f"尝试 {attempt + 1} 失败: {result['error']}")
        
        if "已存在" in result["error"] and attempt == 0:
            # 第一次失败是因为已存在，下次尝试覆盖
            continue
        
        # 其他错误，等待后重试
        import time
        time.sleep(2 ** attempt)  # 指数退避
    
    raise Exception(f"工作区初始化失败: {path}")

# 使用
try:
    workspace = safe_init_workspace("/app/data/workspace/project", "# 项目")
except Exception as e:
    print(f"致命错误: {e}")
```

### 2. 配置管理
```python
import json
from pathlib import Path

class ResearchConfig:
    """研究配置管理器"""
    
    def __init__(self, config_path="research_config.json"):
        self.config_path = Path(config_path)
        self.config = self._load_config()
    
    def _load_config(self):
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                return json.load(f)
        return {
            "default_workspace_root": "/app/data/workspace",
            "template_path": "/app/.proteus/skills/multitask-deep-research/templates",
            "backup_enabled": True,
            "projects": {}
        }
    
    def save(self):
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def create_project(self, name, topic, subtasks):
        """创建新项目配置"""
        project_path = f"{self.config['default_workspace_root']}/{name}"
        
        self.config["projects"][name] = {
            "path": project_path,
            "topic": topic,
            "subtasks": subtasks,
            "created": datetime.now().isoformat(),
            "status": "active"
        }
        
        self.save()
        return project_path

# 使用
config = ResearchConfig()
project_path = config.create_project(
    name="ai_research",
    topic="人工智能研究",
    subtasks=[{"id": "lit_review", "name": "文献综述"}]
)
```

### 3. 批量操作
```python
from scripts.core import update_status, check_status
from typing import List

def batch_update_status(workspace_path: str, subtask_ids: List[str], 
                       status: str, progress: int, note: str = ""):
    """批量更新子任务状态"""
    results = []
    for subtask_id in subtask_ids:
        result = update_status(workspace_path, subtask_id, status, progress, note)
        results.append((subtask_id, result["ok"]))
    
    success_count = sum(1 for _, ok in results if ok)
    return {
        "total": len(results),
        "success": success_count,
        "failed": len(results) - success_count,
        "details": results
    }
```

## 📝 总结

### 核心使用模式

1. **外部系统驱动**: 所有研究逻辑、决策流程由外部系统控制
2. **基础功能调用**: 使用6个核心函数处理文件操作
3. **标准化响应**: 统一处理函数返回结果
4. **灵活集成**: 可与其他技能、API、工具无缝集成

### 适用场景

- 复杂研究项目需要自定义工作流
- 需要集成多种研究工具和资源的场景
- 长期研究项目需要灵活的状态管理
- 多团队协作的研究项目

### 设计优势

1. **解耦**: 研究逻辑与文件操作分离
2. **灵活**: 可适应各种研究流程和工作模式
3. **可测试**: 每个功能独立，易于测试
4. **可扩展**: 可以轻松添加新的文件操作功能

---

**记住**: 本技能只提供**文件操作功能**，所有**研究逻辑**和**决策流程**都由您的**外部系统**负责控制。
