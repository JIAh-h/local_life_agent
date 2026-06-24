from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class ShareBase(BaseModel):
    """分享基础模型"""
    share_type: str = Field(..., max_length=10, description="分享类型（merchant/attraction）")
    share_id: int = Field(..., description="分享对象ID")
    share_channel: str = Field(..., max_length=32, description="分享渠道（wechat/moments/link）")

class ShareCreate(ShareBase):
    """创建分享模型"""
    pass

class ShareResponse(ShareBase):
    """分享响应模型"""
    id: int = Field(..., description="分享ID")
    user_id: int = Field(..., description="用户ID")
    share_url: str = Field(..., description="分享链接")
    view_count: int = Field(0, description="访问次数")
    created_at: datetime = Field(..., description="创建时间")
    
    class Config:
        from_attributes = True
