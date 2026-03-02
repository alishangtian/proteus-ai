#!/usr/bin/env python3
"""
Multi-task deep research integration script
"""

import os
import json
from datetime import datetime

def integrate_results(task_dir):
    """
    Integrate results from subtasks into master findings
    """
    
    print(f"Integrating results for task at: {task_dir}")
    
    master_findings_path = os.path.join(task_dir, "master_findings.md")
    
    # Start with header
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    content = f"# 综合研究报告\n\n**整合时间:** {current_time}\n\n"
    
    # Gather findings from subtasks
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
                    
                    # Extract key findings (simplified)
                    content += f"## {subtask}\n\n"
                    content += f"*来自子任务: {subtask}*\n\n"
                    
                    # Take first 500 characters as summary
                    summary = findings[:500] + "..." if len(findings) > 500 else findings
                    content += f"{summary}\n\n"
                    
                except Exception as e:
                    content += f"## {subtask}\n\n*读取失败: {e}*\n\n"
    
    with open(master_findings_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"Integration complete. Master findings updated: {master_findings_path}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        integrate_results(sys.argv[1])
    else:
        print("Usage: python integrate_results.py <task_directory>")
