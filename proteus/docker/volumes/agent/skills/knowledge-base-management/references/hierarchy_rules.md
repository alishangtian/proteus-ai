# Hierarchy Rules and Directory Naming Conventions

This document describes the rules for automatic hierarchy creation and directory naming in the Knowledge Base Management system.

## Automatic Hierarchy Creation

### Based on Document Content

The system analyzes document content to create hierarchical structures:

1. **Title Analysis**: Extract main topics from document titles
2. **Heading Structure**: Use document headings (H1, H2, H3) for hierarchy levels
3. **Content Clustering**: Group similar documents together
4. **Metadata Analysis**: Use author, date, subject metadata

### Example: Research Paper Hierarchy
```
Research/
├── Artificial Intelligence/
│   ├── Machine Learning/
│   │   ├── Deep Learning/
│   │   │   ├── Convolutional Neural Networks/
│   │   │   └── Transformers/
│   │   └── Reinforcement Learning/
│   └── Natural Language Processing/
└── Computer Science/
    ├── Algorithms/
    └── Data Structures/
```

## Directory Naming Rules

### General Rules
1. **Valid Characters**: Letters, numbers, spaces, hyphens, underscores
2. **Length Limit**: Maximum 255 characters per directory name
3. **Case Sensitivity**: Preserve original case but treat as case-insensitive for search
4. **Special Characters**: Avoid: `\ / : * ? " < > |`

### Automatic Name Cleaning
The system automatically cleans directory names:
- Replace special characters with hyphens
- Remove extra whitespace
- Convert to lowercase for storage (optional)
- Ensure uniqueness within parent directory

### Reserved Names
Avoid these directory names:
- `indexes`, `metadata`, `documents`, `config`, `system`
- Names starting with `.` or `_`

## Multi-level Directory Structure

### Depth Management
- **Maximum Depth**: Configurable (default: 5 levels)
- **Minimum Depth**: At least 1 level (root category)
- **Optimal Depth**: 3-4 levels for most use cases

### Path Examples
```
# Good structure
Research/Computer_Vision/Object_Detection/2024

# Too deep
Research/AI/ML/DL/CNN/Architectures/ResNet/Variants/2024

# Too shallow
Research
```

## Automatic Categorization Rules

### Based on Keywords
```yaml
category_rules:
  research:
    keywords: ["paper", "study", "research", "thesis", "dissertation"]
    subcategories: ["AI", "Biology", "Physics", "Chemistry"]
  
  reports:
    keywords: ["report", "analysis", "audit", "review", "assessment"]
    
  documentation:
    keywords: ["manual", "guide", "tutorial", "docs", "documentation"]
    
  meetings:
    keywords: ["minutes", "agenda", "meeting", "notes", "summary"]
```

### Based on File Metadata
- **Author**: Group by author for personal document collections
- **Date**: Year/Month hierarchical organization
- **Project**: Group by project name or ID
- **Department**: Organizational structure

## Manual Hierarchy Overrides

Users can manually adjust hierarchy:

1. **Move Documents**: Change category assignment
2. **Create Custom Categories**: Define own hierarchy
3. **Merge Categories**: Combine similar categories
4. **Split Categories**: Divide large categories

## Configuration Options

### Hierarchy Configuration in config.yaml
```yaml
hierarchy:
  max_depth: 5
  auto_create: true
  naming_convention: "snake_case"  # or "kebab-case", "camelCase", "PascalCase"
  reserved_names:
    - "indexes"
    - "metadata"
    - "system"
  default_categories:
    - "Uncategorized"
    - "General"
    - "Archive"
```

### Automatic Splitting Rules
```yaml
splitting:
  min_section_length: 500  # characters
  max_sections_per_document: 20
  heading_levels:
    h1: true   # Major sections
    h2: true   # Subsections
    h3: false  # Too detailed
  fallback_method: "chunk_by_length"  # or "chunk_by_paragraph"
```

## Best Practices

### For Consistent Hierarchy
1. **Define Naming Convention Early**: Choose and stick to a convention
2. **Limit Category Proliferation**: Avoid too many top-level categories
3. **Use Descriptive Names**: Clear, meaningful directory names
4. **Maintain Balance**: Even distribution across categories
5. **Regular Review**: Periodically review and reorganize

### For Automatic Processing
1. **Pre-process Documents**: Ensure consistent headings and structure
2. **Test Categorization**: Validate automatic categorization results
3. **Provide Training Data**: For ML-based categorization
4. **Monitor Performance**: Track categorization accuracy

## Troubleshooting

### Common Issues and Solutions

**Issue**: Too many top-level categories
**Solution**: Increase categorization threshold, add consolidation rules

**Issue**: Documents in wrong categories
**Solution**: Review keyword rules, add negative keywords, provide manual corrections

**Issue**: Hierarchy too deep
**Solution**: Reduce max_depth, merge similar subcategories

**Issue**: Inconsistent naming
**Solution**: Enable automatic name cleaning, define naming convention

## Custom Rules Implementation

You can implement custom hierarchy rules by modifying the `kb_manager.py` file:

```python
class CustomHierarchyRules:
    def categorize_document(self, document_content, metadata):
        # Implement custom categorization logic
        pass
    
    def create_directory_structure(self, category, subcategories):
        # Implement custom directory creation
        pass
```

## Performance Considerations

- Deep hierarchies may impact search performance
- Many small directories can cause filesystem overhead
- Balance between organization depth and performance
- Consider using symbolic links for cross-categorization
