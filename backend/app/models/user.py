from sqlalchemy import Column, BigInteger, String, Text, DateTime, func, Boolean, Integer
from sqlalchemy.orm import relationship
from app.database import Base

class User(Base):
    """用户表"""
    __tablename__ = "users"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # 基础认证字段
    username = Column(String(32), unique=True, index=True, comment="用户名")
    hashed_password = Column(String(128), comment="密码哈希")
    phone = Column(String(20), unique=True, index=True, comment="手机号")
    email = Column(String(128), unique=True, index=True, nullable=True, comment="邮箱")
    
    # 第三方登录字段
    openid = Column(String(64), unique=True, nullable=True, comment="微信openid")
    qq_openid = Column(String(64), unique=True, nullable=True, comment="QQ openid")
    
    # 用户信息字段
    nickname = Column(String(32), comment="用户昵称")
    avatar_url = Column(Text, comment="头像URL或Base64")
    
    # 安全相关字段
    is_active = Column(Boolean, default=True, comment="账户是否激活")
    login_attempts = Column(Integer, default=0, comment="登录失败尝试次数")
    locked_until = Column(DateTime, nullable=True, comment="账户锁定截止时间")
    last_login = Column(DateTime, nullable=True, comment="最后登录时间")
    
    # 时间字段
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    
    # 关系
    locations = relationship("UserLocation", back_populates="user")
    location_logs = relationship("LocationLog", back_populates="user")
    merchant_ratings = relationship("MerchantRating", back_populates="user")
    attraction_ratings = relationship("AttractionRating", back_populates="user")
    # 注意：chat_history, chat_contexts, intent_logs 的外键已移除，不再建立 ORM 关系
    favorites = relationship("UserFavorite", back_populates="user")
    share_logs = relationship("ShareLog", back_populates="user")
    daily_recommendations = relationship("DailyRecommendation", back_populates="user")
    search_history = relationship("SearchHistory", back_populates="user")
