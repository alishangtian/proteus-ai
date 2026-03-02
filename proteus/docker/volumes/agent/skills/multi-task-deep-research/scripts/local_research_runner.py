#!/usr/bin/env python3
"""
简化本地研究执行器 - 用于在没有外部API时手动启动研究任务
"""

import os
import sys
import json
from datetime import datetime

def run_local_research(task_dir, subtask_name):
    """
    手动执行本地研究任务
    
    Args:
        task_dir: 主任务目录
        subtask_name: 要执行的子任务名称
    """
    
    config_path = os.path.join(task_dir, "task_config.json")
    if not os.path.exists(config_path):
        print(f"配置文件未找到: {config_path}")
        return False
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # 查找子任务
        target_subtask = None
        for subtask in config.get('subtasks', []):
            if subtask.get('name') == subtask_name:
                target_subtask = subtask
                break
        
        if not target_subtask:
            print(f"未找到子任务: {subtask_name}")
            print(f"可用子任务: {[s.get('name') for s in config.get('subtasks', [])]}")
            return False
        
        # 获取子任务信息
        subtask_dir_name = target_subtask.get('directory', 
                                            subtask_name.replace(" ", "_").replace("/", "_"))
        workspace_path = os.path.join(task_dir, "sub_tasks", subtask_dir_name)
        research_query = target_subtask.get('query', target_subtask.get('description', ''))
        
        print(f"开始执行本地研究任务")
        print(f"任务名称: {subtask_name}")
        print(f"研究查询: {research_query}")
        print(f"工作目录: {workspace_path}")
        print("=" * 60)
        
        # 更新状态
        target_subtask['status'] = 'running'
        target_subtask['started_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        target_subtask['last_activity'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 保存配置
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        print("\n执行指南:")
        print("1. 进入子任务目录:", workspace_path)
        print("2. 查看任务规划:", os.path.join(workspace_path, "task_plan.md"))
        print("3. 使用可用工具执行研究:")
        print("   - serper_search: 搜索信息")
        print("   - web_crawler: 爬取网页内容")
        print("   - python_execute: 数据分析和处理")
        print("4. 将研究发现写入:", os.path.join(workspace_path, "findings.md"))
        print("5. 更新进度:", os.path.join(workspace_path, "progress.md"))
        print("\n完成后运行监控脚本检查进度:")
        print(f"  python scripts/monitor_tasks.py {task_dir}")
        
        return True
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: python local_research_runner.py <任务目录> <子任务名称>")
        print("\n示例:")
        print('  python local_research_runner.py /app/data/tasks/AI研究 "技术发展趋势"')
        sys.exit(1)
    
    task_dir = sys.argv[1]
    subtask_name = sys.argv[2]
    
    success = run_local_research(task_dir, subtask_name)
    
    if success:
        print("\n✓ 本地研究任务准备完成")
        print("请按照上述指南手动执行研究")
    else:
        print("\n✗ 准备失败")
        sys.exit(1)
