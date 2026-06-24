"""
增量式实体索引模块

设计原则：
1. 增量更新：避免全量扫描消息
2. 内存索引：快速查询
3. 时间序列：支持按时间查询
4. 实体关联：建立实体关系图
"""
import logging
import re
from typing import Dict, List, Optional, Any, Set, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class Entity:
    """实体"""
    name: str
    entity_type: str  # location, restaurant, cuisine, price, intent
    first_seen: datetime
    last_seen: datetime
    frequency: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EntityOccurrence:
    """实体出现记录"""
    entity_name: str
    entity_type: str
    message_id: str
    session_id: str
    timestamp: datetime
    context: str  # 实体出现的上下文


class EntityIndex:
    """
    增量式实体索引
    
    职责：
    1. 增量更新实体索引
    2. 提供快速实体查询
    3. 建立实体关系图
    4. 支持时间序列查询
    """
    
    def __init__(self, jieba_instance=None):
        """
        初始化实体索引
        
        Args:
            jieba_instance: jieba分词器实例
        """
        self.jieba = jieba_instance
        
        # 实体索引：entity_type -> entity_name -> Entity
        self.entities: Dict[str, Dict[str, Entity]] = defaultdict(dict)
        
        # 实体出现记录：entity_name -> [EntityOccurrence]
        self.occurrences: Dict[str, List[EntityOccurrence]] = defaultdict(list)
        
        # 会话实体：session_id -> Set[entity_name]
        self.session_entities: Dict[str, Set[str]] = defaultdict(set)
        
        # 实体关系图：entity_name -> Set[related_entity_name]
        self.entity_relations: Dict[str, Set[str]] = defaultdict(set)
        
        # 时间索引：date -> Set[entity_name]
        self.time_index: Dict[str, Set[str]] = defaultdict(set)
        
        # 实体类型配置
        self.entity_patterns = {
            "location": {
                "suffixes": ['路', '街', '区', '市', '省', '镇', '村', '小区', '大厦', '广场', '中心'],
                "regex": r'[\u4e00-\u9fff]{2,6}(?:路|街|区|市|省|镇|村|小区|大厦|广场|中心)'
            },
            "restaurant": {
                "suffixes": ['店', '厅', '馆', '屋', '坊', '楼', '阁', '居', '苑', '堂', '斋', '庄'],
                "regex": r'[\u4e00-\u9fff]{2,6}(?:店|厅|馆|屋|坊|楼|阁|居|苑|堂|斋|庄)'
            },
            "cuisine": {
                "keywords": ['川菜', '湘菜', '粤菜', '鲁菜', '苏菜', '浙菜', '闽菜', '徽菜',
                           '火锅', '烧烤', '日料', '韩餐', '西餐', '中餐', '快餐', '甜品', '咖啡'],
                "regex": r'(?:川菜|湘菜|粤菜|鲁菜|苏菜|浙菜|闽菜|徽菜|火锅|烧烤|日料|韩餐|西餐|中餐|快餐|甜品|咖啡)'
            },
            "price": {
                "patterns": [
                    r'人均\s*(\d+)',
                    r'(\d+)\s*[-~到]\s*(\d+)\s*元',
                    r'(\d+)元'
                ]
            }
        }
    
    def add_message(
        self,
        message: Dict[str, Any],
        session_id: str,
        message_id: str = None
    ) -> List[Entity]:
        """
        增量添加消息中的实体
        
        Args:
            message: 消息内容
            session_id: 会话ID
            message_id: 消息ID
            
        Returns:
            提取的实体列表
        """
        content = message.get("content", "")
        if not content:
            return []
        
        timestamp = datetime.fromisoformat(message.get("timestamp", datetime.now().isoformat()))
        message_id = message_id or f"msg_{timestamp.timestamp()}"
        
        # 提取实体
        entities = self._extract_entities(content)
        
        # 更新索引
        for entity in entities:
            self._update_entity_index(entity, session_id, message_id, timestamp, content)
        
        # 更新会话实体
        for entity in entities:
            self.session_entities[session_id].add(entity.name)
        
        # 建立实体关系
        self._build_entity_relations(entities)
        
        return entities
    
    def _extract_entities(self, content: str) -> List[Entity]:
        """提取实体"""
        entities = []
        timestamp = datetime.now()
        
        # 使用jieba分词
        if self.jieba:
            words = list(self.jieba.cut(content))
            entities.extend(self._extract_from_words(words, timestamp))
        else:
            # 降级到正则表达式
            entities.extend(self._extract_from_regex(content, timestamp))
        
        # 提取价格实体
        entities.extend(self._extract_prices(content, timestamp))
        
        return entities
    
    def _extract_from_words(self, words: List[str], timestamp: datetime) -> List[Entity]:
        """从分词结果提取实体"""
        entities = []
        
        for i, word in enumerate(words):
            # 检查每个实体类型
            for entity_type, config in self.entity_patterns.items():
                if entity_type == "price":
                    continue  # 价格单独处理
                
                if entity_type == "cuisine":
                    # 菜系关键词匹配
                    if word in config.get("keywords", []):
                        entities.append(Entity(
                            name=word,
                            entity_type=entity_type,
                            first_seen=timestamp,
                            last_seen=timestamp
                        ))
                else:
                    # 后缀匹配
                    suffixes = config.get("suffixes", [])
                    if any(word.endswith(suffix) for suffix in suffixes):
                        # 尝试组合前一个词
                        name = word
                        if i > 0 and len(words[i-1]) >= 2:
                            name = words[i-1] + word
                        
                        entities.append(Entity(
                            name=name,
                            entity_type=entity_type,
                            first_seen=timestamp,
                            last_seen=timestamp
                        ))
        
        return entities
    
    def _extract_from_regex(self, content: str, timestamp: datetime) -> List[Entity]:
        """使用正则表达式提取实体"""
        entities = []
        
        for entity_type, config in self.entity_patterns.items():
            if entity_type == "price":
                continue
            
            regex = config.get("regex")
            if regex:
                matches = re.findall(regex, content)
                for match in matches[:5]:  # 限制每个类型最多5个
                    entities.append(Entity(
                        name=match,
                        entity_type=entity_type,
                        first_seen=timestamp,
                        last_seen=timestamp
                    ))
        
        return entities
    
    def _extract_prices(self, content: str, timestamp: datetime) -> List[Entity]:
        """提取价格实体"""
        entities = []
        
        # 人均XX元
        price_matches = re.findall(r'人均\s*(\d+)', content)
        for p in price_matches:
            entities.append(Entity(
                name=f"{p}元",
                entity_type="price",
                first_seen=timestamp,
                last_seen=timestamp
            ))
        
        # XX-XX元
        range_matches = re.findall(r'(\d+)\s*[-~到]\s*(\d+)\s*元', content)
        for low, high in range_matches:
            entities.append(Entity(
                name=f"{low}-{high}元",
                entity_type="price",
                first_seen=timestamp,
                last_seen=timestamp
            ))
        
        return entities
    
    def _update_entity_index(
        self,
        entity: Entity,
        session_id: str,
        message_id: str,
        timestamp: datetime,
        context: str
    ):
        """更新实体索引"""
        entity_type = entity.entity_type
        entity_name = entity.name
        
        # 更新或创建实体
        if entity_name in self.entities[entity_type]:
            existing = self.entities[entity_type][entity_name]
            existing.frequency += 1
            existing.last_seen = timestamp
        else:
            self.entities[entity_type][entity_name] = entity
        
        # 添加出现记录
        occurrence = EntityOccurrence(
            entity_name=entity_name,
            entity_type=entity_type,
            message_id=message_id,
            session_id=session_id,
            timestamp=timestamp,
            context=context[:100]  # 只保留前100个字符
        )
        self.occurrences[entity_name].append(occurrence)
        
        # 更新时间索引
        date_key = timestamp.strftime("%Y-%m-%d")
        self.time_index[date_key].add(entity_name)
    
    def _build_entity_relations(self, entities: List[Entity]):
        """建立实体关系"""
        # 同一消息中的实体相互关联
        entity_names = [e.name for e in entities]
        for i, name1 in enumerate(entity_names):
            for name2 in entity_names[i+1:]:
                self.entity_relations[name1].add(name2)
                self.entity_relations[name2].add(name1)
    
    def get_entity(self, entity_type: str, entity_name: str) -> Optional[Entity]:
        """获取实体"""
        return self.entities.get(entity_type, {}).get(entity_name)
    
    def get_entities_by_type(self, entity_type: str) -> List[Entity]:
        """获取指定类型的所有实体"""
        return list(self.entities.get(entity_type, {}).values())
    
    def get_session_entities(self, session_id: str) -> Dict[str, List[str]]:
        """获取会话中的所有实体"""
        result = defaultdict(list)
        entity_names = self.session_entities.get(session_id, set())
        
        for entity_name in entity_names:
            for entity_type, entities in self.entities.items():
                if entity_name in entities:
                    result[entity_type].append(entity_name)
        
        return dict(result)
    
    def get_related_entities(self, entity_name: str) -> Set[str]:
        """获取相关实体"""
        return self.entity_relations.get(entity_name, set())
    
    def get_entities_by_time(
        self,
        start_date: datetime,
        end_date: datetime = None
    ) -> List[Entity]:
        """按时间范围获取实体"""
        if end_date is None:
            end_date = datetime.now()
        
        entity_names = set()
        current_date = start_date
        
        while current_date <= end_date:
            date_key = current_date.strftime("%Y-%m-%d")
            entity_names.update(self.time_index.get(date_key, set()))
            current_date += timedelta(days=1)
        
        entities = []
        for entity_name in entity_names:
            for entity_type, type_entities in self.entities.items():
                if entity_name in type_entities:
                    entities.append(type_entities[entity_name])
        
        return entities
    
    def get_frequent_entities(
        self,
        entity_type: str = None,
        top_k: int = 10,
        min_frequency: int = 2
    ) -> List[Entity]:
        """获取高频实体"""
        all_entities = []
        
        if entity_type:
            all_entities = list(self.entities.get(entity_type, {}).values())
        else:
            for type_entities in self.entities.values():
                all_entities.extend(type_entities.values())
        
        # 过滤低频实体
        filtered = [e for e in all_entities if e.frequency >= min_frequency]
        
        # 按频率排序
        filtered.sort(key=lambda x: x.frequency, reverse=True)
        
        return filtered[:top_k]
    
    def search_entities(
        self,
        query: str,
        entity_type: str = None,
        top_k: int = 10
    ) -> List[Tuple[Entity, float]]:
        """搜索实体"""
        results = []
        
        search_types = [entity_type] if entity_type else list(self.entities.keys())
        
        for etype in search_types:
            for name, entity in self.entities.get(etype, {}).items():
                # 计算相似度（简单实现）
                similarity = self._calculate_similarity(query, name)
                if similarity > 0.3:  # 相似度阈值
                    results.append((entity, similarity))
        
        # 按相似度排序
        results.sort(key=lambda x: x[1], reverse=True)
        
        return results[:top_k]
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """计算文本相似度（简单实现）"""
        if not text1 or not text2:
            return 0.0
        
        # 字符重叠度
        common_chars = set(text1) & set(text2)
        total_chars = set(text1) | set(text2)
        
        if not total_chars:
            return 0.0
        
        return len(common_chars) / len(total_chars)
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = {
            "total_entities": 0,
            "by_type": {},
            "total_occurrences": 0,
            "total_sessions": len(self.session_entities),
            "total_relations": 0
        }
        
        for entity_type, entities in self.entities.items():
            stats["by_type"][entity_type] = len(entities)
            stats["total_entities"] += len(entities)
        
        stats["total_occurrences"] = sum(len(occ) for occ in self.occurrences.values())
        stats["total_relations"] = sum(len(rels) for rels in self.entity_relations.values())
        
        return stats
    
    def clear_session(self, session_id: str):
        """清除会话数据"""
        entity_names = self.session_entities.get(session_id, set())
        
        # 减少实体频率
        for entity_name in entity_names:
            for entity_type, entities in self.entities.items():
                if entity_name in entities:
                    entity = entities[entity_name]
                    entity.frequency = max(0, entity.frequency - 1)
                    if entity.frequency == 0:
                        del entities[entity_name]
        
        # 清除出现记录
        for entity_name in entity_names:
            if entity_name in self.occurrences:
                self.occurrences[entity_name] = [
                    occ for occ in self.occurrences[entity_name]
                    if occ.session_id != session_id
                ]
        
        # 清除会话实体
        if session_id in self.session_entities:
            del self.session_entities[session_id]
    
    def clear(self):
        """清除所有数据"""
        self.entities.clear()
        self.occurrences.clear()
        self.session_entities.clear()
        self.entity_relations.clear()
        self.time_index.clear()


# 全局单例
_entity_index: Optional[EntityIndex] = None


def get_entity_index(jieba_instance=None) -> EntityIndex:
    """获取实体索引单例"""
    global _entity_index
    
    if _entity_index is None:
        _entity_index = EntityIndex(jieba_instance)
    
    return _entity_index


def reset_entity_index():
    """重置实体索引单例"""
    global _entity_index
    _entity_index = None