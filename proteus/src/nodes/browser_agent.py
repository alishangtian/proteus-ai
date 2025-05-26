"""Browser Agent节点 - 执行浏览器自动化任务"""

import asyncio
import concurrent.futures
import logging
import os
import platform
from functools import partial
from typing import Dict, Any

from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel
from .base import BaseNode
from browser_use import Agent
from browser_use.browser.browser import Browser, BrowserConfig

# 加载环境变量
load_dotenv()

# Windows平台特定配置
if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

logger = logging.getLogger(__name__)


class BrowserAgentNode(BaseNode):
    """Browser Agent节点 - 执行浏览器自动化任务"""

    def __init__(self):
        """初始化BrowserAgentNode，创建独立的线程池"""
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=int(os.getenv("BROWSER_AGENT_THREADS", 4))
        )

    async def _execute_in_threadpool(self, func, *args, **kwargs):
        """在独立线程池中执行同步函数

        Args:
            func: 要执行的同步函数
            *args: 传递给函数的位置参数
            **kwargs: 传递给函数的关键字参数

        Returns:
            函数执行的结果
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor, partial(func, *args, **kwargs)
        )

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行浏览器自动化任务

        Args:
            params: 包含任务参数的字典，必须有'task'键

        Returns:
            执行结果字典，包含'success'、'error'和'result'键

        Raises:
            ValueError: 当task参数为空时
        """
        task = str(params.get("task", ""))
        if not task:
            raise ValueError("task参数不能为空")

        try:
            # 获取浏览器路径配置
            browser_path = os.getenv("BROSWER_PATH")

            # 在独立线程中初始化浏览器
            browser = await self._execute_in_threadpool(
                Browser, config=BrowserConfig(chrome_instance_path=browser_path)
            )

            # 初始化LLM
            llm = ChatOpenAI(
                model=os.getenv("BROSWER_USE_MODEL", "gpt-4o"),
                base_url=os.getenv("BROSWER_BASE_URL", ""),
                api_key=os.getenv("BROSWER_USE_API_KEY", ""),
                temperature=0.0,
            )

            # 创建并执行Agent
            agent = Agent(
                task=task,
                llm=llm,
                browser=browser,
                save_conversation_path=os.getenv("BROSWER_SAVE_CONVERSATION_PATH", ""),
                generate_gif=bool(os.getenv("BROSWER_GENERATE_GIF", "false"))
            )
            result = await agent.run()

            # 构建结果分析提示
            analysis_prompt = """
            请根据context内容回答task问题，所回答的内容需要从context中提取，不要发散。
task：{task}

context：{result}
""".format(
                task=task, result=result
            )

            # 设置分析链
            prompt = ChatPromptTemplate.from_messages(
                [
                    (
                        "system",
                        "你是一个智能问答助手，请只参考context内容回答task问题，不要发散，不要输出其他内容，只输出答案即可。",
                    ),
                    ("human", "{user_message}"),
                ]
            )

            chain = prompt | llm | StrOutputParser()
            analysis_result = chain.invoke({"user_message": analysis_prompt})

            return {
                "success": True,
                "result": analysis_result,
                "error": None,
            }

        except Exception as e:
            logger.error(f"执行浏览器任务失败: {str(e)}", exc_info=True)
            return {"success": False, "error": str(e), "result": None}
        finally:
            # 关闭浏览器
            browser.close()

    async def agent_execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行节点并将结果转换为统一格式

        Args:
            params: 节点参数，必须包含'task'

        Returns:
            Dict[str, Any]: 包含'result'键的执行结果，出错时包含'error'键
        """
        try:
            final_result = await self.execute(params)
            if final_result["success"]:
                return {"result": final_result["result"]}
            return {"result": f"Error: {final_result['error']}"}
        except Exception as e:
            logger.error(f"agent_execute执行失败: {str(e)}", exc_info=True)
            return {"result": f"Error: {str(e)}", "error": str(e)}

    async def close(self):
        """清理资源，关闭线程池"""
        self._executor.shutdown(wait=True)

    def __del__(self):
        """析构函数，确保资源被清理"""
        if hasattr(self, "_executor"):
            self._executor.shutdown(wait=False)
