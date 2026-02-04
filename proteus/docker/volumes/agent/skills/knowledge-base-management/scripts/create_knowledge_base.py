"""
Create a new knowledge base with enhanced features.
"""

import argparse
import json
import os
import sys

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from kb_manager import KnowledgeBaseManager
    KB_MANAGER_AVAILABLE = True
except ImportError as e:
    print(f"Warning: kb_manager module not found: {e}")
    KB_MANAGER_AVAILABLE = False
    
    # Define a simple stub
    class KnowledgeBaseManager:
        def __init__(self, root_path):
            self.root_path = root_path
        
        def create_knowledge_base(self, name, config=None):
            kb_path = os.path.join(self.root_path, name)
            os.makedirs(kb_path, exist_ok=True)
            return {"name": name, "path": kb_path, "status": "created"}

def load_env_config():
    """Load configuration from environment or default."""
    config = {
        "llm_enabled": True,
        "meaningful_names": True,
        "auto_categorize": True,
        "default_categories": ["research", "reports", "documentation", "meetings"]
    }
    
    # Check for .env file
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if os.path.exists(env_path):
        print(f"Found .env file at: {env_path}")
        try:
            from dotenv import load_dotenv
            load_dotenv(env_path)
            
            # Update config based on env vars
            import os as os_module
            if os_module.getenv("LLM_ENABLED", "true").lower() == "false":
                config["llm_enabled"] = False
            if os_module.getenv("MEANINGFUL_NAMES", "true").lower() == "false":
                config["meaningful_names"] = False
                
        except ImportError:
            print("dotenv not available, using default config")
    
    return config

def main():
    parser = argparse.ArgumentParser(description="Create a new knowledge base with enhanced features")
    parser.add_argument("--name", required=True, help="Knowledge base name")
    parser.add_argument("--root", default="/app/data/knowledge_bases", 
                       help="Root directory for knowledge bases")
    parser.add_argument("--config", help="Path to config JSON file")
    parser.add_argument("--llm", choices=["enable", "disable"], default="enable",
                       help="Enable or disable LLM features")
    parser.add_argument("--meaningful-names", choices=["enable", "disable"], default="enable",
                       help="Enable or disable meaningful directory names")
    
    args = parser.parse_args()
    
    # Load config from file if provided
    file_config = None
    if args.config and os.path.exists(args.config):
        with open(args.config, 'r', encoding='utf-8') as f:
            file_config = json.load(f)
    
    # Load environment config
    env_config = load_env_config()
    
    # Merge configurations
    config = env_config.copy()
    
    # Apply command line arguments
    config["llm_enabled"] = args.llm == "enable"
    config["meaningful_names"] = args.meaningful_names == "enable"
    
    # Merge file config last (highest priority)
    if file_config:
        config.update(file_config)
    
    print(f"Creating knowledge base: {args.name}")
    print(f"Root directory: {args.root}")
    print(f"LLM enabled: {config['llm_enabled']}")
    print(f"Meaningful names: {config['meaningful_names']}")
    
    if not KB_MANAGER_AVAILABLE:
        print("\nWarning: Using stub implementation - limited functionality")
        print("Install required dependencies for full features:")
        print("  - kb_manager module")
        print("  - llm_processor module")
        print("  - python-dotenv for .env support")
    
    # Create knowledge base
    manager = KnowledgeBaseManager(args.root)
    result = manager.create_knowledge_base(args.name, config)
    
    print("\nKnowledge base created successfully:")
    print(json.dumps(result, indent=2))
    
    # Additional setup instructions
    print("\nNext steps:")
    print("1. Add documents using process_document.py or upload_document function")
    print("2. Configure .env file with DeepSeek API key for LLM features")
    print("3. Use search_knowledge_base.py to search within the knowledge base")

if __name__ == "__main__":
    main()
