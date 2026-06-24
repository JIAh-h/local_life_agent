from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from decimal import Decimal

class LocationBase(BaseModel):
    """位置基础模型"""
    name: str = Field(..., max_length=32, description="位置名称（家、公司等）")
    address: str = Field(..., max_length=256, description="详细地址")
    latitude: Decimal = Field(..., description="纬度")
    longitude: Decimal = Field(..., description="经度")
    city: Optional[str] = Field(None, max_length=64, description="城市")
    district: Optional[str] = Field(None, max_length=64, description="区县")

class LocationCreate(LocationBase):
    """创建位置模型"""
    is_default: bool = Field(False, description="是否默认位置")

class LocationUpdate(BaseModel):
    """更新位置模型"""
    name: Optional[str] = Field(None, max_length=32, description="位置名称")
    address: Optional[str] = Field(None, max_length=256, description="详细地址")
    latitude: Optional[Decimal] = Field(None, description="纬度")
    longitude: Optional[Decimal] = Field(None, description="经度")
    city: Optional[str] = Field(None, max_length=64, description="城市")
    district: Optional[str] = Field(None, max_length=64, description="区县")
    is_default: Optional[bool] = Field(None, description="是否默认位置")

class LocationResponse(LocationBase):
    """位置响应模型"""
    id: int = Field(..., description="位置ID")
    user_id: int = Field(..., description="用户ID")
    is_default: bool = Field(..., description="是否默认位置")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    
    class Config:
        from_attributes = True

class LocationSetRequest(BaseModel):
    """设置位置请求模型"""
    latitude: Decimal = Field(..., description="纬度")
    longitude: Decimal = Field(..., description="经度")
    address: Optional[str] = Field(None, max_length=256, description="详细地址")
    accuracy: Optional[float] = Field(None, description="定位精度（米）")
    source: str = Field("manual", max_length=32, description="定位来源")
