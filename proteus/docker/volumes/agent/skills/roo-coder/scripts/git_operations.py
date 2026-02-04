#!/usr/bin/env python3
"""
Roo-Coder: Git Operations Script

Provides advanced Git operations for project management.
"""

import os
import sys
import json
import subprocess
from typing import Dict, List, Optional, Tuple


class GitOperations:
    """Advanced Git operations for Roo-Coder."""
    Note: Initialize with repo_path pointing to /app/data/{project_name}
    for proper file persistence and compatibility with the Proteus skill system.
    
    
    def __init__(self, repo_path: str = None):
        self.repo_path = repo_path or os.getcwd()
        
        # Validate repository location
        self._validate_repo_location()
        
        if not self._is_git_repo():
            raise ValueError(f"Not a git repository: {self.repo_path}")
    def _is_git_repo(self) -> bool:
        """Check if directory is a git repository."""
        try:
            result = subprocess.run(
                ['git', 'rev-parse', '--git-dir'],
                cwd=self.repo_path,
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except:
            return False
    
    def _run_git(self, command: str, args: List[str] = None) -> Dict[str, any]:
        """Run git command and return results."""
        try:
            cmd = ['git'] + command.split()
            if args:
                cmd.extend(args)
            
            result = subprocess.run(
                cmd,
                cwd=self.repo_path,
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

    def _validate_repo_location(self):
        """Validate that repository is in appropriate location for persistence."""
        normalized_path = os.path.normpath(self.repo_path)
        
        # Check if repository is under /app/data (recommended for persistence)
        app_data_path = os.path.normpath("/app/data")
        if not normalized_path.startswith(app_data_path + os.sep) and normalized_path != app_data_path:
            print(f"⚠️  Warning: Repository '{{self.repo_path}}' is not under '/app/data/'.")
            print("   For file persistence across sessions, use /app/data/{project_name}")
            print("   Files outside /app/data may not persist between sessions.")
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_detailed_status(self) -> Dict[str, any]:
        """Get comprehensive git status information."""
        # Get basic status
        status = self._run_git('status --porcelain -b')
        if not status['success']:
            return status
        
        # Parse status output
        lines = status['stdout'].split('\n')
        
        # First line contains branch info
        branch_info = lines[0] if lines else ''
        
        # Parse file status
        changes = {
            'staged': [],
            'unstaged': [],
            'untracked': [],
            'conflicted': []
        }
        
        for line in lines[1:]:
            if line:
                status_code = line[:2]
                filename = line[3:]
                
                # Classify changes
                if status_code == '??':
                    changes['untracked'].append(filename)
                elif 'U' in status_code or 'AA' in status_code or 'DD' in status_code:
                    changes['conflicted'].append({
                        'status': status_code,
                        'file': filename
                    })
                elif status_code[0] != ' ' and status_code[0] != '?':
                    changes['staged'].append({
                        'status': status_code,
                        'file': filename
                    })
                elif status_code[1] != ' ':
                    changes['unstaged'].append({
                        'status': status_code,
                        'file': filename
                    })
        
        # Get branch information
        branch_result = self._run_git('branch --show-current')
        current_branch = branch_result['stdout'] if branch_result['success'] else ''
        
        # Get remote information
        remote_result = self._run_git('remote -v')
        remotes = []
        if remote_result['success']:
            for line in remote_result['stdout'].split('\n'):
                if line:
                    parts = line.split()
                    if len(parts) >= 2:
                        remotes.append({
                            'name': parts[0],
                            'url': parts[1],
                            'type': parts[2] if len(parts) > 2 else ''
                        })
        
        return {
            'success': True,
            'current_branch': current_branch,
            'branch_info': branch_info,
            'changes': changes,
            'remotes': remotes,
            'total_changes': {
                'staged': len(changes['staged']),
                'unstaged': len(changes['unstaged']),
                'untracked': len(changes['untracked']),
                'conflicted': len(changes['conflicted'])
            }
        }
    
    def get_diff_summary(self, staged: bool = False) -> Dict[str, any]:
        """Get summary of changes."""
        command = 'diff --stat'
        if staged:
            command = 'diff --staged --stat'
        
        result = self._run_git(command)
        if not result['success']:
            return result
        
        # Parse diff --stat output
        lines = result['stdout'].split('\n')
        
        files_changed = []
        insertions = 0
        deletions = 0
        
        for line in lines:
            if '|' in line:
                # Format: "file.py | 10 +-"
                parts = line.split('|')
                if len(parts) >= 2:
                    filename = parts[0].strip()
                    stats = parts[1].strip()
                    
                    # Extract numbers
                    import re
                    numbers = re.findall(r'\d+', stats)
                    if len(numbers) >= 2:
                        file_insertions = int(numbers[0])
                        file_deletions = int(numbers[1])
                    elif len(numbers) == 1:
                        file_insertions = int(numbers[0])
                        file_deletions = 0
                    else:
                        file_insertions = 0
                        file_deletions = 0
                    
                    files_changed.append({
                        'file': filename,
                        'insertions': file_insertions,
                        'deletions': file_deletions
                    })
                    
                    insertions += file_insertions
                    deletions += file_deletions
        
        return {
            'success': True,
            'files_changed': files_changed,
            'total_insertions': insertions,
            'total_deletions': deletions,
            'file_count': len(files_changed)
        }
    
    def commit_changes(self, message: str, files: List[str] = None, 
                      type_scope: Tuple[str, str] = None) -> Dict[str, any]:
        """Commit changes with optional conventional commit formatting."""
        
        # Format commit message
        if type_scope:
            commit_type, scope = type_scope
            if scope:
                formatted_message = f"{commit_type}({scope}): {message}"
            else:
                formatted_message = f"{commit_type}: {message}"
        else:
            formatted_message = message
        
        # Stage files
        if files:
            for file in files:
                self._run_git(f'add {file}')
        else:
            self._run_git('add .')
        
        # Commit
        commit_result = self._run_git(f'commit -m "{formatted_message}"')
        
        if commit_result['success']:
            return {
                'success': True,
                'message': formatted_message,
                'output': commit_result['stdout']
            }
        else:
            return commit_result
    
    def create_branch(self, branch_name: str, from_branch: str = None) -> Dict[str, any]:
        """Create and switch to new branch."""
        if from_branch:
            # Checkout source branch first
            checkout_result = self._run_git(f'checkout {from_branch}')
            if not checkout_result['success']:
                return checkout_result
        
        # Create and switch to new branch
        result = self._run_git(f'checkout -b {branch_name}')
        
        if result['success']:
            return {
                'success': True,
                'branch': branch_name,
                'output': result['stdout']
            }
        else:
            return result
    
    def push_changes(self, branch: str = None, remote: str = 'origin', 
                    set_upstream: bool = True) -> Dict[str, any]:
        """Push changes to remote repository."""
        command = f'push {remote}'
        if branch:
            command += f' {branch}'
        if set_upstream and branch:
            command += f' --set-upstream {remote} {branch}'
        
        return self._run_git(command)
    
    def create_pull_request(self, title: str, body: str = None, draft: bool = False) -> Dict[str, any]:
        """Create pull request using GitHub CLI."""
        # Check if gh CLI is available
        try:
            subprocess.run(['gh', '--version'], capture_output=True)
        except FileNotFoundError:
            return {
                'success': False,
                'error': 'GitHub CLI (gh) not installed or not in PATH'
            }
        
        # Build gh command
        cmd = ['gh', 'pr', 'create', '--title', title]
        
        if body:
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
                f.write(body)
                body_file = f.name
            
            cmd.extend(['--body-file', body_file])
        
        if draft:
            cmd.append('--draft')
        
        try:
            result = subprocess.run(
                cmd,
                cwd=self.repo_path,
                capture_output=True,
                text=True
            )
            
            # Clean up temp file if created
            if body and 'body_file' in locals():
                import os
                os.unlink(body_file)
            
            return {
                'success': result.returncode == 0,
                'stdout': result.stdout.strip(),
                'stderr': result.stderr.strip(),
                'returncode': result.returncode
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_commit_history(self, limit: int = 10, format: str = 'oneline') -> Dict[str, any]:
        """Get commit history."""
        if format == 'oneline':
            command = f'log --oneline -{limit}'
        elif format == 'detailed':
            command = f'log --pretty=format:"%h|%an|%ad|%s" --date=short -{limit}'
        else:
            command = f'log -{limit}'
        
        result = self._run_git(command)
        if not result['success']:
            return result
        
        commits = []
        if format == 'detailed':
            for line in result['stdout'].split('\n'):
                if line:
                    parts = line.split('|')
                    if len(parts) >= 4:
                        commits.append({
                            'hash': parts[0],
                            'author': parts[1],
                            'date': parts[2],
                            'message': parts[3]
                        })
        else:
            for line in result['stdout'].split('\n'):
                if line:
                    commits.append({'raw': line})
        
        return {
            'success': True,
            'commits': commits,
            'count': len(commits)
        }



    def initialize_repository(self, project_name: str = None) -> Dict[str, any]:
        """Initialize a new git repository in the current directory.
        
        Args:
            project_name: Optional project name for README
            
        Returns:
            Dictionary with initialization results
        """
        if self._is_git_repo():
            return {
                'success': False,
                'repository_path': self.repo_path,
                'error': 'Repository already initialized'
            }
        
        # Initialize git repository
        init_result = self._run_git('init')
        if not init_result['success']:
            return init_result
        
        # Create basic git configuration
        config_results = []
        
        # Set user name if not configured
        user_result = self._run_git('config user.name')
        if not user_result['stdout']:
            self._run_git('config user.name "Roo-Coder"')
            config_results.append('Set default user name')
        
        # Set user email if not configured
        email_result = self._run_git('config user.email')
        if not email_result['stdout']:
            self._run_git('config user.email "roo-coder@example.com"')
            config_results.append('Set default user email')
        
        # Create initial commit with basic files
        readme_content = f'# {{project_name or os.path.basename(self.repo_path)}}\n\nProject initialized by Roo-Coder.'
        readme_path = os.path.join(self.repo_path, 'README.md')
        with open(readme_path, 'w') as f:
            f.write(readme_content)
        
        gitignore_content = "# Default gitignore\n__pycache__/\n*.pyc\n.env\nnode_modules/\n.DS_Store\n*.log\ndist/\nbuild/\n.coverage\nhtmlcov/\n*.sqlite3"
        gitignore_path = os.path.join(self.repo_path, '.gitignore')
        with open(gitignore_path, 'w') as f:
            f.write(gitignore_content)
        
        # Add and commit
        self._run_git('add README.md .gitignore')
        commit_result = self._run_git('commit -m "Initial commit: Project setup"')
        
        return {
            'success': True,
            'repository_path': self.repo_path,
            'initialized': True,
            'config_changes': config_results,
            'files_created': ['README.md', '.gitignore'],
            'initial_commit': commit_result['success']
        }
def main():
    """Command-line interface for Git operations."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Roo-Coder Git Operations')
    parser.add_argument('--status', action='store_true', help='Get detailed git status')
    parser.add_argument('--diff', action='store_true', help='Get diff summary')
    parser.add_argument('--diff-staged', action='store_true', help='Get staged diff summary')
    parser.add_argument('--commit', type=str, help='Commit message')
    parser.add_argument('--type', type=str, help='Commit type (feat, fix, etc.)')
    parser.add_argument('--scope', type=str, help='Commit scope')
    parser.add_argument('--create-branch', type=str, help='Create new branch')
    parser.add_argument('--from-branch', type=str, help='Source branch for new branch')
    parser.add_argument('--history', type=int, help='Get commit history (limit)')

    parser.add_argument('--init', action='store_true', help='Initialize git repository')\n    parser.add_argument('--project-name', type=str, help='Project name for initialization')
    
    args = parser.parse_args()
    
    try:
        git = GitOperations()
        
        if args.status:
            status = git.get_detailed_status()
            print(json.dumps(status, indent=2))
        
        elif args.diff:
            diff = git.get_diff_summary()
            print(json.dumps(diff, indent=2))
        
        elif args.diff_staged:
            diff = git.get_diff_summary(staged=True)
            print(json.dumps(diff, indent=2))
        
        elif args.commit:
            type_scope = (args.type, args.scope) if args.type else None
            result = git.commit_changes(args.commit, type_scope=type_scope)
            print(json.dumps(result, indent=2))
        
        elif args.create_branch:
            result = git.create_branch(args.create_branch, args.from_branch)
            print(json.dumps(result, indent=2))
        
                elif args.init:
            result = git.initialize_repository(args.project_name)
            print(json.dumps(result, indent=2))

elif args.history:
            history = git.get_commit_history(limit=args.history, format='detailed')
            print(json.dumps(history, indent=2))
        
        else:
            parser.print_help()
    
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
