import json
import logging
from datetime import datetime, timedelta
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from app.config import settings
from app.redis_client import get_redis

logger = logging.getLogger(__name__)

router = APIRouter()
AMAP_BASE = "https://restapi.amap.com/v3"
TIMEOUT = 15

# 半径常量
RADIUS_MIN = 100       # 100 米
RADIUS_MAX = 50000     # 50 公里
RADIUS_DEFAULT = 3000  # 3 公里
RADIUS_STEP = 100      # 步进值


# ---------- 请求模型 ----------

class GeocodeRequest(BaseModel):
    address: str
    city: str = ""

class ReGeocodeRequest(BaseModel):
    latitude: float
    longitude: float
    radius: int = 1000

    @field_validator("radius")
    @classmethod
    def clamp_radius(cls, v):
        return max(RADIUS_MIN, min(v, RADIUS_MAX))

class PlaceAroundRequest(BaseModel):
    latitude: float
    longitude: float
    types: str = ""
    radius: int = 3000
    page: int = Field(default=1, ge=1, le=100)
    pageSize: int = Field(default=20, ge=1, le=50)
    keywords: str = ""

    @field_validator("radius")
    @classmethod
    def clamp_radius(cls, v):
        return max(RADIUS_MIN, min(v, RADIUS_MAX))

class PlaceTextRequest(BaseModel):
    keywords: str
    city: str = ""
    types: str = ""
    page: int = 1
    pageSize: int = 20

class DirectionRequest(BaseModel):
    origin: dict  # {latitude, longitude}
    destination: dict  # {latitude, longitude}
    strategy: int = 0

class RouteRequest(BaseModel):
    origin: dict
    destination: dict

class InputTipsRequest(BaseModel):
    keywords: str
    city: str = ""
    type: str = ""
    datatype: str = "all"
    citylimit: bool = False

class WeatherRequest(BaseModel):
    city: str  # 城市编码adcode，如 "440600"（佛山），或城市名如 "佛山"


# ---------- 辅助函数 ----------

async def amap_get(path: str, params: dict):
    """调用高德 REST API（GET 方式）"""
    params["key"] = settings.AMAP_API_KEY
    params["output"] = "JSON"
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(f"{AMAP_BASE}{path}", params=params)
        data = resp.json()
    if data.get("status") != "1":
        raise HTTPException(status_code=502, detail=data.get("info", "高德 API 请求失败"))
    return data


# ---------- 请求模型 ----------

class PositionRequest(BaseModel):
    """定位请求（从前端获取客户端IP，也可传入指定经纬度做逆向查询）"""
    ip: Optional[str] = None

class PositionResponse(BaseModel):
    latitude: float
    longitude: float
    address: str
    province: str = ""
    city: str = ""
    district: str = ""
    adcode: str = ""
    source: str = "ip"  # ip / jsapi

# ---------- 配置接口 ----------

@router.get("/config", summary="获取高德地图 JSAPI 配置")
async def get_amap_config():
    """返回前端高德地图 JSAPI 所需的配置信息（不包含 WebService API Key）"""
    if not settings.AMAP_JSAPI_KEY:
        raise HTTPException(status_code=500, detail="高德地图 JSAPI Key 未配置")
    has_security = bool(settings.AMAP_JSAPI_SECURITY_KEY)
    logger.info(f"[MAP] JSAPI 配置获取 | has_key=true | has_security_key={has_security} | version=2.0")
    return {
        "key": settings.AMAP_JSAPI_KEY,
        "security_key": settings.AMAP_JSAPI_SECURITY_KEY or "",
        "version": "2.0"
    }


@router.get("/radius/config", summary="获取搜索半径配置参数")
async def get_radius_config():
    """返回搜索半径的可配置范围、默认值、步进与预设值列表"""
    return {
        "min": RADIUS_MIN,
        "max": RADIUS_MAX,
        "default": RADIUS_DEFAULT,
        "step": RADIUS_STEP,
        "unit": "m",
        "presets": [
            {"label": "100m", "value": 100},
            {"label": "500m", "value": 500},
            {"label": "1km", "value": 1000},
            {"label": "3km", "value": 3000},
            {"label": "5km", "value": 5000},
            {"label": "10km", "value": 10000},
            {"label": "20km", "value": 20000},
            {"label": "50km", "value": 50000}
        ],
        "warningThreshold": 0.8,
        "description": {
            "RADIUS_MIN": f"最小搜索半径 {RADIUS_MIN}m（{RADIUS_MIN/1000}km）",
            "RADIUS_MAX": f"最大搜索半径 {RADIUS_MAX}m（{RADIUS_MAX/1000}km）",
            "RADIUS_DEFAULT": f"默认搜索半径 {RADIUS_DEFAULT}m（{RADIUS_DEFAULT/1000}km）",
            "note": "超出范围时自动截断到有效区间"
        }
    }


# ---------- 地理编码 ----------

@router.post("/geocode", summary="地理编码：地址转坐标")
async def geocode(req: GeocodeRequest):
    """将详细地址转换为经纬度坐标"""
    params = {"address": req.address}
    if req.city:
        params["city"] = req.city
    data = await amap_get("/geocode/geo", params)

    if not data.get("geocodes") or len(data["geocodes"]) == 0:
        raise HTTPException(status_code=404, detail="未找到该地址的坐标信息")

    g = data["geocodes"][0]
    lng, lat = g["location"].split(",")
    return {
        "latitude": float(lat),
        "longitude": float(lng),
        "address": g.get("formatted_address", ""),
        "level": g.get("level", "")
    }


@router.post("/regeocode", summary="逆地理编码：坐标转地址")
async def regeocode(req: ReGeocodeRequest):
    """将经纬度坐标转换为详细地址信息"""
    location = f"{req.longitude},{req.latitude}"
    data = await amap_get("/geocode/regeo", {
        "location": location,
        "radius": req.radius,
        "extensions": "all"
    })

    regeo = data.get("regeocode", {})
    ac = regeo.get("addressComponent", {})
    address = regeo.get("formatted_address", "")
    city = ac.get("city") or ac.get("province", "")

    logger.info(
        f"[MAP] [逆地理编码] [SUCCESS] "
        f"| coord=({req.latitude:.4f}, {req.longitude:.4f}) "
        f"| address={address[:60]} "
        f"| city={city} "
        f"| detail=前端精确定位(GPS/基站)后调用逆地理获取地址 — 来源jsapi/浏览器"
    )

    return {
        "address": address,
        "country": ac.get("country", ""),
        "province": ac.get("province", ""),
        "city": city,
        "district": ac.get("district", ""),
        "street": ac.get("street", ""),
        "streetNumber": ac.get("streetNumber", ""),
        "adcode": ac.get("adcode", ""),
        "aoi": (regeo.get("aois") or [{}])[0] if regeo.get("aois") else None,
        "pois": regeo.get("pois") or []
    }


# ---------- 高德定位 MCP 服务（IP定位） ----------

@router.post("/position", summary="高德定位 MCP：IP定位获取位置信息")
async def get_position(req: PositionRequest):
    """
    基于客户端IP获取大致地理位置。
    使用高德IP定位API，返回经纬度、城市、地址等信息。
    前端可选择先尝试浏览器精确定位，失败后降级到此接口。
    """
    ip = req.ip
    raw_ip = ip  # 记录原始 IP
    if not ip or ip in ("127.0.0.1", "::1", "localhost"):
        # 开发环境无公网IP，从高德服务端取（返回服务器出口IP定位）
        ip = ""

    params = {
        "key": settings.AMAP_API_KEY,
        "output": "JSON"
    }
    if ip:
        params["ip"] = ip

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(f"{AMAP_BASE}/ip", params=params)
        data = resp.json()

    if data.get("status") != "1":
        err_msg = data.get("info", "未知错误")
        logger.warning(f"[MAP] [IP定位] [FAILED] | client_ip={raw_ip or '开发环境'} | api_msg={err_msg}")
        raise HTTPException(
            status_code=502,
            detail=f"定位服务暂不可用: {err_msg}"
        )

    # 解析IP定位结果（高德IP定位返回的是城市级信息，不含精确坐标）
    province = data.get("province", "")
    city = data.get("city", "")
    adcode = data.get("adcode", "")
    rectangle = data.get("rectangle", "")  # 形如 "112.806249,22.793019;113.376544,23.266426"

    # 从 rectangle 中计算中心点作为大致坐标
    latitude = 0.0
    longitude = 0.0
    if rectangle and ";" in rectangle:
        parts = rectangle.split(";")
        if len(parts) == 2:
            min_lng, min_lat = parts[0].split(",")
            max_lng, max_lat = parts[1].split(",")
            latitude = (float(min_lat) + float(max_lat)) / 2
            longitude = (float(min_lng) + float(max_lng)) / 2

    # 构造地址字符串
    address_parts = [p for p in (province, city) if p]
    address = " ".join(address_parts) if address_parts else "未知位置"

    logger.info(
        f"[MAP] [IP定位] [SUCCESS] "
        f"| client_ip={raw_ip or '开发环境'} "
        f"| city={city} | adcode={adcode} "
        f"| coord=({latitude:.4f}, {longitude:.4f}) "
        f"| detail=后端高德API IP定位"
    )

    return PositionResponse(
        latitude=latitude,
        longitude=longitude,
        address=address,
        province=province,
        city=city,
        district=data.get("district", ""),
        adcode=adcode,
        source="ip"
    )


# ---------- POI 搜索 ----------
#
# 高德地图 POI 分类编码（Web服务API v3.0，23大类体系）
# 参考：https://lbs.amap.com/api/webservice/guide/api/search
#
# 常用一级分类（6位编码 = 一级2位 + 0000）：
#   010000 汽车服务        090000 医疗保健服务
#   020000 汽车销售        100000 住宿服务
#   030000 汽车维修        110000 风景名胜
#   040000 摩托车服务      120000 商务住宅
#   050000 餐饮服务        130000 政府机构及社会团体
#   060000 购物服务        140000 科教文化服务（教育）
#   070000 生活服务        150000 交通设施服务
#   080000 体育休闲服务（娱乐）  160000 金融保险服务
#

def _format_poi(poi: dict) -> dict:
    return {
        "id": poi.get("id", ""),
        "name": poi.get("name", ""),
        "type": poi.get("type", ""),
        "typecode": poi.get("typecode", ""),
        "address": poi.get("address", ""),
        "location": poi.get("location", ""),
        "tel": poi.get("tel", ""),
        "distance": int(poi.get("distance", 0)),
        "photos": poi.get("photos") or [],
        "rating": poi.get("rating", ""),
        "bizExt": poi.get("biz_ext", {})
    }


@router.post("/place/around", summary="周边 POI 搜索")
async def place_around(req: PlaceAroundRequest):
    """搜索指定位置周边的 POI 点"""
    location = f"{req.longitude},{req.latitude}"
    params = {
        "location": location,
        "radius": req.radius,
        "offset": req.pageSize,
        "page": req.page,
        "extensions": "all"
    }
    if req.types:
        params["types"] = req.types
    if req.keywords:
        params["keywords"] = req.keywords

    data = await amap_get("/place/around", params)
    return {
        "pois": [_format_poi(p) for p in (data.get("pois") or [])],
        "total": int(data.get("count", 0))
    }


@router.post("/place/text", summary="关键词 POI 搜索")
async def place_text(req: PlaceTextRequest):
    """通过关键词搜索 POI 点"""
    params = {
        "keywords": req.keywords,
        "offset": req.pageSize,
        "page": req.page,
        "extensions": "all"
    }
    if req.city:
        params["city"] = req.city
    if req.types:
        params["types"] = req.types

    data = await amap_get("/place/text", params)
    return {
        "pois": [_format_poi(p) for p in (data.get("pois") or [])],
        "total": int(data.get("count", 0))
    }


# ---------- 输入提示 ----------

@router.post("/inputtips", summary="输入提示：关键词联想")
async def input_tips(req: InputTipsRequest):
    """根据用户输入的关键词，返回匹配的 POI 列表（用于搜索框自动补全）"""
    params = {
        "keywords": req.keywords,
        "datatype": req.datatype
    }
    if req.city:
        params["city"] = req.city
    if req.type:
        params["type"] = req.type
    if req.citylimit:
        params["citylimit"] = "true"

    data = await amap_get("/assistant/inputtips", params)

    tips = []
    for tip in (data.get("tips") or []):
        location = tip.get("location", "")
        lng, lat = (None, None)
        if location and "," in location:
            parts = location.split(",")
            lng, lat = float(parts[0]), float(parts[1])

        tips.append({
            "id": tip.get("id", ""),
            "name": tip.get("name", ""),
            "district": tip.get("district", ""),
            "address": tip.get("address", ""),
            "typecode": tip.get("typecode", ""),
            "location": {"longitude": lng, "latitude": lat} if lng and lat else None,
            "adcode": tip.get("adcode", "")
        })

    return {"tips": tips}


# ---------- 路线规划 ----------

@router.post("/direction/walking", summary="步行路线规划")
async def walking_direction(req: RouteRequest):
    """获取步行路线规划"""
    params = {
        "origin": f"{req.origin['longitude']},{req.origin['latitude']}",
        "destination": f"{req.destination['longitude']},{req.destination['latitude']}"
    }
    data = await amap_get("/direction/walking", params)

    route = data.get("route")
    if not route or not route.get("paths"):
        raise HTTPException(status_code=404, detail="未找到步行路线")

    path = route["paths"][0]
    steps = []
    for step in (path.get("steps") or []):
        polyline = []
        if step.get("polyline"):
            for p in step["polyline"].split(";"):
                parts = p.split(",")
                if len(parts) == 2:
                    polyline.append({"longitude": float(parts[0]), "latitude": float(parts[1])})
        steps.append({
            "instruction": step.get("instruction", ""),
            "distance": step.get("distance", 0),
            "duration": step.get("duration", 0),
            "polyline": polyline
        })

    return {
        "distance": path.get("distance", 0),
        "duration": path.get("duration", 0),
        "steps": steps
    }


@router.post("/direction/driving", summary="驾车路线规划")
async def driving_direction(req: DirectionRequest):
    """获取驾车路线规划（支持策略选择）"""
    params = {
        "origin": f"{req.origin['longitude']},{req.origin['latitude']}",
        "destination": f"{req.destination['longitude']},{req.destination['latitude']}",
        "strategy": req.strategy
    }
    data = await amap_get("/direction/driving", params)

    route = data.get("route")
    if not route or not route.get("paths"):
        raise HTTPException(status_code=404, detail="未找到驾车路线")

    path = route["paths"][0]
    steps = []
    for step in (path.get("steps") or []):
        polyline = []
        if step.get("polyline"):
            for p in step["polyline"].split(";"):
                parts = p.split(",")
                if len(parts) == 2:
                    polyline.append({"longitude": float(parts[0]), "latitude": float(parts[1])})
        steps.append({
            "instruction": step.get("instruction", ""),
            "distance": step.get("distance", 0),
            "duration": step.get("duration", 0),
            "road": step.get("road", ""),
            "polyline": polyline
        })

    return {
        "distance": path.get("distance", 0),
        "duration": path.get("duration", 0),
        "tolls": path.get("tolls", 0),
        "taxiCost": route.get("taxi_cost", 0),
        "steps": steps
    }


# ---------- 天气服务 ----------
# 使用高德地图天气API（复用 AMAP_API_KEY，无需额外配置）
# 参考: https://lbs.amap.com/api/webservice/guide/api/weatherinfo
# Redis 缓存策略：按市级adcode缓存实时天气，当天有效，避免区县级冗余缓存

def _normalize_city_adcode(adcode: str) -> str:
    """将区县级adcode归一化为市级（如 440604 → 440600），减少冗余缓存"""
    if len(adcode) >= 4 and adcode[-2:] != "00":
        return adcode[:4] + "00"
    return adcode

def _weather_cache_key(adcode: str) -> str:
    """生成天气缓存key，自动归一化为市级"""
    return f"weather:current:{_normalize_city_adcode(adcode)}"

def _seconds_until_midnight() -> int:
    """计算当前到今天午夜（次日0点）的秒数，用作缓存TTL"""
    now = datetime.now()
    midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return int((midnight - now).total_seconds())

@router.post("/weather/current", summary="获取实时天气")
async def weather_current(req: WeatherRequest):
    """根据城市编码或城市名获取实时天气数据（缓存优先策略）"""
    redis = get_redis()
    
    # 若请求参数是区县级adcode，先尝试查市级缓存
    city_key = _weather_cache_key(req.city)
    if city_key != req.city:  # 发生了归一化
        cached = redis.get(city_key)
        if cached:
            return json.loads(cached)

    # 缓存未命中，调用高德API
    params = {
        "city": req.city,
        "extensions": "base"
    }
    data = await amap_get("/weather/weatherInfo", params)

    lives = data.get("lives")
    if not lives or len(lives) == 0:
        raise HTTPException(status_code=404, detail="未找到该城市的天气信息")

    live = lives[0]
    adcode = live.get("adcode", "")
    city_adcode = _normalize_city_adcode(adcode)  # 归一化为市级
    result = {
        "city": live.get("city", ""),
        "adcode": city_adcode,
        "province": live.get("province", ""),
        "weather": live.get("weather", ""),
        "temperature": live.get("temperature", ""),
        "humidity": live.get("humidity", ""),
        "winddirection": live.get("winddirection", ""),
        "windpower": live.get("windpower", ""),
        "reporttime": live.get("reporttime", ""),
        "type": "current"
    }
    
    # 以归一化市级adcode为key缓存，当天过期
    ttl = _seconds_until_midnight()
    result_json = json.dumps(result, ensure_ascii=False)
    if city_adcode:
        redis.setex(_weather_cache_key(city_adcode), ttl, result_json)
        # 同时清理旧的非归一化key（兼容旧缓存）
        if adcode != city_adcode:
            redis.delete(_weather_cache_key(adcode))
    
    return result
