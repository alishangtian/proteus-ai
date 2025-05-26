"""安全相关功能模块

提供密码加密、验证等安全相关功能
"""

import logging
from passlib.context import CryptContext

logger = logging.getLogger(__name__)

# 密码哈希配置
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,  # 明确指定rounds参数
    bcrypt__ident="2b"  # 使用现代bcrypt标识
)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码
    
    Args:
        plain_password: 明文密码
        hashed_password: 哈希后的密码
        
    Returns:
        bool: 密码是否匹配
    """
    try:
        # 确保明文密码和哈希密码都是字符串类型
        if isinstance(plain_password, bytes):
            plain_password = plain_password.decode('utf-8')
        if isinstance(hashed_password, bytes):
            hashed_password = hashed_password.decode('utf-8')
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.error(f"密码验证失败: {e}")
        return False

def get_password_hash(password: str) -> str:
    """生成密码哈希
    
    Args:
        password: 明文密码
        
    Returns:
        str: 哈希后的密码
        
    Raises:
        Exception: 密码哈希生成失败
    """
    try:
        # 确保密码是字符串类型
        if isinstance(password, bytes):
            password = password.decode('utf-8')
        return pwd_context.hash(password)
    except Exception as e:
        logger.error(f"密码哈希生成失败: {e}")
        raise