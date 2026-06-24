from sqlalchemy import Column, BigInteger, String, Integer, DateTime, func, ForeignKey, DECIMAL, JSON, Text, SmallInteger
from sqlalchemy.orm import relationship
from app.database import Base

class Merchant(Base):
    """商家表"""
    __tablename__ = "merchants"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False, comment="商家名称")
    address = Column(String(256), nullable=False, comment="详细地址")
    latitude = Column(DECIMAL(10, 7), nullable=False, comment="纬度")
    longitude = Column(DECIMAL(10, 7), nullable=False, comment="经度")
    city = Column(String(64), comment="城市")
    district = Column(String(64), comment="区县")
    category = Column(String(64), nullable=False, comment="商家类别（火锅、烧烤、日料等）")
    subcategory = Column(String(64), comment="子类别")
    rating = Column(DECIMAL(3, 1), default=0, comment="评分（0-5）")
    rating_count = Column(Integer, default=0, comment="评分人数")
    avg_price = Column(DECIMAL(10, 2), default=0, comment="人均消费（元）")
    phone = Column(String(20), comment="联系电话")
    business_hours = Column(String(128), comment="营业时间")
    tags = Column(JSON, comment="标签（如人气最高、新开店铺）")
    recommended_dishes = Column(JSON, comment="推荐菜品")
    images = Column(JSON, comment="商家图片")
    description = Column(Text, comment="商家描述")
    source = Column(String(32), default="gaode", comment="数据来源")
    source_id = Column(String(64), comment="来源ID")
    status = Column(SmallInteger, default=1, comment="状态（0禁用 1正常）")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    
    # 关系
    ratings = relationship("MerchantRating", back_populates="merchant")

class MerchantRating(Base):
    """商家评分表"""
    __tablename__ = "merchant_ratings"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    merchant_id = Column(BigInteger, ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False, comment="商家ID")
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="用户ID")
    rating = Column(DECIMAL(3, 1), nullable=False, comment="评分（0-5）")
    comment = Column(Text, comment="评价内容")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    
    # 关系
    merchant = relationship("Merchant", back_populates="ratings")
    user = relationship("User", back_populates="merchant_ratings")
