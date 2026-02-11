#!/usr/bin/env python3
"""
List all file-based tasks in a workspace directory.
Usage: python list_tasks.py --workspace /app/data/tasks
"""

import os
import json
import argparse
from datetime import datetime

def list_tasks(workspace_root="/app/data/tasks"):
    """
    List all tasks in the workspace directory.
    
    Args:
        workspace_root: Root directory where task folders are stored
        
    Returns:
        list: List of task metadata dictionaries
    """
    tasks = []
    
    if not os.path.exists(workspace_root):
        print(f"Workspace directory does not exist: {workspace_root}")
        return tasks
    
    # Scan for task directories (pattern: task_*)
    for item in os.listdir(workspace_root):
        item_path = os.path.join(workspace_root, item)
        if os.path.isdir(item_path) and item.startswith("task_"):
            task_json_path = os.path.join(item_path, "task.json")
            if os.path.exists(task_json_path):
                try:
                    with open(task_json_path, "r") as f:
                        task_meta = json.load(f)
                    tasks.append(task_meta)
                except json.JSONDecodeError as e:
                    print(f"Error reading {task_json_path}: {e}")
            else:
                # Directory without task.json
                tasks.append({
                    "task_id": item.replace("task_", ""),
                    "task_name": "Unknown",
                    "description": "No task.json found",
                    "status": "unknown",
                    "workspace_path": item_path,
                    "error": "missing_task_json"
                })
    
    # Sort by creation date (most recent first)
    tasks.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    
    return tasks

def main():
    parser = argparse.ArgumentParser(description="List all file-based tasks")
    parser.add_argument("--workspace", default="/app/data/tasks", 
                       help="Root directory for tasks (default: /app/data/tasks)")
    parser.add_argument("--format", choices=["table", "json", "simple"], default="table",
                       help="Output format (default: table)")
    
    args = parser.parse_args()
    
    tasks = list_tasks(args.workspace)
    
    if args.format == "json":
        print(json.dumps(tasks, indent=2))
    elif args.format == "simple":
        for task in tasks:
            task_id = task.get("task_id", "unknown")
            name = task.get("task_name", "Unknown")
            status = task.get("status", "unknown")
            created = task.get("created_at", "")[:10]  # just date
            print(f"{task_id:8} {name:30} {status:12} {created}")
    else:  # table format
        if not tasks:
            print("No tasks found.")
            return
        
        print(f"Found {len(tasks)} tasks in {args.workspace}")
        print("=" * 100)
        print(f"{'ID':8} {'Name':30} {'Status':12} {'Created':20} {'Path':40}")
        print("-" * 100)
        for task in tasks:
            task_id = task.get("task_id", "unknown")
            name = task.get("task_name", "Unknown")[:28]
            status = task.get("status", "unknown")
            created = task.get("created_at", "")[:19]
            path = task.get("workspace_path", "")[:38]
            print(f"{task_id:8} {name:30} {status:12} {created:20} {path:40}")

if __name__ == "__main__":
    main()
