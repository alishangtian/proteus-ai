#!/usr/bin/env python3
"""
Roo-Coder: Enhanced Code Editor with RooCode-style Editing Capabilities

This module provides advanced code editing utilities inspired by RooCode's
multi-mode approach and diff-based editing system.

IMPORTANT: All projects should be located in /app/data/{project_name} directory
for proper file persistence and compatibility with the Proteus skill system.
"""

import os
import sys
import json
import shutil
import difflib
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any, Union
from enum import Enum


class EditMode(Enum):
    """Editing modes inspired by RooCode's multi-mode system."""
    CODE = "code"          # Standard code editing and implementation
    ARCHITECT = "architect" # Planning and design (read-only analysis)
    ASK = "ask"            # Q&A about code (no edits)
    DEBUG = "debug"        # Debugging and problem-solving
    REFACTOR = "refactor"  # Code refactoring and restructuring
    BATCH = "batch"        # Batch operations across multiple files


class DiffOperation(Enum):
    """Types of diff operations."""
    ADD = "add"
    DELETE = "delete"
    REPLACE = "replace"
    MOVE = "move"


class CodeDiff:
    """Represents a diff between two versions of code."""
    
    def __init__(self, filepath: str, original: str, modified: str):
        self.filepath = filepath
        self.original = original
        self.modified = modified
        self.diff = self._generate_diff()
        self.operations = self._analyze_operations()
    
    def _generate_diff(self) -> List[str]:
        """Generate unified diff between original and modified."""
        original_lines = self.original.splitlines(keepends=True)
        modified_lines = self.modified.splitlines(keepends=True)
        
        diff = difflib.unified_diff(
            original_lines,
            modified_lines,
            fromfile=f'a/{self.filepath}',
            tofile=f'b/{self.filepath}',
            lineterm=''
        )
        return list(diff)
    
    def _analyze_operations(self) -> List[Dict[str, Any]]:
        """Analyze diff to extract specific operations."""
        operations = []
        original_lines = self.original.splitlines()
        modified_lines = self.modified.splitlines()
        
        # Use SequenceMatcher for detailed analysis
        matcher = difflib.SequenceMatcher(None, original_lines, modified_lines)
        
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            op_info = {
                'operation': tag,
                'original_range': (i1, i2),
                'modified_range': (j1, j2),
                'original_text': '\n'.join(original_lines[i1:i2]) if i1 < i2 else '',
                'modified_text': '\n'.join(modified_lines[j1:j2]) if j1 < j2 else '',
            }
            
            # Map to our operation types
            if tag == 'equal':
                continue
            elif tag == 'replace':
                op_info['type'] = DiffOperation.REPLACE.value
            elif tag == 'delete':
                op_info['type'] = DiffOperation.DELETE.value
            elif tag == 'insert':
                op_info['type'] = DiffOperation.ADD.value
            
            operations.append(op_info)
        
        return operations
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of changes."""
        op_types = {}
        for op in self.operations:
            if 'type' in op:
                op_type = op['type']
                op_types[op_type] = op_types.get(op_type, 0) + 1
        
        return {
            'file': self.filepath,
            'diff_lines': len(self.diff),
            'operations': len(self.operations),
            'operations_by_type': op_types,
            'has_changes': len(self.operations) > 0
        }
    
    def apply(self, filepath: str = None) -> bool:
        """Apply diff to file."""
        target = filepath or self.filepath
        try:
            with open(target, 'w', encoding='utf-8') as f:
                f.write(self.modified)
            return True
        except Exception:
            return False
    
    def preview(self, context_lines: int = 3) -> str:
        """Generate human-readable preview of changes."""
        if not self.diff:
            return "No changes"
        
        preview_lines = []
        for line in self.diff:
            if line.startswith('---') or line.startswith('+++'):
                continue
            preview_lines.append(line)
        
        # Limit preview size
        max_lines = context_lines * 10
        if len(preview_lines) > max_lines:
            preview_lines = preview_lines[:max_lines]
            preview_lines.append(f"... ({len(self.diff) - max_lines} more lines)")
        
        return '\n'.join(preview_lines)


class EnhancedCodeEditor:
    """Enhanced code editor with RooCode-style capabilities.
    
    CRITICAL: For proper operation and file persistence, projects should be
    located in /app/data/{project_name} directory. This ensures:
    1. Files persist across sessions
    2. Consistent path resolution
    3. Compatibility with other Proteus skills
    4. Network accessibility via http://host:port/app/data/
    """
    
    def __init__(self, project_root: str = None, mode: EditMode = EditMode.CODE):
        """
        Initialize editor with project root directory.
        
        Args:
            project_root: Path to project root. Recommended: /app/data/{project_name}
            mode: Initial editing mode
        """
        self.project_root = project_root or os.getcwd()
        self.mode = mode
        
        # Validate project root is under /app/data for persistence
        self._validate_project_root()
        
        self.backup_dir = os.path.join(self.project_root, '.roocoder_backups')
        self.temp_dir = os.path.join(self.project_root, '.roocoder_temp')
        os.makedirs(self.backup_dir, exist_ok=True)
        os.makedirs(self.temp_dir, exist_ok=True)
        
        # Mode-specific permissions
        self.mode_permissions = {
            EditMode.CODE: {'read': True, 'write': True, 'execute': True, 'analyze': True},
            EditMode.ARCHITECT: {'read': True, 'write': False, 'execute': False, 'analyze': True},
            EditMode.ASK: {'read': True, 'write': False, 'execute': False, 'analyze': True},
            EditMode.DEBUG: {'read': True, 'write': True, 'execute': True, 'analyze': True},
            EditMode.REFACTOR: {'read': True, 'write': True, 'execute': False, 'analyze': True},
            EditMode.BATCH: {'read': True, 'write': True, 'execute': False, 'analyze': True},
        }
    
    def _validate_project_root(self):
        """Validate that project root is appropriate for file persistence."""
        normalized_root = os.path.normpath(self.project_root)
        
        # Check if project root is under /app/data (recommended for persistence)
        app_data_path = os.path.normpath("/app/data")
        if not normalized_root.startswith(app_data_path + os.sep) and normalized_root != app_data_path:
            print(f"⚠️  Warning: Project root '{self.project_root}' is not under '/app/data/'.")
            print("   For file persistence across sessions, use /app/data/{project_name}")
            print("   Files outside /app/data may not persist between sessions.")
        
        # Ensure directory exists
        os.makedirs(self.project_root, exist_ok=True)
        
        # Check write permissions
        test_file = os.path.join(self.project_root, '.roocoder_test')
        try:
            with open(test_file, 'w') as f:
                f.write('test')
            os.unlink(test_file)
        except PermissionError:
            print(f"⚠️  Warning: No write permission in '{self.project_root}'")
        except Exception as e:
            print(f"⚠️  Warning: Cannot write to '{self.project_root}': {e}")
    
    def set_mode(self, mode: EditMode):
        """Switch editing mode."""
        self.mode = mode
        return f"Switched to {mode.value} mode"
    
    def check_permission(self, action: str) -> bool:
        """Check if current mode allows specific action."""
        permissions = self.mode_permissions.get(self.mode, {})
        return permissions.get(action, False)
    
    # ===== Path Resolution Methods =====
    
    def resolve_path(self, filepath: str) -> str:
        """Resolve file path relative to project root.
        
        Args:
            filepath: Relative or absolute path. If relative, resolves from project_root.
            
        Returns:
            Absolute path normalized for the system.
            
        Note:
            - If filepath is already absolute, returns it as-is
            - Otherwise, joins with project_root
            - Always returns normalized path
        """
        if os.path.isabs(filepath):
            return os.path.normpath(filepath)
        else:
            return os.path.normpath(os.path.join(self.project_root, filepath))
    
    def is_within_project(self, filepath: str) -> bool:
        """Check if a path is within the project directory."""
        resolved = self.resolve_path(filepath)
        project_norm = os.path.normpath(self.project_root)
        
        # Check if resolved path starts with project path
        common = os.path.commonpath([resolved, project_norm])
        return common == project_norm
    
    def get_relative_path(self, filepath: str) -> str:
        """Get path relative to project root."""
        resolved = self.resolve_path(filepath)
        try:
            return os.path.relpath(resolved, self.project_root)
        except ValueError:
            return resolved
    
    # ===== Core File Operations =====
    
    def read_file(self, filepath: str, encoding: str = 'utf-8') -> Tuple[bool, str]:
        """Read file with comprehensive error handling.
        
        Args:
            filepath: Path relative to project_root or absolute path
            encoding: File encoding to use
            
        Returns:
            Tuple of (success, content_or_error_message)
            
        Note:
            - Path is automatically resolved relative to project_root
            - Multiple encodings are tried if default fails
        """
        if not self.check_permission('read'):
            return False, f"Read not allowed in {self.mode.value} mode"
        
        try:
            full_path = self.resolve_path(filepath)
            
            # Security check: ensure file is within project
            if not self.is_within_project(full_path):
                return False, f"Access denied: File '{filepath}' is outside project directory"
            
            # Try multiple encodings
            encodings_to_try = [encoding, 'utf-8-sig', 'latin-1', 'cp1252']
            for enc in encodings_to_try:
                try:
                    with open(full_path, 'r', encoding=enc) as f:
                        content = f.read()
                    return True, content
                except UnicodeDecodeError:
                    continue
            
            return False, "Failed to decode file with any supported encoding"
        except FileNotFoundError:
            return False, f"File not found: {filepath} (resolved to: {full_path if 'full_path' in locals() else 'unknown'})"
        except PermissionError:
            return False, f"Permission denied: {filepath}"
        except Exception as e:
            return False, f"Error reading file: {e}"
    
    def write_file(self, filepath: str, content: str, backup: bool = True, 
                  create_diff: bool = True) -> Tuple[bool, Union[str, Dict]]:
        """Write file with backup and optional diff generation.
        
        Args:
            filepath: Path relative to project_root or absolute path
            content: Content to write
            backup: Whether to create backup before writing
            create_diff: Whether to generate diff against previous version
            
        Returns:
            Tuple of (success, result_or_error_message)
            
        Note:
            - Creates parent directories if they don't exist
            - Generates backup in .roocoder_backups/ directory
            - Returns diff summary if create_diff=True and file existed
        """
        if not self.check_permission('write'):
            return False, f"Write not allowed in {self.mode.value} mode"
        
        try:
            full_path = self.resolve_path(filepath)
            
            # Security check: ensure file is within project
            if not self.is_within_project(full_path):
                return False, f"Access denied: Cannot write outside project directory"
            
            # Read original content if exists
            original_content = None
            if os.path.exists(full_path) and create_diff:
                success, orig = self.read_file(full_path)
                if success:
                    original_content = orig
            
            # Create backup
            if backup and os.path.exists(full_path):
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_filename = f"{os.path.basename(full_path)}.backup_{timestamp}"
                backup_path = os.path.join(self.backup_dir, backup_filename)
                shutil.copy2(full_path, backup_path)
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            
            # Write file
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Generate diff if requested and original exists
            result = {'success': True, 'message': 'File written successfully', 'path': full_path}
            if create_diff and original_content is not None:
                diff = CodeDiff(filepath, original_content, content)
                result['diff'] = diff.get_summary()
                result['preview'] = diff.preview()
                result['has_changes'] = diff.get_summary()['has_changes']
            
            return True, result
        except Exception as e:
            return False, f"Error writing file: {e}"
    
    def edit_with_diff(self, filepath: str, edits: List[Dict[str, Any]]) -> Tuple[bool, Union[str, Dict]]:
        """Edit file using diff operations (RooCode-style).
        
        Args:
            filepath: Path relative to project_root or absolute path
            edits: List of edit operations
            
        Returns:
            Tuple of (success, result_or_error_message)
        """
        if not self.check_permission('write'):
            return False, f"Write not allowed in {self.mode.value} mode"
        
        try:
            # Read current content
            success, content = self.read_file(filepath)
            if not success:
                return False, content
            
            lines = content.splitlines(keepends=True)
            modified_lines = lines.copy()
            
            # Apply edits in reverse order to maintain line numbers
            edits.sort(key=lambda x: x.get('line', 0), reverse=True)
            
            applied_edits = []
            for edit in edits:
                edit_type = edit.get('type', 'replace')
                line_num = edit.get('line', 0) - 1  # Convert to 0-based
                old_text = edit.get('old_text', '')
                new_text = edit.get('new_text', '')
                
                if edit_type == 'replace':
                    if 0 <= line_num < len(modified_lines):
                        if modified_lines[line_num].rstrip('\n') == old_text:
                            modified_lines[line_num] = new_text + ('\n' if modified_lines[line_num].endswith('\n') else '')
                            applied_edits.append(edit)
                elif edit_type == 'insert':
                    if 0 <= line_num <= len(modified_lines):
                        modified_lines.insert(line_num, new_text + '\n')
                        applied_edits.append(edit)
                elif edit_type == 'delete':
                    if 0 <= line_num < len(modified_lines):
                        if modified_lines[line_num].rstrip('\n') == old_text:
                            del modified_lines[line_num]
                            applied_edits.append(edit)
            
            # Write modified content
            new_content = ''.join(modified_lines)
            return self.write_file(filepath, new_content, create_diff=True)
        
        except Exception as e:
            return False, f"Error applying edits: {e}"
    
    # ===== Advanced Editing Features =====
    
    def generate_diff(self, filepath: str, new_content: str) -> Optional[CodeDiff]:
        """Generate diff between current file and new content."""
        success, current_content = self.read_file(filepath)
        if not success:
            return None
        
        return CodeDiff(filepath, current_content, new_content)
    
    def apply_diff(self, filepath: str, diff: CodeDiff) -> bool:
        """Apply a diff to a file."""
        return diff.apply(filepath)
    
    # ===== Code Analysis =====
    
    def analyze_file(self, filepath: str) -> Dict[str, Any]:
        """Analyze a single file."""
        if not self.check_permission('analyze'):
            return {'error': f"Analysis not allowed in {self.mode.value} mode"}
        
        success, content = self.read_file(filepath)
        if not success:
            return {'error': content}
        
        full_path = self.resolve_path(filepath)
        relative_path = self.get_relative_path(filepath)
        
        analysis = {
            'file': relative_path,
            'absolute_path': full_path,
            'size_bytes': len(content),
            'lines': len(content.splitlines()),
            'language': self._detect_language(filepath),
            'in_project_directory': self.is_within_project(full_path),
            'project_root': self.project_root,
        }
        
        return analysis
    
    def analyze_project(self, max_depth: int = 3) -> Dict[str, Any]:
        """Analyze entire project structure.
        
        Args:
            max_depth: Maximum directory depth to traverse
            
        Returns:
            Dictionary with project analysis
        """
        if not self.check_permission('analyze'):
            return {'error': f"Analysis not allowed in {self.mode.value} mode"}
        
        result = {
            'project_root': self.project_root,
            'is_under_app_data': self.project_root.startswith('/app/data'),
            'files': [],
            'by_language': {},
            'by_extension': {},
            'total_size': 0,
            'total_files': 0,
            'directory_depth': {},
        }
        
        for root, dirs, files in os.walk(self.project_root):
            # Skip hidden directories and common excluded dirs
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', '__pycache__', '.git', '.roocoder_backups', '.roocoder_temp']]
            
            level = root.replace(self.project_root, '').count(os.sep)
            if level > max_depth:
                continue
            
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, self.project_root)
                
                # Get file info
                try:
                    size = os.path.getsize(full_path)
                    ext = os.path.splitext(file)[1].lower()
                    language = self._detect_language(file)
                    
                    file_info = {
                        'path': rel_path,
                        'size': size,
                        'extension': ext,
                        'language': language,
                        'depth': level
                    }
                    
                    result['files'].append(file_info)
                    result['total_size'] += size
                    result['total_files'] += 1
                    
                    # Update counters
                    result['by_language'][language] = result['by_language'].get(language, 0) + 1
                    result['by_extension'][ext] = result['by_extension'].get(ext, 0) + 1
                    result['directory_depth'][level] = result['directory_depth'].get(level, 0) + 1
                    
                except Exception as e:
                    continue  # Skip files we can't access
        
        return result
    
    def _detect_language(self, filename: str) -> str:
        """Detect programming language from filename."""
        ext_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.jsx': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'typescript',
            '.java': 'java',
            '.cpp': 'c++',
            '.c': 'c',
            '.h': 'c/c++',
            '.cs': 'c#',
            '.go': 'go',
            '.rs': 'rust',
            '.rb': 'ruby',
            '.php': 'php',
            '.html': 'html',
            '.css': 'css',
            '.scss': 'scss',
            '.json': 'json',
            '.xml': 'xml',
            '.yml': 'yaml',
            '.yaml': 'yaml',
            '.md': 'markdown',
            '.txt': 'text',
            '.sh': 'shell',
            '.bash': 'shell',
        }
        
        ext = os.path.splitext(filename)[1].lower()
        return ext_map.get(ext, 'unknown')
    
    # ===== Validation =====
    
    def validate_syntax(self, filepath: str) -> Tuple[bool, str]:
        """Validate syntax of a file."""
        success, content = self.read_file(filepath)
        if not success:
            return False, content
        
        language = self._detect_language(filepath)
        
        if language == 'python':
            try:
                import ast
                ast.parse(content)
                return True, "Python syntax is valid"
            except SyntaxError as e:
                return False, f"Python syntax error: {e}"
        
        # For other languages, we could add more validators
        return True, f"No syntax validator available for {language}"
    
    # ===== Project Utilities =====
    
    def create_project_structure(self, structure: Dict[str, Any] = None):
        """Create standard project structure.
        
        Args:
            structure: Optional custom structure. If None, creates standard structure.
        """
        if structure is None:
            structure = {
                'src': {},
                'tests': {},
                'docs': {},
                'config': {},
                'data': {},
                'logs': {},
            }
        
        created = []
        for dir_name in structure.keys():
            dir_path = os.path.join(self.project_root, dir_name)
            os.makedirs(dir_path, exist_ok=True)
            created.append(dir_path)
        
        # Create basic files
        basic_files = {
            'README.md': f'# {os.path.basename(self.project_root)}\n\nProject description.',
            '.gitignore': '# Ignore files\n__pycache__/\n*.pyc\n.env\nnode_modules/\n',
            'requirements.txt': '# Project dependencies\n',
        }
        
        for filename, content in basic_files.items():
            filepath = os.path.join(self.project_root, filename)
            if not os.path.exists(filepath):
                with open(filepath, 'w') as f:
                    f.write(content)
                created.append(filepath)
        
        return {'success': True, 'created': created}


# ===== RooCode-style Workflow Manager =====

class RooCodeWorkflow:
    """Manages RooCode-style workflows and modes.
    
    Note: Initialize with project_root pointing to /app/data/{project_name}
    for proper file persistence and compatibility.
    """
    
    def __init__(self, project_root: str = None):
        """
        Initialize workflow manager.
        
        Args:
            project_root: Path to project root. Use /app/data/{project_name} for persistence.
        """
        self.project_root = project_root or os.getcwd()
        self.editor = EnhancedCodeEditor(project_root)
    
    def architect_workflow(self, task_description: str) -> Dict[str, Any]:
        """Architect workflow: analyze and plan."""
        self.editor.set_mode(EditMode.ARCHITECT)
        
        # Analyze project
        analysis = self.editor.analyze_project()
        
        return {
            'mode': 'architect',
            'task': task_description,
            'project_root': self.project_root,
            'project_analysis': analysis,
            'recommendations': self._generate_architect_recommendations(analysis),
            'next_steps': [
                '1. Review project structure',
                '2. Identify key components',
                '3. Plan implementation strategy',
                '4. Create implementation checklist'
            ]
        }
    
    def code_workflow(self, task_description: str, target_file: str = None) -> Dict[str, Any]:
        """Code workflow: implement changes."""
        self.editor.set_mode(EditMode.CODE)
        
        workflow = {
            'mode': 'code',
            'task': task_description,
            'target_file': target_file,
            'project_root': self.project_root,
            'steps': [
                '1. Analyze current implementation',
                '2. Plan specific changes',
                '3. Create backup',
                '4. Implement changes',
                '5. Validate changes',
                '6. Run tests if available'
            ]
        }
        
        if target_file:
            file_analysis = self.editor.analyze_file(target_file)
            workflow['file_analysis'] = file_analysis
        
        return workflow
    
    def debug_workflow(self, problem_description: str, target_file: str = None) -> Dict[str, Any]:
        """Debug workflow: diagnose and fix."""
        self.editor.set_mode(EditMode.DEBUG)
        
        workflow = {
            'mode': 'debug',
            'problem': problem_description,
            'target_file': target_file,
            'project_root': self.project_root,
            'steps': [
                '1. Reproduce the issue',
                '2. Identify symptoms',
                '3. Locate problematic code',
                '4. Determine root cause',
                '5. Implement fix',
                '6. Verify fix works',
                '7. Add regression test if possible'
            ]
        }
        
        if target_file:
            # Check syntax
            valid, message = self.editor.validate_syntax(target_file)
            workflow['syntax_check'] = {
                'valid': valid,
                'message': message
            }
        
        return workflow
    
    def refactor_workflow(self, refactoring_goal: str, target_file: str = None) -> Dict[str, Any]:
        """Refactor workflow: improve code structure."""
        self.editor.set_mode(EditMode.REFACTOR)
        
        workflow = {
            'mode': 'refactor',
            'goal': refactoring_goal,
            'target_file': target_file,
            'project_root': self.project_root,
            'steps': [
                '1. Analyze current code structure',
                '2. Identify improvement opportunities',
                '3. Plan refactoring approach',
                '4. Create backup',
                '5. Apply refactoring incrementally',
                '6. Verify behavior unchanged',
                '7. Update documentation if needed'
            ]
        }
        
        return workflow
    
    def _generate_architect_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        """Generate architectural recommendations."""
        recommendations = []
        
        # Check project location
        if not analysis.get('is_under_app_data', False):
            recommendations.append("Project is not under /app/data/. Move to /app/data/{project_name} for persistence.")
        
        # Check project size
        if analysis['total_files'] > 100:
            recommendations.append("Large codebase detected. Consider modularization.")
        
        # Check file organization
        files_by_depth = analysis.get('directory_depth', {})
        
        # If many files at root level
        if files_by_depth.get(0, 0) > 20:
            recommendations.append("Many files at root level. Consider better organization.")
        
        # Check for common missing files
        expected_files = ['README.md', '.gitignore', 'LICENSE']
        present_files = [f['path'] for f in analysis['files']]
        for expected in expected_files:
            if expected not in present_files:
                recommendations.append(f"Consider adding {expected}")
        
        return recommendations


# ===== CLI Interface =====

def main():
    """Command-line interface for enhanced code editor."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Roo-Coder Enhanced Code Editor',
        epilog='Note: For file persistence, use projects in /app/data/{project_name}'
    )
    
    # Mode selection
    parser.add_argument('--mode', choices=['code', 'architect', 'debug', 'refactor', 'ask', 'batch'],
                       help='Editing mode')
    
    # File operations
    parser.add_argument('--read', type=str, help='Read file content (relative to project root)')
    parser.add_argument('--write', type=str, help='Write file (relative to project root)')
    parser.add_argument('--content', type=str, help='Content to write')
    
    # Analysis
    parser.add_argument('--analyze-file', type=str, help='Analyze a file')
    parser.add_argument('--analyze-project', action='store_true', help='Analyze project')
    
    # Workflows
    parser.add_argument('--workflow', choices=['architect', 'code', 'debug', 'refactor'],
                       help='Start a workflow')
    parser.add_argument('--task', type=str, help='Task description for workflow')
    parser.add_argument('--target', type=str, help='Target file for workflow')
    
    # Project setup
    parser.add_argument('--project-root', type=str, help='Project root directory (default: current directory)')
    parser.add_argument('--create-structure', action='store_true', help='Create standard project structure')
    
    # Output
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    args = parser.parse_args()
    
    # Initialize with project root
    project_root = args.project_root or os.getcwd()
    editor = EnhancedCodeEditor(project_root)
    workflow_manager = RooCodeWorkflow(project_root)
    
    results = {}
    
    # Handle operations
    if args.read:
        success, content = editor.read_file(args.read)
        if args.json:
            results['read'] = {'success': success, 'content': content if success else None}
        else:
            if success:
                print(content)
            else:
                print(f"Error: {content}", file=sys.stderr)
    
    elif args.write and args.content:
        success, result = editor.write_file(args.write, args.content)
        if args.json:
            results['write'] = {'success': success, 'result': result}
        else:
            if success:
                print(f"File written: {args.write}")
                if isinstance(result, dict) and 'preview' in result:
                    print("\nChanges preview:")
                    print(result['preview'])
            else:
                print(f"Error: {result}", file=sys.stderr)
    
    elif args.analyze_file:
        analysis = editor.analyze_file(args.analyze_file)
        if args.json:
            results['analysis'] = analysis
        else:
            print(f"Analysis of {args.analyze_file}:")
            for key, value in analysis.items():
                print(f"  {key}: {value}")
    
    elif args.analyze_project:
        analysis = editor.analyze_project()
        if args.json:
            results['project_analysis'] = analysis
        else:
            print(f"Project analysis for {project_root}:")
            print(f"  Total files: {analysis['total_files']}")
            print(f"  Total size: {analysis['total_size']} bytes")
            print(f"  Languages: {analysis['by_language']}")
            print(f"  Under /app/data/: {analysis.get('is_under_app_data', False)}")
    
    elif args.create_structure:
        result = editor.create_project_structure()
        if args.json:
            results['structure_creation'] = result
        else:
            if result['success']:
                print(f"Created project structure in {project_root}:")
                for item in result['created']:
                    print(f"  • {item}")
            else:
                print(f"Error creating structure", file=sys.stderr)
    
    elif args.workflow and args.task:
        if args.workflow == 'architect':
            result = workflow_manager.architect_workflow(args.task)
        elif args.workflow == 'code':
            result = workflow_manager.code_workflow(args.task, args.target)
        elif args.workflow == 'debug':
            result = workflow_manager.debug_workflow(args.task, args.target)
        elif args.workflow == 'refactor':
            result = workflow_manager.refactor_workflow(args.task, args.target)
        else:
            print(f"Unknown workflow: {args.workflow}", file=sys.stderr)
            return
        
        if args.json:
            results['workflow'] = result
        else:
            print(f"Workflow: {result['mode']}")
            print(f"Project: {result.get('project_root', 'Not specified')}")
            print(f"Task: {result['task']}")
            if 'steps' in result:
                print("Steps:")
                for step in result['steps']:
                    print(f"  {step}")
    
    else:
        parser.print_help()
        return
    
    # Output JSON if requested
    if args.json and results:
        print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
