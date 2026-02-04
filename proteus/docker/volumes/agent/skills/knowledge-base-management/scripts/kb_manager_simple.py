"""
Simplified KB Manager for testing.
"""

import os
import json
import sqlite3
import hashlib
import re
from datetime import datetime

class KnowledgeBaseManager:
    def __init__(self, root_path="/app/data/knowledge_bases"):
        self.root_path = root_path
        os.makedirs(root_path, exist_ok=True)
    
    def create_knowledge_base(self, name, config=None):
        kb_path = os.path.join(self.root_path, name)
        
        if os.path.exists(kb_path):
            raise ValueError(f"Knowledge base '{name}' already exists")
        
        # Create directories
        os.makedirs(kb_path)
        os.makedirs(os.path.join(kb_path, "documents"))
        
        # Save config
        config_data = {
            "name": name,
            "created_at": datetime.now().isoformat(),
            "root_path": kb_path,
            "meaningful_names": True
        }
        
        config_path = os.path.join(kb_path, "config.json")
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2)
        
        print(f"Created knowledge base: {name}")
        return {"name": name, "path": kb_path}
    
    def _generate_meaningful_dirname(self, filename, content=""):
        """Generate meaningful directory name."""
        # Remove extension
        name = os.path.splitext(filename)[0]
        
        # Clean and format
        name = name.lower()
        name = re.sub(r'[\s_]+', '-', name)
        name = re.sub(r'[^a-z0-9\-]', '', name)
        name = name.strip('-')
        
        # If too short, add hash
        if len(name) < 3:
            name = "doc-" + hashlib.md5(filename.encode()).hexdigest()[:8]
        
        # Truncate
        if len(name) > 50:
            name = name[:50]
        
        return name

if __name__ == "__main__":
    manager = KnowledgeBaseManager()
    result = manager.create_knowledge_base("test_kb")
    print(f"Result: {result}")
    
    # Test meaningful name generation
    test_names = [
        "Research_Paper_2024.pdf",
        "meeting-minutes-march-15.docx",
        "report.txt",
        "document.pdf"
    ]
    
    print("\nMeaningful name generation test:")
    for filename in test_names:
        dirname = manager._generate_meaningful_dirname(filename)
        print(f"  {filename} -> {dirname}")
