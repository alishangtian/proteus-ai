"""Serper搜索节点 - 返回搜索结果"""

from typing import Dict, Any
import aiohttp
from .base import BaseNode
from ..api.config import API_CONFIG
import os, time
import logging
from threading import Lock

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


class SerperSearchNode(BaseNode):
    """Serper搜索节点 - 返回搜索结果"""

    # 全局限速器，限制每分钟3个请求
    rate_limiter = RateLimiter(max_requests_per_minute=2)

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        # 限速器
        self.rate_limiter.acquire()
        # 获取搜索关键词
        query = str(params.get("query", ""))
        if not query:
            raise ValueError("query参数不能为空")

        # 获取API密钥
        api_key = os.getenv("SERPER_API_KEY", "")
        if not api_key:
            raise ValueError("未设置SERPER_API_KEY环境变量")

        # 获取可选参数
        country = str(params.get("country", "cn"))
        language = str(params.get("language", "zh"))
        maxResults = int(params.get("max_results", 5))

        try:
            async with aiohttp.ClientSession() as session:
                # 准备请求数据
                headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
                payload = {"q": query, "gl": country, "hl": language, "num": maxResults}

                # 发送请求
                async with session.post(
                    "https://google.serper.dev/search", headers=headers, json=payload
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        # 处理搜索结果
                        results = []

                        # 处理answerBox
                        answer_box = data.get("answerBox")
                        if answer_box:
                            results.append(
                                {
                                    "title": answer_box.get("title", ""),
                                    "link": "",  # answerBox通常没有链接
                                    "snippet": answer_box.get("answer", ""),
                                    "is_answer_box": True,
                                }
                            )

                        # 处理organic结果
                        organic_results = data.get("organic", [])
                        for result in organic_results:
                            results.append(
                                {
                                    "title": result.get("title", ""),
                                    "link": result.get("link", ""),
                                    "snippet": result.get("snippet", ""),
                                }
                            )

                        return {
                            "success": True,
                            "error": None,
                            "results": results,
                            "count": len(results),
                        }
                    else:
                        error_text = await response.text()
                        return {
                            "success": False,
                            "error": f"API请求失败: {error_text}",
                            "results": [],
                            "count": 0,
                        }

        except Exception as e:
            return {"success": False, "error": str(e), "results": [], "count": 0}

    async def agent_execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行节点并将结果转换为统一格式

        将搜索结果转换为易读的文本格式，包括查询信息和搜索结果列表。

        Args:
            params: 节点参数

        Returns:
            Dict[str, Any]: 执行结果，包含纯文本格式的'result'键
        """
        try:
            execute_result = await self.execute(params)
            if not execute_result["success"]:
                result_text += f"Error: {execute_result['error']}"
                return {"result": result_text, **execute_result}
            return {"result": execute_result["results"]}
        except Exception as e:
            return {"result": f"Error: {str(e)}", "error": str(e)}
