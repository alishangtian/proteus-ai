"""LLM API调用模块"""

import logging
import json
import asyncio
import aiohttp
import base64
import os
import threading
import time
from pathlib import Path
from typing import List, Dict, Union, AsyncGenerator, Tuple
from datetime import timedelta

from .config import API_CONFIG, retry_on_error
from .model_manager import ModelManager
from ..utils.langfuse_wrapper import langfuse_wrapper


class RequestLogManager:
    """基于request_id的日志管理器，为每个request_id创建独立的日志文件"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self.loggers = {}
        self.log_dir = Path("logs/llm_requests")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.cleanup_interval = 3600  # 1小时清理一次
        self.max_log_age = 24 * 3600  # 日志文件保留24小时
        self.last_cleanup = time.time()

        # 创建默认logger（用于没有request_id的情况）
        self.default_logger = logging.getLogger(__name__)

    def get_logger(self, request_id: str = None) -> logging.Logger:
        """获取指定request_id的logger"""
        if not request_id:
            return self.default_logger

        # 定期清理过期日志文件
        self._cleanup_old_logs()

        if request_id not in self.loggers:
            with self._lock:
                if request_id not in self.loggers:
                    self._create_logger(request_id)

        return self.loggers[request_id]

    def _create_logger(self, request_id: str):
        """为指定request_id创建logger"""
        logger_name = f"llm_api.{request_id}"
        logger = logging.getLogger(logger_name)

        # 避免重复添加handler
        if logger.handlers:
            self.loggers[request_id] = logger
            return

        logger.setLevel(logging.INFO)

        # 创建文件handler
        log_file = self.log_dir / f"{request_id}.log"
        file_handler = logging.FileHandler(log_file, encoding="utf-8")

        # 设置日志格式
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(formatter)

        logger.addHandler(file_handler)

        # 防止日志向上传播到根logger
        logger.propagate = False

        self.loggers[request_id] = logger

    def _cleanup_old_logs(self):
        """清理过期的日志文件和logger"""
        current_time = time.time()

        # 检查是否需要清理
        if current_time - self.last_cleanup < self.cleanup_interval:
            return

        self.last_cleanup = current_time

        # 清理过期的日志文件
        for log_file in self.log_dir.glob("*.log"):
            if current_time - log_file.stat().st_mtime > self.max_log_age:
                try:
                    log_file.unlink()
                    # 同时清理对应的logger
                    request_id = log_file.stem
                    if request_id in self.loggers:
                        logger = self.loggers[request_id]
                        # 关闭所有handlers
                        for handler in logger.handlers[:]:
                            handler.close()
                            logger.removeHandler(handler)
                        del self.loggers[request_id]
                except Exception as e:
                    self.default_logger.warning(
                        f"清理日志文件失败: {log_file}, 错误: {e}"
                    )

    def close_logger(self, request_id: str):
        """手动关闭指定request_id的logger"""
        if request_id in self.loggers:
            logger = self.loggers[request_id]
            for handler in logger.handlers[:]:
                handler.close()
                logger.removeHandler(handler)
            del self.loggers[request_id]


# 创建全局日志管理器实例
log_manager = RequestLogManager()

# 配置日志记录 - 保持向后兼容
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


@langfuse_wrapper.dynamic_observe()
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
    # 获取专用的logger
    current_logger = log_manager.get_logger(request_id)

    current_logger.info(f"开始调用llm API")
    if model_name is None:
        model_name = "deepseek-chat"
    messages_length = calculate_messages_length(messages)
    current_logger.info(
        f"请求参数: model={model_name}, "
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
        current_logger.error(f"模型配置有误，model_name:{model_name} \n{str(e)}")
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

        # 重试配置
        max_retries = 10
        base_delay = 10  # 初始延迟10秒

        for attempt in range(max_retries + 1):
            try:
                async with session.post(
                    url,
                    headers=headers,
                    json=data,
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        current_logger.error(f"HTTP状态码: {response.status}")
                        current_logger.error(f"API调用失败: {error_text}")
                        # 对于HTTP错误，不重试，直接抛出异常
                        raise ValueError(f"API调用失败: {error_text}")

                    result = await response.json()
                    current_logger.info(f"API调用成功")

                    # 根据模型类型解析不同响应格式并提取usage信息（若存在）
                    usage: Dict = {}
                    if isinstance(result, dict):
                        usage = result.get("usage", {}) or {}

                    text = result["choices"][0]["message"]["content"]
                    return text, usage

            except (
                asyncio.TimeoutError,
                ConnectionError,
                aiohttp.ClientConnectionError,
                aiohttp.ServerDisconnectedError,
                aiohttp.ClientError,
            ) as e:
                # 这些是网络相关异常，进行重试
                if attempt < max_retries:
                    delay = base_delay * (attempt + 1)  # 每次重试延迟增加10秒
                    current_logger.warning(
                        f"API调用失败，第{attempt + 1}次重试，{delay}秒后重试。错误: {str(e)}"
                    )
                    await asyncio.sleep(delay)
                else:
                    # 达到最大重试次数，抛出异常
                    current_logger.error(
                        f"API调用失败，已达到最大重试次数{max_retries}。错误: {str(e)}"
                    )
                    if isinstance(e, asyncio.TimeoutError):
                        raise ValueError("API调用超时")
                    else:
                        raise ConnectionError(f"网络连接异常: {str(e)}")
            except Exception as e:
                current_logger.error(f"API调用异常: {str(e)}")
                # 对于其他异常，如果是网络相关的，转换为ConnectionError以便重试
                if any(
                    keyword in str(e).lower()
                    for keyword in ["disconnected", "connection", "network", "timeout"]
                ):
                    if attempt < max_retries:
                        delay = base_delay * (attempt + 1)
                        current_logger.warning(
                            f"网络异常，第{attempt + 1}次重试，{delay}秒后重试。错误: {str(e)}"
                        )
                        await asyncio.sleep(delay)
                    else:
                        current_logger.error(
                            f"API调用失败，已达到最大重试次数{max_retries}。错误: {str(e)}"
                        )
                        raise ConnectionError(f"网络连接异常: {str(e)}")
                else:
                    # 非网络异常，不重试，直接抛出
                    raise


@langfuse_wrapper.dynamic_observe()
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
    # 获取专用的logger
    current_logger = log_manager.get_logger(request_id)

    current_logger.info(f"开始调用多模态llm API")
    if model_name is None:
        model_name = "gemini-2.5-flash"
    messages_length = calculate_messages_length(
        messages
    )  # 仍然使用原有的长度计算，图片长度暂时忽略
    current_logger.info(
        f"请求参数: model={model_name}, "
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
        current_logger.error(f"模型配置有误，model_name:{model_name} \n{str(e)}")
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

        # 重试配置
        max_retries = 10
        base_delay = 10  # 初始延迟10秒

        for attempt in range(max_retries + 1):
            try:
                async with session.post(
                    url,
                    headers=headers,
                    json=data,
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        current_logger.error(f"HTTP状态码: {response.status}")
                        current_logger.error(f"API调用失败: {error_text}")
                        # 对于HTTP错误，不重试，直接抛出异常
                        raise ValueError(f"API调用失败: {error_text}")

                    result = await response.json()
                    current_logger.info(f"API调用成功")

                    # 根据模型类型解析不同响应格式并提取usage信息（若存在）
                    usage: Dict = {}
                    if isinstance(result, dict):
                        usage = result.get("usage", {}) or {}

                    text = result["choices"][0]["message"]["content"]
                    return text, usage

            except (
                asyncio.TimeoutError,
                ConnectionError,
                aiohttp.ClientConnectionError,
                aiohttp.ServerDisconnectedError,
                aiohttp.ClientError,
            ) as e:
                # 这些是网络相关异常，进行重试
                if attempt < max_retries:
                    delay = base_delay * (attempt + 1)  # 每次重试延迟增加10秒
                    current_logger.warning(
                        f"API调用失败，第{attempt + 1}次重试，{delay}秒后重试。错误: {str(e)}"
                    )
                    await asyncio.sleep(delay)
                else:
                    # 达到最大重试次数，抛出异常
                    current_logger.error(
                        f"API调用失败，已达到最大重试次数{max_retries}。错误: {str(e)}"
                    )
                    if isinstance(e, asyncio.TimeoutError):
                        raise ValueError("API调用超时")
                    else:
                        raise ConnectionError(f"网络连接异常: {str(e)}")
            except Exception as e:
                current_logger.error(f"API调用异常: {str(e)}")
                # 对于其他异常，如果是网络相关的，转换为ConnectionError以便重试
                if any(
                    keyword in str(e).lower()
                    for keyword in ["disconnected", "connection", "network", "timeout"]
                ):
                    if attempt < max_retries:
                        delay = base_delay * (attempt + 1)
                        current_logger.warning(
                            f"网络异常，第{attempt + 1}次重试，{delay}秒后重试。错误: {str(e)}"
                        )
                        await asyncio.sleep(delay)
                    else:
                        current_logger.error(
                            f"API调用失败，已达到最大重试次数{max_retries}。错误: {str(e)}"
                        )
                        raise ConnectionError(f"网络连接异常: {str(e)}")
                else:
                    # 非网络异常，不重试，直接抛出
                    raise


@langfuse_wrapper.dynamic_observe()
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
    # 获取专用的logger
    current_logger = log_manager.get_logger(request_id)

    current_logger.info(f"开始调用流式llm API (thinking模式: {enable_thinking})")
    if model_name is None:
        model_name = "deepseek-chat"

    messages_length = calculate_messages_length(messages)
    current_logger.info(
        f"请求参数: model={model_name}, "
        f"temperature={temperature}, "
        f"messages_count={len(messages)}, "
        f"messages_length={messages_length}, "
        f"enable_thinking={enable_thinking}"
    )

    # 获取模型配置
    try:
        model_config = ModelManager().get_model_config(model_name)
        base_url = model_config["base_url"]
        model_name = model_config["model_name"]
    except Exception as e:
        current_logger.error(f"模型配置有误，model_name:{model_name} \n{str(e)}")
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

        # 重试配置
        max_retries = 10
        base_delay = 10  # 初始延迟10秒

        for attempt in range(max_retries + 1):
            try:
                async with session.post(
                    url,
                    headers=headers,
                    json=data,
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        current_logger.error(f"API调用失败: {error_text}")
                        # 对于HTTP错误，不重试，直接抛出异常
                        raise ValueError(f"API调用失败: {error_text}")

                    current_logger.info(f"流式API调用开始接收数据")

                    # 用于累积完整的usage信息
                    accumulated_usage = {}

                    async for line in response.content:
                        line = line.decode("utf-8").strip()

                        if not line or line == "data: [DONE]":
                            continue

                        if line.startswith("data: "):
                            line = line[6:]  # 移除 "data: " 前缀

                        current_logger.info(f"接收到数据:{line}")
                        try:
                            chunk = json.loads(line)

                            # 提取usage信息（如果存在）
                            if "usage" in chunk:
                                accumulated_usage = chunk["usage"]
                                # 返回usage信息
                                if accumulated_usage:
                                    yield {"type": "usage", "usage": accumulated_usage}

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
                                    current_logger.info(f"流式API调用完成")
                                    return  # 成功完成，退出函数

                        except json.JSONDecodeError as e:
                            current_logger.warning(
                                f"解析JSON失败: {line}, 错误: {str(e)}"
                            )
                            # yield {"type": "content", "content": line}
                            continue
                        except Exception as e:
                            current_logger.error(f"处理流式数据异常: {str(e)}")
                            yield {
                                "type": "error",
                                "error": f"处理流式数据异常: {str(e)}",
                            }
                            continue

            except (
                asyncio.TimeoutError,
                ConnectionError,
                aiohttp.ClientConnectionError,
                aiohttp.ServerDisconnectedError,
                aiohttp.ClientError,
            ) as e:
                # 这些是网络相关异常，进行重试
                if attempt < max_retries:
                    delay = base_delay * (attempt + 1)  # 每次重试延迟增加10秒
                    current_logger.warning(
                        f"流式API调用失败，第{attempt + 1}次重试，{delay}秒后重试。错误: {str(e)}"
                    )
                    yield {
                        "type": "retry",
                        "error": f"网络异常，{delay}秒后重试。",
                    }
                    await asyncio.sleep(delay)
                else:
                    # 达到最大重试次数，抛出异常
                    current_logger.error(
                        f"流式API调用失败，已达到最大重试次数{max_retries}。错误: {str(e)}"
                    )
                    if isinstance(e, asyncio.TimeoutError):
                        yield {"type": "error", "error": "流式API调用超时"}
                    else:
                        yield {"type": "error", "error": f"网络连接异常: {str(e)}"}
                    return
            except Exception as e:
                current_logger.error(f"流式API调用异常: {str(e)}")
                # 对于其他异常，如果是网络相关的，转换为ConnectionError以便重试
                if any(
                    keyword in str(e).lower()
                    for keyword in ["disconnected", "connection", "network", "timeout"]
                ):
                    if attempt < max_retries:
                        delay = base_delay * (attempt + 1)
                        current_logger.warning(
                            f"网络异常，第{attempt + 1}次重试，{delay}秒后重试。错误: {str(e)}"
                        )
                        yield {
                            "type": "retry",
                            "error": f"网络异常，{delay}秒后重试。",
                        }
                        await asyncio.sleep(delay)
                    else:
                        current_logger.error(
                            f"流式API调用失败，已达到最大重试次数{max_retries}。错误: {str(e)}"
                        )
                        yield {"type": "error", "error": f"网络连接异常: {str(e)}"}
                        return
                else:
                    # 非网络异常，不重试，直接抛出
                    current_logger.error(f"非网络异常: {str(e)}")
                    yield {"type": "error", "error": f"流式API调用异常: {str(e)}"}
                    return


@langfuse_wrapper.dynamic_observe()
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
    # 获取专用的logger
    current_logger = log_manager.get_logger(request_id)

    current_logger.info(f"开始调用支持工具的 LLM API（非流式）")
    if model_name is None:
        model_name = "deepseek-chat"

    messages_length = calculate_messages_length(messages)
    current_logger.info(
        f"请求参数: model={model_name}, "
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
        current_logger.error(f"模型配置有误，model_name:{model_name} \n{str(e)}")
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

        # 重试配置
        max_retries = 10
        base_delay = 10  # 初始延迟10秒

        for attempt in range(max_retries + 1):
            try:
                async with session.post(
                    url,
                    headers=headers,
                    json=data,
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        current_logger.error(f"HTTP状态码: {response.status}")
                        current_logger.error(f"API调用失败: {error_text}")
                        # 对于HTTP错误，不重试，直接抛出异常
                        raise ValueError(f"API调用失败: {error_text}")

                    result = await response.json()
                    current_logger.info(f"API调用成功")

                    # 提取usage信息
                    usage: Dict = {}
                    if isinstance(result, dict):
                        usage = result.get("usage", {}) or {}

                    # 返回完整的消息对象
                    message = result["choices"][0]["message"]
                    return message, usage

            except (
                asyncio.TimeoutError,
                ConnectionError,
                aiohttp.ClientConnectionError,
                aiohttp.ServerDisconnectedError,
                aiohttp.ClientError,
            ) as e:
                # 这些是网络相关异常，进行重试
                if attempt < max_retries:
                    delay = base_delay * (attempt + 1)  # 每次重试延迟增加10秒
                    current_logger.warning(
                        f"API调用失败，第{attempt + 1}次重试，{delay}秒后重试。错误: {str(e)}"
                    )
                    await asyncio.sleep(delay)
                else:
                    # 达到最大重试次数，抛出异常
                    current_logger.error(
                        f"API调用失败，已达到最大重试次数{max_retries}。错误: {str(e)}"
                    )
                    if isinstance(e, asyncio.TimeoutError):
                        raise ValueError("API调用超时")
                    else:
                        raise ConnectionError(f"网络连接异常: {str(e)}")
            except Exception as e:
                current_logger.error(f"API调用异常: {str(e)}")
                # 对于其他异常，如果是网络相关的，转换为ConnectionError以便重试
                if any(
                    keyword in str(e).lower()
                    for keyword in ["disconnected", "connection", "network", "timeout"]
                ):
                    if attempt < max_retries:
                        delay = base_delay * (attempt + 1)
                        current_logger.warning(
                            f"网络异常，第{attempt + 1}次重试，{delay}秒后重试。错误: {str(e)}"
                        )
                        await asyncio.sleep(delay)
                    else:
                        current_logger.error(
                            f"API调用失败，已达到最大重试次数{max_retries}。错误: {str(e)}"
                        )
                        raise ConnectionError(f"网络连接异常: {str(e)}")
                else:
                    # 非网络异常，不重试，直接抛出
                    raise


@langfuse_wrapper.dynamic_observe()
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
    # 获取专用的logger
    current_logger = log_manager.get_logger(request_id)

    current_logger.info(f"开始调用支持工具的 LLM API（流式）")
    if model_name is None:
        model_name = "deepseek-chat"

    messages_length = calculate_messages_length(messages)
    current_logger.info(
        f"请求参数: model={model_name}, "
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
        current_logger.error(f"模型配置有误，model_name:{model_name} \n{str(e)}")
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

        # 重试配置
        max_retries = 10
        base_delay = 10  # 初始延迟10秒

        for attempt in range(max_retries + 1):
            try:
                async with session.post(
                    url,
                    headers=headers,
                    json=data,
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        current_logger.error(f"API调用失败: {error_text}")
                        # 对于HTTP错误，不重试，直接抛出异常
                        raise ValueError(f"API调用失败: {error_text}")

                    current_logger.info(f"流式API调用开始接收数据")

                    # 用于累积完整的usage信息和工具调用
                    accumulated_usage = {}
                    accumulated_tool_calls = []

                    async for line in response.content:
                        line = line.decode("utf-8").strip()

                        if not line or line == "data: [DONE]":
                            continue

                        if line.startswith("data: "):
                            line = line[6:]  # 移除 "data: " 前缀
                        current_logger.info(f"接收到数据:{line}")
                        try:
                            chunk = json.loads(line)

                            # 提取usage信息（如果存在）
                            if "usage" in chunk:
                                accumulated_usage = chunk["usage"]
                                if accumulated_usage:
                                    yield {"type": "usage", "usage": accumulated_usage}

                            # 处理choices中的内容
                            if "choices" in chunk and len(chunk["choices"]) > 0:
                                choice = chunk["choices"][0]
                                current_logger.info(f"响应内容: {choice}")
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
                                                accumulated_tool_calls[index][
                                                    "type"
                                                ] = tool_call["type"]
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
                                if choice.get("finish_reason") in [
                                    "stop",
                                    "tool_calls",
                                ]:
                                    current_logger.info(
                                        f"流式API调用完成，finish_reason: {choice.get('finish_reason')}"
                                    )

                                    # 如果有工具调用，返回完整的工具调用信息
                                    if accumulated_tool_calls:
                                        yield {
                                            "type": "tool_calls",
                                            "tool_calls": accumulated_tool_calls,
                                        }
                                    return  # 成功完成，退出函数

                        except json.JSONDecodeError as e:
                            current_logger.warning(
                                f"解析JSON失败: {line}, 错误: {str(e)}"
                            )
                            # yield {"type": "content", "content": line}
                            continue
                        except Exception as e:
                            current_logger.error(f"处理流式数据异常: {str(e)}")
                            yield {
                                "type": "error",
                                "error": f"处理流式数据异常: {str(e)}",
                            }
                            continue

            except (
                asyncio.TimeoutError,
                ConnectionError,
                aiohttp.ClientConnectionError,
                aiohttp.ServerDisconnectedError,
                aiohttp.ClientError,
            ) as e:
                # 这些是网络相关异常，进行重试
                if attempt < max_retries:
                    delay = base_delay * (attempt + 1)  # 每次重试延迟增加10秒
                    current_logger.warning(
                        f"流式API调用失败，第{attempt + 1}次重试，{delay}秒后重试。错误: {str(e)}"
                    )
                    yield {
                        "type": "retry",
                        "error": f"网络异常，{delay}秒后重试。",
                    }
                    await asyncio.sleep(delay)
                else:
                    # 达到最大重试次数，抛出异常
                    current_logger.error(
                        f"流式API调用失败，已达到最大重试次数{max_retries}。错误: {str(e)}"
                    )
                    if isinstance(e, asyncio.TimeoutError):
                        yield {"type": "error", "error": "流式API调用超时"}
                    else:
                        yield {"type": "error", "error": f"网络连接异常: {str(e)}"}
                    return
            except Exception as e:
                current_logger.error(f"流式API调用异常: {str(e)}")
                # 对于其他异常，如果是网络相关的，转换为ConnectionError以便重试
                if any(
                    keyword in str(e).lower()
                    for keyword in ["disconnected", "connection", "network", "timeout"]
                ):
                    if attempt < max_retries:
                        delay = base_delay * (attempt + 1)
                        current_logger.warning(
                            f"网络异常，第{attempt + 1}次重试，{delay}秒后重试。错误: {str(e)}"
                        )
                        yield {
                            "type": "retry",
                            "error": f"网络异常，{delay}秒后重试。",
                        }
                        await asyncio.sleep(delay)
                    else:
                        current_logger.error(
                            f"流式API调用失败，已达到最大重试次数{max_retries}。错误: {str(e)}"
                        )
                        yield {"type": "error", "error": f"网络连接异常: {str(e)}"}
                        return
                else:
                    # 非网络异常，不重试，直接抛出
                    current_logger.error(f"非网络异常: {str(e)}")
                    yield {"type": "error", "error": f"流式API调用异常: {str(e)}"}
                    return
