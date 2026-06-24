"""
安全工具测试

测试JWT Token的生成、验证、存储等功能
"""

import pytest
from datetime import datetime, timedelta
from jose import jwt

from app.config import settings
from app.utils.security import (
    create_access_token,
    create_refresh_token,
    verify_token,
    get_token_from_redis,
    save_token_to_redis,
    delete_token_from_redis,
    add_to_blacklist,
    is_blacklisted,
    revoke_all_user_tokens
)


class TestTokenCreation:
    """Token生成测试"""
    
    def test_create_access_token(self):
        """测试生成Access Token"""
        token = create_access_token(data={"sub": "123"})
        assert token is not None
        assert isinstance(token, str)
        
        # 解码验证
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert payload["sub"] == "123"
        assert payload["type"] == "access"
        assert "exp" in payload
    
    def test_create_refresh_token(self):
        """测试生成Refresh Token"""
        token = create_refresh_token(data={"sub": "123"})
        assert token is not None
        assert isinstance(token, str)
        
        # 解码验证
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert payload["sub"] == "123"
        assert payload["type"] == "refresh"
        assert "exp" in payload
    
    def test_create_token_with_custom_expiry(self):
        """测试自定义过期时间"""
        expires = timedelta(hours=2)
        token = create_access_token(data={"sub": "123"}, expires_delta=expires)
        
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        exp_time = datetime.fromtimestamp(payload["exp"])
        # 验证过期时间大约在2小时后（允许1分钟误差）
        assert exp_time > datetime.utcnow() + timedelta(hours=1, minutes=59)


class TestTokenVerification:
    """Token验证测试"""
    
    def test_verify_valid_access_token(self):
        """测试验证有效的Access Token"""
        token = create_access_token(data={"sub": "123"})
        payload = verify_token(token, "access")
        assert payload["sub"] == "123"
    
    def test_verify_valid_refresh_token(self):
        """测试验证有效的Refresh Token"""
        token = create_refresh_token(data={"sub": "123"})
        payload = verify_token(token, "refresh")
        assert payload["sub"] == "123"
    
    def test_verify_token_wrong_type(self):
        """测试Token类型不匹配"""
        token = create_access_token(data={"sub": "123"})
        with pytest.raises(Exception):
            verify_token(token, "refresh")
    
    def test_verify_invalid_token(self):
        """测试验证无效Token"""
        with pytest.raises(Exception):
            verify_token("invalid_token", "access")
    
    def test_verify_expired_token(self):
        """测试验证过期Token"""
        expires = timedelta(seconds=-1)
        token = create_access_token(data={"sub": "123"}, expires_delta=expires)
        with pytest.raises(Exception):
            verify_token(token, "access")


class TestTokenBlacklist:
    """Token黑名单测试"""
    
    def test_add_to_blacklist(self):
        """测试添加到黑名单"""
        token = create_access_token(data={"sub": "123"})
        result = add_to_blacklist(token)
        assert result is True
        assert is_blacklisted(token) is True
    
    def test_is_not_blacklisted(self):
        """测试Token不在黑名单中"""
        token = create_access_token(data={"sub": "123"})
        assert is_blacklisted(token) is False
