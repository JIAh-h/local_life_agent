"""
小红书笔记数据模型
"""
from sqlalchemy import Column, BigInteger, String, Integer, DateTime, func, Text, JSON, SmallInteger, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class XhsNote(Base):
    """小红书笔记表"""
    __tablename__ = "xhs_notes"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    note_id = Column(String(64), unique=True, nullable=False, index=True, comment="小红书笔记ID")
    xsec_token = Column(String(256), nullable=False, comment="访问令牌")
    display_title = Column(String(256), comment="标题")
    cover_url = Column(Text, comment="封面图URL")
    publish_time = Column(String(32), comment="发布时间")
    author_name = Column(String(64), comment="作者昵称")
    author_avatar = Column(Text, comment="作者头像")
    thumbnails = Column(JSON, comment="缩略图列表")
    image_urls = Column(JSON, comment="完整图片列表（从详情获取后填充）")
    description = Column(Text, comment="完整文案（从详情获取后填充）")
    like_count = Column(Integer, default=0, comment="点赞数")
    collect_count = Column(Integer, default=0, comment="收藏数")
    search_keyword = Column(String(128), index=True, comment="搜索时的关键词")
    source = Column(String(32), default="xiaohongshu", comment="数据来源")
    status = Column(SmallInteger, default=1, comment="状态 0删除 1正常")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    # 关联
    comments = relationship("XhsComment", back_populates="note", cascade="all, delete-orphan")


class XhsComment(Base):
    """小红书评论表（主评论与子回复统一存放）"""
    __tablename__ = "xhs_comments"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    comment_id = Column(String(64), unique=True, nullable=False, comment="小红书评论ID")
    note_id = Column(String(64), ForeignKey("xhs_notes.note_id", ondelete="CASCADE"), nullable=False, index=True, comment="所属笔记ID")
    parent_id = Column(String(64), default=None, index=True, comment="父评论ID（NULL=主评论）")
    content = Column(Text, nullable=False, comment="评论内容")
    create_time = Column(String(32), comment="评论时间")
    ip_location = Column(String(64), comment="IP属地")
    like_count = Column(Integer, default=0, comment="点赞数")
    user_nickname = Column(String(64), comment="用户昵称")
    user_avatar = Column(Text, comment="用户头像")
    status = Column(SmallInteger, default=1, comment="状态")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")

    # 关联
    note = relationship("XhsNote", back_populates="comments")
