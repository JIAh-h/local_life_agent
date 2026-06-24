#!/usr/bin/env python3
"""
JWT双令牌机制测试脚本

测试内容：
1. Redis连接验证（db3）
2. Token生成与验证
3. Token存储与读取
4. Token清除逻辑
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.redis_client import get_redis
from app.utils.security import (
    create_access_token,
    create_refresh_token,
    verify_token,
    store_tokens_in_redis,
    get_token_from_redis,
    remove_token_from_redis,
    blacklist_token,
    is_token_blacklisted,
    revoke_all_user_tokens
)


def test_redis_connection():
    """测试Redis连接"""
    print("1. 测试Redis连接...")
    try:
        redis_client = get_redis()
        redis_client.ping()
        print(f"   ✓ Redis连接成功")
        
        # 检查是否使用db3
        info = redis_client.info("keyspace")
        print(f"   ✓ Redis数据库: {redis_client.connection_pool.connection_kwargs.get('db', 'unknown')}")
        return True
    except Exception as e:
        print(f"   ✗ Redis连接失败: {e}")
        return False


def test_token_creation():
    """测试Token创建"""
    print("\n2. 测试Token创建...")
    try:
        # 创建Access Token
        access_token = create_access_token(data={"sub": "123"})
        print(f"   ✓ Access Token创建成功: {access_token[:50]}...")
        
        # 创建Refresh Token
        refresh_token = create_refresh_token(data={"sub": "123"})
        print(f"   ✓ Refresh Token创建成功: {refresh_token[:50]}...")
        
        return access_token, refresh_token
    except Exception as e:
        print(f"   ✗ Token创建失败: {e}")
        return None, None


def test_token_verification(access_token, refresh_token):
    """测试Token验证"""
    print("\n3. 测试Token验证...")
    try:
        # 验证Access Token
        access_payload = verify_token(access_token, "access")
        print(f"   ✓ Access Token验证成功，用户ID: {access_payload.get('sub')}")
        
        # 验证Refresh Token
        refresh_payload = verify_token(refresh_token, "refresh")
        print(f"   ✓ Refresh Token验证成功，用户ID: {refresh_payload.get('sub')}")
        
        return True
    except Exception as e:
        print(f"   ✗ Token验证失败: {e}")
        return False


def test_token_storage(user_id, access_token, refresh_token):
    """测试Token存储"""
    print("\n4. 测试Token存储到Redis...")
    try:
        # 存储Token
        store_tokens_in_redis(
            user_id=user_id,
            access_token=access_token,
            refresh_token=refresh_token,
            device_info="test_device"
        )
        print(f"   ✓ Token存储成功")
        
        # 验证存储
        redis_client = get_redis()
        
        # 检查Access Token
        access_data = get_token_from_redis(access_token, "access")
        if access_data:
            print(f"   ✓ Access Token在Redis中存在，用户ID: {access_data.get('user_id')}")
        else:
            print(f"   ✗ Access Token在Redis中不存在")
            return False
        
        # 检查Refresh Token
        refresh_data = get_token_from_redis(refresh_token, "refresh")
        if refresh_data:
            print(f"   ✓ Refresh Token在Redis中存在，用户ID: {refresh_data.get('user_id')}")
        else:
            print(f"   ✗ Refresh Token在Redis中不存在")
            return False
        
        # 检查用户Token集合
        user_tokens_key = f"user_tokens:{user_id}"
        tokens = redis_client.smembers(user_tokens_key)
        print(f"   ✓ 用户Token集合存在，包含 {len(tokens)} 个Token")
        
        return True
    except Exception as e:
        print(f"   ✗ Token存储失败: {e}")
        return False


def test_token_removal(user_id, access_token, refresh_token):
    """测试Token删除"""
    print("\n5. 测试Token删除...")
    try:
        # 删除Access Token
        remove_token_from_redis(access_token, "access")
        
        # 验证删除
        access_data = get_token_from_redis(access_token, "access")
        if not access_data:
            print(f"   ✓ Access Token删除成功")
        else:
            print(f"   ✗ Access Token删除失败")
            return False
        
        # 删除Refresh Token
        remove_token_from_redis(refresh_token, "refresh")
        
        # 验证删除
        refresh_data = get_token_from_redis(refresh_token, "refresh")
        if not refresh_data:
            print(f"   ✓ Refresh Token删除成功")
        else:
            print(f"   ✗ Refresh Token删除失败")
            return False
        
        return True
    except Exception as e:
        print(f"   ✗ Token删除失败: {e}")
        return False


def test_token_blacklist():
    """测试Token黑名单"""
    print("\n6. 测试Token黑名单...")
    try:
        # 创建测试Token
        test_token = create_access_token(data={"sub": "456"})
        
        # 添加到黑名单
        blacklist_token(test_token, "access")
        print(f"   ✓ Token添加到黑名单成功")
        
        # 验证黑名单
        if is_token_blacklisted(test_token):
            print(f"   ✓ Token在黑名单中")
        else:
            print(f"   ✗ Token不在黑名单中")
            return False
        
        return True
    except Exception as e:
        print(f"   ✗ Token黑名单测试失败: {e}")
        return False


def test_revoke_all_tokens():
    """测试撤销所有Token"""
    print("\n7. 测试撤销所有Token...")
    try:
        user_id = 789
        
        # 创建多个Token对
        for i in range(3):
            access_token = create_access_token(data={"sub": str(user_id)})
            refresh_token = create_refresh_token(data={"sub": str(user_id)})
            store_tokens_in_redis(
                user_id=user_id,
                access_token=access_token,
                refresh_token=refresh_token,
                device_info=f"device_{i}"
            )
        
        # 验证Token存在
        redis_client = get_redis()
        user_tokens_key = f"user_tokens:{user_id}"
        tokens_before = redis_client.smembers(user_tokens_key)
        print(f"   ✓ 撤销前用户有 {len(tokens_before)} 个Token")
        
        # 撤销所有Token
        revoke_all_user_tokens(user_id)
        
        # 验证撤销
        tokens_after = redis_client.smembers(user_tokens_key)
        print(f"   ✓ 撤销后用户有 {len(tokens_after)} 个Token")
        
        if len(tokens_after) == 0:
            print(f"   ✓ 所有Token撤销成功")
            return True
        else:
            print(f"   ✗ Token撤销不完整")
            return False
    except Exception as e:
        print(f"   ✗ 撤销所有Token测试失败: {e}")
        return False


def main():
    """主测试函数"""
    print("=" * 60)
    print("JWT双令牌机制测试")
    print("=" * 60)
    print(f"Redis URL: {settings.REDIS_URL}")
    print(f"Access Token过期时间: {settings.ACCESS_TOKEN_EXPIRE_MINUTES} 分钟")
    print(f"Refresh Token过期时间: {settings.REFRESH_TOKEN_EXPIRE_DAYS} 天")
    print("=" * 60)
    
    # 测试Redis连接
    if not test_redis_connection():
        print("\n❌ Redis连接失败，请确保Redis服务正在运行")
        return
    
    # 测试Token创建
    access_token, refresh_token = test_token_creation()
    if not access_token or not refresh_token:
        return
    
    # 测试Token验证
    if not test_token_verification(access_token, refresh_token):
        return
    
    # 测试Token存储
    if not test_token_storage(123, access_token, refresh_token):
        return
    
    # 测试Token删除
    if not test_token_removal(123, access_token, refresh_token):
        return
    
    # 测试Token黑名单
    if not test_token_blacklist():
        return
    
    # 测试撤销所有Token
    if not test_revoke_all_tokens():
        return
    
    print("\n" + "=" * 60)
    print("✅ 所有测试通过！")
    print("=" * 60)


if __name__ == "__main__":
    main()