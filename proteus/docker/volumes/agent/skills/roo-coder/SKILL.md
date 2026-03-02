---
name: roo-coder
description: 'AI-driven project code management and editing system inspired by RooCode.
  Use when users need to edit code files, analyze project structures, manage Git operations,
  create pull requests, or perform automated code refactoring. This skill provides
  intelligent code editing workflows, project analysis capabilities, Git integration,
  and PR creation with proper conventions. **IMPORTANT: Project work directory should
  be /app/data/{project_name} for proper file operations and persistence.**'
allowed-tools:
- python_execute
- serper_search
- web_crawler
version: 1.0.0
---
# Roo-Coder: AI-Powered Code Management System

## Overview

Roo-Coder is an AI-driven project code management and editing system that combines intelligent code editing, project analysis, Git operations, and PR creation workflows. Inspired by RooCode's multi-mode approach, this skill enables systematic codebase management through structured workflows.

### 🎯 **CRITICAL: WORK DIRECTORY CONVENTION**
**All projects MUST be located within `/app/data/{project_name}` directory for:**
- **File Persistence**: Files saved here persist across sessions
- **Consistent Paths**: Uniform project structure for all operations  
- **Network Accessibility**: Files accessible via http://host:port/app/data/{file_name}
- **Skill Compatibility**: Ensures compatibility with other skills and tools

**Example project paths:**
- `/app/data/my-web-app` - For web applications
- `/app/data/api-service` - For backend services  
- `/app/data/data-analysis` - For data science projects
- `/app/data/mobile-app` - For mobile applications

## Core Capabilities

### 1. Intelligent Code Editing
- **File Operations**: Read, write, create, delete, and modify code files **within `/app/data/{project_name}`**
- **Code Analysis**: Syntax validation, dependency analysis, structure understanding
- **Refactoring**: Automated code improvements, pattern-based transformations
- **Batch Operations**: Multi-file editing with contextual awareness
- **Path Resolution**: Automatic handling of `/app/data/{project_name}` as project root

### 2. Project Analysis & Structure
- **Project Discovery**: Analyze directory structure, identify project type (Node.js, Python, React, etc.) **starting from `/app/data/{project_name}`**
- **Dependency Mapping**: Understand package.json, requirements.txt, pom.xml, etc.
- **Codebase Health**: Identify tech debt, potential issues, optimization opportunities
- **Architecture Understanding**: Module relationships, import/export patterns

### 3. Git Integration & Version Control
- **Basic Git Operations**: status, diff, add, commit, push, pull, branch management **within project directory**
- **Change Analysis**: Review diffs, understand commit history, track modifications
- **Conflict Resolution**: Identify and help resolve merge conflicts
- **Workflow Enforcement**: Follow Git flow or other branching strategies

### 4. PR Creation & Code Review
- **PR Title Formatting**: Follow conventional commit standards (feat:, fix:, etc.)
- **PR Body Templates**: Use structured templates with summary, testing instructions, links
- **Change Documentation**: Clearly explain what changed and why
- **Validation**: Ensure PR titles pass CI validation checks

## Enhanced Code Editor with RooCode-Style Capabilities

The enhanced code editor provides RooCode-inspired editing features with multi-mode workflows and diff-based editing, **automatically using `/app/data/{project_name}` as the project root**.

### Key Features

#### 1. Multi-Mode Editing System
- **Code Mode**: Full editing capabilities for implementation
- **Architect Mode**: Read-only analysis and planning
- **Debug Mode**: Problem diagnosis and fixing
- **Refactor Mode**: Code restructuring and improvement
- **Ask Mode**: Q&A about code (no edits)
- **Batch Mode**: Operations across multiple files

#### 2. Diff-Based Editing (RooCode-Style)
- **Smart Diffs**: Generate and apply diffs instead of full file replacements
- **Change Preview**: See exactly what will change before applying
- **Operation Tracking**: Track insertions, deletions, and replacements
- **Context-Aware**: Maintains line numbers and context during edits

#### 3. Advanced File Operations
- **Safe Editing**: Automatic backups before any modification
- **Encoding Detection**: Automatic detection of file encoding (UTF-8, Latin-1, etc.)
- **Permission Management**: Mode-specific permissions control
- **Batch Processing**: Apply operations across multiple files matching patterns
- **Path Normalization**: All paths automatically resolved relative to `/app/data/{project_name}`

#### 4. Intelligent Code Analysis
- **Language Detection**: Automatic detection of programming language
- **Project Analysis**: Comprehensive project structure analysis
- **Complexity Estimation**: Heuristic-based code complexity assessment
- **Syntax Validation**: Built-in syntax checking for multiple languages

### Using the Enhanced Editor

#### Python API with Work Directory Convention
```python
from scripts.code_editor import EnhancedCodeEditor, RooCodeWorkflow, EditMode

# Initialize editor with project in /app/data/my-project
project_name = "my-project"
project_root = f"/app/data/{project_name}"  # CRITICAL: Use this path format
editor = EnhancedCodeEditor(project_root=project_root)
workflow = RooCodeWorkflow(project_root=project_root)

# Set mode
editor.set_mode(EditMode.CODE)

# Read file (path relative to project_root)
success, content = editor.read_file("src/app.py")  # Resolves to /app/data/my-project/src/app.py

# Write file with diff generation
success, result = editor.write_file("src/app.py", new_content, create_diff=True)

# Generate diff
diff = editor.generate_diff("src/app.py", modified_content)

# Edit with diff operations
edits = [
    {
        "type": "replace",
        "line": 10,
        "old_text": "old_function()",
        "new_text": "new_function()"
    }
]
success, result = editor.edit_with_diff("src/app.py", edits)
```

#### Workflow Management
```python
# Architect workflow for planning
arch_result = workflow.architect_workflow("Design new API endpoints")

# Code workflow for implementation  
code_result = workflow.code_workflow("Implement user authentication", "auth.py")

# Debug workflow for problem-solving
debug_result = workflow.debug_workflow("Fix memory leak", "service.py")

# Refactor workflow for code improvement
refactor_result = workflow.refactor_workflow("Extract common utilities", "utils.py")
```

#### CLI Usage with Work Directory
```bash
# First, navigate to project directory
cd /app/data/my-project

# Read file
python scripts/code_editor.py --read src/app.py

# Write file
python scripts/code_editor.py --write config.yaml --content "key: value"

# Analyze file
python scripts/code_editor.py --analyze-file src/utils.py

# Analyze project (starts from /app/data/my-project)
python scripts/code_editor.py --analyze-project

# Start architect workflow
python scripts/code_editor.py --workflow architect --task "Design database schema"

# JSON output
python scripts/code_editor.py --read src/app.py --json
```

### Example: Diff-Based Editing Workflow with Proper Paths

```python
# 1. Set up project root
project_root = "/app/data/my-python-app"

# 2. Initialize editor
editor = EnhancedCodeEditor(project_root=project_root)

# 3. Read current file
success, current = editor.read_file("math.py")  # Reads /app/data/my-python-app/math.py

# 4. Create modified version
modified = current.replace("def add", "def add_numbers")

# 5. Generate diff
diff = editor.generate_diff("math.py", modified)

# 6. Preview changes
print(diff.preview())

# 7. Apply diff
diff.apply("math.py")  # Writes to /app/data/my-python-app/math.py
```

### Integration with Existing Skills

The enhanced editor integrates seamlessly with other Roo-Coder components:

1. **Git Integration**: Diffs can be converted to Git patches
2. **PR Creation**: Change summaries can populate PR descriptions
3. **Project Analysis**: Editor uses project analysis for context-aware editing
4. **Validation**: Syntax validation prevents broken code commits

### Best Practices

1. **Always Use `/app/data/{project_name}`**: Ensure all projects are created in this directory
2. **Use Relative Paths**: Pass relative paths to editor methods, not absolute paths
3. **Always Use Diffs**: Generate diffs for transparency and reversibility
4. **Choose Appropriate Mode**: Match mode to task (Architect for planning, Code for implementation)
5. **Preview Before Applying**: Always review diffs before applying changes
6. **Backup Important Files**: Use built-in backup or external version control
7. **Validate Syntax**: Run syntax checks after editing

### Examples Script

Run the examples to see the editor in action:
```bash
cd /app/data/example-project
python scripts/examples.py
```

This will demonstrate:
- Basic file operations with proper paths
- Diff-based editing
- Workflow modes
- Batch operations
- CLI usage


## Workflow Decision Tree

When starting a code management task, follow this decision process:

```
User Request → Identify Project Directory → Analyze Task Type → Select Workflow → Execute with Tools
```

### Project Directory Identification:
1. **Check if project exists in `/app/data/{project_name}`**
2. **If not, create project directory: `/app/data/{project_name}`**
3. **Set this as working directory for all operations**

### Task Type Identification:
- **Code Editing Tasks**: "Edit this file", "Refactor this function", "Add new feature"
- **Project Analysis**: "Analyze this project", "What dependencies does this use?"
- **Git Operations**: "Commit my changes", "Create a branch", "Check git status"
- **PR Creation**: "Create a PR", "Submit for review", "Merge to main"

## Workflow 1: Code Editing & Refactoring

### Step 0: Project Setup
1. **Ensure project is in `/app/data/{project_name}`**
2. **Set working directory to project root**
3. **Initialize EnhancedCodeEditor with project_root parameter**

### Step 1: Context Gathering
1. Read the target file(s) using `python_execute` with file reading operations
2. Understand the current code structure and purpose
3. Identify dependencies and relationships

### Step 2: Change Planning
1. Analyze what needs to be changed and why
2. Consider side effects and dependencies
3. Plan incremental changes with validation points

### Step 3: Implementation
1. Make changes using Python file operations **within project directory**
2. Validate syntax and logic
3. Test changes if possible (run tests, check for errors)

### Step 4: Documentation
1. Document what was changed
2. Explain the rationale for changes
3. Note any potential impacts

## Workflow 2: Project Analysis

### Step 0: Directory Setup
1. **Navigate to `/app/data/{project_name}`**
2. **Use ConfigChecker with project_path parameter**

### Step 1: Discovery
1. Scan directory structure using Python's os module
2. Identify key files (package.json, requirements.txt, etc.)
3. Determine project type and technology stack

### Step 2: Analysis
1. Read configuration files
2. Analyze dependencies and versions
3. Understand project structure and organization

### Step 3: Reporting
1. Create structured project overview
2. Identify potential issues or improvements
3. Provide recommendations based on analysis

## Workflow 3: Git Operations

### Step 0: Repository Setup
1. **Ensure git repository is in `/app/data/{project_name}`**
2. **Initialize GitOperations with repo_path parameter**

### Step 1: Status Check
1. Run `git status` to see current state
2. Review staged and unstaged changes
3. Check branch information

### Step 2: Change Management
1. Stage changes with `git add`
2. Create meaningful commits with descriptive messages
3. Follow conventional commit format when appropriate

### Step 3: Branch Operations
1. Create feature branches: `git checkout -b feature/name`
2. Switch between branches
3. Merge or rebase as needed

## Workflow 4: PR Creation

### Step 0: Preparation
1. **Ensure all changes are in `/app/data/{project_name}`**
2. Ensure all changes are committed and pushed
3. Verify the branch is up-to-date with base branch
4. Review changes with `git diff origin/main...HEAD`

### Step 1: PR Title Creation
1. Determine PR type using conventional commit format:
   - `feat`: New feature
   - `fix`: Bug fix
   - `docs`: Documentation
   - `refactor`: Code refactoring
   - `test`: Tests
   - `chore`: Maintenance

2. Add scope if applicable: `feat(api):`, `fix(ui):`
3. Write clear, imperative summary: "Add user authentication" not "Added user authentication"

### Step 2: PR Body Creation
Use the template from `templates/pr_template.md`:
1. **Summary**: What does the PR do? How to test?
2. **Related Links**: Linear tickets, GitHub issues
3. **Checklist**: Title conventions, docs updated, tests included

### Step 3: PR Submission
1. Use GitHub CLI: `gh pr create --title "..." --body-file body.md`
2. Or create through API if CLI not available
3. Set appropriate labels and reviewers

## Code Editing Patterns with Proper Paths

### File Reading with Work Directory
```python
# ALWAYS use /app/data/{project_name} as base
project_root = "/app/data/my-project"

# Method 1: Using EnhancedCodeEditor (RECOMMENDED)
editor = EnhancedCodeEditor(project_root=project_root)
success, content = editor.read_file("src/app.py")  # Reads /app/data/my-project/src/app.py

# Method 2: Direct file operations with absolute path
file_path = os.path.join(project_root, "src/app.py")
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()
```

### File Writing with Work Directory
```python
project_root = "/app/data/my-project"

# Method 1: Using EnhancedCodeEditor (RECOMMENDED)
editor = EnhancedCodeEditor(project_root=project_root)
success, result = editor.write_file("src/app.py", new_content)

# Method 2: Direct file operations
file_path = os.path.join(project_root, "src/app.py")
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(new_content)
```

### Safe File Operations with Backups
```python
import shutil
project_root = "/app/data/my-project"

# Backup before editing
source = os.path.join(project_root, "file.py")
backup = os.path.join(project_root, "file.py.backup")
shutil.copy2(source, backup)
```

### Directory Operations
```python
import os
project_root = "/app/data/my-project"

# List files in project directory
files = os.listdir(project_root)

# Walk through project structure
for root, dirs, files in os.walk(project_root):
    # root will be absolute paths under /app/data/my-project
    pass
```

## Git Command Patterns

### Basic Git Status (from project directory)
```bash
cd /app/data/my-project
git status
git diff --stat
git log --oneline -10
```

### Commit Operations
```bash
cd /app/data/my-project
git add .
git commit -m "feat(api): Add user authentication endpoint"
git push origin HEAD
```

### Branch Management
```bash
cd /app/data/my-project
git checkout -b feature/new-feature
git branch -a
git merge main
```

## Integration with Create-PR Skill

This skill integrates with the existing `create-pr` skill. When PR creation is needed:

1. Use the patterns and templates from this skill for preparation
2. Refer to `create-pr` skill for specific PR title validation rules
3. Combine both skills' best practices for optimal PR creation

## Common Scenarios

### Scenario 1: Editing a Python File in /app/data/{project_name}
1. **Set project_root = "/app/data/{project_name}"**
2. Read the file to understand current implementation
3. Make targeted changes using Python string manipulation
4. Validate Python syntax
5. Commit changes with descriptive message
6. Create PR if needed

### Scenario 2: Adding New Feature
1. **Ensure project is in `/app/data/{project_name}`**
2. Analyze project structure to find appropriate location
3. Create new files or modify existing ones
4. Update dependencies if needed
5. Test the implementation
6. Document changes and create PR

### Scenario 3: Bug Fix
1. **Navigate to `/app/data/{project_name}`**
2. Identify the problematic code
3. Understand the root cause
4. Implement fix with minimal changes
5. Add test case if possible
6. Create fix PR with proper title

## Quality Standards

### Code Quality
- Follow existing project conventions
- Maintain consistent formatting
- Add comments for complex logic
- Consider performance implications

### Commit Quality
- Use descriptive commit messages
- Group related changes together
- Follow conventional commit format
- Keep commits focused and atomic

### PR Quality
- Clear title following conventions
- Comprehensive description
- Testing instructions
- Related issue links

### Path Quality
- **ALWAYS use `/app/data/{project_name}` as project root**
- Use relative paths within project
- Never hardcode absolute paths outside of `/app/data/`
- Ensure all file operations respect the work directory convention

## References

- **Git Commands**: See `references/git_commands.md` for detailed Git usage
- **PR Templates**: See `templates/` for PR body templates
- **Code Patterns**: See `references/code_patterns.md` for common editing patterns
- **Project Types**: See `references/project_types.md` for different tech stack patterns

## Troubleshooting

### Common Issues
1. **File not found**: Verify paths, ensure you're in `/app/data/{project_name}`
2. **Permission errors**: Ensure file permissions allow reading/writing
3. **Git errors**: Check Git configuration, remote setup
4. **Syntax errors**: Validate code changes before committing
5. **Wrong directory**: Always start from `/app/data/{project_name}`

### Validation Steps
1. **Always verify project is in `/app/data/{project_name}`**
2. Always backup before major changes
3. Test changes incrementally
4. Verify Git operations with status checks
5. Review PR details before submission

### Work Directory Checklist
- [ ] Project created in `/app/data/{project_name}`
- [ ] All file operations use relative paths from project root
- [ ] EnhancedCodeEditor initialized with correct project_root
- [ ] GitOperations initialized with correct repo_path
- [ ] ConfigChecker initialized with correct project_path

---

*Note: This skill is designed to work in conjunction with existing tools like `python_execute` for file operations and `serper_search` for documentation lookup when needed. **The `/app/data/{project_name}` work directory convention is critical for proper operation and data persistence.***

*Last Updated: 2026-02-04 (Enhanced with work directory emphasis)*
