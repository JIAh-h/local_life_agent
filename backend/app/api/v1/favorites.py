from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.schemas.favorite import FavoriteCreate, FavoriteResponse, FavoriteListResponse
from app.services.favorite import FavoriteService

router = APIRouter()


@router.get("", response_model=FavoriteListResponse)
async def get_favorites(
    user_id: int,
    category: Optional[int] = Query(None, description="分类 1=美食 2=景点"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    svc = FavoriteService(db)
    return svc.get_favorites(user_id=user_id, category=category, page=page, page_size=page_size)


@router.post("")
async def add_favorite(data: FavoriteCreate, user_id: int, db: Session = Depends(get_db)):
    svc = FavoriteService(db)
    try:
        fav = svc.add_favorite(user_id, data)
        return {"id": fav.id, "message": "收藏成功"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{favorite_id}")
async def remove_favorite(favorite_id: int, user_id: int, db: Session = Depends(get_db)):
    svc = FavoriteService(db)
    try:
        svc.remove_favorite(user_id, favorite_id)
        return {"message": "已取消收藏"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/check")
async def check_favorited(
    note_id: str = Query(...),
    user_id: int = Query(...),
    db: Session = Depends(get_db)
):
    """检查某篇笔记是否已收藏"""
    from app.models.favorite import UserFavorite
    from sqlalchemy import and_
    exists = db.query(UserFavorite).filter(and_(
        UserFavorite.user_id == user_id,
        UserFavorite.note_id == note_id,
    )).first()
    return {"favorited": exists is not None, "id": exists.id if exists else None}
