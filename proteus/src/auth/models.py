"""认证模块数据模型定义"""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, validator


class RegisterRequest(BaseModel):
    """用户注册请求模型"""

    user_name: str = Field(..., min_length=3, max_length=20, description="用户名")
    nick_name: str = Field(..., min_length=1, max_length=20, description="昵称")
    email: str = Field(
        ...,
        pattern=r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$",
        description="邮箱地址",
    )
    password: str = Field(..., min_length=6, description="密码")
    confirm_password: str = Field(..., min_length=6, description="确认密码")

    @validator("confirm_password")
    def passwords_match(cls, v, values):
        """验证两次输入的密码是否一致"""
        if "password" in values and v != values["password"]:
            raise ValueError("密码不一致")
        return v


class LoginRequest(BaseModel):
    """用户登录请求模型"""

    user_name: str = Field(..., min_length=3, max_length=20, description="用户名")
    password: str = Field(..., min_length=6, description="密码")


class UpdateNicknameRequest(BaseModel):
    user_name: str = Field(..., min_length=3, max_length=20)
    new_nick_name: str = Field(..., min_length=1, max_length=20)
    password: str = Field(..., min_length=6)


class SessionData(BaseModel):
    """会话数据模型"""

    user_name: str = Field(..., description="用户名")
    nick_name: str = Field(..., description="昵称")
    expires: str = Field(..., description="过期时间(ISO格式字符串)")

    @classmethod
    def create(cls, user_name: str, nick_name: str, expires: datetime):
        """创建新的会话数据"""
        return cls(
            user_name=user_name, nick_name=nick_name, expires=expires.isoformat()
        )


class ApiResponse(BaseModel):
    """API响应模型"""

    event: str = Field(..., description="事件类型")
    success: bool = Field(..., description="操作是否成功")
    data: Optional[dict] = Field(None, description="响应数据")
    error: Optional[str] = Field(None, description="错误信息")
