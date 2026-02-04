#!/usr/bin/env python3
"""
List Projects Script for manus

Scans /app/data/manus/ directory and lists all existing projects.
The model (Claude) will determine similarity based on the project names.

Usage: python3 list-projects.py [current-project-name]
"""

import os
import sys

def list_projects(manus_dir="/app/data/manus"):
    """List all projects in manus directory."""
    if not os.path.exists(manus_dir):
        print(f"Directory does not exist: {manus_dir}")
        return []
    
    projects = []
    for item in os.listdir(manus_dir):
        item_path = os.path.join(manus_dir, item)
        if os.path.isdir(item_path):
            projects.append(item)
    
    return sorted(projects)

def main():
    # Get current project name if provided
    current_project = None
    if len(sys.argv) > 1:
        current_project = sys.argv[1]
    
    print("\n[manus] Listing all projects in /app/data/manus/")
    
    projects = list_projects()
    
    if not projects:
        print("No existing projects found.")
        return 0
    
    print(f"Found {len(projects)} project(s):")
    for i, project in enumerate(projects, 1):
        print(f"  {i}. {project}")
    
    if current_project:
        print(f"\nCurrent project name: '{current_project}'")
        print("\n--- MODEL ANALYSIS REQUIRED ---")
        print("Based on the project names above, determine if any existing")
        print(f"project is similar to '{current_project}' and whether to:")
        print("1. Use an existing project (if relevant)")
        print("2. Create a new project with current name")
        print("3. Create a new project with distinct name")
    else:
        print("\n--- MODEL ANALYSIS REQUIRED ---")
        print("Review the project list above to determine if any existing")
        print("project is relevant to the current task.")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
