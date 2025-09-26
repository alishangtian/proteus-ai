import os
import logging
import json
from typing import Optional, Dict, Any
from src.api.llm_api import call_multimodal_llm_api
from src.utils.redis_cache import get_redis_connection
from src.utils.logger import setup_logger
from dotenv import load_dotenv
from PyPDF2 import PdfReader # 导入 PyPDF2
from docx import Document # 导入 python-docx

load_dotenv()
language = os.getenv("LANGUAGE", "中文")

log_file_path = os.getenv("log_file_path", "logs/workflow_engine.log")
setup_logger(log_file_path)
logger = logging.getLogger(__name__)

async def parse_file(file_path: str, file_type: str, file_id: str) -> Optional[str]:
    """
    根据文件类型解析文件内容。
    Args:
        file_path: 文件的完整路径。
        file_type: 文件的MIME类型。
        file_id: 文件的唯一ID。
    Returns:
        解析后的文件内容字符串，如果无法解析则返回None。
    """
    logger.info(f"开始解析文件: {file_path}, 类型: {file_type}")
    parsed_content = None

    if file_type.startswith("image/"):
        try:
            messages = [
                {
                    "role": "user",
                    "content": f"请详细使用{language}描述这张图片的内容",
                },
                {
                    "role": "user",
                    "content": [{"type": "image_url", "image_url": {"url": file_path}}],
                },
            ]
            resp, _ = await call_multimodal_llm_api(messages=messages, request_id=file_id)
            parsed_content = resp
            logger.info(f"图片文件 '{file_path}' 解析成功")
        except Exception as e:
            logger.error(f"图片文件 '{file_path}' 解析失败: {str(e)}", exc_info=True)
            parsed_content = f"图片解析失败: {str(e)}"
    elif file_type.startswith("text/") or file_type in [
        "application/json",
        "application/xml",
        "application/javascript",
        "text/markdown",
        "text/plain",
        "text/html",
        "application/x-python-code", # .py files
    ]:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                parsed_content = f.read()
            logger.info(f"文本文件 '{file_path}' 解析成功")
        except Exception as e:
            logger.error(f"文本文件 '{file_path}' 读取失败: {str(e)}", exc_info=True)
            parsed_content = f"文本文件读取失败: {str(e)}"
    elif file_type == "application/pdf":
        try:
            reader = PdfReader(file_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            parsed_content = text
            logger.info(f"PDF 文件 '{file_path}' 解析成功")
        except Exception as e:
            logger.error(f"PDF 文件 '{file_path}' 解析失败: {str(e)}", exc_info=True)
            parsed_content = f"PDF 文件解析失败: {str(e)}"
    elif file_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        try:
            document = Document(file_path)
            text = "\n".join([para.text for para in document.paragraphs])
            parsed_content = text
            logger.info(f"DOCX 文件 '{file_path}' 解析成功")
        except Exception as e:
            logger.error(f"DOCX 文件 '{file_path}' 解析失败: {str(e)}", exc_info=True)
            parsed_content = f"DOCX 文件解析失败: {str(e)}"
    else:
        logger.info(f"文件 '{file_path}' 类型 '{file_type}' 不支持解析，只进行上传。")
        parsed_content = None # 不支持解析，返回 None

    return parsed_content
