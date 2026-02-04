"""
记忆系统工具函数
提供重要性计算、摘要生成、相似度计算等实用功能
"""

import re
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
import hashlib

# 敏感信息模式
SENSITIVE_PATTERNS = [
    r'\d{3}-\d{2}-\d{4}',  # SSN格式
    r'\d{16}',  # 信用卡号
    r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}',  # 邮箱
    r'\+?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}',  # 电话
]

def calculate_importance(content: str, context: Dict = None) -> float:
    """
    计算记忆内容的重要性评分
    
    Args:
        content: 记忆内容
        context: 上下文信息（可选）
        
    Returns:
        float: 重要性评分 (0.0-1.0)
    """
    score = 0.5  # 基础分
    
    # 1. 内容长度因素
    content_length = len(content)
    if content_length > 200:
        score += 0.05  # 长内容可能更重要
    elif content_length < 20:
        score -= 0.05  # 短内容可能不重要
    
    # 2. 关键词检测
    important_keywords = [
        '喜欢', '偏好', '习惯', '重要', '关键', '必须', '需要',
        'prefer', 'like', 'important', 'critical', 'essential'
    ]
    
    keyword_count = 0
    for keyword in important_keywords:
        if keyword in content:
            keyword_count += 1
    
    score += min(keyword_count * 0.03, 0.15)  # 最多增加0.15
    
    # 3. 情感倾向（简单检测）
    positive_words = ['好', '喜欢', '爱', '满意', '开心', '棒']
    negative_words = ['讨厌', '不喜欢', '恨', '不满意', '糟糕']
    
    positive_count = sum(1 for word in positive_words if word in content)
    negative_count = sum(1 for word in negative_words if word in content)
    
    if positive_count > negative_count:
        score += 0.05
    elif negative_count > positive_count:
        score -= 0.02  # 负面内容可能也需要记住
    
    # 4. 上下文因素
    if context:
        # 用户强调（如重复、大写等）
        if context.get('user_emphasized', False):
            score += 0.1
        
        # 对话位置（开始/结束可能更重要）
        position = context.get('position', 'middle')
        if position in ['beginning', 'end']:
            score += 0.05
    
    # 确保在0-1范围内
    return max(0.0, min(1.0, score))

def apply_time_decay(original_importance: float, age_days: float, 
                    half_life_days: float = 90) -> float:
    """
    应用时间衰减到重要性评分
    
    Args:
        original_importance: 原始重要性
        age_days: 记忆年龄（天数）
        half_life_days: 重要性减半所需天数
        
    Returns:
        float: 衰减后的重要性
    """
    if half_life_days <= 0:
        return original_importance
    
    decay_factor = 0.5 ** (age_days / half_life_days)
    return original_importance * decay_factor

def generate_summary(content: str, max_length: int = 100) -> str:
    """
    生成内容摘要
    
    Args:
        content: 原始内容
        max_length: 摘要最大长度
        
    Returns:
        str: 摘要文本
    """
    if len(content) <= max_length:
        return content
    
    # 简单实现：取开头和结尾部分
    first_part = content[:max_length//2]
    last_part = content[-max_length//2:] if len(content) > max_length else ""
    
    if last_part:
        return f"{first_part}...{last_part}"
    else:
        return first_part + "..."

def sanitize_content(content: str) -> str:
    """
    脱敏处理，移除敏感信息
    
    Args:
        content: 原始内容
        
    Returns:
        str: 脱敏后的内容
    """
    sanitized = content
    
    for pattern in SENSITIVE_PATTERNS:
        sanitized = re.sub(pattern, '[REDACTED]', sanitized)
    
    return sanitized

def calculate_similarity(text1: str, text2: str) -> float:
    """
    计算两个文本的相似度（简单实现）
    
    Args:
        text1: 文本1
        text2: 文本2
        
    Returns:
        float: 相似度 (0.0-1.0)
    """
    if not text1 or not text2:
        return 0.0
    
    # 转换为小写并分词（简单空格分词）
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    
    if not words1 or not words2:
        return 0.0
    
    # Jaccard相似度
    intersection = words1.intersection(words2)
    union = words1.union(words2)
    
    return len(intersection) / len(union)

def extract_tags(content: str, existing_tags: List[str] = None) -> List[str]:
    """
    从内容中提取标签
    
    Args:
        content: 内容文本
        existing_tags: 现有标签列表（可选）
        
    Returns:
        List[str]: 提取的标签
    """
    tags = existing_tags or []
    
    # 预定义类别关键词
    category_keywords = {
        "饮食": ["吃", "喝", "咖啡", "茶", "食物", "餐厅", "做饭"],
        "健康": ["健康", "运动", "健身", "医院", "医生", "药", "睡眠"],
        "工作": ["工作", "项目", "会议", "任务", "截止日期", "同事"],
        "学习": ["学习", "读书", "课程", "教育", "学校", "考试"],
        "娱乐": ["电影", "音乐", "游戏", "旅游", "假期", "爱好"],
        "购物": ["买", "购物", "价格", "商品", "商店", "在线"],
    }
    
    content_lower = content.lower()
    
    for category, keywords in category_keywords.items():
        for keyword in keywords:
            if keyword in content_lower and category not in tags:
                tags.append(category)
                break
    
    # 提取实体名词（简单实现）
    # 这里可以扩展为使用NLP库进行实体识别
    
    return list(set(tags))  # 去重

def generate_memory_id(prefix: str = "mem") -> str:
    """
    生成唯一的记忆ID
    
    Args:
        prefix: ID前缀
        
    Returns:
        str: 记忆ID
    """
    timestamp = int(time.time() * 1000)
    random_part = hashlib.md5(str(time.time()).encode()).hexdigest()[:6]
    return f"{prefix}_{timestamp}_{random_part}"

def format_timestamp(timestamp: float = None, 
                    format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    格式化时间戳
    
    Args:
        timestamp: Unix时间戳，None表示当前时间
        format_str: 格式字符串
        
    Returns:
        str: 格式化后的时间字符串
    """
    if timestamp is None:
        dt = datetime.now()
    else:
        dt = datetime.fromtimestamp(timestamp)
    
    return dt.strftime(format_str)

def parse_time_range(time_range_str: str) -> Tuple[float, float]:
    """
    解析时间范围字符串
    
    Args:
        time_range_str: 时间范围字符串，如 "7d", "30d", "2025-01-01:2025-01-31"
        
    Returns:
        Tuple[float, float]: (开始时间戳, 结束时间戳)
    """
    now = time.time()
    
    # 处理相对时间
    if time_range_str.endswith('d'):
        days = int(time_range_str[:-1])
        start_time = now - (days * 24 * 3600)
        return start_time, now
    
    # 处理绝对时间范围
    elif ':' in time_range_str:
        start_str, end_str = time_range_str.split(':', 1)
        try:
            start_dt = datetime.strptime(start_str.strip(), "%Y-%m-%d")
            end_dt = datetime.strptime(end_str.strip(), "%Y-%m-%d")
            return start_dt.timestamp(), end_dt.timestamp()
        except ValueError:
            pass
    
    # 默认返回最近7天
    return now - (7 * 24 * 3600), now

def compress_memories(memories: List[Dict], similarity_threshold: float = 0.8) -> List[Dict]:
    """
    压缩相似记忆
    
    Args:
        memories: 记忆列表
        similarity_threshold: 相似度阈值
        
    Returns:
        List[Dict]: 压缩后的记忆列表
    """
    if not memories:
        return []
    
    compressed = []
    used_indices = set()
    
    for i, mem1 in enumerate(memories):
        if i in used_indices:
            continue
        
        # 找到相似记忆
        similar_indices = [i]
        for j, mem2 in enumerate(memories[i+1:], start=i+1):
            if j in used_indices:
                continue
            
            similarity = calculate_similarity(
                mem1.get("content", ""),
                mem2.get("content", "")
            )
            
            if similarity >= similarity_threshold:
                similar_indices.append(j)
        
        # 合并相似记忆
        if len(similar_indices) > 1:
            similar_memories = [memories[idx] for idx in similar_indices]
            merged = merge_similar_memories(similar_memories)
            compressed.append(merged)
            
            # 标记已处理
            used_indices.update(similar_indices)
        else:
            compressed.append(mem1)
            used_indices.add(i)
    
    return compressed

def merge_similar_memories(memories: List[Dict]) -> Dict:
    """
    合并相似记忆
    
    Args:
        memories: 相似记忆列表
        
    Returns:
        Dict: 合并后的记忆
    """
    if not memories:
        return {}
    
    # 使用最重要的记忆作为基础
    base_memory = max(memories, key=lambda x: x.get("importance", 0))
    
    # 合并内容
    contents = [m.get("content", "") for m in memories]
    merged_content = generate_summary(" ".join(contents), max_length=500)
    
    # 合并重要性（取最高）
    merged_importance = max(m.get("importance", 0) for m in memories)
    
    # 合并标签
    all_tags = []
    for memory in memories:
        tags = memory.get("tags", [])
        if isinstance(tags, list):
            all_tags.extend(tags)
    
    # 合并元数据
    all_metadata = {}
    for memory in memories:
        metadata = memory.get("metadata", {})
        if isinstance(metadata, dict):
            all_metadata.update(metadata)
    
    # 创建合并后的记忆
    merged_memory = base_memory.copy()
    merged_memory.update({
        "id": generate_memory_id("merged"),
        "content": merged_content,
        "importance": merged_importance,
        "tags": list(set(all_tags)),
        "metadata": all_metadata,
        "merged_from": [m.get("id", "unknown") for m in memories],
        "merged_at": time.time()
    })
    
    return merged_memory

def validate_memory(memory: Dict) -> Tuple[bool, str]:
    """
    验证记忆数据的有效性
    
    Args:
        memory: 记忆数据
        
    Returns:
        Tuple[bool, str]: (是否有效, 错误信息)
    """
    # 检查必需字段
    required_fields = ["id", "content"]
    for field in required_fields:
        if field not in memory:
            return False, f"缺少必需字段: {field}"
    
    # 检查内容非空
    content = memory.get("content", "")
    if not content or not content.strip():
        return False, "内容不能为空"
    
    # 检查重要性范围
    importance = memory.get("importance", 0.5)
    if not isinstance(importance, (int, float)):
        return False, "重要性必须是数字"
    if importance < 0 or importance > 1:
        return False, "重要性必须在0-1范围内"
    
    # 检查标签类型
    tags = memory.get("tags", [])
    if not isinstance(tags, list):
        return False, "标签必须是列表"
    
    return True, ""

# 使用示例
if __name__ == "__main__":
    # 测试重要性计算
    content = "用户喜欢喝黑咖啡，每天早上一杯"
    importance = calculate_importance(content)
    print(f"内容: {content}")
    print(f"重要性评分: {importance}")
    
    # 测试时间衰减
    decayed = apply_time_decay(importance, age_days=30)
    print(f"30天后衰减的重要性: {decayed}")
    
    # 测试摘要生成
    summary = generate_summary("这是一段很长的测试内容，需要被摘要。" * 10)
    print(f"摘要: {summary}")
    
    # 测试相似度计算
    sim = calculate_similarity("我喜欢苹果", "我爱苹果")
    print(f"相似度: {sim}")
    
    # 测试标签提取
    tags = extract_tags("我昨天去看了医生，然后买了些药")
    print(f"提取的标签: {tags}")
