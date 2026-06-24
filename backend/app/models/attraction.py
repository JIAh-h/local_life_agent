from sqlalchemy import Column, BigInteger, String, Integer, DateTime, func, ForeignKey, DECIMAL, JSON, Text, SmallInteger
from sqlalchemy.orm import relationship
from app.database import Base

class Attraction(Base):
    """景点表"""
    __tablename__ = "attractions"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False, comment="景点名称")
    address = Column(String(256), nullable=False, comment="详细地址")
    latitude = Column(DECIMAL(10, 7), nullable=False, comment="纬度")
    longitude = Column(DECIMAL(10, 7), nullable=False, comment="经度")
    city = Column(String(64), comment="城市")
    district = Column(String(64), comment="区县")
    category = Column(String(64), nullable=False, comment="景点类别（公园、博物馆、商场等）")
    subcategory = Column(String(64), comment="子类别")
    rating = Column(DECIMAL(3, 1), default=0, comment="评分（0-5）")
    rating_count = Column(Integer, default=0, comment="评分人数")
    ticket_price = Column(DECIMAL(10, 2), default=0, comment="门票价格（0表示免费）")
    opening_hours = Column(String(128), comment="开放时间")
    phone = Column(String(20), comment="联系电话")
    tags = Column(JSON, comment="标签（如免费景点、亲子友好）")
    highlights = Column(JSON, comment="亮点介绍")
    images = Column(JSON, comment="景点图片")
    description = Column(Text, comment="景点描述")
    source = Column(String(32), default="gaode", comment="数据来源")
    source_id = Column(String(64), comment="来源ID")
    status = Column(SmallInteger, default=1, comment="状态（0禁用 1正常）")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    
    # 关系
    ratings = relationship("AttractionRating", back_populates="attraction")

class AttractionRating(Base):
    """景点评分表"""
    __tablename__ = "attraction_ratings"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    attraction_id = Column(BigInteger, ForeignKey("attractions.id", ondelete="CASCADE"), nullable=False, comment="景点ID")
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="用户ID")
    rating = Column(DECIMAL(3, 1), nullable=False, comment="评分（0-5）")
    comment = Column(Text, comment="评价内容")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    
    # 关系
    attraction = relationship("Attraction", back_populates="ratings")
    user = relationship("User", back_populates="attraction_ratings")
