"""LLM API调用模块"""

import logging
import json
import asyncio
import aiohttp
from typing import List, Dict, Union, AsyncGenerator, Tuple

from .config import API_CONFIG, retry_on_error
from .model_manager import ModelManager

# 配置日志记录
logger = logging.getLogger(__name__)


def calculate_messages_length(messages: List[Dict[str, str]]) -> int:
    """
    计算消息列表的总字符长度

    Args:
        messages: 消息列表

    Returns:
        总字符长度
    """
    total_length = 0
    for message in messages:
        # 计算每条消息中role和content的长度
        total_length += len(message.get("role", ""))
        total_length += len(message.get("content", ""))
    return total_length


def truncate_messages(
    messages: List[Dict[str, str]], max_length: int = 100000
) -> List[Dict[str, str]]:
    """
    如果消息总长度超过max_length，则只截断用户消息的content

    Args:
        messages: 消息列表
        max_length: 最大允许的总字符长度

    Returns:
        截断后的消息列表
    """
    if not messages:
        return messages

    # 如果总长度在限制内，直接返回原始消息
    total_length = calculate_messages_length(messages)
    if total_length <= max_length:
        return messages

    # 计算需要截断的长度
    excess_length = total_length - max_length

    # 获取所有用户消息
    user_messages = [
        msg for msg in messages if msg.get("role") == "user" and msg.get("content")
    ]
    if not user_messages:
        return messages

    # 计算每条用户消息需要截断的平均长度
    truncate_per_message = excess_length // len(user_messages)

    # 创建新的消息列表，截断content
    truncated = []
    remaining_excess = excess_length

    for msg in messages:
        if msg.get("role") == "user" and msg.get("content") and remaining_excess > 0:
            # 只截断用户消息的content
            content = msg["content"]
            # 确保至少保留一半的内容
            content_length = max(len(content) - truncate_per_message, len(content) // 2)
            truncated.append({**msg, "content": content[:content_length]})
            remaining_excess -= len(content) - content_length
        else:
            truncated.append(msg)

    logger.info(
        f"消息长度({total_length})超过{max_length}字符限制，已按比例截断用户消息内容"
    )
    return truncated


def select_model(messages: List[Dict[str, str]], request_id: str = None) -> str:
    """
    根据消息长度选择合适的模型

    Args:
        messages: 消息列表
        request_id: 请求ID,用于日志追踪

    Returns:
        选择的模型名称
    """
    messages_length = calculate_messages_length(messages)

    if messages_length > API_CONFIG["context_length_threshold"]:
        logger.info(
            f"[{request_id}] 消息长度({messages_length})超过阈值"
            f"({API_CONFIG['context_length_threshold']}), "
            f"使用长上下文模型: {API_CONFIG['long_context_model']}"
        )
        return API_CONFIG["long_context_model"]

    return API_CONFIG["model_name"]


async def call_llm_api_stream(
    messages: List[Dict[str, str]], request_id: str = None, output_json: bool = False
) -> AsyncGenerator[str, None]:
    """
    调用llm API服务(流式),支持自动重试

    Args:
        messages: 消息列表
        request_id: 请求ID,用于日志追踪
        output_json: 是否输出JSON结构,默认为False

    Returns:
        异步生成器,生成流式响应内容
    """

    logger.info(f"[{request_id}] 开始流式调用llm API")

    messages = truncate_messages(messages)

    # 根据消息长度选择模型
    model = select_model(messages, request_id)
    messages_length = calculate_messages_length(messages)

    logger.info(
        f"[{request_id}] 请求参数: model={model}, "
        f"messages_count={len(messages)}, "
        f"messages_length={messages_length}"
    )

    # 获取模型配置
    try:
        model_config = ModelManager().get_model_config(model)
        base_url = model_config["base_url"]
        model_type = model_config.get("type", "openai")
    except Exception as e:
        logger.warning(f"[{request_id}] 使用默认API配置: {str(e)}")
        base_url = API_CONFIG["base_url"]
        api_key = API_CONFIG["api_key"]
        model_type = "openai"

    # Configure larger buffer sizes for handling big response chunks
    conn = aiohttp.TCPConnector()
    client_timeout = aiohttp.ClientTimeout(total=120)
    async with aiohttp.ClientSession(
        connector=conn, timeout=client_timeout, read_bufsize=2**17  # 128KB buffer size
    ) as session:
        # 根据模型类型构建不同请求
        if model_type == "gemini":
            # Gemini模型特殊处理
            api_key = model_config.get("X-goog-api-key", model_config.get("api_key"))
            headers = {
                "Content-Type": "application/json",
                "X-goog-api-key": api_key,
            }

            # 构建Gemini格式的请求体
            data = {
                "contents": [{"parts": [{"text": msg["content"]} for msg in messages]}],
                "generationConfig": {
                    "temperature": 0.1,  # Gemini流式调用固定使用0.1温度
                },
            }

            # Gemini不支持output_json参数，忽略
            if output_json:
                logger.warning("Gemini模型不支持output_json参数，已忽略")

            url = base_url
        else:
            # 默认OpenAI格式
            api_key = model_config["api_key"]
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }

            data = {
                "model": model,
                "messages": messages,
                "stream": True,
            }
            if output_json:
                data["response_format"] = {"type": "json_object"}

            url = f"{base_url}/chat/completions"

        try:
            async with session.post(
                url,
                headers=headers,
                json=data,
                chunked=True,
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    if request_id:
                        logger.error(f"[{request_id}] API调用失败: {error_text}")
                    raise ValueError(f"API调用失败: {error_text}")

                if model_type == "gemini":
                    # 处理Gemini流式响应
                    buffer = b""
                    async for chunk in response.content.iter_any():
                        if chunk:
                            buffer += chunk
                            # Gemini响应以换行符分隔的JSON块
                            while b"\n" in buffer:
                                line, buffer = buffer.split(b"\n", 1)
                                if line:
                                    try:
                                        data = json.loads(line.decode("utf-8"))
                                        if "candidates" in data and data["candidates"]:
                                            candidate = data["candidates"][0]
                                            if (
                                                "content" in candidate
                                                and "parts" in candidate["content"]
                                            ):
                                                for part in candidate["content"][
                                                    "parts"
                                                ]:
                                                    if "text" in part:
                                                        yield part["text"]
                                    except Exception as e:
                                        logger.warning(
                                            f"[{request_id}] 解析Gemini响应出错: {str(e)}"
                                        )
                else:
                    # 处理OpenAI流式响应
                    async for line in response.content:
                        if line:
                            try:
                                line = line.decode("utf-8").strip()
                                if line.startswith("data: ") and line != "data: [DONE]":
                                    json_str = line[6:]  # 去掉 "data: "
                                    data = json.loads(json_str)
                                    if len(data["choices"]) > 0:
                                        delta = data["choices"][0].get("delta", {})
                                        if "content" in delta:
                                            yield delta["content"]
                            except Exception as e:
                                if "Chunk too big" in str(e):
                                    logger.warning(
                                        f"[{request_id}] 收到大块响应，尝试继续处理"
                                    )
                                    # Try to process the chunk even if it's large
                                    continue
                                else:
                                    logger.error(
                                        f"[{request_id}] 处理流式响应出错: {str(e)}"
                                    )
                                    raise

        except asyncio.TimeoutError:
            error_msg = "API调用超时"
            if request_id:
                logger.error(f"[{request_id}] {error_msg}")
            raise ValueError(error_msg)
        except Exception as e:
            if request_id:
                logger.error(f"[{request_id}] API调用异常: {str(e)}")
            raise


@retry_on_error(
    max_retries=API_CONFIG["llm_retry_count"],
    sleep=API_CONFIG["llm_retry_delay"],
    logger=logger,
)
async def call_llm_api(
    messages: List[Dict[str, str]],
    request_id: str = None,
    temperature: float = 0.1,
    output_json: bool = False,
    model_name: str = None,
    lang_context_model: str = None,
) -> str:
    """
    调用llm API服务，支持自动重试

    Args:
        messages: 消息列表
        request_id: 请求ID,用于日志追踪
        temperature: 温度参数，控制输出的随机性，默认0.1
        output_json: 是否输出JSON结构,默认为False

    Returns:
        返回完整响应字符串
    """
    logger.info(f"[{request_id}] 开始调用llm API")
    if model_name is None:
        model_name = "base-model"
    messages_length = calculate_messages_length(messages)
    if messages_length > 100000:
        if lang_context_model is None:
            lang_context_model = "lang-context-model"
        model_name = lang_context_model
    logger.info(
        f"[{request_id}] 请求参数: model={model_name}, "
        f"temperature={temperature}, "
        f"messages_count={len(messages)}, "
        f"messages_length={messages_length}"
    )

    # 获取模型配置
    try:
        model_config = ModelManager().get_model_config(model_name)
        base_url = model_config["base_url"]
        model_type = model_config.get("type", "openai")
        model_name = model_config["model_name"]
    except Exception as e:
        logger.error(f"模型配置有误，model_name:{model_name} \n{str(e)}")
        raise ValueError(f"模型配置有误，model_name:{model_name}")
    # Use same optimized session configuration as streaming
    conn = aiohttp.TCPConnector()
    client_timeout = aiohttp.ClientTimeout(total=120)
    async with aiohttp.ClientSession(
        connector=conn, timeout=client_timeout, read_bufsize=2**17  # 128KB buffer size
    ) as session:
        # 根据模型类型构建不同请求
        if model_type == "gemini":
            # Gemini模型特殊处理
            api_key = model_config.get("X-goog-api-key", model_config.get("api_key"))
            headers = {
                "Content-Type": "application/json",
                "X-goog-api-key": api_key,
            }

            # 构建Gemini格式的请求体
            data = {
                "contents": [{"parts": [{"text": msg["content"]} for msg in messages]}],
                "generationConfig": {
                    "temperature": temperature,
                },
            }

            url = base_url
        else:
            # 默认OpenAI格式
            api_key = model_config["api_key"]
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }

            data = {
                "model": model_name,
                "messages": messages,
                "stream": False,
                "temperature": temperature,
            }
            if output_json:
                data["response_format"] = {"type": "json_object"}

            url = f"{base_url}/chat/completions"

        try:
            async with session.post(
                url,
                headers=headers,
                json=data,
                chunked=True,
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(response.status)
                    if request_id:
                        logger.error(f"[{request_id}] API调用失败: {error_text}")
                    raise ValueError(f"API调用失败: {error_text}")

                result = await response.json()
                if request_id:
                    logger.info(f"[{request_id}] API调用成功")

                # 根据模型类型解析不同响应格式
                if model_type == "gemini":
                    if "candidates" in result and result["candidates"]:
                        return result["candidates"][0]["content"]["parts"][0]["text"]
                    else:
                        raise ValueError("Gemini响应格式错误，未找到有效候选")
                else:
                    return result["choices"][0]["message"]["content"]

        except asyncio.TimeoutError:
            error_msg = "API调用超时"
            logger.error(f"[{request_id}] {error_msg}")
            raise ValueError(error_msg)
        except Exception as e:
            logger.error(f"[{request_id}] API调用异常: {str(e)}")
            raise
