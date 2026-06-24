"""
分片存储架构

设计原则：
1. 一致性哈希：使用一致性哈希算法分配会话到分片
2. 故障转移：支持分片故障时的自动切换
3. 水平扩展：支持动态添加/移除分片
4. 透明访问：对上层提供统一的访问接口
"""
import logging
import hashlib
import bisect
from typing import Dict, List, Optional, Any, Set
from datetime import datetime
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ShardConfig:
    """分片配置"""
    shard_id: str
    host: str
    port: int
    db: int = 0
    password: Optional[str] = None
    weight: int = 1  # 权重，用于虚拟节点
    is_active: bool = True
    last_heartbeat: Optional[datetime] = None


@dataclass(order=True)
class VirtualNode:
    """虚拟节点"""
    hash_value: int
    shard_id: str


class ConsistentHash:
    """
    一致性哈希算法
    
    实现：
    1. 使用虚拟节点保证数据分布均匀
    2. 支持动态添加/移除节点
    3. 最小化数据迁移
    """
    
    def __init__(self, virtual_nodes: int = 150):
        """
        初始化一致性哈希
        
        Args:
            virtual_nodes: 每个物理节点的虚拟节点数
        """
        self.virtual_nodes = virtual_nodes
        self.ring: List[VirtualNode] = []
        self.shards: Dict[str, ShardConfig] = {}
        self.sorted_hashes: List[int] = []
    
    def add_shard(self, shard_config: ShardConfig) -> None:
        """添加分片"""
        self.shards[shard_config.shard_id] = shard_config
        
        # 添加虚拟节点
        for i in range(self.virtual_nodes * shard_config.weight):
            hash_value = self._hash(f"{shard_config.shard_id}:{i}")
            node = VirtualNode(hash_value, shard_config.shard_id)
            bisect.insort(self.ring, node)
            self.sorted_hashes.append(hash_value)
        
        self.sorted_hashes.sort()
        logger.info(f"添加分片: {shard_config.shard_id}, 虚拟节点数: {self.virtual_nodes * shard_config.weight}")
    
    def remove_shard(self, shard_id: str) -> None:
        """移除分片"""
        if shard_id not in self.shards:
            return
        
        # 移除虚拟节点
        self.ring = [node for node in self.ring if node.shard_id != shard_id]
        self.sorted_hashes = [node.hash_value for node in self.ring]
        
        del self.shards[shard_id]
        logger.info(f"移除分片: {shard_id}")
    
    def get_shard(self, key: str) -> Optional[ShardConfig]:
        """获取key对应的分片"""
        if not self.ring:
            return None
        
        hash_value = self._hash(key)
        
        # 二分查找
        index = bisect.bisect_right(self.sorted_hashes, hash_value)
        if index >= len(self.sorted_hashes):
            index = 0
        
        shard_id = self.ring[index].shard_id
        return self.shards.get(shard_id)
    
    def get_shard_for_session(self, session_id: str) -> Optional[ShardConfig]:
        """获取会话对应的分片"""
        return self.get_shard(session_id)
    
    def _hash(self, key: str) -> int:
        """计算哈希值"""
        return int(hashlib.md5(key.encode()).hexdigest(), 16)
    
    def get_distribution(self) -> Dict[str, int]:
        """获取分片分布统计"""
        distribution = {}
        for node in self.ring:
            distribution[node.shard_id] = distribution.get(node.shard_id, 0) + 1
        return distribution


class ShardedStorage:
    """
    分片存储管理器
    
    职责：
    1. 管理多个Redis分片
    2. 提供透明的分片访问
    3. 支持故障转移
    4. 提供分片统计信息
    """
    
    def __init__(self, shards: List[ShardConfig] = None, virtual_nodes: int = 150):
        """
        初始化分片存储
        
        Args:
            shards: 分片配置列表
            virtual_nodes: 每个物理节点的虚拟节点数
        """
        self.hash_ring = ConsistentHash(virtual_nodes)
        self.clients: Dict[str, Any] = {}  # shard_id -> Redis client
        self.health_status: Dict[str, bool] = {}  # shard_id -> is_healthy
        
        # 初始化分片
        if shards:
            for shard in shards:
                self.add_shard(shard)
    
    def add_shard(self, shard_config: ShardConfig) -> None:
        """添加分片"""
        self.hash_ring.add_shard(shard_config)
        self.health_status[shard_config.shard_id] = shard_config.is_active
        
        # 创建Redis客户端（延迟初始化）
        self.clients[shard_config.shard_id] = None
    
    def remove_shard(self, shard_id: str) -> None:
        """移除分片"""
        self.hash_ring.remove_shard(shard_id)
        
        if shard_id in self.clients:
            del self.clients[shard_id]
        if shard_id in self.health_status:
            del self.health_status[shard_id]
    
    async def get_client(self, session_id: str) -> Optional[Any]:
        """获取会话对应的Redis客户端"""
        shard = self.hash_ring.get_shard_for_session(session_id)
        if not shard:
            logger.warning(f"未找到分片: {session_id}")
            return None
        
        # 检查分片健康状态
        if not self.health_status.get(shard.shard_id, False):
            logger.warning(f"分片不健康: {shard.shard_id}")
            # 尝试故障转移到下一个分片
            shard = self._failover(session_id, shard.shard_id)
            if not shard:
                return None
        
        # 获取或创建客户端
        client = self.clients.get(shard.shard_id)
        if client is None:
            client = await self._create_client(shard)
            self.clients[shard.shard_id] = client
        
        return client
    
    async def _create_client(self, shard: ShardConfig) -> Any:
        """创建Redis客户端"""
        try:
            import redis.asyncio as aioredis
            url = f'redis://{shard.host}:{shard.port}/{shard.db}'
            client = aioredis.from_url(
                url,
                password=shard.password,
                decode_responses=True
            )
            logger.info(f"创建Redis客户端: {shard.shard_id}")
            return client
        except Exception as e:
            logger.error(f"创建Redis客户端失败: {shard.shard_id}, {e}")
            return None
    
    def _failover(self, session_id: str, failed_shard_id: str) -> Optional[ShardConfig]:
        """故障转移"""
        # 获取所有健康的分片
        healthy_shards = [
            shard_id for shard_id, is_healthy in self.health_status.items()
            if is_healthy and shard_id != failed_shard_id
        ]
        
        if not healthy_shards:
            logger.error("没有可用的健康分片")
            return None
        
        # 简单的轮询故障转移
        # 实际实现可以使用更复杂的策略
        fallback_shard_id = healthy_shards[0]
        logger.info(f"故障转移: {failed_shard_id} -> {fallback_shard_id}")
        
        return self.hash_ring.shards.get(fallback_shard_id)
    
    async def health_check(self) -> Dict[str, bool]:
        """健康检查"""
        results = {}
        
        for shard_id, client in self.clients.items():
            if client is None:
                results[shard_id] = False
                continue
            
            try:
                await client.ping()
                results[shard_id] = True
                self.health_status[shard_id] = True
            except Exception as e:
                logger.warning(f"分片健康检查失败: {shard_id}, {e}")
                results[shard_id] = False
                self.health_status[shard_id] = False
        
        return results
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        distribution = self.hash_ring.get_distribution()
        
        return {
            "total_shards": len(self.hash_ring.shards),
            "healthy_shards": sum(1 for is_healthy in self.health_status.values() if is_healthy),
            "distribution": distribution,
            "shards": [
                {
                    "id": shard.shard_id,
                    "host": shard.host,
                    "port": shard.port,
                    "is_active": self.health_status.get(shard.shard_id, False)
                }
                for shard in self.hash_ring.shards.values()
            ]
        }


# 全局单例
_sharded_storage: Optional[ShardedStorage] = None


def get_sharded_storage(shards: List[ShardConfig] = None) -> ShardedStorage:
    """获取分片存储单例"""
    global _sharded_storage
    
    if _sharded_storage is None:
        _sharded_storage = ShardedStorage(shards)
    
    return _sharded_storage


def reset_sharded_storage():
    """重置分片存储单例"""
    global _sharded_storage
    _sharded_storage = None
