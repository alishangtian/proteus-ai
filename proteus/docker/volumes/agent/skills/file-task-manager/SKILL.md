---
name: file-task-manager
description: File-based task management system that organizes tasks in separate directories with persistent planning files. Each task directory contains task metadata (task.json), planning files (task_plan.md, findings.md, progress.md) based on planning-with-files methodology, and enables task recovery via /task interface. Use when users need to manage multiple tasks with persistent state, require task recovery capabilities, or need file-based organization for long-running projects. Particularly useful for complex multi-step tasks, research projects, or any work requiring organization across sessions.
---

# File-Based Task Manager

A comprehensive file-based task management system that organizes tasks in separate directories with persistent planning files. Each task directory contains all necessary files for task tracking, planning, and recovery.

## Core Concepts

- **Task Directory**: Each task gets its own directory (e.g., `task_abc123/`) containing all task files
- **Task Metadata**: `task.json` file stores task ID, name, status, timestamps, and workspace path
- **Planning Files**: Based on `planning-with-files` methodology:
  - `task_plan.md` - Task roadmap with phases and progress tracking
  - `findings.md` - Research discoveries and decisions
  - `progress.md` - Session logs and error tracking
- **Task Recovery**: Each task can be restored via the `/task` interface using task ID and workspace path

## When to Use This Skill

Use this skill when:

1. **Managing multiple tasks** - Each task is isolated in its own directory
2. **Requiring persistent task state** - Task metadata and planning files survive across sessions
3. **Needing task recovery** - Restore tasks via task ID using the `/task` interface
4. **Working on complex multi-step projects** - Leverage the planning-with-files methodology
5. **Organizing long-running work** - Keep all task-related files in one place

## Quick Start

### 1. Create a New Task

```bash
# Create a new task with name and description
python /app/.proteus/skills/file-task-manager/scripts/create_task.py   --name "My Project"   --description "Build a web application for task management"
```

This creates:
- Task directory: `/app/data/tasks/task_<id>/`
- Task metadata: `task.json`
- Planning files: `task_plan.md`, `findings.md`, `progress.md`
- Workspace subdirectory: `workspace/`

### 2. List All Tasks

```bash
# List all tasks in table format
python /app/.proteus/skills/file-task-manager/scripts/list_tasks.py

# JSON format for programmatic use
python /app/.proteus/skills/file-task-manager/scripts/list_tasks.py --format json
```

### 3. Restore a Task

```bash
# Restore a task by ID (shows task info and restore commands)
python /app/.proteus/skills/file-task-manager/scripts/restore_task.py --task-id <task_id>

# Generate HTTP restore command
python /app/.proteus/skills/file-task-manager/scripts/restore_task.py --task-id <task_id> --interface http

# Generate curl command
python /app/.proteus/skills/file-task-manager/scripts/restore_task.py --task-id <task_id> --interface curl
```

### 4. Update Task Status

```bash
# Update task status
python /app/.proteus/skills/file-task-manager/scripts/update_task.py --task-id <task_id> --status in_progress

# Update task name and description
python /app/.proteus/skills/file-task-manager/scripts/update_task.py --task-id <task_id> --name "New Name" --description "Updated description"
```

### 5. Delete or Archive Tasks

```bash
# Delete a task (with confirmation)
python /app/.proteus/skills/file-task-manager/scripts/delete_task.py --task-id <task_id>

# Force delete without confirmation
python /app/.proteus/skills/file-task-manager/scripts/delete_task.py --task-id <task_id> --force

# Archive a task instead of deleting
python /app/.proteus/skills/file-task-manager/scripts/delete_task.py --task-id <task_id> --archive
```

## Task Directory Structure

```
task_abc123/
├── task.json                 # Task metadata (ID, name, status, timestamps)
├── task_plan.md             # Task roadmap with phases
├── findings.md              # Research discoveries and decisions
├── progress.md              # Session logs and error tracking
└── workspace/               # Working directory for task files
    └── (project files)
```

## Task Metadata (task.json)

The `task.json` file contains:

```json
{
  "task_id": "abc123",
  "task_name": "My Project",
  "description": "Build a web application",
  "created_at": "2026-02-10T16:32:50Z",
  "updated_at": "2026-02-10T16:32:50Z",
  "status": "pending",
  "workspace_path": "/app/data/tasks/task_abc123",
  "owner": "user",
  "tags": [],
  "metadata": {}
}
```

## Task Recovery via /task Interface

Each task directory includes a `task.json` file that enables task recovery through the `/task` interface. The interface expects parameters:

- `taskid`: Task ID from `task.json`
- `workspace`: Workspace path from `task.json`
- Additional parameters as required by your implementation

### Example REST API Call

```bash
# Using curl to restore a task
curl -X POST "http://localhost:8080/task?taskid=abc123&workspace=/app/data/tasks/task_abc123"
```

The `restore_task.py` script can generate appropriate commands for your interface type.

## Planning Files Methodology

This skill extends the `planning-with-files` methodology:

1. **task_plan.md** - Break work into phases, track progress, log errors
2. **findings.md** - Capture research discoveries (follow the 2-Action Rule)
3. **progress.md** - Maintain session logs and test results

### The 2-Action Rule
After every 2 view/browser/search operations, immediately update `findings.md` to prevent loss of visual/multimodal information.

## Scripts Reference

All scripts are located in `/app/.proteus/skills/file-task-manager/scripts/`:

### `create_task.py`
Creates a new task directory with all necessary files.

**Usage:**
```bash
python create_task.py --name "Task Name" --description "Task description" [--workspace /app/data/tasks]
```

### `list_tasks.py`
Lists all tasks in the workspace directory.

**Usage:**
```bash
python list_tasks.py [--workspace /app/data/tasks] [--format table|json|simple]
```

### `restore_task.py`
Restores a task by ID and generates restore commands.

**Usage:**
```bash
python restore_task.py --task-id <id> [--workspace /app/data/tasks] [--interface http|cli|curl|info]
```

### `update_task.py`
Updates task metadata (status, name, description, tags).

**Usage:**
```bash
python update_task.py --task-id <id> [--status pending|in_progress|completed|cancelled] [--name "New Name"] [--description "New description"]
```

### `delete_task.py`
Deletes or archives a task directory.

**Usage:**
```bash
python delete_task.py --task-id <id> [--force] [--archive] [--archive-dir /path]
```

## Templates

Template files are located in `/app/.proteus/skills/file-task-manager/templates/`:

- `task.json` - Task metadata template
- `task_plan.md` - Task planning template
- `findings.md` - Research findings template
- `progress.md` - Progress logging template

## Configuration

### Workspace Location
By default, tasks are stored in `/app/data/tasks`. You can change this by:

1. Setting the `--workspace` parameter on all scripts
2. Creating a symlink: `ln -s /custom/path /app/data/tasks`
3. Modifying the default in each script

### Task ID Generation
Task IDs are generated as 8-character UUID segments (e.g., `abc123`). You can modify the ID generation in `create_task.py` if needed.

## Integration with Other Skills

### Planning-with-Files
This skill is built on top of `planning-with-files` methodology. You can use all planning-with-files techniques within each task directory.

### Memory System
For long-term memory across tasks, consider using the `memory-system` skill to store task patterns and learnings.

## Best Practices

1. **One task per directory** - Keep tasks isolated for clean organization
2. **Regular updates** - Update task status and planning files as work progresses
3. **Use workspace subdirectory** - Store task-specific files in the `workspace/` subdirectory
4. **Backup task directories** - Consider version control or backups for important tasks
5. **Clean up completed tasks** - Archive or delete tasks that are no longer needed

## Examples

### Example 1: Creating and Managing a Research Task

```bash
# Create research task
python create_task.py --name "Market Research" --description "Research competitors in task management space"

# List tasks to get ID
python list_tasks.py --format simple

# Update status to in_progress
python update_task.py --task-id abc123 --status in_progress

# Work on task files...
# Edit /app/data/tasks/task_abc123/task_plan.md
# Edit /app/data/tasks/task_abc123/findings.md

# When done, update status
python update_task.py --task-id abc123 --status completed
```

### Example 2: Restoring a Task After System Restart

```bash
# List tasks to find ID
python list_tasks.py

# Restore task
python restore_task.py --task-id def456 --interface http

# Output shows restore command:
# POST /task?taskid=def456&workspace=/app/data/tasks/task_def456&action=restore
```

## Troubleshooting

### Task Not Found
- Check that the task directory exists: `ls /app/data/tasks/task_<id>`
- Verify `task.json` exists and is valid JSON

### Permission Issues
- Ensure you have write permissions to the workspace directory
- Run scripts with appropriate user privileges

### Script Errors
- Check Python version (requires Python 3.6+)
- Ensure all required modules are available (uuid, json, argparse, etc.)

## Related Skills

- `planning-with-files` - Base methodology for file-based planning
- `memory-system` - Long-term memory management across tasks
- `roo-coder` - Code project management and editing
