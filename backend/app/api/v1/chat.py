from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.schemas.chat import ChatMessage, ChatResponse, ChatHistoryResponse
from app.services.chat import ChatService

router = APIRouter()

@router.post("/send", response_model=ChatResponse)
async def send_message(
    message_data: ChatMessage,
    user_id: int,
    db: Session = Depends(get_db)
):
    """发送自然语言查询"""
    chat_service = ChatService(db)
    return chat_service.process_message(user_id, message_data)

@router.get("/history", response_model=List[ChatHistoryResponse])
async def get_chat_history(
    user_id: int,
    session_id: Optional[str] = Query(None, description="会话ID"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db)
):
    """获取对话历史记录"""
    chat_service = ChatService(db)
    return chat_service.get_history(
        user_id=user_id,
        session_id=session_id,
        page=page,
        page_size=page_size
    )

@router.delete("/history/{session_id}")
async def delete_chat_history(
    session_id: str,
    user_id: int,
    db: Session = Depends(get_db)
):
    """删除对话历史记录"""
    chat_service = ChatService(db)
    chat_service.delete_history(user_id, session_id)
    return {"message": "删除成功"}
