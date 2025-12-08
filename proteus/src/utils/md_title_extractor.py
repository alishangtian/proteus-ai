import re

def extract_title_from_md(md_content: str) -> str:
    """
    从 Markdown 内容中提取第一个一级标题。
    如果不存在一级标题，则返回空字符串。
    """
    if not md_content:
        return ""
    
    # 匹配 Markdown 的一级标题 (以 # 开头，后面跟着一个空格，然后是标题内容)
    match = re.search(r"^#\s*(.+)", md_content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return ""

def remove_title_from_content(md_content: str) -> str:
    """
    从 Markdown 内容中移除第一个一级标题行。
    """
    if not md_content:
        return ""
    
    # 找到第一个一级标题的行
    lines = md_content.splitlines()
    for i, line in enumerate(lines):
        if re.match(r"^#\s*(.+)", line):
            # 移除该行，并重新拼接内容
            return "\n".join(lines[:i] + lines[i+1:]).strip()
    return md_content.strip()
