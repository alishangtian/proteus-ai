
import requests
from bs4 import BeautifulSoup
import sys
import argparse
import re

def get_headers():
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Connection": "keep-alive"
    }

def clean_text(text):
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text).strip()

def html_to_markdown(soup):
    # 移除不需要的标签
    for tag in soup(['script', 'style', 'iframe', 'noscript', 'header', 'footer', 'nav']):
        tag.decompose()
    
    markdown_lines = []
    
    # 获取标题
    title = soup.title.string if soup.title else "No Title"
    h1 = soup.find('h1')
    if h1:
        title = clean_text(h1.get_text())
    
    markdown_lines.append(f"# {title}\n")
    
    # 尝试定位正文容器，针对微信公众号优化，也兼容通用网页
    content_div = soup.select_one('#js_content') or soup.select_one('article') or soup.find('main') or soup.body
    
    if not content_div:
        return "Error: Could not find content body."

    # 遍历子元素转换为 Markdown
    # 这里做一个简化的遍历，实际情况可能需要递归处理，但为了演示保持简单
    for element in content_div.descendants:
        if element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            level = int(element.name[1])
            text = clean_text(element.get_text())
            if text:
                markdown_lines.append(f"{'#' * level} {text}\n")
        
        elif element.name == 'p':
            # 忽略包含图片的p标签的文本（如果有alt通常在img处理，这里简单处理）
            text = clean_text(element.get_text())
            if text and len(text) > 1: # 过滤太短的干扰字符
                markdown_lines.append(f"{text}\n")
        
        elif element.name == 'li':
            text = clean_text(element.get_text())
            if text:
                markdown_lines.append(f"- {text}")
        
        elif element.name == 'pre' or element.name == 'code':
            code_content = element.get_text()
            markdown_lines.append(f"```\n{code_content}\n```\n")
            
    # 去重和清理空行
    final_content = "\n".join(markdown_lines)
    # 简单去重连续换行
    final_content = re.sub(r'\n{3,}', '\n\n', final_content)
    
    return final_content

def fetch_url(url):
    try:
        session = requests.Session()
        response = session.get(url, headers=get_headers(), timeout=15)
        response.encoding = 'utf-8' # 或者是 response.apparent_encoding
        
        if response.status_code != 200:
            print(f"Error: HTTP {response.status_code}")
            return

        soup = BeautifulSoup(response.text, 'html.parser')
        markdown_content = html_to_markdown(soup)
        
        print(markdown_content)

    except Exception as e:
        print(f"Error fetching URL: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Web Scraper Pro")
    parser.add_argument("url", help="The URL to scrape")
    args = parser.parse_args()
    
    fetch_url(args.url)
