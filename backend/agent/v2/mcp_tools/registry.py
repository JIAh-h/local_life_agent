"""
V2 MCP 工具注册器

独立的工具注册器，用于将 MCP 工具注册到 v2 的 ToolRegistry 中。
与 v1 完全解耦，支持动态加载和配置。
"""

import logging
from typing import List, Optional

from ..deterministic import ToolRegistry, DeterministicTool, get_tool_registry
from ..mcp_log import log_mcp_registration, log_mcp_registration_summary
from .config import get_mcp_tools_config, MCPToolsConfig
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

logger = logging.getLogger(__name__)


def _extract_tool_category(tool_name: str) -> str:
    """
    从工具名称中提取类别。
    
    示例:
        "amap.place_around" -> "amap"
        "web.search"        -> "web"
        "system.get_time"   -> "system"
    """
    parts = tool_name.split(".")
    return parts[0] if len(parts) > 1 else "unknown"


class MCPToolRegistry:
    """MCP 工具注册器"""
    
    def __init__(self, config: MCPToolsConfig = None):
        self.config = config or get_mcp_tools_config()
        self._tools: List[DeterministicTool] = []
        self._registered = False
    
    def _create_tools(self) -> List[DeterministicTool]:
        """创建所有 MCP 工具"""
        tools = []
        
        # 高德地图工具
        if self.config.enable_amap_tools:
            tools.extend([
                AmapPlaceAroundTool(),
                AmapRegeocodeTool(),
                AmapDirectionWalkingTool(),
                AmapDirectionBicyclingTool(),
                AmapDirectionDrivingTool(),
                AmapDirectionTransitTool(),
            ])
        
        # 天气工具
        if self.config.enable_weather_tools:
            tools.append(WeatherCurrentTool())
        
        # 系统工具
        if self.config.enable_system_tools:
            tools.append(SystemGetTimeTool())
        
        # Tavily 联网搜索工具
        if self.config.enable_tavily_tools:
            tools.extend([
                TavilySearchTool(),
                TavilyExtractTool(),
            ])
        
        return tools
    
    def register_to(self, tool_registry: ToolRegistry) -> int:
        """
        将 MCP 工具注册到指定的 ToolRegistry
        
        按工具类别分别验证配置，不会因为单个工具配置失败
        而阻止其他工具注册。
        
        Args:
            tool_registry: 目标 ToolRegistry
            
        Returns:
            注册的工具数量
        """
        if self._registered:
            logger.warning("MCP 工具已注册，跳过重复注册")
            return 0
        
        # 预先验证配置（仅记录警告，不阻止注册）
        validation = self.config.validate()
        if not validation["valid"]:
            for err in validation["errors"]:
                logger.warning(f"MCP 工具配置警告（部分工具可能不可用）: {err}")
        
        # 创建工具
        self._tools = self._create_tools()
        total_attempted = len(self._tools)
        
        # 注册工具（结构化日志）
        registered_count = 0
        for tool in self._tools:
            category = _extract_tool_category(tool.name)
            try:
                tool_registry.register(tool)
                registered_count += 1
                # 同时保留原有日志和新增结构化日志
                logger.info(f"注册 MCP 工具: {tool.name}")
                log_mcp_registration(
                    tool_name=tool.name,
                    status="success",
                    tool_category=category,
                    total_registered=registered_count,
                    total_attempted=total_attempted,
                )
            except Exception as e:
                logger.error(f"注册工具 {tool.name} 失败: {e}")
                log_mcp_registration(
                    tool_name=tool.name,
                    status="failure",
                    tool_category=category,
                    error=str(e),
                    total_registered=registered_count,
                    total_attempted=total_attempted,
                )
        
        self._registered = True
        logger.info(f"MCP 工具注册完成: {registered_count}/{total_attempted} 个工具")
        
        # 结构化注册汇总日志
        config_errors = validation["errors"] if not validation["valid"] else None
        log_mcp_registration_summary(
            total_registered=registered_count,
            total_attempted=total_attempted,
            config_valid=validation["valid"],
            config_errors=config_errors,
        )
        
        # 汇总报告已注册工具
        tool_names = self.get_tool_names()
        logger.info(f"已注册的工具列表: {tool_names}")
        
        return registered_count
    
    def get_tools(self) -> List[DeterministicTool]:
        """获取所有 MCP 工具"""
        return self._tools.copy()
    
    def get_tool_names(self) -> List[str]:
        """获取所有工具名称"""
        return [tool.name for tool in self._tools]
    
    def is_registered(self) -> bool:
        """检查是否已注册"""
        return self._registered


# 全局单例
_mcp_tool_registry: Optional[MCPToolRegistry] = None


def get_mcp_tool_registry(config: MCPToolsConfig = None) -> MCPToolRegistry:
    """获取 MCP 工具注册器单例"""
    global _mcp_tool_registry
    if _mcp_tool_registry is None:
        _mcp_tool_registry = MCPToolRegistry(config)
    return _mcp_tool_registry


def reset_mcp_tool_registry():
    """重置 MCP 工具注册器（用于测试）"""
    global _mcp_tool_registry
    _mcp_tool_registry = None


def register_mcp_tools(tool_registry: ToolRegistry = None, config: MCPToolsConfig = None) -> int:
    """
    便捷函数：注册 MCP 工具到 ToolRegistry
    
    Args:
        tool_registry: 目标 ToolRegistry，默认使用全局单例
        config: MCP 工具配置
        
    Returns:
        注册的工具数量
    """
    if tool_registry is None:
        tool_registry = get_tool_registry()
    
    mcp_registry = get_mcp_tool_registry(config)
    return mcp_registry.register_to(tool_registry)
