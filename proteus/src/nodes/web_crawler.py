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
from ..api.config import API_CONFIG
from ..api.llm_api import call_llm_api
from ..utils.redis_cache import RedisCache
from ..utils.langfuse_wrapper import langfuse_wrapper

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
        "system": """你是一名专业的文档精简专家，擅长对文本进行高效压缩与核心信息提取。请根据以下要求处理用户输入的文档内容：

**核心任务：**
将输入的文档压缩至原长度的 30% 左右，同时保留原文的核心信息、关键数据和逻辑结构。

** 内容有效性判断 **
1. 若内容为无意义的格式信息、错误页面或空白内容，直接返回"此链接 {url} 内容无效，请忽略"

**处理原则：**
1. **识别核心内容**：保留主旨句、关键结论、重要定义、核心数据、行动项及必要背景。
2. **删减冗余内容**：剔除重复叙述、过渡性语句、次要细节、冗长举例及非必要的修饰词。
3. **合并同类信息**：将相近观点或事实整合为简洁表述。
4. **维持逻辑连贯**：确保压缩后的文本条理清晰、语义通顺。
5. **保留关键术语与专有名词**：确保专业概念准确无误。

**输出要求：**
- 直接输出压缩后的文本，无需额外解释。
- 尽量使用原文中的关键词与表述方式。
- 若原文结构清晰（如分章节、列表），可保持原有组织形式。

**示例风格（仅供参考）：**
- 原文段落：“在本次项目复盘会议中，各部门代表均发表了详细意见。市场部指出，推广活动在第一季度取得了超出预期的效果，曝光量同比增长 45%，但转化率仍有提升空间；技术部反馈系统稳定性已有显著改善，故障率下降 60%...”
- 压缩后：“项目复盘显示：Q1 市场推广曝光量增 45%，转化率待提升；技术部系统故障率降 60%。”

请根据上述规则，对用户输入的文档进行压缩与提取。
""",
        "user": """原始文档如下：\n\n
<raw_text>
{text}
</raw_text>
\n
文档原始链接：{url}\n
总结后的文档：\n
""",
    }

    TEXT_SUMMARY_PROMPT = {
        "system": """你是一名专业的文档精简专家，擅长对文本进行高效压缩与核心信息提取。请根据以下要求处理用户输入的文档内容：

**核心任务：**
将输入的文档压缩至原长度的 30% 左右，同时保留原文的核心信息、关键数据和逻辑结构。

** 内容有效性判断 **
1. 若内容为无意义的格式信息、错误页面或空白内容，直接返回"此链接 {url} 内容无效，请忽略"

**处理原则：**
1. **识别核心内容**：保留主旨句、关键结论、重要定义、核心数据、行动项及必要背景。
2. **删减冗余内容**：剔除重复叙述、过渡性语句、次要细节、冗长举例及非必要的修饰词。
3. **合并同类信息**：将相近观点或事实整合为简洁表述。
4. **维持逻辑连贯**：确保压缩后的文本条理清晰、语义通顺。
5. **保留关键术语与专有名词**：确保专业概念准确无误。

**输出要求：**
- 直接输出压缩后的文本，无需额外解释。
- 尽量使用原文中的关键词与表述方式。
- 若原文结构清晰（如分章节、列表），可保持原有组织形式。

**示例风格（仅供参考）：**
- 原文段落：“在本次项目复盘会议中，各部门代表均发表了详细意见。市场部指出，推广活动在第一季度取得了超出预期的效果，曝光量同比增长 45%，但转化率仍有提升空间；技术部反馈系统稳定性已有显著改善，故障率下降 60%...”
- 压缩后：“项目复盘显示：Q1 市场推广曝光量增 45%，转化率待提升；技术部系统故障率降 60%。”

请根据上述规则，对用户输入的文档进行压缩与提取。
""",
        "user": """原始文档如下：\n\n
<raw_text>
{text}
</raw_text>
\n
文档原始链接：{url}\n
总结后的文档：\n
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
                response = requests.get(url, timeout=3600)
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

    @langfuse_wrapper.dynamic_observe()
    async def _execute_llm_generation(
        self,
        messages: list,
        model_name: str,
        url: str,
    ) -> Tuple[str, Dict]:
        """执行 LLM 生成（带追踪）

        Args:
            messages: 消息列表
            model_name: 模型名称
            url: 原始URL（用于日志记录）

        Returns:
            tuple: (响应文本, 使用情况)
        """
        start_time = time.time()
        response_text = ""
        usage_info = {}

        try:
            langfuse_instance = langfuse_wrapper.get_langfuse_instance()
            with langfuse_instance.start_as_current_span(
                name="web-crawler-llm-call"
            ) as span:
                # 创建嵌套的generation span
                span.update_trace(tags=["web_crawler", "summary"])
                with span.start_as_current_generation(
                    name="summarize-web-content",
                    model=model_name,
                    input={"prompt": messages, "url": url},
                    model_parameters={
                        "temperature": 0.7,
                    },
                    metadata={
                        "url": url,
                        "content_length": len(messages[-1].get("content", "")),
                    },
                ) as generation:
                    # 调用 LLM API
                    response_text, usage_info = await call_llm_api(
                        messages=messages,
                        model_name=model_name,
                    )

                    # 计算执行时间
                    execution_time = time.time() - start_time

                    # 构建输出内容
                    output_content = {
                        "summary": response_text,
                        "original_url": url,
                    }

                    # 构建使用详情
                    usage_details = {
                        "input_usage": usage_info.get("prompt_tokens", 0),
                        "output_usage": usage_info.get("completion_tokens", 0),
                    }

                    # 更新 generation
                    generation.update(
                        output=output_content,
                        usage_details=usage_details,
                        metadata={
                            "execution_time": execution_time,
                            "summary_length": len(response_text),
                        },
                    )

                    # 评分 - 根据响应质量评分
                    relevance_score = (
                        0.95 if response_text and len(response_text) > 50 else 0.5
                    )
                    generation.score(
                        name="relevance", value=relevance_score, data_type="NUMERIC"
                    )

                    logger.info(
                        f"LLM生成完成 (url: {url}, "
                        f"耗时: {execution_time:.2f}s, "
                        f"tokens: {usage_details['input_usage']+usage_details['output_usage']})"
                    )

            return response_text, usage_info

        except Exception as e:
            execution_time = time.time() - start_time if "start_time" in locals() else 0

            # 尝试更新 generation span 的错误状态
            if "generation" in locals():
                try:
                    if hasattr(generation, "update"):
                        generation.update(
                            output={"error": str(e)},
                            status_message=f"LLM call failed: {str(e)}",
                            metadata={"execution_time": execution_time},
                        )
                except Exception as update_error:
                    logger.warning(f"Failed to update generation span: {update_error}")

            logger.error(f"LLM生成失败 (url: {url}): {str(e)}", exc_info=True)
            raise

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        start_time = time.time()
        url = str(params.get("url", "")).strip()
        need_summary = bool(params.get("need_summary", True))
        # need_summary = True
        include_markdown = bool(params.get("include_markdown", True))
        # include_markdown = True
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
                    text, usage_info = await self._execute_llm_generation(
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
                        model_name="gemini-2.5-flash",
                        url=url,
                    )
                else:
                    text, usage_info = await self._execute_llm_generation(
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
                        model_name="gemini-2.5-flash",
                        url=url,
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
            return {"success": False, "error": error_msg}

        except requests.RequestException as e:
            end_time = time.time()
            execution_time = end_time - start_time
            error_msg = f"请求错误: {str(e)}"
            logger.error(f"{error_msg}, URL: {url}, 耗时: {execution_time:.2f} 秒")
            return {"success": False, "error": error_msg}

        except Exception as e:
            end_time = time.time()
            execution_time = end_time - start_time
            error_msg = f"未知错误: {str(e)}"
            logger.error(f"{error_msg}, URL: {url}, 耗时: {execution_time:.2f} 秒")
            return {"success": False, "error": error_msg}

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
