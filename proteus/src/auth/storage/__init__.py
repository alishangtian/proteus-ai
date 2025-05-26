"""存储实现模块

提供了不同的存储后端实现:
- RedisStorage: 基于Redis的存储实现
- FileStorage: 基于文件系统的存储实现

使用示例:
```python
from auth.storage import get_storage

# 根据配置获取存储实例
storage = get_storage()

# 存储用户数据
storage.save_user("username", user_data)

# 获取会话数据
session = storage.get_session(session_id)
```
"""

import os
from typing import Optional
from .base import StorageBase
from .redis_storage import RedisStorage
from .file_storage import FileStorage

def get_storage() -> StorageBase:
    """获取存储实例
    
    根据环境变量SESSION_MODEL选择存储实现:
    - "redis": 使用Redis存储
    - 其他: 使用文件存储
    
    Returns:
        StorageBase: 存储实例
    """
    storage_type = os.getenv("SESSION_MODEL", "file")
    
    if storage_type == "redis":
        return RedisStorage()
    return FileStorage()

__all__ = ['StorageBase', 'RedisStorage', 'FileStorage', 'get_storage']