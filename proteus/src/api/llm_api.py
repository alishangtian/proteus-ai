"""LLM API调用模块"""

import logging
import json
import asyncio
import aiohttp
import uuid
import base64
import threading
import time
import random
from pathlib import Path
from typing import List, Dict, Union, AsyncGenerator, Tuple

from src.api.model_manager import ModelManager
from src.utils.langfuse_wrapper import langfuse_wrapper


# 网络重试相关异常类型
NETWORK_EXCEPTIONS = (
    asyncio.TimeoutError,
    ConnectionError,
    OSError,
    aiohttp.ClientConnectionError,
    aiohttp.ServerDisconnectedError,
    aiohttp.ClientError,
    aiohttp.ClientPayloadError,
)

# 网络错误关键词（用于从通用 Exception 中识别网络相关错误）
NETWORK_ERROR_KEYWORDS = ["disconnected", "connection", "network", "timeout", "unreachable", "reset"]


def _calculate_retry_delay(attempt: int, base_delay: float = 1.0, max_delay: float = 30.0) -> float:
    """
    计算指数退避重试延迟（含随机抖动）

    网络切换场景下，指数退避比线性退避更合理：
    - 初始延迟较短，快速尝试恢复
    - 后续延迟指数增长，避免频繁重试
    - 随机抖动避免多个客户端同时重试导致的惊群效应

    Args:
        attempt: 当前重试次数（从0开始）
        base_delay: 基础延迟时间（秒），默认1秒
        max_delay: 最大延迟时间（秒），默认30秒

    Returns:
        实际等待的延迟时间（秒）
    """
    delay = min(base_delay * (2 ** attempt), max_delay)
    jitter = random.uniform(0, delay * 0.5)
    return delay + jitter


def _is_network_error(error: Exception) -> bool:
    """
    判断异常是否为网络相关错误

    Args:
        error: 异常实例

    Returns:
        是否为网络错误
    """
    return any(
        keyword in str(error).lower()
        for keyword in NETWORK_ERROR_KEYWORDS
    )


def _create_connector(force_dns_refresh: bool = False) -> aiohttp.TCPConnector:
    """
    创建 TCP 连接器

    每次重试时创建新的连接器，确保网络切换后使用新的连接池和 DNS 缓存。

    Args:
        force_dns_refresh: 是否强制刷新 DNS 缓存（重试时设为True）

    Returns:
        aiohttp.TCPConnector 实例
    """
    return aiohttp.TCPConnector(
        limit=10,
        limit_per_host=5,
        ttl_dns_cache=0 if force_dns_refresh else 300,
        use_dns_cache=not force_dns_refresh,
        keepalive_timeout=30,
        enable_cleanup_closed=True,
        force_close=force_dns_refresh,
    )


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
    long_message_tokens: int = 0,
) -> Tuple[str, Dict]:
    """
    调用llm API服务，支持自动重试

    Args:
        messages: 消息列表
        request_id: 请求ID,用于日志追踪
        temperature: 温度参数，控制输出的随机性，默认0.1
        output_json: 是否输出JSON结构,默认为False
        model_name: 模型名称，默认为 deepseek-chat
        long_message_tokens: 如果大于0，将在消息列表前追加一个大约包含该数量token的长消息

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
    # 请求参数（在重试循环外准备，避免重复构造）
    api_key = model_config["api_key"]
    req_headers = {
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
    if model_config["extra_params"] is not None:
        data.update(model_config["extra_params"])

    if output_json:
        data["response_format"] = {"type": "json_object"}

    url = f"{base_url}/chat/completions"

    # 重试配置
    max_retries = 5
    base_delay = 1.0  # 初始延迟1秒（指数退避）

    client_timeout = aiohttp.ClientTimeout(
        total=120,
        connect=10,
        sock_read=60,
    )

    for attempt in range(max_retries + 1):
        # 每次重试创建新的连接器和会话，确保网络切换后使用新的连接池
        conn = _create_connector(force_dns_refresh=(attempt > 0))
        try:
            async with aiohttp.ClientSession(
                connector=conn,
                timeout=client_timeout,
                read_bufsize=2**17,
                headers={"Connection": "keep-alive"},
            ) as session:
                async with session.post(
                    url,
                    headers=req_headers,
                    json=data,
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        current_logger.error(f"HTTP状态码: {response.status}")
                        current_logger.error(f"API调用失败: {error_text}")
                        raise ValueError(f"API调用失败: {error_text}")

                    result = await response.json()
                    current_logger.info(f"API调用成功")

                    usage: Dict = {}
                    if isinstance(result, dict):
                        usage = result.get("usage", {}) or {}

                    text = result["choices"][0]["message"]["content"]
                    return text, usage

        except NETWORK_EXCEPTIONS as e:
            if attempt < max_retries:
                delay = _calculate_retry_delay(attempt, base_delay)
                current_logger.warning(
                    f"API调用失败，第{attempt + 1}次重试，{delay:.1f}秒后重试。错误: {str(e)}"
                )
                await asyncio.sleep(delay)
            else:
                current_logger.error(
                    f"API调用失败，已达到最大重试次数{max_retries}。错误: {str(e)}"
                )
                if isinstance(e, asyncio.TimeoutError):
                    raise ValueError("API调用超时")
                else:
                    raise ConnectionError(f"网络连接异常: {str(e)}")
        except Exception as e:
            current_logger.error(f"API调用异常: {str(e)}")
            if _is_network_error(e):
                if attempt < max_retries:
                    delay = _calculate_retry_delay(attempt, base_delay)
                    current_logger.warning(
                        f"网络异常，第{attempt + 1}次重试，{delay:.1f}秒后重试。错误: {str(e)}"
                    )
                    await asyncio.sleep(delay)
                else:
                    current_logger.error(
                        f"API调用失败，已达到最大重试次数{max_retries}。错误: {str(e)}"
                    )
                    raise ConnectionError(f"网络连接异常: {str(e)}")
            else:
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
        model_name = "gemini-3-flash-preview"
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
    # 请求参数（在重试循环外准备，避免重复构造）
    api_key = model_config["api_key"]
    req_headers = {
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
    if model_config["extra_params"] is not None:
        data.update(model_config["extra_params"])
    if output_json:
        data["response_format"] = {"type": "json_object"}

    url = f"{base_url}/chat/completions"

    # 重试配置
    max_retries = 5
    base_delay = 1.0  # 初始延迟1秒（指数退避）

    client_timeout = aiohttp.ClientTimeout(
        total=120,
        connect=10,
        sock_read=60,
    )

    for attempt in range(max_retries + 1):
        # 每次重试创建新的连接器和会话，确保网络切换后使用新的连接池
        conn = _create_connector(force_dns_refresh=(attempt > 0))
        try:
            async with aiohttp.ClientSession(
                connector=conn,
                timeout=client_timeout,
                read_bufsize=2**17,
                headers={"Connection": "keep-alive"},
            ) as session:
                async with session.post(
                    url,
                    headers=req_headers,
                    json=data,
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        current_logger.error(f"HTTP状态码: {response.status}")
                        current_logger.error(f"API调用失败: {error_text}")
                        raise ValueError(f"API调用失败: {error_text}")

                    result = await response.json()
                    current_logger.info(f"API调用成功")

                    usage: Dict = {}
                    if isinstance(result, dict):
                        usage = result.get("usage", {}) or {}

                    text = result["choices"][0]["message"]["content"]
                    return text, usage

        except NETWORK_EXCEPTIONS as e:
            if attempt < max_retries:
                delay = _calculate_retry_delay(attempt, base_delay)
                current_logger.warning(
                    f"API调用失败，第{attempt + 1}次重试，{delay:.1f}秒后重试。错误: {str(e)}"
                )
                await asyncio.sleep(delay)
            else:
                current_logger.error(
                    f"API调用失败，已达到最大重试次数{max_retries}。错误: {str(e)}"
                )
                if isinstance(e, asyncio.TimeoutError):
                    raise ValueError("API调用超时")
                else:
                    raise ConnectionError(f"网络连接异常: {str(e)}")
        except Exception as e:
            current_logger.error(f"API调用异常: {str(e)}")
            if _is_network_error(e):
                if attempt < max_retries:
                    delay = _calculate_retry_delay(attempt, base_delay)
                    current_logger.warning(
                        f"网络异常，第{attempt + 1}次重试，{delay:.1f}秒后重试。错误: {str(e)}"
                    )
                    await asyncio.sleep(delay)
                else:
                    current_logger.error(
                        f"API调用失败，已达到最大重试次数{max_retries}。错误: {str(e)}"
                    )
                    raise ConnectionError(f"网络连接异常: {str(e)}")
            else:
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

    # 请求参数（在重试循环外准备，避免重复构造）
    api_key = model_config["api_key"]
    req_headers = {
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
    if model_config["extra_params"] is not None:
        data.update(model_config["extra_params"])

    if output_json:
        data["response_format"] = {"type": "json_object"}

    url = f"{base_url}/chat/completions"

    # 重试配置
    max_retries = 5
    base_delay = 1.0  # 初始延迟1秒（指数退避）

    client_timeout = aiohttp.ClientTimeout(
        total=300,  # 流式调用需要更长的超时时间
        connect=10,
        sock_read=120,
    )

    for attempt in range(max_retries + 1):
        # 每次重试创建新的连接器和会话，确保网络切换后使用新的连接池
        conn = _create_connector(force_dns_refresh=(attempt > 0))
        try:
            async with aiohttp.ClientSession(
                connector=conn,
                timeout=client_timeout,
                read_bufsize=2**17,
                headers={"Connection": "keep-alive"},
            ) as session:
                async with session.post(
                    url,
                    headers=req_headers,
                    json=data,
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        current_logger.error(f"API调用失败: {error_text}")

                        # 分析错误类型
                        error_type = await _analyze_error(error_text)
                        current_logger.info(f"错误分析结果: {error_type}")

                        yield {
                            "type": "error",
                            "error": f"API调用失败: {error_text}",
                            "error_type": error_type,
                        }
                        return

                    current_logger.info(f"流式API调用开始接收数据")

                    # 用于累积完整的usage信息
                    accumulated_usage = {}
                    is_thinking = False

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

                                # 处理thinking内容
                                reasoning_content = delta.get("reasoning_content")
                                reasoning = delta.get("reasoning")
                                if (reasoning and reasoning != "") or (
                                    reasoning_content and reasoning_content != ""
                                ):
                                    is_thinking = True
                                    if reasoning and reasoning != "":
                                        yield {
                                            "type": "thinking",
                                            "content": reasoning,
                                        }
                                    if reasoning_content and reasoning_content != "":
                                        yield {
                                            "type": "thinking",
                                            "content": reasoning_content,
                                        }

                                # 处理普通内容
                                if "content" in delta:
                                    content = delta["content"]
                                    if content:
                                        if is_thinking:
                                            yield {
                                                "type": "thinking",
                                                "content": "",
                                                "is_end": True,
                                            }
                                            is_thinking = False
                                        yield {"type": "content", "content": content}

                                # 检查是否完成
                                if choice.get("finish_reason") == "stop":
                                    if is_thinking:
                                        yield {
                                            "type": "thinking",
                                            "content": "",
                                            "is_end": True,
                                        }
                                        is_thinking = False
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

        except NETWORK_EXCEPTIONS as e:
            if attempt < max_retries:
                delay = _calculate_retry_delay(attempt, base_delay)
                current_logger.warning(
                    f"流式API调用失败，第{attempt + 1}次重试，{delay:.1f}秒后重试。错误: {str(e)}"
                )
                yield {
                    "type": "retry",
                    "error": f"网络异常，{delay:.1f}秒后重试。",
                }
                await asyncio.sleep(delay)
            else:
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
            if _is_network_error(e):
                if attempt < max_retries:
                    delay = _calculate_retry_delay(attempt, base_delay)
                    current_logger.warning(
                        f"网络异常，第{attempt + 1}次重试，{delay:.1f}秒后重试。错误: {str(e)}"
                    )
                    yield {
                        "type": "retry",
                        "error": f"网络异常，{delay:.1f}秒后重试。",
                    }
                    await asyncio.sleep(delay)
                else:
                    current_logger.error(
                        f"流式API调用失败，已达到最大重试次数{max_retries}。错误: {str(e)}"
                    )
                    yield {"type": "error", "error": f"网络连接异常: {str(e)}"}
                    return
            else:
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

    # 请求参数（在重试循环外准备，避免重复构造）
    api_key = model_config["api_key"]
    req_headers = {
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
    if model_config["extra_params"] is not None:
        data.update(model_config["extra_params"])

    # 如果提供了工具定义，添加到请求中
    if tools:
        data["tools"] = tools

    url = f"{base_url}/chat/completions"

    # 重试配置
    max_retries = 5
    base_delay = 1.0  # 初始延迟1秒（指数退避）

    client_timeout = aiohttp.ClientTimeout(
        total=120,
        connect=10,
        sock_read=60,
    )

    for attempt in range(max_retries + 1):
        # 每次重试创建新的连接器和会话，确保网络切换后使用新的连接池
        conn = _create_connector(force_dns_refresh=(attempt > 0))
        try:
            async with aiohttp.ClientSession(
                connector=conn,
                timeout=client_timeout,
                read_bufsize=2**17,
                headers={"Connection": "keep-alive"},
            ) as session:
                async with session.post(
                    url,
                    headers=req_headers,
                    json=data,
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        current_logger.error(f"HTTP状态码: {response.status}")
                        current_logger.error(f"API调用失败: {error_text}")
                        raise ValueError(f"API调用失败: {error_text}")

                    result = await response.json()
                    current_logger.info(f"API调用成功")

                    usage: Dict = {}
                    if isinstance(result, dict):
                        usage = result.get("usage", {}) or {}

                    message = result["choices"][0]["message"]
                    return message, usage

        except NETWORK_EXCEPTIONS as e:
            if attempt < max_retries:
                delay = _calculate_retry_delay(attempt, base_delay)
                current_logger.warning(
                    f"API调用失败，第{attempt + 1}次重试，{delay:.1f}秒后重试。错误: {str(e)}"
                )
                await asyncio.sleep(delay)
            else:
                current_logger.error(
                    f"API调用失败，已达到最大重试次数{max_retries}。错误: {str(e)}"
                )
                if isinstance(e, asyncio.TimeoutError):
                    raise ValueError("API调用超时")
                else:
                    raise ConnectionError(f"网络连接异常: {str(e)}")
        except Exception as e:
            current_logger.error(f"API调用异常: {str(e)}")
            if _is_network_error(e):
                if attempt < max_retries:
                    delay = _calculate_retry_delay(attempt, base_delay)
                    current_logger.warning(
                        f"网络异常，第{attempt + 1}次重试，{delay:.1f}秒后重试。错误: {str(e)}"
                    )
                    await asyncio.sleep(delay)
                else:
                    current_logger.error(
                        f"API调用失败，已达到最大重试次数{max_retries}。错误: {str(e)}"
                    )
                    raise ConnectionError(f"网络连接异常: {str(e)}")
            else:
                raise


@langfuse_wrapper.dynamic_observe()
async def _analyze_error(error_text: str) -> str:
    """
    使用 LLM 分析错误类型

    Args:
        error_text: 错误信息文本

    Returns:
        错误类型字符串
    """
    try:
        prompt = f"""请分析以下 API 错误信息，并将其分类为以下三种类型之一：
1. token_limit_exceeded (token 超限)
2. rate_limit_exceeded (tpm 或者 rpm 超限)
3. invalid_api_key (api_key无效)
4. other (其他错误)

错误信息：
{error_text}

请只返回分类代码（例如：token_limit_exceeded），不要返回其他内容。"""

        messages = [{"role": "user", "content": prompt}]
        # 强制使用 deepseek-chat
        response_text, _ = await call_llm_api(
            messages=messages, model_name="deepseek-chat", temperature=0.1
        )
        return response_text.strip()
    except Exception as e:
        # 避免循环依赖或递归错误导致崩溃，记录日志并返回 other
        logging.getLogger(__name__).error(f"错误分析失败: {e}")
        return "other"


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

    # 请求参数（在重试循环外准备，避免重复构造）
    api_key = model_config["api_key"]
    req_headers = {
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
    if model_config["extra_params"] is not None:
        data.update(model_config["extra_params"])

    # 如果提供了工具定义，添加到请求中
    if tools:
        data["tools"] = tools

    url = f"{base_url}/chat/completions"

    # 重试配置
    max_retries = 5
    base_delay = 1.0  # 初始延迟1秒（指数退避）

    client_timeout = aiohttp.ClientTimeout(
        total=300,  # 流式调用需要更长的超时时间
        connect=10,
        sock_read=120,
    )

    for attempt in range(max_retries + 1):
        # 每次重试创建新的连接器和会话，确保网络切换后使用新的连接池
        conn = _create_connector(force_dns_refresh=(attempt > 0))
        try:
            async with aiohttp.ClientSession(
                connector=conn,
                timeout=client_timeout,
                read_bufsize=2**17,
                headers={"Connection": "keep-alive"},
            ) as session:
                async with session.post(
                    url,
                    headers=req_headers,
                    json=data,
                ) as response:
                    current_logger.info(f"response.status = {response.status}")
                    if response.status != 200:
                        error_text = await response.text()
                        current_logger.error(f"API调用失败: {error_text}")
                        # 分析错误类型
                        error_type = await _analyze_error(error_text)
                        current_logger.info(f"错误分析结果: {error_type}")

                        yield {
                            "type": "error",
                            "error": f"API调用失败: {error_text}",
                            "error_type": error_type,
                        }
                        return

                    current_logger.info(f"流式API调用开始接收数据")

                    # 用于累积完整的usage信息和工具调用
                    accumulated_usage = {}
                    accumulated_tool_calls = []
                    is_thinking = False

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
                                # 安全地获取 reasoning_content 和 reasoning 字段
                                reasoning_content = delta.get("reasoning_content")
                                reasoning = delta.get("reasoning")
                                reasoning_details = delta.get("reasoning_details")

                                if (reasoning_content and reasoning_content != "") or (
                                    reasoning and reasoning != ""
                                ):
                                    is_thinking = True
                                    if reasoning_content and reasoning_content != "":
                                        yield {
                                            "type": "thinking",
                                            "thinking_type": "reasoning_content",
                                            "content": reasoning_content,
                                        }

                                    if reasoning and reasoning != "":
                                        yield {
                                            "type": "thinking",
                                            "thinking_type": "reasoning",
                                            "content": reasoning,
                                        }
                                if reasoning_details and reasoning_details[0]:
                                    yield {
                                        "type": "reasoning_details",
                                        "content": reasoning_details,
                                    }

                                # 处理普通内容
                                if "content" in delta:
                                    content = delta["content"]
                                    if content:
                                        if is_thinking:
                                            yield {
                                                "type": "thinking",
                                                "content": "",
                                                "is_end": True,
                                            }
                                            is_thinking = False
                                        yield {"type": "content", "content": content}

                                # 处理工具调用
                                if "tool_calls" in delta:
                                    if is_thinking:
                                        yield {
                                            "type": "thinking",
                                            "content": "",
                                            "is_end": True,
                                        }
                                        is_thinking = False
                                    tool_calls = delta["tool_calls"]
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
                                                tool_call_id = tool_call["id"]
                                                if (
                                                    not tool_call_id
                                                    or tool_call_id == ""
                                                ):
                                                    tool_call_id = str(uuid.uuid4())
                                                accumulated_tool_calls[index][
                                                    "id"
                                                ] = tool_call_id
                                            if "type" in tool_call:
                                                accumulated_tool_calls[index][
                                                    "type"
                                                ] = tool_call["type"]
                                            if "function" in tool_call:
                                                func = tool_call["function"]
                                                if (
                                                    "name" in func
                                                    and func["name"]
                                                    and func["name"] != ""
                                                ):
                                                    accumulated_tool_calls[index][
                                                        "function"
                                                    ]["name"] = func["name"]
                                                if (
                                                    "arguments" in func
                                                    and func["arguments"]
                                                    and func["arguments"] != ""
                                                ):
                                                    accumulated_tool_calls[index][
                                                        "function"
                                                    ]["arguments"] += func["arguments"]

                                # 检查是否完成
                                if choice.get("finish_reason") in [
                                    "stop",
                                    "tool_calls",
                                ]:
                                    if is_thinking:
                                        yield {
                                            "type": "thinking",
                                            "content": "",
                                            "is_end": True,
                                        }
                                        is_thinking = False
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

        except NETWORK_EXCEPTIONS as e:
            if attempt < max_retries:
                delay = _calculate_retry_delay(attempt, base_delay)
                current_logger.warning(
                    f"流式API调用失败，第{attempt + 1}次重试，{delay:.1f}秒后重试。错误: {str(e)}"
                )
                yield {
                    "type": "retry",
                    "error": f"网络异常，{delay:.1f}秒后重试。",
                }
                await asyncio.sleep(delay)
            else:
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
            if _is_network_error(e):
                if attempt < max_retries:
                    delay = _calculate_retry_delay(attempt, base_delay)
                    current_logger.warning(
                        f"网络异常，第{attempt + 1}次重试，{delay:.1f}秒后重试。错误: {str(e)}"
                    )
                    yield {
                        "type": "retry",
                        "error": f"网络异常，{delay:.1f}秒后重试。",
                    }
                    await asyncio.sleep(delay)
                else:
                    current_logger.error(
                        f"流式API调用失败，已达到最大重试次数{max_retries}。错误: {str(e)}"
                    )
                    yield {"type": "error", "error": f"网络连接异常: {str(e)}"}
                    return
            else:
                current_logger.error(f"非网络异常: {str(e)}")
                yield {"type": "error", "error": f"流式API调用异常: {str(e)}"}
                return
