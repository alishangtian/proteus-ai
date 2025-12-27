"""文件系统存储实现"""

import os
import json
import logging
from typing import Dict, Optional
from .base import StorageBase

logger = logging.getLogger(__name__)


class FileStorage(StorageBase):
    """文件系统存储实现类"""

    def __init__(self):
        """初始化文件存储

        创建数据目录（如果不存在）
        """
        self.data_dir = os.getenv("DATA_PATH", "./data")
        os.makedirs(self.data_dir, exist_ok=True)

    def _get_user_file(self, user_name: str) -> str:
        """获取用户数据文件路径

        Args:
            user_name: 用户名

        Returns:
            str: 文件路径
        """
        return os.path.join(self.data_dir, f"user_{user_name}.json")

    def _get_session_file(self, session_id: str) -> str:
        """获取会话数据文件路径

        Args:
            session_id: 会话ID

        Returns:
            str: 文件路径
        """
        return os.path.join(self.data_dir, f"session_{session_id}.json")

    def save_user(self, user_name: str, user_data: Dict) -> bool:
        """保存用户数据到文件

        Args:
            user_name: 用户名
            user_data: 用户数据字典

        Returns:
            bool: 保存是否成功
        """
        try:
            with open(self._get_user_file(user_name), "w") as f:
                json.dump(user_data, f)
            return True
        except Exception as e:
            logger.error(f"保存用户数据失败: {e}")
            return False

    def get_user(self, user_name: str) -> Optional[Dict]:
        """从文件获取用户数据

        Args:
            user_name: 用户名

        Returns:
            Optional[Dict]: 用户数据字典，不存在则返回None
        """
        try:
            with open(self._get_user_file(user_name), "r") as f:
                return json.load(f)
        except FileNotFoundError:
            return None
        except Exception as e:
            logger.error(f"读取用户数据失败: {e}")
            return None

    def get_user_by_email(self, email: str) -> Optional[Dict]:
        """根据邮箱获取用户数据

        Args:
            email: 邮箱地址

        Returns:
            Optional[Dict]: 用户数据字典，不存在则返回None
        """
        try:
            for filename in os.listdir(self.data_dir):
                if filename.startswith("user_") and filename.endswith(".json"):
                    file_path = os.path.join(self.data_dir, filename)
                    with open(file_path, "r") as f:
                        try:
                            user_data = json.load(f)
                            if user_data.get("email") == email:
                                return user_data
                        except json.JSONDecodeError:
                            continue
            return None
        except Exception as e:
            logger.error(f"根据邮箱查找用户失败: {e}")
            return None

    def save_session(self, session_id: str, session_data: Dict) -> bool:
        """保存会话数据到文件

        Args:
            session_id: 会话ID
            session_data: 会话数据字典

        Returns:
            bool: 保存是否成功
        """
        try:
            with open(self._get_session_file(session_id), "w") as f:
                json.dump(session_data, f)
            return True
        except Exception as e:
            logger.error(f"保存会话数据失败: {e}")
            return False

    def get_session(self, session_id: str) -> Optional[Dict]:
        """从文件获取会话数据

        Args:
            session_id: 会话ID

        Returns:
            Optional[Dict]: 会话数据字典，不存在则返回None
        """
        try:
            with open(self._get_session_file(session_id), "r") as f:
                return json.load(f)
        except FileNotFoundError:
            return None
        except Exception as e:
            logger.error(f"读取会话数据失败: {e}")
            return None

    def delete_session(self, session_id: str) -> bool:
        """删除会话文件

        Args:
            session_id: 会话ID

        Returns:
            bool: 删除是否成功
        """
        try:
            os.remove(self._get_session_file(session_id))
            return True
        except FileNotFoundError:
            return True  # 文件不存在也视为删除成功
        except Exception as e:
            logger.error(f"删除会话文件失败: {e}")
            return False
