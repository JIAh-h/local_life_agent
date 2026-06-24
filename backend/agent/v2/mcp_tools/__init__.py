"""
V2 Agent MCP 工具模块

独立实现高德地图 MCP 工具，与 v1 完全解耦。
设计原则：
1. 继承自 v2 的 DeterministicTool 基类
2. 使用独立的配置和 HTTP 客户端
3. 不依赖 v1 的 MCPBus 或任何 v1 代码
4. 支持工具注册和发现
"""

from .amap_tools import (
    AmapPlaceAroundTool,
    AmapRegeocodeTool,
    AmapDirectionWalkingTool,
    AmapDirectionBicyclingTool,
    AmapDirectionDrivingTool,
    AmapDirectionTransitTool,
    WeatherCurrentTool,
    SystemGetTimeTool,
)
from .tavily_tools import TavilySearchTool, TavilyExtractTool
from .registry import MCPToolRegistry, get_mcp_tool_registry

__all__ = [
    # 高德地图工具
    "AmapPlaceAroundTool",
    "AmapRegeocodeTool", 
    "AmapDirectionWalkingTool",
    "AmapDirectionBicyclingTool",
    "AmapDirectionDrivingTool",
    "AmapDirectionTransitTool",
    
    # 天气工具
    "WeatherCurrentTool",
    
    # 系统工具
    "SystemGetTimeTool",
    
    # Tavily 联网搜索工具
    "TavilySearchTool",
    "TavilyExtractTool",
    
    # 注册器
    "MCPToolRegistry",
    "get_mcp_tool_registry",
]
