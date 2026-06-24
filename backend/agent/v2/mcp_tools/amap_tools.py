"""
V2 高德地图 MCP 工具实现

使用高德官方 MCP Server（Streamable HTTP 方式），基于 JSON-RPC 2.0 协议。
文档：https://lbs.amap.com/api/mcp-server/gettingstarted
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from ..deterministic import DeterministicTool, ToolResult
from .config import get_mcp_tools_config

logger = logging.getLogger(__name__)


class AmapBaseTool(DeterministicTool):
    """高德地图工具基类 - 使用 MCP Server 协议"""
    
    def __init__(self):
        self.config = get_mcp_tools_config().amap
    
    def _parse_sse_response(self, sse_text: str) -> dict:
        """
        解析 SSE (Server-Sent Events) 格式的响应
        
        SSE 格式示例:
        event: message
        data: {"jsonrpc": "2.0", "result": {...}, "id": "xxx"}
        
        Args:
            sse_text: SSE 响应文本
            
        Returns:
            解析后的 JSON 数据
        """
        result = None
        for line in sse_text.strip().split("\n"):
            line = line.strip()
            if line.startswith("data: "):
                data_str = line[6:]  # 去掉 "data: " 前缀
                try:
                    result = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
        
        if result is None:
            raise Exception(f"无法解析 SSE 响应: {sse_text[:200]}")
        
        return result
    
    async def _call_mcp_tool(self, tool_name: str, params: dict) -> dict:
        """
        调用高德 MCP Server 工具（标准 MCP tools/call 协议）
        
        Args:
            tool_name: MCP 工具名称（如 around_search）
            params: 工具参数
            
        Returns:
            MCP 响应结果
        """
        request_id = str(uuid.uuid4())
        
        # 构建标准 MCP JSON-RPC 2.0 请求（使用 tools/call）
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": params
            },
            "id": request_id
        }
        
        endpoint = self.config.mcp_endpoint
        
        # MCP Streamable HTTP 协议要求的请求头
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
        }
        
        # 抑制 httpx/httpcore 的 DEBUG 日志，避免泄露 URL 中的 API Key
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        
        try:
            async with httpx.AsyncClient(timeout=self.config.request_timeout) as client:
                response = await client.post(
                    endpoint,
                    json=payload,
                    headers=headers
                )
                response.raise_for_status()
                
                # 根据响应 Content-Type 解析
                content_type = response.headers.get("content-type", "")
                if "text/event-stream" in content_type:
                    # SSE 格式：解析最后一个 data 事件
                    result = self._parse_sse_response(response.text)
                else:
                    result = response.json()
        except httpx.HTTPStatusError as e:
            # HTTP 错误不暴露完整 URL（含 API Key）
            raise Exception(f"MCP Server HTTP 错误: {e.response.status_code}")
        except Exception as e:
            # 其他错误也不暴露完整 URL
            raise Exception(f"MCP Server 请求失败: {type(e).__name__}")
        
        # 检查 JSON-RPC 错误
        if "error" in result:
            error = result["error"]
            raise Exception(f"MCP Server 错误: {error.get('message', str(error))}")
        
        # 提取结果数据（tools/call 返回 result 中包含 content）
        if "result" in result:
            inner = result["result"]
            # 标准 MCP 工具调用返回格式：{"content": [{"type": "text", "text": "..."}]}
            if isinstance(inner, dict) and "content" in inner:
                for item in inner["content"]:
                    if item.get("type") == "text":
                        try:
                            return json.loads(item["text"])
                        except (json.JSONDecodeError, KeyError):
                            return item["text"]
                return inner
            return inner
        
        raise Exception(f"MCP Server 返回无效响应: {result}")


class AmapPlaceAroundTool(AmapBaseTool):
    """周边 POI 搜索工具 - 使用 MCP Server"""
    
    @property
    def name(self) -> str:
        return "amap.place_around"
    
    @property
    def description(self) -> str:
        return "搜索指定位置周边的 POI（兴趣点），如餐厅、景点、商场等"
    
    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "latitude": {
                    "type": "number",
                    "description": "纬度"
                },
                "longitude": {
                    "type": "number",
                    "description": "经度"
                },
                "radius": {
                    "type": "integer",
                    "description": "搜索半径（米）",
                    "default": 3000
                },
                "types": {
                    "type": "string",
                    "description": "POI 类型编码，多个用逗号分隔",
                    "default": ""
                },
                "keywords": {
                    "type": "string",
                    "description": "搜索关键词",
                    "default": ""
                },
                "page": {
                    "type": "integer",
                    "description": "页码",
                    "default": 1
                },
                "page_size": {
                    "type": "integer",
                    "description": "每页数量",
                    "default": 20
                }
            },
            "required": ["latitude", "longitude"]
        }
    
    async def execute(self, **kwargs) -> ToolResult:
        """执行周边搜索"""
        latitude = kwargs.get("latitude")
        longitude = kwargs.get("longitude")
        radius = kwargs.get("radius", self.config.default_radius)
        types = kwargs.get("types", "")
        keywords = kwargs.get("keywords", "")
        page = kwargs.get("page", 1)
        page_size = kwargs.get("page_size", self.config.default_page_size)
        
        # MCP Server 参数格式（官方名称: around_search）
        mcp_params = {
            "location": f"{longitude},{latitude}",
            "radius": str(radius),
        }
        
        if types:
            mcp_params["types"] = types
        if keywords:
            mcp_params["keywords"] = keywords
        if page > 1:
            mcp_params["page"] = str(page)
        if page_size != 20:
            mcp_params["offset"] = str(page_size)
        
        try:
            data = await self._call_mcp_tool("maps_around_search", mcp_params)
            
            pois = []
            for p in (data.get("pois") or []):
                pois.append({
                    "id": p.get("id", ""),
                    "name": p.get("name", ""),
                    "type": p.get("type", ""),
                    "address": p.get("address", ""),
                    "location": p.get("location", ""),
                    "distance": int(p.get("distance", 0)),
                    "rating": p.get("rating", ""),
                    "tel": p.get("tel", ""),
                })
            
            return ToolResult(
                success=True,
                data={"pois": pois, "total": int(data.get("count", 0))}
            )
            
        except Exception as e:
            logger.error(f"周边搜索失败: {e}")
            return ToolResult(
                success=False,
                error=f"周边搜索失败: {str(e)}"
            )


class AmapRegeocodeTool(AmapBaseTool):
    """逆地理编码工具 - 使用 MCP Server"""
    
    @property
    def name(self) -> str:
        return "amap.regeocode"
    
    @property
    def description(self) -> str:
        return "将经纬度坐标转换为详细地址信息"
    
    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "latitude": {
                    "type": "number",
                    "description": "纬度"
                },
                "longitude": {
                    "type": "number",
                    "description": "经度"
                }
            },
            "required": ["latitude", "longitude"]
        }
    
    async def execute(self, **kwargs) -> ToolResult:
        """执行逆地理编码"""
        latitude = kwargs.get("latitude")
        longitude = kwargs.get("longitude")
        
        # MCP Server 参数格式（官方名称: regeocode）
        mcp_params = {
            "location": f"{longitude},{latitude}"
        }
        
        try:
            data = await self._call_mcp_tool("maps_regeocode", mcp_params)
            
            regeo = data.get("regeocode", {})
            ac = regeo.get("addressComponent", {})
            
            result = {
                "address": regeo.get("formatted_address", ""),
                "city": ac.get("city") or ac.get("province", ""),
                "district": ac.get("district", ""),
                "adcode": ac.get("adcode", ""),
            }
            
            return ToolResult(success=True, data=result)
            
        except Exception as e:
            logger.error(f"逆地理编码失败: {e}")
            return ToolResult(
                success=False,
                error=f"逆地理编码失败: {str(e)}"
            )


class AmapDirectionWalkingTool(AmapBaseTool):
    """步行路线规划工具 - 使用 MCP Server"""
    
    @property
    def name(self) -> str:
        return "amap.direction_walking"
    
    @property
    def description(self) -> str:
        return "规划两个地点之间的步行路线"
    
    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "origin": {
                    "type": "object",
                    "description": "起点坐标 {latitude, longitude}",
                    "properties": {
                        "latitude": {"type": "number"},
                        "longitude": {"type": "number"}
                    },
                    "required": ["latitude", "longitude"]
                },
                "destination": {
                    "type": "object",
                    "description": "终点坐标 {latitude, longitude}",
                    "properties": {
                        "latitude": {"type": "number"},
                        "longitude": {"type": "number"}
                    },
                    "required": ["latitude", "longitude"]
                }
            },
            "required": ["origin", "destination"]
        }
    
    async def execute(self, **kwargs) -> ToolResult:
        """执行步行路线规划"""
        origin = kwargs.get("origin")
        destination = kwargs.get("destination")
        
        # MCP Server 参数格式
        mcp_params = {
            "origin": f"{origin['longitude']},{origin['latitude']}",
            "destination": f"{destination['longitude']},{destination['latitude']}",
        }
        
        try:
            data = await self._call_mcp_tool("maps_direction_walking", mcp_params)
            
            route = data.get("route", {})
            paths = route.get("paths", [])
            
            if paths:
                result = {
                    "distance": paths[0].get("distance", 0),
                    "duration": paths[0].get("duration", 0)
                }
            else:
                result = {"distance": 0, "duration": 0}
            
            return ToolResult(success=True, data=result)
            
        except Exception as e:
            logger.error(f"步行路线规划失败: {e}")
            return ToolResult(
                success=False,
                error=f"步行路线规划失败: {str(e)}"
            )


class AmapDirectionBicyclingTool(AmapBaseTool):
    """骑行路线规划工具 - 使用 MCP Server"""
    
    @property
    def name(self) -> str:
        return "amap.direction_bicycling"
    
    @property
    def description(self) -> str:
        return "规划两个地点之间的骑行路线，适合自行车或电动车出行"
    
    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "origin": {
                    "type": "object",
                    "description": "起点坐标 {latitude, longitude}",
                    "properties": {
                        "latitude": {"type": "number"},
                        "longitude": {"type": "number"}
                    },
                    "required": ["latitude", "longitude"]
                },
                "destination": {
                    "type": "object",
                    "description": "终点坐标 {latitude, longitude}",
                    "properties": {
                        "latitude": {"type": "number"},
                        "longitude": {"type": "number"}
                    },
                    "required": ["latitude", "longitude"]
                }
            },
            "required": ["origin", "destination"]
        }
    
    async def execute(self, **kwargs) -> ToolResult:
        """执行骑行路线规划"""
        origin = kwargs.get("origin")
        destination = kwargs.get("destination")
        
        # MCP Server 参数格式
        mcp_params = {
            "origin": f"{origin['longitude']},{origin['latitude']}",
            "destination": f"{destination['longitude']},{destination['latitude']}",
        }
        
        try:
            data = await self._call_mcp_tool("maps_direction_bicycling", mcp_params)
            
            route = data.get("data", {})
            paths = route.get("paths", [])
            
            if paths:
                path = paths[0]
                result = {
                    "distance": path.get("distance", 0),
                    "duration": path.get("duration", 0),
                    "steps": [
                        {
                            "instruction": step.get("instruction", ""),
                            "road": step.get("road", ""),
                            "distance": step.get("distance", 0),
                            "duration": step.get("duration", 0),
                        }
                        for step in path.get("steps", [])[:10]  # 最多返回 10 步
                    ]
                }
            else:
                result = {"distance": 0, "duration": 0, "steps": []}
            
            return ToolResult(success=True, data=result)
            
        except Exception as e:
            logger.error(f"骑行路线规划失败: {e}")
            return ToolResult(
                success=False,
                error=f"骑行路线规划失败: {str(e)}"
            )


class AmapDirectionDrivingTool(AmapBaseTool):
    """驾车路线规划工具 - 使用 MCP Server"""
    
    @property
    def name(self) -> str:
        return "amap.direction_driving"
    
    @property
    def description(self) -> str:
        return "规划两个地点之间的驾车路线，支持多种策略（最快、最短、避开拥堵等）"
    
    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "origin": {
                    "type": "object",
                    "description": "起点坐标 {latitude, longitude}",
                    "properties": {
                        "latitude": {"type": "number"},
                        "longitude": {"type": "number"}
                    },
                    "required": ["latitude", "longitude"]
                },
                "destination": {
                    "type": "object",
                    "description": "终点坐标 {latitude, longitude}",
                    "properties": {
                        "latitude": {"type": "number"},
                        "longitude": {"type": "number"}
                    },
                    "required": ["latitude", "longitude"]
                },
                "strategy": {
                    "type": "integer",
                    "description": "驾车策略：0-速度优先(默认)，1-费用优先，2-距离优先，3-不走高速，4-躲避拥堵，5-多策略",
                    "default": 0
                },
                "waypoints": {
                    "type": "array",
                    "description": "途经点坐标列表 [{latitude, longitude}, ...]，最多支持16个",
                    "items": {
                        "type": "object",
                        "properties": {
                            "latitude": {"type": "number"},
                            "longitude": {"type": "number"}
                        }
                    }
                }
            },
            "required": ["origin", "destination"]
        }
    
    async def execute(self, **kwargs) -> ToolResult:
        """执行驾车路线规划"""
        origin = kwargs.get("origin")
        destination = kwargs.get("destination")
        strategy = kwargs.get("strategy", 0)
        waypoints = kwargs.get("waypoints", [])
        
        # MCP Server 参数格式
        mcp_params = {
            "origin": f"{origin['longitude']},{origin['latitude']}",
            "destination": f"{destination['longitude']},{destination['latitude']}",
            "strategy": str(strategy),
        }
        
        # 处理途经点
        if waypoints:
            waypoint_strs = [
                f"{wp['longitude']},{wp['latitude']}"
                for wp in waypoints[:16]  # 最多16个途经点
            ]
            mcp_params["waypoints"] = ";".join(waypoint_strs)
        
        try:
            data = await self._call_mcp_tool("maps_direction_driving", mcp_params)
            
            route = data.get("route", {})
            paths = route.get("paths", [])
            
            if paths:
                path = paths[0]
                result = {
                    "distance": path.get("distance", 0),
                    "duration": path.get("duration", 0),
                    "tolls": path.get("tolls", 0),
                    "toll_distance": path.get("toll_distance", 0),
                    "traffic_lights": path.get("traffic_lights", 0),
                    "steps": [
                        {
                            "instruction": step.get("instruction", ""),
                            "road": step.get("road", ""),
                            "distance": step.get("distance", 0),
                            "duration": step.get("duration", 0),
                            "tolls": step.get("tolls", 0),
                        }
                        for step in path.get("steps", [])[:10]  # 最多返回 10 步
                    ]
                }
            else:
                result = {"distance": 0, "duration": 0, "tolls": 0, "steps": []}
            
            return ToolResult(success=True, data=result)
            
        except Exception as e:
            logger.error(f"驾车路线规划失败: {e}")
            return ToolResult(
                success=False,
                error=f"驾车路线规划失败: {str(e)}"
            )


class AmapDirectionTransitTool(AmapBaseTool):
    """公交路线规划工具 - 使用 MCP Server"""
    
    @property
    def name(self) -> str:
        return "amap.direction_transit"
    
    @property
    def description(self) -> str:
        return "规划两个地点之间的公共交通路线（地铁、公交等），需要指定起终点所在城市"
    
    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "origin": {
                    "type": "object",
                    "description": "起点坐标 {latitude, longitude}",
                    "properties": {
                        "latitude": {"type": "number"},
                        "longitude": {"type": "number"}
                    },
                    "required": ["latitude", "longitude"]
                },
                "destination": {
                    "type": "object",
                    "description": "终点坐标 {latitude, longitude}",
                    "properties": {
                        "latitude": {"type": "number"},
                        "longitude": {"type": "number"}
                    },
                    "required": ["latitude", "longitude"]
                },
                "city": {
                    "type": "string",
                    "description": "起点城市（城市名或城市编码），如\"北京\"、\"010\""
                },
                "cityd": {
                    "type": "string",
                    "description": "终点城市（城市名或城市编码），跨城规划时必填"
                },
                "strategy": {
                    "type": "integer",
                    "description": "公交策略：0-最快捷(默认)，1-最经济，2-最少换乘，3-最少步行，4-最舒适，5-不坐地铁",
                    "default": 0
                },
                "nightflag": {
                    "type": "integer",
                    "description": "是否包含夜班车：0-不包含(默认)，1-包含",
                    "default": 0
                }
            },
            "required": ["origin", "destination", "city"]
        }
    
    async def execute(self, **kwargs) -> ToolResult:
        """执行公交路线规划"""
        origin = kwargs.get("origin")
        destination = kwargs.get("destination")
        city = kwargs.get("city")
        cityd = kwargs.get("cityd", "")
        strategy = kwargs.get("strategy", 0)
        nightflag = kwargs.get("nightflag", 0)
        
        # MCP Server 参数格式
        mcp_params = {
            "origin": f"{origin['longitude']},{origin['latitude']}",
            "destination": f"{destination['longitude']},{destination['latitude']}",
            "city": city,
            "cityd": cityd or city,
            "strategy": str(strategy),
            "nightflag": str(nightflag),
        }
        
        try:
            data = await self._call_mcp_tool("maps_direction_transit_integrated", mcp_params)
            
            route = data.get("route", {})
            transits = route.get("transits", [])
            
            if transits:
                # 返回最多 5 条方案
                results = []
                for transit in transits[:5]:
                    segments = []
                    for seg in transit.get("segments", []):
                        segment_info = {}
                        # 公交信息
                        bus = seg.get("bus", {})
                        if bus and bus.get("buslines"):
                            busline = bus["buslines"][0]
                            segment_info["bus"] = {
                                "name": busline.get("name", ""),
                                "type": busline.get("type", ""),
                                "departure_stop": busline.get("departure_stop", {}).get("name", ""),
                                "arrival_stop": busline.get("arrival_stop", {}).get("name", ""),
                                "distance": busline.get("distance", 0),
                                "duration": busline.get("duration", 0),
                            }
                        # 步行信息
                        walking = seg.get("walking", {})
                        if walking and walking.get("distance"):
                            segment_info["walking"] = {
                                "distance": walking.get("distance", 0),
                                "duration": walking.get("duration", 0),
                            }
                        if segment_info:
                            segments.append(segment_info)
                    
                    results.append({
                        "duration": transit.get("duration", 0),
                        "distance": transit.get("distance", 0),
                        "nightflag": transit.get("nightflag", 0),
                        "segments": segments,
                    })
                
                result = {"transits": results, "count": len(results)}
            else:
                result = {"transits": [], "count": 0}
            
            return ToolResult(success=True, data=result)
            
        except Exception as e:
            logger.error(f"公交路线规划失败: {e}")
            return ToolResult(
                success=False,
                error=f"公交路线规划失败: {str(e)}"
            )


class WeatherCurrentTool(AmapBaseTool):
    """当前天气查询工具 - 使用 MCP Server"""
    
    @property
    def name(self) -> str:
        return "weather.current"
    
    @property
    def description(self) -> str:
        return "查询指定城市的当前天气信息"
    
    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "城市编码或名称"
                }
            },
            "required": ["city"]
        }
    
    async def execute(self, **kwargs) -> ToolResult:
        """执行天气查询"""
        city = kwargs.get("city")
        
        # MCP Server 参数格式
        mcp_params = {
            "city": city
        }
        
        try:
            data = await self._call_mcp_tool("maps_weather", mcp_params)
            
            lives = data.get("lives", [])
            if lives:
                result = lives[0]
            else:
                result = {"weather": "未知"}
            
            return ToolResult(success=True, data=result)
            
        except Exception as e:
            logger.error(f"天气查询失败: {e}")
            return ToolResult(
                success=False,
                error=f"天气查询失败: {str(e)}"
            )


class SystemGetTimeTool(DeterministicTool):
    """获取当前时间工具"""
    
    @property
    def name(self) -> str:
        return "system.get_time"
    
    @property
    def description(self) -> str:
        return "获取当前系统时间"
    
    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
    
    async def execute(self, **kwargs) -> ToolResult:
        """获取当前时间"""
        try:
            now = datetime.now()
            result = {
                "time": now.isoformat(),
                "weekday": now.strftime("%A")
            }
            return ToolResult(success=True, data=result)
            
        except Exception as e:
            logger.error(f"获取时间失败: {e}")
            return ToolResult(
                success=False,
                error=f"获取时间失败: {str(e)}"
            )
