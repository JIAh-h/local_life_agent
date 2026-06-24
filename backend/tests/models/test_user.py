"""
用户模型测试

测试用户模型的创建、更新、查询等操作
"""

import pytest
from app.models.user import User


class TestUserModel:
    """用户模型测试"""
    
    def test_create_user(self, db_session):
        """测试创建用户"""
        user = User(
            openid="test_create_user",
            nickname="创建测试用户",
            avatar_url="https://example.com/avatar.jpg",
            phone="13800000001"
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        
        assert user.id is not None
        assert user.openid == "test_create_user"
        assert user.nickname == "创建测试用户"
        assert user.created_at is not None
        assert user.updated_at is not None
    
    def test_user_repr(self, test_user):
        """测试用户字符串表示"""
        assert "测试用户" in repr(test_user)
    
    def test_update_user(self, db_session, test_user):
        """测试更新用户信息"""
        test_user.nickname = "更新后的昵称"
        test_user.phone = "13800000002"
        db_session.commit()
        db_session.refresh(test_user)
        
        assert test_user.nickname == "更新后的昵称"
        assert test_user.phone == "13800000002"
    
    def test_query_user_by_openid(self, db_session, test_user):
        """测试通过openid查询用户"""
        user = db_session.query(User).filter(User.openid == test_user.openid).first()
        assert user is not None
        assert user.id == test_user.id
    
    def test_query_user_by_id(self, db_session, test_user):
        """测试通过ID查询用户"""
        user = db_session.query(User).filter(User.id == test_user.id).first()
        assert user is not None
        assert user.openid == test_user.openid
    
    def test_user_optional_fields(self, db_session):
        """测试用户可选字段"""
        user = User(openid="test_optional_fields")
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        
        assert user.nickname is None
        assert user.avatar_url is None
        assert user.phone is None
