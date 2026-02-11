#!/usr/bin/env python3
"""
Delete a task directory (with confirmation).
Usage: python delete_task.py --task-id <id> --workspace /app/data/tasks
"""

import os
import json
import argparse
import shutil
from datetime import datetime

def delete_task(task_id, workspace_root="/app/data/tasks", force=False):
    """
    Delete a task directory.
    
    Args:
        task_id: Task ID to delete
        workspace_root: Root directory where task folders are stored
        force: If True, skip confirmation
        
    Returns:
        bool: True if deleted, False otherwise
    """
    task_dir = os.path.join(workspace_root, f"task_{task_id}")
    
    if not os.path.exists(task_dir):
        print(f"Task directory not found: {task_dir}")
        return False
    
    # Read task metadata first
    task_json_path = os.path.join(task_dir, "task.json")
    task_name = "Unknown"
    if os.path.exists(task_json_path):
        try:
            with open(task_json_path, "r") as f:
                task_meta = json.load(f)
                task_name = task_meta.get("task_name", "Unknown")
        except:
            pass
    
    if not force:
        confirm = input(f"Are you sure you want to delete task '{task_name}' (ID: {task_id})? [y/N]: ")
        if confirm.lower() != 'y':
            print("Deletion cancelled.")
            return False
    
    try:
        shutil.rmtree(task_dir)
        print(f"Task '{task_name}' (ID: {task_id}) deleted successfully.")
        return True
    except Exception as e:
        print(f"Error deleting task directory: {e}")
        return False

def archive_task(task_id, workspace_root="/app/data/tasks", archive_root=None):
    """
    Archive a task by moving it to an archive directory.
    
    Args:
        task_id: Task ID to archive
        workspace_root: Root directory where task folders are stored
        archive_root: Archive directory (default: workspace_root/_archive)
        
    Returns:
        bool: True if archived, False otherwise
    """
    if archive_root is None:
        archive_root = os.path.join(workspace_root, "_archive")
    
    task_dir = os.path.join(workspace_root, f"task_{task_id}")
    
    if not os.path.exists(task_dir):
        print(f"Task directory not found: {task_dir}")
        return False
    
    os.makedirs(archive_root, exist_ok=True)
    
    try:
        # Update task status to archived if task.json exists
        task_json_path = os.path.join(task_dir, "task.json")
        if os.path.exists(task_json_path):
            with open(task_json_path, "r") as f:
                task_meta = json.load(f)
            task_meta["status"] = "archived"
            task_meta["archived_at"] = datetime.utcnow().isoformat() + "Z"
            with open(task_json_path, "w") as f:
                json.dump(task_meta, f, indent=2)
        
        # Move directory
        dest_dir = os.path.join(archive_root, f"task_{task_id}")
        shutil.move(task_dir, dest_dir)
        print(f"Task {task_id} archived to {dest_dir}")
        return True
    except Exception as e:
        print(f"Error archiving task: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Delete or archive a file-based task")
    parser.add_argument("--task-id", required=True, help="Task ID to delete/archive")
    parser.add_argument("--workspace", default="/app/data/tasks", 
                       help="Root directory for tasks (default: /app/data/tasks)")
    parser.add_argument("--force", action="store_true", 
                       help="Force deletion without confirmation")
    parser.add_argument("--archive", action="store_true",
                       help="Archive instead of delete")
    parser.add_argument("--archive-dir", 
                       help="Archive directory (default: workspace/_archive)")
    
    args = parser.parse_args()
    
    if args.archive:
        success = archive_task(args.task_id, args.workspace, args.archive_dir)
    else:
        success = delete_task(args.task_id, args.workspace, args.force)
    
    exit(0 if success else 1)

if __name__ == "__main__":
    main()
