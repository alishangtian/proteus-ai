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

                if model_type == "gemini":
                    if "candidates" in result and result["candidates"]:
                        text = result["candidates"][0]["content"]["parts"][0]["text"]
                        return text, usage
                    else:
                        raise ValueError("Gemini响应格式错误，未找到有效候选")
                else:
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
