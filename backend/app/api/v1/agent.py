"""
Agent API 路由 —— 智能体对话接口
"""
import json
import asyncio
import logging
import uuid
from typing import Optional, Literal, List
from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from datetime import datetime
from app.services.chat_history import (
    _ensure_user_id,
    save_chat_message,
    load_chat_history,
    get_user_sessions,
    delete_chat_history,
    _chat_key,
    _index_key
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Agent 智能体"])


# ─── 模型配置 ───

AVAILABLE_MODELS = {
    "providers": [
        {
            "name": "小米",
            "key": "xiaomi",
            "api_key_env": "XIAOMI_API_KEY",
            "base_url": "https://token-plan-cn.xiaomimimo.com/v1",
            "models": [
                {"key": "mimo-v2.5-pro", "label": "MiMo V2.5 Pro"},
                {"key": "mimo-v2.5",     "label": "MiMo V2.5"},
            ],
        },
        {
            "name": "阿里百炼",
            "key": "aliyun",
            "models": [
                {"key": "deepseek-v4-pro", "label": "DeepSeek V4 Pro"},
                {"key": "deepseek-v4-flash",   "label": "DeepSeek V4 Flash"},
                {"key": "qwen3.7-plus",         "label": "Qwen 3.7 Plus"},
                {"key": "glm-5.1",              "label": "GLM 5.1"},
                {"key": "qwen3.6-plus",         "label": "Qwen 3.6 Plus"},
            ],
        },
    ],
}

# 默认模型
DEFAULT_MODEL_CONFIG = {
    "provider": "xiaomi",
    "model": "mimo-v2.5-pro",
}


# ─── 请求/响应模型 ───

class AgentChatRequest(BaseModel):
    message: str                       # 用户消息
    user_id: Optional[str] = None      # 用户ID（支持UUID格式）
    session_id: Optional[str] = None   # 会话ID
    latitude: Optional[float] = None   # 当前纬度
    longitude: Optional[float] = None  # 当前经度
    stream: bool = True                # 是否流式
    model_config: dict = None          # 选中的模型配置 {provider, model}


class AgentChatResponse(BaseModel):
    session_id: str
    reply: str
    intent: Optional[str] = None
    entities: Optional[dict] = None
    actions: list[str] = []
    suggestions: list[str] = []
    results: Optional[dict] = None
    meta: dict = {}


class ChatHistoryItem(BaseModel):
    id: int
    user_id: str
    session_id: str
    message_type: str  # "user" or "assistant"
    content: str
    message_metadata: Optional[dict] = None
    created_at: datetime


class ChatSessionItem(BaseModel):
    session_id: str
    last_message: str
    last_message_time: datetime
    message_count: int


# ─── 获取 Agent 依赖 ───

def get_agent_system(request: Request):
    """从 App state 获取 Agent 系统组件"""
    app = request.app
    return {
        "orchestrator": app.state.agent_orchestrator,
        "mcp_bus": app.state.agent_mcp_bus,
        "skills_engine": app.state.agent_skills_engine,
        "memory_system": app.state.agent_memory_system,
    }


def get_db_session():
    """获取数据库会话"""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_redis_client():
    """获取 Redis 客户端"""
    from app.redis_client import get_redis
    return get_redis()


# 对话历史服务已移至 app.services.chat_history 模块


# ─── 路由 ───

@router.get("/models", summary="获取可用模型列表")
async def get_models():
    """返回所有可用对话模型的分组列表"""
    return AVAILABLE_MODELS


@router.post("/chat", summary="Agent 对话（非流式）")
async def agent_chat(
    req: AgentChatRequest,
    agent: dict = Depends(get_agent_system),
    db_session=Depends(get_db_session),
    redis_client=Depends(get_redis_client),
):
    """处理用户消息，返回 Agent 回复（非流式）"""
    orchestrator = agent["orchestrator"]
    memory = agent["memory_system"]
    
    # 获取用户ID（从请求中或使用默认值）
    user_id = _ensure_user_id(req.user_id)
    
    # 保存本次对话使用的模型配置到 memory
    model_cfg = req.model_config or DEFAULT_MODEL_CONFIG
    if req.session_id and memory:
        await memory.set_working(req.session_id, "model_config", model_cfg)

    # 保存用户消息到历史
    await save_chat_message(
        user_id=user_id,
        session_id=req.session_id or "default",
        message_type="user",
        content=req.message,
        db_session=db_session,
        redis_client=redis_client
    )

    result = await orchestrator.process_message(
        user_id=str(user_id),
        message=req.message,
        session_id=req.session_id,
        latitude=req.latitude,
        longitude=req.longitude,
    )
    
    # 将模型信息注入结果
    result["meta"]["model"] = model_cfg
    
    # 保存AI回复到历史
    await save_chat_message(
        user_id=user_id,
        session_id=result.get("session_id", req.session_id or "default"),
        message_type="assistant",
        content=result.get("reply", ""),
        message_metadata={
            "intent": result.get("intent"),
            "entities": result.get("entities"),
            "actions": result.get("actions", []),
        },
        db_session=db_session,
        redis_client=redis_client
    )
    
    return AgentChatResponse(**result)


@router.post("/chat/stream", summary="Agent 对话（SSE 流式）")
async def agent_chat_stream(
    req: AgentChatRequest,
    agent: dict = Depends(get_agent_system),
    db_session=Depends(get_db_session),
    redis_client=Depends(get_redis_client),
):
    """处理用户消息，返回 SSE 流式 Agent 回复"""
    orchestrator = agent["orchestrator"]
    memory = agent["memory_system"]
    
    # 获取用户ID
    user_id = _ensure_user_id(req.user_id)
    
    # 保存模型配置
    model_cfg = req.model_config or DEFAULT_MODEL_CONFIG
    if req.session_id and memory:
        await memory.set_working(req.session_id, "model_config", model_cfg)

    # 保存用户消息到历史
    await save_chat_message(
        user_id=user_id,
        session_id=req.session_id or "default",
        message_type="user",
        content=req.message,
        db_session=db_session,
        redis_client=redis_client
    )

    async def event_generator():
        full_reply = ""
        session_id = req.session_id or "default"
        
        try:
            async for event in orchestrator.process_message_stream(
                user_id=str(user_id),
                message=req.message,
                session_id=req.session_id,
                latitude=req.latitude,
                longitude=req.longitude,
            ):
                event_name = event.get("event", "content")
                data = event.get("data", {})

                # 收集完整的回复内容
                if event_name == "content" and isinstance(data, dict) and "text" in data:
                    full_reply += data["text"]
                
                # 记录session_id
                if event_name == "done" and isinstance(data, dict) and "session_id" in data:
                    session_id = data["session_id"]

                if isinstance(data, dict):
                    data_str = json.dumps(data, ensure_ascii=False)
                elif isinstance(data, list):
                    data_str = json.dumps(data, ensure_ascii=False)
                else:
                    data_str = str(data)

                yield f"event: {event_name}\ndata: {data_str}\n\n"

            # 流式完成后保存AI回复到历史
            if full_reply:
                await save_chat_message(
                    user_id=user_id,
                    session_id=session_id,
                    message_type="assistant",
                    content=full_reply,
                    message_metadata={"stream": True},
                    db_session=db_session,
                    redis_client=redis_client
                )

        except Exception as e:
            logger.error(f"SSE 流式响应出错: {e}")
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/history", summary="获取对话历史")
async def get_chat_history(
    user_id: str = Query(..., description="用户ID（支持UUID格式）"),
    session_id: Optional[str] = Query(None, description="会话ID"),
    limit: int = Query(50, ge=1, le=200, description="返回消息数量"),
    db_session=Depends(get_db_session),
    redis_client=Depends(get_redis_client),
):
    """获取对话历史记录，优先从Redis加载，降级到MySQL"""
    messages = await load_chat_history(
        user_id=user_id,
        session_id=session_id,
        limit=limit,
        db_session=db_session,
        redis_client=redis_client
    )
    return {"messages": messages}


@router.get("/sessions", summary="获取用户会话列表")
async def get_user_chat_sessions(
    user_id: str = Query(..., description="用户ID（支持UUID格式）"),
    db_session=Depends(get_db_session),
    redis_client=Depends(get_redis_client),
):
    """获取用户的会话列表"""
    sessions = await get_user_sessions(
        user_id=user_id,
        db_session=db_session,
        redis_client=redis_client
    )
    return {"sessions": sessions}


@router.delete("/history/{session_id}", summary="删除对话历史")
async def delete_chat_history(
    session_id: str,
    user_id: str = Query(..., description="用户ID（支持UUID格式）"),
    db_session=Depends(get_db_session),
    redis_client=Depends(get_redis_client),
):
    """删除指定会话的对话历史"""
    user_id = _ensure_user_id(user_id)
    
    # 1. 删除 MySQL 中的记录
    deleted = 0
    try:
        from app.models.chat import ChatHistory
        deleted = db_session.query(ChatHistory).filter(
            ChatHistory.user_id == user_id,
            ChatHistory.session_id == session_id
        ).delete()
        db_session.commit()
        logger.info(f"从MySQL删除对话历史: {deleted} 条")
    except Exception as e:
        logger.error(f"从MySQL删除对话历史失败: {e}")
        db_session.rollback()
    
    # 2. 删除 Redis 缓存
    if redis_client:
        try:
            cache_key = _chat_key(user_id, session_id)
            redis_client.delete(cache_key)
            
            # 更新会话索引
            index_key = _index_key(user_id)
            session_index = redis_client.get(index_key)
            if session_index:
                sessions = json.loads(session_index)
                if session_id in sessions:
                    del sessions[session_id]
                    redis_client.setex(index_key, 86400, json.dumps(sessions, ensure_ascii=False))
        except Exception as e:
            logger.error(f"从Redis删除对话历史失败: {e}")
    
    return {"message": "删除成功", "deleted_count": deleted}


@router.get("/health", summary="Agent 系统健康检查")
async def agent_health(agent: dict = Depends(get_agent_system)):
    """返回 Agent 各组件健康状态"""
    memory = agent["memory_system"]
    return {
        "status": "ok",
        "components": {
            "orchestrator": "ready",
            "mcp_bus": f"{len(agent['mcp_bus'].list_tools())} tools",
            "skills_engine": f"{len(agent['skills_engine'].list_skills())} skills",
            "memory_system": "active" if memory else "disabled",
        }
    }
