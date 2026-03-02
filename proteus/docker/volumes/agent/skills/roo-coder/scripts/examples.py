#!/usr/bin/env python3
"""
Roo-Coder Examples: Demonstrating proper usage with /app/data/{project_name} work directory.

This script shows how to use Roo-Coder skills with the recommended project structure
where all projects are located in /app/data/{project_name} for proper file persistence.
"""

import os
import sys
import json
import tempfile
import shutil

# Add skill scripts to path
skill_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, skill_dir)

from scripts.code_editor import EnhancedCodeEditor, RooCodeWorkflow, EditMode
from scripts.git_operations import GitOperations
from scripts.config_check import ConfigChecker


def demonstrate_project_setup():
    """Demonstrate setting up a project in /app/data/{project_name}."""
    print("=" * 70)
    print("DEMO 1: Project Setup in /app/data/{project_name}")
    print("=" * 70)
    
    # Create a temporary project directory under /app/data for demonstration
    # In real usage, this would be a permanent directory like /app/data/my-project
    temp_project = tempfile.mkdtemp(prefix="roocoder_demo_", dir="/app/data")
    project_name = os.path.basename(temp_project)
    
    print(f"Project created: {temp_project}")
    print(f"Project name: {project_name}")
    print(f"Full path: {temp_project}")
    print()
    
    # Initialize EnhancedCodeEditor
    print("1. Initializing EnhancedCodeEditor:")
    editor = EnhancedCodeEditor(project_root=temp_project)
    print(f"   Project root: {editor.project_root}")
    print(f"   Is under /app/data: {editor.project_root.startswith('/app/data')}")
    print()
    
    # Create project structure
    print("2. Creating basic project structure:")
    result = editor.create_project_structure()
    if result['success']:
        for item in result['created']:
            print(f"   • {os.path.relpath(item, temp_project)}")
    print()
    
    # Write a sample file
    print("3. Writing sample Python file:")
    sample_code = """
def hello_world():
    print("Hello from Roo-Coder example")
"""
    
    # Write the file
    sample_path = os.path.join(temp_project, "src", "main.py")
    with open(sample_path, "w") as f:
        f.write(sample_code)
    print(f"   Created: {os.path.relpath(sample_path, temp_project)}")
    print()
    
    # End of demonstration
    print("Demo completed successfully!")
    print(f"Project created at: {temp_project}")
    
if __name__ == "__main__":
    demonstrate_project_setup()