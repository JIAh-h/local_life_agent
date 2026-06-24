from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal

class RecommendationBase(BaseModel):
    """推荐基础模型"""
    recommend_type: str = Field(..., max_length=10, description="推荐类型（merchant/attraction）")
    recommend_id: int = Field(..., description="推荐对象ID")
    recommend_reason: str = Field(..., max_length=256, description="推荐理由")
    score: Decimal = Field(0, description="推荐分数")

class RecommendationResponse(RecommendationBase):
    """推荐响应模型"""
    id: int = Field(..., description="推荐ID")
    user_id: int = Field(..., description="用户ID")
    weather_info: Optional[Dict[str, Any]] = Field(None, description="天气信息")
    is_clicked: bool = Field(False, description="是否被点击")
    feedback: Optional[int] = Field(None, description="用户反馈（1喜欢 0无反馈 -1不喜欢）")
    created_at: datetime = Field(..., description="创建时间")
    
    class Config:
        from_attributes = True

class RecommendationFeedback(BaseModel):
    """推荐反馈模型"""
    recommendation_id: int = Field(..., description="推荐ID")
    feedback: int = Field(..., description="用户反馈（1喜欢 -1不喜欢）")
