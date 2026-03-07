#!/usr/bin/env python3
"""
多任务深度研究 - 任务管理器 v3.0

设计原则：
  - 零 hardcoding：所有路径通过 __file__ 动态推导或参数传入
  - Python-first：所有操作通过 python_execute 工具调用，无 shell 脚本依赖
  - 目录探查：提供 list_tasks / inspect_workspace 等探查方法
  - 状态持久化：所有状态写入 config.json，支持跨会话恢复
  - 非阻塞监控：check_and_dispatch_next() 每次调用只执行一次检查

用法（在 python_execute 中）：
  import sys
  sys.path.insert(0, "/app/.proteus/skills/multi-task-deep-research/scripts")
  from task_manager import TaskManager

  # 创建任务
  tm = TaskManager(token="YOUR_TOKEN")
  task_id = tm.create_task("任务名称", "研究目标")

  # 拆分子任务
  tm.split_subtasks([
      {"name": "market_research", "query": "详细指令...", "depends_on": []},
      {"name": "tech_analysis",   "query": "详细指令...", "depends_on": ["market_research"]},
  ])

  # 下发（第一批无依赖任务）
  tm.dispatch_all_by_dependency()

  # 后续轮次：检查 + 触发后续任务
  result = tm.check_and_dispatch_next()

  # 全部完成后汇总
  tm.collect_and_finalize()
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import uuid
import argparse
import requests
import urllib3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ─── 动态路径（零 hardcoding）────────────────────────────────────────────────
# 脚本所在目录 → 技能根目录
_SCRIPT_DIR  = Path(__file__).resolve().parent          # .../multi-task-deep-research/scripts
_SKILL_DIR   = _SCRIPT_DIR.parent                       # .../multi-task-deep-research
_TEMPLATES   = _SKILL_DIR / "templates"

# 默认任务存储目录（可在实例化时覆盖）
DEFAULT_TASKS_BASE = "/app/data/tasks"

# ─── API 默认参数 ─────────────────────────────────────────────────────────────
DEFAULT_API_URL            = "https://nginx/task"
DEFAULT_MODEL              = "deepseek-reasoner"
DEFAULT_ITECOUNT           = 200
DEFAULT_CONVERSATION_ROUND = 5
DEFAULT_TOOLS              = ["serper_search", "web_crawler", "python_execute"]
DEFAULT_SKILLS             = ["planning-with-files"]
MAX_RETRY                  = 3
RETRY_BACKOFF              = 2   # 指数退避基数（秒）
MAX_PARALLEL               = 3   # 最大并行下发数


# ─── 文件工具 ─────────────────────────────────────────────────────────────────

def _render_template(name: str, ctx: Dict) -> str:
    """渲染模板，替换 {key} 占位符；模板不存在时返回空白标题"""
    p = _TEMPLATES / name
    if not p.exists():
        return f"# {name}\n"
    text = p.read_text(encoding="utf-8")
    for k, v in ctx.items():
        text = text.replace("{" + k + "}", str(v) if v is not None else "")
    return text


def _write(path: str | Path, content: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def _read(path: str | Path) -> str:
    p = Path(path)
    return p.read_text(encoding="utf-8") if p.exists() else ""


def _save_config(cfg: Dict, task_dir: str | Path) -> None:
    _write(Path(task_dir) / "config.json",
           json.dumps(cfg, ensure_ascii=False, indent=2))


def _load_config(task_dir: str | Path) -> Dict:
    p = Path(task_dir) / "config.json"
    if not p.exists():
        raise FileNotFoundError(f"config.json 不存在: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


# ─── 依赖图工具 ───────────────────────────────────────────────────────────────

def _has_cycle(subtasks: List[Dict]) -> bool:
    """DFS 检测循环依赖"""
    graph = {s["name"]: s.get("depends_on", []) for s in subtasks}
    visited: set = set()
    stack:   set = set()

    def dfs(node: str) -> bool:
        visited.add(node)
        stack.add(node)
        for nb in graph.get(node, []):
            if nb not in visited:
                if dfs(nb):
                    return True
            elif nb in stack:
                return True
        stack.discard(node)
        return False

    return any(dfs(s["name"]) for s in subtasks if s["name"] not in visited)


def _topo_layers(subtasks: List[Dict]) -> List[List[Dict]]:
    """拓扑排序，返回分层列表（同层可并行）"""
    by_name   = {s["name"]: s for s in subtasks}
    in_degree = {s["name"]: len(s.get("depends_on", [])) for s in subtasks}
    remaining = set(in_degree)
    layers: List[List[Dict]] = []

    while remaining:
        ready = [n for n in remaining if in_degree[n] == 0]
        if not ready:
            raise ValueError("子任务依赖图存在循环，无法完成拓扑排序")
        layers.append([by_name[n] for n in ready])
        for n in ready:
            remaining.discard(n)
            for s in subtasks:
                if n in s.get("depends_on", []) and s["name"] in remaining:
                    in_degree[s["name"]] -= 1
    return layers


# ─── 主类 ─────────────────────────────────────────────────────────────────────

class TaskManager:
    """
    多任务深度研究管理器 v3.0

    所有路径通过 Python 动态推导，无 hardcoding。
    外部 agent 通过 python_execute 调用本类，无需任何 shell 脚本。
    """

    def __init__(
        self,
        token:          str  = "",
        api_url:        str  = DEFAULT_API_URL,
        tasks_base_dir: str  = DEFAULT_TASKS_BASE,
    ):
        self.token          = token
        self.api_url        = api_url
        self.tasks_base_dir = tasks_base_dir
        self.task_id:   Optional[str]  = None
        self.task_dir:  Optional[Path] = None
        self.config:    Optional[Dict] = None

    # ── 工作区探查（目录驱动，非 hardcoding）─────────────────────────────────

    @staticmethod
    def list_tasks(tasks_base_dir: str = DEFAULT_TASKS_BASE) -> List[Dict]:
        """
        列出 tasks_base_dir 下所有任务，通过读取 config.json 获取状态。
        返回列表，每项包含 task_id / task_name / status / created_at / subtask_count。
        """
        base = Path(tasks_base_dir)
        if not base.exists():
            return []
        result = []
        for d in sorted(base.iterdir()):
            if not d.is_dir():
                continue
            cfg_path = d / "config.json"
            if not cfg_path.exists():
                continue
            try:
                cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
                result.append({
                    "task_id":      cfg.get("task_id", d.name),
                    "task_name":    cfg.get("task_name", ""),
                    "status":       cfg.get("status", "unknown"),
                    "created_at":   cfg.get("created_at", ""),
                    "subtask_count": len(cfg.get("subtasks", [])),
                    "task_dir":     str(d),
                })
            except Exception as e:
                result.append({"task_id": d.name, "error": str(e)})
        return result

    @staticmethod
    def inspect_workspace(task_id_or_dir: str,
                          tasks_base_dir: str = DEFAULT_TASKS_BASE) -> Dict:
        """
        探查指定任务目录的完整状态：
        - 主任务 config / 文件列表
        - 每个子任务的目录内容 + 进度文件摘要
        无需 hardcoding 任何路径，完全通过 Python 目录遍历实现。
        """
        task_dir = _resolve_task_dir(task_id_or_dir, tasks_base_dir)
        cfg = _load_config(task_dir)

        def _file_summary(path: Path) -> Dict:
            if not path.exists():
                return {"exists": False}
            size = path.stat().st_size
            preview = path.read_text(encoding="utf-8")[:300] if size > 0 else ""
            return {"exists": True, "size_bytes": size, "preview": preview}

        subtask_details = []
        for s in cfg.get("subtasks", []):
            s_dir = Path(s["workspace_path"])
            subtask_details.append({
                "name":      s["name"],
                "status":    s["status"],
                "files": {
                    "config.json":   _file_summary(s_dir / "config.json"),
                    "task_plan.md":  _file_summary(s_dir / "task_plan.md"),
                    "findings.md":   _file_summary(s_dir / "findings.md"),
                    "progress.md":   _file_summary(s_dir / "progress.md"),
                    "completed.flag": _file_summary(s_dir / "completed.flag"),
                },
            })

        return {
            "task_id":     cfg.get("task_id"),
            "task_name":   cfg.get("task_name"),
            "status":      cfg.get("status"),
            "task_dir":    str(task_dir),
            "main_files": {
                "config.json":     _file_summary(task_dir / "config.json"),
                "task_plan.md":    _file_summary(task_dir / "task_plan.md"),
                "findings.md":     _file_summary(task_dir / "findings.md"),
                "progress.md":     _file_summary(task_dir / "progress.md"),
                "final_report.md": _file_summary(task_dir / "final_report.md"),
            },
            "subtasks": subtask_details,
        }

    # ── 创建任务 ──────────────────────────────────────────────────────────────

    def create_task(
        self,
        task_name:   str,
        goal:        str,
        description: str = "",
    ) -> str:
        """创建主任务目录和规划文件，返回 task_id"""
        ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
        uid = uuid.uuid4().hex[:6]
        self.task_id  = f"task_{ts}_{uid}"
        self.task_dir = Path(self.tasks_base_dir) / self.task_id
        (self.task_dir / "subtasks").mkdir(parents=True, exist_ok=True)

        self.config = {
            "task_id":      self.task_id,
            "task_name":    task_name,
            "goal":         goal,
            "description":  description,
            "created_at":   datetime.now().isoformat(),
            "token":        self.token,
            "api_endpoint": self.api_url,
            "status":       "created",
            "subtasks":     [],
        }
        _save_config(self.config, self.task_dir)
        self._init_main_files(task_name, goal, description)
        print(f"[TaskManager] ✅ 主任务已创建: {self.task_id}")
        print(f"[TaskManager] 📁 任务目录: {self.task_dir}")
        return self.task_id

    def _init_main_files(self, task_name: str, goal: str, description: str) -> None:
        now = datetime.now().isoformat()
        base_ctx = dict(
            task_name=task_name, task_id=self.task_id,
            created_at=now, goal=goal,
        )
        _write(self.task_dir / "task_plan.md",
               _render_template("main_task_plan.md", {
                   **base_ctx,
                   "current_phase": "Phase 1: 任务分析与拆解",
                   "token_masked":  "***（已隐藏）",
                   "subtask_table": "",
                   "phase1_status": "in_progress",
                   "phase2_status": "pending",
                   "phase3_status": "pending",
                   "phase4_status": "pending",
                   "decisions":     "|      |      |",
                   "errors":        "|      |      |      |",
               }))
        _write(self.task_dir / "findings.md",
               _render_template("findings.md", {
                   "subtask_name":  task_name,
                   "background":    description or goal,
                   "key_findings_1": "待研究",
                   "key_findings_2": "", "key_findings_3": "",
                   "data_support": "", "references": "", "future_research": "",
               }))
        _write(self.task_dir / "progress.md",
               _render_template("progress.md", {
                   "subtask_name":  task_name,
                   "date":          datetime.now().strftime("%Y-%m-%d"),
                   "current_phase": "Phase 1",
                   "start_time":    now,
                   "phase_name":    "任务创建",
                   "status":        "completed",
                   "action_1":      "主任务目录已创建",
                   "action_2":      "配置文件已初始化",
                   "phase":         "1",
                   "goal":          goal,
               }))

    # ── 加载任务（会话恢复） ──────────────────────────────────────────────────

    @classmethod
    def load_task(
        cls,
        task_id_or_dir:  str,
        tasks_base_dir:  str = DEFAULT_TASKS_BASE,
    ) -> "TaskManager":
        """
        从已有任务目录恢复 TaskManager。
        参数可以是：
          - task_id（如 task_20260307_143749_a1b2c3）
          - 完整路径（如 /app/data/tasks/task_xxx）
        会话中断后调用此方法即可无缝恢复，无需重新下发已完成的子任务。
        """
        task_dir = _resolve_task_dir(task_id_or_dir, tasks_base_dir)
        cfg = _load_config(task_dir)
        tm = cls(
            token=cfg.get("token", ""),
            api_url=cfg.get("api_endpoint", DEFAULT_API_URL),
            tasks_base_dir=tasks_base_dir,
        )
        tm.task_id  = cfg["task_id"]
        tm.task_dir = task_dir
        tm.config   = cfg
        print(f"[TaskManager] ✅ 任务已恢复: {tm.task_id}")
        print(f"[TaskManager] 📋 子任务数量: {len(cfg.get('subtasks', []))}")
        return tm

    # ── 子任务拆分 ────────────────────────────────────────────────────────────

    def split_subtasks(self, definitions: List[Dict]) -> List[str]:
        """
        拆分子任务并建立目录。

        definitions 格式：
          [
            {
              "name":       "market_research",   # 见名知意的英文名
              "query":      "详细研究指令...",    # 越详细越好
              "depends_on": [],                   # 依赖的子任务名列表
            },
            ...
          ]

        返回子任务 ID 列表。
        """
        if _has_cycle(definitions):
            raise ValueError("子任务依赖关系中存在循环依赖，请检查 depends_on 配置")

        ids = []
        for i, sd in enumerate(definitions):
            sid   = f"subtask_{i + 1:03d}"
            s_dir = self.task_dir / "subtasks" / sd["name"]
            s_dir.mkdir(parents=True, exist_ok=True)

            subtask = {
                "id":             sid,
                "name":           sd["name"],
                "query":          sd["query"],
                "depends_on":     sd.get("depends_on", []),
                "status":         "pending",
                "workspace_path": str(s_dir),
                "dispatched_at":  None,
                "completed_at":   None,
            }
            self.config["subtasks"].append(subtask)
            ids.append(sid)
            self._init_subtask_files(s_dir, sd, sid)

        _save_config(self.config, self.task_dir)
        print(f"[TaskManager] ✅ 已创建 {len(ids)} 个子任务")
        return ids

    def _init_subtask_files(self, s_dir: Path, sd: Dict, sid: str) -> None:
        now = datetime.now().isoformat()
        ctx_plan = dict(
            subtask_name=sd["name"], subtask_id=sid,
            parent_task_id=self.task_id, workspace_path=str(s_dir),
            goal=sd["query"],
            dependencies=", ".join(sd.get("depends_on", [])) or "无",
            status="pending", created_at=now, completed_at="",
            phase1_status="pending", phase2_status="pending", phase3_status="pending",
            findings="", resources="", errors="|      |      |      |",
        )
        _write(s_dir / "task_plan.md", _render_template("subtask_plan.md", ctx_plan))
        _write(s_dir / "findings.md",  _render_template("findings.md", {
            "subtask_name":  sd["name"], "background": sd["query"],
            "key_findings_1": "待研究",
            "key_findings_2": "", "key_findings_3": "",
            "data_support": "", "references": "", "future_research": "",
        }))
        _write(s_dir / "progress.md", _render_template("progress.md", {
            "subtask_name":  sd["name"],
            "date":          datetime.now().strftime("%Y-%m-%d"),
            "current_phase": "Phase 1",
            "start_time":    now,
            "phase_name":    "初始化",
            "status":        "pending",
            "action_1":      "子任务目录已创建",
            "action_2":      "等待下发执行",
            "phase":         "1",
            "goal":          sd["query"],
        }))
        # 子任务独立 config.json（执行引擎参考用）
        _write(s_dir / "config.json", json.dumps({
            "subtask_id":          sid,
            "parent_task_id":      self.task_id,
            "name":                sd["name"],
            "query":               sd["query"],
            "workspace_path":      str(s_dir),
            "status":              "pending",
            "depends_on":          sd.get("depends_on", []),
            "created_at":          now,
            "dispatched_at":       None,
            "completed_at":        None,
            "model_name":          DEFAULT_MODEL,
            "itecount":            DEFAULT_ITECOUNT,
            "conversation_round":  DEFAULT_CONVERSATION_ROUND,
            "tool_choices":        DEFAULT_TOOLS,
            "selected_skills":     DEFAULT_SKILLS,
        }, ensure_ascii=False, indent=2))

    # ── 下发单个子任务（含重试）──────────────────────────────────────────────

    def dispatch_subtask(self, subtask_name: str, **kwargs) -> Dict:
        """
        通过 Task API 下发子任务（自动重试 3 次，指数退避）。
        已 completed 的任务自动跳过。
        """
        subtask = self._find_subtask(subtask_name)
        if subtask["status"] == "completed":
            print(f"[TaskManager] ⏭️  {subtask_name} 已完成，跳过下发")
            return {}

        payload = {
            "query":               subtask["query"],
            "workspace_path":      subtask["workspace_path"],
            "modul":               "task",
            "model_name":          kwargs.get("model_name",          DEFAULT_MODEL),
            "itecount":            kwargs.get("itecount",            DEFAULT_ITECOUNT),
            "conversation_round":  kwargs.get("conversation_round",  DEFAULT_CONVERSATION_ROUND),
            "tool_choices":        DEFAULT_TOOLS,
            "selected_skills":     DEFAULT_SKILLS,
        }
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type":  "application/json",
        }

        last_err = None
        for attempt in range(1, MAX_RETRY + 1):
            try:
                resp = requests.post(
                    self.api_url, headers=headers, json=payload,
                    verify=False, timeout=30,
                )
                resp.raise_for_status()
                subtask["status"]        = "dispatched"
                subtask["dispatched_at"] = datetime.now().isoformat()
                _save_config(self.config, self.task_dir)
                print(f"[TaskManager] ✅ 已下发: {subtask_name} (attempt {attempt})")
                return resp.json()
            except Exception as e:
                last_err = e
                wait = RETRY_BACKOFF ** attempt
                print(f"[TaskManager] ⚠️  下发失败 (attempt {attempt}/{MAX_RETRY}): {e}，{wait}s 后重试")
                if attempt < MAX_RETRY:
                    time.sleep(wait)

        subtask["status"] = "failed"
        _save_config(self.config, self.task_dir)
        raise RuntimeError(
            f"子任务 {subtask_name} 下发失败（已重试 {MAX_RETRY} 次）: {last_err}"
        )

    # ── 按依赖顺序批量下发 ────────────────────────────────────────────────────

    def dispatch_all_by_dependency(self, max_parallel: int = MAX_PARALLEL, **kwargs) -> None:
        """
        下发当前就绪的第一批 pending 子任务（依赖均已 completed）。

        ⚠️  本方法只下发依赖已全部满足的任务（第一批），后续批次必须通过
        check_and_dispatch_next() 在每轮对话中逐步触发，以确保依赖按序完成。
        禁止在单次调用中一次性下发所有层次的任务。

        已 completed/dispatched 的任务自动跳过；受 max_parallel 限制。
        """
        completed_names = {
            s["name"] for s in self.config["subtasks"] if s["status"] == "completed"
        }
        dispatched_count = sum(
            1 for s in self.config["subtasks"] if s["status"] == "dispatched"
        )
        dispatched: List[str] = []

        for s in self.config["subtasks"]:
            if s["status"] != "pending":
                continue
            if all(dep in completed_names for dep in s.get("depends_on", [])):
                if dispatched_count >= max_parallel:
                    print(f"[TaskManager] ⏸️  已达并行上限 ({max_parallel})，剩余任务等待后续触发")
                    break
                try:
                    self.dispatch_subtask(s["name"], **kwargs)
                    dispatched.append(s["name"])
                    dispatched_count += 1
                except RuntimeError as e:
                    print(f"[TaskManager] ❌ {s['name']} 下发失败: {e}")

        if dispatched:
            pending_count = sum(
                1 for s in self.config["subtasks"] if s["status"] == "pending"
            )
            print(f"[TaskManager] 🚀 已下发第一批就绪任务: {dispatched}")
            if pending_count > 0:
                print(
                    f"[TaskManager] ⏳ 仍有 {pending_count} 个任务待后续轮次触发"
                    + "（依赖未满足或超出并行限制）"
                )
            print("[TaskManager] → 本轮结束，请等待子任务执行后在新一轮调用 check_and_dispatch_next()")
        else:
            print("[TaskManager] ℹ️  当前无就绪任务可下发")

    # ── 进度分析（纯文件读取，无网络调用）───────────────────────────────────

    def analyze_progress(self, subtask_name: str) -> float:
        """
        读取子任务工作区文件，计算完成进度分（0~100）。

        评分维度：
          - task_plan.md 中 [x] 完成率（40%）
          - findings.md  内容充实度（30%）
          - progress.md  完成关键词（30%）
          - completed.flag 文件存在（强制 100）
        """
        subtask = self._find_subtask(subtask_name, strict=False)
        if subtask is None:
            return 0.0

        s_dir = Path(subtask["workspace_path"])

        # completed.flag 强制完成
        if (s_dir / "completed.flag").exists():
            return 100.0

        score = 0.0

        # task_plan.md → [x] 完成率（40%）
        plan = _read(s_dir / "task_plan.md")
        if plan:
            done  = len(re.findall(r"- \[x\]", plan, re.IGNORECASE))
            todo  = len(re.findall(r"- \[ \]",  plan))
            total = done + todo
            if total > 0:
                score += (done / total) * 40

        # findings.md → 大小（30%）
        f_path = s_dir / "findings.md"
        if f_path.exists():
            size = f_path.stat().st_size
            score += 30 if size > 1000 else (15 if size > 500 else 0)

        # progress.md → 关键词（30%）
        prog = _read(s_dir / "progress.md").lower()
        if any(k in prog for k in ["总结", "结论", "complete", "finished", "100%", "已完成"]):
            score += 30

        return round(score, 1)

    def check_subtask_completed(self, subtask_name: str) -> bool:
        """判断子任务是否完成（进度 ≥ 90 或存在 completed.flag）"""
        subtask = self._find_subtask(subtask_name, strict=False)
        if subtask is None:
            return False
        if subtask["status"] == "completed":
            return True

        score = self.analyze_progress(subtask_name)
        s_dir = Path(subtask["workspace_path"])
        if (s_dir / "completed.flag").exists() or score >= 90.0:
            subtask["status"]       = "completed"
            subtask["completed_at"] = datetime.now().isoformat()
            _save_config(self.config, self.task_dir)
            print(f"[TaskManager] ✅ 子任务完成: {subtask_name} (score={score}%)")
            return True
        return False

    # ── 状态查询 ──────────────────────────────────────────────────────────────

    def get_all_status(self) -> Dict[str, str]:
        """返回所有子任务的最新状态（自动刷新 dispatched 任务）"""
        for s in self.config["subtasks"]:
            if s["status"] == "dispatched":
                self.check_subtask_completed(s["name"])
        return {s["name"]: s["status"] for s in self.config["subtasks"]}

    def is_all_completed(self) -> bool:
        return all(v == "completed" for v in self.get_all_status().values())

    # ── 核心监控 API（非阻塞）────────────────────────────────────────────────

    def check_and_dispatch_next(self, **kwargs) -> Dict:
        """
        非阻塞式监控核心方法（每轮对话调用一次，不循环等待）。

        执行逻辑：
          1. 刷新所有 dispatched 子任务的完成状态（读文件判断）
          2. 找出依赖已全部满足、且状态为 pending 的子任务 → 立即下发
          3. 返回结构化状态报告

        返回格式：
          {
            "status":           {"task_name": "completed|dispatched|pending|failed"},
            "newly_dispatched": ["task_name", ...],
            "pending":          ["task_name", ...],
            "all_completed":    True/False,
          }

        典型用法（每轮对话独立调用，不阻塞）：
          tm = TaskManager.load_task(task_id)
          result = tm.check_and_dispatch_next()
          if result["all_completed"]:
              tm.collect_and_finalize()
          else:
              print("未完成:", result["pending"])
              # 告知用户等待后再次触发
        """
        # Step 1: 刷新 dispatched 任务状态
        for s in self.config["subtasks"]:
            if s["status"] == "dispatched":
                self.check_subtask_completed(s["name"])

        # Step 2: 找可下发的 pending 任务
        completed_names = {
            s["name"] for s in self.config["subtasks"] if s["status"] == "completed"
        }
        dispatched_count = sum(
            1 for s in self.config["subtasks"] if s["status"] == "dispatched"
        )
        newly_dispatched: List[str] = []

        for s in self.config["subtasks"]:
            if s["status"] != "pending":
                continue
            if all(d in completed_names for d in s.get("depends_on", [])):
                if dispatched_count >= MAX_PARALLEL:
                    break
                try:
                    self.dispatch_subtask(s["name"], **kwargs)
                    newly_dispatched.append(s["name"])
                    dispatched_count += 1
                except RuntimeError as e:
                    print(f"[TaskManager] ❌ 触发下发失败: {s['name']}: {e}")

        # Step 3: 汇总
        all_status = {s["name"]: s["status"] for s in self.config["subtasks"]}
        pending    = [n for n, st in all_status.items() if st not in ("completed", "failed")]
        all_done   = len(pending) == 0

        if all_done:
            print("[TaskManager] ✅ 所有子任务已完成，可调用 collect_and_finalize()")
        else:
            print(f"[TaskManager] ⏳ 仍有 {len(pending)} 个任务未完成: {pending}")
            if newly_dispatched:
                print(f"[TaskManager] 🚀 本次新触发下发: {newly_dispatched}")
            print("[TaskManager] → 请等待后再次调用 check_and_dispatch_next()")

        return {
            "status":           all_status,
            "newly_dispatched": newly_dispatched,
            "pending":          pending,
            "all_completed":    all_done,
        }

    # ── 会话恢复 ──────────────────────────────────────────────────────────────

    def resume(self, **kwargs) -> None:
        """
        恢复执行：跳过已完成的子任务，继续下发未完成的子任务。
        适用于会话中断后的恢复场景。
        """
        print(f"[TaskManager] 🔄 恢复任务: {self.task_id}")
        status = self.get_all_status()
        print(f"[TaskManager] 当前状态: {status}")
        pending = [s for s in self.config["subtasks"] if s["status"] in ("pending", "failed")]
        if not pending:
            print("[TaskManager] ✅ 所有子任务已完成，无需恢复")
            return
        print(f"[TaskManager] 待执行: {[s['name'] for s in pending]}")
        self.dispatch_all_by_dependency(**kwargs)

    # ── 成果汇总 ──────────────────────────────────────────────────────────────

    def collect_and_finalize(self) -> str:
        """汇总所有子任务 findings，生成 final_report.md，返回报告路径"""
        task_name = self.config.get("task_name", "研究任务")
        goal      = self.config.get("goal", "")
        now       = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 收集子任务发现
        sections = []
        for s in self.config["subtasks"]:
            content = _read(Path(s["workspace_path"]) / "findings.md").strip()
            if content:
                sections.append(f"## {s['name']}\n\n{content}")

        # 子任务汇总表
        table_rows = "\n".join(
            f"| {s['name']} | {', '.join(s.get('depends_on', [])) or '无'} "
            f"| {s['status']} | {s.get('completed_at') or '-'} |"
            for s in self.config["subtasks"]
        )

        report = f"""# 最终研究报告：{task_name}

> 生成时间：{now}
> 任务 ID：{self.task_id}

---

## 执行摘要

（请在此处补充 200 字以内的核心结论）

---

## 研究背景与目标

{goal}

---

## 研究方法与子任务划分

| 子任务 | 依赖 | 状态 | 完成时间 |
|--------|------|------|----------|
{table_rows}

---

## 核心发现

{chr(10).join(sections) if sections else "（暂无发现）"}

---

## 综合分析与洞察

（基于以上各子任务发现，进行综合分析）

---

## 结论与建议

（核心结论和行动建议）

---

## 参考资料

（各子任务引用的主要资料来源）
"""
        report_path = self.task_dir / "final_report.md"
        _write(report_path, report)

        # 更新主任务 findings.md
        _write(self.task_dir / "findings.md",
               f"# 研究发现汇总：{task_name}\n\n" + "\n\n".join(sections))

        self.config["status"]       = "completed"
        self.config["completed_at"] = datetime.now().isoformat()
        _save_config(self.config, self.task_dir)

        print(f"[TaskManager] ✅ 最终报告已生成: {report_path}")
        return str(report_path)

    # ── 内部工具 ──────────────────────────────────────────────────────────────

    def _find_subtask(self, name: str, strict: bool = True) -> Optional[Dict]:
        for s in self.config["subtasks"]:
            if s["name"] == name:
                return s
        if strict:
            raise ValueError(f"子任务不存在: {name}")
        return None


# ─── 路径解析工具 ─────────────────────────────────────────────────────────────

def _resolve_task_dir(task_id_or_dir: str, tasks_base_dir: str) -> Path:
    """将 task_id 或完整路径解析为 Path 对象"""
    p = Path(task_id_or_dir)
    if p.is_absolute():
        return p
    return Path(tasks_base_dir) / task_id_or_dir


# ─── CLI 入口 ─────────────────────────────────────────────────────────────────

def _cli():
    parser = argparse.ArgumentParser(
        description="多任务深度研究 - 任务管理器 v3.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
命令示例：
  # 列出所有任务
  python task_manager.py list

  # 探查任务目录
  python task_manager.py inspect task_20260307_143749_a1b2c3

  # 查看任务状态
  python task_manager.py status task_20260307_143749_a1b2c3

  # 非阻塞检查 + 触发后续任务
  python task_manager.py check-next task_20260307_143749_a1b2c3

  # 汇总成果
  python task_manager.py collect task_20260307_143749_a1b2c3

  # 恢复中断任务
  python task_manager.py resume task_20260307_143749_a1b2c3
        """,
    )
    sub = parser.add_subparsers(dest="cmd")

    # list
    p_list = sub.add_parser("list", help="列出所有任务")
    p_list.add_argument("--base", default=DEFAULT_TASKS_BASE, help="任务根目录")

    # inspect
    p_inspect = sub.add_parser("inspect", help="探查任务目录（完整状态）")
    p_inspect.add_argument("task_id", help="任务ID或路径")
    p_inspect.add_argument("--base", default=DEFAULT_TASKS_BASE)

    # status
    p_status = sub.add_parser("status", help="查看任务状态")
    p_status.add_argument("task_id", help="任务ID或路径")
    p_status.add_argument("--base", default=DEFAULT_TASKS_BASE)

    # check-next
    p_cn = sub.add_parser("check-next", help="检查完成情况 + 触发后续任务（非阻塞）")
    p_cn.add_argument("task_id", help="任务ID或路径")
    p_cn.add_argument("--base", default=DEFAULT_TASKS_BASE)

    # collect
    p_col = sub.add_parser("collect", help="汇总成果，生成最终报告")
    p_col.add_argument("task_id", help="任务ID或路径")
    p_col.add_argument("--base", default=DEFAULT_TASKS_BASE)

    # resume
    p_res = sub.add_parser("resume", help="恢复中断的任务")
    p_res.add_argument("task_id", help="任务ID或路径")
    p_res.add_argument("--base", default=DEFAULT_TASKS_BASE)

    args = parser.parse_args()

    if args.cmd == "list":
        tasks = TaskManager.list_tasks(args.base)
        print(json.dumps(tasks, ensure_ascii=False, indent=2))

    elif args.cmd == "inspect":
        info = TaskManager.inspect_workspace(args.task_id, args.base)
        print(json.dumps(info, ensure_ascii=False, indent=2))

    elif args.cmd == "status":
        tm = TaskManager.load_task(args.task_id, args.base)
        print(json.dumps(tm.get_all_status(), ensure_ascii=False, indent=2))

    elif args.cmd == "check-next":
        tm = TaskManager.load_task(args.task_id, args.base)
        result = tm.check_and_dispatch_next()
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.cmd == "collect":
        tm = TaskManager.load_task(args.task_id, args.base)
        path = tm.collect_and_finalize()
        print(f"最终报告: {path}")

    elif args.cmd == "resume":
        tm = TaskManager.load_task(args.task_id, args.base)
        tm.resume()

    else:
        parser.print_help()


if __name__ == "__main__":
    _cli()
