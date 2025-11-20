"""存储接口基类定义"""

from abc import ABC, abstractmethod
from typing import Optional, Dict


class StorageBase(ABC):
    """存储接口基类

    定义了用户数据和会话数据存储的通用接口
    """

    @abstractmethod
    def save_user(self, user_name: str, user_data: Dict) -> bool:
        """保存用户数据

        Args:
            user_name: 用户名
            user_data: 用户数据字典

        Returns:
            bool: 保存是否成功
        """
        pass

    @abstractmethod
    def get_user(self, user_name: str) -> Optional[Dict]:
        """获取用户数据

        Args:
            user_name: 用户名

        Returns:
            Optional[Dict]: 用户数据字典，不存在则返回None
        """
        pass

    @abstractmethod
    def save_session(self, session_id: str, session_data: Dict) -> bool:
        """保存会话数据

        Args:
            session_id: 会话ID
            session_data: 会话数据字典

        Returns:
            bool: 保存是否成功
        """
        pass

    @abstractmethod
    def get_session(self, session_id: str) -> Optional[Dict]:
        """获取会话数据

        Args:
            session_id: 会话ID

        Returns:
            Optional[Dict]: 会话数据字典，不存在则返回None
        """
        pass

    @abstractmethod
    def delete_session(self, session_id: str) -> bool:
        """删除会话数据

        Args:
            session_id: 会话ID

        Returns:
            bool: 删除是否成功
        """
        pass
