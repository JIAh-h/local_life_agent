"""
认证API测试

测试用户注册、登录、Token刷新、登出等接口
"""

import pytest
from fastapi import status


class TestAuthRegister:
    """用户注册测试"""
    
    def test_register_success(self, client):
        """测试注册成功"""
        response = client.post("/api/v1/auth/register", json={
            "openid": "new_test_openid",
            "nickname": "新用户",
            "device_info": "Test Device"
        })
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
    
    def test_register_duplicate_openid(self, client, test_user):
        """测试重复openid注册"""
        response = client.post("/api/v1/auth/register", json={
            "openid": test_user.openid,
            "nickname": "重复用户"
        })
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestAuthLogin:
    """用户登录测试"""
    
    def test_login_success(self, client, test_user):
        """测试登录成功"""
        response = client.post("/api/v1/auth/login", json={
            "openid": test_user.openid,
            "device_info": "Test Device"
        })
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
    
    def test_login_user_not_found(self, client):
        """测试用户不存在"""
        response = client.post("/api/v1/auth/login", json={
            "openid": "nonexistent_openid"
        })
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestAuthRefresh:
    """Token刷新测试"""
    
    def test_refresh_success(self, client, test_user_refresh_token):
        """测试Token刷新成功"""
        response = client.post("/api/v1/auth/refresh", json={
            "refresh_token": test_user_refresh_token
        })
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
    
    def test_refresh_invalid_token(self, client):
        """测试无效Token刷新"""
        response = client.post("/api/v1/auth/refresh", json={
            "refresh_token": "invalid_token"
        })
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestAuthLogout:
    """用户登出测试"""
    
    def test_logout_success(self, client, authorized_headers):
        """测试登出成功"""
        response = client.post("/api/v1/auth/logout", headers=authorized_headers)
        assert response.status_code == status.HTTP_200_OK
    
    def test_logout_all_devices(self, client, authorized_headers):
        """测试登出所有设备"""
        response = client.post("/api/v1/auth/logout-all", headers=authorized_headers)
        assert response.status_code == status.HTTP_200_OK


class TestAuthVerify:
    """Token验证测试"""
    
    def test_verify_token_success(self, client, authorized_headers):
        """测试Token验证成功"""
        response = client.get("/api/v1/auth/verify-token", headers=authorized_headers)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["valid"] is True
    
    def test_verify_token_no_auth(self, client):
        """测试未认证访问"""
        response = client.get("/api/v1/auth/verify-token")
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestAuthMe:
    """获取当前用户信息测试"""
    
    def test_get_current_user(self, client, authorized_headers, test_user):
        """测试获取当前用户信息"""
        response = client.get("/api/v1/auth/me", headers=authorized_headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == test_user.id
        assert data["openid"] == test_user.openid
