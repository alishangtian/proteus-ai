"""
Manage knowledge base hierarchy.
"""

import argparse
import os
import json

def create_directory_structure(kb_path, path):
    """
    Create directory structure in knowledge base.
    
    Args:
        kb_path: Path to knowledge base
        path: Directory path to create (e.g., "Research/AI/2024")
    """
    full_path = os.path.join(kb_path, "documents", path)
    os.makedirs(full_path, exist_ok=True)
    
    print(f"Created directory: {full_path}")
    return full_path

def list_hierarchy(kb_path, base_path=""):
    """
    List directory hierarchy.
    
    Args:
        kb_path: Path to knowledge base
        base_path: Base path to start from
    """
    start_path = os.path.join(kb_path, "documents", base_path)
    
    if not os.path.exists(start_path):
        print(f"Path not found: {start_path}")
        return {}
    
    hierarchy = {}
    
    for item in os.listdir(start_path):
        item_path = os.path.join(start_path, item)
        if os.path.isdir(item_path):
            relative_path = os.path.join(base_path, item) if base_path else item
            hierarchy[item] = {
                "type": "directory",
                "path": relative_path,
                "subdirectories": list_hierarchy(kb_path, relative_path)
            }
        else:
            hierarchy[item] = {
                "type": "file",
                "path": os.path.join(base_path, item) if base_path else item
            }
    
    return hierarchy

def print_hierarchy_text(hierarchy, indent=0):
    """Print hierarchy in text format."""
    for name, info in hierarchy.items():
        prefix = "  " * indent + "├── "
        if info["type"] == "directory":
            print(f"{prefix}{name}/")
            print_hierarchy_text(info["subdirectories"], indent + 1)
        else:
            print(f"{prefix}{name}")

def main():
    parser = argparse.ArgumentParser(description="Manage knowledge base hierarchy")
    parser.add_argument("--kb-path", required=True, help="Path to knowledge base")
    
    subparsers = parser.add_subparsers(dest="action", required=True, 
                                      help="Action to perform")
    
    # Create parser
    create_parser = subparsers.add_parser("create", help="Create directory")
    create_parser.add_argument("--path", required=True, 
                              help="Directory path to create")
    
    # List parser
    list_parser = subparsers.add_parser("list", help="List hierarchy")
    list_parser.add_argument("--base-path", default="", 
                            help="Base path to start from")
    list_parser.add_argument("--format", choices=["text", "json"], 
                            default="text", help="Output format")
    
    # Move parser (stub)
    move_parser = subparsers.add_parser("move", help="Move directory/file")
    move_parser.add_argument("--from", dest="from_path", required=True,
                            help="Source path")
    move_parser.add_argument("--to", dest="to_path", required=True,
                            help="Destination path")
    
    args = parser.parse_args()
    
    # Check if knowledge base exists
    if not os.path.exists(args.kb_path):
        print(f"Error: Knowledge base not found at {args.kb_path}")
        return
    
    # Perform action
    if args.action == "create":
        result = create_directory_structure(args.kb_path, args.path)
        print(f"Success: Created {result}")
    
    elif args.action == "list":
        hierarchy = list_hierarchy(args.kb_path, args.base_path)
        
        if args.format == "json":
            print(json.dumps(hierarchy, indent=2))
        else:
            print(f"Hierarchy for {args.base_path or 'root'}:")
            print("-" * 50)
            print_hierarchy_text(hierarchy)
    
    elif args.action == "move":
        print(f"Move from {args.from_path} to {args.to_path}")
        print("Note: Move functionality not yet implemented")
    
    else:
        print(f"Unknown action: {args.action}")

if __name__ == "__main__":
    main()
