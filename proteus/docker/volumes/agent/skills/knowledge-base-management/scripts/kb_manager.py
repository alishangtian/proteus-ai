"""
Enhanced Knowledge Base Manager with meaningful directory names.
LLM integration is available if llm_processor is installed.
"""

import os
import json
import sqlite3
import shutil
import hashlib
import re
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

class KnowledgeBaseManager:
    """Manager for multiple knowledge bases with meaningful directory names."""
    
    def __init__(self, root_path: str = "/app/data/knowledge_bases"):
        self.root_path = root_path
        os.makedirs(root_path, exist_ok=True)
        
        # Try to import LLM processor
        self.llm_processor = None
        try:
            from llm_processor import get_llm_processor
            self.llm_processor = get_llm_processor()
            print("LLM processor initialized")
        except ImportError:
            print("LLM processor not available, using fallback methods")
    
    def create_knowledge_base(self, name: str, config: Optional[Dict] = None) -> Dict:
        """Create a new knowledge base."""
        kb_path = os.path.join(self.root_path, name)
        
        if os.path.exists(kb_path):
            raise ValueError(f"Knowledge base '{name}' already exists")
        
        # Default config
        default_config = {
            "name": name,
            "created_at": datetime.now().isoformat(),
            "root_path": kb_path,
            "llm_enabled": self.llm_processor is not None,
            "meaningful_names": True
        }
        
        if config:
            default_config.update(config)
        
        # Create directory structure
        os.makedirs(kb_path)
        os.makedirs(os.path.join(kb_path, "documents"))
        os.makedirs(os.path.join(kb_path, "indexes"))
        os.makedirs(os.path.join(kb_path, "metadata"))
        
        # Save config
        config_path = os.path.join(kb_path, "config.json")
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=2)
        
        # Initialize database
        db_path = os.path.join(kb_path, "metadata.db")
        self._init_database(db_path)
        
        print(f"Created knowledge base: {name}")
        print(f"LLM enabled: {default_config['llm_enabled']}")
        print(f"Meaningful names: {default_config['meaningful_names']}")
        
        return {"name": name, "path": kb_path, "config": default_config}
    
    def _init_database(self, db_path: str):
        """Initialize SQLite database."""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("CREATE TABLE IF NOT EXISTS documents (id TEXT PRIMARY KEY, filename TEXT, original_path TEXT, file_type TEXT, category TEXT, meaningful_name TEXT, title TEXT, uploaded_date TEXT, file_size INTEGER, summary TEXT, full_text_path TEXT, processed INTEGER DEFAULT 0, llm_processed INTEGER DEFAULT 0)")
        
        conn.commit()
        conn.close()
    
    def _generate_meaningful_dirname(self, filename: str, content: str = "") -> str:
        """
        Generate meaningful directory name from filename and content.
        
        Args:
            filename: Original filename
            content: Document content (first part)
            
        Returns:
            Meaningful directory name
        """
        import re
        import hashlib
        
        # Remove extension
        name = os.path.splitext(filename)[0]
        
        # Clean the name - more aggressive cleaning
        name = name.lower()
        
        # Remove common prefixes/suffixes
        name = re.sub(r'^(document|doc|file|report|paper|thesis|manual|guide|meeting|minutes)_?', '', name)
        name = re.sub(r'_(document|doc|file|report|paper|thesis|manual|guide|meeting|minutes)$', '', name)
        
        # Replace separators with hyphens
        name = re.sub(r'[\s_\.\-]+', '-', name)
        
        # Remove special characters and numbers at beginning/end
        name = re.sub(r'^[0-9\-]+', '', name)
        name = re.sub(r'[^a-z0-9\-]', '', name)
        name = name.strip('-')
        
        # Extract meaningful words from content if name is too short
        if len(name) < 5 or name in ['', 'untitled', 'new', 'temp']:
            if content and isinstance(content, str):
                # Find longer words that might be meaningful
                words = re.findall(r'\b[a-z]{4,}\b', content[:500].lower())
                
                # Common words to exclude
                exclude_words = {
                    'this', 'that', 'with', 'from', 'have', 'were', 'what', 'when',
                    'which', 'about', 'their', 'there', 'would', 'could', 'should'
                }
                
                meaningful_words = []
                for word in words:
                    if (word not in exclude_words and 
                        word not in meaningful_words and
                        not word.endswith('ing') and
                        not word.endswith('ed')):
                        meaningful_words.append(word)
                        if len(meaningful_words) >= 3:
                            break
                
                if meaningful_words:
                    name = '-'.join(meaningful_words)
        
        # If still not good, try to extract from filename differently
        if not name or len(name) < 3:
            # Try to get words from filename
            filename_no_ext = os.path.splitext(filename)[0]
            words = re.findall(r'[a-z]{3,}', filename_no_ext.lower())
            if words:
                name = '-'.join(words[:3])
        
        # Final fallback - use descriptive name with hash
        if not name or len(name) < 3:
            # Use meaningful prefix based on file type
            ext = os.path.splitext(filename)[1].lower()
            if ext in ['.pdf', '.docx', '.doc']:
                prefix = 'document'
            elif ext in ['.txt', '.md']:
                prefix = 'text'
            elif ext in ['.jpg', '.png', '.gif']:
                prefix = 'image'
            else:
                prefix = 'file'
            
            hash_part = hashlib.md5(filename.encode()).hexdigest()[:6]
            name = f"{prefix}-{hash_part}"
        
        # Ensure uniqueness and length
        name = name[:40]  # Shorter limit for readability
        
        return name
        """
        Generate meaningful directory name from filename and content.
        
        Args:
            filename: Original filename
            content: Document content (first part)
            
        Returns:
            Meaningful directory name
        """
        import re
        import hashlib
        
        # Remove extension
        name = os.path.splitext(filename)[0]
        
        # Clean the name - more aggressive cleaning
        name = name.lower()
        
        # Remove common prefixes/suffixes
        name = re.sub(r'^(document|doc|file|report|paper|thesis|manual|guide|meeting|minutes)_?', '', name)
        name = re.sub(r'_(document|doc|file|report|paper|thesis|manual|guide|meeting|minutes)$', '', name)
        
        # Replace separators with hyphens
        name = re.sub(r'[\s_\.\-]+', '-', name)
        
        # Remove special characters and numbers at beginning/end
        name = re.sub(r'^[0-9\-]+', '', name)
        name = re.sub(r'[^a-z0-9\-]', '', name)
        name = name.strip('-')
        
        # Extract meaningful words from content if name is too short
        if len(name) < 5 or name in ['', 'untitled', 'new', 'temp']:
            if content and isinstance(content, str):
                # Find longer words that might be meaningful
                words = re.findall(r'\b[a-z]{4,}\b', content[:500].lower())
                
                # Common words to exclude
                exclude_words = {
                    'this', 'that', 'with', 'from', 'have', 'were', 'what', 'when',
                    'which', 'about', 'their', 'there', 'would', 'could', 'should'
                }
                
                meaningful_words = []
                for word in words:
                    if (word not in exclude_words and 
                        word not in meaningful_words and
                        not word.endswith('ing') and
                        not word.endswith('ed')):
                        meaningful_words.append(word)
                        if len(meaningful_words) >= 3:
                            break
                
                if meaningful_words:
                    name = '-'.join(meaningful_words)
        
        # If still not good, try to extract from filename differently
        if not name or len(name) < 3:
            # Try to get words from filename
            filename_no_ext = os.path.splitext(filename)[0]
            words = re.findall(r'[a-z]{3,}', filename_no_ext.lower())
            if words:
                name = '-'.join(words[:3])
        
        # Final fallback - use descriptive name with hash
        if not name or len(name) < 3:
            # Use meaningful prefix based on file type
            ext = os.path.splitext(filename)[1].lower()
            if ext in ['.pdf', '.docx', '.doc']:
                prefix = 'document'
            elif ext in ['.txt', '.md']:
                prefix = 'text'
            elif ext in ['.jpg', '.png', '.gif']:
                prefix = 'image'
            else:
                prefix = 'file'
            
            hash_part = hashlib.md5(filename.encode()).hexdigest()[:6]
            name = f"{prefix}-{hash_part}"
        
        # Ensure uniqueness and length
        name = name[:40]  # Shorter limit for readability
        
        return name
        """
        Generate meaningful directory name from filename and content.
        
        Args:
            filename: Original filename
            content: Document content (first part)
            
        Returns:
            Meaningful directory name
        """
        # Remove extension
        name = os.path.splitext(filename)[0]
        
        # Clean the name
        name = name.lower()
        
        # Replace common separators with hyphens
        name = re.sub(r'[\s_\.]+', '-', name)
        
        # Remove special characters
        name = re.sub(r'[^a-z0-9\-]', '', name)
        
        # Remove leading/trailing hyphens
        name = name.strip('-')
        
        # If name is too short or generic, try to improve it
        if len(name) < 3 or name in ['document', 'file', 'doc', 'untitled']:
            # Try to extract words from content
            if content:
                # Find potential title words
                words = re.findall(r'\b[a-z]{3,}\b', content[:200].lower())
                meaningful_words = []
                
                # Common words to exclude
                exclude_words = {'the', 'and', 'for', 'with', 'this', 'that', 'from', 'have', 'were', 'what'}
                
                for word in words:
                    if word not in exclude_words and word not in meaningful_words:
                        meaningful_words.append(word)
                        if len(meaningful_words) >= 2:
                            break
                
                if meaningful_words:
                    name = '-'.join(meaningful_words)
        
        # If still not good, create a descriptive name
        if not name or len(name) < 3:
            # Use part of hash for uniqueness
            hash_part = hashlib.md5(filename.encode()).hexdigest()[:6]
            name = f"document-{hash_part}"
        
        # Truncate if too long
        if len(name) > 50:
            # Try to truncate at word boundary
            if '-' in name:
                parts = name.split('-')
                truncated = []
                current_length = 0
                for part in parts:
                    if current_length + len(part) + 1 <= 50:
                        truncated.append(part)
                        current_length += len(part) + 1
                    else:
                        break
                name = '-'.join(truncated)
            else:
                name = name[:50]
        
        return name
    
    def _extract_title(self, filename: str, content: str = "") -> str:
        """Extract title from filename and content."""
        # Use filename as base
        title = os.path.splitext(filename)[0]
        
        # Replace separators with spaces
        title = re.sub(r'[\-_\.]+', ' ', title)
        
        # Title case
        title = title.title()
        
        # If filename seems generic, try content
        if len(title) < 5 and content:
            # Look for potential title in first line
            first_line = content.split('\n')[0].strip()
            if 10 < len(first_line) < 100:
                title = first_line
        
        return title
    
    def _categorize_document(self, filename: str, content: str = "") -> str:
        """Categorize document based on filename and content."""
        import re
        
        filename_lower = filename.lower()
        content_lower = content[:500].lower() if content else ""
        
        # Check for research papers (more specific)
        research_terms = ['research', 'paper', 'thesis', 'dissertation', 'study', 'journal', 'article', '学术', '论文']
        if any(term in filename_lower for term in research_terms) or            any(term in content_lower for term in ['abstract', 'introduction', 'methodology', 'conclusion']):
            
            # Further categorize research
            if any(term in content_lower for term in ['ai', 'artificial', 'intelligence', 'machine', 'learning', 'neural']):
                return "research/artificial-intelligence"
            elif any(term in content_lower for term in ['computer', 'software', 'algorithm', 'programming']):
                return "research/computer-science"
            elif any(term in content_lower for term in ['business', 'finance', 'economic', 'market']):
                return "research/business"
            else:
                return "research/general"
        
        # Check for reports
        report_terms = ['report', 'analysis', 'audit', 'review', 'assessment', 'evaluation', 'summary']
        if any(term in filename_lower for term in report_terms):
            if any(term in filename_lower for term in ['financial', 'finance', 'revenue', 'profit']):
                return "reports/financial"
            elif any(term in filename_lower for term in ['quarterly', 'annual', 'monthly']):
                return "reports/periodic"
            else:
                return "reports/general"
        
        # Check for documentation
        doc_terms = ['manual', 'guide', 'tutorial', 'documentation', 'instructions', 'howto', 'readme']
        if any(term in filename_lower for term in doc_terms):
            return "documentation/technical"
        
        # Check for meetings
        meeting_terms = ['meeting', 'minutes', 'agenda', 'notes', 'summary', 'memo', '会议', '记录']
        if any(term in filename_lower for term in meeting_terms):
            return "meetings/records"
        
        # Check for projects
        project_terms = ['proposal', 'plan', 'project', 'roadmap', 'timeline', 'schedule']
        if any(term in filename_lower for term in project_terms):
            return "projects/planning"
        
        # Check for presentations
        presentation_terms = ['presentation', 'slides', 'deck', 'ppt', 'keynote']
        if any(term in filename_lower for term in presentation_terms):
            return "presentations"
        
        # Default category based on file extension
        ext = os.path.splitext(filename)[1].lower()
        if ext in ['.pdf', '.docx', '.doc']:
            return "documents/formal"
        elif ext in ['.txt', '.md']:
            return "documents/text"
        elif ext in ['.jpg', '.png', '.gif', '.bmp']:
            return "media/images"
        
        # Final default
        return "uncategorized/general"
        """Categorize document based on filename and content."""
        import re
        
        filename_lower = filename.lower()
        content_lower = content[:500].lower() if content else ""
        
        # Check for research papers (more specific)
        research_terms = ['research', 'paper', 'thesis', 'dissertation', 'study', 'journal', 'article', '学术', '论文']
        if any(term in filename_lower for term in research_terms) or            any(term in content_lower for term in ['abstract', 'introduction', 'methodology', 'conclusion']):
            
            # Further categorize research
            if any(term in content_lower for term in ['ai', 'artificial', 'intelligence', 'machine', 'learning', 'neural']):
                return "research/artificial-intelligence"
            elif any(term in content_lower for term in ['computer', 'software', 'algorithm', 'programming']):
                return "research/computer-science"
            elif any(term in content_lower for term in ['business', 'finance', 'economic', 'market']):
                return "research/business"
            else:
                return "research/general"
        
        # Check for reports
        report_terms = ['report', 'analysis', 'audit', 'review', 'assessment', 'evaluation', 'summary']
        if any(term in filename_lower for term in report_terms):
            if any(term in filename_lower for term in ['financial', 'finance', 'revenue', 'profit']):
                return "reports/financial"
            elif any(term in filename_lower for term in ['quarterly', 'annual', 'monthly']):
                return "reports/periodic"
            else:
                return "reports/general"
        
        # Check for documentation
        doc_terms = ['manual', 'guide', 'tutorial', 'documentation', 'instructions', 'howto', 'readme']
        if any(term in filename_lower for term in doc_terms):
            return "documentation/technical"
        
        # Check for meetings
        meeting_terms = ['meeting', 'minutes', 'agenda', 'notes', 'summary', 'memo', '会议', '记录']
        if any(term in filename_lower for term in meeting_terms):
            return "meetings/records"
        
        # Check for projects
        project_terms = ['proposal', 'plan', 'project', 'roadmap', 'timeline', 'schedule']
        if any(term in filename_lower for term in project_terms):
            return "projects/planning"
        
        # Check for presentations
        presentation_terms = ['presentation', 'slides', 'deck', 'ppt', 'keynote']
        if any(term in filename_lower for term in presentation_terms):
            return "presentations"
        
        # Default category based on file extension
        ext = os.path.splitext(filename)[1].lower()
        if ext in ['.pdf', '.docx', '.doc']:
            return "documents/formal"
        elif ext in ['.txt', '.md']:
            return "documents/text"
        elif ext in ['.jpg', '.png', '.gif', '.bmp']:
            return "media/images"
        
        # Final default
        return "uncategorized/general"