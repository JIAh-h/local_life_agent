from sqlalchemy import Column, BigInteger, String, Integer, DateTime, func, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class SearchHistory(Base):
    """搜索历史表"""
    __tablename__ = "search_history"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="用户ID")
    keyword = Column(String(128), nullable=False, comment="搜索关键词")
    search_type = Column(String(32), nullable=False, comment="搜索类型（food/attraction）")
    result_count = Column(Integer, default=0, comment="结果数量")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    
    # 关系
    user = relationship("User", back_populates="search_history")
