#!/usr/bin/env python3
"""
多任务深度研究整合脚本 - 简化增强版
智能整合子任务研究发现，生成结构化综合报告
"""

import os
import json
import re
from datetime import datetime

def extract_key_findings(content, max_chars=2000):
    """
    从研究发现内容中提取关键发现
    """
    if not content or len(content.strip()) < 100:
        return "无实质性发现或内容过短"
    
    # 尝试提取章节
    sections = []
    
    # 查找所有## 标题（二级标题）
    section_pattern = r'##\s+(.+?)\n(.*?)(?=\n##\s+|$)'
    matches = re.findall(section_pattern, content, re.DOTALL)
    
    if matches:
        for title, section_content in matches:
            if len(section_content.strip()) > 100:
                cleaned = re.sub(r'\n{3,}', '\n\n', section_content.strip())
                if len(cleaned) > 500:
                    cleaned = cleaned[:500] + "..."
                sections.append("### " + title + "\n" + cleaned + "\n")
    
    if sections:
        return "\n".join(sections)
    
    # 尝试提取要点
    bullet_pattern = r'[-*•]\s+(.+?)(?=\n[-*•]|\n\n|$)'
    bullets = re.findall(bullet_pattern, content, re.DOTALL)
    
    if bullets and len(bullets) > 2:
        key_bullets = bullets[:5]
        bullet_text = "\n".join(["- " + bullet.strip() for bullet in key_bullets])
        return "### 关键要点\n" + bullet_text + "\n"
    
    # 返回摘要
    summary = content.strip()
    if len(summary) > max_chars:
        summary = summary[:max_chars] + "..."
    return summary

def analyze_task_config(config_path):
    """
    分析任务配置，获取子任务结构和状态
    """
    if not os.path.exists(config_path):
        return None
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config
    except Exception as e:
        print("读取任务配置失败: " + str(e))
        return None

def categorize_subtasks(subtasks):
    """
    根据状态分类子任务
    """
    categories = {
        "completed": [],
        "running": [],
        "pending": [],
        "error": []
    }
    
    for subtask in subtasks:
        status = subtask.get("status", "pending")
        if status in categories:
            categories[status].append(subtask)
        else:
            categories["pending"].append(subtask)
    
    return categories

def integrate_results(task_dir):
    """
    智能整合子任务研究发现，生成结构化综合报告
    """
    print("开始整合研究成果: " + task_dir)
    
    master_findings_path = os.path.join(task_dir, "master_findings.md")
    config_path = os.path.join(task_dir, "task_config.json")
    
    config = analyze_task_config(config_path)
    if not config:
        print("警告: 无法读取任务配置，使用简单整合模式")
        return simple_integrate(task_dir)
    
    task_name = config.get("task_name", "未知任务")
    subtasks = config.get("subtasks", [])
    
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 开始构建报告
    content = "# 综合研究报告: " + task_name + "\n\n"
    content += "**整合时间:** " + current_time + "\n"
    content += "**任务状态:** " + config.get('status', '未知') + "\n"
    content += "**总体进度:** " + str(config.get('overall_progress', 0)) + "%\n\n"
    
    content += "## 执行摘要\n\n"
    content += "本次研究整合了" + str(len(subtasks)) + "个子任务的研究发现。"
    
    categorized = categorize_subtasks(subtasks)
    completed_count = len(categorized["completed"])
    running_count = len(categorized["running"])
    
    content += "\n**完成情况:** " + str(completed_count) + "个已完成，" + str(running_count) + "个进行中\n\n"
    
    # 收集所有子任务的发现
    all_findings = []
    subtasks_dir = os.path.join(task_dir, "sub_tasks")
    
    for subtask in subtasks:
        subtask_name = subtask.get("name", "未知子任务")
        subtask_dir_name = subtask.get("directory", subtask_name.replace(" ", "_").replace("/", "_"))
        status = subtask.get("status", "pending")
        progress = subtask.get("progress", 0.0)
        
        subtask_path = os.path.join(subtasks_dir, subtask_dir_name)
        findings_file = os.path.join(subtask_path, "findings.md")
        
        findings_content = ""
        if os.path.exists(findings_file):
            try:
                with open(findings_file, 'r', encoding='utf-8') as f:
                    findings_text = f.read()
                
                key_findings = extract_key_findings(findings_text)
                findings_content = key_findings
                
            except Exception as e:
                findings_content = "*读取研究发现失败: " + str(e) + "*"
        else:
            findings_content = "*未找到研究发现文件*"
        
        all_findings.append({
            "name": subtask_name,
            "status": status,
            "progress": progress,
            "content": findings_content,
            "dependencies": subtask.get("dependencies", [])
        })
    
    # 按状态组织发现
    content += "\n## 子任务研究发现\n\n"
    
    # 先展示已完成的任务
    completed_findings = [f for f in all_findings if f["status"] == "completed"]
    if completed_findings:
        content += "### 已完成任务\n\n"
        for finding in completed_findings:
            content += "#### " + finding['name'] + "\n"
            content += "**状态:** 已完成 | **进度:** " + str(finding['progress']) + "%\n\n"
            content += finding['content'] + "\n\n"
    
    # 然后展示进行中的任务
    running_findings = [f for f in all_findings if f["status"] == "running"]
    if running_findings:
        content += "### 进行中任务\n\n"
        for finding in running_findings:
            content += "#### " + finding['name'] + "\n"
            content += "**状态:** 进行中 | **进度:** " + str(finding['progress']) + "%\n\n"
            content += finding['content'] + "\n\n"
    
    # 最后展示其他任务
    other_findings = [f for f in all_findings if f["status"] not in ["completed", "running"]]
    if other_findings:
        content += "### 其他任务\n\n"
        for finding in other_findings:
            content += "#### " + finding['name'] + "\n"
            content += "**状态:** " + finding['status'] + " | **进度:** " + str(finding['progress']) + "%\n\n"
            content += finding['content'] + "\n\n"
    
    # 添加依赖关系分析
    content += "\n## 任务依赖关系\n\n"
    
    has_dependencies = False
    for finding in all_findings:
        if finding["dependencies"]:
            has_dependencies = True
            content += "- **" + finding['name'] + "** 依赖: " + ", ".join(finding['dependencies']) + "\n"
    
    if not has_dependencies:
        content += "所有子任务均为独立任务，无依赖关系。\n"
    
    # 添加总结
    content += "\n## 综合结论与建议\n\n"
    content += "### 主要发现总结\n"
    content += "1. 本次研究共收集了" + str(len(completed_findings)) + "个已完成任务的研究发现\n"
    content += "2. 尚有" + str(running_count) + "个任务正在进行中\n"
    content += "3. 研究整体进度为" + str(config.get('overall_progress', 0)) + "%\n\n"
    
    content += "### 下一步建议\n"
    content += "1. 继续监控进行中任务的进度\n"
    content += "2. 根据已完成任务的发现调整后续研究方向\n"
    content += "3. 定期更新整合报告以反映最新进展\n\n"
    
    content += "### 质量评估\n"
    content += "- **完整性:** " + str(len(completed_findings)) + "/" + str(len(subtasks)) + " 个任务已完成\n"
    content += "- **及时性:** 报告基于" + current_time + "的最新数据\n"
    content += "- **可追溯性:** 所有发现均关联到具体子任务\n\n"
    
    content += "---\n"
    content += "*报告生成时间: " + current_time + "*\n"
    content += "*使用技能: multi-task-deep-research v1.4.0*\n"
    content += "*整合模式: 智能整合*"
    
    # 写入文件
    with open(master_findings_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("整合完成，综合报告已更新: " + master_findings_path)
    print("整合了 " + str(len(all_findings)) + " 个子任务的发现")
    print("报告长度: " + str(len(content)) + " 字符")

def simple_integrate(task_dir):
    """
    简单整合模式（向后兼容）
    """
    print("使用简单整合模式...")
    
    master_findings_path = os.path.join(task_dir, "master_findings.md")
    
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    content = "# 综合研究报告\n\n**整合时间:** " + current_time + "\n\n"
    
    subtasks_dir = os.path.join(task_dir, "sub_tasks")
    if os.path.exists(subtasks_dir):
        subtasks = os.listdir(subtasks_dir)
        
        for subtask in subtasks:
            subtask_path = os.path.join(subtasks_dir, subtask)
            findings_file = os.path.join(subtask_path, "findings.md")
            
            if os.path.exists(findings_file):
                try:
                    with open(findings_file, 'r', encoding='utf-8') as f:
                        findings = f.read()
                    
                    content += "## " + subtask + "\n\n"
                    content += "*来自子任务: " + subtask + "*\n\n"
                    
                    summary = findings[:500] + "..." if len(findings) > 500 else findings
                    content += summary + "\n\n"
                    
                except Exception as e:
                    content += "## " + subtask + "\n\n*读取失败: " + str(e) + "*\n\n"
    
    with open(master_findings_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("整合完成，主研究发现已更新: " + master_findings_path)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        integrate_results(sys.argv[1])
    else:
        print("用法: python integrate_results.py <任务目录>")
        print("\n示例:")
        print("  python integrate_results.py /app/data/tasks/我的任务")
        print("\n功能:")
        print("  - 智能整合子任务研究发现")
        print("  - 生成结构化综合报告")
        print("  - 按任务状态组织内容")
        print("  - 分析依赖关系和进展")
