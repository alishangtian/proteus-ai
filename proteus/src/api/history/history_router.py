from fastapi import APIRouter, HTTPException, Body
from datetime import datetime
from typing import Optional
from src.api.history_service import HistoryService
from src.login.login_router import ApiResponse

router = APIRouter(tags=["历史记录模块"])
history_service = HistoryService()

@router.get("/history", response_model=ApiResponse)
async def get_history():
    """获取所有历史记录
    
    Returns:
        dict: 包含历史记录的响应
    """
    try:
        history = history_service.get_all_history()
        return ApiResponse(
            event="get_history",
            success=True,
            data={"items": history}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history/{chat_id}", response_model=ApiResponse)
async def get_history_by_id(chat_id: str):
    """根据ID获取历史记录
    
    Args:
        chat_id: 聊天ID
        
    Returns:
        dict: 包含历史记录的响应
    """
    try:
        history = history_service.get_history_by_id(chat_id)
        if not history:
            raise HTTPException(status_code=404, detail="History not found")
        return ApiResponse(
            event="get_history_by_id",
            success=True,
            data={"item": history}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/history/{chat_id}", response_model=ApiResponse)
async def delete_history(chat_id: str):
    """删除历史记录
    
    Args:
        chat_id: 聊天ID
        
    Returns:
        dict: 操作结果
    """
    try:
        success = history_service.delete_history(chat_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete history")
        return ApiResponse(
            event="delete_history",
            success=True,
            message="History deleted successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/history/{chat_id}/summary", response_model=ApiResponse)
async def update_history_summary(chat_id: str, summary: str = Body(..., embed=True)):
    """更新历史记录摘要
    
    Args:
        chat_id: 聊天ID
        summary: 摘要内容
        
    Returns:
        dict: 操作结果
    """
    try:
        success = history_service.update_history_summary(chat_id, summary)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update summary")
        return ApiResponse(
            event="update_history_summary",
            success=True,
            message="Summary updated successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))