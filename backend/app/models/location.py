from sqlalchemy import Column, BigInteger, String, Boolean, DateTime, func, ForeignKey, DECIMAL, Float
from sqlalchemy.orm import relationship
from app.database import Base

class UserLocation(Base):
    """用户位置表"""
    __tablename__ = "user_locations"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="用户ID")
    name = Column(String(32), nullable=False, comment="位置名称（家、公司等）")
    address = Column(String(256), nullable=False, comment="详细地址")
    latitude = Column(DECIMAL(10, 7), nullable=False, comment="纬度")
    longitude = Column(DECIMAL(10, 7), nullable=False, comment="经度")
    city = Column(String(64), comment="城市")
    district = Column(String(64), comment="区县")
    is_default = Column(Boolean, default=False, comment="是否默认位置")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    
    # 关系
    user = relationship("User", back_populates="locations")

class LocationLog(Base):
    """定位日志表"""
    __tablename__ = "location_logs"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="用户ID")
    latitude = Column(DECIMAL(10, 7), nullable=False, comment="纬度")
    longitude = Column(DECIMAL(10, 7), nullable=False, comment="经度")
    accuracy = Column(Float, comment="定位精度（米）")
    source = Column(String(32), nullable=False, comment="定位来源（browser/ip/manual）")
    ip_address = Column(String(45), comment="IP地址")
    user_agent = Column(String(512), comment="用户代理")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    
    # 关系
    user = relationship("User", back_populates="location_logs")
