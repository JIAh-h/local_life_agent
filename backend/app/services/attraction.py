import json
import httpx
import logging
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Optional
from decimal import Decimal
from app.models.attraction import Attraction
from app.schemas.attraction import AttractionListResponse
from app.redis_client import get_redis
from app.config import settings

logger = logging.getLogger(__name__)


class AttractionService:
    """景点推荐服务"""
    
    def __init__(self, db: Session):
        self.db = db
        self.redis = get_redis()
    
    def search_nearby(
        self,
        latitude: Decimal,
        longitude: Decimal,
        radius: int = 3000,
        category: Optional[str] = None,
        sort_by: Optional[str] = None,
        tags: Optional[List[str]] = None,
        page: int = 1,
        page_size: int = 20
    ) -> AttractionListResponse:
        """搜索周边景点"""
        # 尝试从数据库查询已缓存的景点
        query = self.db.query(Attraction).filter(Attraction.status == 1)
        
        # 如果没有本地数据，调用POI API
        if query.count() == 0:
            poi_results = self._call_poi_api(latitude, longitude, radius, "景点")
            if poi_results:
                self._save_attractions_to_db(poi_results)
        
        # 重新构建查询
        query = self.db.query(Attraction).filter(Attraction.status == 1)
        
        # 按距离筛选（经纬度范围粗筛）
        lat_range = float(radius) / 111000
        lng_range = float(radius) / (111000 * abs(float(latitude) * 0.01745))
        
        query = query.filter(
            and_(
                Attraction.latitude.between(float(latitude) - lat_range, float(latitude) + lat_range),
                Attraction.longitude.between(float(longitude) - lng_range, float(longitude) + lng_range)
            )
        )
        
        # 按类型筛选
        if category:
            query = query.filter(Attraction.category == category)
        
        # 按标签筛选
        if tags:
            for tag in tags:
                query = query.filter(Attraction.tags.contains(tag))
        
        # 排序
        if sort_by == "rating":
            query = query.order_by(Attraction.rating.desc())
        elif sort_by == "price":
            query = query.order_by(Attraction.ticket_price.asc())
        else:
            # 默认按评分排序
            query = query.order_by(Attraction.rating.desc())
        
        # 计算总数
        total = query.count()
        
        # 分页
        offset = (page - 1) * page_size
        items = query.offset(offset).limit(page_size).all()
        
        return AttractionListResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=items
        )
    
    def get_by_id(self, attraction_id: int) -> Optional[Attraction]:
        """根据ID获取景点详情"""
        cache_key = f"attraction:detail:{attraction_id}"
        
        # 尝试从Redis缓存获取
        try:
            cached = self.redis.get(cache_key)
            if cached:
                pass
        except Exception as e:
            logger.warning(f"Redis读取失败: {e}")
        
        # 从数据库获取
        attraction = self.db.query(Attraction).filter(
            and_(Attraction.id == attraction_id, Attraction.status == 1)
        ).first()
        
        if attraction:
            # 更新缓存
            try:
                self.redis.set(cache_key, json.dumps({
                    "id": attraction.id,
                    "name": attraction.name,
                    "rating": float(attraction.rating) if attraction.rating else 0
                }, ensure_ascii=False), ex=3600)
            except Exception as e:
                logger.warning(f"Redis写入失败: {e}")
        
        return attraction
    
    def _call_poi_api(
        self,
        latitude: Decimal,
        longitude: Decimal,
        radius: int,
        category: str
    ) -> List[dict]:
        """调用高德地图POI API搜索周边景点"""
        api_key = settings.AMAP_API_KEY
        if not api_key:
            logger.warning("高德地图API Key未配置，跳过POI搜索")
            return []
        
        try:
            url = "https://restapi.amap.com/v3/place/around"
            params = {
                "key": api_key,
                "location": f"{longitude},{latitude}",
                "radius": radius,
                "types": "110000|060000",  # 风景名胜|体育休闲服务
                "offset": 25,
                "page": 1,
                "output": "json"
            }
            
            with httpx.Client(timeout=15) as client:
                response = client.get(url, params=params)
                data = response.json()
            
            if data.get("status") == "1" and data.get("pois"):
                results = []
                for poi in data["pois"]:
                    location = poi.get("location", "")
                    if not location:
                        continue
                    lng, lat = location.split(",")
                    
                    results.append({
                        "name": poi.get("name", ""),
                        "address": poi.get("address", ""),
                        "latitude": float(lat),
                        "longitude": float(lng),
                        "city": poi.get("cityname", ""),
                        "district": poi.get("adname", ""),
                        "category": self._extract_category(poi.get("type", "")),
                        "phone": self._safe_str(poi.get("tel", ""), 20),
                        "source_id": poi.get("id", ""),
                        "description": poi.get("tag", ""),
                        "opening_hours": self._safe_str(poi.get("business_time", ""))
                    })
                return results
        except Exception as e:
            logger.error(f"POI API调用失败: {e}")
        
        return []
    
    def _extract_category(self, type_str: str) -> str:
        """从POI类型字符串中提取分类"""
        category_map = {
            "公园": "公园",
            "博物馆": "博物馆",
            "商场": "商场",
            "景点": "景点",
            "寺庙": "宗教",
            "古迹": "历史古迹",
            "游乐": "游乐园",
            "动物园": "动物园",
            "植物园": "植物园",
            "美术馆": "美术馆",
            "展览馆": "展览馆",
            "图书馆": "图书馆",
            "剧院": "剧院",
            "体育": "体育场馆",
        }
        for key, value in category_map.items():
            if key in type_str:
                return value
        return "其他"
    
    @staticmethod
    def _safe_str(value, max_len: int = 0) -> str:
        """确保值为字符串，截断过长的值"""
        if isinstance(value, list):
            return ""
        s = str(value) if value is not None else ""
        return s[:max_len] if max_len > 0 and len(s) > max_len else s

    def _save_attractions_to_db(self, poi_results: List[dict]) -> None:
        """将POI结果保存到数据库"""
        for item in poi_results:
            existing = self.db.query(Attraction).filter(
                Attraction.source_id == item.get("source_id")
            ).first()
            if existing:
                continue
            
            attraction = Attraction(
                name=item.get("name", ""),
                address=item.get("address", ""),
                latitude=Decimal(str(item.get("latitude", 0))),
                longitude=Decimal(str(item.get("longitude", 0))),
                city=item.get("city", ""),
                district=item.get("district", ""),
                category=item.get("category", "其他"),
                phone=item.get("phone", ""),
                description=item.get("description", ""),
                opening_hours=item.get("opening_hours", ""),
                source="gaode",
                source_id=item.get("source_id", ""),
                tags=[],
                highlights=[],
                images=[]
            )
            self.db.add(attraction)
        
        try:
            self.db.commit()
        except Exception as e:
            logger.error(f"保存景点数据失败: {e}")
            self.db.rollback()
