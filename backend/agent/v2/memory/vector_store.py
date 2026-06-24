"""
向量存储模块 - 集成Qdrant进行语义检索

设计原则：
1. 异步非阻塞：使用aioredis避免阻塞事件循环
2. 降级策略：向量检索失败时降级到关键词检索
3. 缓存优化：缓存常用查询结果
4. 批量操作：支持批量向量化和存储
"""
import logging
import json
import hashlib
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class VectorDocument:
    """向量文档"""
    id: str
    content: str
    vector: List[float]
    metadata: Dict[str, Any]
    session_id: str
    timestamp: datetime


class VectorStore:
    """
    向量存储管理器
    
    职责：
    1. 管理向量文档的存储和检索
    2. 提供语义相似度搜索
    3. 与embedding服务集成
    4. 支持批量操作和缓存
    """
    
    def __init__(
        self,
        qdrant_client=None,
        embedding_service=None,
        redis_client=None,
        collection_name: str = "memory_vectors",
        vector_dimension: int = 1152
    ):
        """
        初始化向量存储
        
        Args:
            qdrant_client: Qdrant客户端实例
            embedding_service: 嵌入服务实例
            redis_client: Redis客户端（用于缓存）
            collection_name: 集合名称
            vector_dimension: 向量维度
        """
        self.qdrant = qdrant_client
        self.embedding = embedding_service
        self.redis = redis_client
        self.collection_name = collection_name
        self.vector_dimension = vector_dimension
        
        # 缓存配置
        self.cache_ttl = 3600  # 1小时
        self.cache_prefix = "vector_cache:"
        
        # 性能统计
        self.stats = {
            "total_queries": 0,
            "cache_hits": 0,
            "embedding_calls": 0,
            "vector_searches": 0
        }
    
    async def initialize(self):
        """初始化向量存储"""
        if not self.qdrant:
            logger.warning("Qdrant客户端未提供，向量存储将降级")
            return False
        
        try:
            # 检查集合是否存在
            collections = await self.qdrant.async_client.get_collections()
            collection_names = [c.name for c in collections.collections]
            
            if self.collection_name not in collection_names:
                # 创建集合
                await self._create_collection()
                logger.info(f"创建向量集合: {self.collection_name}")
            
            logger.info(f"向量存储初始化成功: {self.collection_name}")
            return True
            
        except Exception as e:
            logger.error(f"向量存储初始化失败: {e}")
            return False
    
    async def _create_collection(self):
        """创建向量集合"""
        from qdrant_client.http.models import Distance, VectorParams
        
        await self.qdrant.async_client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(
                size=self.vector_dimension,
                distance=Distance.COSINE
            )
        )
    
    def _generate_id(self, content: str, session_id: str) -> str:
        """生成文档ID"""
        unique_str = f"{session_id}:{content}:{datetime.now().isoformat()}"
        return hashlib.md5(unique_str.encode()).hexdigest()
    
    async def store_message(
        self,
        message: Dict[str, Any],
        session_id: str,
        metadata: Dict[str, Any] = None
    ) -> Optional[str]:
        """
        存储消息到向量库
        
        Args:
            message: 消息内容
            session_id: 会话ID
            metadata: 额外元数据
            
        Returns:
            文档ID或None
        """
        if not self.qdrant or not self.embedding:
            logger.warning("向量存储未初始化")
            return None
        
        try:
            content = message.get("content", "")
            if not content:
                return None
            
            # 生成向量
            vector = await self.embedding.embed(content)
            if not vector or all(v == 0.0 for v in vector):
                logger.warning("向量生成失败")
                return None
            
            # 生成文档ID
            doc_id = self._generate_id(content, session_id)
            
            # 准备元数据
            doc_metadata = {
                "session_id": session_id,
                "role": message.get("role", "unknown"),
                "timestamp": datetime.now().isoformat(),
                "content_length": len(content),
                **(metadata or {})
            }
            
            # 提取实体信息
            entities = message.get("entities", {})
            if entities:
                doc_metadata["entities"] = entities
            
            # 存储到Qdrant
            await self.qdrant.async_client.upsert(
                collection_name=self.collection_name,
                points=[{
                    "id": doc_id,
                    "vector": vector,
                    "payload": {
                        "content": content,
                        "metadata": doc_metadata
                    }
                }]
            )
            
            logger.debug(f"消息向量化存储成功: {doc_id}")
            self.stats["embedding_calls"] += 1
            
            return doc_id
            
        except Exception as e:
            logger.error(f"消息向量化存储失败: {e}")
            return None
    
    async def store_batch(
        self,
        messages: List[Dict[str, Any]],
        session_id: str,
        metadata: Dict[str, Any] = None
    ) -> List[str]:
        """
        批量存储消息
        
        Args:
            messages: 消息列表
            session_id: 会话ID
            metadata: 额外元数据
            
        Returns:
            文档ID列表
        """
        if not self.qdrant or not self.embedding:
            return []
        
        try:
            # 准备内容列表
            contents = [msg.get("content", "") for msg in messages]
            valid_contents = [c for c in contents if c]
            
            if not valid_contents:
                return []
            
            # 批量生成向量
            vectors = await self.embedding.embed_batch(valid_contents)
            
            # 准备数据点
            points = []
            doc_ids = []
            
            for i, (msg, vector) in enumerate(zip(messages, vectors)):
                if not vector or all(v == 0.0 for v in vector):
                    continue
                
                content = msg.get("content", "")
                doc_id = self._generate_id(content, session_id)
                
                doc_metadata = {
                    "session_id": session_id,
                    "role": msg.get("role", "unknown"),
                    "timestamp": datetime.now().isoformat(),
                    "content_length": len(content),
                    **(metadata or {})
                }
                
                entities = msg.get("entities", {})
                if entities:
                    doc_metadata["entities"] = entities
                
                points.append({
                    "id": doc_id,
                    "vector": vector,
                    "payload": {
                        "content": content,
                        "metadata": doc_metadata
                    }
                })
                doc_ids.append(doc_id)
            
            # 批量存储
            if points:
                await self.qdrant.async_client.upsert(
                    collection_name=self.collection_name,
                    points=points
                )
                logger.info(f"批量向量化存储成功: {len(points)}条")
                self.stats["embedding_calls"] += len(points)
            
            return doc_ids
            
        except Exception as e:
            logger.error(f"批量向量化存储失败: {e}")
            return []
    
    async def search_similar(
        self,
        query: str,
        session_id: str = None,
        top_k: int = 5,
        score_threshold: float = 0.7,
        filters: Dict[str, Any] = None
    ) -> List[Tuple[str, float, Dict[str, Any]]]:
        """
        语义相似度搜索
        
        Args:
            query: 查询文本
            session_id: 会话ID（可选过滤）
            top_k: 返回结果数量
            score_threshold: 相似度阈值
            filters: 额外过滤条件
            
        Returns:
            [(文档ID, 相似度分数, 元数据), ...]
        """
        self.stats["total_queries"] += 1
        
        # 检查缓存
        cache_key = self._get_cache_key(query, session_id, top_k)
        cached_result = await self._get_from_cache(cache_key)
        if cached_result:
            self.stats["cache_hits"] += 1
            return cached_result
        
        if not self.qdrant or not self.embedding:
            logger.warning("向量搜索未初始化")
            return []
        
        try:
            # 生成查询向量
            query_vector = await self.embedding.embed(query)
            if not query_vector or all(v == 0.0 for v in query_vector):
                logger.warning("查询向量生成失败")
                return []
            
            # 构建过滤条件
            search_filter = self._build_filter(session_id, filters)
            
            # 执行搜索
            search_result = await self.qdrant.async_client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=top_k,
                score_threshold=score_threshold,
                query_filter=search_filter
            )
            
            # 处理结果
            results = []
            for point in search_result:
                doc_id = point.id
                score = point.score
                payload = point.payload or {}
                metadata = payload.get("metadata", {})
                
                results.append((doc_id, score, metadata))
            
            # 缓存结果
            await self._set_cache(cache_key, results)
            
            self.stats["vector_searches"] += 1
            logger.debug(f"向量搜索完成: {len(results)}条结果")
            
            return results
            
        except Exception as e:
            logger.error(f"向量搜索失败: {e}")
            return []
    
    async def search_by_entities(
        self,
        entities: Dict[str, List[str]],
        session_id: str = None,
        top_k: int = 10
    ) -> List[Tuple[str, float, Dict[str, Any]]]:
        """
        基于实体的语义搜索
        
        Args:
            entities: 实体字典 {"locations": [...], "restaurants": [...], ...}
            session_id: 会话ID
            top_k: 返回数量
            
        Returns:
            搜索结果
        """
        # 构建查询文本
        query_parts = []
        for entity_type, entity_list in entities.items():
            if entity_list:
                query_parts.extend(entity_list[:3])  # 每个类型最多3个实体
        
        if not query_parts:
            return []
        
        query = " ".join(query_parts)
        return await self.search_similar(query, session_id, top_k)
    
    async def get_session_vectors(
        self,
        session_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        获取会话的所有向量
        
        Args:
            session_id: 会话ID
            limit: 返回数量限制
            
        Returns:
            向量文档列表
        """
        if not self.qdrant:
            return []
        
        try:
            # 构建过滤条件
            search_filter = {
                "must": [
                    {
                        "key": "metadata.session_id",
                        "match": {"value": session_id}
                    }
                ]
            }
            
            # 滚动查询
            result = await self.qdrant.async_client.scroll(
                collection_name=self.collection_name,
                scroll_filter=search_filter,
                limit=limit,
                with_payload=True,
                with_vectors=False
            )
            
            documents = []
            for point in result[0]:  # result是(points, next_page_offset)
                payload = point.payload or {}
                documents.append({
                    "id": point.id,
                    "content": payload.get("content", ""),
                    "metadata": payload.get("metadata", {})
                })
            
            return documents
            
        except Exception as e:
            logger.error(f"获取会话向量失败: {e}")
            return []
    
    async def delete_session_vectors(self, session_id: str) -> bool:
        """
        删除会话的所有向量
        
        Args:
            session_id: 会话ID
            
        Returns:
            是否成功
        """
        if not self.qdrant:
            return False
        
        try:
            # 构建过滤条件
            delete_filter = {
                "must": [
                    {
                        "key": "metadata.session_id",
                        "match": {"value": session_id}
                    }
                ]
            }
            
            # 删除
            await self.qdrant.async_client.delete(
                collection_name=self.collection_name,
                points_selector=delete_filter
            )
            
            logger.info(f"删除会话向量: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"删除会话向量失败: {e}")
            return False
    
    def _build_filter(
        self,
        session_id: str = None,
        filters: Dict[str, Any] = None
    ) -> Optional[Dict[str, Any]]:
        """构建Qdrant过滤条件"""
        conditions = []
        
        if session_id:
            conditions.append({
                "key": "metadata.session_id",
                "match": {"value": session_id}
            })
        
        if filters:
            for key, value in filters.items():
                if isinstance(value, str):
                    conditions.append({
                        "key": f"metadata.{key}",
                        "match": {"value": value}
                    })
                elif isinstance(value, list):
                    conditions.append({
                        "key": f"metadata.{key}",
                        "match": {"any": value}
                    })
        
        if not conditions:
            return None
        
        return {"must": conditions}
    
    def _get_cache_key(
        self,
        query: str,
        session_id: str = None,
        top_k: int = 5
    ) -> str:
        """生成缓存键"""
        key_parts = [query, str(top_k)]
        if session_id:
            key_parts.append(session_id)
        key_str = ":".join(key_parts)
        return f"{self.cache_prefix}{hashlib.md5(key_str.encode()).hexdigest()}"
    
    async def _get_from_cache(self, key: str) -> Optional[List[Tuple[str, float, Dict[str, Any]]]]:
        """从缓存获取结果"""
        if not self.redis:
            return None
        
        try:
            data = await self.redis.get(key)
            if data:
                return json.loads(data)
        except Exception:
            pass
        return None
    
    async def _set_cache(
        self,
        key: str,
        value: List[Tuple[str, float, Dict[str, Any]]]
    ):
        """设置缓存"""
        if not self.redis:
            return
        
        try:
            await self.redis.set(
                key,
                json.dumps(value, ensure_ascii=False),
                ex=self.cache_ttl
            )
        except Exception:
            pass
    
    def get_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        total_queries = self.stats["total_queries"]
        cache_hit_rate = (
            self.stats["cache_hits"] / total_queries 
            if total_queries > 0 else 0.0
        )
        
        return {
            "total_queries": total_queries,
            "cache_hits": self.stats["cache_hits"],
            "cache_hit_rate": f"{cache_hit_rate:.2%}",
            "embedding_calls": self.stats["embedding_calls"],
            "vector_searches": self.stats["vector_searches"]
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        result = {
            "healthy": False,
            "qdrant_connected": False,
            "embedding_ready": False,
            "stats": self.get_stats()
        }
        
        if self.qdrant:
            try:
                health = await self.qdrant.health_check()
                result["qdrant_connected"] = health.get("healthy", False)
            except Exception:
                pass
        
        if self.embedding:
            result["embedding_ready"] = self.embedding.is_ready
        
        result["healthy"] = result["qdrant_connected"] and result["embedding_ready"]
        return result


# 全局单例
_vector_store: Optional[VectorStore] = None


def get_vector_store(
    qdrant_client=None,
    embedding_service=None,
    redis_client=None
) -> VectorStore:
    """获取向量存储单例"""
    global _vector_store
    
    if _vector_store is None:
        _vector_store = VectorStore(
            qdrant_client=qdrant_client,
            embedding_service=embedding_service,
            redis_client=redis_client
        )
    
    return _vector_store


def reset_vector_store():
    """重置向量存储单例"""
    global _vector_store
    _vector_store = None