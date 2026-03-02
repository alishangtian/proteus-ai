"""Logging configuration module"""

import os
import logging
from typing import Optional

def setup_logger(
    log_file_path: str,
    log_level: int = logging.INFO,
    logger_name: Optional[str] = None
) -> logging.Logger:
    """Configure and return a logger with file and console handlers.
    
    Args:
        log_file_path: Path to the log file
        log_level: Logging level (default: logging.INFO)
        logger_name: Name of the logger (default: None for root logger)
        
    Returns:
        logging.Logger: Configured logger instance
    """
    # 确保日志目录存在
    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
    
    # 获取或创建logger
    logger = logging.getLogger(logger_name) if logger_name else logging.getLogger()
    logger.setLevel(log_level)
    
    # 创建文件处理器
    file_handler = logging.FileHandler(log_file_path)
    file_handler.setLevel(log_level)
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    
    # 配置日志格式
    log_format = '%(asctime)s - %(name)s - %(levelname)s - [%(process)d:%(threadName)s] - [%(filename)s:%(lineno)d] - %(message)s'
    formatter = logging.Formatter(log_format, datefmt='%Y-%m-%d %H:%M:%S')
    
    # 设置格式化器
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # 移除现有的处理器
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # 添加处理器到logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger