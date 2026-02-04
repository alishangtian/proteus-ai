"""
Enhanced Document Processor with LLM integration and meaningful naming.
"""

import os
import sys
import json
import argparse
from datetime import datetime

def process_document(input_path, output_dir, category=None, use_llm=True, config=None):
    """
    Process a single document with optional LLM enhancement.
    
    Args:
        input_path: Path to input document
        output_dir: Output directory
        category: Document category
        use_llm: Use LLM for processing
        config: Additional configuration
        
    Returns:
        Dictionary with processing results
    """
    print(f"Processing document: {input_path}")
    print(f"Output directory: {output_dir}")
    print(f"Category: {category}")
    print(f"Use LLM: {use_llm}")
    
    # Check if file exists
    if not os.path.exists(input_path):
        print(f"Error: File not found: {input_path}")
        return {"success": False, "error": "File not found"}
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Extract basic information
    filename = os.path.basename(input_path)
    file_ext = os.path.splitext(filename)[1].lower().lstrip('.')
    
    # Read content
    try:
        with open(input_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read(5000)  # Read first 5000 chars for processing
    except:
        content = f"Binary file: {filename}"
    
    # Generate meaningful name
    meaningful_name = generate_meaningful_name(filename, content, use_llm)
    
    # Create document directory with meaningful name
    doc_dir = os.path.join(output_dir, meaningful_name)
    os.makedirs(doc_dir, exist_ok=True)
    
    # Copy original file
    dest_path = os.path.join(doc_dir, filename)
    try:
        import shutil
        shutil.copy2(input_path, dest_path)
        print(f"Copied original to: {dest_path}")
    except Exception as e:
        print(f"Error copying file: {e}")
        return {"success": False, "error": f"Copy failed: {e}"}
    
    # Save content
    content_path = os.path.join(doc_dir, "content.txt")
    with open(content_path, 'w', encoding='utf-8') as f:
        f.write(content if isinstance(content, str) else str(content))
    
    # Generate summary
    summary = generate_summary(content, use_llm)
    
    # Save summary
    summary_path = os.path.join(doc_dir, "summary.txt")
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write(summary)
    
    # Split into sections
    sections = split_into_sections(content, filename, use_llm)
    
    # Save sections
    sections_dir = os.path.join(doc_dir, "sections")
    os.makedirs(sections_dir, exist_ok=True)
    
    for section_name, section_data in sections.items():
        section_path = os.path.join(sections_dir, section_name)
        os.makedirs(section_path, exist_ok=True)
        
        # Save section content
        with open(os.path.join(section_path, "content.txt"), 'w', encoding='utf-8') as f:
            f.write(section_data.get("content", ""))
        
        # Save section summary
        with open(os.path.join(section_path, "summary.txt"), 'w', encoding='utf-8') as f:
            f.write(section_data.get("summary", ""))
    
    # Create metadata
    metadata = {
        "filename": filename,
        "original_path": input_path,
        "file_type": file_ext,
        "category": category or "uncategorized",
        "meaningful_name": meaningful_name,
        "processed_date": datetime.now().isoformat(),
        "use_llm": use_llm,
        "summary_length": len(summary),
        "sections_count": len(sections),
        "sections": list(sections.keys())
    }
    
    # Save metadata
    metadata_path = os.path.join(doc_dir, "metadata.json")
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    
    print(f"Successfully processed document")
    print(f"  Meaningful name: {meaningful_name}")
    print(f"  Summary: {summary[:100]}..." if len(summary) > 100 else f"  Summary: {summary}")
    print(f"  Sections: {len(sections)}")
    
    return {
        "success": True,
        "meaningful_name": meaningful_name,
        "doc_dir": doc_dir,
        "metadata": metadata
    }

def generate_meaningful_name(filename, content, use_llm=True):
    """Generate meaningful directory name."""
    import re
    import hashlib
    
    if use_llm:
        try:
            from llm_processor import get_llm_processor
            llm = get_llm_processor()
            name = llm.generate_meaningful_name(content, filename, max_length=50)
            print(f"LLM generated name: {name}")
            return name
        except Exception as e:
            print(f"LLM name generation failed: {e}")
            # Fall through to non-LLM method
    
    # Non-LLM method
    name = os.path.splitext(filename)[0]
    name = name.lower()
    name = re.sub(r'[\s_\.]+', '-', name)
    name = re.sub(r'[^a-z0-9\-]', '', name)
    name = name.strip('-')
    
    # If name is too short or generic
    if len(name) < 3 or name in ['document', 'file', 'doc', 'untitled']:
        # Try to extract from content
        if content and isinstance(content, str):
            words = re.findall(r'\b[a-z]{3,}\b', content[:200].lower())
            exclude = {'the', 'and', 'for', 'with', 'this', 'that'}
            meaningful = [w for w in words if w not in exclude]
            if len(meaningful) >= 2:
                name = '-'.join(meaningful[:2])
    
    # Final fallback
    if not name or len(name) < 3:
        hash_part = hashlib.md5(filename.encode()).hexdigest()[:6]
        name = f"doc-{hash_part}"
    
    # Truncate
    if len(name) > 50:
        name = name[:50]
    
    return name

def generate_summary(content, use_llm=True):
    """Generate document summary."""
    if use_llm:
        try:
            from llm_processor import get_llm_processor
            llm = get_llm_processor()
            summary = llm.extract_summary(content, max_length=300)
            print(f"LLM generated summary ({len(summary)} chars)")
            return summary
        except Exception as e:
            print(f"LLM summary generation failed: {e}")
            # Fall through to non-LLM method
    
    # Non-LLM method
    if not content or not isinstance(content, str):
        return "No summary available."
    
    # Take first few sentences
    import re
    sentences = re.split(r'[.!?]+', content)
    summary_parts = []
    total_length = 0
    
    for sentence in sentences:
        sentence = sentence.strip()
        if sentence and len(sentence) > 20:
            if total_length + len(sentence) + 1 <= 300:
                summary_parts.append(sentence)
                total_length += len(sentence) + 1
            else:
                break
    
    summary = '. '.join(summary_parts)
    if summary and not summary.endswith('.'):
        summary += '.'
    
    return summary[:300]

def split_into_sections(content, title="", use_llm=True):
    """Split document into sections."""
    if use_llm:
        try:
            from llm_processor import get_llm_processor
            llm = get_llm_processor()
            sections = llm.split_into_sections(content, title)
            print(f"LLM split into {len(sections)} sections")
            return sections
        except Exception as e:
            print(f"LLM section splitting failed: {e}")
            # Fall through to non-LLM method
    
    # Non-LLM method
    sections = {}
    
    if not content or not isinstance(content, str):
        sections["/document"] = {
            "content": content or "",
            "summary": "No content",
            "title": title or "Document"
        }
        return sections
    
    # Simple paragraph-based splitting
    paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
    
    if len(paragraphs) <= 1:
        sections["/document"] = {
            "content": content,
            "summary": content[:200] + "..." if len(content) > 200 else content,
            "title": title or "Document"
        }
    else:
        # Group paragraphs into sections
        target_sections = min(5, max(2, len(paragraphs) // 3))
        chunk_size = max(1, len(paragraphs) // target_sections)
        
        for i in range(0, len(paragraphs), chunk_size):
            section_num = i // chunk_size + 1
            section_content = '\n\n'.join(paragraphs[i:i+chunk_size])
            
            # Create section title
            first_words = ' '.join(section_content.split()[:5])
            section_title = f"Section {section_num}: {first_words}..."
            
            sections[f"/section-{section_num}"] = {
                "content": section_content,
                "summary": section_content[:150] + "..." if len(section_content) > 150 else section_content,
                "title": section_title
            }
    
    return sections

def main():
    parser = argparse.ArgumentParser(description="Process documents with LLM enhancement")
    parser.add_argument("--input", required=True, help="Input document file")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    parser.add_argument("--category", help="Document category")
    parser.add_argument("--use-llm", action="store_true", default=True, 
                       help="Use LLM for processing (default: True)")
    parser.add_argument("--no-llm", dest="use_llm", action="store_false",
                       help="Disable LLM processing")
    parser.add_argument("--config", help="Path to config JSON file")
    
    args = parser.parse_args()
    
    # Load config if provided
    config = None
    if args.config and os.path.exists(args.config):
        with open(args.config, 'r', encoding='utf-8') as f:
            config = json.load(f)
    
    # Process document
    result = process_document(
        args.input,
        args.output_dir,
        category=args.category,
        use_llm=args.use_llm,
        config=config
    )
    
    # Print result
    if result.get("success"):
        print("\nProcessing completed successfully!")
        print(json.dumps(result.get("metadata", {}), indent=2))
    else:
        print(f"\nProcessing failed: {result.get('error', 'Unknown error')}")
        sys.exit(1)

if __name__ == "__main__":
    main()
