from pydantic import BaseModel, Field
from typing import Optional, List, Union, Any
from datetime import datetime


class CommentItem(BaseModel):
    """评论与子评论"""
    id: str = Field("", description="评论ID")
    content: str = Field("", description="评论内容")
    create_time: str = Field("", description="评论时间")
    ip_location: str = Field("", description="IP属地")
    like_count: int = Field(0, description="点赞数")
    user_nickname: str = Field("", description="用户昵称")
    user_image: str = Field("", description="用户头像")
    sub_comments: list = Field(default_factory=list, description="子回复列表")


class FavoriteCreate(BaseModel):
    """创建收藏 — 关联小红书笔记"""
    note_id: str = Field(..., description="小红书笔记ID")
    category: int = Field(1, description="分类: 1=美食 2=景点")
    # 笔记详情（同步写入 xhs_notes）
    display_title: str = Field("", description="标题")
    cover_url: str = Field("", description="封面图URL")
    image_urls: list = Field(default_factory=list, description="图片列表")
    description: str = Field("", description="完整文案")
    author_name: str = Field("", description="作者昵称")
    author_avatar: str = Field("", description="作者头像")
    publish_time: Union[str, int] = Field("", description="发布时间")
    like_count: int = Field(0, description="点赞数")
    collect_count: int = Field(0, description="收藏数")
    comment_count: int = Field(0, description="评论数")
    xsec_token: str = Field("", description="访问令牌")
    comments: List[CommentItem] = Field(default_factory=list, description="评论列表（含子评论）")


class FavoriteResponse(BaseModel):
    id: int
    user_id: int
    note_id: str
    category: int
    created_at: datetime
    # 关联的笔记信息
    note_title: str = ""
    note_cover: str = ""
    note_author: str = ""
    note_author_avatar: str = ""
    note_publish_time: str = ""
    note_desc: str = ""
    note_like_count: int = 0
    note_collect_count: int = 0
    note_image_urls: list = []
    note_comment_count: int = 0
    xsec_token: str = ""
    comments: List[CommentItem] = Field(default_factory=list, description="评论列表")

    class Config:
        from_attributes = True


class FavoriteListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[FavoriteResponse]
