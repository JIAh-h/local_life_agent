"""
多级缓存架构

设计原则：
1. L1缓存：内存缓存（LRU），超低延迟
2. L2缓存：Redis缓存，中等延迟，跨进程共享
3. 自动回填：L2 miss时自动从L1回填
4. 缓存预热：支持热点数据预加载
5. 缓存失效：支持主动失效和TTL过期
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Any, Callable, Awaitable
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import wraps

logger = logging.getLogger(__name__)


@dataclass
class CacheConfig:
    """缓存配置"""
    # L1内存缓存配置
    l1_max_size: int = 1000
    l1_ttl: int = 300  # 5分钟
    l1_cleanup_interval: int = 60  # 1分钟清理一次
    
    # L2 Redis缓存配置
    l2_ttl: int = 3600  # 1小时
    l2_prefix: str = "cache:"
    
    # 缓存策略
    enable_write_through: bool = True  # 写穿透：同时写入L1和L2
    enable_read_through: bool = True  # 读穿透：L1 miss时自动从L2加载
    enable_write_back: bool = False  # 写回：只写L1，异步写L2
    
    # 预热配置
    enable_warmup: bool = False
    warmup_keys: List[str] = field(default_factory=list)


@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    value: Any
    created_at: float
    last_accessed: float
    access_count: int = 0
    ttl: int = 300
    
    def is_expired(self) -> bool:
        """检查是否过期"""
        return time.time() - self.created_at > self.ttl
    
    def touch(self):
        """更新访问时间"""
        self.last_accessed = time.time()
        self.access_count += 1


class LRUCache:
    """
    LRU缓存（线程安全版本）
    
    使用OrderedDict实现，支持：
    1. O(1)的get/put操作
    2. 自动淘汰最久未使用的条目
    3. TTL过期支持
    """
    
    def __init__(self, max_size: int = 1000, ttl: int = 300):
        """
        初始化LRU缓存
        
        Args:
            max_size: 最大缓存条目数
            ttl: 默认TTL（秒）
        """
        self.max_size = max_size
        self.default_ttl = ttl
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = asyncio.Lock()
        
        # 统计信息
        self._hits = 0
        self._misses = 0
        self._evictions = 0
    
    async def get(self, key: str) -> Optional[Any]:
        """
        获取缓存值
        
        Args:
            key: 缓存键
            
        Returns:
            缓存值，如果不存在或已过期则返回None
        """
        async with self._lock:
            entry = self._cache.get(key)
            
            if entry is None:
                self._misses += 1
                return None
            
            # 检查是否过期
            if entry.is_expired():
                del self._cache[key]
                self._misses += 1
                return None
            
            # 更新访问信息
            entry.touch()
            self._cache.move_to_end(key)
            self._hits += 1
            
            return entry.value
    
    async def put(self, key: str, value: Any, ttl: int = None) -> bool:
        """
        存储缓存值
        
        Args:
            key: 缓存键
            value: 缓存值
            ttl: TTL（秒），None使用默认值
            
        Returns:
            是否成功
        """
        async with self._lock:
            # 如果key已存在，先删除
            if key in self._cache:
                del self._cache[key]
            
            # 检查是否需要淘汰
            while len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)
                self._evictions += 1
            
            # 创建新条目
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=time.time(),
                last_accessed=time.time(),
                ttl=ttl or self.default_ttl
            )
            
            self._cache[key] = entry
            return True
    
    async def delete(self, key: str) -> bool:
        """
        删除缓存条目
        
        Args:
            key: 缓存键
            
        Returns:
            是否成功删除
        """
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    async def clear(self) -> int:
        """
        清空缓存
        
        Returns:
            清除的条目数
        """
        async with self._lock:
            count = len(self._cache)
            self._cache.clear()
            return count
    
    async def cleanup_expired(self) -> int:
        """
        清理过期条目
        
        Returns:
            清理的条目数
        """
        async with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired()
            ]
            
            for key in expired_keys:
                del self._cache[key]
            
            return len(expired_keys)
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        total_requests = self._hits + self._misses
        hit_rate = self._hits / total_requests if total_requests > 0 else 0.0
        
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(hit_rate, 4),
            "evictions": self._evictions
        }


class MultiLevelCache:
    """
    多级缓存管理器
    
    架构：
    - L1: 内存LRU缓存（超低延迟）
    - L2: Redis缓存（跨进程共享）
    
    支持：
    - 写穿透：同时写入L1和L2
    - 读穿透：L1 miss时自动从L2加载
    - 缓存预热：热点数据预加载
    - 自动清理：定期清理过期数据
    """
    
    def __init__(self, redis_client=None, config: CacheConfig = None):
        """
        初始化多级缓存
        
        Args:
            redis_client: Redis客户端（可选，用于L2缓存）
            config: 缓存配置
        """
        self.redis = redis_client
        self.config = config or CacheConfig()
        
        # L1缓存
        self.l1 = LRUCache(
            max_size=self.config.l1_max_size,
            ttl=self.config.l1_ttl
        )
        
        # 清理任务
        self._cleanup_task: Optional[asyncio.Task] = None
        
        # 统计信息
        self._l2_hits = 0
        self._l2_misses = 0
        self._write_count = 0
        
        logger.info(f"多级缓存初始化完成: L1={self.config.l1_max_size}条, L2={'启用' if redis_client else '禁用'}")
    
    async def start(self):
        """启动缓存服务"""
        # 启动定期清理任务
        if self.config.l1_cleanup_interval > 0:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        # 预热缓存
        if self.config.enable_warmup and self.config.warmup_keys:
            await self._warmup_cache()
    
    async def stop(self):
        """停止缓存服务"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
    
    async def _cleanup_loop(self):
        """定期清理过期缓存"""
        while True:
            try:
                await asyncio.sleep(self.config.l1_cleanup_interval)
                cleaned = await self.l1.cleanup_expired()
                if cleaned > 0:
                    logger.debug(f"L1缓存清理: {cleaned}条过期数据")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"缓存清理异常: {e}")
    
    async def _warmup_cache(self):
        """预热缓存"""
        if not self.redis or not self.config.warmup_keys:
            return
        
        warmed = 0
        for key in self.config.warmup_keys:
            try:
                value = await self._get_from_l2(key)
                if value is not None:
                    await self.l1.put(key, value)
                    warmed += 1
            except Exception as e:
                logger.warning(f"缓存预热失败: {key}, {e}")
        
        logger.info(f"缓存预热完成: {warmed}/{len(self.config.warmup_keys)}条")
    
    async def get(self, key: str, loader: Callable[[], Awaitable[Any]] = None) -> Optional[Any]:
        """
        获取缓存值
        
        读穿透流程：
        1. 先查L1
        2. L1 miss则查L2
        3. L2 miss则调用loader（如果提供）
        4. 将结果回填到L1和L2
        
        Args:
            key: 缓存键
            loader: 数据加载函数（可选）
            
        Returns:
            缓存值
        """
        # 1. 查L1
        value = await self.l1.get(key)
        if value is not None:
            return value
        
        # 2. 查L2
        if self.redis and self.config.enable_read_through:
            value = await self._get_from_l2(key)
            if value is not None:
                self._l2_hits += 1
                # 回填到L1
                await self.l1.put(key, value)
                return value
            else:
                self._l2_misses += 1
        
        # 3. 调用loader
        if loader:
            try:
                value = await loader()
                if value is not None:
                    # 写入L1和L2
                    await self.put(key, value)
                    return value
            except Exception as e:
                logger.error(f"数据加载失败: {key}, {e}")
        
        return None
    
    async def put(self, key: str, value: Any, ttl: int = None) -> bool:
        """
        存储缓存值
        
        写穿透流程：
        1. 写入L1
        2. 如果启用写穿透，同时写入L2
        
        Args:
            key: 缓存键
            value: 缓存值
            ttl: TTL（秒），None使用默认值
            
        Returns:
            是否成功
        """
        self._write_count += 1
        
        # 写入L1
        l1_ttl = ttl or self.config.l1_ttl
        await self.l1.put(key, value, l1_ttl)
        
        # 写入L2
        if self.redis and self.config.enable_write_through:
            l2_ttl = ttl or self.config.l2_ttl
            await self._put_to_l2(key, value, l2_ttl)
        
        return True
    
    async def delete(self, key: str) -> bool:
        """
        删除缓存
        
        Args:
            key: 缓存键
            
        Returns:
            是否成功
        """
        # 从L1删除
        await self.l1.delete(key)
        
        # 从L2删除
        if self.redis:
            await self._delete_from_l2(key)
        
        return True
    
    async def clear(self) -> bool:
        """
        清空所有缓存
        
        Returns:
            是否成功
        """
        await self.l1.clear()
        
        # 注意：不清空L2，因为可能是共享的
        logger.warning("已清空L1缓存，L2缓存未清空（可能是共享的）")
        return True
    
    async def invalidate_pattern(self, pattern: str) -> int:
        """
        按模式失效缓存
        
        Args:
            pattern: 键模式（支持*通配符）
            
        Returns:
            失效的条目数
        """
        # 这里简化处理，只清除L1
        # 实际实现应该同时清除L2
        count = 0
        keys_to_delete = []
        
        for key in self.l1._cache.keys():
            if self._match_pattern(key, pattern):
                keys_to_delete.append(key)
        
        for key in keys_to_delete:
            await self.l1.delete(key)
            count += 1
        
        return count
    
    def _match_pattern(self, key: str, pattern: str) -> bool:
        """简单的模式匹配"""
        if '*' not in pattern:
            return key == pattern
        
        prefix = pattern.split('*')[0]
        return key.startswith(prefix)
    
    # ─── L2缓存操作 ───
    
    async def _get_from_l2(self, key: str) -> Optional[Any]:
        """从L2（Redis）获取"""
        if not self.redis:
            return None
        
        try:
            redis_key = f"{self.config.l2_prefix}{key}"
            data = await self.redis.get(redis_key)
            
            if data:
                import json
                return json.loads(data)
            return None
        except Exception as e:
            logger.warning(f"L2缓存读取失败: {key}, {e}")
            return None
    
    async def _put_to_l2(self, key: str, value: Any, ttl: int) -> bool:
        """写入L2（Redis）"""
        if not self.redis:
            return False
        
        try:
            import json
            redis_key = f"{self.config.l2_prefix}{key}"
            data = json.dumps(value, ensure_ascii=False)
            await self.redis.set(redis_key, data, ex=ttl)
            return True
        except Exception as e:
            logger.warning(f"L2缓存写入失败: {key}, {e}")
            return False
    
    async def _delete_from_l2(self, key: str) -> bool:
        """从L2（Redis）删除"""
        if not self.redis:
            return False
        
        try:
            redis_key = f"{self.config.l2_prefix}{key}"
            await self.redis.delete(redis_key)
            return True
        except Exception as e:
            logger.warning(f"L2缓存删除失败: {key}, {e}")
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        l1_stats = self.l1.get_statistics()
        
        total_l2_requests = self._l2_hits + self._l2_misses
        l2_hit_rate = self._l2_hits / total_l2_requests if total_l2_requests > 0 else 0.0
        
        return {
            "l1": l1_stats,
            "l2": {
                "enabled": self.redis is not None,
                "hits": self._l2_hits,
                "misses": self._l2_misses,
                "hit_rate": round(l2_hit_rate, 4)
            },
            "writes": self._write_count,
            "config": {
                "l1_max_size": self.config.l1_max_size,
                "l1_ttl": self.config.l1_ttl,
                "l2_ttl": self.config.l2_ttl,
                "write_through": self.config.enable_write_through,
                "read_through": self.config.enable_read_through
            }
        }


# 缓存装饰器
def cached(cache: MultiLevelCache, key_prefix: str = "", ttl: int = None):
    """
    缓存装饰器
    
    Args:
        cache: 缓存实例
        key_prefix: 键前缀
        ttl: TTL（秒）
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 生成缓存键
            key = f"{key_prefix}:{func.__name__}:{str(args)}:{str(kwargs)}"
            
            # 尝试从缓存获取
            result = await cache.get(key)
            if result is not None:
                return result
            
            # 执行函数
            result = await func(*args, **kwargs)
            
            # 存入缓存
            if result is not None:
                await cache.put(key, result, ttl)
            
            return result
        return wrapper
    return decorator


# 全局单例
_cache_manager: Optional[MultiLevelCache] = None


def get_cache_manager(redis_client=None, config: CacheConfig = None) -> MultiLevelCache:
    """获取缓存管理器单例"""
    global _cache_manager
    
    if _cache_manager is None:
        _cache_manager = MultiLevelCache(redis_client, config)
    
    return _cache_manager


def reset_cache_manager():
    """重置缓存管理器单例"""
    global _cache_manager
    _cache_manager = None
