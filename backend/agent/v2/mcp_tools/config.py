"""
V2 MCP 工具配置

独立配置模块，不依赖 v1 的配置系统。
支持从环境变量或配置文件加载。
"""

import os
from dataclasses import dataclass
from typing import Optional

# 加载 .env 文件（确保 os.getenv 能读到 .env 中的值）
try:
    from dotenv import load_dotenv
    from pathlib import Path
    # 多路径回退查找 .env 文件
    # 从当前文件位置向上查找直到项目根目录
    _current = Path(__file__).resolve().parent
    _env_path = None
    for _ in range(6):  # 最多向上查6级
        _candidate = _current / ".env"
        if _candidate.exists():
            _env_path = _candidate
            break
        _candidate = _current / "backend" / ".env"
        if _candidate.exists():
            _env_path = _candidate
            break
        _current = _current.parent
    
    if _env_path and _env_path.exists():
        load_dotenv(_env_path, override=True)
        import logging
        logging.getLogger(__name__).info(f"已加载环境变量文件: {_env_path}")
    else:
        import logging
        logging.getLogger(__name__).warning("未找到 .env 文件，使用系统环境变量")
except ImportError:
    import logging
    logging.getLogger(__name__).warning(
        "python-dotenv 未安装，无法自动加载 .env 文件。"
        "请安装: pip install python-dotenv"
    )
except Exception as e:
    import logging
    logging.getLogger(__name__).warning(f"加载 .env 文件异常: {e}")


@dataclass
class AmapConfig:
    """高德地图配置"""
    api_key: str = ""
    jsapi_key: str = ""
    jsapi_security_key: str = ""
    
    # 高德官方 MCP Server 端点（Streamable HTTP 方式）
    # 文档：https://lbs.amap.com/api/mcp-server/gettingstarted
    mcp_server_url: str = "https://mcp.amap.com/mcp"
    
    # 默认参数
    default_radius: int = 3000
    default_page_size: int = 20
    request_timeout: int = 15
    
    @classmethod
    def from_env(cls) -> "AmapConfig":
        """从环境变量加载配置"""
        return cls(
            api_key=os.getenv("AMAP_API_KEY", ""),
            jsapi_key=os.getenv("AMAP_JSAPI_KEY", ""),
            jsapi_security_key=os.getenv("AMAP_JSAPI_SECURITY_KEY", ""),
        )
    
    def validate(self) -> bool:
        """验证配置是否有效"""
        return bool(self.api_key)
    
    @property
    def mcp_endpoint(self) -> str:
        """获取带 API Key 的完整 MCP Server 端点 URL"""
        return f"{self.mcp_server_url}?key={self.api_key}"
    
    @property
    def masked_endpoint(self) -> str:
        """获取脱敏后的端点 URL（用于日志输出，隐藏 API Key）"""
        if not self.api_key:
            return f"{self.mcp_server_url}?key="
        # 保留前4位和后4位，中间用 **** 替代
        key = self.api_key
        if len(key) > 8:
            masked_key = key[:4] + "****" + key[-4:]
        else:
            masked_key = "****"
        return f"{self.mcp_server_url}?key={masked_key}"


@dataclass
class TavilyConfig:
    """Tavily 联网搜索配置"""
    api_key: str = ""
    
    # Tavily MCP Server 端点（Streamable HTTP 方式）
    # 文档：https://docs.tavily.com/documentation/mcp
    mcp_server_url: str = "https://mcp.tavily.com/mcp"
    
    # 默认参数
    request_timeout: int = 30
    max_results: int = 5
    
    @classmethod
    def from_env(cls) -> "TavilyConfig":
        """从环境变量加载配置"""
        return cls(
            api_key=os.getenv("TAVILY_API_KEY", ""),
        )
    
    def validate(self) -> bool:
        """验证配置是否有效"""
        return bool(self.api_key)
    
    @property
    def mcp_endpoint(self) -> str:
        """获取带 API Key 的完整 MCP Server 端点 URL"""
        return f"{self.mcp_server_url}?tavilyApiKey={self.api_key}"
    
    @property
    def masked_endpoint(self) -> str:
        """获取脱敏后的端点 URL（用于日志输出，隐藏 API Key）"""
        if not self.api_key:
            return f"{self.mcp_server_url}?tavilyApiKey="
        # 保留前4位和后4位，中间用 **** 替代
        key = self.api_key
        if len(key) > 8:
            masked_key = key[:4] + "****" + key[-4:]
        else:
            masked_key = "****"
        return f"{self.mcp_server_url}?tavilyApiKey={masked_key}"


@dataclass
class MCPToolsConfig:
    """MCP 工具总配置"""
    amap: AmapConfig = None
    tavily: TavilyConfig = None
    
    # 工具开关
    enable_amap_tools: bool = True
    enable_weather_tools: bool = True
    enable_system_tools: bool = True
    enable_tavily_tools: bool = True
    
    # 日志配置
    log_tool_calls: bool = True
    log_level: str = "INFO"
    
    def __post_init__(self):
        if self.amap is None:
            self.amap = AmapConfig.from_env()
        if self.tavily is None:
            self.tavily = TavilyConfig.from_env()
    
    @classmethod
    def from_env(cls) -> "MCPToolsConfig":
        """从环境变量加载配置"""
        return cls(
            amap=AmapConfig.from_env(),
            tavily=TavilyConfig.from_env(),
            enable_amap_tools=os.getenv("ENABLE_AMAP_TOOLS", "true").lower() == "true",
            enable_weather_tools=os.getenv("ENABLE_WEATHER_TOOLS", "true").lower() == "true",
            enable_system_tools=os.getenv("ENABLE_SYSTEM_TOOLS", "true").lower() == "true",
            enable_tavily_tools=os.getenv("ENABLE_TAVILY_TOOLS", "true").lower() == "true",
        )
    
    def validate(self) -> dict:
        """验证配置，返回错误信息"""
        errors = []
        
        if self.enable_amap_tools and not self.amap.validate():
            errors.append("高德地图 API Key 未配置")
        
        if self.enable_tavily_tools and not self.tavily.validate():
            errors.append("Tavily API Key 未配置")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }


# 全局配置实例
_config: Optional[MCPToolsConfig] = None


def get_mcp_tools_config() -> MCPToolsConfig:
    """获取 MCP 工具配置（单例）"""
    global _config
    if _config is None:
        _config = MCPToolsConfig.from_env()
    return _config


def set_mcp_tools_config(config: MCPToolsConfig):
    """设置 MCP 工具配置（用于测试）"""
    global _config
    _config = config


def reset_mcp_tools_config():
    """重置配置（用于测试）"""
    global _config
    _config = None
