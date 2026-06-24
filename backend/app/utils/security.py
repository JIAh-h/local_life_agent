from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
import bcrypt
from fastapi import HTTPException, status
import redis
import json
from app.config import settings
from app.redis_client import get_redis

# Redis键前缀常量
ACCESS_TOKEN_PREFIX = "access_token:"
REFRESH_TOKEN_PREFIX = "refresh_token:"
USER_TOKENS_PREFIX = "user_tokens:"
TOKEN_BLACKLIST_PREFIX = "token_blacklist:"


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    创建Access Token
    
    Args:
        data: 令牌数据，通常包含用户ID等信息
        expires_delta: 可选的过期时间增量
    
    Returns:
        JWT格式的Access Token字符串
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({
        "exp": expire,
        "type": "access",
        "iat": datetime.utcnow()
    })
    
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    创建Refresh Token
    
    Args:
        data: 令牌数据，通常包含用户ID等信息
        expires_delta: 可选的过期时间增量
    
    Returns:
        JWT格式的Refresh Token字符串
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    
    to_encode.update({
        "exp": expire,
        "type": "refresh",
        "iat": datetime.utcnow()
    })
    
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def verify_token(token: str, token_type: str = "access") -> Dict[str, Any]:
    """
    验证JWT Token
    
    Args:
        token: JWT Token字符串
        token_type: 令牌类型，"access"或"refresh"
    
    Returns:
        解码后的令牌数据
    
    Raises:
        HTTPException: 令牌无效或过期
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        
        # 验证令牌类型
        if payload.get("type") != token_type:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # 检查令牌是否在黑名单中
        if is_token_blacklisted(token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return payload
        
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def store_tokens_in_redis(
    user_id: int,
    access_token: str,
    refresh_token: str,
    device_info: Optional[str] = None
) -> None:
    """
    将Token信息写入Redis
    
    Args:
        user_id: 用户ID
        access_token: Access Token
        refresh_token: Refresh Token
        device_info: 设备信息（可选）
    """
    redis_client = get_redis()
    
    # 计算TTL
    access_ttl = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60  # 转换为秒
    refresh_ttl = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60  # 转换为秒
    
    # Token数据结构
    token_data = {
        "user_id": user_id,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "device_info": device_info or "unknown",
        "created_at": datetime.utcnow().isoformat(),
        "last_accessed": datetime.utcnow().isoformat()
    }
    
    # 存储Access Token -> Token数据映射
    redis_client.setex(
        f"{ACCESS_TOKEN_PREFIX}{access_token}",
        access_ttl,
        json.dumps(token_data)
    )
    
    # 存储Refresh Token -> Token数据映射
    redis_client.setex(
        f"{REFRESH_TOKEN_PREFIX}{refresh_token}",
        refresh_ttl,
        json.dumps(token_data)
    )
    
    # 存储用户的Token集合（用于强制下线等场景）
    user_tokens_key = f"{USER_TOKENS_PREFIX}{user_id}"
    redis_client.sadd(user_tokens_key, access_token)
    redis_client.sadd(user_tokens_key, refresh_token)
    # 用户Token集合的过期时间设置为Refresh Token的过期时间
    redis_client.expire(user_tokens_key, refresh_ttl)


def get_token_from_redis(token: str, token_type: str = "access") -> Optional[Dict[str, Any]]:
    """
    从Redis获取Token信息
    
    Args:
        token: JWT Token字符串
        token_type: 令牌类型，"access"或"refresh"
    
    Returns:
        Token数据字典，如果不存在则返回None
    """
    redis_client = get_redis()
    
    if token_type == "access":
        key = f"{ACCESS_TOKEN_PREFIX}{token}"
    else:
        key = f"{REFRESH_TOKEN_PREFIX}{token}"
    
    token_data = redis_client.get(key)
    if token_data:
        data = json.loads(token_data)
        # 更新最后访问时间
        data["last_accessed"] = datetime.utcnow().isoformat()
        redis_client.setex(key, redis_client.ttl(key), json.dumps(data))
        return data
    return None


def remove_token_from_redis(token: str, token_type: str = "access") -> None:
    """
    从Redis删除指定Token
    
    Args:
        token: JWT Token字符串
        token_type: 令牌类型，"access"或"refresh"
    """
    redis_client = get_redis()
    
    if token_type == "access":
        key = f"{ACCESS_TOKEN_PREFIX}{token}"
    else:
        key = f"{REFRESH_TOKEN_PREFIX}{token}"
    
    # 获取Token数据以清理用户Token集合
    token_data = redis_client.get(key)
    if token_data:
        data = json.loads(token_data)
        user_id = data.get("user_id")
        if user_id:
            user_tokens_key = f"{USER_TOKENS_PREFIX}{user_id}"
            redis_client.srem(user_tokens_key, token)
    
    # 删除Token
    redis_client.delete(key)


def blacklist_token(token: str, token_type: str = "access") -> None:
    """
    将Token加入黑名单
    
    Args:
        token: JWT Token字符串
        token_type: 令牌类型，"access"或"refresh"
    """
    redis_client = get_redis()
    
    # 计算黑名单过期时间（与Token过期时间一致）
    if token_type == "access":
        ttl = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    else:
        ttl = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    
    # 添加到黑名单
    redis_client.setex(
        f"{TOKEN_BLACKLIST_PREFIX}{token}",
        ttl,
        json.dumps({
            "token": token,
            "type": token_type,
            "blacklisted_at": datetime.utcnow().isoformat()
        })
    )
    
    # 同时删除Token
    remove_token_from_redis(token, token_type)


def is_token_blacklisted(token: str) -> bool:
    """
    检查Token是否在黑名单中
    
    Args:
        token: JWT Token字符串
    
    Returns:
        如果Token在黑名单中返回True，否则返回False
    """
    redis_client = get_redis()
    return redis_client.exists(f"{TOKEN_BLACKLIST_PREFIX}{token}") > 0


def revoke_all_user_tokens(user_id: int) -> None:
    """
    撤销用户的所有Token（强制下线）
    
    Args:
        user_id: 用户ID
    """
    redis_client = get_redis()
    user_tokens_key = f"{USER_TOKENS_PREFIX}{user_id}"
    
    # 获取用户的所有Token
    tokens = redis_client.smembers(user_tokens_key)
    
    for token in tokens:
        # 将每个Token加入黑名单
        # 由于无法确定Token类型，尝试作为access和refresh都加入黑名单
        blacklist_token(token, "access")
        blacklist_token(token, "refresh")
    
    # 删除用户的Token集合
    redis_client.delete(user_tokens_key)


def refresh_access_token(refresh_token: str) -> Dict[str, str]:
    """
    使用Refresh Token获取新的Access Token
    
    Args:
        refresh_token: Refresh Token字符串
    
    Returns:
        包含新access_token和refresh_token的字典
    
    Raises:
        HTTPException: Refresh Token无效或过期
    """
    # 验证Refresh Token
    payload = verify_token(refresh_token, "refresh")
    user_id = payload.get("sub")
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )
    
    # 检查Refresh Token是否在Redis中存在
    token_data = get_token_from_redis(refresh_token, "refresh")
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token not found or expired",
        )
    
    # 撤销旧的Token对
    remove_token_from_redis(token_data.get("access_token", ""), "access")
    remove_token_from_redis(refresh_token, "refresh")
    
    # 生成新的Token对
    new_access_token = create_access_token(data={"sub": str(user_id)})
    new_refresh_token = create_refresh_token(data={"sub": str(user_id)})
    
    # 存储新的Token对
    store_tokens_in_redis(
        user_id=user_id,
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        device_info=token_data.get("device_info")
    )
    
    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer"
    }


def get_user_id_from_token(token: str) -> Optional[int]:
    """
    从Token中获取用户ID
    
    Args:
        token: JWT Token字符串
    
    Returns:
        用户ID，如果Token无效则返回None
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        if user_id:
            return int(user_id)
    except JWTError:
        pass
    return None


def hash_password(password: str) -> str:
    """
    对密码进行哈希处理
    
    Args:
        password: 原始密码
    
    Returns:
        哈希后的密码字符串
    """
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证密码是否正确
    
    Args:
        plain_password: 原始密码
        hashed_password: 哈希后的密码
    
    Returns:
        密码是否匹配
    """
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


def generate_password_hash(password: str) -> str:
    """
    生成密码哈希（别名函数）
    
    Args:
        password: 原始密码
    
    Returns:
        哈希后的密码字符串
    """
    return hash_password(password)


def check_password_hash(password: str, password_hash: str) -> bool:
    """
    检查密码哈希是否匹配（别名函数）
    
    Args:
        password: 原始密码
        password_hash: 哈希后的密码
    
    Returns:
        密码是否匹配
    """
    return verify_password(password, password_hash)