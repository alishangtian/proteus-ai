---
name: multi-task-deep-research
description: 企业级多任务深度研究智能体系统 - 基于文件规划的复杂多任务研究框架，集成系统性研究方法论、多源验证机制和智能化报告生成，支持依赖关系管理和顺序子任务执行
allowed-tools:
  - python_execute
  - serper_search
  - web_crawler
version: v1.2.0
optimization-date: 2026-03-05
optimization-methodology: 五步执行模式优化 + 任务目录规划 + API优先下发 + 定期休眠监控
author: Proteus AI Research Team
tags:
  - research
  - multi-task
  - planning
  - analysis
  - coordination
  - deep-research
---

# 🎯 多任务深度研究技能：企业级智能研究协调系统

## 🌟 技能核心价值：为什么选择多任务深度研究？

多任务深度研究技能是**planning-with-files模式**与**深度研究方法论**的融合升级，专为复杂、多维度、需要并行处理的研究任务而设计。与单任务研究相比，本技能提供：

### 🔍 多任务 vs. 单任务研究：关键区别

| 维度 | 单任务深度研究 | 多任务深度研究 |
|------|---------------|--------------|
| **任务规模** | 单一研究问题 | 多个相关研究子任务 |
| **协调机制** | 线性执行 | 并行执行+进度监控 |
| **输出结构** | 单一报告 | 主报告+子任务报告 |
| **资源利用** | 串行资源分配 | 智能资源调度 |
| **风险控制** | 单一失败点 | 容错与任务隔离 |
| **价值产出** | 深度但单一 | 广度+深度综合 |

### 🏆 技能解决的四大核心问题

1. **复杂问题分解** - 将宏大研究问题拆解为可管理的子任务
2. **并行执行协调** - 智能调度和监控多个子任务进度
3. **结果整合挑战** - 系统化整合分散的研究发现
4. **质量控制统一** - 确保所有子任务达到一致质量标准

---

# 🔄 五步执行模式：主任务直接操作文件系统的标准工作流

## 🎯 核心设计理念

多任务深度研究技能的核心创新在于**主任务直接操作文件系统**的设计理念。与传统的脚本调用模式不同，优化后的五步执行模式强调：

1. **直接文件操作**：主任务使用Python代码直接读写文件系统
2. **统一执行环境**：所有操作在同一个Python执行环境中完成
3. **实时状态同步**：文件状态实时更新，无需额外同步机制
4. **简化调试维护**：单一代码库，调试和维护更简单

## 📋 第一步：任务总规划与目录生成

**目标**：在主任务中直接创建完整的任务目录结构和规划文件

**Python代码示例**：
```python
# 在主任务中直接创建任务结构
import os
import json
from datetime import datetime

def create_task_directly(task_name):
    """直接创建任务目录和文件"""
    # 1. 创建主目录
    task_dir = f"/app/data/tasks/{task_name.replace(' ', '_')}"
    os.makedirs(task_dir, exist_ok=True)
    
    # 2. 创建子目录
    for subdir in ['sub_tasks', 'reports', 'data/sources']:
        os.makedirs(os.path.join(task_dir, subdir), exist_ok=True)
    
    # 3. 直接写入规划文件
    plan_content = f"# 主任务规划: {task_name}\n生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    with open(f"{task_dir}/master_task_plan.md", 'w', encoding='utf-8') as f:
        f.write(plan_content)
    
    # 4. 直接写入配置文件
    config = {
        "task_name": task_name,
        "created_at": datetime.now().isoformat(),
        "status": "planning",
        "progress": 0.0
    }
    with open(f"{task_dir}/task_config.json", 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)
    
    return task_dir
```

**文件系统操作**：
- `os.makedirs()`：创建目录结构
- `open() + write()`：写入文本文件
- `json.dump()`：写入配置文件

## 📝 第二步：主任务与子任务文件丰富化

**目标**：在主任务中直接创建和丰富所有任务文件

**Python代码示例**：
```python
def enrich_files_directly(task_dir, subtasks):
    """直接丰富任务文件"""
    for subtask in subtasks:
        # 创建子任务目录
        subtask_dir = f"{task_dir}/sub_tasks/{subtask['name'].replace(' ', '_')}"
        os.makedirs(subtask_dir, exist_ok=True)
        
        # 直接写入子任务文件
        files = {
            "task_plan.md": f"# {subtask['name']}规划\n描述: {subtask.get('desc', '')}",
            "findings.md": f"# {subtask['name']}发现\n状态: 进行中",
            "progress.md": f"# {subtask['name']}进度\n进度: 0%"
        }
        
        for filename, content in files.items():
            with open(f"{subtask_dir}/{filename}", 'w', encoding='utf-8') as f:
                f.write(content)
    
    print(f"文件丰富化完成: {len(subtasks)}个子任务")
```

## 🚀 第三步：子任务API优先下发

**目标**：在主任务中直接调用API启动子任务

**Python代码示例**：
```python
import requests

def start_tasks_directly(task_dir, api_config):
    """直接通过API启动任务"""
    config_path = f"{task_dir}/task_config.json"
    
    # 读取配置
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # 直接调用API
    for task in config.get('tasks', []):
        try:
            response = requests.post(
                api_config['endpoint'],
                json={"query": task['query']},
                headers={"Authorization": f"Bearer {api_config['token']}"},
                timeout=30
            )
            
            if response.status_code == 200:
                task['status'] = 'running'
                print(f"✅ {task['name']}启动成功")
        except Exception as e:
            print(f"❌ {task['name']}启动失败: {e}")
    
    # 更新配置
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)
```

## 🔍 第四步：定期休眠监控

**目标**：在主任务中实现智能监控循环

**Python代码示例**：
```python
import time

def monitor_directly(task_dir, interval=300):
    """直接实现监控"""
    check_count = 0
    
    while True:
        check_count += 1
        print(f"🔄 第{check_count}次检查")
        
        # 检查进度
        progress = check_progress(task_dir)
        print(f"📊 进度: {progress}%")
        
        if progress >= 100:
            print("🎊 任务完成!")
            break
        
        # 智能休眠
        sleep_time = interval
        if progress < 30:
            sleep_time = interval // 2
        elif progress > 80:
            sleep_time = interval * 2
        
        print(f"⏳ 休眠{sleep_time}秒")
        time.sleep(sleep_time)
```

## 📊 第五步：最终结果生成

**目标**：在主任务中直接生成综合报告

**Python代码示例**：
```python
def generate_report_directly(task_dir):
    """直接生成报告"""
    # 收集发现
    findings = collect_findings(task_dir)
    
    # 生成报告
    report_content = f"# 综合研究报告\n生成时间: {datetime.now()}\n\n"
    report_content += "## 研究发现\n" + "\n".join(findings)
    
    # 写入报告
    report_path = f"{task_dir}/reports/final_report.md"
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report_content)
    
    return report_path
```

## 📈 模式对比：直接操作 vs 脚本调用

| 方面 | 脚本调用模式 | **直接文件操作模式** |
|------|--------------|----------------------|
| **控制粒度** | 粗粒度（脚本级） | **细粒度（代码级）** |
| **错误处理** | 跨脚本复杂 | **直接异常处理** |
| **状态管理** | 需要同步机制 | **文件即时更新** |
| **调试难度** | 高（多进程） | **低（单进程）** |
| **部署复杂度** | 高（多脚本） | **低（单文件）** |
| **灵活性** | 有限 | **极高** |

## 🛠️ 实施指南

### 1. 代码组织
```python
# research_project.py
# ├── 规划模块 (planning.py)
# ├── 执行模块 (execution.py)
# ├── 监控模块 (monitoring.py)
# └── 报告模块 (reporting.py)
```

### 2. 错误处理策略
```python
def safe_file_operation(func):
    """文件操作安全装饰器"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except IOError as e:
            print(f"文件操作错误: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"JSON解析错误: {e}")
            return None
    return wrapper
```

### 3. 性能优化
- **批量操作**：减少文件系统调用
- **缓存机制**：避免重复读取
- **并发处理**：独立任务并行执行

---

通过这五步执行模式，您可以在主任务中直接使用Python代码实现完整的多任务研究流程，获得最大的灵活性和控制力。
# 🚀 快速开始：在主任务中实施五步执行模式

## 📋 完整示例代码

以下是在主任务中使用`python_execute`工具实现五步执行模式的完整示例：

```python
# 在主任务中执行多任务研究
import os
import json
from datetime import datetime

def run_complete_research():
    """完整五步执行示例"""
    
    # 第一步：规划
    task_dir = "/app/data/tasks/示例研究"
    os.makedirs(task_dir, exist_ok=True)
    
    with open(f"{task_dir}/plan.md", 'w', encoding='utf-8') as f:
        f.write(f"# 研究计划\n时间: {datetime.now()}")
    
    # 第二步：创建子任务
    subtasks = ["分析", "研究", "总结"]
    for task in subtasks:
        subtask_dir = f"{task_dir}/sub_tasks/{task}"
        os.makedirs(subtask_dir, exist_ok=True)
        
        with open(f"{subtask_dir}/task.md", 'w', encoding='utf-8') as f:
            f.write(f"# {task}任务")
    
    # 第三步：执行（简化）
    print("执行子任务...")
    
    # 第四步：监控（简化）
    print("监控进度...")
    
    # 第五步：报告
    report_path = f"{task_dir}/report.md"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("# 研究报告\n完成!")
    
    print(f"研究完成！报告: {report_path}")
    return task_dir

# 执行
if __name__ == "__main__":
    run_complete_research()
```

## 🔧 在主任务中调用

在主任务中，使用`python_execute`工具运行代码：

```python
# 主任务调用示例
research_code = """
import os
from datetime import datetime

# 创建研究目录
task_dir = "/app/data/tasks/我的研究"
os.makedirs(task_dir, exist_ok=True)

# 写入规划文件
with open(f"{task_dir}/plan.md", 'w', encoding='utf-8') as f:
    f.write(f"研究开始于: {datetime.now()}")

print(f"任务目录: {task_dir}")
"""

# 使用python_execute执行
result = python_execute(code=research_code, language="python", enable_network=True)
print(result)
```

## 📁 核心文件操作函数

### 1. 目录管理
```python
def setup_research_project(name):
    """设置研究项目目录"""
    project_dir = f"/app/data/tasks/{name}"
    
    # 创建目录结构
    dirs = ['sub_tasks', 'reports', 'data', 'logs']
    for d in dirs:
        os.makedirs(f"{project_dir}/{d}", exist_ok=True)
    
    return project_dir
```

### 2. 配置文件管理
```python
def update_project_config(project_dir, key, value):
    """更新项目配置"""
    config_file = f"{project_dir}/config.json"
    
    # 读取或创建配置
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            config = json.load(f)
    else:
        config = {}
    
    # 更新配置
    config[key] = value
    config['updated'] = datetime.now().isoformat()
    
    # 写入配置
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
    
    return config
```

### 3. 进度跟踪
```python
def update_progress(project_dir, task_name, progress):
    """更新任务进度"""
    progress_file = f"{project_dir}/sub_tasks/{task_name}/progress.md"
    
    content = f"# 进度跟踪\n任务: {task_name}\n进度: {progress}%\n时间: {datetime.now()}"
    
    with open(progress_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return progress
```

## 🎯 使用建议

### 1. 开始步骤
1. 从简单的文件操作开始
2. 逐步添加复杂功能
3. 测试每一步的文件输出

### 2. 调试技巧
1. 检查目录结构是否正确
2. 验证文件内容格式
3. 监控配置文件更新

### 3. 扩展方法
1. 添加更多的文件模板
2. 实现更复杂的监控逻辑
3. 集成外部工具和服务

---

通过这个快速开始指南，您可以在主任务中直接使用Python代码操作文件系统，实现高效的多任务研究管理。
# 🏗️ 文件系统架构：基于五步执行模式优化

## 📁 优化后的目录结构

```
项目根目录/
├── 第一步：规划文件/
│   ├── master_task_plan.md          # 详细的主任务规划
│   ├── task_config.json             # 任务配置和状态
│   └── architecture_diagram.md      # 任务架构图
├── 第二步：任务文件/
│   ├── master_findings.md           # 主研究发现模板
│   ├── master_progress.md           # 主任务进度跟踪
│   └── sub_tasks/                   # 子任务目录
│       ├── [task_name_1]/
│       │   ├── task_plan.md         # 详细的子任务规划
│       │   ├── findings.md          # 结构化研究发现模板
│       │   ├── progress.md          # 详细进度跟踪
│       │   ├── references/          # 参考资料
│       │   └── data/                # 子任务数据
│       ├── [task_name_2]/
│       │   └── ...                  # 类似结构
│       └── ...
├── 第三步：执行监控/
│   ├── api_logs/                    # API调用日志
│   ├── error_reports/               # 错误报告
│   └── status_snapshots/            # 状态快照
├── 第四步：监控数据/
│   ├── monitoring_logs/              # 监控日志
│   ├── progress_history/             # 进度历史
│   └── alerts/                       # 警报记录
└── 第五步：最终输出/
    ├── final_report.md               # 综合研究报告
    ├── executive_summary.md          # 执行摘要
    ├── action_plan.md                # 行动计划
    ├── knowledge_base/               # 知识库
    │   ├── findings_by_topic/        # 按主题分类的发现
    │   ├── patterns_insights/        # 模式和洞察
    │   └── recommendations/          # 建议库
    └── presentation/                 # 演示材料
        ├── slides.md                 # 幻灯片
        ├── visualizations/           # 可视化图表
        └── handouts/                 # 讲义材料
```

## 📄 核心文件说明（优化版）

### 1. master_task_plan.md (主任务规划)
- **目的**：详细定义总体研究目标、范围、子任务分解、时间规划
- **内容结构**：
  - **研究背景**：问题陈述、重要性分析
  - **总体目标**：明确的研究目标和关键问题
  - **研究范围**：包含范围和排除范围的明确定义
  - **子任务分解**：详细的子任务描述、目标、交付物
  - **依赖关系图**：可视化展示任务依赖关系
  - **时间规划**：详细的阶段划分和时间线
  - **资源分配**：工具、技能、时间的详细分配
  - **质量标准**：明确的质量标准和验收条件
  - **风险管理**：识别风险、评估、缓解措施

### 2. task_config.json (任务配置)
- **目的**：机器可读的任务配置和状态跟踪，支持自动化执行
- **内容结构**：
  - **任务元数据**：名称、描述、创建时间、版本
  - **子任务配置**：详细的任务配置、依赖、状态
  - **API配置**：API端点、认证、模型参数
  - **监控配置**：检查间隔、通知设置、警报阈值
  - **执行统计**：进度统计、性能指标、错误记录
  - **整合配置**：报告模板、输出格式、质量检查

### 3. 子任务文件集合
- **task_plan.md**：详细的子任务规划，包含具体的研究方法、数据来源、分析框架
- **findings.md**：结构化研究发现模板，支持自动提取和整合
- **progress.md**：详细的进度跟踪，包含里程碑、检查点、质量验证
- **配置和参考文件**：支持子任务执行的附加文件和配置

---

# 🔧 脚本工具集：支持五步执行模式

## 🛠️ 核心脚本说明

### 1. init_multi_task.py (初始化脚本)
- **功能**：执行第一步任务总规划和目录生成
- **增强特性**：
  - 支持依赖关系的子任务管理
  - 智能文件夹名称生成和验证
  - 自动创建完整的目录结构
  - 生成丰富的模板文件

### 2. enrich_task_files.py (新增：文件丰富化脚本)
- **功能**：支持第二步主任务和子任务文件丰富化
- **主要特性**：
  - 自动填充模板文件的关键部分
  - 确保文件之间的逻辑一致性
  - 添加丰富的示例和指导内容
  - 验证文件完整性和质量

### 3. start_subtasks.py (子任务启动脚本)
- **功能**：执行第三步子任务API优先下发
- **增强特性**：
  - 增强的错误处理和诊断功能
  - 详细的网络诊断和连通性检查
  - 依赖关系的拓扑排序和验证
  - 指数退避重试机制

### 4. continuous_monitor.py (新增：持续监控脚本)
- **功能**：执行第四步定期休眠监控
- **主要特性**：
  - 可配置的检查间隔（默认300秒）
  - 智能的状态变化检测
  - 自动的异常识别和警报
  - 渐进式的休眠策略

### 5. generate_final_report.py (新增：最终报告生成脚本)
- **功能**：执行第五步最终结果生成
- **主要特性**：
  - 自动收集和整合所有子任务结果
  - 智能的跨任务分析和模式识别
  - 多种输出格式支持（报告、摘要、行动计划）
  - 知识归档和结构化存储

## 🔄 脚本协同工作流

```
初始化 → 丰富化 → API下发 → 持续监控 → 结果生成
   ↓         ↓         ↓         ↓         ↓
init_multi_task.py → enrich_task_files.py → start_subtasks.py → continuous_monitor.py → generate_final_report.py
```

---

# 🎯 应用场景与案例示例

## 📈 场景一：技术趋势综合研究（五步模式实践）

**问题**："全面研究2026年AI智能体发展趋势，包括技术、市场、政策、应用等多个维度"

**五步执行模式实践**：

### 第一步：任务总规划
- 创建`ai_agent_trends_2026`项目目录
- 规划4个子任务：技术趋势、市场分析、政策研究、战略建议
- 定义依赖关系：前三者并行，战略建议依赖前三者
- 生成详细的主任务规划文档

### 第二步：文件丰富化
- 完善主任务规划中的研究范围和质量标准
- 为每个子任务创建丰富的研究模板：
  - 技术趋势：预设技术维度分析框架
  - 市场分析：预设市场规模、竞争格局分析模板
  - 政策研究：预设法规、伦理、安全分析框架
  - 战略建议：预设SWOT分析和战略矩阵

### 第三步：API优先下发
- 验证API配置，确保连通性
- 按依赖顺序启动子任务：先启动技术、市场、政策三个并行任务
- 监控启动状态，处理可能的错误
- 等待前三者完成后自动启动战略建议任务

### 第四步：定期休眠监控
- 设置5分钟检查间隔
- 监控各子任务进度，识别异常
- 在关键里程碑发送进度报告
- 自动检测依赖满足情况，适时触发后续任务

### 第五步：最终结果生成
- 自动整合四个子任务的发现
- 生成综合性研究报告和可执行的战略建议
- 创建知识库，归档关键发现和洞察
- 生成演示材料，支持决策沟通

**输出成果**：
1. 完整的五步执行过程文档
2. 综合性研究报告（80+页）
3. 执行摘要（1-2页）
4. 具体的战略行动计划
5. 可重用的知识库和模板

---

# ⚙️ 高级配置与自定义

## 🔧 API配置优化

```json
{
  "api_config": {
    "endpoint": "https://127.0.0.1/task",
    "auth_token": "您的认证令牌",
    "model_name": "deepseek-reasoner",
    "itecount": 200,
    "conversation_round": 5,
    "tool_choices": ["serper_search", "web_crawler", "python_execute"],
    "selected_skills": ["planning-with-files", "deep-research"],
    "priority": "high",  // 任务优先级
    "timeout": 120,      // 超时设置（秒）
    "retry_strategy": {  // 重试策略
      "max_retries": 3,
      "backoff_factor": 2,
      "retry_codes": [429, 500, 502, 503, 504]
    }
  }
}
```

## ⏱️ 监控配置优化

```json
{
  "monitoring": {
    "enabled": true,
    "interval_seconds": 300,
    "adaptive_interval": true,  // 自适应间隔
    "alert_thresholds": {
      "progress_stagnation": 3600,  // 进度停滞阈值（秒）
      "error_count": 3,             // 错误计数阈值
      "dependency_timeout": 7200    // 依赖超时阈值（秒）
    },
    "notifications": {
      "email": "user@example.com",
      "webhook": "https://hooks.slack.com/...",
      "critical_only": true
    },
    "reporting": {
      "daily_summary": true,
      "milestone_reports": true,
      "auto_integration": true  // 自动结果整合
    }
  }
}
```

## 📊 质量保证配置

```json
{
  "quality_assurance": {
    "checkpoints": [
      {
        "name": "规划完成检查",
        "criteria": ["master_task_plan完整", "子任务分解合理", "依赖关系明确"],
        "required": true
      },
      {
        "name": "文件丰富化检查", 
        "criteria": ["所有模板文件完整", "内容结构合理", "示例丰富"],
        "required": true
      },
      {
        "name": "API下发验证",
        "criteria": ["API连通性", "任务启动成功", "状态跟踪正常"],
        "required": true
      },
      {
        "name": "最终质量检查",
        "criteria": ["所有子任务完成", "发现整合完整", "建议具体可行"],
        "required": true
      }
    ],
    "scoring_system": {
      "completeness": 25,
      "accuracy": 25, 
      "depth": 20,
      "consistency": 15,
      "actionability": 15
    },
    "minimum_score": 80
  }
}
```

---

# 🛡️ 故障排除与最佳实践

## 🔍 常见问题与解决方案

### 问题1：API下发失败
**症状**：子任务无法通过API启动，返回连接错误或认证失败
**解决方案**：
1. 运行环境检查脚本：`python scripts/check_environment.py`
2. 验证API端点连通性：使用curl测试`curl -X GET {endpoint}/health`
3. 检查认证令牌是否正确且有权限
4. 考虑使用本地执行模式作为备用方案

### 问题2：文件丰富化不足
**症状**：模板文件内容过于简单，缺乏指导性
**解决方案**：
1. 运行文件丰富化脚本：`python scripts/enrich_task_files.py {task_dir}`
2. 参考最佳实践案例中的文件模板
3. 手动添加领域特定的示例和指导内容
4. 确保文件之间的引用和逻辑一致性

### 问题3：监控间隔不合理
**症状**：要么检查过于频繁导致资源浪费，要么检查间隔太长错过关键状态变化
**解决方案**：
1. 启用自适应间隔：`{"adaptive_interval": true}`
2. 基于任务阶段调整检查频率：
   - 规划阶段：低频率（如1小时）
   - 执行阶段：中频率（如5-15分钟）
   - 收尾阶段：高频率（如1-5分钟）
3. 基于进度变化动态调整：进度变化快时增加频率，稳定时减少频率

### 问题4：最终结果质量不足
**症状**：报告简单堆砌子任务结果，缺乏深度整合
**解决方案**：
1. 预留专门的整合时间（建议总时间的15-20%）
2. 使用系统化整合框架：
   - 主题聚类：将相关发现按主题组织
   - 矛盾分析：识别和解决不一致的发现
   - 模式识别：提取跨任务的模式和趋势
   - 优先级排序：基于影响和可行性排序建议
3. 多轮验证：至少进行两轮交叉验证和编辑

## 💡 最佳实践总结

### 规划阶段最佳实践
- 花费足够时间进行详细规划（15-20%总时间）
- 使用MECE原则确保子任务分解合理
- 明确依赖关系，避免循环依赖
- 设计可扩展的目录结构

### 执行阶段最佳实践
- 优先使用API下发，充分利用外部资源
- 实现健壮的错误处理和重试机制
- 保持适中的监控频率，平衡及时性和资源消耗
- 及时更新状态文件，确保信息准确性

### 整合阶段最佳实践
- 预留专门的整合时间，避免仓促收尾
- 使用系统化的整合框架，确保深度和一致性
- 生成多种形式的输出，满足不同受众需求
- 建立知识归档，支持未来重用和扩展

---

# 🌟 总结：五步执行模式的核心优势

多任务深度研究技能的**五步执行模式**将复杂的多任务研究项目系统化为可管理、可重复、高质量的标准化流程：

## 🎯 模式优势总结

1. **系统性规划** - 详细的任务总规划确保项目方向正确、结构合理
2. **深度准备** - 丰富的文件模板确保研究有明确的框架和指导
3. **高效执行** - API优先下发充分利用计算资源，实现智能调度
4. **持续跟踪** - 定期休眠监控确保及时发现和解决问题
5. **价值交付** - 综合性结果生成确保研究成果实用、可操作

## 🔄 模式进化：从复杂到简单

传统的多任务研究面临协调复杂、质量不一、整合困难等挑战。五步执行模式通过：

- **标准化**：将复杂过程分解为五个明确的步骤
- **自动化**：通过脚本工具支持各步骤的自动化执行
- **质量内建**：在每个步骤中嵌入质量控制机制
- **知识积累**：通过模板和案例积累最佳实践

## 🚀 立即开始您的五步多任务研究

**下一次当您面临复杂、多维度研究任务时，使用标准化的五步执行模式：**

启动关键词示例：
- "请使用五步执行模式研究[复杂问题]"
- "需要按照任务规划、文件丰富、API下发、定期监控、结果生成的流程分析[主题]"
- "帮我使用多任务深度研究技能，遵循五步模式协调研究[项目]"
- "为[决策]提供基于五步执行模式的综合研究报告"

---
**版本信息**: v1.2.0  
**更新日期**: 2026-03-05  
**核心价值**: 五步执行模式 + 任务目录规划 + API优先下发 + 定期休眠监控  
**适用对象**: 研究项目经理、战略分析师、学术研究者、企业决策者  
**质量承诺**: 系统性规划 + 深度准备 + 高效执行 + 持续跟踪 + 价值交付  
**持续愿景**: 打造最标准化、最高效、最可靠的企业级多任务研究平台
