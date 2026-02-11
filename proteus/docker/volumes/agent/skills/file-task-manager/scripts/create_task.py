#!/usr/bin/env python3
"""
Create a new file-based task directory with all necessary files.
Usage: python create_task.py --name "Task Name" --description "Task description" --workspace /app/data/tasks
"""

import os
import json
import uuid
import argparse
from datetime import datetime
import shutil

def create_task(task_name, description, workspace_root="/app/data/tasks"):
    """
    Create a new task directory with all required files.
    
    Args:
        task_name: Name of the task
        description: Description of the task
        workspace_root: Root directory where task folders will be created
        
    Returns:
        dict: Task metadata including task_id and path
    """
    # Generate unique task ID
    task_id = str(uuid.uuid4())[:8]
    task_dir = os.path.join(workspace_root, f"task_{task_id}")
    
    # Create task directory
    os.makedirs(task_dir, exist_ok=True)
    
    # Create workspace subdirectory (optional)
    workspace_dir = os.path.join(task_dir, "workspace")
    os.makedirs(workspace_dir, exist_ok=True)
    
    # Current timestamp
    now = datetime.utcnow().isoformat() + "Z"
    
    # Create task.json file
    task_meta = {
        "task_id": task_id,
        "task_name": task_name,
        "description": description,
        "created_at": now,
        "updated_at": now,
        "status": "pending",  # pending, in_progress, completed, cancelled
        "workspace_path": task_dir,
        "owner": os.environ.get("USER", "unknown"),
        "tags": [],
        "metadata": {}
    }
    
    task_json_path = os.path.join(task_dir, "task.json")
    with open(task_json_path, "w") as f:
        json.dump(task_meta, f, indent=2)
    
    # Copy template files
    templates_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
    
    # Copy task_plan.md template
    template_plan = os.path.join(templates_dir, "task_plan.md")
    if os.path.exists(template_plan):
        shutil.copy(template_plan, os.path.join(task_dir, "task_plan.md"))
        # Update task_plan.md with task name
        plan_path = os.path.join(task_dir, "task_plan.md")
        with open(plan_path, "r") as f:
            content = f.read()
        content = content.replace("[Brief Description]", task_name)
        content = content.replace("[One sentence describing the end state]", description)
        with open(plan_path, "w") as f:
            f.write(content)
    
    # Copy findings.md template
    template_findings = os.path.join(templates_dir, "findings.md")
    if os.path.exists(template_findings):
        shutil.copy(template_findings, os.path.join(task_dir, "findings.md"))
    
    # Copy progress.md template
    template_progress = os.path.join(templates_dir, "progress.md")
    if os.path.exists(template_progress):
        shutil.copy(template_progress, os.path.join(task_dir, "progress.md"))
    
    print(f"Created task directory: {task_dir}")
    print(f"Task ID: {task_id}")
    print(f"Task metadata saved to: {task_json_path}")
    
    return task_meta

def main():
    parser = argparse.ArgumentParser(description="Create a new file-based task")
    parser.add_argument("--name", required=True, help="Task name")
    parser.add_argument("--description", required=True, help="Task description")
    parser.add_argument("--workspace", default="/app/data/tasks", 
                       help="Root directory for tasks (default: /app/data/tasks)")
    
    args = parser.parse_args()
    
    # Create the task
    task_meta = create_task(args.name, args.description, args.workspace)
    
    # Print task info in JSON format for easy parsing
    print("\nTask created successfully:")
    print(json.dumps(task_meta, indent=2))

if __name__ == "__main__":
    main()
