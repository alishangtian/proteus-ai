---
name: manus
version: 2.5.0
description: Implements Manus-style file-based planning for complex tasks. Creates
  task_plan.md, findings.md, and progress.md. Use when starting complex multi-step
  tasks, research projects, or any task requiring >5 tool calls. Now with automatic
  session recovery after /clear.
user-invocable: true
hooks:
  Stop:
  - hooks:
    - command: 'if command -v pwsh &> /dev/null && [[ "$OSTYPE" == "msys" || "$OSTYPE"
        == "win32" || "$OS" == "Windows_NT" ]]; then pwsh -ExecutionPolicy Bypass
        -File "/app/.proteus/skills/manus/scripts/check-complete.ps1" 2>/dev/null
        || powershell -ExecutionPolicy Bypass -File "/app/.proteus/skills/manus/scripts/check-complete.ps1"
        2>/dev/null || bash "/app/.proteus/skills/manus/scripts/check-complete.sh"

        else bash "/app/.proteus/skills/manus/scripts/check-complete.sh" fi'
      type: command
allowed-tools:
  - python_execute
  - serper_search
  - web_crawler
---
# manus

Use persistent markdown files as your "working memory on disk."

## FIRST: Check for Previous Session & Project Directory (v2.5.0)

**Enhanced Project Discovery:** Before starting work, check for existing projects to avoid duplication and leverage previous work. 

### Step 1: Scan Existing Projects
Scan the `/app/data/manus/` directory to see all existing projects.

**Option A: Run the list-projects script (recommended):**
```bash
python3 /app/.proteus/skills/manus/scripts/list-projects.py "$(basename $(pwd))"
```

**Option B: Use Python code directly:**
```python
import os

manus_dir = "/app/data/manus"
if os.path.exists(manus_dir):
    projects = [d for d in os.listdir(manus_dir) if os.path.isdir(os.path.join(manus_dir, d))]
    print(f"Existing projects in {manus_dir}:")
    for project in sorted(projects):
        print(f"  - {project}")
else:
    print(f"Directory does not exist: {manus_dir}")
```

### Step 2: Check for Previous Session Context
If you decide to use the current directory (new or existing project), check for unsynced context from previous sessions:

```bash
python3 /app/.proteus/skills/manus/scripts/session-catchup.py "$(pwd)"
```

**If catchup report shows unsynced context:**
1. Run `git diff --stat` to see actual code changes
2. Read current planning files (`task_plan.md`, `findings.md`, `progress.md`)
3. Update planning files based on catchup report + git diff
4. Then proceed with task

### Decision Guidelines

| Situation | Model Action |
|-----------|--------------|
| Existing project name matches or is very similar to current task | Consider using existing project |
| Existing project has some relevance but not exact match | Evaluate based on task context |
| No relevant existing projects found | Create new project |
| Unsynced context detected | Review and integrate before proceeding |

**Key Principle:** The model should use its judgment to determine project similarity, not rely on automated scoring.
imited)
Filesystem = Disk (persistent, unlimited)

→ Anything important gets written to disk.
```

## File Purposes

| File | Purpose | When to Update |
|------|---------|----------------|
| `task_plan.md` | Phases, progress, decisions | After each phase |
| `findings.md` | Research, discoveries | After ANY discovery |
| `progress.md` | Session log, test results | Throughout session |

## Critical Rules

### 1. Create Plan First
Never start a complex task without `task_plan.md`. Non-negotiable.

### 2. The 2-Action Rule
> "After every 2 view/browser/search operations, IMMEDIATELY save key findings to text files."

This prevents visual/multimodal information from being lost.

### 3. Read Before Decide
Before major decisions, read the plan file. This keeps goals in your attention window.

### 4. Update After Act
After completing any phase:
- Mark phase status: `in_progress` → `complete`
- Log any errors encountered
- Note files created/modified

### 5. Log ALL Errors
Every error goes in the plan file. This builds knowledge and prevents repetition.

```markdown
## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| FileNotFoundError | 1 | Created default config |
| API timeout | 2 | Added retry logic |
```

### 6. Never Repeat Failures
```
if action_failed:
    next_action != same_action
```
Track what you tried. Mutate the approach.

## The 3-Strike Error Protocol

```
ATTEMPT 1: Diagnose & Fix
  → Read error carefully
  → Identify root cause
  → Apply targeted fix

ATTEMPT 2: Alternative Approach
  → Same error? Try different method
  → Different tool? Different library?
  → NEVER repeat exact same failing action

ATTEMPT 3: Broader Rethink
  → Question assumptions
  → Search for solutions
  → Consider updating the plan

AFTER 3 FAILURES: Escalate to User
  → Explain what you tried
  → Share the specific error
  → Ask for guidance
```

## Read vs Write Decision Matrix

| Situation | Action | Reason |
|-----------|--------|--------|
| Just wrote a file | DON'T read | Content still in context |
| Viewed image/PDF | Write findings NOW | Multimodal → text before lost |
| Browser returned data | Write to file | Screenshots don't persist |
| Starting new phase | Read plan/findings | Re-orient if context stale |
| Error occurred | Read relevant file | Need current state to fix |
| Resuming after gap | Read all planning files | Recover state |

## The 5-Question Reboot Test

If you can answer these, your context management is solid:

| Question | Answer Source |
|----------|---------------|
| Where am I? | Current phase in task_plan.md |
| Where am I going? | Remaining phases |
| What's the goal? | Goal statement in plan |
| What have I learned? | findings.md |
| What have I done? | progress.md |

## When to Use This Pattern

**Use for:**
- Multi-step tasks (3+ steps)
- Research tasks
- Building/creating projects
- Tasks spanning many tool calls
- Anything requiring organization

**Skip for:**
- Simple questions
- Single-file edits
- Quick lookups

## Templates

Copy these templates to start:

- [templates/task_plan.md](templates/task_plan.md) — Phase tracking
- [templates/findings.md](templates/findings.md) — Research storage
- [templates/progress.md](templates/progress.md) — Session logging

## Scripts

Helper scripts for automation:

- `scripts/init-session.sh` — Initialize all planning files
- `scripts/check-complete.sh` — Verify all phases complete
- `scripts/session-catchup.py` — Recover context from previous session (v2.2.0)

## Advanced Topics

- **Manus Principles:** See [reference.md](reference.md)
- **Real Examples:** See [examples.md](examples.md)

## Anti-Patterns

| Don't | Do Instead |
|-------|------------|
| Use TodoWrite for persistence | Create task_plan.md file |
| State goals once and forget | Re-read plan before decisions |
| Hide errors and retry silently | Log errors to plan file |
| Stuff everything in context | Store large content in files |
| Start executing immediately | Create plan file FIRST |
| Repeat failed actions | Track attempts, mutate approach |
| Create files in skill directory | Create files in your project |
