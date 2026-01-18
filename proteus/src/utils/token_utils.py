import tiktoken
from typing import List, Dict, Any

def count_tokens(messages: List[Dict[str, Any]], model: str = "gpt-3.5-turbo-0613") -> int:
    """
    计算消息列表的 token 数
    """
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")

    num_tokens = 0
    for message in messages:
        num_tokens += 4  # 每条消息的基础 token (role, content, etc.)
        for key, value in message.items():
            if value is None:
                continue
            if isinstance(value, str):
                num_tokens += len(encoding.encode(value))
            elif isinstance(value, list):
                # 处理 tool_calls 等复杂结构
                num_tokens += len(encoding.encode(str(value)))
            if key == "name":  # 如果有 name 字段，额外消耗 token
                num_tokens += -1
    num_tokens += 2  # 助手回复的起始 token
    return num_tokens
