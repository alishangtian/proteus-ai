"""历史记录服务模块"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from pydantic import BaseModel
from .config import APIConfig

# 配置日志
module_logger = logging.getLogger(__name__)


class ChatHistory(BaseModel):
    """聊天历史记录模型

    Attributes:
        id: 聊天会话ID
        query: 用户查询内容
        timestamp: 时间戳
        model: 使用的模型类型
        agentid: 代理ID(可选)
        summary: 摘要内容(可选)
    """

    id: str
    query: str
    timestamp: str
    model: str
    agentid: Optional[str] = None
    summary: Optional[str] = None


class HistoryService:
    """历史记录服务类"""

    def __init__(self, history_file_path: str = APIConfig().data_path):
        """初始化历史记录服务

        Args:
            history_file_path: 历史记录文件路径
        """
        self.history_file_path = history_file_path + "/history.json"
        self._ensure_history_file_exists()

    def _ensure_history_file_exists(self):
        """确保历史记录文件存在"""
        directory = os.path.dirname(self.history_file_path)
        if not os.path.exists(directory):
            os.makedirs(directory)

        if not os.path.exists(self.history_file_path):
            with open(self.history_file_path, "w", encoding="utf-8") as f:
                json.dump([], f)

    def get_all_history(self) -> List[Dict[str, Any]]:
        """获取所有历史记录

        Returns:
            List[Dict[str, Any]]: 历史记录列表
        """
        try:
            with open(self.history_file_path, "r", encoding="utf-8") as f:
                history = json.load(f)
            return history
        except Exception as e:
            module_logger.error(f"获取历史记录失败: {str(e)}")
            return []

    def add_history(self, chat_history: ChatHistory) -> bool:
        """添加历史记录

        Args:
            chat_history: 聊天历史记录

        Returns:
            bool: 是否添加成功
        """
        try:
            history = self.get_all_history()
            history.append(chat_history.model_dump())

            with open(self.history_file_path, "w", encoding="utf-8") as f:
                json.dump(history, f, ensure_ascii=False, indent=2)

            return True
        except Exception as e:
            module_logger.error(f"添加历史记录失败: {str(e)}")
            return False

    def get_history_by_id(self, chat_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取历史记录

        Args:
            chat_id: 聊天ID

        Returns:
            Optional[Dict[str, Any]]: 历史记录
        """
        try:
            history = self.get_all_history()
            for item in history:
                if item.get("id") == chat_id:
                    return item
            return None
        except Exception as e:
            module_logger.error(f"获取历史记录失败: {str(e)}")
            return None

    def update_history_summary(self, chat_id: str, summary: str) -> bool:
        """更新历史记录摘要

        Args:
            chat_id: 聊天ID
            summary: 摘要内容

        Returns:
            bool: 是否更新成功
        """
        try:
            history = self.get_all_history()
            for item in history:
                if item.get("id") == chat_id:
                    item["summary"] = summary
                    break

            with open(self.history_file_path, "w", encoding="utf-8") as f:
                json.dump(history, f, ensure_ascii=False, indent=2)

            return True
        except Exception as e:
            module_logger.error(f"更新历史记录摘要失败: {str(e)}")
            return False

    def delete_history(self, chat_id: str) -> bool:
        """删除历史记录

        Args:
            chat_id: 聊天ID

        Returns:
            bool: 是否删除成功
        """
        try:
            history = self.get_all_history()
            history = [item for item in history if item.get("id") != chat_id]

            with open(self.history_file_path, "w", encoding="utf-8") as f:
                json.dump(history, f, ensure_ascii=False, indent=2)

            return True
        except Exception as e:
            module_logger.error(f"删除历史记录失败: {str(e)}")
            return False

    def clear_all_history(self) -> bool:
        """清空所有历史记录

        Returns:
            bool: 是否清空成功
        """
        try:
            with open(self.history_file_path, "w", encoding="utf-8") as f:
                json.dump([], f)

            return True
        except Exception as e:
            module_logger.error(f"清空历史记录失败: {str(e)}")
            return False


# 全局单例历史服务工厂，兼容代码中对 get_history_service 的调用
_history_service: Optional[HistoryService] = None


def get_history_service() -> HistoryService:
    """返回全局 HistoryService 单例实例。

    目的：兼容代码中 `from src.api.history_service import get_history_service as _get_history_service`
    的导入使用，避免在多个模块中重复创建 HistoryService 实例。
    """
    global _history_service
    if _history_service is None:
        _history_service = HistoryService()
    return _history_service
