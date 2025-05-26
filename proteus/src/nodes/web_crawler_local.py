from typing import Dict, Any, List, Callable
import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from bs4 import BeautifulSoup, Comment
from .base import BaseNode
import re
import logging

logger = logging.getLogger(__name__)

class SeleniumWebCrawlerNode(BaseNode):
    """网络爬虫节点 - 使用 Selenium 接收 URL 并返回网页正文内容的节点

    参数:
        url (str): 需要抓取的网页URL

    返回:
        dict: 包含执行状态、错误信息和提取的正文内容
    """

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        start_time = time.time()
        url = str(params.get("url", "")).strip()
        if not url:
            raise ValueError("url参数不能为空")

        logger.info(f"开始爬取: {url}")

        # 配置 Selenium WebDriver
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")  # 无头模式
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--enable-unsafe-swiftshader")
        options.add_argument("--disable-extensions")
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--incognito")  # 隐身模式
        options.add_argument("--window-size=1280,1024")
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
        )
        try:
            # 启动 WebDriver
            driver = webdriver.Chrome(options=options)
            driver.set_page_load_timeout(120)
            # 访问 URL
            driver.get(url)
            # 等待页面加载完成

            # 从环境变量获取等待条件的选择器
            wait_selectors_str = os.getenv(
                "WEBCRAWLER_WAIT_SELECTORS", "main,article,div.article"
            )
            wait_selectors = [
                (By.CSS_SELECTOR, selector.strip())
                for selector in wait_selectors_str.split(",")
            ]

            # 使用任何一种条件进行等待
            WebDriverWait(driver, 120).until(
                EC.any_of(
                    *[
                        EC.presence_of_element_located(selector)
                        for selector in wait_selectors
                    ]
                )
            )

            # 获取页面源码
            html = driver.page_source
            # 预处理 HTML
            main_content = None
            soup = BeautifulSoup(html)
            # 从环境变量获取内容选择器
            content_selectors_str = os.getenv(
                "WEBCRAWLER_CONTENT_SELECTORS",
                "article,div.article,div.article-content,main",
            )
            content_selectors = [
                selector.strip() for selector in content_selectors_str.split(",")
            ]

            # 尝试多种选择器来找到正文内容
            for selector in content_selectors:
                main_content = soup.select_one(selector)
                if main_content:
                    break

            # 提取并清理文本
            text = main_content.get_text(separator="\n")

            # 优化文本格式
            text = re.sub(r"\n{3,}", "\n\n", text)  # 合并多余空行
            text = re.sub(r"[ \t]{2,}", " ", text)  # 删除多余空格
            text = text.strip()

            end_time = time.time()
            execution_time = end_time - start_time
            content_length = len(text)
            logger.info(
                f"爬取成功: {url}, 内容长度: {content_length} 字符, 耗时: {execution_time:.2f} 秒"
            )
            return {"success": True, "error": None, "content": text}

        except TimeoutException as e:
            end_time = time.time()
            execution_time = end_time - start_time
            logger.error(
                f"页面加载超时: {url}, 错误: {str(e)}, 耗时: {execution_time:.2f} 秒"
            )
            return {"success": False, "error": f"页面加载超时: {str(e)}"}
        except WebDriverException as e:
            end_time = time.time()
            execution_time = end_time - start_time
            logger.error(
                f"WebDriver 错误: {url}, 错误: {str(e)}, 耗时: {execution_time:.2f} 秒"
            )
            return {
                "success": False,
                "error": f"WebDriver 错误: {str(e)}"
            }
        except Exception as e:
            end_time = time.time()
            execution_time = end_time - start_time
            logger.error(
                f"未知错误: {url}, 错误: {str(e)}, 耗时: {execution_time:.2f} 秒"
            )
            return {"success": False, "error": str(e)}
        finally:
            # 关闭 WebDriver
            if "driver" in locals():
                logger.info(f"关闭WebDriver: {url}")
                driver.close()
                driver.quit()

    async def agent_execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        execution_result = await self.execute(params)
        return {"result": execution_result.get("content", "爬取失败，请忽略这个链接")}