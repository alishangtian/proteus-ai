import logging
import tiktoken
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def count_tokens(
    messages: List[Dict[str, Any]], model: str = "gpt-3.5-turbo-0613"
) -> int:
    """
    计算消息列表的 token 数。
    当 tiktoken 计算失败时，退化为字数/2 进行估算（不区分中英文）。
    """
    try:
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
    except Exception as e:
        # 退化为字数/2 估算（不区分中英文）
        logger.warning(f"tiktoken 计算失败，退化为字数/2 估算: {e}")
        total_chars = 0
        for message in messages:
            for value in message.values():
                if value is None:
                    continue
                if isinstance(value, str):
                    total_chars += len(value)
                elif isinstance(value, list):
                    total_chars += len(str(value))
        return total_chars // 2
