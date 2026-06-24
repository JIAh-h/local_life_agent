"""
关键信息权重系统

设计原则：
1. 多维权重：考虑实体类型、频率、时间、用户偏好
2. 动态调整：根据用户行为实时调整权重
3. 优先级排序：支持按权重排序保留关键信息
4. 上下文感知：考虑当前对话上下文调整权重
"""
import logging
import math
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class WeightedEntity:
    """带权重的实体"""
    name: str
    entity_type: str
    weight: float
    frequency: int = 1
    first_seen: datetime = field(default_factory=datetime.now)
    last_seen: datetime = field(default_factory=datetime.now)
    user_preference: float = 0.0  # 用户偏好分数 [-1, 1]
    context_relevance: float = 0.0  # 上下文相关性 [0, 1]


@dataclass
class WeightConfig:
    """权重配置"""
    # 基础权重（按实体类型）
    type_weights: Dict[str, float] = field(default_factory=lambda: {
        "restaurant": 1.0,    # 餐厅名称（高权重）
        "location": 0.9,      # 地点（高权重）
        "cuisine": 0.8,       # 菜系（中高权重）
        "price": 0.7,         # 价格（中权重）
        "intent": 0.6,        # 意图（中权重）
        "preference": 0.85,   # 用户偏好（中高权重）
    })
    
    # 时间衰减因子
    time_decay_hours: float = 24.0  # 24小时后权重减半
    
    # 频率权重因子
    frequency_factor: float = 0.1  # 每次出现增加10%权重
    max_frequency_bonus: float = 1.0  # 最大频率加成
    
    # 用户偏好权重
    preference_factor: float = 0.3  # 用户偏好对权重的影响
    
    # 上下文相关性权重
    context_factor: float = 0.2  # 上下文相关性对权重的影响


class InfoWeightSystem:
    """
    关键信息权重系统
    
    职责：
    1. 为实体分配多维权重
    2. 根据时间、频率、偏好动态调整权重
    3. 提供按权重排序的实体列表
    4. 支持压缩时的关键信息保留决策
    """
    
    def __init__(self, entity_index=None, config: WeightConfig = None):
        """
        初始化权重系统
        
        Args:
            entity_index: 实体索引实例
            config: 权重配置
        """
        self.entity_index = entity_index
        self.config = config or WeightConfig()
        
        # 用户偏好缓存：session_id -> entity_name -> preference_score
        self._user_preferences: Dict[str, Dict[str, float]] = defaultdict(dict)
        
        # 上下文实体缓存：session_id -> Set[entity_name]
        self._context_entities: Dict[str, set] = defaultdict(set)
        
        # 权重缓存：session_id -> entity_name -> WeightedEntity
        self._weight_cache: Dict[str, Dict[str, WeightedEntity]] = defaultdict(dict)
    
    def calculate_weight(
        self,
        entity_name: str,
        entity_type: str,
        session_id: str = None,
        frequency: int = 1,
        first_seen: datetime = None,
        last_seen: datetime = None
    ) -> float:
        """
        计算实体权重
        
        Args:
            entity_name: 实体名称
            entity_type: 实体类型
            session_id: 会话ID
            frequency: 出现频次
            first_seen: 首次出现时间
            last_seen: 最后出现时间
            
        Returns:
            权重分数 [0, 1]
        """
        now = datetime.now()
        first_seen = first_seen or now
        last_seen = last_seen or now
        
        # 1. 基础类型权重
        base_weight = self.config.type_weights.get(entity_type, 0.5)
        
        # 2. 时间衰减权重
        hours_since_last = (now - last_seen).total_seconds() / 3600
        time_weight = math.exp(-hours_since_last / self.config.time_decay_hours)
        
        # 3. 频率权重
        frequency_bonus = min(
            frequency * self.config.frequency_factor,
            self.config.max_frequency_bonus
        )
        frequency_weight = 1.0 + frequency_bonus
        
        # 4. 用户偏好权重
        preference_weight = 1.0
        if session_id and session_id in self._user_preferences:
            pref_score = self._user_preferences[session_id].get(entity_name, 0.0)
            preference_weight = 1.0 + (pref_score * self.config.preference_factor)
        
        # 5. 上下文相关性权重
        context_weight = 1.0
        if session_id and entity_name in self._context_entities.get(session_id, set()):
            context_weight = 1.0 + self.config.context_factor
        
        # 综合权重
        final_weight = (
            base_weight *
            time_weight *
            frequency_weight *
            preference_weight *
            context_weight
        )
        
        # 归一化到 [0, 1]
        return min(max(final_weight, 0.0), 1.0)
    
    def update_from_entity_index(self, session_id: str) -> None:
        """从实体索引更新权重缓存"""
        if not self.entity_index:
            return
        
        try:
            # 获取会话中的实体
            session_entities = self.entity_index.get_session_entities(session_id)
            
            for entity_type, entity_names in session_entities.items():
                for entity_name in entity_names:
                    entity = self.entity_index.get_entity(entity_type, entity_name)
                    if entity:
                        weight = self.calculate_weight(
                            entity_name=entity_name,
                            entity_type=entity_type,
                            session_id=session_id,
                            frequency=entity.frequency,
                            first_seen=entity.first_seen,
                            last_seen=entity.last_seen
                        )
                        
                        self._weight_cache[session_id][entity_name] = WeightedEntity(
                            name=entity_name,
                            entity_type=entity_type,
                            weight=weight,
                            frequency=entity.frequency,
                            first_seen=entity.first_seen,
                            last_seen=entity.last_seen,
                            user_preference=self._user_preferences.get(session_id, {}).get(entity_name, 0.0),
                            context_relevance=1.0 if entity_name in self._context_entities.get(session_id, set()) else 0.0
                        )
            
            logger.debug(f"权重缓存更新: {session_id}, {len(self._weight_cache[session_id])} 个实体")
            
        except Exception as e:
            logger.warning(f"从实体索引更新权重失败: {e}")
    
    def update_context(self, session_id: str, current_entities: List[str]) -> None:
        """
        更新当前上下文实体
        
        Args:
            session_id: 会话ID
            current_entities: 当前上下文中的实体名称列表
        """
        self._context_entities[session_id] = set(current_entities)
    
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
        if session_id not in self._user_preferences:
            self._user_preferences[session_id] = {}
        
        current = self._user_preferences[session_id].get(entity_name, 0.0)
        new_preference = max(-1.0, min(1.0, current + preference_delta))
        self._user_preferences[session_id][entity_name] = new_preference
        
        # 更新权重缓存
        if session_id in self._weight_cache and entity_name in self._weight_cache[session_id]:
            self._weight_cache[session_id][entity_name].user_preference = new_preference
    
    def get_weighted_entities(
        self,
        session_id: str,
        entity_type: str = None,
        top_k: int = 20,
        min_weight: float = 0.1
    ) -> List[WeightedEntity]:
        """
        获取按权重排序的实体列表
        
        Args:
            session_id: 会话ID
            entity_type: 实体类型过滤（可选）
            top_k: 返回数量
            min_weight: 最小权重阈值
            
        Returns:
            按权重排序的实体列表
        """
        # 确保权重缓存是最新的
        if session_id not in self._weight_cache:
            self.update_from_entity_index(session_id)
        
        entities = list(self._weight_cache.get(session_id, {}).values())
        
        # 按类型过滤
        if entity_type:
            entities = [e for e in entities if e.entity_type == entity_type]
        
        # 按权重过滤
        entities = [e for e in entities if e.weight >= min_weight]
        
        # 按权重排序
        entities.sort(key=lambda x: x.weight, reverse=True)
        
        return entities[:top_k]
    
    def get_critical_entities(
        self,
        session_id: str,
        threshold: float = 0.7
    ) -> List[WeightedEntity]:
        """
        获取关键实体（高权重实体）
        
        Args:
            session_id: 会话ID
            threshold: 权重阈值
            
        Returns:
            关键实体列表
        """
        return self.get_weighted_entities(
            session_id=session_id,
            top_k=50,
            min_weight=threshold
        )
    
    def should_preserve(
        self,
        session_id: str,
        entity_name: str,
        entity_type: str,
        threshold: float = 0.5
    ) -> bool:
        """
        判断实体是否应该保留
        
        Args:
            session_id: 会话ID
            entity_name: 实体名称
            entity_type: 实体类型
            threshold: 保留阈值
            
        Returns:
            是否应该保留
        """
        weight = self.calculate_weight(
            entity_name=entity_name,
            entity_type=entity_type,
            session_id=session_id
        )
        return weight >= threshold
    
    def get_preservation_score(
        self,
        session_id: str,
        entities: List[Dict[str, str]]
    ) -> float:
        """
        计算实体集合的保留分数
        
        Args:
            session_id: 会话ID
            entities: 实体列表 [{"name": "...", "type": "..."}]
            
        Returns:
            保留分数 [0, 1]
        """
        if not entities:
            return 0.0
        
        total_weight = 0.0
        for entity in entities:
            weight = self.calculate_weight(
                entity_name=entity.get("name", ""),
                entity_type=entity.get("type", ""),
                session_id=session_id
            )
            total_weight += weight
        
        return total_weight / len(entities)
    
    def clear_session(self, session_id: str) -> None:
        """清除会话数据"""
        if session_id in self._user_preferences:
            del self._user_preferences[session_id]
        if session_id in self._context_entities:
            del self._context_entities[session_id]
        if session_id in self._weight_cache:
            del self._weight_cache[session_id]
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_sessions = len(self._weight_cache)
        total_entities = sum(len(entities) for entities in self._weight_cache.values())
        
        # 计算平均权重
        all_weights = []
        for entities in self._weight_cache.values():
            all_weights.extend([e.weight for e in entities.values()])
        
        avg_weight = sum(all_weights) / len(all_weights) if all_weights else 0.0
        
        return {
            "total_sessions": total_sessions,
            "total_entities": total_entities,
            "average_weight": avg_weight,
            "type_weights": self.config.type_weights
        }


# 全局单例
_info_weight_system: Optional[InfoWeightSystem] = None


def get_info_weight_system(
    entity_index=None,
    config: WeightConfig = None
) -> InfoWeightSystem:
    """获取关键信息权重系统单例"""
    global _info_weight_system
    
    if _info_weight_system is None:
        _info_weight_system = InfoWeightSystem(entity_index, config)
    
    return _info_weight_system


def reset_info_weight_system():
    """重置关键信息权重系统单例"""
    global _info_weight_system
    _info_weight_system = None
