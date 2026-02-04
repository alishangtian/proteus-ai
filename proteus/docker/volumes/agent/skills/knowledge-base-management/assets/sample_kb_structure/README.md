# Sample Knowledge Base Structure

This directory shows an example knowledge base structure for reference.

## Directory Layout
```
sample_kb_structure/
├── config.yaml              # Configuration file
├── metadata.db              # SQLite metadata database
├── documents/               # All documents organized by category
│   ├── Research/
│   │   ├── AI/
│   │   │   ├── Machine_Learning/
│   │   │   │   ├── doc_abc123/
│   │   │   │   │   ├── original.pdf
│   │   │   │   │   ├── content.txt
│   │   │   │   │   ├── summary.txt
│   │   │   │   │   ├── metadata.json
│   │   │   │   │   └── sections/
│   │   │   │   │       ├── 01_introduction/
│   │   │   │   │       │   ├── content.txt
│   │   │   │   │       │   └── summary.txt
│   │   │   │   │       └── 02_methodology/
│   │   │   │   │           ├── content.txt
│   │   │   │   │           └── summary.txt
│   │   │   │   └── doc_def456/
│   │   │   │       └── ...
│   │   │   └── Natural_Language_Processing/
│   │   │       └── ...
│   │   └── Biology/
│   │       └── ...
│   ├── Reports/
│   │   └── ...
│   └── Documentation/
│       └── ...
├── indexes/                 # Search indexes
│   ├── vector_index.faiss  # Vector search index
│   ├── keyword_index.json  # Keyword search index
│   └── hierarchy_index.json # Hierarchy index
├── metadata/               # Additional metadata
│   ├── categories.json     # Category definitions
│   ├── authors.json        # Author information
│   └── statistics.json     # Usage statistics
└── temp/                   # Temporary files
    └── uploads/           # Temporary upload directory
```

## File Descriptions

### config.yaml
Main configuration file containing all knowledge base settings.

### metadata.db
SQLite database storing:
- Document metadata
- Section information
- Search history
- User preferences

### documents/
Hierarchical organization of all documents:
- Each document gets its own directory
- Directory name includes document ID
- Subdirectories for sections (if document is split)

### indexes/
Search indexes for fast retrieval:
- **vector_index.faiss**: FAISS vector index for semantic search
- **keyword_index.json**: Inverted index for keyword search
- **hierarchy_index.json**: Index of hierarchical relationships

### metadata/
Additional metadata files:
- **categories.json**: Category definitions and relationships
- **authors.json**: Author information and statistics
- **statistics.json**: Usage statistics and metrics

### temp/
Temporary files for processing:
- **uploads/**: Temporary storage for file uploads
- **processing/**: Files being processed
- **cache/**: Cache files for performance

## Example Document Structure

### metadata.json
```json
{
  "id": "doc_abc123",
  "filename": "attention_is_all_you_need.pdf",
  "title": "Attention Is All You Need",
  "authors": ["Vaswani, A.", "Shazeer, N.", "Parmar, N.", "et al."],
  "year": 2017,
  "category": "Research/AI/Natural_Language_Processing",
  "keywords": ["transformer", "attention", "nlp", "neural networks"],
  "abstract": "The dominant sequence transduction models are based on complex recurrent or convolutional neural networks...",
  "pages": 15,
  "file_size": 1248576,
  "upload_date": "2024-01-15T10:30:00Z",
  "processed_date": "2024-01-15T10:35:00Z",
  "sections": [
    {
      "id": "sec_001",
      "title": "Introduction",
      "path": "Research/AI/NLP/Transformers/Introduction",
      "summary": "Introduction to sequence transduction models...",
      "word_count": 450
    },
    {
      "id": "sec_002",
      "title": "Background",
      "path": "Research/AI/NLP/Transformers/Background",
      "summary": "Background on RNNs, LSTMs, and attention mechanisms...",
      "word_count": 620
    }
  ]
}
```

### summary.txt
```
Title: Attention Is All You Need
Authors: Vaswani, A., Shazeer, N., Parmar, N., et al.
Year: 2017

Summary: This paper introduces the Transformer model architecture, which relies entirely on attention mechanisms without using recurrence or convolution. The Transformer achieves state-of-the-art results on machine translation tasks while being more parallelizable and requiring significantly less time to train.

Key Points:
- Proposes Transformer architecture based on self-attention
- Eliminates recurrence and convolution operations
- Achieves superior translation quality
- Enables more parallelization than RNN-based models
- Introduces multi-head attention mechanism
```

## Best Practices

1. **Consistent Naming**: Use consistent naming conventions for directories
2. **Regular Backups**: Backup the entire knowledge base regularly
3. **Index Maintenance**: Rebuild indexes after significant changes
4. **Metadata Quality**: Ensure high-quality metadata for better search
5. **Directory Depth**: Limit directory depth to 3-5 levels for optimal performance
