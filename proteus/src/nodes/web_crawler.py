from typing import Dict, Any, Optional, Tuple
import os
import logging
import time
import requests
import tempfile
from threading import Lock
from pathlib import Path
from PyPDF2 import PdfReader
from .base import BaseNode
from .web_crawler_local import SeleniumWebCrawlerNode
from ..api.config import API_CONFIG
from ..api.llm_api import call_llm_api
from ..utils.redis_cache import RedisCache

logger = logging.getLogger(__name__)


class RateLimiter:
    """全局请求限速器，使用漏斗桶算法实现"""

    def __init__(self, max_requests_per_minute: int):
        self.rate = max_requests_per_minute / 60.0  # 每秒处理的请求数
        self.capacity = max_requests_per_minute  # 桶的容量
        self.water = 0  # 当前桶中的水量（请求数）
        self.last_update = time.time()
        self.lock = Lock()

    def _update_water(self):
        """更新桶中的水量"""
        now = time.time()
        time_passed = now - self.last_update
        # 计算这段时间内流出的水量
        leaked = time_passed * self.rate
        # 更新水量，不能小于0
        self.water = max(0, self.water - leaked)
        self.last_update = now

    def acquire(self):
        """尝试添加一个请求到桶中，如果桶满则等待"""
        with self.lock:
            while True:
                self._update_water()
                # 如果桶中还有空间，立即处理请求
                if self.water < self.capacity:
                    self.water += 1
                    return
                # 计算需要等待的时间
                # 等待到桶中有空间的时间
                wait_time = (self.water - self.capacity + 1) / self.rate
                time.sleep(wait_time)


class SerperWebCrawlerNode(BaseNode):
    """网络爬虫节点 - 使用 Serper API 接收 URL 并返回网页正文内容的节点

    参数:
        url (str): 需要抓取的网页URL

    返回:
        dict: 包含执行状态、错误信息和提取的正文内容
    """

    # 全局限速器，限制每分钟10个请求
    rate_limiter = RateLimiter(max_requests_per_minute=5)

    # 提示词模板
    MARKDOWN_SUMMARY_PROMPT = {
        "system": """你是一名专业的Markdown文档处理专家，请严格遵循以下要求：
1. 文档内容判断，当认为内容是一些毫无意义的格式信息或者无意义信息，请直接返回"此链接 {url} 内容无效，请忽略"
2. 核心任务：将用户提供的Markdown文档转化为结构清晰、保留关键要素的总结性文档
3. 格式要求：
   - 必须保持Markdown格式
   - 保留必要的图片(![]())和表格(| |)
   - 使用章节分级整理内容
4. 内容要求：
   - 保持原文核心观点和技术细节
   - 删除冗余示例和重复描述
   - 维持原有技术术语的准确性
5. 注意事项：
   - 不要添加原文未出现的内容
   - 如遇复杂结构，保持信息完整性优于格式简洁
   - 请只返回Markdown格式的总结，不要包含任何额外的说明或提示
   - 保持原文严谨度，字数缩减至20%以内，避免主观阐释  
   """,
        "user": """请处理以下Markdown文档：\n
{text}\n
文档原始链接：{url}
""",
    }

    TEXT_SUMMARY_PROMPT = {
        "system": """你是一名专业的文档处理专家，请严格遵循以下要求：
1. 文档内容判断，当认为内容是一些毫无意义的格式信息或者无意义信息，请直接返回"此链接 {url} 内容无效，请忽略"
2. 核心任务：将用户提供的文档转化为结构清晰、保留关键要素的总结文档
3. 格式要求：
   - 使用章节分级整理内容
4. 内容要求：
   - 保持原文核心观点和技术细节
   - 删除冗余示例和重复描述
   - 维持原有技术术语的准确性
5. 注意事项：
   - 不要添加原文未出现的内容
   - 如遇复杂结构，保持信息完整性优于格式简洁
   - 请只返回总结，不要包含任何额外的说明或提示
   - 保持原文严谨度，字数缩减至50%以内，避免主观阐释""",
        "user": """请处理以下文档：\n
{text}\n
文档原始链接：{url}
""",
    }

    # Redis缓存实例
    _cache: RedisCache
    _cache_ttl = int(os.getenv("WEB_CRAWLER_CACHE_TTL", "3600"))  # 默认1小时

    def __init__(self):
        super().__init__()
        self.api_key = API_CONFIG["serper_api_key"]
        self.api_url = "https://scrape.serper.dev"
        self._cache = RedisCache()

    def _is_pdf_url(self, url: str) -> bool:
        """检查URL是否指向PDF文件"""
        return url.lower().endswith(".pdf")

    def _download_and_extract_pdf(self, url: str) -> str:
        """下载PDF文件并提取文本内容"""
        try:
            # 创建临时目录
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir) / "temp.pdf"

                # 下载PDF文件
                self.rate_limiter.acquire()
                response = requests.get(url, timeout=120)
                response.raise_for_status()

                # 保存到临时文件
                with open(temp_path, "wb") as f:
                    f.write(response.content)

                # 提取文本内容
                text = ""
                with open(temp_path, "rb") as f:
                    reader = PdfReader(f)
                    for page in reader.pages:
                        text += page.extract_text() + "\n"

                return text.strip()
        except Exception as e:
            logger.error(f"PDF处理失败: {url}, 错误: {str(e)}")
            raise

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        start_time = time.time()
        url = str(params.get("url", "")).strip()
        need_summary = bool(params.get("need_summary", True))
        include_markdown = bool(params.get("include_markdown", True))
        if not url:
            raise ValueError("url参数不能为空")

        # 如果是PDF链接，特殊处理
        if self._is_pdf_url(url):
            logger.info(f"检测到PDF链接: {url}")

        logger.info(f"开始爬取: {url}")

        try:
            # 检查缓存
            text = self._get_from_cache(url)
            if text is not None:
                logger.info(f"从缓存获取内容: {url}")
            else:
                if self._is_pdf_url(url):
                    logger.info(f"从网络获取PDF内容: {url}")
                    text = self._download_and_extract_pdf(url)
                else:
                    logger.info(f"从网络获取网页内容: {url}")

                    headers = {
                        "X-API-KEY": self.api_key,
                        "Content-Type": "application/json",
                    }
                    data = {"url": url, "includeMarkdown": include_markdown}

                    # 等待限速器允许请求
                    self.rate_limiter.acquire()

                    # 发送请求
                    response = requests.post(
                        self.api_url, headers=headers, json=data, timeout=120
                    )
                    response.raise_for_status()

                    # 获取响应内容
                    result = response.json()
                    if include_markdown:
                        text = result.get("markdown", "")
                    else:
                        text = result.get("text", "")
                    # 去除空行
                    text = "\n".join(line for line in text.splitlines() if line.strip())

            self._add_to_cache(url, text)
            if need_summary:
                # 检查内容是否有效
                if not text or len(text.strip()) < 50 or "not found" in text.lower():
                    text = f"此网页内容无效，请忽略。链接：{url}"
                elif include_markdown:
                    text = await call_llm_api(
                        messages=[
                            {
                                "role": "system",
                                "content": self.MARKDOWN_SUMMARY_PROMPT[
                                    "system"
                                ].format(url=url),
                            },
                            {
                                "role": "user",
                                "content": self.MARKDOWN_SUMMARY_PROMPT["user"].format(
                                    text=text, url=url
                                ),
                            },
                        ],
                        model_name="deepseek-chat",
                    )
                else:
                    text = await call_llm_api(
                        messages=[
                            {
                                "role": "system",
                                "content": self.TEXT_SUMMARY_PROMPT["system"].format(
                                    url=url
                                ),
                            },
                            {
                                "role": "user",
                                "content": self.TEXT_SUMMARY_PROMPT["user"].format(
                                    text=text, url=url
                                ),
                            },
                        ],
                        model_name="deepseek-chat",
                    )

            end_time = time.time()
            execution_time = end_time - start_time
            content_length = len(text)
            logger.info(
                f"爬取成功: {url}, 内容长度: {content_length} 字符, 耗时: {execution_time:.2f} 秒"
            )

            return {"success": True, "error": None, "content": text}

        except requests.Timeout:
            end_time = time.time()
            execution_time = end_time - start_time
            error_msg = f"请求超时: {url}"
            logger.error(f"{error_msg}, 耗时: {execution_time:.2f} 秒")
            return {"success": True}

        except requests.RequestException as e:
            end_time = time.time()
            execution_time = end_time - start_time
            error_msg = f"请求错误: {str(e)}"
            logger.error(f"{error_msg}, URL: {url}, 耗时: {execution_time:.2f} 秒")
            return {"success": True}

        except Exception as e:
            end_time = time.time()
            execution_time = end_time - start_time
            error_msg = f"未知错误: {str(e)}"
            logger.error(f"{error_msg}, URL: {url}, 耗时: {execution_time:.2f} 秒")
            return {"success": True}

    async def agent_execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        execution_result = await self.execute(params)
        return {"result": execution_result.get("content", "爬取失败，请忽略这个链接")}

    def _get_from_cache(self, url: str) -> Optional[str]:
        """从Redis缓存获取URL对应的内容"""
        cache_key = f"crawler:cache:{url}"
        return self._cache.get(cache_key)

    def _add_to_cache(self, url: str, content: str) -> None:
        """将URL和内容添加到Redis缓存"""
        cache_key = f"crawler:cache:{url}"
        self._cache.set(cache_key, content, self._cache_ttl)
