from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.schemas.location import LocationCreate, LocationUpdate, LocationResponse, LocationSetRequest
from app.services.location import LocationService

router = APIRouter()

@router.get("/current", response_model=LocationResponse)
async def get_current_location(
    user_id: int,
    db: Session = Depends(get_db)
):
    """获取用户当前位置"""
    location_service = LocationService(db)
    location = location_service.get_current_location(user_id)
    if not location:
        raise HTTPException(status_code=404, detail="未找到用户位置")
    return location

@router.post("/set", response_model=LocationResponse)
async def set_location(
    location_data: LocationSetRequest,
    user_id: int,
    db: Session = Depends(get_db)
):
    """手动设置用户位置"""
    location_service = LocationService(db)
    return location_service.set_location(user_id, location_data)

@router.get("/favorites", response_model=List[LocationResponse])
async def get_favorite_locations(
    user_id: int,
    db: Session = Depends(get_db)
):
    """获取用户常用位置列表"""
    location_service = LocationService(db)
    return location_service.get_favorite_locations(user_id)

@router.post("/favorites", response_model=LocationResponse)
async def add_favorite_location(
    location_data: LocationCreate,
    user_id: int,
    db: Session = Depends(get_db)
):
    """添加常用位置"""
    location_service = LocationService(db)
    return location_service.add_favorite_location(user_id, location_data)

@router.put("/favorites/{location_id}", response_model=LocationResponse)
async def update_favorite_location(
    location_id: int,
    location_data: LocationUpdate,
    user_id: int,
    db: Session = Depends(get_db)
):
    """更新常用位置"""
    location_service = LocationService(db)
    return location_service.update_favorite_location(user_id, location_id, location_data)

@router.delete("/favorites/{location_id}")
async def delete_favorite_location(
    location_id: int,
    user_id: int,
    db: Session = Depends(get_db)
):
    """删除常用位置"""
    location_service = LocationService(db)
    location_service.delete_favorite_location(user_id, location_id)
    return {"message": "删除成功"}

@router.post("/switch/{location_id}", response_model=LocationResponse)
async def switch_location(
    location_id: int,
    user_id: int,
    db: Session = Depends(get_db)
):
    """切换到常用位置"""
    location_service = LocationService(db)
    return location_service.switch_location(user_id, location_id)
