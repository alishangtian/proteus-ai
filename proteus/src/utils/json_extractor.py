"""
提取JSON内容的工具模块
用于从Markdown格式的文本中提取纯JSON内容，去掉代码标识
"""

import re
import json
import logging

logger = logging.getLogger(__name__)

def extract_json_from_markdown(text):
    """
    从Markdown格式的文本中提取纯JSON内容
    
    参数:
        text: 可能包含Markdown格式的JSON文本
        
    返回:
        dict: 解析后的JSON对象，如果解析失败则返回None
    """
    if not text:
        return None
        
    # 尝试直接解析，可能本身就是有效的JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # 尝试移除Markdown代码块标记
    # 匹配 ```json 或 ``` 开头和 ``` 结尾的代码块
    code_block_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
    code_blocks = re.findall(code_block_pattern, text)
    
    if code_blocks:
        for block in code_blocks:
            try:
                return json.loads(block)
            except json.JSONDecodeError:
                continue
    
    # 如果没有找到代码块或解析失败，尝试查找看起来像JSON的部分
    json_pattern = r'({[\s\S]*?})'
    json_candidates = re.findall(json_pattern, text)
    
    for candidate in json_candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    
    logger.warning(f"无法从文本中提取有效的JSON: {text[:100]}...")
    return None

def extract_json_string_from_markdown(text):
    """
    从Markdown格式的文本中提取纯JSON字符串内容
    
    参数:
        text: 可能包含Markdown格式的JSON文本
        
    返回:
        str: 提取的JSON字符串，如果提取失败则返回原文本
    """
    if not text:
        return text
        
    # 匹配 ```json 或 ``` 开头和 ``` 结尾的代码块
    code_block_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
    match = re.search(code_block_pattern, text)
    
    if match:
        return match.group(1).strip()
    
    # 如果没有找到代码块，尝试查找看起来像JSON的部分
    json_pattern = r'({[\s\S]*?})'
    match = re.search(json_pattern, text)
    
    if match:
        return match.group(1).strip()
    
    # 如果都没找到，返回原文本
    return text