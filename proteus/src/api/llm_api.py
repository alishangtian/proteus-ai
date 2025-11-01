"""LLM API调用模块"""

import logging
import json
import asyncio
import aiohttp
import base64
from pathlib import Path
from typing import List, Dict, Union, AsyncGenerator, Tuple

from .config import API_CONFIG, retry_on_error
from .model_manager import ModelManager
from ..utils.langfuse_wrapper import langfuse_wrapper

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
        total_length += len(message.get("role", ""))
        content = message.get("content", "")
        if isinstance(content, str):
            total_length += len(content)
        elif isinstance(content, list):
            for item in content:
                if item.get("type") == "text":
                    total_length += len(item.get("text", ""))
                elif item.get("type") == "image_url":
                    # 图片URL的长度可以忽略，或者根据实际情况估算
                    total_length += 0  # 暂时忽略图片长度
    return total_length


def encode_image_to_base64(image_path: Union[str, Path]) -> str:
    """
    将图片编码为Base64字符串

    Args:
        image_path: 图片文件路径

    Returns:
        Base64编码的图片字符串
    """
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


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
) -> Tuple[str, Dict]:
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
        model_name = "deepseek-chat"
    messages_length = calculate_messages_length(messages)
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
    # 优化连接配置，提高稳定性
    conn = aiohttp.TCPConnector(
        limit=10,  # 连接池大小
        limit_per_host=5,  # 每个主机的连接数
        ttl_dns_cache=300,  # DNS缓存时间
        use_dns_cache=True,
        keepalive_timeout=30,  # 保持连接时间
        enable_cleanup_closed=True,  # 自动清理关闭的连接
    )
    client_timeout = aiohttp.ClientTimeout(
        total=120,  # 总超时时间
        connect=10,  # 连接超时时间
        sock_read=60,  # 读取超时时间
    )
    async with aiohttp.ClientSession(
        connector=conn,
        timeout=client_timeout,
        read_bufsize=2**17,  # 128KB buffer size
        headers={"Connection": "keep-alive"},  # 保持连接
    ) as session:
        # 根据模型类型构建不同请求
        # 默认OpenAI格式
        api_key = model_config["api_key"]
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-Title": "proteus-ai",
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

                # 根据模型类型解析不同响应格式并提取usage信息（若存在）
                usage: Dict = {}
                if isinstance(result, dict):
                    usage = result.get("usage", {}) or {}

                text = result["choices"][0]["message"]["content"]
                return text, usage

        except asyncio.TimeoutError:
            error_msg = "API调用超时"
            logger.error(f"[{request_id}] {error_msg}")
            raise ValueError(error_msg)
        except aiohttp.ClientConnectionError as e:
            error_msg = f"连接错误: {str(e)}"
            logger.error(f"[{request_id}] {error_msg}")
            raise ConnectionError(error_msg)
        except aiohttp.ServerDisconnectedError as e:
            error_msg = f"服务器连接中断: {str(e)}"
            logger.error(f"[{request_id}] {error_msg}")
            raise ConnectionError(error_msg)
        except aiohttp.ClientError as e:
            error_msg = f"客户端错误: {str(e)}"
            logger.error(f"[{request_id}] {error_msg}")
            raise ConnectionError(error_msg)
        except Exception as e:
            logger.error(f"[{request_id}] API调用异常: {str(e)}")
            # 对于网络相关的异常，转换为ConnectionError以便重试
            if any(
                keyword in str(e).lower()
                for keyword in ["disconnected", "connection", "network", "timeout"]
            ):
                raise ConnectionError(f"网络连接异常: {str(e)}")
            raise


@retry_on_error(
    max_retries=API_CONFIG["llm_retry_count"],
    sleep=API_CONFIG["llm_retry_delay"],
    logger=logger,
)
async def call_multimodal_llm_api(
    messages: List[Dict[str, Union[str, List[Dict[str, Union[str, Dict[str, str]]]]]]],
    request_id: str = None,
    temperature: float = 0.1,
    output_json: bool = False,
    model_name: str = None,
) -> Tuple[str, Dict]:
    """
    调用llm API服务，支持自动重试和多模态输入

    Args:
        messages: 消息列表，支持文本和图片URL
        request_id: 请求ID,用于日志追踪
        temperature: 温度参数，控制输出的随机性，默认0.1
        output_json: 是否输出JSON结构,默认为False

    Returns:
        返回完整响应字符串
    """
    logger.info(f"[{request_id}] 开始调用多模态llm API")
    if model_name is None:
        model_name = "gemini-2.5-flash"
    messages_length = calculate_messages_length(
        messages
    )  # 仍然使用原有的长度计算，图片长度暂时忽略
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
        model_name = model_config["model_name"]
    except Exception as e:
        logger.error(f"模型配置有误，model_name:{model_name} \n{str(e)}")
        raise ValueError(f"模型配置有误，model_name:{model_name}")
    # 优化连接配置，提高稳定性
    conn = aiohttp.TCPConnector(
        limit=10,  # 连接池大小
        limit_per_host=5,  # 每个主机的连接数
        ttl_dns_cache=300,  # DNS缓存时间
        use_dns_cache=True,
        keepalive_timeout=30,  # 保持连接时间
        enable_cleanup_closed=True,  # 自动清理关闭的连接
    )
    client_timeout = aiohttp.ClientTimeout(
        total=120,  # 总超时时间
        connect=10,  # 连接超时时间
        sock_read=60,  # 读取超时时间
    )
    async with aiohttp.ClientSession(
        connector=conn,
        timeout=client_timeout,
        read_bufsize=2**17,  # 128KB buffer size
        headers={"Connection": "keep-alive"},  # 保持连接
    ) as session:
        # 根据模型类型构建不同请求
        # 默认OpenAI格式
        api_key = model_config["api_key"]
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-Title": "proteus-ai",
        }

        processed_messages = []
        for message in messages:
            if isinstance(message.get("content"), list):
                new_content = []
                for item in message["content"]:
                    if item.get("type") == "image_url" and not item["image_url"][
                        "url"
                    ].startswith("data:"):
                        image_path = item["image_url"]["url"]
                        base64_image = encode_image_to_base64(image_path)
                        new_content.append(
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                },
                            }
                        )
                    else:
                        new_content.append(item)
                processed_messages.append({**message, "content": new_content})
            else:
                processed_messages.append(message)

        data = {
            "model": model_name,
            "messages": processed_messages,
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

                # 根据模型类型解析不同响应格式并提取usage信息（若存在）
                usage: Dict = {}
                if isinstance(result, dict):
                    usage = result.get("usage", {}) or {}

                text = result["choices"][0]["message"]["content"]
                return text, usage

        except asyncio.TimeoutError:
            error_msg = "API调用超时"
            logger.error(f"[{request_id}] {error_msg}")
            raise ValueError(error_msg)
        except aiohttp.ClientConnectionError as e:
            error_msg = f"连接错误: {str(e)}"
            logger.error(f"[{request_id}] {error_msg}")
            raise ConnectionError(error_msg)
        except aiohttp.ServerDisconnectedError as e:
            error_msg = f"服务器连接中断: {str(e)}"
            logger.error(f"[{request_id}] {error_msg}")
            raise ConnectionError(error_msg)
        except aiohttp.ClientError as e:
            error_msg = f"客户端错误: {str(e)}"
            logger.error(f"[{request_id}] {error_msg}")
            raise ConnectionError(error_msg)
        except Exception as e:
            logger.error(f"[{request_id}] API调用异常: {str(e)}")
            # 对于网络相关的异常，转换为ConnectionError以便重试
            if any(
                keyword in str(e).lower()
                for keyword in ["disconnected", "connection", "network", "timeout"]
            ):
                raise ConnectionError(f"网络连接异常: {str(e)}")
            raise


async def call_llm_api_stream(
    messages: List[Dict[str, str]],
    request_id: str = None,
    temperature: float = 0.1,
    output_json: bool = False,
    model_name: str = None,
    enable_thinking: bool = False,
) -> AsyncGenerator[Dict[str, Union[str, Dict]], None]:
    """
    调用llm API服务的流式版本，支持thinking和non-thinking模式

    Args:
        messages: 消息列表
        request_id: 请求ID,用于日志追踪
        temperature: 温度参数，控制输出的随机性，默认0.1
        output_json: 是否输出JSON结构,默认为False
        model_name: 模型名称
        enable_thinking: 是否启用thinking模式，默认False

    Yields:
        字典格式的流式响应，包含以下字段：
        - type: 'thinking' | 'content' | 'usage' | 'error'
        - content: 文本内容（当type为thinking或content时）
        - usage: token使用信息（当type为usage时）
        - error: 错误信息（当type为error时）
    """
    logger.info(f"[{request_id}] 开始调用流式llm API (thinking模式: {enable_thinking})")
    if model_name is None:
        model_name = "deepseek-chat"

    messages_length = calculate_messages_length(messages)
    logger.info(
        f"[{request_id}] 请求参数: model={model_name}, "
        f"temperature={temperature}, "
        f"messages_count={len(messages)}, "
        f"messages_length={messages_length}, "
        f"enable_thinking={enable_thinking}"
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

    # 优化连接配置，提高稳定性
    conn = aiohttp.TCPConnector(
        limit=10,
        limit_per_host=5,
        ttl_dns_cache=300,
        use_dns_cache=True,
        keepalive_timeout=30,
        enable_cleanup_closed=True,
    )
    client_timeout = aiohttp.ClientTimeout(
        total=300,  # 流式调用需要更长的超时时间
        connect=10,
        sock_read=120,
    )

    async with aiohttp.ClientSession(
        connector=conn,
        timeout=client_timeout,
        read_bufsize=2**17,
        headers={"Connection": "keep-alive"},
    ) as session:
        api_key = model_config["api_key"]
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-Title": "proteus-ai",
        }

        data = {
            "model": model_name,
            "messages": messages,
            "stream": True,
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
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"[{request_id}] API调用失败: {error_text}")
                    yield {"type": "error", "error": f"API调用失败: {error_text}"}
                    return

                logger.info(f"[{request_id}] 流式API调用开始接收数据")

                # 用于累积完整的usage信息
                accumulated_usage = {}

                async for line in response.content:
                    line = line.decode("utf-8").strip()

                    if not line or line == "data: [DONE]":
                        continue

                    if line.startswith("data: "):
                        line = line[6:]  # 移除 "data: " 前缀

                    try:
                        chunk = json.loads(line)

                        # 提取usage信息（如果存在）
                        if "usage" in chunk:
                            accumulated_usage = chunk["usage"]

                        # 处理choices中的内容
                        if "choices" in chunk and len(chunk["choices"]) > 0:
                            choice = chunk["choices"][0]
                            delta = choice.get("delta", {})

                            # 处理thinking内容（如果启用）
                            if enable_thinking:
                                reasoning_content = delta.get("reasoning_content")
                                if reasoning_content:
                                    yield {
                                        "type": "thinking",
                                        "content": reasoning_content,
                                    }

                            # 处理普通内容
                            if "content" in delta:
                                content = delta["content"]
                                if content:
                                    yield {"type": "content", "content": content}

                            # 检查是否完成
                            if choice.get("finish_reason") == "stop":
                                logger.info(f"[{request_id}] 流式API调用完成")
                                # 返回usage信息
                                if accumulated_usage:
                                    yield {"type": "usage", "usage": accumulated_usage}

                    except json.JSONDecodeError as e:
                        logger.warning(
                            f"[{request_id}] 解析JSON失败: {line}, 错误: {str(e)}"
                        )
                        continue
                    except Exception as e:
                        logger.error(f"[{request_id}] 处理流式数据异常: {str(e)}")
                        yield {"type": "error", "error": f"处理流式数据异常: {str(e)}"}
                        continue

        except asyncio.TimeoutError:
            error_msg = "流式API调用超时"
            logger.error(f"[{request_id}] {error_msg}")
            yield {"type": "error", "error": error_msg}
        except aiohttp.ClientConnectionError as e:
            error_msg = f"连接错误: {str(e)}"
            logger.error(f"[{request_id}] {error_msg}")
            yield {"type": "error", "error": error_msg}
        except aiohttp.ServerDisconnectedError as e:
            error_msg = f"服务器连接中断: {str(e)}"
            logger.error(f"[{request_id}] {error_msg}")
            yield {"type": "error", "error": error_msg}
        except aiohttp.ClientError as e:
            error_msg = f"客户端错误: {str(e)}"
            logger.error(f"[{request_id}] {error_msg}")
            yield {"type": "error", "error": error_msg}
        except Exception as e:
            logger.error(f"[{request_id}] 流式API调用异常: {str(e)}")
            yield {"type": "error", "error": f"流式API调用异常: {str(e)}"}


@retry_on_error(
    max_retries=API_CONFIG["llm_retry_count"],
    sleep=API_CONFIG["llm_retry_delay"],
    logger=logger,
)
async def call_llm_api_with_tools(
    messages: List[Dict[str, str]],
    tools: List[Dict] = None,
    request_id: str = None,
    temperature: float = 0.1,
    model_name: str = None,
) -> Tuple[Dict, Dict]:
    """
    调用支持工具调用的 LLM API 服务（非流式）

    Args:
        messages: 消息列表
        tools: 工具定义列表，格式遵循 OpenAI 工具调用规范
        request_id: 请求ID，用于日志追踪
        temperature: 温度参数，控制输出的随机性，默认0.1
        model_name: 模型名称，默认为 deepseek-chat

    Returns:
        返回元组 (message_dict, usage_dict)
        - message_dict: 完整的消息对象，包含 content 和可能的 tool_calls
        - usage_dict: token 使用信息
    """
    logger.info(f"[{request_id}] 开始调用支持工具的 LLM API（非流式）")
    if model_name is None:
        model_name = "deepseek-chat"

    messages_length = calculate_messages_length(messages)
    logger.info(
        f"[{request_id}] 请求参数: model={model_name}, "
        f"temperature={temperature}, "
        f"messages_count={len(messages)}, "
        f"messages_length={messages_length}, "
        f"tools_count={len(tools) if tools else 0}"
    )

    # 获取模型配置
    try:
        model_config = ModelManager().get_model_config(model_name)
        base_url = model_config["base_url"]
        model_name = model_config["model_name"]
    except Exception as e:
        logger.error(f"模型配置有误，model_name:{model_name} \n{str(e)}")
        raise ValueError(f"模型配置有误，model_name:{model_name}")

    # 优化连接配置，提高稳定性
    conn = aiohttp.TCPConnector(
        limit=10,
        limit_per_host=5,
        ttl_dns_cache=300,
        use_dns_cache=True,
        keepalive_timeout=30,
        enable_cleanup_closed=True,
    )
    client_timeout = aiohttp.ClientTimeout(
        total=120,
        connect=10,
        sock_read=60,
    )

    async with aiohttp.ClientSession(
        connector=conn,
        timeout=client_timeout,
        read_bufsize=2**17,
        headers={"Connection": "keep-alive"},
    ) as session:
        api_key = model_config["api_key"]
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-Title": "proteus-ai",
        }

        data = {
            "model": model_name,
            "messages": messages,
            "stream": False,
            "temperature": temperature,
        }

        # 如果提供了工具定义，添加到请求中
        if tools:
            data["tools"] = tools

        url = f"{base_url}/chat/completions"

        try:
            async with session.post(
                url,
                headers=headers,
                json=data,
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

                # 提取usage信息
                usage: Dict = {}
                if isinstance(result, dict):
                    usage = result.get("usage", {}) or {}

                # 返回完整的消息对象
                message = result["choices"][0]["message"]
                return message, usage

        except asyncio.TimeoutError:
            error_msg = "API调用超时"
            logger.error(f"[{request_id}] {error_msg}")
            raise ValueError(error_msg)
        except aiohttp.ClientConnectionError as e:
            error_msg = f"连接错误: {str(e)}"
            logger.error(f"[{request_id}] {error_msg}")
            raise ConnectionError(error_msg)
        except aiohttp.ServerDisconnectedError as e:
            error_msg = f"服务器连接中断: {str(e)}"
            logger.error(f"[{request_id}] {error_msg}")
            raise ConnectionError(error_msg)
        except aiohttp.ClientError as e:
            error_msg = f"客户端错误: {str(e)}"
            logger.error(f"[{request_id}] {error_msg}")
            raise ConnectionError(error_msg)
        except Exception as e:
            logger.error(f"[{request_id}] API调用异常: {str(e)}")
            if any(
                keyword in str(e).lower()
                for keyword in ["disconnected", "connection", "network", "timeout"]
            ):
                raise ConnectionError(f"网络连接异常: {str(e)}")
            raise


@langfuse_wrapper.observe_decorator(
    name="call_llm_api_with_tools_stream", capture_input=True, capture_output=True
)
async def call_llm_api_with_tools_stream(
    messages: List[Dict[str, str]],
    tools: List[Dict] = None,
    request_id: str = None,
    temperature: float = 0.1,
    model_name: str = None,
    enable_thinking: bool = True,
) -> AsyncGenerator[Dict[str, Union[str, Dict, List]], None]:
    """
    调用支持工具调用的 LLM API 服务（流式）

    Args:
        messages: 消息列表
        tools: 工具定义列表，格式遵循 OpenAI 工具调用规范
        request_id: 请求ID，用于日志追踪
        temperature: 温度参数，控制输出的随机性，默认0.1
        model_name: 模型名称，默认为 deepseek-chat
        enable_thinking: 是否启用thinking模式，默认True

    Yields:
        字典格式的流式响应，包含以下字段：
        - type: 'thinking' | 'content' | 'tool_calls' | 'usage' | 'error'
        - content: 文本内容（当type为thinking或content时）
        - tool_calls: 工具调用列表（当type为tool_calls时）
        - usage: token使用信息（当type为usage时）
        - error: 错误信息（当type为error时）
    """
    logger.info(f"[{request_id}] 开始调用支持工具的 LLM API（流式）")
    if model_name is None:
        model_name = "deepseek-chat"

    messages_length = calculate_messages_length(messages)
    logger.info(
        f"[{request_id}] 请求参数: model={model_name}, "
        f"temperature={temperature}, "
        f"messages_count={len(messages)}, "
        f"messages_length={messages_length}, "
        f"tools_count={len(tools) if tools else 0}"
    )

    # 获取模型配置
    try:
        model_config = ModelManager().get_model_config(model_name)
        base_url = model_config["base_url"]
        model_name = model_config["model_name"]
    except Exception as e:
        logger.error(f"模型配置有误，model_name:{model_name} \n{str(e)}")
        raise ValueError(f"模型配置有误，model_name:{model_name}")

    # 优化连接配置，提高稳定性
    conn = aiohttp.TCPConnector(
        limit=10,
        limit_per_host=5,
        ttl_dns_cache=300,
        use_dns_cache=True,
        keepalive_timeout=30,
        enable_cleanup_closed=True,
    )
    client_timeout = aiohttp.ClientTimeout(
        total=300,  # 流式调用需要更长的超时时间
        connect=10,
        sock_read=120,
    )

    async with aiohttp.ClientSession(
        connector=conn,
        timeout=client_timeout,
        read_bufsize=2**17,
        headers={"Connection": "keep-alive"},
    ) as session:
        api_key = model_config["api_key"]
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-Title": "proteus-ai",
        }

        data = {
            "model": model_name,
            "messages": messages,
            "stream": True,
            "temperature": temperature,
        }

        # 如果提供了工具定义，添加到请求中
        if tools:
            data["tools"] = tools

        url = f"{base_url}/chat/completions"

        try:
            async with session.post(
                url,
                headers=headers,
                json=data,
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"[{request_id}] API调用失败: {error_text}")
                    yield {"type": "error", "error": f"API调用失败: {error_text}"}
                    return

                logger.info(f"[{request_id}] 流式API调用开始接收数据")

                # 用于累积完整的usage信息和工具调用
                accumulated_usage = {}
                accumulated_tool_calls = []

                async for line in response.content:
                    line = line.decode("utf-8").strip()

                    if not line or line == "data: [DONE]":
                        continue

                    if line.startswith("data: "):
                        line = line[6:]  # 移除 "data: " 前缀

                    try:
                        chunk = json.loads(line)

                        # 提取usage信息（如果存在）
                        if "usage" in chunk:
                            accumulated_usage = chunk["usage"]

                        # 处理choices中的内容
                        if "choices" in chunk and len(chunk["choices"]) > 0:
                            choice = chunk["choices"][0]
                            logger.info(f"[{request_id}] 响应内容: {choice}")
                            delta = choice.get("delta", {})

                            # 处理thinking内容（如果启用）
                            if enable_thinking:
                                # 安全地获取 reasoning_content 和 reasoning 字段
                                reasoning_content = delta.get("reasoning_content")
                                reasoning = delta.get("reasoning")

                                if reasoning_content and reasoning_content != "":
                                    yield {
                                        "type": "thinking",
                                        "content": reasoning_content,
                                    }

                                if reasoning and reasoning != "":
                                    yield {
                                        "type": "thinking",
                                        "content": reasoning,
                                    }

                            # 处理普通内容
                            if "content" in delta:
                                content = delta["content"]
                                if content:
                                    yield {"type": "content", "content": content}

                            # 处理工具调用
                            if "tool_calls" in delta:
                                tool_calls = delta["tool_calls"]
                                if tool_calls:
                                    # 累积工具调用信息
                                    for tool_call in tool_calls:
                                        index = tool_call.get("index", 0)

                                        # 确保accumulated_tool_calls有足够的空间
                                        while len(accumulated_tool_calls) <= index:
                                            accumulated_tool_calls.append(
                                                {
                                                    "id": "",
                                                    "type": "function",
                                                    "function": {
                                                        "name": "",
                                                        "arguments": "",
                                                    },
                                                }
                                            )

                                        # 更新工具调用信息
                                        if "id" in tool_call:
                                            accumulated_tool_calls[index]["id"] = (
                                                tool_call["id"]
                                            )
                                        if "type" in tool_call:
                                            accumulated_tool_calls[index]["type"] = (
                                                tool_call["type"]
                                            )
                                        if "function" in tool_call:
                                            func = tool_call["function"]
                                            if "name" in func:
                                                accumulated_tool_calls[index][
                                                    "function"
                                                ]["name"] = func["name"]
                                            if "arguments" in func:
                                                accumulated_tool_calls[index][
                                                    "function"
                                                ]["arguments"] += func["arguments"]

                            # 检查是否完成
                            if choice.get("finish_reason") in ["stop", "tool_calls"]:
                                logger.info(
                                    f"[{request_id}] 流式API调用完成，finish_reason: {choice.get('finish_reason')}"
                                )

                                # 如果有工具调用，返回完整的工具调用信息
                                if accumulated_tool_calls:
                                    yield {
                                        "type": "tool_calls",
                                        "tool_calls": accumulated_tool_calls,
                                    }

                                # 返回usage信息
                                if accumulated_usage:
                                    yield {"type": "usage", "usage": accumulated_usage}

                    except json.JSONDecodeError as e:
                        logger.warning(
                            f"[{request_id}] 解析JSON失败: {line}, 错误: {str(e)}"
                        )
                        continue
                    except Exception as e:
                        logger.error(f"[{request_id}] 处理流式数据异常: {str(e)}")
                        yield {"type": "error", "error": f"处理流式数据异常: {str(e)}"}
                        continue

        except asyncio.TimeoutError:
            error_msg = "流式API调用超时"
            logger.error(f"[{request_id}] {error_msg}")
            yield {"type": "error", "error": error_msg}
        except aiohttp.ClientConnectionError as e:
            error_msg = f"连接错误: {str(e)}"
            logger.error(f"[{request_id}] {error_msg}")
            yield {"type": "error", "error": error_msg}
        except aiohttp.ServerDisconnectedError as e:
            error_msg = f"服务器连接中断: {str(e)}"
            logger.error(f"[{request_id}] {error_msg}")
            yield {"type": "error", "error": error_msg}
        except aiohttp.ClientError as e:
            error_msg = f"客户端错误: {str(e)}"
            logger.error(f"[{request_id}] {error_msg}")
            yield {"type": "error", "error": error_msg}
        except Exception as e:
            logger.error(f"[{request_id}] 流式API调用异常: {str(e)}")
            yield {"type": "error", "error": f"流式API调用异常: {str(e)}"}
