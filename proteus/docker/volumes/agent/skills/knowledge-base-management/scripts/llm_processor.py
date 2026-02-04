"""
LLM Processor for document analysis using DeepSeek API.
"""

import os
import json
import re
from typing import Dict, List, Optional, Any
import requests
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class LLMProcessor:
    """Processor for document analysis using DeepSeek LLM."""
    
    def __init__(self):
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        self.model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        self.base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY not found in environment variables")
    
    def call_llm(self, prompt: str, system_prompt: Optional[str] = None, 
                 temperature: float = 0.1, max_tokens: int = 2000) -> str:
        """
        Call DeepSeek LLM API.
        
        Args:
            prompt: User prompt
            system_prompt: System prompt (optional)
            temperature: Temperature for generation
            max_tokens: Maximum tokens to generate
            
        Returns:
            Generated text
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        data = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"].strip()
            else:
                raise Exception(f"API call failed: {response.status_code} - {response.text}")
                
        except Exception as e:
            raise Exception(f"LLM call failed: {str(e)}")
    
    def generate_meaningful_name(self, content: str, filename: str, 
                                max_length: int = 50) -> str:
        """
        Generate a meaningful directory name based on document content.
        
        Args:
            content: Document content
            filename: Original filename
            max_length: Maximum length for directory name
            
        Returns:
            Meaningful directory name
        """
        system_prompt = """You are a helpful assistant that generates meaningful, descriptive names for document directories. 
        The name should be concise, informative, and reflect the main topic or purpose of the document.
        Use lowercase letters, hyphens for spaces, and avoid special characters."""
        
        prompt = f"""Based on the following document information, generate a meaningful directory name."

Original filename: {filename}
Document content (first 2000 characters): {content[:2000]}

Generate a directory name that:
1. Reflects the main topic or purpose
2. Is concise (max {max_length} characters)
3. Uses lowercase letters and hyphens (no spaces)
4. Avoids special characters
5. Is descriptive but not too long

Return ONLY the directory name, nothing else.
Example format: "research-paper-attention-mechanisms" or "project-report-q4-2024"
"""
        
        try:
            name = self.call_llm(prompt, system_prompt, temperature=0.3, max_tokens=100)
            
            # 清理名称
            name = name.strip()
            name = name.lower()
            
            # 替换空格和特殊字符为连字符
            name = re.sub(r'[\s_]+', '-', name)
            name = re.sub(r'[^a-z0-9\-]', '', name)
            
            # 移除开头和结尾的连字符
            name = name.strip('-')
            
            # 截断到最大长度
            if len(name) > max_length:
                # 尝试在单词边界处截断
                if '-' in name:
                    parts = name.split('-')
                    truncated = []
                    current_length = 0
                    for part in parts:
                        if current_length + len(part) + 1 <= max_length:
                            truncated.append(part)
                            current_length += len(part) + 1
                        else:
                            break
                    name = '-'.join(truncated)
                else:
                    name = name[:max_length]
            
            # 确保名称不为空
            if not name:
                # 使用文件名作为后备
                name = re.sub(r'[^a-z0-9\-]', '', filename.lower().replace(' ', '-').replace('.', '-'))
                name = name[:max_length] if len(name) > max_length else name
            
            return name
            
        except Exception as e:
            print(f"Failed to generate meaningful name with LLM: {e}")
            # 使用简化版本作为后备
            return self._generate_simple_name(filename, max_length)
    
    def _generate_simple_name(self, filename: str, max_length: int = 50) -> str:
        """Generate a simple name from filename."""
        # 移除扩展名
        name = os.path.splitext(filename)[0]
        
        # 转换为小写，用连字符替换空格和特殊字符
        name = name.lower()
        name = re.sub(r'[\s_]+', '-', name)
        name = re.sub(r'[^a-z0-9\-]', '', name)
        name = name.strip('-')
        
        # 截断到最大长度
        if len(name) > max_length:
            name = name[:max_length]
        
        return name if name else "document"
    
    def extract_summary(self, content: str, max_length: int = 300) -> str:
        """
        Extract summary from document content using LLM.
        
        Args:
            content: Document content
            max_length: Maximum summary length
            
        Returns:
            Document summary
        """
        system_prompt = """You are a helpful assistant that extracts concise summaries from documents.
        Your summaries should capture the main points, key findings, and purpose of the document."""
        
        prompt = f"""Please provide a concise summary of the following document content."

Document content (first 4000 characters): {content[:4000]}

Requirements:
1. Summary should be {max_length} characters or less
2. Capture the main topic and key points
3. Be clear and informative
4. Use complete sentences

Summary:"""
        
        try:
            summary = self.call_llm(prompt, system_prompt, temperature=0.2, max_tokens=500)
            return summary.strip()
            
        except Exception as e:
            print(f"Failed to extract summary with LLM: {e}")
            # 使用简单摘要作为后备
            return self._extract_simple_summary(content, max_length)
    
    def _extract_simple_summary(self, content: str, max_length: int = 300) -> str:
        """Extract simple summary from content."""
        # 取前几个句子作为摘要
        sentences = re.split(r'[.!?]+', content)
        summary_parts = []
        current_length = 0
        
        for sentence in sentences:
            sentence = sentence.strip()
            if sentence:
                if current_length + len(sentence) + 1 <= max_length:
                    summary_parts.append(sentence)
                    current_length += len(sentence) + 1
                else:
                    break
        
        summary = '. '.join(summary_parts)
        if summary and not summary.endswith('.'):
            summary += '.'
        
        return summary[:max_length]
    
    def categorize_document(self, content: str, filename: str, 
                           existing_categories: List[str] = None) -> str:
        """
        Categorize document using LLM.
        
        Args:
            content: Document content
            filename: Original filename
            existing_categories: List of existing categories (optional)
            
        Returns:
            Category path (e.g., "Research/AI/Machine-Learning")
        """
        system_prompt = """You are a helpful assistant that categorizes documents into hierarchical categories.
        Categories should be organized in a logical hierarchy (e.g., Research/AI/Machine-Learning).
        Use broad categories at the top level, becoming more specific at lower levels."""
        
        categories_hint = ""
        if existing_categories:
            categories_hint = f"Existing categories in the knowledge base: {", ".join(existing_categories[:10])}"
            if len(existing_categories) > 10:
                categories_hint += f" (and {len(existing_categories)-10} more)"
        
        prompt = f"""Categorize the following document into a hierarchical category structure."

Original filename: {filename}
Document content (first 2000 characters): {content[:2000]}
{categories_hint}

Please provide:
1. A hierarchical category path (2-3 levels recommended)
2. Each level should be descriptive and concise
3. Use forward slashes to separate levels (e.g., "Research/AI/Machine-Learning")
4. Use hyphens for multi-word category names
5. If an existing category is appropriate, use it

Return ONLY the category path, nothing else.
Example: "Research/Computer-Science/Algorithms" or "Business/Reports/Q4-2023"
"""
        
        try:
            category_path = self.call_llm(prompt, system_prompt, temperature=0.2, max_tokens=100)
            
            # 清理分类路径
            category_path = category_path.strip()
            
            # 确保使用正确的分隔符
            category_path = category_path.replace('\\', '/')
            category_path = category_path.replace('\\', '/')
            # 清理每一级
            levels = category_path.split('/')
            cleaned_levels = []
            for level in levels:
                level = level.strip()
                if level:
                    # 转换为小写，用连字符替换空格
                    level = level.lower()
                    level = re.sub(r'[\s_]+', '-', level)
                    level = re.sub(r'[^a-z0-9\-]', '', level)
                    level = level.strip('-')
                    if level:
                        cleaned_levels.append(level)
            
            # 重新组合
            if cleaned_levels:
                return '/'.join(cleaned_levels)
            else:
                return "uncategorized/general"
                
        except Exception as e:
            print(f"Failed to categorize with LLM: {e}")
            return "uncategorized/general"
    
    def split_into_sections(self, content: str, title: str = "") -> Dict[str, str]:
        """
        Split document into logical sections using LLM.
        
        Args:
            content: Document content
            title: Document title
            
        Returns:
            Dictionary with section_path -> content
        """
        system_prompt = """You are a helpful assistant that analyzes document structure and splits it into logical sections.
        Identify natural breaks, topics, or chapters in the document."""
        
        prompt = f"""Analyze the following document and split it into logical sections."

Document title: {title}
Document content (first 6000 characters): {content[:6000]}

Please provide a JSON object with the following structure:
{{
  "sections": [
    {{
      "title": "Section title",
      "content": "Section content",
      "summary": "Brief section summary"
    }}
  ]
}}

Requirements:
1. Identify 3-8 logical sections
2. Each section should have a descriptive title
3. Include the actual content for each section
4. Provide a brief summary for each section
5. Make sure sections cover the entire provided content

Return ONLY the JSON object, nothing else.
"""
        
        try:
            response = self.call_llm(prompt, system_prompt, temperature=0.1, max_tokens=4000)
            
            # 尝试解析JSON
            try:
                result = json.loads(response)
                sections = result.get("sections", [])
                
                # 转换为路径格式
                section_dict = {}
                for i, section in enumerate(sections):
                    section_title = section.get("title", f"section-{i+1}")
                    section_content = section.get("content", "")
                    section_summary = section.get("summary", "")
                    
                    # 创建路径
                    path_title = re.sub(r'[^a-z0-9\-]', '', section_title.lower().replace(' ', '-'))
                    if not path_title:
                        path_title = f"section-{i+1}"
                    
                    section_path = f"/{path_title}"
                    section_dict[section_path] = {
                        "content": section_content,
                        "summary": section_summary,
                        "title": section_title
                    }
                
                return section_dict
                
            except json.JSONDecodeError:
                print(f"Failed to parse LLM response as JSON: {response[:200]}")
                return self._split_into_simple_sections(content, title)
                
        except Exception as e:
            print(f"Failed to split sections with LLM: {e}")
            return self._split_into_simple_sections(content, title)
    
    def _split_into_simple_sections(self, content: str, title: str = "") -> Dict[str, str]:
        """Simple section splitting as fallback."""
        sections = {}
        
        # 简单按段落分割
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
        
        if len(paragraphs) <= 1:
            sections["/document"] = {
                "content": content,
                "summary": content[:200] + "..." if len(content) > 200 else content,
                "title": title or "Document"
            }
        else:
            # 将段落分组为章节
            chunk_size = max(1, len(paragraphs) // 5)  # 目标5个章节
            for i in range(0, len(paragraphs), chunk_size):
                section_num = i // chunk_size + 1
                section_content = '\n\n'.join(paragraphs[i:i+chunk_size])
                sections[f"/section-{section_num}"] = {
                    "content": section_content,
                    "summary": section_content[:150] + "..." if len(section_content) > 150 else section_content,
                    "title": f"Section {section_num}"
                }
        
        return sections

# 全局实例
_llm_processor = None

def get_llm_processor() -> LLMProcessor:
    """Get or create LLM processor instance."""
    global _llm_processor
    if _llm_processor is None:
        _llm_processor = LLMProcessor()
    return _llm_processor
