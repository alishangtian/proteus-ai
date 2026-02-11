#!/usr/bin/env python3
"""
Restore a task by task ID. This script reads task metadata and provides instructions
for restoring the task via the /task interface.
Usage: python restore_task.py --task-id <id> --workspace /app/data/tasks
"""

import os
import json
import argparse
import sys
import urllib.parse

def restore_task(task_id, workspace_root="/app/data/tasks"):
    """
    Restore a task by its ID.
    
    Args:
        task_id: Task ID to restore
        workspace_root: Root directory where task folders are stored
        
    Returns:
        dict: Task metadata if found, None otherwise
    """
    task_dir = os.path.join(workspace_root, f"task_{task_id}")
    task_json_path = os.path.join(task_dir, "task.json")
    
    if not os.path.exists(task_json_path):
        print(f"Task not found: {task_id}")
        print(f"Expected path: {task_json_path}")
        return None
    
    try:
        with open(task_json_path, "r") as f:
            task_meta = json.load(f)
        
        # Update last accessed time? maybe not
        print(f"Task found: {task_meta.get('task_name')}")
        print(f"Status: {task_meta.get('status')}")
        print(f"Workspace: {task_dir}")
        
        return task_meta
    except json.JSONDecodeError as e:
        print(f"Error reading task metadata: {e}")
        return None

def generate_restore_command(task_meta, interface_type="http"):
    """
    Generate a restore command for the task based on interface type.
    
    Args:
        task_meta: Task metadata dictionary
        interface_type: Type of interface - "http", "cli", "curl"
        
    Returns:
        str: Command or URL to restore the task
    """
    task_id = task_meta.get("task_id")
    workspace_path = task_meta.get("workspace_path")
    
    if interface_type == "http":
        # Assuming HTTP POST to /task endpoint
        params = {
            "taskid": task_id,
            "workspace": workspace_path,
            "action": "restore"
        }
        query_string = urllib.parse.urlencode(params)
        return f"POST /task?{query_string}"
    elif interface_type == "curl":
        quoted_workspace = urllib.parse.quote(workspace_path)
        return f"curl -X POST 'http://localhost:8080/task?taskid={task_id}&workspace={quoted_workspace}'"
    elif interface_type == "cli":
        return f'task-cli restore --task-id {task_id} --workspace "{workspace_path}"'
    else:
        return f"Restore task {task_id} from workspace {workspace_path}"

def main():
    parser = argparse.ArgumentParser(description="Restore a file-based task by ID")
    parser.add_argument("--task-id", required=True, help="Task ID to restore")
    parser.add_argument("--workspace", default="/app/data/tasks", 
                       help="Root directory for tasks (default: /app/data/tasks)")
    parser.add_argument("--interface", choices=["http", "cli", "curl", "info"], default="info",
                       help="Interface type for restore command (default: info)")
    
    args = parser.parse_args()
    
    task_meta = restore_task(args.task_id, args.workspace)
    
    if task_meta is None:
        sys.exit(1)
    
    if args.interface != "info":
        command = generate_restore_command(task_meta, args.interface)
        print(f"\nRestore command ({args.interface}):")
        print(command)
    
    # Print task files
    task_dir = os.path.join(args.workspace, f"task_{args.task_id}")
    print(f"\nTask files in {task_dir}:")
    if os.path.exists(task_dir):
        for root, dirs, files in os.walk(task_dir):
            level = root.replace(task_dir, '').count(os.sep)
            indent = ' ' * 2 * level
            print(f"{indent}{os.path.basename(root)}/")
            subindent = ' ' * 2 * (level + 1)
            for file in files:
                print(f"{subindent}{file}")
            # Don't walk into workspace subdirectory deeply
            if os.path.basename(root) == "workspace":
                dirs[:] = []  # don't recurse further
    else:
        print("Task directory not found.")
    
    # Print current task plan status
    task_plan_path = os.path.join(task_dir, "task_plan.md")
    if os.path.exists(task_plan_path):
        print(f"\nTask plan exists: {task_plan_path}")
        # Optionally read and show current phase
        try:
            with open(task_plan_path, "r") as f:
                content = f.read()
                # Extract current phase (simple grep)
                import re
                phase_match = re.search(r"## Current Phase\s*\n([^\n]+)", content)
                if phase_match:
                    print(f"Current phase: {phase_match.group(1).strip()}")
        except Exception as e:
            print(f"Cannot read task plan: {e}")

if __name__ == "__main__":
    main()
