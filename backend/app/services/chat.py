import json
import uuid
import re
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc
from typing import List, Optional, Dict, Any
from app.models.chat import ChatHistory, ChatContext, IntentLog
from app.models.merchant import Merchant
from app.models.attraction import Attraction
from app.schemas.chat import ChatMessage, ChatResponse, ChatHistoryResponse
from app.redis_client import get_redis
from app.config import settings

logger = logging.getLogger(__name__)

# 意图识别规则
INTENT_PATTERNS = {
    "search_food": [
        r"(找|搜|查|推荐|附近|周边).*(吃|饭|餐|食|美食|餐厅|饭店|火锅|烧烤|日料|小吃|夜宵|早餐|午餐|晚餐|下午茶)",
        r"(吃什么|去哪吃|有.*吃的|吃饭的地方)",
        r"(饿了|肚子饿|想吃|嘴馋)",
    ],
    "search_attraction": [
        r"(找|搜|查|推荐|附近|周边).*(景点|景区|公园|博物馆|商场|游乐|玩|逛|去处|打卡|旅游)",
        r"(去哪玩|有什么玩的|好玩的地方|周末去哪)",
        r"(无聊|消遣|打发时间|出去走走)",
    ],
    "search_food_category": [
        r"(火锅|烧烤|日料|韩料|西餐|中餐|快餐|甜品|咖啡|奶茶|海鲜|自助|烤鱼|小龙虾|串串)",
    ],
    "search_attraction_category": [
        r"(公园|博物馆|商场|寺庙|古迹|游乐场|动物园|植物园|美术馆|展览馆|图书馆|电影院|KTV)",
    ],
    "greeting": [
        r"^(你好|嗨|hi|hello|hey|您好|早上好|中午好|下午好|晚上好|在吗)",
    ],
    "thanks": [
        r"(谢谢|感谢|多谢|谢了|thanks|thank you|thx)",
    ],
    "goodbye": [
        r"(再见|拜拜|bye|goodbye|回见|下次见|晚安)",
    ],
    "help": [
        r"(帮助|怎么用|使用说明|功能|你能做什么|你会什么|帮我)",
    ],
}

# 实体提取规则
ENTITY_PATTERNS = {
    "food_category": {
        "火锅": ["火锅", "涮锅"],
        "烧烤": ["烧烤", "烤肉", "BBQ"],
        "日料": ["日料", "日本料理", "寿司", "刺身"],
        "韩料": ["韩料", "韩国料理", "炸鸡"],
        "西餐": ["西餐", "牛排", "披萨", "意面"],
        "中餐": ["中餐", "炒菜", "家常菜"],
        "快餐": ["快餐", "麦当劳", "肯德基", "汉堡"],
        "甜品": ["甜品", "蛋糕", "冰淇淋"],
        "咖啡": ["咖啡", "星巴克"],
        "奶茶": ["奶茶", "茶饮", "果茶"],
        "海鲜": ["海鲜", "鱼", "虾", "螃蟹"],
        "自助餐": ["自助", "自助餐"],
    },
    "attraction_category": {
        "公园": ["公园", "花园", "绿地"],
        "博物馆": ["博物馆", "纪念馆"],
        "商场": ["商场", "购物中心", "mall"],
        "寺庙": ["寺庙", "庙宇", "教堂"],
        "古迹": ["古迹", "遗址", "古城"],
        "游乐园": ["游乐场", "游乐园", "乐园"],
        "动物园": ["动物园"],
        "植物园": ["植物园"],
        "美术馆": ["美术馆", "画廊"],
        "展览馆": ["展览馆", "展览中心"],
    },
}

# 意图回复模板
RESPONSE_TEMPLATES = {
    "greeting": [
        "你好！我是小紫薯，可以帮你找美食、查景点。请问有什么可以帮您的？",
        "嗨！欢迎使用小紫薯。我可以帮你搜索附近的美食和景点，有什么需要帮忙的吗？",
    ],
    "thanks": [
        "不客气，很高兴能帮到您！还有其他需要吗？",
        "不用谢，随时为您服务！",
    ],
    "goodbye": [
        "再见！祝您生活愉快！",
        "拜拜，有需要随时找我哦！",
    ],
    "help": [
        "我是小紫薯，可以帮您：\n1. 搜索附近美食（如'附近有什么好吃的'）\n2. 搜索周边景点（如'附近有什么好玩的'）\n3. 按类型推荐（如'推荐火锅店'）\n\n请直接告诉我您的需求！",
    ],
    "search_food_no_result": [
        "抱歉，没有找到符合条件的美食。您可以试试换个关键词或扩大搜索范围。",
    ],
    "search_attraction_no_result": [
        "抱歉，没有找到符合条件的景点。您可以试试换个关键词或扩大搜索范围。",
    ],
    "search_food_with_result": [
        "为您找到以下美食推荐：\n{results}",
    ],
    "search_attraction_with_result": [
        "为您找到以下景点推荐：\n{results}",
    ],
    "unknown": [
        "抱歉，我暂时不太理解您的意思。您可以试试问'附近有什么好吃的'或'附近有什么好玩的'。",
        "我没有完全理解您的需求。您可以直接说'找美食'或'找景点'，我来帮您搜索。",
    ],
}


class ChatService:
    """聊天服务"""
    
    def __init__(self, db: Session):
        self.db = db
        self.redis = get_redis()
    
    def process_message(self, user_id: int, message_data: ChatMessage) -> ChatResponse:
        """处理用户消息"""
        import time
        start_time = time.time()
        
        # 获取或创建会话ID
        session_id = message_data.session_id or str(uuid.uuid4())
        
        # 1. 保存用户消息到数据库
        user_msg = ChatHistory(
            user_id=user_id,
            session_id=session_id,
            message_type="user",
            content=message_data.message,
            message_metadata=None
        )
        self.db.add(user_msg)
        self.db.commit()
        
        # 2. 提取意图和实体
        intent = self._extract_intent(message_data.message)
        entities = self._extract_entities(message_data.message)
        
        # 3. 获取对话上下文
        context = self._get_context(user_id, session_id)
        
        # 4. 根据意图调用相应服务获取结果
        recommendations = []
        response_text = ""
        
        intent_name = intent.get("intent", "unknown")
        
        if intent_name in ["search_food", "search_food_category"]:
            recommendations = self._search_food(intent_name, entities, message_data.latitude, message_data.longitude)
            if recommendations:
                results_text = self._format_food_results(recommendations)
                response_text = RESPONSE_TEMPLATES["search_food_with_result"][0].format(results=results_text)
            else:
                response_text = RESPONSE_TEMPLATES["search_food_no_result"][0]
        
        elif intent_name in ["search_attraction", "search_attraction_category"]:
            recommendations = self._search_attractions(intent_name, entities, message_data.latitude, message_data.longitude)
            if recommendations:
                results_text = self._format_attraction_results(recommendations)
                response_text = RESPONSE_TEMPLATES["search_attraction_with_result"][0].format(results=results_text)
            else:
                response_text = RESPONSE_TEMPLATES["search_attraction_no_result"][0]
        
        elif intent_name in RESPONSE_TEMPLATES:
            import random
            response_text = random.choice(RESPONSE_TEMPLATES[intent_name])
        
        else:
            import random
            response_text = random.choice(RESPONSE_TEMPLATES["unknown"])
        
        # 5. 生成对话建议
        suggestions = self._generate_suggestions(intent_name, entities)
        
        # 6. 更新对话上下文
        new_context = {
            "last_intent": intent_name,
            "last_entities": entities,
            "last_latitude": message_data.latitude,
            "last_longitude": message_data.longitude,
        }
        self._update_context(user_id, session_id, new_context)
        
        # 7. 保存AI回复到数据库
        ai_msg = ChatHistory(
            user_id=user_id,
            session_id=session_id,
            message_type="ai",
            content=response_text,
            message_metadata={
                "intent": intent_name,
                "entities": entities,
                "recommendations_count": len(recommendations)
            }
        )
        self.db.add(ai_msg)
        
        # 8. 记录意图识别日志
        elapsed_ms = int((time.time() - start_time) * 1000)
        intent_log = IntentLog(
            user_id=user_id,
            session_id=session_id,
            query=message_data.message,
            intent=intent_name,
            entities=entities,
            confidence=intent.get("confidence", 0.0),
            response_time=elapsed_ms
        )
        self.db.add(intent_log)
        self.db.commit()
        
        return ChatResponse(
            message=response_text,
            session_id=session_id,
            recommendations=recommendations,
            suggestions=suggestions,
            intent=intent_name,
            entities=entities
        )
    
    def get_history(
        self,
        user_id: int,
        session_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> List[ChatHistoryResponse]:
        """获取对话历史记录"""
        query = self.db.query(ChatHistory).filter(ChatHistory.user_id == user_id)
        
        if session_id:
            query = query.filter(ChatHistory.session_id == session_id)
        
        # 按时间倒序
        query = query.order_by(desc(ChatHistory.created_at))
        
        # 分页
        offset = (page - 1) * page_size
        records = query.offset(offset).limit(page_size).all()
        
        return [
            ChatHistoryResponse(
                id=record.id,
                user_id=record.user_id,
                session_id=record.session_id,
                message_type=record.message_type,
                content=record.content,
                message_metadata=record.message_metadata,
                created_at=record.created_at
            )
            for record in records
        ]
    
    def delete_history(self, user_id: int, session_id: str) -> None:
        """删除对话历史记录"""
        # 删除数据库中的对话历史
        deleted = self.db.query(ChatHistory).filter(
            and_(
                ChatHistory.user_id == user_id,
                ChatHistory.session_id == session_id
            )
        ).delete()
        
        # 删除意图日志
        self.db.query(IntentLog).filter(
            and_(
                IntentLog.user_id == user_id,
                IntentLog.session_id == session_id
            )
        ).delete()
        
        # 删除上下文
        self.db.query(ChatContext).filter(
            and_(
                ChatContext.user_id == user_id,
                ChatContext.session_id == session_id
            )
        ).delete()
        
        self.db.commit()
        
        # 删除Redis缓存中的上下文
        cache_key = f"chat:context:{user_id}:{session_id}"
        try:
            self.redis.delete(cache_key)
        except Exception as e:
            logger.warning(f"Redis删除失败: {e}")
    
    def _extract_intent(self, query: str) -> dict:
        """基于规则的意图识别"""
        query_lower = query.lower().strip()
        
        # 按优先级匹配意图
        for intent, patterns in INTENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    return {"intent": intent, "confidence": 0.85}
        
        # 如果匹配到食物类别关键词
        for category in ENTITY_PATTERNS.get("food_category", {}).values():
            for keyword in category:
                if keyword in query_lower:
                    return {"intent": "search_food_category", "confidence": 0.80}
        
        # 如果匹配到景点类别关键词
        for category in ENTITY_PATTERNS.get("attraction_category", {}).values():
            for keyword in category:
                if keyword in query_lower:
                    return {"intent": "search_attraction_category", "confidence": 0.80}
        
        return {"intent": "unknown", "confidence": 0.0}
    
    def _extract_entities(self, query: str) -> dict:
        """基于规则的实体提取"""
        entities = {}
        query_lower = query.lower().strip()
        
        # 提取食物类别
        for category, keywords in ENTITY_PATTERNS.get("food_category", {}).items():
            for keyword in keywords:
                if keyword in query_lower:
                    entities["food_category"] = category
                    break
            if "food_category" in entities:
                break
        
        # 提取景点类别
        for category, keywords in ENTITY_PATTERNS.get("attraction_category", {}).items():
            for keyword in keywords:
                if keyword in query_lower:
                    entities["attraction_category"] = category
                    break
            if "attraction_category" in entities:
                break
        
        # 提取价格偏好
        if re.search(r"(便宜|实惠|性价比|平价)", query_lower):
            entities["price_preference"] = "low"
        elif re.search(r"(贵|高档|豪华|高端)", query_lower):
            entities["price_preference"] = "high"
        
        return entities
    
    def _get_context(self, user_id: int, session_id: str) -> dict:
        """获取对话上下文"""
        cache_key = f"chat:context:{user_id}:{session_id}"
        
        # 从Redis获取
        try:
            cached = self.redis.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Redis读取上下文失败: {e}")
        
        # 从数据库获取最新的上下文
        contexts = self.db.query(ChatContext).filter(
            and_(
                ChatContext.user_id == user_id,
                ChatContext.session_id == session_id
            )
        ).all()
        
        context = {}
        for ctx in contexts:
            try:
                context[ctx.context_key] = json.loads(ctx.context_value)
            except (json.JSONDecodeError, TypeError):
                context[ctx.context_key] = ctx.context_value
        
        # 回写缓存
        if context:
            try:
                self.redis.set(cache_key, json.dumps(context, ensure_ascii=False), ex=3600)
            except Exception:
                pass
        
        return context
    
    def _update_context(self, user_id: int, session_id: str, context: dict) -> None:
        """更新对话上下文"""
        cache_key = f"chat:context:{user_id}:{session_id}"
        
        # 更新Redis缓存
        try:
            existing = self._get_context(user_id, session_id)
            existing.update(context)
            self.redis.set(cache_key, json.dumps(existing, ensure_ascii=False), ex=3600)
        except Exception as e:
            logger.warning(f"Redis更新上下文失败: {e}")
        
        # 更新数据库
        for key, value in context.items():
            db_ctx = self.db.query(ChatContext).filter(
                and_(
                    ChatContext.user_id == user_id,
                    ChatContext.session_id == session_id,
                    ChatContext.context_key == key
                )
            ).first()
            
            value_str = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
            expire_time = datetime.now() + timedelta(hours=2)
            
            if db_ctx:
                db_ctx.context_value = value_str
                db_ctx.expire_time = expire_time
            else:
                new_ctx = ChatContext(
                    user_id=user_id,
                    session_id=session_id,
                    context_key=key,
                    context_value=value_str,
                    expire_time=expire_time
                )
                self.db.add(new_ctx)
        
        self.db.commit()
    
    def _search_food(self, intent: str, entities: dict, latitude: Optional[float], longitude: Optional[float]) -> List[dict]:
        """搜索美食"""
        from app.services.food import FoodService
        
        if not latitude or not longitude:
            return []
        
        food_service = FoodService(self.db)
        category = entities.get("food_category")
        
        result = food_service.search_nearby(
            latitude=latitude,
            longitude=longitude,
            radius=3000,
            category=category,
            sort_by="rating",
            page_size=5
        )
        
        return [
            {
                "id": item.id,
                "name": item.name,
                "category": item.category,
                "rating": float(item.rating) if item.rating else 0,
                "avg_price": float(item.avg_price) if item.avg_price else 0,
                "address": item.address,
                "type": "merchant"
            }
            for item in result.items
        ]
    
    def _search_attractions(self, intent: str, entities: dict, latitude: Optional[float], longitude: Optional[float]) -> List[dict]:
        """搜索景点"""
        from app.services.attraction import AttractionService
        
        if not latitude or not longitude:
            return []
        
        attraction_service = AttractionService(self.db)
        category = entities.get("attraction_category")
        
        result = attraction_service.search_nearby(
            latitude=latitude,
            longitude=longitude,
            radius=3000,
            category=category,
            sort_by="rating",
            page_size=5
        )
        
        return [
            {
                "id": item.id,
                "name": item.name,
                "category": item.category,
                "rating": float(item.rating) if item.rating else 0,
                "ticket_price": float(item.ticket_price) if item.ticket_price else 0,
                "address": item.address,
                "type": "attraction"
            }
            for item in result.items
        ]
    
    def _format_food_results(self, recommendations: List[dict]) -> str:
        """格式化美食搜索结果"""
        lines = []
        for i, item in enumerate(recommendations, 1):
            price_info = f"人均¥{item['avg_price']}" if item['avg_price'] > 0 else "价格待查"
            lines.append(f"{i}. {item['name']}（{item['category']}，评分{item['rating']}，{price_info}）")
        return "\n".join(lines)
    
    def _format_attraction_results(self, recommendations: List[dict]) -> str:
        """格式化景点搜索结果"""
        lines = []
        for i, item in enumerate(recommendations, 1):
            price_info = "免费" if item['ticket_price'] == 0 else f"门票¥{item['ticket_price']}"
            lines.append(f"{i}. {item['name']}（{item['category']}，评分{item['rating']}，{price_info}）")
        return "\n".join(lines)
    
    def _generate_suggestions(self, intent: str, entities: dict) -> List[str]:
        """生成对话建议"""
        suggestions = []
        
        if intent in ["search_food", "search_food_category"]:
            suggestions = ["换个类型试试", "看看附近的景点", "查看收藏的美食"]
        elif intent in ["search_attraction", "search_attraction_category"]:
            suggestions = ["换个类型试试", "看看附近的美食", "查看收藏的景点"]
        elif intent == "greeting":
            suggestions = ["附近有什么好吃的", "附近有什么好玩的", "推荐火锅店", "找附近的公园"]
        elif intent in ["thanks", "goodbye"]:
            suggestions = []
        else:
            suggestions = ["找美食", "找景点", "附近有什么好吃的", "附近有什么好玩的"]
        
        return suggestions
