# API Usage and Integration Guide

This document provides comprehensive API documentation for the Knowledge Base Management system.

## Quick Start

### Installation
```bash
# Install from local directory
pip install -e /path/to/knowledge-base-management

# Or add to Python path
import sys
sys.path.append('/path/to/knowledge-base-management')
```

### Basic Usage
```python
from kb_manager import KnowledgeBaseManager, create_knowledge_base, search_documents

# Create a knowledge base
kb = create_knowledge_base("MyResearch", root_path="/app/data/knowledge_bases")

# Or use the manager
manager = KnowledgeBaseManager("/app/data/knowledge_bases")
kb = manager.create_knowledge_base("MyResearch")
```

## Core API Reference

### KnowledgeBaseManager Class

#### `__init__(root_path="/app/data/knowledge_bases")`
Initialize manager with root directory.

**Parameters:**
- `root_path`: Root directory for all knowledge bases

**Returns:** KnowledgeBaseManager instance

#### `create_knowledge_base(name, config=None)`
Create a new knowledge base.

**Parameters:**
- `name`: Knowledge base name
- `config`: Optional configuration dictionary

**Returns:** Dictionary with created knowledge base info

**Example:**
```python
config = {
    "description": "AI Research Papers",
    "categories": ["ML", "NLP", "CV"],
    "max_file_size": 10485760  # 10MB
}
kb_info = manager.create_knowledge_base("AI_Research", config)
```

#### `get_knowledge_base(name)`
Get an existing knowledge base.

**Parameters:**
- `name`: Knowledge base name

**Returns:** KnowledgeBase instance or None

#### `list_knowledge_bases()`
List all knowledge bases.

**Returns:** List of knowledge base names

### KnowledgeBase Class

#### `upload_document(file_path, category=None, auto_categorize=True, **kwargs)`
Upload a document to the knowledge base.

**Parameters:**
- `file_path`: Path to document file
- `category`: Document category
- `auto_categorize`: Enable automatic categorization
- `**kwargs`: Additional metadata (title, author, etc.)

**Returns:** Dictionary with document metadata

**Example:**
```python
document = kb.upload_document(
    "research_paper.pdf",
    category="AI/ML",
    title="Attention Is All You Need",
    author="Vaswani et al.",
    year=2017,
    tags=["transformer", "nlp", "attention"]
)
```

#### `process_document(doc_id, force_reprocess=False)`
Process a document: extract text, split sections, generate summaries.

**Parameters:**
- `doc_id`: Document ID
- `force_reprocess`: Force reprocessing even if already processed

**Returns:** Dictionary with processing results

**Example:**
```python
result = kb.process_document("doc_abc123")
print(f"Created {result['sections_count']} sections")
```

#### `search(query, disclosure_level=3, category_filter=None, max_results=20)`
Search documents using hierarchical disclosure.

**Parameters:**
- `query`: Search query
- `disclosure_level`: Hierarchy levels to disclose
- `category_filter`: Filter by category
- `max_results`: Maximum results to return

**Returns:** List of search results

**Example:**
```python
results = kb.search(
    query="neural networks",
    disclosure_level=2,
    category_filter="AI/ML",
    max_results=10
)

for result in results:
    print(f"{result['title']} (score: {result['score']:.2f})")
    print(f"Paths: {', '.join(result['disclosed_paths'])}")
```

#### `get_hierarchy(root_category=None)`
Get hierarchical structure of knowledge base.

**Parameters:**
- `root_category`: Optional root category to start from

**Returns:** Nested dictionary representing hierarchy

**Example:**
```python
hierarchy = kb.get_hierarchy()
import json
print(json.dumps(hierarchy, indent=2))
```

#### `rebuild_indexes(index_types=None)`
Rebuild search indexes.

**Parameters:**
- `index_types`: List of index types to rebuild ("vector", "keyword", "hierarchy")

**Returns:** Dictionary with rebuild results

## Convenience Functions

### `create_knowledge_base(name, root_path="/app/data/knowledge_bases", **kwargs)`
Convenience function to create knowledge base.

```python
from kb_manager import create_knowledge_base

kb_info = create_knowledge_base(
    "MyKB",
    root_path="/app/data/kbs",
    description="My knowledge base",
    auto_index=True
)
```

### `search_documents(query, kb_path, **kwargs)`
Convenience function to search documents.

```python
from kb_manager import search_documents

results = search_documents(
    "machine learning",
    "/app/data/knowledge_bases/MyKB",
    disclosure_level=3,
    max_results=15
)
```

## Command Line Interface

### Knowledge Base Creation
```bash
python scripts/create_knowledge_base.py --name "ResearchLibrary" --root /app/data/kbs
```

### Document Processing
```bash
python scripts/process_document.py --input paper.pdf --output-dir ./processed --category "AI"
```

### Search
```bash
python scripts/search_knowledge_base.py --kb-path /app/data/kbs/ResearchLibrary --query "transformer" --max-results 10
```

### Hierarchy Management
```bash
python scripts/manage_hierarchy.py --kb-path /app/data/kbs/ResearchLibrary --action create --path "AI/NLP/2024"
python scripts/manage_hierarchy.py --kb-path /app/data/kbs/ResearchLibrary --action list --base-path "AI"
```

## REST API (Optional)

If you need a web API, you can use Flask or FastAPI:

```python
from flask import Flask, request, jsonify
from kb_manager import KnowledgeBaseManager

app = Flask(__name__)
manager = KnowledgeBaseManager()

@app.route('/api/knowledge_bases', methods=['POST'])
def create_kb():
    data = request.json
    result = manager.create_knowledge_base(data['name'], data.get('config'))
    return jsonify(result)

@app.route('/api/search', methods=['GET'])
def search():
    kb_name = request.args.get('kb')
    query = request.args.get('q')
    level = int(request.args.get('level', 3))
    
    kb = manager.get_knowledge_base(kb_name)
    if not kb:
        return jsonify({"error": "Knowledge base not found"}), 404
    
    results = kb.search(query, disclosure_level=level)
    return jsonify({"results": results})

if __name__ == '__main__':
    app.run(debug=True)
```

## Python Integration Examples

### Example 1: Batch Document Upload
```python
import os
from kb_manager import KnowledgeBaseManager

manager = KnowledgeBaseManager("/app/data/knowledge_bases")
kb = manager.create_knowledge_base("ResearchPapers")

# Upload all PDFs in a directory
pdf_dir = "/path/to/pdfs"
for filename in os.listdir(pdf_dir):
    if filename.endswith(".pdf"):
        file_path = os.path.join(pdf_dir, filename)
        
        # Extract metadata from filename
        title = filename.replace(".pdf", "").replace("_", " ")
        
        # Upload document
        doc = kb.upload_document(
            file_path,
            category="Research",
            title=title,
            auto_categorize=True
        )
        
        # Process document
        kb.process_document(doc["id"])
        
        print(f"Processed: {filename}")

# Rebuild indexes for better search
kb.rebuild_indexes()
```

### Example 2: Advanced Search with Filtering
```python
from kb_manager import KnowledgeBaseManager

manager = KnowledgeBaseManager()
kb = manager.get_knowledge_base("CompanyDocs")

# Complex search with multiple filters
def advanced_search(query, filters=None):
    # Basic search
    results = kb.search(query, disclosure_level=3, max_results=50)
    
    # Apply custom filters
    if filters:
        filtered_results = []
        for result in results:
            if apply_filters(result, filters):
                filtered_results.append(result)
        results = filtered_results
    
    # Sort by custom criteria
    results.sort(key=lambda x: (
        -x['score'],  # Primary: relevance score
        -len(x['disclosed_paths']),  # Secondary: hierarchy depth
    ))
    
    return results

# Usage
filters = {
    "min_year": 2020,
    "authors": ["John Doe", "Jane Smith"],
    "exclude_categories": ["Archive", "Old"]
}

search_results = advanced_search("project report", filters)
```

### Example 3: Export Knowledge Base Structure
```python
import json
from kb_manager import KnowledgeBaseManager

def export_knowledge_base(kb_name, export_format="json"):
    manager = KnowledgeBaseManager()
    kb = manager.get_knowledge_base(kb_name)
    
    if not kb:
        return None
    
    # Get full hierarchy
    hierarchy = kb.get_hierarchy()
    
    # Get document list
    documents = []
    # (Implementation to get all documents)
    
    export_data = {
        "name": kb_name,
        "hierarchy": hierarchy,
        "document_count": len(documents),
        "documents": documents[:1000]  # Limit for export
    }
    
    if export_format == "json":
        return json.dumps(export_data, indent=2)
    elif export_format == "yaml":
        import yaml
        return yaml.dump(export_data, default_flow_style=False)
    
    return export_data

# Export to JSON
json_export = export_knowledge_base("ResearchLibrary", "json")
with open("knowledge_base_export.json", "w") as f:
    f.write(json_export)
```

## Error Handling

### Common Exceptions
```python
try:
    kb = manager.create_knowledge_base("MyKB")
except ValueError as e:
    print(f"Creation failed: {e}")
except PermissionError as e:
    print(f"Permission denied: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

### Custom Error Classes
```python
class KnowledgeBaseError(Exception):
    """Base exception for knowledge base errors."""
    pass

class DocumentNotFoundError(KnowledgeBaseError):
    """Document not found in knowledge base."""
    pass

class SearchError(KnowledgeBaseError):
    """Search operation failed."""
    pass
```

## Configuration Management

### Loading Configuration
```python
import yaml

def load_config(config_path):
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

config = load_config("kb_config.yaml")
manager = KnowledgeBaseManager(config["root_path"])
```

### Dynamic Configuration
```python
class ConfigManager:
    def __init__(self, kb_path):
        self.kb_path = kb_path
        self.config_path = os.path.join(kb_path, "config.yaml")
    
    def update_config(self, updates):
        # Load existing config
        with open(self.config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Apply updates
        config.update(updates)
        
        # Save updated config
        with open(self.config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        
        return config
```

## Testing

### Unit Tests
```python
import unittest
from kb_manager import KnowledgeBaseManager

class TestKnowledgeBase(unittest.TestCase):
    def setUp(self):
        self.manager = KnowledgeBaseManager("/tmp/test_kbs")
    
    def test_create_kb(self):
        kb_info = self.manager.create_knowledge_base("TestKB")
        self.assertEqual(kb_info["name"], "TestKB")
        self.assertTrue(os.path.exists(kb_info["path"]))
    
    def tearDown(self):
        # Cleanup
        import shutil
        if os.path.exists("/tmp/test_kbs"):
            shutil.rmtree("/tmp/test_kbs")

if __name__ == "__main__":
    unittest.main()
```

### Integration Tests
```python
def test_document_lifecycle():
    """Test complete document lifecycle."""
    manager = KnowledgeBaseManager("/tmp/test_integration")
    kb = manager.create_knowledge_base("IntegrationTest")
    
    # Upload
    doc = kb.upload_document("test.txt", category="Test")
    
    # Process
    process_result = kb.process_document(doc["id"])
    assert process_result["status"] == "success"
    
    # Search
    results = kb.search("test")
    assert len(results) > 0
    
    # Cleanup
    import shutil
    shutil.rmtree("/tmp/test_integration")
```

## Performance Tips

1. **Batch Operations**: Use batch uploads and processing
2. **Index Management**: Regularly rebuild indexes for large changes
3. **Connection Pooling**: Reuse database connections
4. **Caching**: Cache frequent queries and hierarchy data
5. **Asynchronous Processing**: Use async for large operations

## Security Considerations

1. **Input Validation**: Validate all user inputs
2. **Path Sanitization**: Prevent directory traversal attacks
3. **Access Control**: Implement proper authentication/authorization
4. **Data Encryption**: Encrypt sensitive metadata
5. **Audit Logging**: Log all significant operations
