# Search Mechanisms and Algorithms

This document describes the search algorithms and hierarchical disclosure mechanisms used in the Knowledge Base Management system.

## Hierarchical Disclosure Search

### Concept
Hierarchical disclosure search allows users to navigate knowledge bases like exploring a tree structure. Instead of returning flat results, it reveals the hierarchical context of matches.

### How It Works
1. **Level-by-Level Navigation**: Start with top-level categories
2. **Progressive Disclosure**: Reveal deeper levels as user drills down
3. **Context Preservation**: Maintain full path context in results
4. **Scope Limitation**: Search within selected hierarchy levels

### Example Flow
```
Search: "neural networks"
→ Level 1: Research/ (5 matches)
   → Level 2: Research/AI/ (5 matches)
      → Level 3: Research/AI/Machine_Learning/ (3 matches)
         → Level 4: Research/AI/Machine_Learning/Deep_Learning/ (3 matches)
```

### Implementation
```python
def hierarchical_search(query, current_path=None, max_depth=3, min_similarity=0.5):
    """
    Search with hierarchical constraints.
    
    Args:
        query: Search query
        current_path: Current directory path (None for root)
        max_depth: Maximum hierarchy depth to search
        min_similarity: Minimum similarity score
    """
    results = []
    
    # Get documents/sections within current path
    candidates = get_candidates_within_path(current_path)
    
    for candidate in candidates:
        # Calculate similarity
        similarity = calculate_similarity(query, candidate)
        
        if similarity >= min_similarity:
            # Apply hierarchical disclosure
            disclosed_path = apply_disclosure(candidate.path, max_depth)
            
            results.append({
                "item": candidate,
                "similarity": similarity,
                "disclosed_path": disclosed_path,
                "full_path": candidate.path
            })
    
    # Group by hierarchy level
    grouped_results = group_by_hierarchy(results, max_depth)
    
    return grouped_results
```

## Search Algorithms

### 1. Vector Search (Semantic Search)
**Technology**: FAISS, Sentence Transformers
**Use Case**: Semantic similarity, concept search

```python
from sentence_transformers import SentenceTransformer
import faiss

class VectorSearch:
    def __init__(self, model_name="all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)
        self.index = faiss.IndexFlatL2(384)  # Dimension for MiniLM
    
    def search(self, query, k=10):
        query_embedding = self.model.encode([query])
        distances, indices = self.index.search(query_embedding, k)
        return indices, distances
```

### 2. Keyword Search
**Technology**: Whoosh, Lucene, or custom inverted index
**Use Case**: Exact term matching, phrase search

### 3. Hybrid Search
**Technology**: Combination of vector and keyword search
**Use Case**: General-purpose search with relevance ranking

```python
def hybrid_search(query, alpha=0.7):
    """
    Combine vector and keyword search results.
    
    Args:
        query: Search query
        alpha: Weight for vector search (1-alpha for keyword)
    """
    vector_results = vector_search(query)
    keyword_results = keyword_search(query)
    
    # Normalize scores
    vector_scores = normalize_scores(vector_results)
    keyword_scores = normalize_scores(keyword_results)
    
    # Combine scores
    combined_scores = {}
    for doc_id in set(vector_scores.keys()) | set(keyword_scores.keys()):
        vector_score = vector_scores.get(doc_id, 0)
        keyword_score = keyword_scores.get(doc_id, 0)
        combined_scores[doc_id] = alpha * vector_score + (1 - alpha) * keyword_score
    
    return sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)
```

### 4. Faceted Search
**Technology**: Elasticsearch-like faceting
**Use Case**: Filtering by metadata (date, author, category)

## Indexing Strategies

### Document Indexing
```python
def index_document(document, level="document"):
    """
    Index a document at multiple levels.
    
    Args:
        document: Document object
        level: Indexing level (document, section, paragraph)
    """
    # Extract content
    content = extract_content(document, level)
    
    # Create embeddings
    embedding = create_embedding(content)
    
    # Update vector index
    vector_index.add(embedding, document.id)
    
    # Update keyword index
    keywords = extract_keywords(content)
    for keyword in keywords:
        keyword_index[keyword].append(document.id)
    
    # Update hierarchy index
    hierarchy_index[document.category].append(document.id)
```

### Hierarchical Indexing
- **Level 0**: Document-level index
- **Level 1**: Section-level index  
- **Level 2**: Paragraph-level index
- **Level 3**: Sentence-level index (optional)

## Relevance Ranking

### Ranking Factors
1. **Content Relevance**: Semantic similarity to query
2. **Hierarchy Level**: Higher-level matches get bonus
3. **Recency**: Newer documents weighted higher
4. **Popularity**: Frequently accessed documents
5. **Authority**: Author reputation or source credibility

### Ranking Formula
```
score = w1 * semantic_similarity + 
        w2 * hierarchy_weight + 
        w3 * recency_score + 
        w4 * popularity_score + 
        w5 * authority_score
```

## Search Configuration

### Configuration in config.yaml
```yaml
search:
  algorithm: "hybrid"  # vector, keyword, hybrid
  vector_model: "all-MiniLM-L6-v2"
  keyword_weights:
    title: 3.0
    summary: 2.0
    content: 1.0
    metadata: 0.5
  hierarchy:
    disclosure_levels: 3
    level_weights: [1.0, 0.8, 0.6, 0.4, 0.2]
  faceted_fields:
    - "category"
    - "author"
    - "year"
    - "document_type"
  performance:
    max_results: 100
    timeout_ms: 5000
    cache_ttl: 300  # seconds
```

## Performance Optimization

### Index Optimization
1. **Sharding**: Split index by category or date range
2. **Compression**: Use quantized vectors for memory efficiency
3. **Caching**: Cache frequent queries and results
4. **Incremental Updates**: Update index incrementally

### Query Optimization
1. **Query Expansion**: Add synonyms and related terms
2. **Spelling Correction**: Auto-correct typos
3. **Stop Word Removal**: Remove common words
4. **Stemming/Lemmatization**: Reduce words to root form

## Advanced Features

### 1. Query Understanding
- Intent detection
- Entity recognition
- Query classification

### 2. Personalization
- User-specific ranking
- Search history analysis
- Preference learning

### 3. Auto-complete
- Prefix-based suggestions
- Popular query suggestions
- Context-aware suggestions

### 4. Spell Checking
- Edit distance calculation
- Phonetic matching
- Context-aware correction

## Monitoring and Analytics

### Search Metrics
- **Query Volume**: Number of searches over time
- **Click-through Rate**: Percentage of clicked results
- **Zero Results Rate**: Percentage of queries with no results
- **Average Position**: Average rank of clicked results
- **Query Length**: Distribution of query lengths

### Performance Metrics
- **Response Time**: Average search latency
- **Index Size**: Memory usage of search indexes
- **Cache Hit Rate**: Percentage of cached results
- **Error Rate**: Percentage of failed searches

## Troubleshooting

### Common Search Issues

**Issue**: No results for valid queries
**Solution**: Check index coverage, verify text extraction quality

**Issue**: Slow search performance
**Solution**: Optimize index, implement caching, reduce index size

**Issue**: Irrelevant results
**Solution**: Adjust ranking weights, improve query understanding

**Issue**: Inconsistent hierarchy disclosure
**Solution**: Verify hierarchy indexing, check depth configuration

## Custom Search Implementation

You can implement custom search algorithms by extending the base classes:

```python
class CustomSearchAlgorithm(BaseSearch):
    def search(self, query, filters=None):
        # Implement custom search logic
        pass
    
    def index_document(self, document):
        # Implement custom indexing
        pass
```

## Integration with External Systems

### Search API
```python
class SearchAPI:
    def search_endpoint(self, query, filters, format="json"):
        """REST API endpoint for search."""
        results = search_engine.search(query, filters)
        return format_results(results, format)
    
    def suggest_endpoint(self, prefix, limit=10):
        """Auto-complete suggestions."""
        return search_engine.suggest(prefix, limit)
```

### Web Interface Integration
- JavaScript search widget
- Real-time search updates
- Faceted navigation interface
