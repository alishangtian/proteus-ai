# Git Command Reference

## 🎯 **IMPORTANT: Repository Location Convention**

**All Roo-Coder git repositories should be located at `/app/data/{project_name}`:**

### Why This Location?
1. **File Persistence**: Git operations on files in `/app/data/` persist across sessions
2. **Consistent Environment**: All tools work from the same directory
3. **Network Access**: Repository files accessible via HTTP
4. **Skill Integration**: Compatible with EnhancedCodeEditor and other tools

### Working with Git in `/app/data/{project_name}`:
```bash
# Always navigate to project directory first
cd /app/data/my-project

# Check git status
git status

# View project location in git output
git rev-parse --show-toplevel  # Shows: /app/data/my-project
```

### Using GitOperations Class:
```python
from scripts.git_operations import GitOperations

# Initialize with project path
git = GitOperations(repo_path="/app/data/my-project")

# All operations work from this directory
status = git.get_detailed_status()
print(f"Repository: {status['repository_path']}")  # Shows: /app/data/my-project
```

### Initializing a New Repository:
```bash
# Create project directory
mkdir -p /app/data/new-project
cd /app/data/new-project

# Initialize git repository using Roo-Coder
python /app/.proteus/skills/roo-coder/scripts/git_operations.py --init --project-name "New Project"
```

---

## Essential Git Commands



## Essential Git Commands

### Repository Status
```bash
# Check current status
git status

# View changes in working directory
git diff

# View staged changes
git diff --staged

# View brief status
git status -s
```

### Branch Operations
```bash
# List all branches
git branch -a

# Create new branch
git checkout -b feature/branch-name

# Switch to branch
git checkout branch-name

# Delete branch (local)
git branch -d branch-name

# Delete branch (remote)
git push origin --delete branch-name
```

### Commit Operations
```bash
# Stage all changes
git add .

# Stage specific files
git add file1.py file2.js

# Commit with message
git commit -m "Type(scope): Description"

# Amend last commit
git commit --amend

# View commit history
git log --oneline -20

# View detailed log
git log --graph --pretty=format:'%Cred%h%Creset -%C(yellow)%d%Creset %s %Cgreen(%cr) %C(bold blue)<%an>%Creset' --abbrev-commit
```

### Remote Operations
```bash
# View remote repositories
git remote -v

# Push to remote
git push origin branch-name

# Push with tracking
git push -u origin branch-name

# Pull from remote
git pull origin main

# Fetch from remote
git fetch origin
```

### Stashing
```bash
# Stash changes
git stash

# Stash with message
git stash save "Work in progress"

# List stashes
git stash list

# Apply stash
git stash apply stash@{0}

# Pop stash (apply and remove)
git stash pop
```

### Merging & Rebasing
```bash
# Merge branch into current
git merge feature-branch

# Rebase onto branch
git rebase main

# Abort rebase
git rebase --abort

# Continue rebase after conflicts
git rebase --continue
```

## Git Workflow Patterns

### Feature Branch Workflow
```bash
# Start new feature
git checkout main
git pull origin main
git checkout -b feature/awesome-feature

# Work on feature...
git add .
git commit -m "feat(component): Add awesome feature"

# Push feature
git push -u origin feature/awesome-feature

# Create PR, then merge via GitHub/GitLab UI
```

### Hotfix Workflow
```bash
# Create hotfix from main
git checkout main
git pull origin main
git checkout -b hotfix/critical-bug

# Fix the bug...
git add .
git commit -m "fix(core): Fix critical security bug"

# Push and create PR
git push -u origin hotfix/critical-bug
```

### Release Preparation
```bash
# Create release branch
git checkout -b release/v1.2.0

# Update version, changelog
git add .
git commit -m "chore: Update version to 1.2.0"

# Push release branch
git push -u origin release/v1.2.0
```

## Git Configuration

### User Configuration
```bash
# Set user name
git config --global user.name "Your Name"

# Set user email
git config --global user.email "your.email@example.com"

# View configuration
git config --list
```

### Aliases
```bash
# Create aliases
git config --global alias.co checkout
git config --global alias.br branch
git config --global alias.ci commit
git config --global alias.st status
git config --global alias.lg "log --graph --pretty=format:'%Cred%h%Creset -%C(yellow)%d%Creset %s %Cgreen(%cr) %C(bold blue)<%an>%Creset' --abbrev-commit"
```

## Advanced Git

### Interactive Rebase
```bash
# Rebase last 3 commits
git rebase -i HEAD~3

# Options in interactive rebase:
# p, pick = use commit
# r, reword = use commit, but edit commit message
# e, edit = use commit, but stop for amending
# s, squash = use commit, but meld into previous commit
# d, drop = remove commit
```

### Submodules
```bash
# Add submodule
git submodule add https://github.com/user/repo.git path/to/submodule

# Initialize submodules
git submodule init
git submodule update

# Update submodules
git submodule update --remote
```

### Bisect (Find Bug)
```bash
# Start bisect
git bisect start
git bisect bad HEAD
git bisect good v1.0.0

# Test current commit, then:
git bisect good  # if commit is good
git bisect bad   # if commit has bug

# Reset when done
git bisect reset
```

## Common Issues & Solutions

### Undo Changes
```bash
# Unstage file
git reset HEAD file.py

# Discard changes in working directory
git checkout -- file.py

# Reset to previous commit (soft - keep changes)
git reset --soft HEAD~1

# Reset to previous commit (hard - discard changes)
git reset --hard HEAD~1
```

### Recover Lost Commits
```bash
# View reflog
git reflog

# Reset to specific reflog entry
git reset --hard HEAD@{2}
```

### Fix Commit Author
```bash
# For last commit
git commit --amend --author="Name <email>"

# For multiple commits (use interactive rebase)
git rebase -i HEAD~5
# Mark commits as 'edit', then:
git commit --amend --author="Name <email>"
git rebase --continue
```

## Git Hooks

Common hook locations in `.git/hooks/`:
- `pre-commit`: Run before commit
- `commit-msg`: Validate commit message
- `pre-push`: Run before push

Example pre-commit hook:
```bash
#!/bin/bash
# Run tests before commit
python -m pytest tests/
```

## Integration with CI/CD

### Conventional Commits for CI
```bash
# These commit types trigger different CI behaviors:
# feat:     New feature → trigger deployment
# fix:      Bug fix → trigger deployment
# perf:     Performance → trigger deployment
# docs:     Documentation → skip deployment
# style:    Formatting → skip deployment
# refactor: Code change → skip deployment
# test:     Tests → skip deployment
# chore:    Maintenance → skip deployment
```

### PR Title Validation
PR titles should match pattern:
```
^(feat|fix|perf|test|docs|refactor|build|ci|chore|revert)(\([a-zA-Z0-9 ]+( Node)?\))?!?: [A-Z].+[^.]$
```

## Best Practices

1. **Commit Often**: Small, focused commits
2. **Write Good Messages**: Use conventional format
3. **Branch Strategically**: Follow Git flow or similar
4. **Review Before Push**: Check `git diff` and `git log`
5. **Keep History Clean**: Use rebase for feature branches
6. **Handle Conflicts Early**: Resolve as soon as they appear
7. **Use Tags for Releases**: `git tag v1.0.0 && git push origin v1.0.0`
