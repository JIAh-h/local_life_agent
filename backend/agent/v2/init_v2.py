"""
Agent v2 初始化脚本 - Fat Skills 架构

配置和初始化：
- SkillLoader: 从Markdown加载技能
- Resolver: 技能路由器
- ToolRegistry: 确定性工具层
- Reactor: Thin Harness核心
- MemoryManager: 增强记忆系统（异步版本+向量检索）
"""
import logging
from typing import Optional

from .reactor import Reactor, ReactorConfig, get_reactor
from .resolver import Resolver, get_resolver
from .skills_loader import SkillLoader, get_skill_loader
from .deterministic import ToolRegistry, get_tool_registry
from .memory import EnhancedMemoryManager, ContextAssembler, get_vector_store, get_entity_index, get_multi_granularity_summarizer, get_info_weight_system, get_sharded_storage, get_cache_manager, CacheConfig, QdrantManager, get_qdrant_manager
from .mcp_tools import get_mcp_tool_registry, MCPToolRegistry
from .mcp_log import setup_mcp_logging

logger = logging.getLogger(__name__)


class AgentSystemV2:
    """
    Agent系统 v2 - Fat Skills 架构
    
    组件：
    1. SkillLoader: 从Markdown加载技能定义
    2. Resolver: 技能路由器（触发词/语义/LLM）
    3. ToolRegistry: 确定性工具层
    4. Reactor: Thin Harness核心
    5. MemoryManager: 增强记忆系统（异步版本）
    """
    
    def __init__(
        self,
        redis_client=None,
        async_redis_client=None,
        llm_client=None,
        embedding_client=None,
        qdrant_client=None,
        sharded_storage=None,
        config: ReactorConfig = None,
        skills_dir: str = None
    ):
        """
        初始化Agent系统
        
        Args:
            redis_client: 同步Redis客户端（用于向后兼容）
            async_redis_client: 异步Redis客户端（用于记忆系统）
            llm_client: LLM客户端
            embedding_client: 向量化客户端（用于语义路由）
            qdrant_client: Qdrant客户端（用于向量检索）。若不提供，v2 将自动创建独立实例。
            sharded_storage: 分片存储管理器（用于水平扩展）
            config: Reactor配置
            skills_dir: 技能目录路径
        """
        self.redis_client = redis_client
        self.async_redis_client = async_redis_client
        self.llm_client = llm_client
        self.embedding_client = embedding_client
        self.qdrant_client = qdrant_client  # 可能为 None，后续自动创建
        self.sharded_storage = sharded_storage
        self.config = config or ReactorConfig()
        
        # v2 独立的 Qdrant 管理器（当外部未提供时自动创建）
        self._qdrant_manager: Optional[QdrantManager] = None
        
        # 组件
        self._skill_loader: Optional[SkillLoader] = None
        self._resolver: Optional[Resolver] = None
        self._tool_registry: Optional[ToolRegistry] = None
        self._memory: Optional[EnhancedMemoryManager] = None
        self._context_assembler: Optional[ContextAssembler] = None
        self._vector_store = None
        self._entity_index = None
        self._summarizer = None
        self._weight_system = None
        self._sharded_storage = None
        self._reactor: Optional[Reactor] = None
        
        # 初始化
        self._initialize(skills_dir)
    
    def _initialize(self, skills_dir: str = None):
        """初始化所有组件"""
        logger.info("初始化 Agent System v2 (Fat Skills架构)...")
        
        # 1. 创建技能加载器
        self._skill_loader = get_skill_loader(skills_dir)
        skills_count = len(self._skill_loader.list_skills())
        logger.info(f"技能加载器初始化完成: {skills_count} 个技能")
        
        # 2. 创建确定性工具层
        self._tool_registry = get_tool_registry()
        
        # 初始化 MCP 结构化日志
        setup_mcp_logging()
        
        # 注册 MCP 工具（高德地图等）
        self._mcp_tool_registry = get_mcp_tool_registry()
        mcp_tools_count = self._mcp_tool_registry.register_to(self._tool_registry)
        
        total_tools = len(self._tool_registry.list_tools())
        logger.info(f"确定性工具层初始化完成: {total_tools} 个工具 (其中 MCP 工具: {mcp_tools_count} 个)")
        
        # 3. 创建路由器
        self._resolver = get_resolver(
            skill_loader=self._skill_loader,
            llm_client=self.llm_client,
            embedding_client=self.embedding_client
        )
        logger.info("技能路由器初始化完成")
        
        # 4. 创建向量存储（如果Qdrant客户端可用）
        # 优先使用外部传入的 qdrant_client，否则创建 v2 独立实例
        if not self.qdrant_client:
            try:
                self._qdrant_manager = get_qdrant_manager()
                self.qdrant_client = self._qdrant_manager
                logger.info("[V2 Qdrant] 使用 v2 独立 Qdrant 管理器")
            except Exception as e:
                logger.warning(f"[V2 Qdrant] 创建独立 Qdrant 管理器失败: {e}")
        
        if self.qdrant_client and self.embedding_client:
            self._vector_store = get_vector_store(
                qdrant_client=self.qdrant_client,
                embedding_service=self.embedding_client,
                redis_client=self.async_redis_client or self.redis_client
            )
            logger.info("向量存储初始化完成")
        else:
            logger.info("向量存储未启用（缺少Qdrant客户端或embedding服务）")
        
        # 5. 创建增量实体索引
        self._entity_index = get_entity_index()
        logger.info("增量实体索引初始化完成")
        
        # 6. 创建多粒度摘要管理器
        self._summarizer = get_multi_granularity_summarizer(
            llm_client=self.llm_client,
            embedding_client=self.embedding_client,
            entity_index=self._entity_index
        )
        logger.info("多粒度摘要管理器初始化完成")
        
        # 7. 创建关键信息权重系统
        self._weight_system = get_info_weight_system(
            entity_index=self._entity_index
        )
        logger.info("关键信息权重系统初始化完成")
        
        # 8. 创建分片存储管理器（如果提供了分片配置）
        if self.sharded_storage:
            self._sharded_storage = self.sharded_storage
            logger.info("分片存储管理器初始化完成")
        else:
            # 尝试创建默认分片存储（使用当前Redis作为单分片）
            if self.redis_client or self.async_redis_client:
                try:
                    from .memory import ShardConfig
                    default_shard = ShardConfig(
                        shard_id="default",
                        host="localhost",
                        port=6379,
                        db=0
                    )
                    self._sharded_storage = get_sharded_storage(shards=[default_shard])
                    logger.info("默认分片存储管理器初始化完成")
                except Exception as e:
                    logger.warning(f"默认分片存储初始化失败: {e}")
        
        # 9. 创建多级缓存管理器
        cache_config = CacheConfig(
            l1_max_size=1000,
            l1_ttl=300,  # 5分钟
            l2_ttl=3600,  # 1小时
            enable_write_through=True,
            enable_read_through=True
        )
        self._cache_manager = get_cache_manager(
            redis_client=self.async_redis_client or self.redis_client,
            config=cache_config
        )
        logger.info("多级缓存管理器初始化完成")
        
        # 10. 创建增强记忆管理器（异步版本+向量检索+实体索引+多粒度摘要+权重系统+分片存储+多级缓存）
        # 优先使用异步Redis客户端，降级到同步客户端
        redis_for_memory = self.async_redis_client or self.redis_client
        self._memory = EnhancedMemoryManager(
            redis_client=redis_for_memory,
            llm_client=self.llm_client,
            vector_store=self._vector_store,
            entity_index=self._entity_index,
            summarizer=self._summarizer,
            weight_system=self._weight_system,
            sharded_storage=self._sharded_storage,
            cache_manager=self._cache_manager,
            config={
                "max_messages": 50,
                "ttl": 86400 * 7,  # 7天
                "enable_vector_store": self._vector_store is not None,
                "enable_entity_index": True,
                "enable_summarizer": True,
                "enable_weight_system": True,
                "enable_sharded_storage": self._sharded_storage is not None,
                "enable_cache": True
            }
        )
        logger.info("增强记忆管理器初始化完成（异步版本+向量检索+实体索引+多粒度摘要+权重系统+分片存储+多级缓存）")
        
        # 9. 创建上下文组装器
        self._context_assembler = ContextAssembler()
        logger.info("上下文组装器初始化完成")
        
        # 10. 创建Reactor (Thin Harness)
        self._reactor = Reactor(
            resolver=self._resolver,
            memory_manager=self._memory,
            tool_registry=self._tool_registry,
            context_assembler=self._context_assembler,
            config=self.config
        )
        logger.info("Reactor (Thin Harness) 初始化完成")
        
        logger.info("Agent System v2 初始化完成")
    
    @property
    def skill_loader(self) -> SkillLoader:
        """获取技能加载器"""
        return self._skill_loader
    
    @property
    def resolver(self) -> Resolver:
        """获取技能路由器"""
        return self._resolver
    
    @property
    def tool_registry(self) -> ToolRegistry:
        """获取确定性工具层"""
        return self._tool_registry
    
    @property
    def mcp_tool_registry(self) -> MCPToolRegistry:
        """获取 MCP 工具注册器"""
        return self._mcp_tool_registry
    
    @property
    def memory(self) -> EnhancedMemoryManager:
        """获取增强记忆管理器"""
        return self._memory
    
    @property
    def context_assembler(self) -> ContextAssembler:
        """获取上下文组装器"""
        return self._context_assembler
    
    @property
    def reactor(self) -> Reactor:
        """获取Reactor"""
        return self._reactor
    
    async def process_message(
        self,
        user_message: str,
        session_id: str = None,
        user_id: str = None,
        location: dict = None,
        stream: bool = False,
        **kwargs
    ):
        """
        处理用户消息（代理方法）
        
        Args:
            user_message: 用户消息
            session_id: 会话ID
            user_id: 用户ID
            location: 用户位置
            stream: 是否流式
            **kwargs: 其他参数
            
        Returns:
            响应结果
        """
        return await self._reactor.process_message(
            user_message=user_message,
            session_id=session_id,
            user_id=user_id,
            location=location,
            stream=stream,
            **kwargs
        )
    
    def get_system_info(self) -> dict:
        """
        获取系统信息
        
        Returns:
            系统信息字典
        """
        return {
            "version": "2.8.0",
            "architecture": "Thin Harness, Fat Skills",
            "components": {
                "skills": {
                    "count": len(self._skill_loader.list_skills()) if self._skill_loader else 0,
                    "categories": list(self._skill_loader._categories.keys()) if self._skill_loader else []
                },
                "tools": {
                    "deterministic": len(self._tool_registry.list_tools()) if self._tool_registry else 0,
                    "mcp": {
                        "enabled": self._mcp_tool_registry.is_registered() if self._mcp_tool_registry else False,
                        "count": len(self._mcp_tool_registry.get_tools()) if self._mcp_tool_registry else 0,
                        "tools": self._mcp_tool_registry.get_tool_names() if self._mcp_tool_registry else []
                    }
                },
                "memory": {
                    "type": "EnhancedMemoryManager",
                    "storage": "Redis",
                    "connected": self.redis_client is not None,
                    "max_messages": self._memory.max_messages if self._memory else 0,
                    "ttl_days": self._memory.ttl // 86400 if self._memory else 0,
                    "vector_store_enabled": self._vector_store is not None,
                    "entity_index_enabled": self._entity_index is not None,
                    "summarizer_enabled": self._summarizer is not None,
                    "weight_system_enabled": self._weight_system is not None,
                    "sharded_storage_enabled": self._sharded_storage is not None,
                    "cache_enabled": self._cache_manager is not None
                },
                "vector_store": {
                    "enabled": self._vector_store is not None,
                    "type": "Qdrant" if self._vector_store else None,
                    "embedding_service": self.embedding_client is not None
                },
                "entity_index": {
                    "enabled": self._entity_index is not None,
                    "stats": self._entity_index.get_statistics() if self._entity_index else {}
                },
                "summarizer": {
                    "enabled": self._summarizer is not None,
                    "type": "MultiGranularitySummarizer" if self._summarizer else None,
                    "stats": self._summarizer.get_statistics() if self._summarizer else {}
                },
                "weight_system": {
                    "enabled": self._weight_system is not None,
                    "type": "InfoWeightSystem" if self._weight_system else None,
                    "stats": self._weight_system.get_statistics() if self._weight_system else {}
                },
                "sharded_storage": {
                    "enabled": self._sharded_storage is not None,
                    "type": "ShardedStorage" if self._sharded_storage else None,
                    "stats": self._sharded_storage.get_statistics() if self._sharded_storage else {}
                },
                "cache": {
                    "enabled": self._cache_manager is not None,
                    "type": "MultiLevelCache" if self._cache_manager else None,
                    "stats": self._cache_manager.get_statistics() if self._cache_manager else {}
                },
                "resolver": {
                    "confidence_threshold": self._resolver.confidence_threshold if self._resolver else 0
                }
            },
            "config": {
                "max_turns": self.config.max_turns,
                "max_tokens": self.config.max_tokens,
                "temperature": self.config.temperature,
                "enable_streaming": self.config.enable_streaming,
                "enable_memory": self.config.enable_memory,
                "enable_skills": getattr(self.config, 'enable_skills', True)
            }
        }
    
    def list_skills(self) -> list:
        """列出所有技能"""
        return self._skill_loader.list_skills() if self._skill_loader else []
    
    def reload_skills(self):
        """重新加载技能（热更新）"""
        if self._skill_loader:
            self._skill_loader.load_all_skills()
            logger.info("技能重新加载完成")


# 全局单例
_agent_system: Optional[AgentSystemV2] = None


def init_agent_system(
    redis_client=None,
    async_redis_client=None,
    llm_client=None,
    embedding_client=None,
    qdrant_client=None,
    sharded_storage=None,
    config: ReactorConfig = None,
    skills_dir: str = None
) -> AgentSystemV2:
    """
    初始化Agent系统（全局单例）
    
    Args:
        redis_client: 同步Redis客户端（用于向后兼容）
        async_redis_client: 异步Redis客户端（用于记忆系统）
        llm_client: LLM客户端
        embedding_client: 向量化客户端
        qdrant_client: Qdrant客户端（用于向量检索）
        sharded_storage: 分片存储管理器（用于水平扩展）
        config: Reactor配置
        skills_dir: 技能目录路径
        
    Returns:
        AgentSystemV2实例
    """
    global _agent_system
    
    if _agent_system is None:
        _agent_system = AgentSystemV2(
            redis_client=redis_client,
            async_redis_client=async_redis_client,
            llm_client=llm_client,
            embedding_client=embedding_client,
            qdrant_client=qdrant_client,
            sharded_storage=sharded_storage,
            config=config,
            skills_dir=skills_dir
        )
    
    return _agent_system


def get_agent_system() -> Optional[AgentSystemV2]:
    """获取Agent系统单例"""
    return _agent_system


def reset_agent_system():
    """重置Agent系统单例（用于测试）"""
    global _agent_system
    _agent_system = None
