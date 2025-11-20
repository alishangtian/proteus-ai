"""Markdown文档标题提取工具"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def extract_title_from_md(content: str) -> str:
    """从Markdown文档内容中提取标题
    
    Args:
        content: Markdown文档内容
        
    Returns:
        提取的标题，如果无法提取则返回默认标题
    """
    if not content or not isinstance(content, str):
        logger.warning("无法从空内容或非字符串内容中提取标题")
        return "未命名文档"
    
    # 清理内容，移除前后空白
    content = content.strip()
    
    if not content:
        return "未命名文档"
    
    # 尝试从第一行提取标题
    first_line = content.split('\n', 1)[0].strip()
    
    # 移除Markdown标题标记
    title = _clean_md_title(first_line)
    
    # 如果清理后标题为空，则尝试其他方式
    if not title:
        title = _extract_title_alternative(content)
    
    # 如果仍然没有标题，使用默认标题
    if not title:
        title = "未命名文档"
    
    # 限制标题长度
    if len(title) > 100:
        title = title[:97] + "..."
    
    logger.debug(f"从内容中提取标题: '{title}'")
    return title


def _clean_md_title(line: str) -> str:
    """清理Markdown标题标记
    
    Args:
        line: 包含Markdown标题标记的行
        
    Returns:
        清理后的标题文本
    """
    # 移除 # 开头的标题标记
    line = re.sub(r'^#+\s*', '', line)
    
    # 移除 ===== 或 ----- 下划线标题
    line = re.sub(r'\s*[=-]+\s*$', '', line)
    
    # 移除可能的HTML标签
    line = re.sub(r'<[^>]+>', '', line)
    
    # 移除Markdown链接 [text](url)
    line = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', line)
    
    # 移除Markdown粗体/斜体标记
    line = re.sub(r'\*\*([^*]+)\*\*', r'\1', line)  # **bold**
    line = re.sub(r'\*([^*]+)\*', r'\1', line)      # *italic*
    line = re.sub(r'__([^_]+)__', r'\1', line)      # __bold__
    line = re.sub(r'_([^_]+)_', r'\1', line)        # _italic_
    
    return line.strip()


def _extract_title_alternative(content: str) -> str:
    """备用的标题提取方法
    
    Args:
        content: Markdown文档内容
        
    Returns:
        提取的标题
    """
    # 方法1: 查找第一个非空行
    lines = content.split('\n')
    for line in lines:
        line = line.strip()
        if line and not line.startswith('#') and not re.match(r'^[=-]+$', line):
            # 取前50个字符作为标题
            return line[:50].strip()
    
    # 方法2: 取内容的前50个字符
    if len(content) > 50:
        return content[:50].strip() + "..."
    else:
        return content.strip() or "未命名文档"


def extract_title_and_content(content: str) -> tuple[str, str]:
    """同时提取标题和清理后的内容
    
    Args:
        content: 原始内容
        
    Returns:
        (标题, 清理后的内容)
    """
    title = extract_title_from_md(content)
    
    # 清理内容：移除第一行标题（如果是Markdown标题格式）
    lines = content.split('\n')
    if lines and lines[0].strip().startswith('#'):
        # 移除第一行标题
        cleaned_content = '\n'.join(lines[1:]).strip()
    else:
        cleaned_content = content.strip()
    
    return title, cleaned_content


# 测试函数
if __name__ == "__main__":
    # 测试用例
    test_cases = [
        "# 这是一个标题\n这是正文内容",
        "## 二级标题\n正文",
        "没有标题标记的内容",
        "标题行\n========\n正文",
        "标题行\n--------\n正文",
        "**粗体标题**\n正文",
        "[链接标题](http://example.com)\n正文",
        "<h1>HTML标题</h1>\n正文",
        "",  # 空内容
        "   ",  # 空白内容
    ]
    
    for i, test_content in enumerate(test_cases):
        title = extract_title_from_md(test_content)
        print(f"测试 {i+1}: '{title}'")