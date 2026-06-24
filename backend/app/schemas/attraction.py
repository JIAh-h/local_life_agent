from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from decimal import Decimal

class AttractionBase(BaseModel):
    """景点基础模型"""
    name: str = Field(..., max_length=128, description="景点名称")
    address: str = Field(..., max_length=256, description="详细地址")
    latitude: Decimal = Field(..., description="纬度")
    longitude: Decimal = Field(..., description="经度")
    city: Optional[str] = Field(None, max_length=64, description="城市")
    district: Optional[str] = Field(None, max_length=64, description="区县")
    category: str = Field(..., max_length=64, description="景点类别")
    subcategory: Optional[str] = Field(None, max_length=64, description="子类别")
    rating: Decimal = Field(0, description="评分（0-5）")
    rating_count: int = Field(0, description="评分人数")
    ticket_price: Decimal = Field(0, description="门票价格（0表示免费）")
    opening_hours: Optional[str] = Field(None, max_length=128, description="开放时间")
    phone: Optional[str] = Field(None, max_length=20, description="联系电话")
    tags: Optional[List[str]] = Field(None, description="标签")
    highlights: Optional[List[str]] = Field(None, description="亮点介绍")
    images: Optional[List[str]] = Field(None, description="景点图片")
    description: Optional[str] = Field(None, description="景点描述")

class AttractionCreate(AttractionBase):
    """创建景点模型"""
    source: str = Field("gaode", max_length=32, description="数据来源")
    source_id: Optional[str] = Field(None, max_length=64, description="来源ID")

class AttractionUpdate(BaseModel):
    """更新景点模型"""
    name: Optional[str] = Field(None, max_length=128, description="景点名称")
    address: Optional[str] = Field(None, max_length=256, description="详细地址")
    category: Optional[str] = Field(None, max_length=64, description="景点类别")
    rating: Optional[Decimal] = Field(None, description="评分")
    ticket_price: Optional[Decimal] = Field(None, description="门票价格")
    opening_hours: Optional[str] = Field(None, max_length=128, description="开放时间")
    phone: Optional[str] = Field(None, max_length=20, description="联系电话")
    tags: Optional[List[str]] = Field(None, description="标签")
    highlights: Optional[List[str]] = Field(None, description="亮点介绍")
    description: Optional[str] = Field(None, description="景点描述")

class AttractionResponse(AttractionBase):
    """景点响应模型"""
    id: int = Field(..., description="景点ID")
    source: str = Field(..., description="数据来源")
    source_id: Optional[str] = Field(None, description="来源ID")
    status: int = Field(1, description="状态（0禁用 1正常）")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    
    class Config:
        from_attributes = True

class AttractionListResponse(BaseModel):
    """景点列表响应模型"""
    total: int = Field(..., description="总数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页数量")
    items: List[AttractionResponse] = Field(..., description="景点列表")
