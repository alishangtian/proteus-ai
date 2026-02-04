# Knowledge Base Management Skill

A comprehensive knowledge base management system with DeepSeek LLM integration and meaningful directory naming.

## Features

- **Meaningful Directory Names**: Generates descriptive folder names instead of generic IDs
- **DeepSeek LLM Integration**: Uses AI for summarization, categorization, and section splitting
- **Hierarchical Organization**: Creates logical folder structures based on document content
- **Intelligent Search**: Multi-level disclosure search with context preservation
- **Centralized Management**: All knowledge bases stored in a unified directory structure

## Quick Start

### 1. Installation

```bash
# Clone or copy the skill
cp -r knowledge-base-management /path/to/skills/

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your DeepSeek API key
```

### 2. Create a Knowledge Base

```bash
python scripts/create_knowledge_base.py --name "MyResearch" --llm enable
```

### 3. Process Documents

```bash
# Process with LLM
python scripts/process_document.py --input document.pdf --output-dir ./processed --use-llm

# Process without LLM (fallback)
python scripts/process_document.py --input document.pdf --output-dir ./processed --no-llm
```

### 4. Search Documents

```bash
python scripts/search_knowledge_base.py --kb-path /app/data/knowledge_bases/MyResearch --query "research topic"
```

## Configuration

### Environment Variables (.env)

```env
# DeepSeek API (required for LLM features)
DEEPSEEK_API_KEY=your_api_key_here
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_BASE_URL=https://api.deepseek.com

# Processing Settings
LLM_ENABLED=true
MEANINGFUL_NAMES=true
MAX_FILE_SIZE_MB=50
```

### Knowledge Base Configuration

Each knowledge base has a `config.json` file with settings:
- `llm_enabled`: Enable/disable LLM features
- `meaningful_names`: Use descriptive directory names
- `auto_categorize`: Automatic document categorization
- `max_hierarchy_depth`: Maximum directory depth

## API Usage

```python
from kb_manager import KnowledgeBaseManager

# Initialize manager
manager = KnowledgeBaseManager("/app/data/knowledge_bases")

# Create knowledge base
kb = manager.create_knowledge_base("ResearchLibrary")

# Upload document with meaningful naming
document = kb.upload_document(
    "paper.pdf",
    category="AI Research",
    use_llm=True
)

# Process with LLM
result = kb.process_document(document["id"], use_llm=True)

# Search documents
results = kb.search("neural networks", disclosure_level=2)
```

## Directory Structure

```
knowledge_bases_root/
├── ResearchLibrary/
│   ├── config.json
│   ├── documents/
│   │   ├── research/
│   │   │   ├── artificial-intelligence/
│   │   │   │   ├── attention-is-all-you-need-2017/  # Meaningful name!
│   │   │   │   │   ├── original.pdf
│   │   │   │   │   ├── summary.txt
│   │   │   │   │   └── sections/
│   │   │   │   └── bert-pretraining-transformers/
│   │   └── reports/
│   ├── indexes/
│   └── metadata.db
```

## Troubleshooting

### Common Issues

1. **LLM processing fails**: Check API key in `.env`, verify network connectivity
2. **Meaningful names too generic**: Adjust naming parameters or use LLM for better names
3. **Import errors**: Install required dependencies from `requirements.txt`

### Fallback Mechanisms

The system includes intelligent fallbacks when LLM is unavailable:
- Rule-based categorization using filename patterns
- Simple summarization from first sentences
- Basic section splitting by paragraphs
- Cleaned filenames for directory names

## License

This skill is provided as-is. DeepSeek API usage may be subject to DeepSeek's terms of service.
