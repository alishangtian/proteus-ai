#!/usr/bin/env python3
"""
Roo-Coder: Configuration Check Script

Checks project configuration, dependencies, and setup.

IMPORTANT: For proper file persistence and compatibility, projects should be
located in /app/data/{project_name} directory. This ensures configuration
files persist across sessions and maintain consistency.
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Optional


class ConfigChecker:
    """Check project configuration and dependencies.
    
    Note: Initialize with project_path pointing to /app/data/{project_name}
    for proper file persistence and compatibility with the Proteus skill system.
    """
    
    def __init__(self, project_path: str = None):
        """
        Initialize configuration checker.
        
        Args:
            project_path: Path to project directory. Recommended: /app/data/{project_name}
        """
        self.project_path = project_path or os.getcwd()
        self.issues = []
        self.warnings = []
        self.recommendations = []
        
        # Validate project location
        self._validate_project_location()
    
    def _validate_project_location(self):
        """Validate that project is in appropriate location for persistence."""
        normalized_path = os.path.normpath(self.project_path)
        
        # Check if project is under /app/data (recommended for persistence)
        app_data_path = os.path.normpath("/app/data")
        if not normalized_path.startswith(app_data_path + os.sep) and normalized_path != app_data_path:
            self.warnings.append(f"Project '{self.project_path}' is not under '/app/data/'.")
            self.warnings.append("For file persistence across sessions, use /app/data/{project_name}")
            self.warnings.append("Files outside /app/data may not persist between sessions.")
        else:
            self.recommendations.append(f"Project is properly located under /app/data for persistence")
    
    def check_all(self) -> Dict[str, any]:
        """Run all checks."""
        self.issues.clear()
        self.warnings.clear()
        self.recommendations.clear()
        
        # First validate location
        self._validate_project_location()
        
        checks = [
            self.check_git_setup,
            self.check_project_structure,
            self.check_dependencies,
            self.check_readme,
            self.check_gitignore,
            self.check_license,
            self.check_build_tools
        ]
        
        for check in checks:
            try:
                check()
            except Exception as e:
                self.issues.append(f"Check failed: {check.__name__}: {e}")
        
        return {
            'project_path': self.project_path,
            'is_under_app_data': self.project_path.startswith('/app/data'),
            'issues': self.issues,
            'warnings': self.warnings,
            'recommendations': self.recommendations,
            'summary': {
                'total_issues': len(self.issues),
                'total_warnings': len(self.warnings),
                'total_recommendations': len(self.recommendations)
            }
        }
    
    def check_git_setup(self):
        """Check git repository setup."""
        git_dir = os.path.join(self.project_path, '.git')
        if not os.path.exists(git_dir):
            self.issues.append("Not a git repository")
            return
        
        # Check for remote
        try:
            result = subprocess.run(
                ['git', 'remote', '-v'],
                cwd=self.project_path,
                capture_output=True,
                text=True
            )
            if result.returncode == 0 and result.stdout.strip():
                remotes = result.stdout.count('\n')
                self.recommendations.append(f"Git remotes configured ({remotes} found)")
            else:
                self.warnings.append("No git remotes configured")
        except:
            self.warnings.append("Could not check git remotes")
    
    def check_project_structure(self):
        """Check project structure and organization."""
        expected_dirs = ['src', 'tests', 'docs']
        expected_files = ['README.md', '.gitignore']
        
        for dir_name in expected_dirs:
            dir_path = os.path.join(self.project_path, dir_name)
            if os.path.isdir(dir_path):
                self.recommendations.append(f"Directory found: {dir_name}")
            else:
                self.warnings.append(f"Recommended directory missing: {dir_name}")
        
        for file_name in expected_files:
            file_path = os.path.join(self.project_path, file_name)
            if os.path.isfile(file_path):
                self.recommendations.append(f"File found: {file_name}")
            else:
                if file_name == '.gitignore':
                    self.issues.append(f"Missing: {file_name}")
                else:
                    self.warnings.append(f"Recommended file missing: {file_name}")
    
    def check_dependencies(self):
        """Check dependency management files."""
        dep_files = {
            'python': ['requirements.txt', 'Pipfile', 'pyproject.toml'],
            'node': ['package.json', 'package-lock.json', 'yarn.lock'],
            'java': ['pom.xml', 'build.gradle'],
            'go': ['go.mod'],
            'rust': ['Cargo.toml']
        }
        
        found_files = []
        for lang, files in dep_files.items():
            for file in files:
                if os.path.exists(os.path.join(self.project_path, file)):
                    found_files.append((lang, file))
        
        if found_files:
            languages = set(lang for lang, _ in found_files)
            if len(languages) == 1:
                lang = list(languages)[0]
                self.recommendations.append(f"Dependency files found for {lang}")
            else:
                self.warnings.append(f"Multiple language dependency files: {languages}")
            
            # List found files
            for lang, file in found_files:
                self.recommendations.append(f"  - {file}")
        else:
            self.warnings.append("No dependency management files found")
    
    def check_readme(self):
        """Check README file quality."""
        readme_path = os.path.join(self.project_path, 'README.md')
        if not os.path.exists(readme_path):
            self.issues.append("README.md not found")
            return
        
        try:
            with open(readme_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Basic quality checks
            checks = [
                ("Has title", len(content.strip()) > 0),
                ("Has description", len(content) > 100),
                ("Has installation instructions", 'install' in content.lower() or 'setup' in content.lower()),
                ("Has usage examples", 'usage' in content.lower() or 'example' in content.lower())
            ]
            
            for check_name, check_passed in checks:
                if check_passed:
                    self.recommendations.append(f"README: {check_name}")
                else:
                    self.warnings.append(f"README missing: {check_name}")
            
            # Size check
            if len(content) < 500:
                self.warnings.append("README is very short (< 500 chars)")
            elif len(content) > 5000:
                self.recommendations.append("README is comprehensive")
        
        except Exception as e:
            self.warnings.append(f"Could not read README: {e}")
    
    def check_gitignore(self):
        """Check .gitignore file."""
        gitignore_path = os.path.join(self.project_path, '.gitignore')
        if not os.path.exists(gitignore_path):
            self.issues.append(".gitignore not found")
            return
        
        try:
            with open(gitignore_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check for common patterns
            common_patterns = [
                ('node_modules', 'node.js dependencies'),
                ('.env', 'environment variables'),
                ('__pycache__', 'Python cache'),
                ('*.log', 'log files'),
                ('dist/', 'build output'),
                ('build/', 'build output'),
                ('.DS_Store', 'macOS system file')
            ]
            
            found_patterns = []
            for pattern, description in common_patterns:
                if pattern in content:
                    found_patterns.append(description)
            
            if found_patterns:
                self.recommendations.append(f".gitignore includes: {', '.join(found_patterns)}")
            else:
                self.warnings.append(".gitignore missing common patterns")
            
            # Size check
            lines = content.strip().split('\n')
            non_empty_lines = [line for line in lines if line.strip() and not line.strip().startswith('#')]
            
            if len(non_empty_lines) < 5:
                self.warnings.append(".gitignore is very short")
        
        except Exception as e:
            self.warnings.append(f"Could not read .gitignore: {e}")
    
    def check_license(self):
        """Check for license file."""
        license_files = ['LICENSE', 'LICENSE.txt', 'LICENSE.md']
        
        for license_file in license_files:
            if os.path.exists(os.path.join(self.project_path, license_file)):
                self.recommendations.append(f"License file found: {license_file}")
                return
        
        self.warnings.append("No license file found")
    
    def check_build_tools(self):
        """Check for build/CI tools."""
        ci_files = [
            '.github/workflows/',
            '.gitlab-ci.yml',
            '.travis.yml',
            'Jenkinsfile',
            'azure-pipelines.yml'
        ]
        
        found_ci = []
        for ci_file in ci_files:
            ci_path = os.path.join(self.project_path, ci_file)
            if os.path.exists(ci_path):
                found_ci.append(ci_file)
        
        if found_ci:
            self.recommendations.append(f"CI/CD configuration found: {', '.join(found_ci)}")
        else:
            self.warnings.append("No CI/CD configuration found")
        
        # Check for linters/formatters
        linter_files = [
            '.eslintrc', '.eslintrc.js', '.eslintrc.json',
            '.prettierrc',
            '.flake8', 'pylintrc',
            '.golangci.yml'
        ]
        
        found_linters = []
        for linter_file in linter_files:
            if os.path.exists(os.path.join(self.project_path, linter_file)):
                found_linters.append(linter_file)
        
        if found_linters:
            self.recommendations.append(f"Linter/formatter configuration found: {', '.join(found_linters)}")
        else:
            self.warnings.append("No linter/formatter configuration found")
    
    def create_basic_structure(self):
        """Create basic project structure."""
        created = []
        
        # Create directories
        directories = ['src', 'tests', 'docs', 'data', 'config']
        for directory in directories:
            dir_path = os.path.join(self.project_path, directory)
            os.makedirs(dir_path, exist_ok=True)
            created.append(dir_path)
        
        # Create basic files if they don't exist
        basic_files = {
            'README.md': f'# {os.path.basename(self.project_path)}\n\nProject description.',
            '.gitignore': '# Ignore files\n__pycache__/\n*.pyc\n.env\nnode_modules/\n.DS_Store\n*.log\n',
            'requirements.txt': '# Project dependencies\n' if any(f.endswith('.py') for f in os.listdir(self.project_path)) else '',
        }
        
        for filename, content in basic_files.items():
            filepath = os.path.join(self.project_path, filename)
            if not os.path.exists(filepath):
                with open(filepath, 'w') as f:
                    f.write(content)
                created.append(filepath)
        
        return {
            'success': True,
            'created': created,
            'project_path': self.project_path
        }


def main():
    """Command-line interface for configuration check."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Roo-Coder Configuration Checker',
        epilog='Note: For file persistence, use projects in /app/data/{project_name}'
    )
    
    parser.add_argument('--path', type=str, help='Project path (default: current directory)')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--create-structure', action='store_true', help='Create basic project structure')
    
    args = parser.parse_args()
    
    checker = ConfigChecker(args.path)
    
    if args.create_structure:
        results = checker.create_basic_structure()
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            print(f"Created project structure in: {results['project_path']}")
            for item in results['created']:
                print(f"  • {item}")
    else:
        results = checker.check_all()
        
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            print(f"Configuration Check for: {results['project_path']}")
            print(f"Under /app/data/: {results['is_under_app_data']}")
            print("=" * 60)
            
            if results['issues']:
                print("\n❌ ISSUES:")
                for issue in results['issues']:
                    print(f"  • {issue}")
            
            if results['warnings']:
                print("\n⚠️  WARNINGS:")
                for warning in results['warnings']:
                    print(f"  • {warning}")
            
            if results['recommendations']:
                print("\n✅ RECOMMENDATIONS:")
                for rec in results['recommendations']:
                    print(f"  • {rec}")
            
            print("\n" + "=" * 60)
            summary = results['summary']
            print(f"Summary: {summary['total_issues']} issues, "
                  f"{summary['total_warnings']} warnings, "
                  f"{summary['total_recommendations']} recommendations")


if __name__ == '__main__':
    main()
