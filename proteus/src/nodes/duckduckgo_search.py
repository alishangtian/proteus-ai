"""DuckDuckGo搜索节点 - 返回搜索结果"""

from typing import Dict, Any
from duckduckgo_search import DDGS
from .base import BaseNode
import json, logging

logger = logging.getLogger(__name__)


class DuckDuckGoSearchNode(BaseNode):
    """DuckDuckGo搜索节点 - 返回搜索结果"""

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        # 获取搜索关键词
        query = str(params.get("query", ""))
        if not query:
            raise ValueError("query参数不能为空")

        # 获取可选参数
        region = str(params.get("region", "cn-zh"))
        maxResults = int(params.get("maxResultes", 20))

        try:
            with DDGS() as ddgs:
                # 执行搜索
                results = ddgs.text(query, max_results=maxResults, region=region)
                # 返回结果
                return {
                    "success": True,
                    "error": None,
                    "results": results,
                    "count": len(results),
                }
        except Exception as e:
            logger.error(f"DuckDuckGo搜索失败：{e}")
            return {"success": False, "error": str(e), "results": [], "count": 0}

    async def agent_execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        result = await self.execute(params)
        return {
            "success": result.get("success", False),
            "result": result.get("results", []),
        }
