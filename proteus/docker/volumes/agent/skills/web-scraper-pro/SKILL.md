---
name: web-scraper-pro
description: 高级网页内容提取技能，用于应对简单的反爬虫机制（如User-Agent检测），并将网页HTML内容智能转换为LLM易于阅读的Markdown格式。主要用于替代基础的crawler工具，特别是在基础工具无法获取内容或内容格式混乱时。当用户提供一个URL并要求"阅读"、"总结"或"提取"内容时，如果标准爬虫失败或需要更高质量的文本提取，请运行此技能。
license: Complete terms in LICENSE.txt
allowed-tools:
  - python_execute
---
# Web Scraper Pro Skill

## Description
这是一个高级网页内容提取技能，专门用于应对简单的反爬虫机制（如User-Agent检测），并将网页 HTML 内容智能转换为 LLM 易于阅读的 Markdown 格式。
它主要用于替代基础的 crawler 工具，特别是在基础工具无法获取内容或内容格式混乱时。

## Components
- **Tools**:
    - `tools/crawler.py`: 核心 Python 脚本，使用 `requests` 和 `BeautifulSoup` 进行抓取和解析。

## Usage
当用户提供一个 URL 并要求"阅读"、"总结"或"提取"内容时，如果标准爬虫失败或需要更高质量的文本提取，请运行此技能。

## Execution Protocol
1.  **Input**: 用户提供的 URL。
2.  **Action**: 使用 python_execute 运行 `crawler.py`。
3.  **Command**: `python3 /app/.proteus/skills/web_scraper_pro/tools/crawler.py <URL>`
4.  **Output**: 脚本将输出网页的 Markdown 文本。

## Example
User: "总结这篇文章 https://mp.weixin.qq.com/s/xxxx"
Agent: 
```python
python3 /app/.proteus/skills/web_scraper_pro/tools/crawler.py https://mp.weixin.qq.com/s/xxxx
```
