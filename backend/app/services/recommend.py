import json
import httpx
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import and_, func as sql_func
from typing import List
from app.models.recommend import DailyRecommendation
from app.models.merchant import Merchant
from app.models.attraction import Attraction
from app.models.favorite import UserFavorite
from app.schemas.recommend import RecommendationResponse, RecommendationFeedback
from app.redis_client import get_redis
from app.config import settings

logger = logging.getLogger(__name__)


class RecommendService:
    """推荐服务"""
    
    def __init__(self, db: Session):
        self.db = db
        self.redis = get_redis()
    
    def get_today_recommendations(self, user_id: int, latitude: float, longitude: float) -> List[RecommendationResponse]:
        """获取今日推荐"""
        today = date.today()
        
        # 检查是否已有今日推荐
        existing = self.db.query(DailyRecommendation).filter(
            and_(
                DailyRecommendation.user_id == user_id,
                sql_func.date(DailyRecommendation.created_at) == today
            )
        ).all()
        
        if existing:
            return [self._to_response(rec) for rec in existing]
        
        # 没有今日推荐，生成新的
        recommendations = self._generate_recommendations(user_id, latitude, longitude)
        
        # 保存到数据库
        saved_recs = []
        for rec_data in recommendations[:10]:  # 最多保存10条
            rec = DailyRecommendation(
                user_id=user_id,
                recommend_type=rec_data["recommend_type"],
                recommend_id=rec_data["recommend_id"],
                recommend_reason=rec_data["recommend_reason"],
                weather_info=rec_data.get("weather_info"),
                score=Decimal(str(rec_data.get("score", 0)))
            )
            self.db.add(rec)
            saved_recs.append(rec)
        
        try:
            self.db.commit()
            for rec in saved_recs:
                self.db.refresh(rec)
            return [self._to_response(rec) for rec in saved_recs]
        except Exception as e:
            logger.error(f"保存推荐失败: {e}")
            self.db.rollback()
            return []
    
    def submit_feedback(self, user_id: int, feedback_data: RecommendationFeedback) -> None:
        """提交推荐反馈"""
        rec = self.db.query(DailyRecommendation).filter(
            and_(
                DailyRecommendation.id == feedback_data.recommendation_id,
                DailyRecommendation.user_id == user_id
            )
        ).first()
        
        if not rec:
            raise ValueError("推荐记录不存在")
        
        # 更新反馈
        if feedback_data.feedback == 1:
            rec.feedback = 1
            rec.is_clicked = True
        elif feedback_data.feedback == -1:
            rec.feedback = -1
        else:
            rec.feedback = 0
        
        self.db.commit()
    
    def refresh_recommendations(self, user_id: int, latitude: float, longitude: float) -> List[RecommendationResponse]:
        """刷新推荐内容"""
        today = date.today()
        
        # 删除旧的今日推荐
        self.db.query(DailyRecommendation).filter(
            and_(
                DailyRecommendation.user_id == user_id,
                sql_func.date(DailyRecommendation.created_at) == today
            )
        ).delete()
        self.db.commit()
        
        # 生成新的推荐
        return self.get_today_recommendations(user_id, latitude, longitude)
    
    def _generate_recommendations(self, user_id: int, latitude: float, longitude: float) -> List[dict]:
        """生成推荐"""
        recommendations = []
        
        # 1. 获取天气信息
        weather_info = self._get_weather_info(latitude, longitude)
        
        # 2. 获取用户偏好
        preferences = self._get_user_preferences(user_id)
        
        # 3. 获取附近商家和景点
        lat_range = 0.05  # 约5km
        lng_range = 0.05
        
        nearby_merchants = self.db.query(Merchant).filter(
            and_(
                Merchant.status == 1,
                Merchant.latitude.between(latitude - lat_range, latitude + lat_range),
                Merchant.longitude.between(longitude - lng_range, longitude + lng_range)
            )
        ).order_by(Merchant.rating.desc()).limit(20).all()
        
        nearby_attractions = self.db.query(Attraction).filter(
            and_(
                Attraction.status == 1,
                Attraction.latitude.between(latitude - lat_range, latitude + lat_range),
                Attraction.longitude.between(longitude - lng_range, longitude + lng_range)
            )
        ).order_by(Attraction.rating.desc()).limit(20).all()
        
        # 4. 生成推荐理由并打分
        for merchant in nearby_merchants[:5]:
            reason = self._generate_merchant_reason(merchant, weather_info, preferences)
            score = self._calculate_score(merchant, preferences, "merchant")
            recommendations.append({
                "recommend_type": "merchant",
                "recommend_id": merchant.id,
                "recommend_reason": reason,
                "weather_info": weather_info,
                "score": score
            })
        
        for attraction in nearby_attractions[:5]:
            reason = self._generate_attraction_reason(attraction, weather_info, preferences)
            score = self._calculate_score(attraction, preferences, "attraction")
            recommendations.append({
                "recommend_type": "attraction",
                "recommend_id": attraction.id,
                "recommend_reason": reason,
                "weather_info": weather_info,
                "score": score
            })
        
        # 按分数排序
        recommendations.sort(key=lambda x: x["score"], reverse=True)
        
        return recommendations
    
    def _get_weather_info(self, latitude: float, longitude: float) -> dict:
        """获取天气信息（缓存优先策略，复用 map.py 的 Redis key weather:current:{adcode}）"""
        api_key = settings.AMAP_API_KEY
        if not api_key:
            logger.warning("高德地图API Key未配置，跳过天气查询")
            return {"weather": "未知", "temperature": "未知", "description": "未知", "wind": "", "humidity": ""}
        
        try:
            # 1. 通过经纬度获取城市编码（adcode）
            geo_url = "https://restapi.amap.com/v3/geocode/regeo"
            geo_params = {
                "key": api_key,
                "location": f"{longitude},{latitude}",
                "output": "json"
            }
            
            with httpx.Client(timeout=10) as client:
                geo_response = client.get(geo_url, params=geo_params)
                geo_data = geo_response.json()
            
            adcode = ""
            if geo_data.get("status") == "1":
                adcode = geo_data.get("regeocode", {}).get("addressComponent", {}).get("adcode", "")
            
            if not adcode:
                return {"weather": "未知", "temperature": "未知", "description": "未知", "wind": "", "humidity": ""}

            # 归一化为市级adcode（如 440604 → 440600），避免区县级冗余缓存
            city_adcode = adcode if (len(adcode) >= 4 and adcode[-2:] == "00") else adcode[:4] + "00"

            # 2. 尝试从Redis读取缓存（与 map.py weather_current 共用 key）
            cache_key = f"weather:current:{city_adcode}"
            cached = self.redis.get(cache_key)
            if cached:
                try:
                    data = json.loads(cached)
                    wind_dir = data.get("winddirection", "")
                    wind_power = data.get("windpower", "")
                    weather = data.get("weather", "未知")
                    return {
                        "weather": weather,
                        "temperature": data.get("temperature", "未知"),
                        "description": weather,
                        "winddirection": wind_dir,
                        "windpower": wind_power,
                        "wind": f"{wind_dir}风 {wind_power}级" if wind_dir else "",
                        "humidity": data.get("humidity", ""),
                        "city": data.get("city", ""),
                        "reporttime": data.get("reporttime", "")
                    }
                except Exception:
                    pass  # 缓存解析失败，回退到API调用

            # 3. 缓存未命中，调用高德天气API
            weather_url = "https://restapi.amap.com/v3/weather/weatherInfo"
            weather_params = {
                "key": api_key,
                "city": adcode,
                "extensions": "base",
                "output": "json"
            }
            
            with httpx.Client(timeout=10) as client:
                weather_response = client.get(weather_url, params=weather_params)
                weather_data = weather_response.json()
            
            if weather_data.get("status") == "1" and weather_data.get("lives"):
                live = weather_data["lives"][0]
                weather = live.get("weather", "未知")
                wind_dir = live.get("winddirection", "")
                wind_power = live.get("windpower", "")
                result = {
                    "weather": weather,
                    "temperature": live.get("temperature", "未知"),
                    "description": weather,
                    "winddirection": wind_dir,
                    "windpower": wind_power,
                    "wind": f"{wind_dir}风 {wind_power}级" if wind_dir else "",
                    "humidity": live.get("humidity", ""),
                    "city": live.get("city", ""),
                    "reporttime": live.get("reporttime", "")
                }

                # 4. 写入缓存（与 map.py 同格式，确保两侧互通，使用归一化市级adcode）
                cache_payload = {
                    "city": live.get("city", ""),
                    "adcode": city_adcode,
                    "province": live.get("province", ""),
                    "weather": weather,
                    "temperature": live.get("temperature", ""),
                    "humidity": live.get("humidity", ""),
                    "winddirection": wind_dir,
                    "windpower": wind_power,
                    "reporttime": live.get("reporttime", ""),
                    "type": "current"
                }
                now = datetime.now()
                midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                ttl = int((midnight - now).total_seconds())
                self.redis.setex(cache_key, ttl, json.dumps(cache_payload, ensure_ascii=False))

                return result
        except Exception as e:
            logger.error(f"高德天气查询失败: {e}")
        
        return {"weather": "未知", "temperature": "未知", "description": "未知", "wind": "", "humidity": ""}
    
    def _get_user_preferences(self, user_id: int) -> dict:
        """获取用户偏好（基于历史收藏和反馈）"""
        preferences = {
            "favorite_categories": [],
            "preferred_price_range": None,
            "liked_types": []
        }
        
        try:
            # 分析用户收藏的商家类型
            favorites = self.db.query(UserFavorite).filter(
                UserFavorite.user_id == user_id
            ).all()
            
            category_counts = {}
            for fav in favorites:
                if fav.merchant_id:
                    merchant = self.db.query(Merchant).filter(Merchant.id == fav.merchant_id).first()
                    if merchant and merchant.category:
                        category_counts[merchant.category] = category_counts.get(merchant.category, 0) + 1
                if fav.attraction_id:
                    attraction = self.db.query(Attraction).filter(Attraction.id == fav.attraction_id).first()
                    if attraction and attraction.category:
                        category_counts[attraction.category] = category_counts.get(attraction.category, 0) + 1
            
            # 按收藏次数排序
            sorted_categories = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)
            preferences["favorite_categories"] = [cat for cat, _ in sorted_categories[:5]]
            
            # 分析用户反馈
            positive_recs = self.db.query(DailyRecommendation).filter(
                and_(
                    DailyRecommendation.user_id == user_id,
                    DailyRecommendation.feedback == 1
                )
            ).all()
            
            for rec in positive_recs:
                if rec.recommend_type == "merchant" and rec.recommend_id:
                    merchant = self.db.query(Merchant).filter(Merchant.id == rec.recommend_id).first()
                    if merchant and merchant.category:
                        liked = preferences.get("liked_types") or []
                        liked.append(merchant.category)
                        preferences["liked_types"] = liked
            
            preferences["liked_types"] = list(set(preferences.get("liked_types") or []))[:5]
            
        except Exception as e:
            logger.error(f"获取用户偏好失败: {e}")
        
        return preferences
    
    def _generate_merchant_reason(self, merchant: Merchant, weather_info: dict, preferences: dict) -> str:
        """生成商家推荐理由"""
        reasons = []
        
        weather = weather_info.get("weather", "")
        temperature = weather_info.get("temperature", "")
        
        # 根据天气推荐
        if "雨" in weather:
            reasons.append(f"今天有雨，推荐室内美食「{merchant.name}」")
        elif temperature and temperature.isdigit() and int(temperature) > 30:
            reasons.append(f"今天天气炎热，推荐清凉美食「{merchant.name}」")
        elif temperature and temperature.isdigit() and int(temperature) < 10:
            reasons.append(f"今天天气寒冷，推荐暖身美食「{merchant.name}」")
        
        # 根据评分推荐
        if merchant.rating and float(merchant.rating) >= 4.5:
            reasons.append(f"高评分商家（{merchant.rating}分），品质有保障")
        
        # 根据用户偏好推荐
        if merchant.category in preferences.get("favorite_categories", []):
            reasons.append(f"您常去的{merchant.category}类餐厅")
        
        # 如果没有特别理由，使用通用理由
        if not reasons:
            category = merchant.category or "美食"
            reasons.append(f"附近热门{category}推荐")
        
        return reasons[0]
    
    def _generate_attraction_reason(self, attraction: Attraction, weather_info: dict, preferences: dict) -> str:
        """生成景点推荐理由"""
        reasons = []
        
        weather = weather_info.get("weather", "")
        
        # 根据天气推荐
        if "晴" in weather:
            reasons.append(f"今天天气晴朗，推荐户外景点「{attraction.name}」")
        elif "雨" in weather:
            if attraction.category in ["博物馆", "商场", "美术馆", "展览馆", "图书馆"]:
                reasons.append(f"今天有雨，推荐室内景点「{attraction.name}」")
        
        # 根据评分推荐
        if attraction.rating and float(attraction.rating) >= 4.5:
            reasons.append(f"高评分景点（{attraction.rating}分），值得一去")
        
        # 根据门票价格推荐
        if attraction.ticket_price and float(attraction.ticket_price) == 0:
            reasons.append("免费景点，随时出发")
        
        # 根据用户偏好
        if attraction.category in preferences.get("favorite_categories", []):
            reasons.append(f"您常去的{attraction.category}类景点")
        
        if not reasons:
            reasons.append(f"附近热门景点推荐")
        
        return reasons[0]
    
    def _calculate_score(self, item, preferences: dict, item_type: str) -> float:
        """计算推荐分数"""
        score = 50.0  # 基础分
        
        # 评分加权
        rating = float(item.rating) if item.rating else 0
        score += rating * 8  # 最高40分
        
        # 用户偏好加权
        category = item.category or ""
        if category in preferences.get("favorite_categories", []):
            score += 15
        if category in preferences.get("liked_types", []):
            score += 10
        
        # 价格因素（商家）
        if item_type == "merchant" and hasattr(item, 'avg_price') and item.avg_price:
            price = float(item.avg_price)
            if 20 <= price <= 100:
                score += 5  # 适中价格加分
        
        # 免费景点加分
        if item_type == "attraction" and hasattr(item, 'ticket_price'):
            if item.ticket_price and float(item.ticket_price) == 0:
                score += 5
        
        return round(score, 2)
    
    def _to_response(self, rec: DailyRecommendation) -> RecommendationResponse:
        """转换为响应模型"""
        return RecommendationResponse(
            id=rec.id,
            user_id=rec.user_id,
            recommend_type=rec.recommend_type,
            recommend_id=rec.recommend_id,
            recommend_reason=rec.recommend_reason,
            weather_info=rec.weather_info,
            score=rec.score,
            is_clicked=rec.is_clicked,
            feedback=rec.feedback,
            created_at=rec.created_at
        )
