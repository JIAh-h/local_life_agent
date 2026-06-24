"""
多粒度摘要系统

设计原则：
1. 三层粒度：消息级、话题段级、会话级
2. 增量更新：新消息到达时增量处理
3. 话题分割：基于语义相似度自动分割话题
4. 渐进压缩：从细粒度到粗粒度逐层压缩
5. 信息保留：关键实体和意图在每个粒度级别保留
"""
import logging
import json
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ConversationSegment:
    """对话片段（话题段）"""
    segment_id: str
    session_id: str
    topic: str
    messages: List[Dict[str, Any]] = field(default_factory=list)
    entities: Dict[str, List[str]] = field(default_factory=dict)
    intents: List[str] = field(default_factory=list)
    summary: str = ""
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    message_count: int = 0


@dataclass
class SessionSummary:
    """会话级摘要"""
    session_id: str
    overall_summary: str = ""
    segments: List[ConversationSegment] = field(default_factory=list)
    key_entities: Dict[str, List[str]] = field(default_factory=dict)
    intent_distribution: Dict[str, int] = field(default_factory=dict)
    total_messages: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class MultiGranularitySummarizer:
    """
    多粒度摘要管理器
    
    三层摘要结构：
    1. 消息级（L1）：原始消息，保留全部细节
    2. 话题段级（L2）：按话题分组，生成段落摘要
    3. 会话级（L3）：全局摘要，涵盖所有话题
    
    职责：
    1. 自动话题分割
    2. 增量更新摘要
    3. 提供多粒度查询接口
    4. 与压缩系统协同工作
    """
    
    # 配置常量
    DEFAULT_SEGMENT_SIZE = 10        # 默认每段消息数
    SIMILARITY_THRESHOLD = 0.3       # 话题分割相似度阈值
    MAX_SEGMENTS = 20                # 最大段落数
    
    def __init__(self, llm_client=None, embedding_client=None, entity_index=None, config: dict = None):
        """
        初始化多粒度摘要管理器
        
        Args:
            llm_client: LLM客户端（用于摘要生成）
            embedding_client: 向量化客户端（用于话题分割）
            entity_index: 实体索引实例
            config: 配置字典
        """
        self.llm = llm_client
        self.embedding = embedding_client
        self.entity_index = entity_index
        
        # 加载配置
        config = config or {}
        self.segment_size = config.get("segment_size", self.DEFAULT_SEGMENT_SIZE)
        self.similarity_threshold = config.get("similarity_threshold", self.SIMILARITY_THRESHOLD)
        self.max_segments = config.get("max_segments", self.MAX_SEGMENTS)
        
        # 会话摘要缓存
        self._session_summaries: Dict[str, SessionSummary] = {}
        
        # 话题关键词库（用于话题识别）
        self._topic_keywords = {
            "餐厅推荐": ["推荐", "餐厅", "吃饭", "用餐", "饭店", "好吃"],
            "价格查询": ["价格", "人均", "消费", "便宜", "贵", "多少钱"],
            "位置导航": ["地址", "在哪", "怎么去", "路线", "导航", "地铁"],
            "菜品偏好": ["菜系", "川菜", "湘菜", "粤菜", "火锅", "烧烤"],
            "环境要求": ["环境", "安静", "氛围", "装修", "风格"],
            "预订服务": ["预订", "预约", "订位", "排队", "等位"]
        }
    
    async def process_message(
        self,
        session_id: str,
        message: Dict[str, Any],
        all_messages: List[Dict[str, Any]] = None
    ) -> None:
        """
        处理新消息，增量更新摘要
        
        Args:
            session_id: 会话ID
            message: 新消息
            all_messages: 全部消息列表（可选，用于话题分割）
        """
        # 获取或创建会话摘要
        if session_id not in self._session_summaries:
            self._session_summaries[session_id] = SessionSummary(
                session_id=session_id,
                start_time=datetime.now()
            )
        
        session_summary = self._session_summaries[session_id]
        
        # 更新消息计数
        session_summary.total_messages += 1
        session_summary.end_time = datetime.now()
        
        # 如果没有段落，创建第一个
        if not session_summary.segments:
            session_summary.segments.append(ConversationSegment(
                segment_id=f"{session_id}_seg_0",
                session_id=session_id,
                topic="新对话",
                start_time=datetime.now()
            ))
        
        current_segment = session_summary.segments[-1]
        
        # 添加消息到当前段落
        current_segment.messages.append(message)
        current_segment.message_count += 1
        current_segment.end_time = datetime.now()
        
        # 提取实体和意图
        await self._extract_message_info(message, current_segment, session_id)
        
        # 检查是否需要话题分割
        if all_messages and len(current_segment.messages) >= self.segment_size:
            await self._check_topic_shift(session_id, current_segment, all_messages)
        
        # 定期更新段落摘要
        if current_segment.message_count % 5 == 0:
            await self._update_segment_summary(current_segment)
    
    async def _extract_message_info(
        self,
        message: Dict[str, Any],
        segment: ConversationSegment,
        session_id: str
    ) -> None:
        """提取消息中的实体和意图"""
        content = message.get("content", "")
        
        # 从实体索引获取（如果可用）
        if self.entity_index:
            try:
                entities = self.entity_index.add_message(message, session_id)
                for entity in entities:
                    etype = entity.entity_type
                    if etype not in segment.entities:
                        segment.entities[etype] = []
                    if entity.name not in segment.entities[etype]:
                        segment.entities[etype].append(entity.name)
            except Exception as e:
                logger.warning(f"实体索引更新失败: {e}")
        
        # 提取意图
        intent = self._detect_intent(content)
        if intent and intent not in segment.intents:
            segment.intents.append(intent)
    
    def _detect_intent(self, content: str) -> Optional[str]:
        """检测消息意图"""
        content_lower = content.lower()
        
        intent_scores = {}
        for intent, keywords in self._topic_keywords.items():
            score = sum(1 for kw in keywords if kw in content_lower)
            if score > 0:
                intent_scores[intent] = score
        
        if intent_scores:
            return max(intent_scores, key=intent_scores.get)
        return None
    
    async def _check_topic_shift(
        self,
        session_id: str,
        current_segment: ConversationSegment,
        all_messages: List[Dict[str, Any]]
    ) -> None:
        """检查是否发生了话题转换"""
        if not self.embedding:
            # 没有embedding服务，基于规则判断
            await self._rule_based_topic_check(session_id, current_segment)
            return
        
        try:
            # 使用embedding计算语义相似度
            recent_messages = [m.get("content", "") for m in current_segment.messages[-3:]]
            recent_text = " ".join(recent_messages)
            
            # 获取之前段落的文本
            session_summary = self._session_summaries[session_id]
            if len(session_summary.segments) > 1:
                prev_segment = session_summary.segments[-2]
                prev_text = " ".join([m.get("content", "") for m in prev_segment.messages[-3:]])
                
                # 计算相似度（简化实现，实际需要embedding）
                similarity = self._calculate_text_similarity(recent_text, prev_text)
                
                if similarity < self.similarity_threshold:
                    # 话题转换，创建新段落
                    await self._create_new_segment(session_id, current_segment)
            
        except Exception as e:
            logger.warning(f"话题分割检测失败: {e}")
    
    async def _rule_based_topic_check(
        self,
        session_id: str,
        current_segment: ConversationSegment
    ) -> None:
        """基于规则的话题检查"""
        # 检查意图是否变化
        if len(current_segment.intents) >= 2:
            recent_intents = current_segment.intents[-3:]
            if len(set(recent_intents)) >= 2:
                await self._create_new_segment(session_id, current_segment)
    
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """计算文本相似度（简单实现）"""
        if not text1 or not text2:
            return 0.0
        
        # 字符级别的相似度
        set1 = set(text1)
        set2 = set(text2)
        
        if not set1 or not set2:
            return 0.0
        
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        
        return intersection / union if union > 0 else 0.0
    
    async def _create_new_segment(
        self,
        session_id: str,
        current_segment: ConversationSegment
    ) -> None:
        """创建新的对话段落"""
        # 先更新当前段落的摘要
        await self._update_segment_summary(current_segment)
        
        # 限制段落数量
        session_summary = self._session_summaries[session_id]
        if len(session_summary.segments) >= self.max_segments:
            # 合并最旧的段落
            await self._merge_old_segments(session_id)
        
        # 创建新段落
        segment_index = len(session_summary.segments)
        new_segment = ConversationSegment(
            segment_id=f"{session_id}_seg_{segment_index}",
            session_id=session_id,
            topic="新话题",
            start_time=datetime.now()
        )
        
        session_summary.segments.append(new_segment)
        logger.debug(f"创建新段落: {new_segment.segment_id}")
    
    async def _update_segment_summary(self, segment: ConversationSegment) -> None:
        """更新段落摘要"""
        if not segment.messages:
            return
        
        if self.llm:
            try:
                segment.summary = await self._llm_segment_summary(segment)
            except Exception as e:
                logger.warning(f"LLM段落摘要失败: {e}")
                segment.summary = self._rule_segment_summary(segment)
        else:
            segment.summary = self._rule_segment_summary(segment)
        
        # 更新话题标签
        segment.topic = self._detect_segment_topic(segment)
    
    async def _llm_segment_summary(self, segment: ConversationSegment) -> str:
        """使用LLM生成段落摘要"""
        # 构建对话文本
        conversation = []
        for msg in segment.messages[-10:]:  # 只取最近10条
            role = "用户" if msg.get("role") == "user" else "助手"
            content = msg.get("content", "")[:80]
            conversation.append(f"{role}: {content}")
        
        # 构建实体信息
        entity_info = []
        for etype, names in segment.entities.items():
            if names:
                entity_info.append(f"{etype}: {', '.join(names[:3])}")
        
        prompt = f"""请对以下对话段落进行摘要，要求：
1. 用一句话概括对话主题
2. 保留关键实体信息
3. 控制在50字以内

对话内容：
{chr(10).join(conversation)}

关键实体：
{chr(10).join(entity_info) if entity_info else '无'}

请直接输出摘要："""
        
        try:
            result = await self.llm.chat(
                messages=[
                    {"role": "system", "content": "你是一个专业的对话摘要助手。"},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=100,
                temperature=0.3
            )
            
            summary = result.get("content", "") if isinstance(result, dict) else result
            return summary if summary else self._rule_segment_summary(segment)
            
        except Exception as e:
            logger.warning(f"LLM摘要生成失败: {e}")
            return self._rule_segment_summary(segment)
    
    def _rule_segment_summary(self, segment: ConversationSegment) -> str:
        """基于规则的段落摘要"""
        parts = []
        
        # 用户消息数
        user_count = sum(1 for m in segment.messages if m.get("role") == "user")
        if user_count > 0:
            parts.append(f"{user_count}轮对话")
        
        # 关键实体
        if segment.entities.get("restaurant"):
            restaurants = segment.entities["restaurant"][:3]
            parts.append(f"提及{', '.join(restaurants)}")
        
        if segment.entities.get("cuisine"):
            cuisines = segment.entities["cuisine"][:2]
            parts.append(f"偏好{'/'.join(cuisines)}")
        
        # 意图
        if segment.intents:
            parts.append(f"讨论{segment.intents[0]}")
        
        return "；".join(parts) if parts else "对话片段"
    
    def _detect_segment_topic(self, segment: ConversationSegment) -> str:
        """检测段落话题"""
        # 基于意图分布
        if segment.intents:
            intent_counts = {}
            for intent in segment.intents:
                intent_counts[intent] = intent_counts.get(intent, 0) + 1
            return max(intent_counts, key=intent_counts.get)
        
        return "通用对话"
    
    async def _merge_old_segments(self, session_id: str) -> None:
        """合并旧段落"""
        session_summary = self._session_summaries[session_id]
        
        if len(session_summary.segments) < 3:
            return
        
        # 合并前两个段落
        first = session_summary.segments[0]
        second = session_summary.segments[1]
        
        # 合并消息
        first.messages.extend(second.messages)
        first.message_count += second.message_count
        first.end_time = second.end_time
        
        # 合并实体
        for etype, names in second.entities.items():
            if etype not in first.entities:
                first.entities[etype] = []
            for name in names:
                if name not in first.entities[etype]:
                    first.entities[etype].append(name)
        
        # 合并意图
        for intent in second.intents:
            if intent not in first.intents:
                first.intents.append(intent)
        
        # 更新摘要
        first.summary = f"{first.summary}；{second.summary}" if first.summary else second.summary
        
        # 移除第二个段落
        session_summary.segments.pop(1)
        
        # 重新编号
        for i, seg in enumerate(session_summary.segments):
            seg.segment_id = f"{session_id}_seg_{i}"
    
    async def get_session_summary(self, session_id: str) -> Optional[SessionSummary]:
        """获取会话级摘要"""
        if session_id not in self._session_summaries:
            return None
        
        session_summary = self._session_summaries[session_id]
        
        # 如果没有整体摘要，生成一个
        if not session_summary.overall_summary:
            await self._generate_session_summary(session_id)
        
        return session_summary
    
    async def _generate_session_summary(self, session_id: str) -> None:
        """生成会话级整体摘要"""
        session_summary = self._session_summaries.get(session_id)
        if not session_summary:
            return
        
        # 收集所有段落摘要
        segment_summaries = [seg.summary for seg in session_summary.segments if seg.summary]
        
        # 收集所有实体
        all_entities = {}
        for seg in session_summary.segments:
            for etype, names in seg.entities.items():
                if etype not in all_entities:
                    all_entities[etype] = set()
                all_entities[etype].update(names)
        
        # 统计意图分布
        intent_counts = {}
        for seg in session_summary.segments:
            for intent in seg.intents:
                intent_counts[intent] = intent_counts.get(intent, 0) + 1
        
        session_summary.intent_distribution = intent_counts
        session_summary.key_entities = {k: list(v)[:10] for k, v in all_entities.items()}
        
        if self.llm and segment_summaries:
            try:
                session_summary.overall_summary = await self._llm_session_summary(
                    segment_summaries, all_entities, intent_counts
                )
            except Exception as e:
                logger.warning(f"LLM会话摘要失败: {e}")
                session_summary.overall_summary = self._rule_session_summary(
                    segment_summaries, all_entities, intent_counts
                )
        else:
            session_summary.overall_summary = self._rule_session_summary(
                segment_summaries, all_entities, intent_counts
            )
    
    async def _llm_session_summary(
        self,
        segment_summaries: List[str],
        entities: Dict[str, set],
        intent_counts: Dict[str, int]
    ) -> str:
        """使用LLM生成会话级摘要"""
        entity_info = []
        for etype, names in entities.items():
            if names:
                entity_info.append(f"{etype}: {', '.join(list(names)[:5])}")
        
        intent_info = [f"{k}({v}次)" for k, v in sorted(intent_counts.items(), key=lambda x: -x[1])]
        
        prompt = f"""请对以下会话进行整体摘要，要求：
1. 概括用户的主要需求和关注点
2. 列出讨论的主要话题
3. 保留关键实体信息
4. 控制在100字以内

对话段落摘要：
{chr(10).join(f'- {s}' for s in segment_summaries[:10])}

关键实体：
{chr(10).join(entity_info) if entity_info else '无'}

意图分布：{', '.join(intent_info) if intent_info else '无'}

请直接输出会话摘要："""
        
        try:
            result = await self.llm.chat(
                messages=[
                    {"role": "system", "content": "你是一个专业的会话分析助手。"},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200,
                temperature=0.3
            )
            
            summary = result.get("content", "") if isinstance(result, dict) else result
            return summary if summary else self._rule_session_summary(segment_summaries, entities, intent_counts)
            
        except Exception as e:
            logger.warning(f"LLM会话摘要生成失败: {e}")
            return self._rule_session_summary(segment_summaries, entities, intent_counts)
    
    def _rule_session_summary(
        self,
        segment_summaries: List[str],
        entities: Dict[str, set],
        intent_counts: Dict[str, int]
    ) -> str:
        """基于规则的会话级摘要"""
        parts = []
        
        # 话题统计
        if intent_counts:
            top_intents = sorted(intent_counts.items(), key=lambda x: -x[1])[:3]
            parts.append(f"主要讨论: {', '.join([i[0] for i in top_intents])}")
        
        # 关键实体
        if entities.get("restaurant"):
            restaurants = list(entities["restaurant"])[:3]
            parts.append(f"涉及餐厅: {', '.join(restaurants)}")
        
        if entities.get("location"):
            locations = list(entities["location"])[:3]
            parts.append(f"涉及地点: {', '.join(locations)}")
        
        # 段落数
        parts.append(f"共{len(segment_summaries)}个话题段")
        
        return "；".join(parts) if parts else "会话摘要"
    
    def get_segment_details(self, session_id: str, segment_index: int = -1) -> Optional[ConversationSegment]:
        """获取指定段落详情"""
        if session_id not in self._session_summaries:
            return None
        
        segments = self._session_summaries[session_id].segments
        if not segments:
            return None
        
        try:
            return segments[segment_index]
        except IndexError:
            return None
    
    def get_all_segments(self, session_id: str) -> List[ConversationSegment]:
        """获取所有段落"""
        if session_id not in self._session_summaries:
            return []
        
        return self._session_summaries[session_id].segments
    
    def clear_session(self, session_id: str) -> None:
        """清除会话摘要"""
        if session_id in self._session_summaries:
            del self._session_summaries[session_id]
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_sessions = len(self._session_summaries)
        total_segments = sum(len(s.segments) for s in self._session_summaries.values())
        total_messages = sum(s.total_messages for s in self._session_summaries.values())
        
        return {
            "total_sessions": total_sessions,
            "total_segments": total_segments,
            "total_messages": total_messages,
            "avg_segments_per_session": total_segments / total_sessions if total_sessions > 0 else 0,
            "avg_messages_per_segment": total_messages / total_segments if total_segments > 0 else 0
        }


# 全局单例
_summarizer: Optional[MultiGranularitySummarizer] = None


def get_multi_granularity_summarizer(
    llm_client=None,
    embedding_client=None,
    entity_index=None,
    config: dict = None
) -> MultiGranularitySummarizer:
    """获取多粒度摘要管理器单例"""
    global _summarizer
    
    if _summarizer is None:
        _summarizer = MultiGranularitySummarizer(llm_client, embedding_client, entity_index, config)
    
    return _summarizer


def reset_multi_granularity_summarizer():
    """重置多粒度摘要管理器单例"""
    global _summarizer
    _summarizer = None
