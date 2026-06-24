"""
Agent v2 增强记忆系统
在保持薄Harness架构优势的同时，增强长对话记忆能力

组件：
- EnhancedMemoryManager  : 增强版记忆管理器（滑动窗口+智能压缩）
- ContextAssembler       : 智能上下文组装器（token限制管理）
- VectorStore            : 向量存储管理器（语义检索）
- EntityIndex            : 增量式实体索引（快速实体查询）
- MultiGranularitySummarizer : 多粒度摘要管理器（话题分割+分层摘要）
- InfoWeightSystem       : 关键信息权重系统（多维权重+动态调整）
- ShardedStorage         : 分片存储管理器（一致性哈希+水平扩展）
- MultiLevelCache        : 多级缓存管理器（L1内存+L2 Redis）
"""
from .memory_manager import EnhancedMemoryManager
from .context_assembler import ContextAssembler
from .vector_store import VectorStore, get_vector_store
from .entity_index import EntityIndex, get_entity_index
from .multi_granularity_summary import MultiGranularitySummarizer, get_multi_granularity_summarizer
from .info_weight import InfoWeightSystem, get_info_weight_system
from .sharded_storage import ShardedStorage, ShardConfig, get_sharded_storage, reset_sharded_storage
from .cache import MultiLevelCache, CacheConfig, get_cache_manager, reset_cache_manager, cached
from .qdrant_manager import QdrantManager, get_qdrant_manager, create_qdrant_manager, reset_qdrant_manager

__all__ = [
    "EnhancedMemoryManager",
    "ContextAssembler",
    "VectorStore",
    "get_vector_store",
    "EntityIndex",
    "get_entity_index",
    "MultiGranularitySummarizer",
    "get_multi_granularity_summarizer",
    "InfoWeightSystem",
    "get_info_weight_system",
    "ShardedStorage",
    "ShardConfig",
    "get_sharded_storage",
    "reset_sharded_storage",
    "MultiLevelCache",
    "CacheConfig",
    "get_cache_manager",
    "reset_cache_manager",
    "cached",
    "QdrantManager",
    "get_qdrant_manager",
    "create_qdrant_manager",
    "reset_qdrant_manager",
]
