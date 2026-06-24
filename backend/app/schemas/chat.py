from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class ChatMessage(BaseModel):
    """聊天消息模型"""
    message: str = Field(..., description="用户消息")
    session_id: Optional[str] = Field(None, description="会话ID")
    latitude: Optional[float] = Field(None, description="用户纬度")
    longitude: Optional[float] = Field(None, description="用户经度")

class ChatResponse(BaseModel):
    """聊天响应模型"""
    message: str = Field(..., description="AI回复")
    session_id: str = Field(..., description="会话ID")
    recommendations: Optional[List[Dict[str, Any]]] = Field(None, description="推荐结果")
    suggestions: Optional[List[str]] = Field(None, description="对话建议")
    intent: Optional[str] = Field(None, description="识别意图")
    entities: Optional[Dict[str, Any]] = Field(None, description="提取实体")

class ChatHistoryResponse(BaseModel):
    """对话历史响应模型"""
    id: int = Field(..., description="消息ID")
    user_id: int = Field(..., description="用户ID")
    session_id: str = Field(..., description="会话ID")
    message_type: str = Field(..., description="消息类型（user/ai）")
    content: str = Field(..., description="消息内容")
    message_metadata: Optional[Dict[str, Any]] = Field(None, description="消息元数据")
    created_at: datetime = Field(..., description="创建时间")
    
    class Config:
        from_attributes = True
