from fastapi import APIRouter
from app.api.v1 import auth, location, food, attraction, xiaohongshu, chat, favorites, share, recommend, map as map_router

# 强制使用 Agent v2 路由（v1 已废弃并删除）
from app.api.v1 import agent_v2 as agent_router

api_router = APIRouter()

# 认证路由
api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["用户认证"],
    responses={404: {"description": "Not found"}},
)

# 定位服务路由
api_router.include_router(
    location.router,
    prefix="/location",
    tags=["定位服务"],
    responses={404: {"description": "Not found"}},
)

# 美食推荐路由
api_router.include_router(
    food.router,
    prefix="/food",
    tags=["美食推荐"],
    responses={404: {"description": "Not found"}},
)

# 景点推荐路由
api_router.include_router(
    attraction.router,
    prefix="/attraction",
    tags=["景点推荐"],
    responses={404: {"description": "Not found"}},
)

# 小红书笔记路由
api_router.include_router(
    xiaohongshu.router,
    prefix="/xiaohongshu",
    tags=["小红书笔记"],
    responses={404: {"description": "Not found"}},
)

# 自然语言交互路由
api_router.include_router(
    chat.router,
    prefix="/chat",
    tags=["自然语言交互"],
    responses={404: {"description": "Not found"}},
)

# 收藏管理路由
api_router.include_router(
    favorites.router,
    prefix="/favorites",
    tags=["收藏管理"],
    responses={404: {"description": "Not found"}},
)

# 分享功能路由
api_router.include_router(
    share.router,
    prefix="/share",
    tags=["分享功能"],
    responses={404: {"description": "Not found"}},
)

# 今日推荐路由
api_router.include_router(
    recommend.router,
    prefix="/recommend",
    tags=["今日推荐"],
    responses={404: {"description": "Not found"}},
)

# 高德地图配置路由（密钥安全分发）
api_router.include_router(
    map_router.router,
    prefix="/map",
    tags=["高德地图配置"],
    responses={404: {"description": "Not found"}},
)

# Agent 智能体路由（强制 v2）
api_router.include_router(
    agent_router.router,
    prefix="/agent",
    tags=["智能体"],
    responses={404: {"description": "Not found"}},
)
