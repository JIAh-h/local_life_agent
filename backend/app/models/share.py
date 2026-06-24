from sqlalchemy import Column, BigInteger, String, Integer, DateTime, func, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class ShareLog(Base):
    """分享日志表"""
    __tablename__ = "share_logs"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="分享用户ID")
    share_type = Column(String(10), nullable=False, comment="分享类型（merchant/attraction）")
    share_id = Column(BigInteger, nullable=False, comment="分享对象ID")
    share_channel = Column(String(32), nullable=False, comment="分享渠道（wechat/moments/link）")
    share_url = Column(String(512), nullable=False, comment="分享链接")
    view_count = Column(Integer, default=0, comment="访问次数")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    
    # 关系
    user = relationship("User", back_populates="share_logs")
