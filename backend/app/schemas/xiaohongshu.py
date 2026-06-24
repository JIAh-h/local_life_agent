from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class NoteBase(BaseModel):
    """笔记基础模型"""
    title: str = Field(..., max_length=256, description="笔记标题")
    author: str = Field(..., max_length=64, description="作者昵称")
    author_avatar: Optional[str] = Field(None, max_length=512, description="作者头像")
    publish_time: datetime = Field(..., description="发布时间")
    like_count: int = Field(0, description="点赞数")
    comment_count: int = Field(0, description="评论数")
    collect_count: int = Field(0, description="收藏数")
    content: Optional[str] = Field(None, description="笔记内容")
    summary: Optional[str] = Field(None, description="内容摘要")
    pros: Optional[List[str]] = Field(None, description="优点列表")
    cons: Optional[List[str]] = Field(None, description="缺点列表")
    tips: Optional[List[str]] = Field(None, description="避坑提示")
    original_url: str = Field(..., max_length=512, description="原文链接")
    images: Optional[List[str]] = Field(None, description="笔记图片")

class NoteCreate(NoteBase):
    """创建笔记模型"""
    merchant_id: Optional[int] = Field(None, description="关联商家ID")
    attraction_id: Optional[int] = Field(None, description="关联景点ID")
    source: str = Field("xiaohongshu", max_length=32, description="数据来源")
    source_id: Optional[str] = Field(None, max_length=64, description="来源ID")

class NoteUpdate(BaseModel):
    """更新笔记模型"""
    title: Optional[str] = Field(None, max_length=256, description="笔记标题")
    content: Optional[str] = Field(None, description="笔记内容")
    summary: Optional[str] = Field(None, description="内容摘要")
    pros: Optional[List[str]] = Field(None, description="优点列表")
    cons: Optional[List[str]] = Field(None, description="缺点列表")
    tips: Optional[List[str]] = Field(None, description="避坑提示")

class NoteResponse(NoteBase):
    """笔记响应模型"""
    id: int = Field(..., description="笔记ID")
    merchant_id: Optional[int] = Field(None, description="关联商家ID")
    attraction_id: Optional[int] = Field(None, description="关联景点ID")
    source: str = Field(..., description="数据来源")
    source_id: Optional[str] = Field(None, description="来源ID")
    status: int = Field(1, description="状态（0禁用 1正常）")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    
    class Config:
        from_attributes = True

class NoteListResponse(BaseModel):
    """笔记列表响应模型"""
    total: int = Field(..., description="总数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页数量")
    items: List[NoteResponse] = Field(..., description="笔记列表")
