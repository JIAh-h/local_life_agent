"""
Pytest配置和公共Fixtures

提供测试数据库、测试客户端等公共fixture
"""

import pytest
import asyncio
from typing import Generator, AsyncGenerator
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.config import settings
from app.models.user import User
from app.utils.security import create_access_token, create_refresh_token


# ==================== 测试数据库配置 ====================

# 使用SQLite内存数据库进行测试
TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环（用于异步测试）"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """
    创建测试数据库会话
    
    每个测试函数都会获得一个新的数据库会话，测试结束后回滚
    """
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """
    创建测试客户端
    
    使用测试数据库替代生产数据库
    """
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# ==================== 用户Fixtures ====================

@pytest.fixture
def test_user(db_session: Session) -> User:
    """
    创建测试用户
    """
    user = User(
        openid="test_openid_001",
        nickname="测试用户",
        avatar_url="https://example.com/avatar.jpg",
        phone="13800138001"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_user_token(test_user: User) -> str:
    """
    获取测试用户的Access Token
    """
    return create_access_token(data={"sub": str(test_user.id)})


@pytest.fixture
def test_user_refresh_token(test_user: User) -> str:
    """
    获取测试用户的Refresh Token
    """
    return create_refresh_token(data={"sub": str(test_user.id)})


@pytest.fixture
def authorized_headers(test_user_token: str) -> dict:
    """
    获取包含认证信息的请求头
    """
    return {"Authorization": f"Bearer {test_user_token}"}


# ==================== 数据Fixtures ====================

@pytest.fixture
def sample_merchant(db_session: Session, test_user: User):
    """
    创建测试商家数据
    """
    from app.models.merchant import Merchant
    
    merchant = Merchant(
        name="测试餐厅",
        address="北京市朝阳区测试路123号",
        latitude=39.9042,
        longitude=116.4074,
        city="北京",
        district="朝阳区",
        category="火锅",
        rating=4.5,
        avg_price=120.00,
        phone="010-12345678",
        business_hours="10:00-22:00",
        tags=["人气最高", "服务好"],
        recommended_dishes=["毛肚", "虾滑"]
    )
    db_session.add(merchant)
    db_session.commit()
    db_session.refresh(merchant)
    return merchant


@pytest.fixture
def sample_attraction(db_session: Session, test_user: User):
    """
    创建测试景点数据
    """
    from app.models.attraction import Attraction
    
    attraction = Attraction(
        name="测试公园",
        address="北京市海淀区测试路456号",
        latitude=39.9842,
        longitude=116.3074,
        city="北京",
        district="海淀区",
        category="公园",
        rating=4.8,
        ticket_price=0.00,
        opening_hours="06:00-22:00",
        phone="010-87654321",
        tags=["免费景点", "亲子友好"],
        highlights=["樱花大道", "人工湖"]
    )
    db_session.add(attraction)
    db_session.commit()
    db_session.refresh(attraction)
    return attraction


# ==================== Mock Fixtures ====================

@pytest.fixture
def mock_redis(monkeypatch):
    """
    Mock Redis客户端
    """
    class MockRedis:
        def __init__(self):
            self.data = {}
        
        def get(self, key):
            return self.data.get(key)
        
        def set(self, key, value, ex=None):
            self.data[key] = value
        
        def delete(self, key):
            if key in self.data:
                del self.data[key]
        
        def exists(self, key):
            return key in self.data
        
        def keys(self, pattern):
            return [k for k in self.data.keys() if pattern.replace("*", "") in k]
    
    return MockRedis()
