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
    ApiResponse
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
        
    return SessionData(
        username=session_data["username"],
        expires=session_data["expires"]
    )

@router.post("/register", response_model=ApiResponse)
async def register(register_data: RegisterRequest):
    """用户注册接口"""
    user_data = {
        "username": register_data.username,
        "email": register_data.email,
        "hashed_password": get_password_hash(register_data.password),
        "disabled": "False"
    }
    
    # 检查用户是否已存在
    if storage.get_user(register_data.username):
        return ApiResponse(
            event="register",
            success=False,
            error="用户名已存在"
        ).dict()
    
    # 保存用户数据
    if not storage.save_user(register_data.username, user_data):
        return ApiResponse(
            event="register",
            success=False,
            error="系统错误，请稍后重试"
        ).dict()
    
    return ApiResponse(
        event="register",
        success=True,
        data={"username": register_data.username}
    ).dict()

@router.post("/login", response_model=ApiResponse)
async def login(request: Request, login_data: LoginRequest):
    """用户登录接口"""
    logger.info(f"用户登录: {login_data.username}")
    
    # 获取用户数据
    user_data = storage.get_user(login_data.username)
    if not user_data or not verify_password(
        login_data.password, user_data["hashed_password"]
    ):
        return ApiResponse(
            event="login",
            success=False,
            error="无效的用户名或密码"
        ).dict()

    # 创建新会话
    session_id = str(uuid.uuid4())
    expires = datetime.now() + timedelta(minutes=SESSION_EXPIRE_MINUTES)
    session_data = {
        "username": login_data.username,
        "expires": expires.isoformat()
    }
    
    # 保存会话数据
    if not storage.save_session(session_id, session_data):
        return ApiResponse(
            event="login",
            success=False,
            error="系统错误，请稍后重试"
        ).dict()
    
    # 返回响应并设置cookie
    response = JSONResponse(
        content=ApiResponse(event="login", success=True).dict()
    )
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
            data={"username": user.username}
        ).dict()
    return ApiResponse(
        event="check_session",
        success=False,
        error="未登录"
    ).dict()