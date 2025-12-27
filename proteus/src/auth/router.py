"""认证路由模块"""

import os
import uuid
import logging
from typing import Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse, FileResponse

from .models import (
    RegisterRequest,
    LoginRequest,
    SessionData,
    ApiResponse,
    UpdateNicknameRequest,
    ResetPasswordRequest,
)
from .storage import get_storage
from .security import verify_password, get_password_hash

logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter(tags=["认证模块"])

# 获取存储实例
storage = get_storage()

# 会话配置
SESSION_EXPIRE_MINUTES = int(os.getenv("SESSION_EXPIRE_MINUTES", 30))


async def get_current_user(request: Request) -> Optional[SessionData]:
    """获取当前登录用户

    Args:
        request: FastAPI请求对象

    Returns:
        Optional[SessionData]: 当前用户的会话数据，未登录则返回None
    """
    session_id = request.cookies.get("session")
    if not session_id:
        return None

    session_data = storage.get_session(session_id)
    if not session_data:
        return None

    # 获取用户数据以获取昵称
    user_data = storage.get_user(session_data["user_name"])
    if not user_data:
        return None

    # 确保向后兼容：如果用户数据中没有昵称，则使用用户名作为昵称
    nick_name = user_data.get("nick_name", session_data["user_name"])

    return SessionData(
        user_name=session_data["user_name"],
        nick_name=nick_name,
        expires=session_data["expires"],
    )


@router.post("/register", response_model=ApiResponse)
async def register(register_data: RegisterRequest):
    """用户注册接口"""
    user_data = {
        "user_name": register_data.user_name,
        "nick_name": register_data.nick_name,
        "email": register_data.email,
        "hashed_password": get_password_hash(register_data.password),
        "disabled": "False",
    }

    # 检查用户是否已存在
    if storage.get_user(register_data.user_name):
        return ApiResponse(event="register", success=False, error="用户名已存在").dict()

    # 保存用户数据
    if not storage.save_user(register_data.user_name, user_data):
        return ApiResponse(
            event="register", success=False, error="系统错误，请稍后重试"
        ).dict()

    return ApiResponse(
        event="register",
        success=True,
        data={
            "user_name": register_data.user_name,
            "nick_name": register_data.nick_name,
        },
    ).dict()


@router.post("/login", response_model=ApiResponse)
async def login(request: Request, login_data: LoginRequest):
    """用户登录接口"""
    logger.info(f"用户登录: {login_data.user_name}")

    # 获取用户数据
    user_data = storage.get_user(login_data.user_name)
    if not user_data or not verify_password(
        login_data.password, user_data["hashed_password"]
    ):
        return ApiResponse(
            event="login", success=False, error="无效的用户名或密码"
        ).dict()

    # 创建新会话
    session_id = str(uuid.uuid4())
    expires = datetime.now() + timedelta(minutes=SESSION_EXPIRE_MINUTES)
    session_data = {"user_name": login_data.user_name, "expires": expires.isoformat()}

    # 保存会话数据
    if not storage.save_session(session_id, session_data):
        return ApiResponse(
            event="login", success=False, error="系统错误，请稍后重试"
        ).dict()

    # 返回响应并设置cookie
    response = JSONResponse(content=ApiResponse(event="login", success=True).dict())
    response.set_cookie(
        key="session",
        value=session_id,
        max_age=SESSION_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=True,
        samesite="Lax",
    )
    return response


@router.get("/register")
async def serve_register_page():
    """返回注册页面"""
    return FileResponse("static/register.html")


@router.get("/login")
async def serve_login_page():
    """返回登录页面"""
    return FileResponse("static/login.html")


@router.get("/logout")
async def logout(request: Request):
    """用户登出接口"""
    session_id = request.cookies.get("session")
    if session_id:
        storage.delete_session(session_id)
    return FileResponse("static/login.html")


@router.get("/check_session", response_model=ApiResponse)
async def check_session(user: Optional[SessionData] = Depends(get_current_user)):
    """检查会话状态"""
    if user:
        return ApiResponse(
            event="check_session",
            success=True,
            data={"user_name": user.user_name, "nick_name": user.nick_name},
        ).dict()
    return ApiResponse(event="check_session", success=False, error="未登录").dict()


@router.post("/update_nickname", response_model=ApiResponse)
async def update_nickname(request: Request, update_data: UpdateNicknameRequest):
    """修改用户昵称接口"""
    logger.info(f"用户修改昵称: {update_data.user_name} -> {update_data.new_nick_name}")

    # 获取用户数据
    user_data = storage.get_user(update_data.user_name)
    if not user_data:
        return ApiResponse(
            event="update_nickname", success=False, error="用户名不存在"
        ).dict()

    # 验证密码
    if not verify_password(update_data.password, user_data["hashed_password"]):
        return ApiResponse(
            event="update_nickname", success=False, error="密码错误"
        ).dict()

    # 检查新昵称是否已存在（排除当前用户）
    # 注意：这里简化了昵称重复检查，实际项目中可能需要更复杂的逻辑
    # 由于存储层没有提供查询所有用户的方法，这里暂时不实现昵称重复检查
    # 可以根据需要扩展存储层接口来支持昵称查询

    # 更新用户昵称
    user_data["nick_name"] = update_data.new_nick_name

    # 保存更新后的用户数据
    if not storage.save_user(update_data.user_name, user_data):
        return ApiResponse(
            event="update_nickname", success=False, error="系统错误，请稍后重试"
        ).dict()

    logger.info(
        f"用户 {update_data.user_name} 已修改昵称为 {update_data.new_nick_name}"
    )
    return ApiResponse(
        event="update_nickname",
        success=True,
        data={"message": f"用户昵称已修改为 {update_data.new_nick_name}"},
    ).dict()


@router.post("/reset_password", response_model=ApiResponse)
async def reset_password(reset_data: ResetPasswordRequest):
    """重置密码接口（无需旧密码）"""
    logger.info(f"尝试重置密码，邮箱: {reset_data.email}")

    # 根据邮箱查找用户
    user_data = storage.get_user(reset_data.username)
    if not user_data:
        return ApiResponse(
            event="reset_password", success=False, error="该邮箱未注册"
        ).dict()

    if not user_data["email"] or user_data["email"] != reset_data.email:
        return ApiResponse(
            event="reset_password", success=False, error="无效的邮箱地址"
        ).dict()

    # 更新密码
    user_data["hashed_password"] = get_password_hash(reset_data.new_password)

    # 保存更新后的用户数据
    if not storage.save_user(user_data["user_name"], user_data):
        return ApiResponse(
            event="reset_password", success=False, error="系统错误，请稍后重试"
        ).dict()

    logger.info(f"用户 {user_data['user_name']} (邮箱: {reset_data.email}) 密码已重置")
    return ApiResponse(
        event="reset_password",
        success=True,
        data={"message": "密码重置成功"},
    ).dict()
