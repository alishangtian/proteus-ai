"""
多任务深度研究基础功能模块 - 优化版
提供原子性的文件操作功能，供外部系统调用以构建自定义研究流程。

设计原则：
1. 极简函数接口 - 6个核心函数
2. 专注文件操作 - 只处理文件系统，无研究逻辑
3. 标准化返回格式 - 统一 {"ok": bool, "data": {}, "error": ""}
4. 灵活模板系统 - 支持自定义模板路径
"""

import os
import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

def _standard_response(ok: bool, data: Dict[str, Any] = None, error: str = "") -> Dict[str, Any]:
    """标准化响应格式"""
    return {
        "ok": ok,
        "data": data or {},
        "error": error
    }

def init_workspace(workspace_path: str, 
                   plan_content: str = "# 研究项目\n\n## 目标",
                   template_path: Optional[str] = None,
                   overwrite: bool = False) -> Dict[str, Any]:
    """
    初始化研究工作区
    
    Args:
        workspace_path: 工作区目录路径
        plan_content: 任务规划内容 (Markdown格式)
        template_path: 模板路径，None时使用默认模板
        overwrite: 是否覆盖已存在的工作区
    
    Returns:
        标准化响应格式
    """
    workspace = Path(workspace_path)
    
    # 检查工作区是否已存在
    if workspace.exists() and not overwrite:
        return _standard_response(False, error=f"工作区已存在: {workspace_path}")
    
    # 使用默认模板路径
    if template_path is None:
        template_path = "../templates"
    
    template_dir = Path(template_path)
    
    try:
        # 创建工作区目录
        workspace.mkdir(parents=True, exist_ok=True)
        
        # 创建标准子目录
        subtasks_dir = workspace / "subtasks"
        subtasks_dir.mkdir(exist_ok=True)
        
        reports_dir = workspace / "reports"
        reports_dir.mkdir(exist_ok=True)
        
        files_created = []
        
        # 创建或复制标准文件
        standard_files = ["task_plan.md", "findings.md", "progress.md"]
        for filename in standard_files:
            src_path = template_dir / filename
            dest_path = workspace / filename
            
            if src_path.exists():
                shutil.copy2(src_path, dest_path)
            else:
                # 创建默认文件
                if filename == "task_plan.md":
                    content = plan_content
                else:
                    content = f"# {filename.replace('.md', '').replace('_', ' ').title()}\n\n"
                
                with open(dest_path, 'w', encoding='utf-8') as f:
                    f.write(content)
            
            files_created.append(str(dest_path))
        
        # 写入任务规划内容
        plan_path = workspace / "task_plan.md"
        with open(plan_path, 'w', encoding='utf-8') as f:
            f.write(plan_content)
        
        # 创建元数据文件
        metadata = {
            "created_at": datetime.now().isoformat(),
            "workspace_path": str(workspace),
            "template_used": str(template_dir),
            "version": "3.0.0-optimized"
        }
        
        metadata_path = workspace / ".workspace_meta.json"
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        files_created.append(str(metadata_path))
        
        return _standard_response(True, data={
            "workspace_path": str(workspace),
            "files_created": files_created,
            "directories": [str(subtasks_dir), str(reports_dir)],
            "metadata": metadata
        })
        
    except Exception as e:
        return _standard_response(False, error=str(e))

def add_subtasks(workspace_path: str, 
                subtasks: List[Dict[str, Any]],
                template_path: Optional[str] = None) -> Dict[str, Any]:
    """
    添加子任务到工作区
    
    Args:
        workspace_path: 工作区目录路径
        subtasks: 子任务定义列表，每个元素需要包含:
                 - id: 子任务唯一标识
                 - name: 子任务名称 (可选)
                 - description: 子任务描述 (可选)
        template_path: 子任务模板路径，None时使用默认模板
    
    Returns:
        标准化响应格式
    """
    workspace = Path(workspace_path)
    subtasks_dir = workspace / "subtasks"
    
    if not workspace.exists():
        return _standard_response(False, error=f"工作区不存在: {workspace_path}")
    
    # 使用默认模板路径
    if template_path is None:
        template_path = "../templates/subtask_template"
    
    template_dir = Path(template_path)
    
    created = []
    subtask_info = {}
    
    try:
        for subtask_def in subtasks:
            subtask_id = subtask_def.get("id")
            if not subtask_id:
                continue
            
            # 创建子任务目录
            subtask_dir = subtasks_dir / subtask_id
            subtask_dir.mkdir(parents=True, exist_ok=True)
            
            # 创建子任务文件
            subtask_files = ["task_plan.md", "findings.md", "progress.md"]
            for filename in subtask_files:
                src_path = template_dir / filename
                dest_path = subtask_dir / filename
                
                if src_path.exists():
                    shutil.copy2(src_path, dest_path)
                
                # 如果是任务规划文件，填充基本信息
                if filename == "task_plan.md" and dest_path.exists():
                    with open(dest_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # 简单的占位符替换
                    name = subtask_def.get("name", subtask_id)
                    description = subtask_def.get("description", "")
                    
                    content = content.replace("[子任务描述]", description)
                    content = content.replace("[子任务ID]", subtask_id)
                    content = content.replace("[研究主题]", name)
                    
                    with open(dest_path, 'w', encoding='utf-8') as f:
                        f.write(content)
            
            created.append(subtask_id)
            subtask_info[subtask_id] = {
                "path": str(subtask_dir),
                "name": subtask_def.get("name", subtask_id),
                "description": subtask_def.get("description", "")
            }
        
        return _standard_response(True, data={
            "subtasks_created": created,
            "subtask_info": subtask_info,
            "total_created": len(created)
        })
        
    except Exception as e:
        return _standard_response(False, data={
            "subtasks_created": created,
            "subtask_info": subtask_info
        }, error=str(e))

def log_finding(workspace_path: str, 
               target: str,  # "root" 或 "subtasks/{id}"
               title: str,
               content: str,
               metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    记录研究发现
    
    Args:
        workspace_path: 工作区目录路径
        target: 记录目标，"root"表示总发现，否则为"subtasks/{id}"
        title: 发现标题
        content: 发现内容
        metadata: 附加元数据，如分类、来源、可信度等
    
    Returns:
        标准化响应格式
    """
    workspace = Path(workspace_path)
    
    if not workspace.exists():
        return _standard_response(False, error=f"工作区不存在: {workspace_path}")
    
    try:
        # 确定目标文件
        if target == "root":
            target_file = workspace / "findings.md"
        elif target.startswith("subtasks/"):
            subtask_id = target.replace("subtasks/", "")
            target_file = workspace / "subtasks" / subtask_id / "findings.md"
        else:
            target_file = workspace / target / "findings.md" if target.endswith("/") else workspace / f"{target}/findings.md"
        
        # 确保目录存在
        target_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 确保文件存在
        if not target_file.exists():
            with open(target_file, 'w', encoding='utf-8') as f:
                f.write("# 研究发现\n\n")
        
        # 构建发现条目
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"\n## {title}\n\n"
        entry += f"**时间:** {timestamp}\n"
        
        # 添加元数据
        if metadata:
            for key, value in metadata.items():
                if isinstance(value, list):
                    entry += f"**{key}:**\n"
                    for item in value:
                        entry += f"- {item}\n"
                    entry += "\n"
                else:
                    entry += f"**{key}:** {value}\n"
        
        entry += f"\n{content}\n\n"
        entry += "---\n"
        
        # 追加到文件
        with open(target_file, 'a', encoding='utf-8') as f:
            f.write(entry)
        
        finding_id = f"finding_{int(datetime.now().timestamp())}"
        
        return _standard_response(True, data={
            "file_path": str(target_file),
            "finding_id": finding_id,
            "timestamp": timestamp,
            "target": target,
            "entry_length": len(entry)
        })
        
    except Exception as e:
        return _standard_response(False, error=str(e))

def update_status(workspace_path: str,
                 subtask_id: str,
                 status: str,  # "pending", "working", "completed"
                 progress: int = 0,  # 0-100
                 note: str = "") -> Dict[str, Any]:
    """
    更新子任务状态
    
    Args:
        workspace_path: 工作区目录路径
        subtask_id: 子任务ID
        status: 状态值
        progress: 进度百分比 (0-100)
        note: 状态说明
    
    Returns:
        标准化响应格式
    """
    workspace = Path(workspace_path)
    status_file = workspace / "subtasks" / subtask_id / "progress.md"
    
    if not workspace.exists():
        return _standard_response(False, error=f"工作区不存在: {workspace_path}")
    
    if not status_file.exists():
        return _standard_response(False, error=f"状态文件不存在: {status_file}")
    
    try:
        # 读取当前内容
        with open(status_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 更新状态信息
        lines = content.split('\n')
        updated_lines = []
        
        for line in lines:
            if "**状态:**" in line:
                line = f"**状态:** {status}"
            elif "**进度:**" in line:
                line = f"**进度:** {progress}%"
            elif "最后更新" in line:
                line = f"**最后更新:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            updated_lines.append(line)
        
        # 添加说明
        if note:
            note_entry = f"- {datetime.now().strftime('%H:%M')}: {note}\n"
            note_added = False
            
            for i, line in enumerate(updated_lines):
                if "活动记录" in line or "说明" in line:
                    updated_lines.insert(i + 1, note_entry)
                    note_added = True
                    break
            
            if not note_added:
                updated_lines.append(f"\n## 说明\n{note_entry}")
        
        # 写回文件
        with open(status_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(updated_lines))
        
        # 更新总进度文件
        total_progress_file = workspace / "progress.md"
        if total_progress_file.exists():
            with open(total_progress_file, 'a', encoding='utf-8') as f:
                f.write(f"\n{subtask_id}: {status} ({progress}%) - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        
        return _standard_response(True, data={
            "subtask_id": subtask_id,
            "status": status,
            "progress": progress,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return _standard_response(False, error=str(e))

def check_status(workspace_path: str, detailed: bool = False) -> Dict[str, Any]:
    """
    检查工作区状态
    
    Args:
        workspace_path: 工作区目录路径
        detailed: 是否返回详细信息
    
    Returns:
        标准化响应格式
    """
    workspace = Path(workspace_path)
    
    if not workspace.exists():
        return _standard_response(False, error=f"工作区不存在: {workspace_path}")
    
    try:
        subtasks_dir = workspace / "subtasks"
        
        subtask_status = {}
        all_completed = True
        total_progress = 0
        subtask_count = 0
        pending_tasks = []
        
        if subtasks_dir.exists():
            for subtask_dir in subtasks_dir.iterdir():
                if not subtask_dir.is_dir():
                    continue
                
                subtask_id = subtask_dir.name
                progress_file = subtask_dir / "progress.md"
                
                status = "unknown"
                progress = 0
                
                if progress_file.exists():
                    with open(progress_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # 提取状态
                    for line in content.split('\n'):
                        if "**状态:**" in line:
                            status = line.split("**状态:**")[1].strip()
                            break
                        elif "状态:" in line:
                            status = line.split("状态:")[1].strip()
                            break
                    
                    # 提取进度
                    for line in content.split('\n'):
                        if "**进度:**" in line:
                            import re
                            match = re.search(r'(\d+)%', line)
                            if match:
                                progress = int(match.group(1))
                            break
                
                subtask_status[subtask_id] = {
                    "status": status,
                    "progress": progress,
                    "path": str(subtask_dir)
                }
                
                if status != "completed":
                    all_completed = False
                    if status == "pending":
                        pending_tasks.append(subtask_id)
                
                total_progress += progress
                subtask_count += 1
        
        overall_progress = total_progress / subtask_count if subtask_count > 0 else 0
        
        data = {
            "all_completed": all_completed,
            "overall_progress": round(overall_progress, 1),
            "subtask_count": subtask_count,
            "pending_tasks": pending_tasks,
            "check_time": datetime.now().isoformat()
        }
        
        if detailed:
            data["subtask_status"] = subtask_status
        
        return _standard_response(True, data=data)
        
    except Exception as e:
        return _standard_response(False, error=str(e))

def generate_summary(workspace_path: str,
                    template_path: Optional[str] = None,
                    output_format: str = "markdown") -> Dict[str, Any]:
    """
    生成研究总结报告
    
    Args:
        workspace_path: 工作区目录路径
        template_path: 报告模板路径，None时使用默认模板
        output_format: 输出格式，目前仅支持"markdown"
    
    Returns:
        标准化响应格式
    """
    workspace = Path(workspace_path)
    
    if not workspace.exists():
        return _standard_response(False, error=f"工作区不存在: {workspace_path}")
    
    try:
        # 收集基本信息
        subtasks_dir = workspace / "subtasks"
        findings = []
        
        if subtasks_dir.exists():
            for subtask_dir in subtasks_dir.iterdir():
                if not subtask_dir.is_dir():
                    continue
                
                findings_file = subtask_dir / "findings.md"
                if findings_file.exists():
                    with open(findings_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # 简单提取章节
                    lines = content.split('\n')
                    current_section = ""
                    current_content = []
                    
                    for line in lines:
                        if line.startswith('## '):
                            if current_section and current_content:
                                findings.append({
                                    "subtask": subtask_dir.name,
                                    "section": current_section,
                                    "content": '\n'.join(current_content)
                                })
                            current_section = line[3:].strip()
                            current_content = []
                        elif line.strip() and not line.startswith('#') and line.strip() != '---':
                            current_content.append(line.strip())
                    
                    if current_section and current_content:
                        findings.append({
                            "subtask": subtask_dir.name,
                            "section": current_section,
                            "content": '\n'.join(current_content)
                        })
        
        # 生成报告内容
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        subtask_count = len([d for d in subtasks_dir.iterdir() if d.is_dir()]) if subtasks_dir.exists() else 0
        
        report_content = f"""# 研究总结报告

## 概览
- **生成时间:** {timestamp}
- **工作区:** {workspace_path}
- **子任务数量:** {subtask_count}
- **研究发现数量:** {len(findings)}

## 主要发现
"""
        
        if findings:
            for i, finding in enumerate(findings[:5], 1):
                preview = finding['content'][:100] + "..." if len(finding['content']) > 100 else finding['content']
                report_content += f"{i}. **{finding['section']}** (来自 {finding['subtask']})\n"
                report_content += f"   {preview}\n\n"
        else:
            report_content += "暂无研究发现。\n\n"
        
        report_content += """## 状态总结

请检查各子任务的状态和进度。

## 下一步建议

基于当前研究进展，建议：

1. 审查研究发现的质量和完整性
2. 确保所有子任务都有明确的状态
3. 根据需要进行深入研究
4. 整理最终成果

---

*本报告由多任务深度研究基础功能生成。*
"""
        
        # 保存报告
        reports_dir = workspace / "reports"
        reports_dir.mkdir(exist_ok=True)
        
        report_filename = f"summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        report_path = reports_dir / report_filename
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        # 创建便捷链接
        summary_link = workspace / "latest_summary.md"
        if summary_link.exists():
            summary_link.unlink()
        
        try:
            summary_link.symlink_to(report_path.relative_to(workspace))
        except:
            # 如果不支持符号链接，则复制文件
            shutil.copy2(report_path, summary_link)
        
        return _standard_response(True, data={
            "report_path": str(report_path),
            "summary_link": str(summary_link),
            "findings_count": len(findings),
            "report_length": len(report_content),
            "format": output_format
        })
        
    except Exception as e:
        return _standard_response(False, error=str(e))

# 导出所有函数
__all__ = [
    "init_workspace",
    "add_subtasks", 
    "log_finding",
    "update_status",
    "check_status",
    "generate_summary"
]
