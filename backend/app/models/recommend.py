from sqlalchemy import Column, BigInteger, String, Integer, DateTime, func, ForeignKey, JSON, DECIMAL, Boolean, SmallInteger
from sqlalchemy.orm import relationship
from app.database import Base

class DailyRecommendation(Base):
    """今日推荐表"""
    __tablename__ = "daily_recommendations"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="用户ID")
    recommend_type = Column(String(10), nullable=False, comment="推荐类型（merchant/attraction）")
    recommend_id = Column(BigInteger, nullable=False, comment="推荐对象ID")
    recommend_reason = Column(String(256), nullable=False, comment="推荐理由")
    weather_info = Column(JSON, comment="天气信息")
    score = Column(DECIMAL(5, 2), default=0, comment="推荐分数")
    is_clicked = Column(Boolean, default=False, comment="是否被点击")
    feedback = Column(SmallInteger, comment="用户反馈（1喜欢 0无反馈 -1不喜欢）")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    
    # 关系
    user = relationship("User", back_populates="daily_recommendations")
