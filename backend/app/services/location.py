import json
import httpx
import logging
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Optional
from app.models.location import UserLocation, LocationLog
from app.schemas.location import LocationCreate, LocationUpdate, LocationSetRequest
from app.redis_client import get_redis
from app.config import settings

logger = logging.getLogger(__name__)


class LocationService:
    """定位服务"""
    
    def __init__(self, db: Session):
        self.db = db
        self.redis = get_redis()
    
    def get_current_location(self, user_id: int) -> Optional[UserLocation]:
        """获取用户当前位置"""
        cache_key = f"user:location:{user_id}"
        
        # 1. 首先尝试从Redis缓存获取
        try:
            cached = self.redis.get(cache_key)
            if cached:
                location_id = int(cached)
                location = self.db.query(UserLocation).filter(UserLocation.id == location_id).first()
                if location:
                    return location
        except Exception as e:
            logger.warning(f"Redis读取失败: {e}")
        
        # 2. 从数据库获取默认位置
        location = self.db.query(UserLocation).filter(
            and_(
                UserLocation.user_id == user_id,
                UserLocation.is_default == True
            )
        ).first()
        
        if location:
            # 更新缓存
            self._set_location_cache(user_id, location.id)
            return location
        
        # 3. 如果没有默认位置，获取最近添加的位置
        location = self.db.query(UserLocation).filter(
            UserLocation.user_id == user_id
        ).order_by(UserLocation.updated_at.desc()).first()
        
        if location:
            self._set_location_cache(user_id, location.id)
            return location
        
        return None
    
    def set_location(self, user_id: int, location_data: LocationSetRequest) -> UserLocation:
        """手动设置用户位置"""
        # 地理编码：将经纬度转换为地址
        geo_info = {}
        if not location_data.address:
            geo_info = self._geocode(float(location_data.latitude), float(location_data.longitude))
        
        address = location_data.address or geo_info.get("address", "未知地址")
        city = geo_info.get("city", "")
        district = geo_info.get("district", "")
        
        # 查找或创建当前位置记录
        location = self.db.query(UserLocation).filter(
            and_(
                UserLocation.user_id == user_id,
                UserLocation.is_default == True
            )
        ).first()
        
        if location:
            # 更新默认位置
            location.address = address
            location.latitude = location_data.latitude
            location.longitude = location_data.longitude
            location.city = city
            location.district = district
        else:
            # 创建新的默认位置
            location = UserLocation(
                user_id=user_id,
                name="当前位置",
                address=address,
                latitude=location_data.latitude,
                longitude=location_data.longitude,
                city=city,
                district=district,
                is_default=True
            )
            self.db.add(location)
        
        # 记录定位日志
        log = LocationLog(
            user_id=user_id,
            latitude=location_data.latitude,
            longitude=location_data.longitude,
            accuracy=location_data.accuracy,
            source=location_data.source
        )
        self.db.add(log)
        
        self.db.commit()
        self.db.refresh(location)
        
        # 更新Redis缓存
        self._set_location_cache(user_id, location.id)
        
        return location
    
    def get_favorite_locations(self, user_id: int) -> List[UserLocation]:
        """获取用户常用位置列表"""
        return self.db.query(UserLocation).filter(
            UserLocation.user_id == user_id
        ).order_by(UserLocation.is_default.desc(), UserLocation.updated_at.desc()).all()
    
    def add_favorite_location(self, user_id: int, location_data: LocationCreate) -> UserLocation:
        """添加常用位置"""
        # 如果设置为默认，先取消其他默认
        if location_data.is_default:
            self._clear_default(user_id)
        
        # 如果是第一个位置，自动设为默认
        count = self.db.query(UserLocation).filter(UserLocation.user_id == user_id).count()
        if count == 0:
            location_data.is_default = True
        
        location = UserLocation(
            user_id=user_id,
            name=location_data.name,
            address=location_data.address,
            latitude=location_data.latitude,
            longitude=location_data.longitude,
            city=location_data.city,
            district=location_data.district,
            is_default=location_data.is_default
        )
        self.db.add(location)
        self.db.commit()
        self.db.refresh(location)
        
        # 如果是默认位置，更新缓存
        if location.is_default:
            self._set_location_cache(user_id, location.id)
        
        return location
    
    def update_favorite_location(self, user_id: int, location_id: int, location_data: LocationUpdate) -> UserLocation:
        """更新常用位置"""
        location = self.db.query(UserLocation).filter(
            and_(
                UserLocation.id == location_id,
                UserLocation.user_id == user_id
            )
        ).first()
        
        if not location:
            raise ValueError("位置记录不存在")
        
        # 如果设置为默认，先取消其他默认
        if location_data.is_default and not location.is_default:
            self._clear_default(user_id)
        
        # 更新字段
        update_data = location_data.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(location, key, value)
        
        self.db.commit()
        self.db.refresh(location)
        
        # 更新缓存
        if location.is_default:
            self._set_location_cache(user_id, location.id)
        
        return location
    
    def delete_favorite_location(self, user_id: int, location_id: int) -> None:
        """删除常用位置"""
        location = self.db.query(UserLocation).filter(
            and_(
                UserLocation.id == location_id,
                UserLocation.user_id == user_id
            )
        ).first()
        
        if not location:
            raise ValueError("位置记录不存在")
        
        is_default = location.is_default
        self.db.delete(location)
        self.db.commit()
        
        # 如果删除的是默认位置，将最新位置设为默认
        if is_default:
            next_location = self.db.query(UserLocation).filter(
                UserLocation.user_id == user_id
            ).order_by(UserLocation.updated_at.desc()).first()
            
            if next_location:
                next_location.is_default = True
                self.db.commit()
                self._set_location_cache(user_id, next_location.id)
            else:
                self._clear_location_cache(user_id)
    
    def switch_location(self, user_id: int, location_id: int) -> UserLocation:
        """切换到常用位置"""
        location = self.db.query(UserLocation).filter(
            and_(
                UserLocation.id == location_id,
                UserLocation.user_id == user_id
            )
        ).first()
        
        if not location:
            raise ValueError("位置记录不存在")
        
        # 清除其他默认
        self._clear_default(user_id)
        
        # 设置当前为默认
        location.is_default = True
        self.db.commit()
        self.db.refresh(location)
        
        # 更新缓存
        self._set_location_cache(user_id, location.id)
        
        return location
    
    def _set_location_cache(self, user_id: int, location_id: int) -> None:
        """设置位置缓存"""
        cache_key = f"user:location:{user_id}"
        try:
            self.redis.set(cache_key, str(location_id), ex=3600)  # 缓存1小时
        except Exception as e:
            logger.warning(f"Redis写入失败: {e}")
    
    def _clear_location_cache(self, user_id: int) -> None:
        """清除位置缓存"""
        cache_key = f"user:location:{user_id}"
        try:
            self.redis.delete(cache_key)
        except Exception as e:
            logger.warning(f"Redis删除失败: {e}")
    
    def _clear_default(self, user_id: int) -> None:
        """清除用户的默认位置"""
        self.db.query(UserLocation).filter(
            and_(
                UserLocation.user_id == user_id,
                UserLocation.is_default == True
            )
        ).update({"is_default": False})
    
    def _geocode(self, latitude: float, longitude: float) -> dict:
        """地理编码：经纬度转地址（调用高德地图API）"""
        api_key = settings.AMAP_API_KEY
        if not api_key:
            logger.warning("高德地图API Key未配置")
            return {}
        
        try:
            url = "https://restapi.amap.com/v3/geocode/regeo"
            params = {
                "key": api_key,
                "location": f"{longitude},{latitude}",
                "output": "json"
            }
            
            with httpx.Client(timeout=10) as client:
                response = client.get(url, params=params)
                data = response.json()
            
            if data.get("status") == "1" and data.get("regeocode"):
                regeocode = data["regeocode"]
                address_component = regeocode.get("addressComponent", {})
                return {
                    "address": regeocode.get("formatted_address", ""),
                    "city": address_component.get("city", ""),
                    "district": address_component.get("district", ""),
                    "province": address_component.get("province", "")
                }
        except Exception as e:
            logger.error(f"地理编码失败: {e}")
        
        return {}
    
    def _reverse_geocode(self, address: str) -> dict:
        """反向地理编码：地址转经纬度（调用高德地图API）"""
        api_key = settings.AMAP_API_KEY
        if not api_key:
            logger.warning("高德地图API Key未配置")
            return {}
        
        try:
            url = "https://restapi.amap.com/v3/geocode/geo"
            params = {
                "key": api_key,
                "address": address,
                "output": "json"
            }
            
            with httpx.Client(timeout=10) as client:
                response = client.get(url, params=params)
                data = response.json()
            
            if data.get("status") == "1" and data.get("geocodes"):
                location = data["geocodes"][0].get("location", "")
                if location:
                    lng, lat = location.split(",")
                    return {
                        "latitude": float(lat),
                        "longitude": float(lng),
                        "formatted_address": data["geocodes"][0].get("formatted_address", "")
                    }
        except Exception as e:
            logger.error(f"反向地理编码失败: {e}")
        
        return {}
