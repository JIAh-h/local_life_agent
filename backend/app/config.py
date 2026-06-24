from pydantic_settings import BaseSettings
from typing import List
import os

class Settings(BaseSettings):
    # 应用配置
    APP_NAME: str = "小紫薯AI Agent"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = True
    
    # Agent版本固定为 v2（v1 已废弃删除）
    AGENT_VERSION: str = "v2"
    
    # 数据库配置
    DATABASE_URL: str = "mysql://root:password@localhost:3306/tianyan_life"
    DB_ECHO: bool = False
    
    # Redis配置 - 指定使用db3存储Token
    REDIS_URL: str = "redis://localhost:6379/3"
    
    # JWT双令牌配置
    SECRET_KEY: str = "your-secret-key-here"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30  # Access Token过期时间：30分钟
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7  # Refresh Token过期时间：7天
    
    # CORS配置
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:5174", "http://localhost:3000"]
    
    # 高德地图 API Key（复用该 Key 调用天气服务，无需额外配置）
    AMAP_API_KEY: str = ""
    AMAP_JSAPI_KEY: str = ""  # 高德地图 JSAPI Key（前端使用）
    AMAP_JSAPI_SECURITY_KEY: str = ""  # 高德地图 JSAPI 安全密钥（前端使用）
    BAIDU_MAP_API_KEY: str = ""  # 百度地图API Key
    XHS_API_KEY: str = ""  # 小红书API Key
    DASHSCOPE_API_KEY: str = ""  # 阿里百炼平台 API Key（用于 embedding 向量化）
    XIAOMI_API_KEY: str = ""  # 小米科技对话模型 API Key
    # 天气服务已集成至高德MCP，复用 AMAP_API_KEY，无需单独配置
    
    # 分页配置
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "allow"  # 允许加载未在类中声明的环境变量

settings = Settings()
