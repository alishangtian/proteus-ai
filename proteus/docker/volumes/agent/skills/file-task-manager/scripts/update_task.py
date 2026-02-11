#!/usr/bin/env python3
"""
Update task metadata (status, name, description, etc.)
Usage: python update_task.py --task-id <id> --status in_progress
"""

import os
import json
import argparse
from datetime import datetime

def update_task(task_id, workspace_root="/app/data/tasks", **updates):
    """
    Update task metadata.
    
    Args:
        task_id: Task ID to update
        workspace_root: Root directory where task folders are stored
        **updates: Key-value pairs to update in task metadata
        
    Returns:
        dict: Updated task metadata if successful, None otherwise
    """
    task_dir = os.path.join(workspace_root, f"task_{task_id}")
    task_json_path = os.path.join(task_dir, "task.json")
    
    if not os.path.exists(task_json_path):
        print(f"Task not found: {task_id}")
        return None
    
    try:
        with open(task_json_path, "r") as f:
            task_meta = json.load(f)
        
        # Apply updates
        for key, value in updates.items():
            if value is not None:
                task_meta[key] = value
        
        # Update timestamp
        task_meta["updated_at"] = datetime.utcnow().isoformat() + "Z"
        
        # Save back
        with open(task_json_path, "w") as f:
            json.dump(task_meta, f, indent=2)
        
        print(f"Task {task_id} updated successfully.")
        return task_meta
        
    except json.JSONDecodeError as e:
        print(f"Error reading task metadata: {e}")
        return None
    except Exception as e:
        print(f"Error updating task: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description="Update file-based task metadata")
    parser.add_argument("--task-id", required=True, help="Task ID to update")
    parser.add_argument("--workspace", default="/app/data/tasks", 
                       help="Root directory for tasks (default: /app/data/tasks)")
    
    # Update fields
    parser.add_argument("--status", choices=["pending", "in_progress", "completed", "cancelled"], 
                       help="Update task status")
    parser.add_argument("--name", help="Update task name")
    parser.add_argument("--description", help="Update task description")
    parser.add_argument("--tag", action="append", help="Add a tag to task (can be used multiple times)")
    parser.add_argument("--remove-tag", help="Remove a tag from task")
    
    args = parser.parse_args()
    
    # Prepare updates dict
    updates = {}
    if args.status:
        updates["status"] = args.status
    if args.name:
        updates["task_name"] = args.name
    if args.description:
        updates["description"] = args.description
    
    # Handle tags
    if args.tag:
        updates["tags"] = args.tag
    
    if not updates:
        print("No updates specified. Use --status, --name, --description, or --tag to update.")
        return
    
    # Perform update
    task_meta = update_task(args.task_id, args.workspace, **updates)
    
    if task_meta:
        print("\nUpdated task metadata:")
        print(json.dumps(task_meta, indent=2))

if __name__ == "__main__":
    main()
