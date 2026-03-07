#!/usr/bin/env python3
"""
多任务深度研究监控脚本
支持依赖关系状态显示
"""

import os
import json
from datetime import datetime

def monitor_task(task_dir):
    """
    监控多任务研究项目状态
    
    Args:
        task_dir: 任务目录路径
    """
    
    config_path = os.path.join(task_dir, "task_config.json")
    if not os.path.exists(config_path):
        print(f"配置文件未找到: {config_path}")
        return
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        task_name = config.get('task_name', '未知任务')
        created_at = config.get('created_at', '未知时间')
        overall_progress = config.get('overall_progress', 0.0)
        
        print(f"监控任务: {task_name}")
        print(f"创建时间: {created_at}")
        print(f"总体进度: {overall_progress:.1f}%")
        print("=" * 60)
        
        # 检查子任务
        subtasks_dir = os.path.join(task_dir, "sub_tasks")
        subtasks = config.get('subtasks', [])
        
        if not subtasks:
            print("没有子任务")
            return
        
        print(f"子任务数量: {len(subtasks)}")
        print("")
        
        # 按状态分组
        status_groups = {}
        for subtask in subtasks:
            status = subtask.get('status', 'unknown')
            if status not in status_groups:
                status_groups[status] = []
            status_groups[status].append(subtask)
        
        # 显示状态统计
        print("状态统计:")
        for status in sorted(status_groups.keys()):
            count = len(status_groups[status])
            print(f"  {status}: {count} 个任务")
        
        print("")
        print("子任务详情:")
        print("-" * 60)
        
        for i, subtask in enumerate(subtasks, 1):
            name = subtask.get('name', f'子任务{i}')
            status = subtask.get('status', 'unknown')
            progress = subtask.get('progress', 0.0)
            dependencies = subtask.get('dependencies', [])
            created = subtask.get('created_at', '未知')
            started = subtask.get('started_at', '未开始')
            completed = subtask.get('completed_at', '未完成')
            
            # 状态图标
            status_icon = {                'pending': '⏳',                'running': '🔄',                'completed': '✅',                'error': '❌',                'waiting': '[等待]'            }.get(status, '❓')            
            print(f"{i}. {status_icon} {name}")
            print(f"   状态: {status} | 进度: {progress:.1f}%")
            
            if dependencies:
                print(f"   依赖: {', '.join(dependencies)}")

            if status == "waiting":
                waiting_for = subtask.get("waiting_for", "未知")
                waiting_since = subtask.get("waiting_since", "未知")
                print(f"   等待: {waiting_for} (自{waiting_since})")
            
            if started != '未开始':
                print(f"   开始时间: {started}")
            
            if completed != '未完成':
                print(f"   完成时间: {completed}")
            
            # 检查实际文件状态
            subtask_dir_name = subtask.get('directory', name.replace(" ", "_").replace("/", "_"))
            subtask_path = os.path.join(subtasks_dir, subtask_dir_name)
            
            if os.path.exists(subtask_path):
                progress_file = os.path.join(subtask_path, "progress.md")
                findings_file = os.path.join(subtask_path, "findings.md")
                
                if os.path.exists(progress_file):
                    try:
                        with open(progress_file, 'r', encoding='utf-8') as f:
                            progress_content = f.read()
                        
                        # 提取进度信息
                        import re
                        progress_match = re.search(r'进度:\s*(\d+)%', progress_content)
                        if progress_match:
                            file_progress = int(progress_match.group(1))
                            if file_progress != progress:
                                print(f"   注意: 文件进度({file_progress}%)与配置进度({progress}%)不一致")
                    except:
                        pass
                
                if os.path.exists(findings_file):
                    try:
                        with open(findings_file, 'r', encoding='utf-8') as f:
                            findings_content = f.read()
                        
                        if "[等待研究完成]" not in findings_content and len(findings_content.strip()) > 300:
                            print(f"   研究发现: 已生成 ({len(findings_content)} 字符)")
                        else:
                            print(f"   研究发现: 等待中")
                    except:
                        pass
            
            print("")
        
        # 检查依赖关系
        print("依赖关系检查:")
        print("-" * 60)
        
        valid = True
        name_to_task = {task['name']: task for task in subtasks}
        
        for subtask in subtasks:
            name = subtask.get('name', '')
            dependencies = subtask.get('dependencies', [])
            
            for dep_name in dependencies:
                if dep_name not in name_to_task:
                    print(f"  ❌ {name} -> {dep_name}: 依赖不存在")
                    valid = False
                else:
                    dep_task = name_to_task[dep_name]
                    dep_status = dep_task.get('status', 'unknown')
                    
                    if subtask.get('status') == 'running' and dep_status != 'completed':
                        print(f"  ⚠  {name} -> {dep_name}: 任务运行中但依赖未完成({dep_status})")
                    elif subtask.get('status') == 'completed' and dep_status != 'completed':
                        print(f"  ⚠  {name} -> {dep_name}: 任务已完成但依赖未完成({dep_status})")
                    else:
                        print(f"  ✓  {name} -> {dep_name}: 正常({dep_status})")
        
        if not valid:
            print("\n⚠ 存在无效依赖关系")
        
        # 更新监控时间
        config['last_monitored'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        print("\n监控完成")
        
    except Exception as e:
        print(f"错误: {e}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        monitor_task(sys.argv[1])
    else:
        print("用法: python monitor_tasks.py <任务目录>")
        print("\n示例:")
        print("  python monitor_tasks.py /app/data/tasks/我的任务")
