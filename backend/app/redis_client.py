import redis
import redis.asyncio as aioredis
from app.config import settings

# 创建同步Redis连接（用于向后兼容）
redis_client = redis.from_url(
    settings.REDIS_URL,
    decode_responses=True
)

# 异步Redis客户端（延迟初始化）
_async_redis_client = None


def get_redis():
    """获取同步Redis客户端"""
    return redis_client


async def get_async_redis():
    """获取异步Redis客户端"""
    global _async_redis_client
    
    if _async_redis_client is None:
        _async_redis_client = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True
        )
    
    return _async_redis_client


async def close_async_redis():
    """关闭异步Redis连接"""
    global _async_redis_client
    
    if _async_redis_client is not None:
        await _async_redis_client.close()
        _async_redis_client = None
