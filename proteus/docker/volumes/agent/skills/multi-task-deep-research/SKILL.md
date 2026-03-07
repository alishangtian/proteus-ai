---
name: multi-task-deep-research
description: 融合深度研究技能和 planning-with-files 技能的多任务深度研究工作流。实现基于文件规划的多任务深度研究系统，支持主任务目录创建、子任务拆分、子任务目录建立、子任务下发、任务监控和成果产出。适用于复杂研究项目的系统性规划和分布式执行。
allowed-tools:
  - python_execute
  - serper_search
  - web_crawler
version: 3.0.0
---

# 多任务深度研究技能 (Multi-Task Deep Research)

融合 **deep-research** 与 **planning-with-files** 能力，通过 Task API 将复杂研究任务拆分为多个子任务并发执行，最终整合产出高质量研究报告。

> **核心原则**
> - **Python-first**：所有操作均通过 `python_execute` 调用 `task_manager.py`，无需 shell 脚本
> - **零 hardcoding**：路径通过 `__file__` 动态推导，目录探查通过 Python 遍历实现
> - **文件驱动**：所有状态写入文件，支持跨会话无缝恢复
> - **非阻塞监控**：禁止 while+sleep 阻塞；每轮对话独立调用 `check_and_dispatch_next()` 一次

---

## 触发条件

| 触发 | 不触发 |
|------|--------|
| 需要多角度深度调研的复杂课题 | 单一问题快速搜索 |
| 研究内容可拆分为 3~7 个子任务 | 简单信息查询 |
| 需要并行执行多个子任务 | 不需要拆分的单一研究 |

---

## 目录结构

```
/app/data/tasks/{task_id}/
├── config.json          # 主任务配置（含 Token、子任务列表、状态）
├── task_plan.md         # 主任务执行计划
├── findings.md          # 主任务研究发现汇总
├── progress.md          # 主任务进度日志
├── final_report.md      # 最终研究报告（完成后生成）
└── subtasks/
    ├── {subtask_name}/
    │   ├── config.json      # 子任务配置（执行引擎读取）
    │   ├── task_plan.md     # 子任务执行计划（含 [ ]/[x] 进度标记）
    │   ├── findings.md      # 子任务研究发现
    │   ├── progress.md      # 子任务执行进度
    │   └── completed.flag   # 完成标志（存在即视为完成）
    └── ...
```

**目录探查（Python 动态实现，非 hardcoding）**：

```python
import sys
sys.path.insert(0, "/app/.proteus/skills/multi-task-deep-research/scripts")
from task_manager import TaskManager

# 列出所有已存在的任务（读取各目录的 config.json）
tasks = TaskManager.list_tasks()   # 默认扫描 /app/data/tasks/
for t in tasks:
    print(t["task_id"], t["task_name"], t["status"])

# 探查某个任务的完整目录状态（文件大小、内容预览）
info = TaskManager.inspect_workspace("task_20260307_143749_a1b2c3")
print(info)
```

---

## 完整工作流程

### Step 0：获取 API Token（必须）

在开始任何操作前，**必须先向用户获取 Token**：
- 询问用户提供 API Token
- Token 仅存于 `config.json`，不在日志或报告中明文展示
- Token 格式示例：`f12ff351-9789-4c85-a1eb-d89ea8f6d8bc`

---

### Step 1：创建主任务

```python
import sys
sys.path.insert(0, "/app/.proteus/skills/multi-task-deep-research/scripts")
from task_manager import TaskManager

tm = TaskManager(token="用户提供的Token")
task_id = tm.create_task(
    task_name="AI医疗应用深度研究",
    goal="全面调研AI在医疗领域的应用现状、发展趋势和未来展望",
    description="可选背景说明"
)
print(f"任务已创建: {task_id}")
# 输出示例: 任务已创建: task_20260307_143749_a1b2c3
```

此步骤自动完成：
- 创建 `/app/data/tasks/{task_id}/` 目录结构
- 初始化 `config.json`（含 token、状态、子任务列表）
- 使用模板生成 `task_plan.md`、`findings.md`、`progress.md`

---

### Step 2：子任务拆分

基于第一性原理分析任务本质，按以下原则拆分：

| 原则 | 说明 |
|------|------|
| **独立性** | 每个子任务可独立执行，不依赖其他子任务的中间过程 |
| **完整性** | 所有子任务合并后覆盖主任务全部研究维度 |
| **粒度适中** | 每个子任务预计执行 5~20 分钟，过大则再拆分 |
| **依赖最小化** | 减少依赖链长度，提高并行度 |
| **命名规范** | `name` 必须是见名知意的英文，如 `market_research`、`tech_analysis` |

**子任务 Query 编写规范**（质量直接影响研究深度）：

```
✅ 好的 Query：
  "深度调研2024年国内大模型市场规模、主要玩家市占率、融资情况。
   需覆盖：(1)市场规模数据（引用权威报告）；(2)TOP5厂商产品对比；
   (3)近12个月融资事件（金额/轮次）；(4)技术差异化分析。
   输出需包含具体数据，来源需可信。"

❌ 差的 Query：
  "调研AI市场"
```

```python
subtask_definitions = [
    {
        "name":       "market_research",
        "query":      "详细研究指令（包含研究对象+具体维度+输出要求+质量标准）...",
        "depends_on": []
    },
    {
        "name":       "tech_analysis",
        "query":      "详细研究指令...",
        "depends_on": ["market_research"]   # 依赖 market_research 完成后执行
    },
    {
        "name":       "competitor_analysis",
        "query":      "详细研究指令...",
        "depends_on": ["market_research"]   # 与 tech_analysis 并行
    },
    {
        "name":       "final_synthesis",
        "query":      "基于以上研究整合分析...",
        "depends_on": ["tech_analysis", "competitor_analysis"]
    }
]
tm.split_subtasks(subtask_definitions)
# 自动完成：循环依赖检测、目录创建、模板文件初始化
```

**依赖 DAG 示意**：
```
market_research ──→ tech_analysis ──┐
                └──→ competitor_analysis ──┘──→ final_synthesis
```

执行层次（拓扑排序自动计算）：
```
第1层: market_research          ← 立即下发
第2层: tech_analysis             ← 第1层完成后并行下发
       competitor_analysis
第3层: final_synthesis           ← 第2层全部完成后下发
```

---

### Step 3：下发第一批子任务

```python
# 仅下发依赖已全部满足的第一批任务（无依赖的任务）
# 有依赖的任务会在后续监控轮次中由 check_and_dispatch_next() 自动触发
tm.dispatch_all_by_dependency(max_parallel=3)
```

> ⚠️ **重要**：`dispatch_all_by_dependency()` **只下发第一批就绪任务**（依赖已满足的），
> 后续批次（有依赖的任务）必须通过 Step 4 的 `check_and_dispatch_next()` 逐步触发。
> **下发完成后，必须立即告知用户等待，并结束本轮对话。**
> **严禁在同一轮对话中直接调用 `collect_and_finalize()`。**

**告知用户的标准输出格式**：
```
已下发第一批子任务：[任务名列表]
任务 ID：task_20260307_143749_a1b2c3

请等待约 X 分钟后，在新的对话中输入：
"检查任务 task_20260307_143749_a1b2c3 的进度"
（根据子任务复杂度，简单查询等 3~5 分钟，标准研究等 8~15 分钟，复杂研究等 15~30 分钟）
```

**下发原理**（在 task_manager.py 内部实现，无需外部 curl）：
- 从 `config.json` 读取 `token` 和 `api_endpoint`
- 构建 payload（含 query、workspace_path、model 参数）
- POST 到 Task API，自动重试 3 次（指数退避：2s/4s/8s）
- 下发成功后更新子任务状态为 `dispatched`，持久化到 `config.json`

---

### Step 4：非阻塞式监控（每轮对话独立调用）

> ⚠️ **禁止** 在单次 `python_execute` 中使用 `while/sleep` 阻塞等待。
> ⚠️ **禁止** 在下发子任务的同一轮对话中直接进入 Step 5。
> 正确模式：**下发 → 本轮结束告知用户等待 → 用户触发新一轮 → 调用 `check_and_dispatch_next()`**

#### 标准监控模式（每轮对话执行）

```python
import sys
sys.path.insert(0, "/app/.proteus/skills/multi-task-deep-research/scripts")
from task_manager import TaskManager

# 从文件恢复任务状态（无内存依赖，支持跨会话）
tm = TaskManager.load_task("task_20260307_143749_a1b2c3")

# 一次性检查 + 触发后续依赖任务
result = tm.check_and_dispatch_next()

print("当前状态:", result["status"])
print("新下发任务:", result["newly_dispatched"])
print("未完成任务:", result["pending"])
print("是否全部完成:", result["all_completed"])

if result["all_completed"]:
    # 仅当所有子任务均已 completed 时，才进入 Step 5
    report_path = tm.collect_and_finalize()
    print(f"最终报告: {report_path}")
else:
    # 必须告知用户等待，绝对不能在本轮直接汇总报告
    print("仍有未完成任务，请等待后在新一轮对话中再次触发检查")
    # 告知用户建议等待时间和下一步操作
```

> ⚠️ **关键约束**：
> - 当 `result["all_completed"]` 为 `False` 时，**必须结束本轮对话，告知用户等待**
> - **不得**在 `all_completed=False` 的情况下调用 `collect_and_finalize()`
> - 新下发的任务（`newly_dispatched`）说明有依赖链上的后续任务刚被触发，仍需等待

#### `check_and_dispatch_next()` 内部逻辑

```
1. 遍历所有 dispatched 子任务 → 读取工作区文件 → 计算完成分数
   - task_plan.md 中 [x] 完成率  → 40%
   - findings.md  内容大小       → 30%（>1000字节=满分）
   - progress.md  完成关键词     → 30%（含"总结/结论/complete/100%"）
   - completed.flag 文件存在     → 强制 100 分

2. 分数 ≥ 90 或 completed.flag 存在 → 标记为 completed，写入 config.json

3. 找出依赖已全部 completed 的 pending 任务 → 立即下发（受 MAX_PARALLEL=3 限制）

4. 返回结构化报告
```

#### 返回结构说明

| 字段 | 类型 | 含义 |
|------|------|------|
| `status` | `Dict[str, str]` | 所有子任务的最新状态 |
| `newly_dispatched` | `List[str]` | 本次新触发下发的任务名 |
| `pending` | `List[str]` | 仍未完成的任务名 |
| `all_completed` | `bool` | 是否所有任务均已完成 |

#### 建议检查间隔

| 子任务复杂度 | 建议等待时间 |
|-------------|------------|
| 简单查询（1~2 次搜索） | 3~5 分钟 |
| 标准研究任务 | 8~15 分钟 |
| 复杂深度研究 | 15~30 分钟 |

---

### Step 5：成果汇总与报告生成

```python
tm = TaskManager.load_task("task_20260307_143749_a1b2c3")
report_path = tm.collect_and_finalize()
# 生成 /app/data/tasks/{task_id}/final_report.md
```

**最终报告结构**：
```markdown
# 最终研究报告：{任务名称}
## 执行摘要
## 研究背景与目标
## 研究方法与子任务划分（含状态表）
## 核心发现（各子任务 findings.md 汇总）
## 综合分析与洞察
## 结论与建议
## 参考资料
```

---

## 会话恢复

任务执行中断后（如会话被清除），通过以下方式恢复：

```python
import sys
sys.path.insert(0, "/app/.proteus/skills/multi-task-deep-research/scripts")
from task_manager import TaskManager

# 方式一：先探查所有任务，找到目标任务
tasks = TaskManager.list_tasks()   # 扫描 /app/data/tasks/ 下所有 config.json
for t in tasks:
    print(t["task_id"], t["status"], t["subtask_count"], "个子任务")

# 方式二：直接用 task_id 恢复（从 config.json 读取所有状态）
tm = TaskManager.load_task("task_20260307_143749_a1b2c3")

# 查看详细状态
status = tm.get_all_status()
print(status)

# 继续执行（自动跳过已完成任务，下发未完成任务）
tm.resume()
```

---

## 状态流转

```
pending → dispatched → completed
                    ↘ failed → (重试) → dispatched
```

| 状态 | 描述 |
|------|------|
| `pending` | 子任务已定义，等待下发 |
| `dispatched` | 已通过 Task API 下发，执行中 |
| `completed` | 已完成（进度≥90% 或存在 `completed.flag`） |
| `failed` | 下发失败（已重试 3 次） |

---

## 错误处理

| 错误类型 | 处理策略 |
|----------|----------|
| API 调用失败 | 自动重试 3 次（指数退避：2s/4s/8s） |
| 循环依赖 | `split_subtasks()` 时自动检测并抛出异常 |
| 子任务执行超时 | 手动调用 `tm.dispatch_subtask("task_name")` 重新下发 |
| 依赖任务失败 | 修复后调用 `tm.resume()` |
| 会话中断 | `TaskManager.load_task(task_id)` 恢复，自动跳过已完成任务 |

---

## 任务结束标准

- [ ] 所有子任务状态均为 `completed`
- [ ] `final_report.md` 已生成，包含执行摘要、核心发现、结论建议
- [ ] 主任务 `config.json` 中 `status` 已更新为 `completed`
- [ ] `findings.md` 已汇总所有子任务发现

---

## 完整调用示例

```python
import sys
sys.path.insert(0, "/app/.proteus/skills/multi-task-deep-research/scripts")
from task_manager import TaskManager

# ── 第一轮对话：创建并下发第一批 ────────────────────────────────────────────
tm = TaskManager(token="YOUR_TOKEN_HERE")
task_id = tm.create_task("大模型市场研究", "调研2024年国内大模型市场格局")

tm.split_subtasks([
    {
        "name":       "market_size",
        "query":      "调研2024年国内大模型市场规模（引用艾瑞/IDC等权威报告），"
                      "包含市场规模数据、增速、细分赛道占比。",
        "depends_on": []
    },
    {
        "name":       "player_analysis",
        "query":      "深度分析国内大模型TOP10厂商（百度/阿里/腾讯/华为/字节等），"
                      "对比产品能力、商业化进展、用户规模数据。",
        "depends_on": []
    },
    {
        "name":       "investment_trend",
        "query":      "调研2023-2024年国内大模型领域投融资情况，"
                      "包含融资事件列表、金额、轮次、主要投资机构。",
        "depends_on": ["market_size"]
    },
    {
        "name":       "final_synthesis",
        "query":      "基于市场规模、玩家分析、投融资数据，撰写综合研究报告，"
                      "提炼核心洞察和未来趋势判断。",
        "depends_on": ["player_analysis", "investment_trend"]
    }
])

# 仅下发第一批（无依赖）任务：market_size + player_analysis
# investment_trend 和 final_synthesis 依赖未满足，不会在此处下发
tm.dispatch_all_by_dependency()
# ⛔ 本轮对话到此结束！告知用户等待，严禁继续调用 collect_and_finalize()
print(f"任务ID: {task_id}，已下发第一批子任务（market_size, player_analysis）")
print("请等待 10~15 分钟后，在新的对话中发送：检查任务进度")

# ── 第二轮及后续轮次：检查 + 触发后续任务 ───────────────────────────────────
# 每次用户触发检查时，在新的一轮对话中执行：
tm = TaskManager.load_task(task_id)
result = tm.check_and_dispatch_next()
# check_and_dispatch_next() 会：
#   1. 检测 market_size/player_analysis 是否完成
#   2. 若 market_size 完成 → 自动下发 investment_trend
#   3. 若 player_analysis 和 investment_trend 均完成 → 自动下发 final_synthesis
if result["all_completed"]:
    # 只有 all_completed=True 时才能汇总报告
    report = tm.collect_and_finalize()
    print(f"研究完成！报告路径: {report}")
else:
    print(f"进行中: {result['status']}")
    print(f"本轮新下发: {result['newly_dispatched']}")
    print(f"未完成: {result['pending']}")
    print("请继续等待，下次触发检查时将自动推进")
```
