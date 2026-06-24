from sqlalchemy import Column, BigInteger, DateTime, func, ForeignKey, String, SmallInteger
from sqlalchemy.orm import relationship
from app.database import Base


class UserFavorite(Base):
    """用户收藏表（关联小红书笔记）"""
    __tablename__ = "user_favorites"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="用户ID")
    note_id = Column(String(64), ForeignKey("xhs_notes.note_id", ondelete="CASCADE"), nullable=False, index=True, comment="小红书笔记ID")
    category = Column(SmallInteger, nullable=False, default=1, comment="分类: 1=美食 2=景点")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")

    # 关系
    user = relationship("User", back_populates="favorites")
    note = relationship("XhsNote")
