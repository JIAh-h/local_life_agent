"""
增强版记忆管理器 - 异步版本

设计原则：
1. 保持v2简洁性：单一职责，无状态设计
2. 添加滑动窗口：防止消息无限增长
3. 智能压缩：保留关键实体和意图信息
4. 渐进式增强：可选功能，不影响核心流程
5. 全异步：使用aioredis避免阻塞事件循环
"""
import json
import re
import logging
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def _async_retry_on_redis_error(func):
    """Redis操作异步重试装饰器"""
    import functools
    import asyncio
    
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        max_attempts = 3
        last_error = None
        
        for attempt in range(max_attempts):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_error = e
                if attempt < max_attempts - 1:
                    logger.warning(f"{func.__name__} 第{attempt + 1}次失败: {e}, 重试...")
                    await asyncio.sleep(0.5 * (attempt + 1))
                else:
                    logger.error(f"{func.__name__} 在{max_attempts}次尝试后失败: {e}")
        
        raise last_error
    
    return wrapper


class EnhancedMemoryManager:
    """
    增强版记忆管理器（异步版本）
    
    在v2简化MemoryManager基础上增强：
    1. 滑动窗口管理：MAX_MESSAGES=50，防止内存溢出
    2. 智能对话压缩：超过阈值时自动压缩，保留关键实体
    3. 首条消息保留：确保对话起始上下文不丢失
    4. 可选LLM压缩：支持LLM生成高质量摘要
    5. 全异步：使用aioredis避免阻塞
    
    职责：
    1. 管理会话上下文（已推荐POI、对话历史）
    2. 提供上下文组装接口
    3. 支持记忆过期和清理
    4. 智能压缩长对话
    """
    
    # 配置常量
    DEFAULT_MAX_RECOMMENDED = 50      # 最大已推荐数量
    DEFAULT_MAX_MESSAGES = 50         # 最大消息数
    DEFAULT_MESSAGE_WINDOW = 10       # 最近消息窗口（原v2是6，增加到10）
    DEFAULT_TTL = 86400 * 7           # 默认过期时间（7天，原v2是24h）
    COMPRESS_THRESHOLD = 30           # 压缩阈值
    KEEP_RECENT = 10                  # 保留最近完整轮次
    
    def __init__(self, redis_client=None, llm_client=None, vector_store=None, 
                 entity_index=None, summarizer=None, weight_system=None, 
                 sharded_storage=None, cache_manager=None, config: dict = None):
        """
        初始化增强版记忆管理器
        
        Args:
            redis_client: Redis客户端实例（aioredis异步客户端）
            llm_client: LLM客户端（可选，用于智能压缩）
            vector_store: 向量存储实例（可选，用于语义检索）
            entity_index: 实体索引实例（可选，用于增量实体索引）
            summarizer: 多粒度摘要管理器（可选，用于话题分割和分层摘要）
            weight_system: 关键信息权重系统（可选，用于信息优先级排序）
            sharded_storage: 分片存储管理器（可选，用于水平扩展）
            cache_manager: 多级缓存管理器（可选，用于查询优化）
            config: 配置字典，可覆盖默认配置
        """
        self.redis = redis_client
        self.llm = llm_client
        self.vector_store = vector_store
        self.entity_index = entity_index
        self.summarizer = summarizer
        self.weight_system = weight_system
        self.sharded_storage = sharded_storage
        self.cache_manager = cache_manager
        
        # 加载配置
        config = config or {}
        self.max_recommended = config.get("max_recommended", self.DEFAULT_MAX_RECOMMENDED)
        self.max_messages = config.get("max_messages", self.DEFAULT_MAX_MESSAGES)
        self.message_window = config.get("message_window", self.DEFAULT_MESSAGE_WINDOW)
        self.ttl = config.get("ttl", self.DEFAULT_TTL)
        self.compress_threshold = config.get("compress_threshold", self.COMPRESS_THRESHOLD)
        self.keep_recent = config.get("keep_recent", self.KEEP_RECENT)
        self.enable_vector_store = config.get("enable_vector_store", True)
        self.enable_entity_index = config.get("enable_entity_index", True)
        self.enable_summarizer = config.get("enable_summarizer", True)
        self.enable_weight_system = config.get("enable_weight_system", True)
        
        # jieba分词器（延迟加载）
        self._jieba = None
    
    @property
    def jieba(self):
        """延迟加载jieba分词器"""
        if self._jieba is None:
            try:
                import jieba
                self._jieba = jieba
            except ImportError:
                logger.warning("jieba未安装，将使用正则表达式进行实体提取")
                self._jieba = False
        return self._jieba
    
    async def _get_redis_client(self, session_id: str = None):
        """
        获取Redis客户端（支持分片存储）
        
        Args:
            session_id: 会话ID（用于分片路由）
            
        Returns:
            Redis客户端实例
        """
        # 如果有分片存储，根据session_id路由到对应分片
        if self.sharded_storage and session_id:
            try:
                client = await self.sharded_storage.get_client(session_id)
                if client:
                    return client
                logger.warning(f"分片存储获取客户端失败，降级到默认Redis")
            except Exception as e:
                logger.warning(f"分片存储访问失败，降级到默认Redis: {e}")
        
        # 降级到默认Redis客户端
        return self.redis
    
    # ─── 上下文组装 ───
    
    async def get_context(self, session_id: str, include_messages: bool = True) -> dict:
        """
        获取会话上下文
        
        Args:
            session_id: 会话ID
            include_messages: 是否包含对话历史
            
        Returns:
            上下文字典，包含：
            - already_recommended: 已推荐的POI列表
            - recent_messages: 最近对话历史
            - session_id: 会话ID
            - message_count: 总消息数
        """
        # 尝试从缓存获取
        cache_key = f"context:{session_id}:{include_messages}"
        if self.cache_manager:
            cached_context = await self.cache_manager.get(cache_key)
            if cached_context is not None:
                return cached_context
        
        context = {
            "session_id": session_id,
            "already_recommended": await self.get_already_recommended(session_id),
        }
        
        if include_messages:
            messages = await self.get_recent_messages(session_id)
            context["recent_messages"] = messages
            context["message_count"] = await self._get_message_count(session_id)
        
        # 存入缓存（短TTL，因为上下文会频繁变化）
        if self.cache_manager:
            await self.cache_manager.put(cache_key, context, ttl=30)  # 30秒
        
        return context
    
    # ─── 已推荐POI管理 ───
    
    async def get_already_recommended(self, session_id: str) -> List[str]:
        """获取已推荐的POI名称列表"""
        redis = await self._get_redis_client(session_id)
        if not redis:
            return []
        
        try:
            key = f"session:{session_id}:recommended"
            data = await redis.get(key)
            return json.loads(data) if data else []
        except Exception as e:
            logger.warning(f"获取已推荐列表失败: {e}")
            return []
    
    async def update_recommended(self, session_id: str, new_pois: List[dict]) -> int:
        """更新已推荐的POI列表"""
        redis = await self._get_redis_client(session_id)
        if not redis:
            return 0
        
        try:
            current = await self.get_already_recommended(session_id)
            
            # 提取新推荐的POI名称
            for poi in new_pois:
                name = poi.get("name", "")
                if name and name not in current:
                    current.append(name)
            
            # 限制数量
            if len(current) > self.max_recommended:
                current = current[-self.max_recommended:]
            
            # 保存到Redis
            key = f"session:{session_id}:recommended"
            await redis.set(key, json.dumps(current, ensure_ascii=False), ex=self.ttl)
            
            logger.debug(f"更新已推荐列表: {len(current)} 个POI")
            return len(current)
            
        except Exception as e:
            logger.warning(f"更新已推荐列表失败: {e}")
            return 0
    
    async def clear_recommended(self, session_id: str) -> bool:
        """清空已推荐列表"""
        redis = await self._get_redis_client(session_id)
        if not redis:
            return False
        
        try:
            key = f"session:{session_id}:recommended"
            await redis.delete(key)
            return True
        except Exception as e:
            logger.warning(f"清空已推荐列表失败: {e}")
            return False
    
    # ─── 对话历史管理（增强版） ───
    
    @_async_retry_on_redis_error
    async def get_recent_messages(self, session_id: str, n: int = None) -> List[dict]:
        """
        获取最近n条对话
        
        增强点：
        1. 支持压缩消息的解析
        2. 自动跳过系统摘要消息的截断
        """
        redis = await self._get_redis_client(session_id)
        if not redis:
            return []
        
        n = n or self.message_window
        
        key = f"session:{session_id}:messages"
        messages = await redis.lrange(key, -n, -1)
        parsed = [json.loads(m) for m in messages if m]
        return parsed
    
    async def get_all_messages(self, session_id: str) -> List[dict]:
        """获取所有消息（用于压缩判断）"""
        redis = await self._get_redis_client(session_id)
        if not redis:
            return []
        
        try:
            key = f"session:{session_id}:messages"
            messages = await redis.lrange(key, 0, -1)
            return [json.loads(m) for m in messages if m]
        except Exception as e:
            logger.warning(f"获取全部消息失败: {e}")
            return []
    
    @_async_retry_on_redis_error
    async def save_message(self, session_id: str, message: dict) -> bool:
        """
        保存对话消息（增强版）
        
        增强点：
        1. 滑动窗口：超过MAX_MESSAGES时保留首条+最近N-1条
        2. 自动触发压缩检查
        3. 向量化存储：支持语义检索
        4. 增量实体索引：支持快速实体查询
        """
        redis = await self._get_redis_client(session_id)
        if not redis:
            return False
        
        # 验证消息格式
        if "role" not in message or "content" not in message:
            logger.warning(f"消息格式错误: {message}")
            return False
        
        # 添加时间戳
        if "timestamp" not in message:
            message["timestamp"] = datetime.now().isoformat()
        
        key = f"session:{session_id}:messages"
        await redis.rpush(key, json.dumps(message, ensure_ascii=False))
        
        # 滑动窗口管理
        length = await redis.llen(key)
        if length > self.max_messages:
            # 保留首条消息 + 最近N-1条
            first = await redis.lindex(key, 0)
            await redis.ltrim(key, -(self.max_messages - 1), -1)
            if first:
                await redis.lpush(key, first)
            logger.debug(f"滑动窗口修剪: {length} -> {self.max_messages}")
        
        # 检查是否需要压缩
        if length > self.compress_threshold:
            await self._compress_conversation(session_id)
        
        # 向量化存储（异步，不阻塞主流程）
        if self.vector_store and self.enable_vector_store:
            try:
                await self.vector_store.store_message(message, session_id)
            except Exception as e:
                logger.warning(f"向量化存储失败（不影响主流程）: {e}")
        
        # 增量实体索引（异步，不阻塞主流程）
        if self.entity_index and self.enable_entity_index:
            try:
                # 生成消息ID
                message_id = f"msg_{session_id}_{message.get('timestamp', datetime.now().isoformat())}"
                self.entity_index.add_message(message, session_id, message_id)
            except Exception as e:
                logger.warning(f"实体索引更新失败（不影响主流程）: {e}")
        
        # 多粒度摘要更新（异步，不阻塞主流程）
        if self.summarizer and self.enable_summarizer:
            try:
                await self.summarizer.process_message(session_id, message)
            except Exception as e:
                logger.warning(f"多粒度摘要更新失败（不影响主流程）: {e}")
        
        # 失效相关缓存
        if self.cache_manager:
            try:
                await self.cache_manager.invalidate_pattern(f"context:{session_id}:*")
            except Exception as e:
                logger.warning(f"缓存失效失败（不影响主流程）: {e}")
        
        return True
    
    async def save_conversation(self, session_id: str, user_message: str, assistant_reply: str) -> bool:
        """保存一轮对话（用户消息 + 助手回复）"""
        user_saved = await self.save_message(session_id, {
            "role": "user",
            "content": user_message
        })
        assistant_saved = await self.save_message(session_id, {
            "role": "assistant",
            "content": assistant_reply
        })
        return user_saved and assistant_saved
    
    async def clear_messages(self, session_id: str) -> bool:
        """清空对话历史"""
        redis = await self._get_redis_client(session_id)
        if not redis:
            return False
        
        try:
            key = f"session:{session_id}:messages"
            await redis.delete(key)
            
            # 失效相关缓存
            if self.cache_manager:
                try:
                    await self.cache_manager.invalidate_pattern(f"context:{session_id}:*")
                except Exception as e:
                    logger.warning(f"缓存失效失败: {e}")
            
            return True
        except Exception as e:
            logger.warning(f"清空对话历史失败: {e}")
            return False
    
    async def _get_message_count(self, session_id: str) -> int:
        """获取消息总数"""
        redis = await self._get_redis_client(session_id)
        if not redis:
            return 0
        
        try:
            key = f"session:{session_id}:messages"
            return await redis.llen(key)
        except Exception:
            return 0
    
    # ─── 智能压缩 ───
    
    def _calculate_complexity(self, messages: List[dict]) -> float:
        """
        计算对话复杂度（0-1之间）
        
        复杂度因素：
        1. 消息平均长度
        2. 实体密度（地点、店名、价格等）
        3. 工具调用次数
        4. 对话轮次
        """
        if not messages:
            return 0.0
        
        # 1. 消息平均长度
        avg_length = sum(len(m.get("content", "")) for m in messages) / len(messages)
        length_score = min(avg_length / 200, 1.0)  # 200字符为满分
        
        # 2. 实体密度
        entity_count = 0
        for msg in messages:
            content = msg.get("content", "")
            # 统计可能的实体数量
            entity_count += len(re.findall(r'[\u4e00-\u9fff]{2,6}(?:店|厅|馆|屋|坊|楼|阁)', content))
            entity_count += len(re.findall(r'人均\s*\d+', content))
            entity_count += len(re.findall(r'[\u4e00-\u9fff]{2,6}(?:路|街|区|市|省)', content))
        
        entity_density = entity_count / len(messages) if messages else 0
        entity_score = min(entity_density / 2, 1.0)  # 每条消息2个实体为满分
        
        # 3. 工具调用次数
        tool_calls = sum(1 for m in messages if m.get("role") == "tool" or m.get("tool_calls"))
        tool_ratio = tool_calls / len(messages) if messages else 0
        tool_score = min(tool_ratio * 2, 1.0)  # 50%工具调用为满分
        
        # 4. 对话轮次
        turn_count = sum(1 for m in messages if m.get("role") == "user")
        turn_score = min(turn_count / 20, 1.0)  # 20轮为满分
        
        # 综合复杂度（加权平均）
        complexity = (
            length_score * 0.3 +
            entity_score * 0.3 +
            tool_score * 0.2 +
            turn_score * 0.2
        )
        
        return min(complexity, 1.0)
    
    def _get_dynamic_threshold(self, messages: List[dict]) -> int:
        """
        根据对话复杂度动态调整压缩阈值
        
        策略：
        - 低复杂度（<0.3）：使用默认阈值（30条）
        - 中复杂度（0.3-0.7）：降低阈值（20-30条）
        - 高复杂度（>0.7）：进一步降低阈值（15-20条）
        """
        complexity = self._calculate_complexity(messages)
        
        if complexity < 0.3:
            # 低复杂度：使用默认阈值
            return self.compress_threshold
        elif complexity < 0.7:
            # 中复杂度：线性插值
            return int(self.compress_threshold - (complexity - 0.3) * 25)
        else:
            # 高复杂度：进一步降低
            return max(15, int(self.compress_threshold - (complexity - 0.7) * 30))
    
    async def _compress_conversation(self, session_id: str):
        """
        智能压缩对话历史（动态阈值版本）
        
        策略：
        1. 计算对话复杂度
        2. 根据复杂度动态调整压缩阈值
        3. 提取关键实体（地名、店名、价格、菜系）
        4. 保留意图分布
        5. 生成压缩摘要
        6. 重组消息列表
        """
        messages = await self.get_all_messages(session_id)
        
        # 动态计算压缩阈值
        dynamic_threshold = self._get_dynamic_threshold(messages)
        
        if len(messages) <= dynamic_threshold:
            return
        
        # 分离：保留最近 + 压缩早期
        recent = messages[-self.keep_recent:]
        to_compress = messages[:-self.keep_recent]
        
        # 过滤掉已有的压缩摘要
        to_compress = [m for m in to_compress if m.get("metadata", {}).get("type") != "compressed_summary"]
        
        if not to_compress:
            return
        
        # 提取关键实体
        entities = await self._extract_entities(to_compress)
        
        # 生成压缩摘要（优先使用LLM，降级到规则）
        if self.llm:
            summary = await self._llm_summary(to_compress, entities)
        else:
            summary = self._rule_summary(to_compress, entities)
        
        # 构建压缩消息
        compressed_msg = {
            "role": "system",
            "content": summary,
            "timestamp": datetime.now().isoformat(),
            "metadata": {
                "type": "compressed_summary",
                "compressed_count": len(to_compress),
                "entities": entities,
                "time_range": {
                    "start": to_compress[0].get("timestamp"),
                    "end": to_compress[-1].get("timestamp")
                }
            }
        }
        
        # 重组：压缩摘要 + 最近消息
        new_messages = [compressed_msg] + recent
        
        # 更新Redis（使用分片存储）
        redis = await self._get_redis_client(session_id)
        key = f"session:{session_id}:messages"
        await redis.delete(key)
        if new_messages:
            await redis.rpush(key, *[json.dumps(m, ensure_ascii=False) for m in new_messages])
            await redis.expire(key, self.ttl)
        
        logger.info(f"对话压缩完成: {len(messages)} -> {len(new_messages)} 条")
    
    async def _extract_entities(self, messages: List[dict]) -> Dict[str, List[str]]:
        """
        提取关键实体（增强版：支持jieba分词）
        """
        entities = {
            "locations": set(),
            "restaurants": set(),
            "cuisines": set(),
            "prices": set(),
            "intents": set()
        }
        
        # 中文地名后缀
        location_suffixes = ['路', '街', '区', '市', '省', '镇', '村', '小区', '大厦', '广场', '中心']
        # 中文店名后缀
        shop_suffixes = ['店', '厅', '馆', '屋', '坊', '楼', '阁', '居', '苑', '堂', '斋', '庄']
        # 菜系关键词
        cuisine_keywords = ['川菜', '湘菜', '粤菜', '鲁菜', '苏菜', '浙菜', '闽菜', '徽菜', 
                           '火锅', '烧烤', '日料', '韩餐', '西餐', '中餐', '快餐', '甜品', '咖啡']
        
        for msg in messages:
            content = msg.get("content", "")
            
            # 从消息metadata中提取
            msg_entities = msg.get("entities", {})
            if msg_entities:
                if "food_type" in msg_entities:
                    entities["cuisines"].add(msg_entities["food_type"])
                if "place_type" in msg_entities:
                    entities["locations"].add(msg_entities["place_type"])
            
            # 从intent中提取
            intent = msg.get("intent", "")
            if intent:
                entities["intents"].add(intent)
            
            # 使用jieba分词提取实体
            if self.jieba and self.jieba is not False:
                words = list(self.jieba.cut(content))
                
                for i, word in enumerate(words):
                    # 提取地名
                    if any(word.endswith(suffix) for suffix in location_suffixes):
                        # 尝试获取前一个词作为地名的一部分
                        if i > 0 and len(words[i-1]) >= 2:
                            entities["locations"].add(words[i-1] + word)
                        else:
                            entities["locations"].add(word)
                    
                    # 提取店名
                    if any(word.endswith(suffix) for suffix in shop_suffixes):
                        # 尝试获取前一个词作为店名的一部分
                        if i > 0 and len(words[i-1]) >= 2:
                            entities["restaurants"].add(words[i-1] + word)
                        else:
                            entities["restaurants"].add(word)
                    
                    # 提取菜系
                    if word in cuisine_keywords:
                        entities["cuisines"].add(word)
            else:
                # 降级：使用正则表达式
                # 匹配中文店名（如XX店、XX厅、XX馆）
                shop_matches = re.findall(r'[\u4e00-\u9fff]{2,6}(?:店|厅|馆|屋|坊|楼|阁)', content)
                entities["restaurants"].update(shop_matches[:3])
                
                # 匹配地名
                location_matches = re.findall(r'[\u4e00-\u9fff]{2,6}(?:路|街|区|市|省)', content)
                entities["locations"].update(location_matches[:3])
            
            # 匹配价格（通用）
            price_matches = re.findall(r'人均\s*(\d+)', content)
            for p in price_matches:
                entities["prices"].add(f"{p}元")
            
            # 匹配价格区间
            price_range_matches = re.findall(r'(\d+)\s*[-~到]\s*(\d+)\s*元', content)
            for low, high in price_range_matches:
                entities["prices"].add(f"{low}-{high}元")
        
        return {k: list(v)[:10] for k, v in entities.items()}
    
    def _rule_summary(self, messages: List[dict], entities: Dict) -> str:
        """规则压缩摘要生成"""
        parts = []
        
        # 统计用户和助手消息数
        user_count = sum(1 for m in messages if m.get("role") == "user")
        if user_count > 0:
            parts.append(f"用户进行了{user_count}轮对话")
        
        # 提取意图分布
        if entities.get("intents"):
            parts.append(f"涉及意图: {', '.join(entities['intents'][:5])}")
        
        # 提取关键实体
        if entities.get("restaurants"):
            parts.append(f"提及店名: {', '.join(entities['restaurants'][:5])}")
        if entities.get("locations"):
            parts.append(f"涉及地点: {', '.join(entities['locations'][:3])}")
        if entities.get("cuisines"):
            parts.append(f"偏好菜系: {', '.join(entities['cuisines'][:3])}")
        if entities.get("prices"):
            parts.append(f"价格区间: {', '.join(entities['prices'][:3])}")
        
        return "[历史摘要] " + "；".join(parts)
    
    async def _llm_summary(self, messages: List[dict], entities: Dict) -> str:
        """使用LLM生成智能摘要"""
        try:
            # 格式化消息
            conversation_text = []
            for msg in messages:
                role = "用户" if msg.get("role") == "user" else "助手"
                content = msg.get("content", "")[:100]
                conversation_text.append(f"{role}: {content}")
            
            prompt = f"""请对以下对话进行摘要，要求：
1. 保留用户的关键需求和偏好
2. 保留重要的地点、店名、价格等实体
3. 使用简洁的第三人称描述
4. 控制在100字以内

对话内容：
{chr(10).join(conversation_text[:20])}

已提取的关键实体：
{json.dumps(entities, ensure_ascii=False)}

请直接输出摘要："""
            
            result = await self.llm.chat(
                messages=[
                    {"role": "system", "content": "你是一个专业的对话摘要助手。"},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200,
                temperature=0.3
            )
            
            summary = result.get("content", "") if isinstance(result, dict) else result
            return f"[历史摘要] {summary}" if summary else self._rule_summary(messages, entities)
            
        except Exception as e:
            logger.warning(f"LLM摘要生成失败，降级到规则: {e}")
            return self._rule_summary(messages, entities)
    
    # ─── 会话管理 ───
    
    async def get_session_info(self, session_id: str) -> dict:
        """获取会话信息"""
        context = await self.get_context(session_id)
        
        return {
            "session_id": session_id,
            "message_count": context.get("message_count", 0),
            "recommended_count": len(context.get("already_recommended", [])),
        }
    
    async def delete_session(self, session_id: str) -> bool:
        """删除会话（包括所有相关数据）"""
        redis = await self._get_redis_client(session_id)
        if not redis:
            return False
        
        try:
            await self.clear_recommended(session_id)
            await self.clear_messages(session_id)
            
            # 删除向量数据
            if self.vector_store:
                try:
                    await self.vector_store.delete_session_vectors(session_id)
                except Exception as e:
                    logger.warning(f"删除会话向量失败: {e}")
            
            # 清除实体索引数据
            if self.entity_index:
                try:
                    self.entity_index.clear_session(session_id)
                except Exception as e:
                    logger.warning(f"清除会话实体索引失败: {e}")
            
            # 清除多粒度摘要数据
            if self.summarizer:
                try:
                    self.summarizer.clear_session(session_id)
                except Exception as e:
                    logger.warning(f"清除会话摘要失败: {e}")
            
            # 清除权重系统数据
            if self.weight_system:
                try:
                    self.weight_system.clear_session(session_id)
                except Exception as e:
                    logger.warning(f"清除会话权重数据失败: {e}")
            
            # 失效所有相关缓存
            if self.cache_manager:
                try:
                    await self.cache_manager.invalidate_pattern(f"*{session_id}*")
                except Exception as e:
                    logger.warning(f"缓存失效失败: {e}")
            
            logger.info(f"删除会话: {session_id}")
            return True
        except Exception as e:
            logger.warning(f"删除会话失败: {e}")
            return False
    
    # ─── 实体索引查询 ───
    
    def get_session_entities(self, session_id: str) -> Dict[str, List[str]]:
        """
        获取会话中的所有实体
        
        Args:
            session_id: 会话ID
            
        Returns:
            实体字典，按类型分组
        """
        if not self.entity_index:
            return {}
        
        try:
            return self.entity_index.get_session_entities(session_id)
        except Exception as e:
            logger.warning(f"获取会话实体失败: {e}")
            return {}
    
    def get_frequent_entities(
        self,
        entity_type: str = None,
        top_k: int = 10,
        min_frequency: int = 2
    ) -> List[Dict[str, Any]]:
        """
        获取高频实体
        
        Args:
            entity_type: 实体类型（可选）
            top_k: 返回数量
            min_frequency: 最低频次
            
        Returns:
            高频实体列表
        """
        if not self.entity_index:
            return []
        
        try:
            entities = self.entity_index.get_frequent_entities(entity_type, top_k, min_frequency)
            return [
                {
                    "name": e.name,
                    "type": e.entity_type,
                    "frequency": e.frequency,
                    "first_seen": e.first_seen.isoformat(),
                    "last_seen": e.last_seen.isoformat(),
                }
                for e in entities
            ]
        except Exception as e:
            logger.warning(f"获取高频实体失败: {e}")
            return []
    
    def get_related_entities(self, entity_name: str) -> List[str]:
        """
        获取与指定实体相关的实体
        
        Args:
            entity_name: 实体名称
            
        Returns:
            相关实体名称列表
        """
        if not self.entity_index:
            return []
        
        try:
            return list(self.entity_index.get_related_entities(entity_name))
        except Exception as e:
            logger.warning(f"获取相关实体失败: {e}")
            return []
    
    def get_entity_index_stats(self) -> Dict[str, Any]:
        """获取实体索引统计信息"""
        if not self.entity_index:
            return {"enabled": False}
        
        try:
            stats = self.entity_index.get_statistics()
            return {
                "enabled": True,
                "stats": stats
            }
        except Exception as e:
            logger.error(f"获取实体索引统计失败: {e}")
            return {"enabled": True, "error": str(e)}
    
    # ─── 多粒度摘要查询 ───
    
    async def get_session_summary(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        获取会话级摘要
        
        Args:
            session_id: 会话ID
            
        Returns:
            会话摘要字典
        """
        if not self.summarizer:
            return None
        
        try:
            summary = await self.summarizer.get_session_summary(session_id)
            if not summary:
                return None
            
            return {
                "session_id": summary.session_id,
                "overall_summary": summary.overall_summary,
                "total_messages": summary.total_messages,
                "segment_count": len(summary.segments),
                "key_entities": summary.key_entities,
                "intent_distribution": summary.intent_distribution,
                "start_time": summary.start_time.isoformat() if summary.start_time else None,
                "end_time": summary.end_time.isoformat() if summary.end_time else None,
            }
        except Exception as e:
            logger.error(f"获取会话摘要失败: {e}")
            return None
    
    def get_conversation_segments(self, session_id: str) -> List[Dict[str, Any]]:
        """
        获取会话的所有对话段落
        
        Args:
            session_id: 会话ID
            
        Returns:
            段落列表
        """
        if not self.summarizer:
            return []
        
        try:
            segments = self.summarizer.get_all_segments(session_id)
            return [
                {
                    "segment_id": seg.segment_id,
                    "topic": seg.topic,
                    "summary": seg.summary,
                    "message_count": seg.message_count,
                    "entities": seg.entities,
                    "intents": seg.intents,
                    "start_time": seg.start_time.isoformat() if seg.start_time else None,
                    "end_time": seg.end_time.isoformat() if seg.end_time else None,
                }
                for seg in segments
            ]
        except Exception as e:
            logger.warning(f"获取对话段落失败: {e}")
            return []
    
    def get_summarizer_stats(self) -> Dict[str, Any]:
        """获取多粒度摘要统计信息"""
        if not self.summarizer:
            return {"enabled": False}
        
        try:
            stats = self.summarizer.get_statistics()
            return {
                "enabled": True,
                "stats": stats
            }
        except Exception as e:
            logger.error(f"获取摘要统计失败: {e}")
            return {"enabled": True, "error": str(e)}
    
    # ─── 关键信息权重查询 ───
    
    def get_weighted_entities(
        self,
        session_id: str,
        entity_type: str = None,
        top_k: int = 20
    ) -> List[Dict[str, Any]]:
        """
        获取按权重排序的实体列表
        
        Args:
            session_id: 会话ID
            entity_type: 实体类型过滤（可选）
            top_k: 返回数量
            
        Returns:
            按权重排序的实体列表
        """
        if not self.weight_system:
            return []
        
        try:
            entities = self.weight_system.get_weighted_entities(
                session_id=session_id,
                entity_type=entity_type,
                top_k=top_k
            )
            
            return [
                {
                    "name": e.name,
                    "type": e.entity_type,
                    "weight": e.weight,
                    "frequency": e.frequency,
                    "user_preference": e.user_preference,
                    "context_relevance": e.context_relevance
                }
                for e in entities
            ]
        except Exception as e:
            logger.warning(f"获取权重实体失败: {e}")
            return []
    
    def get_critical_entities(
        self,
        session_id: str,
        threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        获取关键实体（高权重实体）
        
        Args:
            session_id: 会话ID
            threshold: 权重阈值
            
        Returns:
            关键实体列表
        """
        if not self.weight_system:
            return []
        
        try:
            entities = self.weight_system.get_critical_entities(
                session_id=session_id,
                threshold=threshold
            )
            
            return [
                {
                    "name": e.name,
                    "type": e.entity_type,
                    "weight": e.weight,
                    "frequency": e.frequency
                }
                for e in entities
            ]
        except Exception as e:
            logger.warning(f"获取关键实体失败: {e}")
            return []
    
    def update_user_preference(
        self,
        session_id: str,
        entity_name: str,
        preference_delta: float
    ) -> None:
        """
        更新用户偏好
        
        Args:
            session_id: 会话ID
            entity_name: 实体名称
            preference_delta: 偏好变化量 [-1, 1]
        """
        if not self.weight_system:
            return
        
        try:
            self.weight_system.update_user_preference(
                session_id=session_id,
                entity_name=entity_name,
                preference_delta=preference_delta
            )
        except Exception as e:
            logger.warning(f"更新用户偏好失败: {e}")
    
    def get_weight_system_stats(self) -> Dict[str, Any]:
        """获取关键信息权重系统统计信息"""
        if not self.weight_system:
            return {"enabled": False}
        
        try:
            stats = self.weight_system.get_statistics()
            return {
                "enabled": True,
                "stats": stats
            }
        except Exception as e:
            logger.error(f"获取权重系统统计失败: {e}")
            return {"enabled": True, "error": str(e)}
    
    # ─── 语义检索 ───
    
    async def semantic_search(
        self,
        query: str,
        session_id: str = None,
        top_k: int = 5,
        score_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        语义相似度搜索
        
        Args:
            query: 查询文本
            session_id: 会话ID（可选过滤）
            top_k: 返回结果数量
            score_threshold: 相似度阈值
            
        Returns:
            搜索结果列表
        """
        if not self.vector_store:
            logger.warning("向量存储未初始化")
            return []
        
        try:
            results = await self.vector_store.search_similar(
                query=query,
                session_id=session_id,
                top_k=top_k,
                score_threshold=score_threshold
            )
            
            # 格式化结果
            formatted_results = []
            for doc_id, score, metadata in results:
                formatted_results.append({
                    "id": doc_id,
                    "score": score,
                    "metadata": metadata
                })
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"语义搜索失败: {e}")
            return []
    
    async def search_by_entities(
        self,
        entities: Dict[str, List[str]],
        session_id: str = None,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        基于实体的语义搜索
        
        Args:
            entities: 实体字典
            session_id: 会话ID
            top_k: 返回数量
            
        Returns:
            搜索结果
        """
        if not self.vector_store:
            return []
        
        try:
            results = await self.vector_store.search_by_entities(
                entities=entities,
                session_id=session_id,
                top_k=top_k
            )
            
            return [
                {"id": doc_id, "score": score, "metadata": metadata}
                for doc_id, score, metadata in results
            ]
            
        except Exception as e:
            logger.error(f"实体搜索失败: {e}")
            return []
    
    async def get_vector_stats(self) -> Dict[str, Any]:
        """获取向量存储统计信息"""
        if not self.vector_store:
            return {"enabled": False}
        
        try:
            stats = self.vector_store.get_stats()
            health = await self.vector_store.health_check()
            
            return {
                "enabled": True,
                "healthy": health.get("healthy", False),
                "stats": stats
            }
        except Exception as e:
            logger.error(f"获取向量统计失败: {e}")
            return {"enabled": True, "healthy": False, "error": str(e)}
    
    # ─── 工具方法 ───
    
    def extract_pois_from_results(self, results: dict) -> List[dict]:
        """从工具执行结果中提取POI列表"""
        all_pois = []
        
        for key, value in results.items():
            if not isinstance(value, dict):
                continue
            
            if "pois" in value:
                all_pois.extend(value["pois"])
            elif "items" in value:
                for item in value["items"]:
                    if isinstance(item, dict):
                        poi = item.get("poi", item)
                        if isinstance(poi, dict):
                            all_pois.append(poi)
        
        # 去重
        seen_names = set()
        unique_pois = []
        for poi in all_pois:
            name = poi.get("name", "")
            if name and name not in seen_names:
                seen_names.add(name)
                unique_pois.append(poi)
        
        return unique_pois
    
    def filter_already_recommended(self, pois: List[dict], already_recommended: List[str]) -> List[dict]:
        """过滤已推荐的POI"""
        if not already_recommended:
            return pois
        
        filtered = []
        for poi in pois:
            name = poi.get("name", "")
            if name and name not in already_recommended:
                filtered.append(poi)
        
        return filtered
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取记忆管理器统计信息"""
        stats = {
            "max_messages": self.max_messages,
            "message_window": self.message_window,
            "ttl_days": self.ttl // 86400,
            "compress_threshold": self.compress_threshold,
            "keep_recent": self.keep_recent,
            "redis_connected": self.redis is not None,
            "llm_enabled": self.llm is not None,
            "components": {}
        }
        
        # 向量存储统计
        if self.vector_store:
            stats["components"]["vector_store"] = {
                "enabled": self.enable_vector_store,
                "type": "VectorStore"
            }
        
        # 实体索引统计
        if self.entity_index:
            stats["components"]["entity_index"] = {
                "enabled": self.enable_entity_index,
                "stats": self.entity_index.get_statistics()
            }
        
        # 摘要管理器统计
        if self.summarizer:
            stats["components"]["summarizer"] = {
                "enabled": self.enable_summarizer,
                "stats": self.summarizer.get_statistics()
            }
        
        # 权重系统统计
        if self.weight_system:
            stats["components"]["weight_system"] = {
                "enabled": self.enable_weight_system,
                "stats": self.weight_system.get_statistics()
            }
        
        # 分片存储统计
        if self.sharded_storage:
            stats["components"]["sharded_storage"] = {
                "enabled": True,
                "stats": self.sharded_storage.get_statistics()
            }
        
        # 缓存统计
        if self.cache_manager:
            stats["components"]["cache"] = {
                "enabled": True,
                "stats": self.cache_manager.get_statistics()
            }
        
        return stats


# 全局单例（延迟初始化）
_memory_manager: Optional[EnhancedMemoryManager] = None


def get_memory_manager(redis_client=None, llm_client=None, vector_store=None, 
                       entity_index=None, summarizer=None, weight_system=None,
                       sharded_storage=None, cache_manager=None, config: dict = None) -> EnhancedMemoryManager:
    """获取记忆管理器单例"""
    global _memory_manager
    
    if _memory_manager is None:
        _memory_manager = EnhancedMemoryManager(redis_client, llm_client, vector_store, 
                                               entity_index, summarizer, weight_system,
                                               sharded_storage, cache_manager, config)
    
    return _memory_manager


def reset_memory_manager():
    """重置记忆管理器单例（用于测试）"""
    global _memory_manager
    _memory_manager = None
