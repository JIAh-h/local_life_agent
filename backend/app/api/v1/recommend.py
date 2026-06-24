from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.schemas.recommend import RecommendationResponse, RecommendationFeedback
from app.services.recommend import RecommendService

router = APIRouter()

@router.get("/today", response_model=List[RecommendationResponse])
async def get_today_recommendations(
    user_id: int,
    latitude: float = Query(..., description="用户纬度"),
    longitude: float = Query(..., description="用户经度"),
    db: Session = Depends(get_db)
):
    """获取今日推荐"""
    recommend_service = RecommendService(db)
    return recommend_service.get_today_recommendations(user_id, latitude, longitude)

@router.post("/feedback")
async def submit_recommendation_feedback(
    feedback_data: RecommendationFeedback,
    user_id: int,
    db: Session = Depends(get_db)
):
    """提交推荐反馈"""
    recommend_service = RecommendService(db)
    recommend_service.submit_feedback(user_id, feedback_data)
    return {"message": "反馈提交成功"}

@router.post("/refresh", response_model=List[RecommendationResponse])
async def refresh_recommendations(
    user_id: int,
    latitude: float = Query(..., description="用户纬度"),
    longitude: float = Query(..., description="用户经度"),
    db: Session = Depends(get_db)
):
    """刷新推荐内容"""
    recommend_service = RecommendService(db)
    return recommend_service.refresh_recommendations(user_id, latitude, longitude)
