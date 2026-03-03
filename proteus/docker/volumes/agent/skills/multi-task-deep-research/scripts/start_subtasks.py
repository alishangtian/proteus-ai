#!/usr/bin/env python3
"""
多任务深度研究子任务启动脚本
支持依赖关系的顺序启动，一次只启动一个任务
"""

import os
import json
import time
import sys
from datetime import datetime

# Try to import requests, install if not available
try:
    import requests
except ImportError:
    print("requests模块未找到，尝试安装...")
    try:
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
        import requests
        print("requests安装成功")
    except Exception as e:
        print(f"安装requests失败: {e}")
        print("请手动安装: pip install requests")
        sys.exit(1)

def topological_sort(subtasks):
    """
    对子任务进行拓扑排序，考虑依赖关系
    
    Args:
        subtasks: List of subtask dictionaries with 'name' and 'dependencies' fields
    
    Returns:
        List of subtasks in topological order
    """
    # Build adjacency list and indegree map
    name_to_task = {task["name"]: task for task in subtasks}
    adjacency = {task["name"]: [] for task in subtasks}
    indegree = {task["name"]: 0 for task in subtasks}
    
    for task in subtasks:
        for dep_name in task.get("dependencies", []):
            if dep_name in name_to_task:
                adjacency[dep_name].append(task["name"])
                indegree[task["name"]] = indegree.get(task["name"], 0) + 1
    
    # Kahn's algorithm for topological sort
    result = []
    queue = [task_name for task_name in indegree if indegree[task_name] == 0]
    
    while queue:
        current = queue.pop(0)
        result.append(name_to_task[current])
        
        for neighbor in adjacency[current]:
            indegree[neighbor] -= 1
            if indegree[neighbor] == 0:
                queue.append(neighbor)
    
    # Check for cycles
    if len(result) != len(subtasks):
        print("⚠ 警告: 检测到循环依赖，部分任务无法排序")
        # Add remaining tasks (with cycles) at the end
        remaining = [task for task in subtasks if task not in result]
        result.extend(remaining)
    
    return result

def check_task_status(workspace_path):
    """
    检查任务状态，判断是否完成
    
    Args:
        workspace_path: 任务工作目录
    
    Returns:
        bool: True if task is completed, False otherwise
    """
    try:
        progress_file = os.path.join(workspace_path, "progress.md")
        if os.path.exists(progress_file):
            with open(progress_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Simple check for completion status
            if "状态: 完成" in content or "状态: completed" in content or "进度: 100%" in content:
                return True
        
        findings_file = os.path.join(workspace_path, "findings.md")
        if os.path.exists(findings_file):
            with open(findings_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check if findings are populated (not just template)
            if "[等待研究完成]" not in content and len(content.strip()) > 200:
                return True
        
        return False
    except:
        return False

def start_subtask(task_dir, subtask, api_config, max_retries=2, retry_delay=5):
    """
    启动单个子任务，支持重试机制
    
    Args:
        task_dir: 主任务目录
        subtask: 子任务配置字典
        api_config: API配置
        max_retries: 最大重试次数
        retry_delay: 重试延迟秒数
    
    Returns:
        bool: True if successful, False otherwise
    """
    subtask_name = subtask.get("name")
    subtask_query = subtask.get("query", subtask.get("description", ""))
    subtask_dir_name = subtask.get("directory", subtask_name.replace(" ", "_").replace("/", "_"))
    
    # Build workspace path
    workspace_path = os.path.join(task_dir, "sub_tasks", subtask_dir_name)
    
    print(f"启动子任务: {subtask_name}")
    print(f"  查询: {subtask_query[:100]}...")
    print(f"  工作目录: {workspace_path}")
    
    if subtask.get("dependencies"):
        print(f"  依赖: {', '.join(subtask['dependencies'])}")
    
    # Prepare API payload - 完全匹配用户提供的curl示例
    payload = {
        "query": subtask_query,
        "workspace_path": workspace_path,
        "modul": "task",
        "model_name": api_config.get("model_name", "deepseek-reasoner"),
        "itecount": api_config.get("itecount", 200),
        "team_name": "",
        "conversation_id": "",
        "conversation_round": api_config.get("conversation_round", 5),
        "tool_memory_enabled": False,
        "enable_tools": True,
        "tool_choices": api_config.get("tool_choices", ["serper_search", "web_crawler", "python_execute"]),
        "selected_skills": api_config.get("selected_skills", ["planning-with-file"]),
        "stream": True
    }
    
    # Prepare headers
    endpoint = api_config.get("endpoint", "https://127.0.0.1/task")
    auth_token = api_config.get("auth_token", "421f1d95-1bb4-439b-b66e-941c46cc2831")
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    }
    
    # 重试逻辑
    for attempt in range(max_retries + 1):
        try:
            if attempt > 0:
                print(f"  第{attempt}次重试...")
                import time
                time.sleep(retry_delay * attempt)  # 递增延迟
            
            # Send request (disable SSL verification for local testing)
            response = requests.post(
                endpoint,
                json=payload,
                headers=headers,
                verify=False,
                timeout=30
            )
            
            if response.status_code == 200:
                print(f"  ✓ 子任务启动成功")
                
                # Update subtask status
                subtask["status"] = "running"
                subtask["started_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                subtask["last_activity"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                subtask["api_calls"] = subtask.get("api_calls", 0) + 1
                
                return True
            else:
                print(f"  ✗ 子任务启动失败. 状态码: {response.status_code}")
                if response.text:
                    print(f"    响应: {response.text[:200]}")
                
                # 如果不是最后一次尝试，继续重试
                if attempt < max_retries:
                    continue
                else:
                    # Mark as error
                    subtask["status"] = "error"
                    subtask["error_count"] = subtask.get("error_count", 0) + 1
                    return False
            
        except requests.exceptions.Timeout:
            print(f"  ⏱ 请求超时")
            if attempt < max_retries:
                print(f"    等待{retry_delay * (attempt + 1)}秒后重试...")
                continue
            else:
                print(f"  ✗ 达到最大重试次数，放弃")
                subtask["status"] = "error"
                subtask["error_count"] = subtask.get("error_count", 0) + 1
                return False
                
        except requests.exceptions.ConnectionError as e:
            print(f"  🔌 连接错误: {e}")
            if attempt < max_retries:
                print(f"    等待{retry_delay * (attempt + 1)}秒后重试...")
                continue
            else:
                print(f"  ✗ 达到最大重试次数，放弃")
                subtask["status"] = "error"
                subtask["error_count"] = subtask.get("error_count", 0) + 1
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"  ✗ 请求异常: {e}")
            if attempt < max_retries:
                continue
            else:
                subtask["status"] = "error"
                subtask["error_count"] = subtask.get("error_count", 0) + 1
                return False
    
    # 理论上不会执行到这里
    return False

def start_subtasks_sequential(task_dir, wait_for_completion=False, check_interval=30, max_checks=120):
    """
    按依赖顺序顺序启动子任务，一次只启动一个
    
    Args:
        task_dir: 主任务目录
        wait_for_completion: 是否等待每个任务完成后再启动下一个
        check_interval: 检查任务完成状态的间隔秒数
        max_checks: 最大检查次数
    
    Returns:
        bool: True if all tasks started successfully, False otherwise
    """
    
    config_path = os.path.join(task_dir, "task_config.json")
    if not os.path.exists(config_path):
        print(f"错误: 任务配置文件未找到 {config_path}")
        return False
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        task_name = config.get("task_name", "未知任务")
        print(f"按依赖顺序启动子任务: {task_name}")
        
        # Get API configuration
        api_config = config.get("api_config", {})
        if not api_config:
            print("警告: 任务配置中没有API配置")
            api_config = {
                "endpoint": "https://127.0.0.1/task",
                "auth_token": "421f1d95-1bb4-439b-b66e-941c46cc2831",
                "model_name": "deepseek-reasoner",
                "itecount": 200,
                "conversation_round": 5,
                "tool_choices": ["serper_search", "web_crawler", "python_execute"],
            "selected_skills": ["planning-with-file"],
            }
        
        # Get subtasks
        subtasks = config.get("subtasks", [])
        if not subtasks:
            print("没有需要启动的子任务")
            return True
        
        # Filter only pending tasks
        pending_tasks = [t for t in subtasks if t.get("status") == "pending"]
        if not pending_tasks:
            print("没有待处理的子任务")
            return True
        
        print(f"找到 {len(pending_tasks)} 个待处理子任务")
        
        # Sort tasks by dependencies
        sorted_tasks = topological_sort(pending_tasks)
        
        print("\n依赖执行顺序:")
        for i, task in enumerate(sorted_tasks, 1):
            deps = task.get("dependencies", [])
            deps_str = f" (依赖: {', '.join(deps)})" if deps else ""
            print(f"  {i}. {task['name']}{deps_str}")
        
        # Start tasks one by one
        success_count = 0
        total_tasks = len(sorted_tasks)
        
        for i, task in enumerate(sorted_tasks, 1):
            print(f"\n[{i}/{total_tasks}] 处理子任务...")
            
            # Check if dependencies are completed (if we're checking)
            if wait_for_completion:
                deps = task.get("dependencies", [])
                if deps:
                    # Check if all dependencies are completed
                    all_deps_completed = True
                    for dep_name in deps:
                        # Find the dependency task
                        dep_task = next((t for t in subtasks if t["name"] == dep_name), None)
                        if dep_task:
                            workspace_path = os.path.join(task_dir, "sub_tasks", dep_task.get("directory", dep_name.replace(" ", "_").replace("/", "_")))
                            if not check_task_status(workspace_path):
                                all_deps_completed = False
                                print(f"  等待依赖任务完成: {dep_name}")
                                break
                                # 设置任务为等待状态                                task["status"] = "waiting"                                task["waiting_for"] = dep_name                                task["waiting_since"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")                    
                # 依赖检查通过，恢复pending状态                if task.get("status") == "waiting":                    task["status"] = "pending"                    task.pop("waiting_for", None)                    task.pop("waiting_since", None)                    if not all_deps_completed:
                        # Wait for dependencies to complete
                        print(f"  等待依赖任务完成...")
                        checks = 0
                        while checks < max_checks and not all_deps_completed:
                            time.sleep(check_interval)
                            checks += 1
                            
                            # Re-check
                            all_deps_completed = True
                            for dep_name in deps:
                                dep_task = next((t for t in subtasks if t["name"] == dep_name), None)
                                if dep_task:
                                    workspace_path = os.path.join(task_dir, "sub_tasks", dep_task.get("directory", dep_name.replace(" ", "_").replace("/", "_")))
                                    if not check_task_status(workspace_path):
                                        all_deps_completed = False
                                        break
                            
                            if not all_deps_completed and checks % 10 == 0:
                                print(f"  仍在等待依赖任务完成... ({checks * check_interval} 秒)")
                        
                        if not all_deps_completed:
                            print(f"  ⚠ 超时: 依赖任务未在预期时间内完成")
                            # We'll still try to start the task
            else:
                # Just log dependencies but don't wait
                deps = task.get("dependencies", [])
                if deps:
                    print(f"  注意: 任务有依赖 {', '.join(deps)}，但未启用等待完成模式")
            
            # Start the task
            success = start_subtask(task_dir, task, api_config, max_retries=2, retry_delay=5)            
            if success:
                success_count += 1
                
                if wait_for_completion and i < total_tasks:
                    # Wait for this task to complete before starting next
                    print(f"  等待任务完成...")
                    checks = 0
                    workspace_path = os.path.join(task_dir, "sub_tasks", task.get("directory", task["name"].replace(" ", "_").replace("/", "_")))
                    
                    while checks < max_checks and not check_task_status(workspace_path):
                        time.sleep(check_interval)
                        checks += 1
                        
                        if checks % 10 == 0:
                            print(f"  仍在等待任务完成... ({checks * check_interval} 秒)")
                    
                    if check_task_status(workspace_path):
                        print(f"  ✓ 任务完成")
                        task["status"] = "completed"
                        task["completed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    else:
                        print(f"  ⚠ 超时: 任务未在预期时间内完成")
            
            # Save updated config after each task
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            # Small delay between API calls
            if i < total_tasks:
                time.sleep(2)
        
        # Final status
        print(f"\n启动完成: {success_count}/{total_tasks} 个子任务成功启动")
        
        # Calculate overall progress
        completed_tasks = len([t for t in subtasks if t.get("status") == "completed"])
        running_tasks = len([t for t in subtasks if t.get("status") == "running"])
        total = len(subtasks)
        
        if total > 0:
            config["overall_progress"] = (completed_tasks + running_tasks * 0.5) / total * 100
            config["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        
        return success_count == total_tasks
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        return False

def start_subtasks_with_dependencies(task_dir, specific_tasks=None):
    """
    启动子任务（兼容旧接口）
    
    Args:
        task_dir: 主任务目录
        specific_tasks: 特定任务列表（如果为None则启动所有）
    
    Returns:
        bool: True if successful, False otherwise
    """
    print("注意: 此功能已更新为顺序启动模式")
    print("子任务将按依赖关系顺序启动，一次只启动一个")
    
    # For backward compatibility, we'll use sequential mode without waiting
    return start_subtasks_sequential(task_dir, wait_for_completion=False)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        task_dir = sys.argv[1]
        
        # Check for mode flags
        if len(sys.argv) > 2:
            if sys.argv[2] == "--wait":
                # Sequential mode with waiting
                wait_for_completion = True
                print("使用顺序等待模式: 每个任务完成后才启动下一个")
                success = start_subtasks_sequential(task_dir, wait_for_completion=True)
            elif sys.argv[2] == "--sequential":
                # Sequential mode without waiting
                wait_for_completion = False
                print("使用顺序启动模式: 按依赖顺序启动，但不等待完成")
                success = start_subtasks_sequential(task_dir, wait_for_completion=False)
            elif sys.argv[2] == "--specific":
                # Specific tasks (legacy mode)
                specific_tasks = sys.argv[3:]
                print(f"启动特定任务: {', '.join(specific_tasks)}")
                print("注意: 依赖关系可能不被完全遵守")
                success = start_subtasks_with_dependencies(task_dir, specific_tasks)
            else:
                print(f"未知参数: {sys.argv[2]}")
                print("使用默认顺序启动模式")
                success = start_subtasks_sequential(task_dir, wait_for_completion=False)
        else:
            # Default: sequential mode without waiting
            print("使用默认顺序启动模式: 按依赖顺序启动，但不等待完成")
            success = start_subtasks_sequential(task_dir, wait_for_completion=False)
        
        if success:
            print("\n✓ 所有子任务启动流程完成")
        else:
            print("\n⚠ 部分子任务启动失败")
            sys.exit(1)
    else:
        print("用法: python start_subtasks.py <任务目录> [模式]")
        print("\n模式:")
        print("  --wait          顺序等待模式: 每个任务完成后才启动下一个")
        print("  --sequential    顺序启动模式: 按依赖顺序启动，但不等待完成 (默认)")
        print("  --specific      特定任务模式: 启动指定的任务 (传统模式)")
        print("\n示例:")
        print("  python start_subtasks.py /app/data/tasks/我的任务")
        print("  python start_subtasks.py /app/data/tasks/我的任务 --wait")
        print("  python start_subtasks.py /app/data/tasks/我的任务 --sequential")
        print("  python start_subtasks.py /app/data/tasks/我的任务 --specific \"任务A\" \"任务B\"")
