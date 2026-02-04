# Code Editing Patterns

## 🎯 **IMPORTANT: Project Location for File Operations**

**All file operations should assume the project is located at `/app/data/{project_name}`:**

### File Path Resolution:
```python
# ALWAYS resolve paths relative to /app/data/{project_name}
import os

# Correct way: Use project root
project_root = "/app/data/my-project"
file_path = os.path.join(project_root, "src/app.py")

# Using EnhancedCodeEditor (RECOMMENDED):
from scripts.code_editor import EnhancedCodeEditor
editor = EnhancedCodeEditor(project_root="/app/data/my-project")
success, content = editor.read_file("src/app.py")  # Resolves to /app/data/my-project/src/app.py
```

### Why This Matters:
1. **Persistence**: Files in `/app/data/` persist across sessions
2. **Consistency**: All tools use the same path resolution logic
3. **Security**: Prevents writing outside designated project area
4. **Accessibility**: Files are network-accessible via HTTP

### Example Patterns with Proper Paths:



## File Operations Patterns

### Safe File Reading
```python
import os
import sys

def read_file_safe(filepath):
    '''Read file with error handling and encoding detection'''
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        try:
            with open(filepath, 'r', encoding='latin-1') as f:
                return f.read()
        except Exception as e:
            return f"Error reading file: {e}"
    except FileNotFoundError:
        return f"File not found: {filepath}"
    except Exception as e:
        return f"Error: {e}"
```

### Safe File Writing
```python
import os
import shutil
from datetime import datetime

def write_file_safe(filepath, content, backup=True):
    '''Write file with optional backup'''
    try:
        # Create backup if requested
        if backup and os.path.exists(filepath):
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = f"{filepath}.backup_{timestamp}"
            shutil.copy2(filepath, backup_path)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        # Write file
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    except Exception as e:
        return f"Error writing file: {e}"
```

### Directory Operations
```python
import os
from pathlib import Path

def analyze_directory(path):
    '''Analyze directory structure'''
    result = {
        'path': path,
        'exists': os.path.exists(path),
        'is_dir': os.path.isdir(path),
        'files': [],
        'directories': [],
        'size': 0
    }
    
    if result['exists'] and result['is_dir']:
        for root, dirs, files in os.walk(path):
            # Limit depth for large directories
            level = root.replace(path, '').count(os.sep)
            if level > 3:  # Max 3 levels deep
                continue
                
            for dir_name in dirs:
                result['directories'].append(os.path.join(root, dir_name))
            for file_name in files:
                full_path = os.path.join(root, file_name)
                result['files'].append(full_path)
                try:
                    result['size'] += os.path.getsize(full_path)
                except:
                    pass
    
    return result
```

## Code Analysis Patterns

### Syntax Validation
```python
import ast
import subprocess
import sys

def validate_python_syntax(code):
    '''Validate Python syntax'''
    try:
        ast.parse(code)
        return True, "Syntax is valid"
    except SyntaxError as e:
        return False, f"Syntax error: {e}"
```

### Dependency Detection
```python
import re
import json
import os

def detect_project_type(directory):
    '''Detect project type based on configuration files'''
    files = os.listdir(directory)
    
    # Common project indicators
    indicators = {
        'node': ['package.json', 'package-lock.json', 'yarn.lock'],
        'python': ['requirements.txt', 'setup.py', 'pyproject.toml', 'Pipfile'],
        'java': ['pom.xml', 'build.gradle', 'build.gradle.kts'],
        'go': ['go.mod', 'go.sum'],
        'rust': ['Cargo.toml', 'Cargo.lock'],
        'ruby': ['Gemfile', 'Gemfile.lock'],
        'php': ['composer.json', 'composer.lock'],
        'docker': ['Dockerfile', 'docker-compose.yml']
    }
    
    detected = []
    for lang, config_files in indicators.items():
        for config in config_files:
            if config in files:
                detected.append(lang)
                break
    
    return detected
```

## Code Modification Patterns

### String Replacement
```python
def replace_in_code(code, old_pattern, new_pattern):
    '''Replace pattern in code with context awareness'''
    lines = code.split('
')
    modified_lines = []
    changes_made = 0
    
    for line in lines:
        if old_pattern in line:
            new_line = line.replace(old_pattern, new_pattern)
            modified_lines.append(new_line)
            changes_made += 1
        else:
            modified_lines.append(line)
    
    return '
'.join(modified_lines), changes_made
```

### Function Extraction
```python
def extract_function(code, start_line, end_line, new_function_name):
    '''Extract code block into new function'''
    lines = code.split('
')
    
    # Extract the code block
    extracted = lines[start_line-1:end_line]
    
    # Create function definition
    indent = ' ' * 4  # Assume 4-space indentation
    function_def = f"\n{indent}def {new_function_name}():"
    function_body = [indent + line for line in extracted]
    
    # Replace original code with function call
    lines[start_line-1:end_line] = [indent + f"{new_function_name}()"]
    
    # Insert function definition after imports/at appropriate location
    # Find where to insert (after imports, before first class/function)
    insert_pos = 0
    for i, line in enumerate(lines):
        if line.strip().startswith('def ') or line.strip().startswith('class '):
            insert_pos = i
            break
    
    # Insert function
    lines.insert(insert_pos, '')
    lines.insert(insert_pos + 1, function_def)
    for body_line in reversed(function_body):
        lines.insert(insert_pos + 2, body_line)
    
    return '\n'.join(lines)
```

## Project Structure Patterns

### File Organization
```python
def suggest_file_structure(project_type):
    '''Suggest file structure based on project type'''
    structures = {
        'python': [
            'src/',
            'src/__init__.py',
            'tests/',
            'tests/__init__.py',
            'requirements.txt',
            'setup.py',
            'README.md',
            '.gitignore'
        ],
        'node': [
            'src/',
            'package.json',
            'package-lock.json',
            'README.md',
            '.gitignore',
            'tsconfig.json' if 'typescript' in project_type else None
        ],
        'react': [
            'src/',
            'src/components/',
            'src/pages/',
            'src/utils/',
            'package.json',
            'README.md',
            '.gitignore',
            'public/'
        ]
    }
    
    # Clean None values
    suggestions = []
    for structure in structures.get(project_type, []):
        if structure:
            suggestions.append(structure)
    
    return suggestions
```

## Git Integration Patterns

### Git Operations via Python
```python
import subprocess
import os

def run_git_command(command, cwd=None):
    '''Run git command and return output'''
    try:
        if cwd is None:
            cwd = os.getcwd()
        
        result = subprocess.run(
            ['git'] + command.split(),
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        
        return {
            'success': result.returncode == 0,
            'stdout': result.stdout.strip(),
            'stderr': result.stderr.strip(),
            'returncode': result.returncode
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}
```

### Change Analysis
```python
def analyze_git_changes():
    '''Analyze current git changes'''
    status = run_git_command('status --porcelain')
    diff = run_git_command('diff --stat')
    
    if not status['success']:
        return None
    
    # Parse status output
    changes = {
        'staged': [],
        'unstaged': [],
        'untracked': []
    }
    
    for line in status['stdout'].split('\n'):
        if line:
            status_code = line[:2]
            filename = line[3:]
            
            if status_code == '??':
                changes['untracked'].append(filename)
            elif status_code[0] != ' ' and status_code[0] != '?':
                changes['staged'].append((status_code, filename))
            elif status_code[1] != ' ':
                changes['unstaged'].append((status_code, filename))
    
    return changes
```

## Validation Patterns

### Pre-Commit Validation
```python
def validate_changes_before_commit():
    '''Validate changes before committing'''
    issues = []
    
    # Check for syntax errors
    changes = analyze_git_changes()
    if changes:
        for status, filename in changes['staged'] + changes['unstaged']:
            if filename.endswith('.py'):
                with open(filename, 'r') as f:
                    code = f.read()
                valid, message = validate_python_syntax(code)
                if not valid:
                    issues.append(f"Syntax error in {filename}: {message}")
    
    # Check for large files
    for status, filename in changes.get('staged', []):
        try:
            size = os.path.getsize(filename)
            if size > 10 * 1024 * 1024:  # 10MB
                issues.append(f"Large file: {filename} ({size/1024/1024:.1f}MB)")
        except:
            pass
    
    return issues
```

## Template Patterns

### PR Template Generation
```python
def generate_pr_template(title, changes_summary, ticket_url=None):
    '''Generate PR template'''
    branch_name = title.split(':')[0].strip() if ':' in title else 'feature-branch'
    template = f'''## Summary

{changes_summary}

## Testing Instructions

1. Checkout this branch: `git checkout {branch_name}`
2. Run tests: `npm test` or `pytest`
3. Verify functionality manually

## Related Links

{f"[Linear Ticket]({ticket_url})" if ticket_url else "<!-- Add Linear ticket link -->"}

## Checklist

- [ ] PR title follows conventional commit format
- [ ] Code changes are tested
- [ ] Documentation updated if needed
- [ ] No breaking changes introduced
'''
    return template
```

## Best Practices

### Code Editing
1. **Always backup** before making changes
2. **Validate syntax** after modifications
3. **Make incremental changes** with verification points
4. **Follow project conventions** for formatting and style
5. **Add comments** for complex modifications

### File Management
1. **Check file permissions** before reading/writing
2. **Handle encoding properly** (UTF-8 preferred)
3. **Create directories** as needed
4. **Clean up temporary files**

### Git Integration
1. **Check git status** before operations
2. **Stage changes incrementally**
3. **Write meaningful commit messages**
4. **Verify remote connections**
5. **Handle conflicts gracefully**
