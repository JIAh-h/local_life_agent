"""
Agent API 路由 v2 - 使用新的Reactor架构
保持原有API接口不变，内部使用新的ReAct循环引擎
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
    delete_session,
    _chat_key,
    _index_key,
    save_regenerate_version,
    get_round_versions,
    get_round_id_by_message
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Agent 智能体 v2"])


# ─── 模型配置（v2 独立维护，不再依赖 v1 agent 模块） ───

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

DEFAULT_MODEL_CONFIG = {
    "provider": "xiaomi",
    "model": "mimo-v2.5-pro",
}


# ─── 请求/响应模型（保持与v1兼容） ───

class AgentChatRequest(BaseModel):
    """Agent对话请求"""
    message: str                       # 用户消息
    user_id: Optional[str] = None      # 用户ID（支持UUID格式）
    session_id: Optional[str] = None   # 会话ID
    latitude: Optional[float] = None   # 当前纬度
    longitude: Optional[float] = None  # 当前经度
    address: Optional[str] = None      # 当前地址（用于注入系统提示词）
    city: Optional[str] = None         # 当前城市（用于注入系统提示词）
    district: Optional[str] = None     # 当前区/县
    stream: bool = True                # 是否流式
    model_config: dict = None          # 选中的模型配置 {provider, model}


class AgentChatResponse(BaseModel):
    """Agent对话响应"""
    session_id: str
    reply: str
    intent: Optional[str] = None
    entities: Optional[dict] = None
    actions: list[str] = []
    suggestions: list[str] = []
    results: Optional[dict] = None
    meta: dict = {}


class ChatHistoryItem(BaseModel):
    """对话历史项"""
    id: int
    user_id: str
    session_id: str
    message_type: str  # "user" or "assistant"
    content: str
    message_metadata: Optional[dict] = None
    created_at: datetime


class ChatSessionItem(BaseModel):
    """会话项"""
    session_id: str
    last_message: str
    last_message_time: datetime
    message_count: int


# ─── 获取依赖 ───

def get_reactor_instance(request: Request):
    """从 App state 获取 Reactor 实例"""
    app = request.app
    return app.state.reactor


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


# ─── API路由 ───

@router.post("/chat", response_model=AgentChatResponse)
async def agent_chat(
    request: AgentChatRequest,
    reactor=Depends(get_reactor_instance),
    db_session=Depends(get_db_session),
    redis_client=Depends(get_redis_client)
):
    """
    Agent对话接口（非流式）
    
    保持与v1接口完全兼容，内部使用新的Reactor
    """
    user_id = _ensure_user_id(request.user_id)
    session_id = request.session_id or f"sess_{uuid.uuid4().hex[:12]}"
    
    # 构建位置信息
    location = None
    if request.latitude and request.longitude:
        location = {
            "latitude": request.latitude,
            "longitude": request.longitude,
            "address": request.address or "",
            "city": request.city or "",
            "district": request.district or "",
        }
    
    # 使用Reactor处理消息
    model_cfg = request.model_config or DEFAULT_MODEL_CONFIG
    result = await reactor.process_message(
        user_message=request.message,
        session_id=session_id,
        user_id=user_id,
        location=location,
        stream=False,
        provider=model_cfg.get("provider"),
        model=model_cfg.get("model")
    )
    
    # 保存对话历史
    await save_chat_message(
        user_id=user_id,
        session_id=session_id,
        message_type="user",
        content=request.message,
        db_session=db_session,
        redis_client=redis_client
    )
    
    await save_chat_message(
        user_id=user_id,
        session_id=session_id,
        message_type="assistant",
        content=result.get("reply", ""),
        message_metadata={
            "intent": result.get("intent"),
            "entities": result.get("entities"),
            "actions": result.get("actions"),
        },
        db_session=db_session,
        redis_client=redis_client
    )
    
    return AgentChatResponse(**result)


@router.post("/chat/stream")
async def agent_chat_stream(
    request: AgentChatRequest,
    reactor=Depends(get_reactor_instance),
    db_session=Depends(get_db_session),
    redis_client=Depends(get_redis_client)
):
    """
    Agent对话接口（流式SSE）
    
    保持与v1接口完全兼容，内部使用新的Reactor
    """
    user_id = _ensure_user_id(request.user_id)
    session_id = request.session_id or f"sess_{uuid.uuid4().hex[:12]}"
    
    # 构建位置信息
    location = None
    if request.latitude and request.longitude:
        location = {
            "latitude": request.latitude,
            "longitude": request.longitude,
            "address": request.address or "",
            "city": request.city or "",
            "district": request.district or "",
        }
    
    async def event_generator():
        """SSE事件生成器"""
        full_reply = ""
        round_id = f"{session_id}_{uuid.uuid4().hex[:12]}"
        
        try:
            # 使用Reactor处理消息（流式）
            # process_message是async函数，stream=True时返回async generator，需先await
            model_cfg = request.model_config or DEFAULT_MODEL_CONFIG
            async for event in await reactor.process_message(
                user_message=request.message,
                session_id=session_id,
                user_id=user_id,
                location=location,
                stream=True,
                provider=model_cfg.get("provider"),
                model=model_cfg.get("model")
            ):
                event_type = event.get("event", "message")
                event_data = event.get("data", {})
                
                # 收集完整回复
                if event_type == "content":
                    full_reply += event_data.get("text", "")
                
                # 拦截 done 事件，注入 round_id，然后保存消息
                if event_type == "done":
                    # 注入 round_id，让前端能正确关联轮次
                    event_data["round_id"] = round_id
                    # 保存对话历史
                    await save_chat_message(
                        user_id=user_id,
                        session_id=session_id,
                        message_type="user",
                        content=request.message,
                        round_id=round_id,
                        db_session=db_session,
                        redis_client=redis_client
                    )
                    await save_chat_message(
                        user_id=user_id,
                        session_id=session_id,
                        message_type="ai",
                        content=full_reply,
                        round_id=round_id,
                        db_session=db_session,
                        redis_client=redis_client
                    )
                
                # 发送SSE事件
                yield f"event: {event_type}\ndata: {json.dumps(event_data, ensure_ascii=False)}\n\n"
            
        except Exception as e:
            logger.error(f"流式处理失败: {e}", exc_info=True)
            error_data = {"message": "抱歉，处理您的请求时遇到了问题。", "error": str(e)}
            yield f"event: error\ndata: {json.dumps(error_data, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/history", summary="获取对话历史")
async def get_chat_history(
    user_id: str = Query(..., description="用户ID（支持UUID格式）"),
    session_id: Optional[str] = Query(None, description="会话ID"),
    limit: int = Query(50, ge=1, le=200, description="返回条数"),
    db_session=Depends(get_db_session),
    redis_client=Depends(get_redis_client)
):
    """获取对话历史"""
    messages = await load_chat_history(
        user_id=user_id,
        session_id=session_id,
        limit=limit,
        db_session=db_session,
        redis_client=redis_client
    )
    
    return {
        "user_id": user_id,
        "session_id": session_id,
        "messages": messages,
        "total": len(messages)
    }


@router.get("/sessions", summary="获取用户会话列表")
async def get_sessions(
    user_id: str = Query(..., description="用户ID（支持UUID格式）"),
    db_session=Depends(get_db_session),
    redis_client=Depends(get_redis_client)
):
    """获取用户的所有会话"""
    sessions = await get_user_sessions(
        user_id=user_id,
        db_session=db_session,
        redis_client=redis_client
    )
    
    return {
        "user_id": user_id,
        "sessions": sessions,
        "total": len(sessions)
    }


@router.post("/regenerate", summary="重新生成AI回复")
async def regenerate_reply(
    request: Request,
    reactor=Depends(get_reactor_instance),
    db_session=Depends(get_db_session),
    redis_client=Depends(get_redis_client)
):
    """
    重新生成指定轮次的AI回复
    
    请求体:
    {
        "user_id": "xxx",
        "session_id": "xxx",
        "round_id": "xxx",  // 要重新生成的轮次ID
        "latitude": 22.5,
        "longitude": 114.0,
        "stream": true,
        "model_config": {...}
    }
    
    流程:
    1. 根据 round_id 找到对应的用户消息
    2. 调用 reactor 重新生成回复
    3. 保存新版本到数据库（version + 1）
    """
    body = await request.json()
    
    user_id = _ensure_user_id(body.get("user_id"))
    session_id = body.get("session_id")
    round_id = body.get("round_id")
    stream = body.get("stream", True)
    model_config = body.get("model_config")
    
    if not round_id:
        return {"error": "缺少 round_id 参数"}
    
    # 获取该轮次的所有版本，找到用户消息
    versions = await get_round_versions(user_id, round_id, db_session)
    if not versions:
        return {"error": "未找到该轮次记录"}
    
    # 从数据库获取用户消息
    from app.models.chat import ChatHistory
    user_message_record = db_session.query(ChatHistory).filter(
        ChatHistory.round_id == round_id,
        ChatHistory.message_type == "user"
    ).first()
    
    if not user_message_record:
        return {"error": "未找到对应的用户消息"}
    
    user_message = user_message_record.content
    
    # 构建位置信息
    location = None
    latitude = body.get("latitude")
    longitude = body.get("longitude")
    if latitude and longitude:
        location = {
            "latitude": latitude,
            "longitude": longitude,
            "address": body.get("address", ""),
            "city": body.get("city", ""),
            "district": body.get("district", ""),
        }
    
    if stream:
        async def event_generator():
            """流式重新生成"""
            full_reply = ""
            model_cfg = model_config or DEFAULT_MODEL_CONFIG
            
            try:
                async for event in await reactor.process_message(
                    user_message=user_message,
                    session_id=session_id,
                    user_id=user_id,
                    location=location,
                    stream=True,
                    provider=model_cfg.get("provider"),
                    model=model_cfg.get("model")
                ):
                    event_type = event.get("event", "message")
                    event_data = event.get("data", {})
                    
                    if event_type == "content":
                        full_reply += event_data.get("text", "")
                    
                    # 拦截 done 事件，注入版本信息并保存
                    if event_type == "done":
                        # 保存新版本
                        result = await save_regenerate_version(
                            user_id=user_id,
                            session_id=session_id,
                            round_id=round_id,
                            content=full_reply,
                            db_session=db_session,
                            redis_client=redis_client
                        )
                        # 注入版本信息
                        event_data["round_id"] = round_id
                        event_data["version"] = result["version"]
                    
                    yield f"event: {event_type}\ndata: {json.dumps(event_data, ensure_ascii=False)}\n\n"
                
            except Exception as e:
                logger.error(f"重新生成失败: {e}", exc_info=True)
                yield f"event: error\ndata: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
        
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    else:
        # 非流式
        model_cfg = model_config or DEFAULT_MODEL_CONFIG
        result = await reactor.process_message(
            user_message=user_message,
            session_id=session_id,
            user_id=user_id,
            location=location,
            stream=False,
            provider=model_cfg.get("provider"),
            model=model_cfg.get("model")
        )
        
        # 保存新版本
        version_result = await save_regenerate_version(
            user_id=user_id,
            session_id=session_id,
            round_id=round_id,
            content=result.get("reply", ""),
            db_session=db_session,
            redis_client=redis_client
        )
        
        return {
            "session_id": session_id,
            "round_id": round_id,
            "version": version_result["version"],
            **result
        }


@router.get("/versions/{round_id}", summary="获取指定轮次的所有版本")
async def get_versions(
    round_id: str,
    user_id: str = Query(..., description="用户ID（支持UUID格式）"),
    db_session=Depends(get_db_session)
):
    """获取指定轮次的所有AI回复版本"""
    versions = await get_round_versions(user_id, round_id, db_session)
    
    return {
        "round_id": round_id,
        "versions": versions,
        "total": len(versions)
    }


@router.delete("/history/{session_id}", summary="删除对话历史")
async def delete_session(
    session_id: str,
    user_id: str = Query(..., description="用户ID（支持UUID格式）"),
    db_session=Depends(get_db_session),
    redis_client=Depends(get_redis_client)
):
    """删除指定会话的全部对话记录（MySQL + Redis 双清）"""
    user_id = _ensure_user_id(user_id)
    deleted_count = 0

    # 1. 删除 MySQL 中的记录
    try:
        from app.models.chat import ChatHistory
        deleted_count = db_session.query(ChatHistory).filter(
            ChatHistory.user_id == user_id,
            ChatHistory.session_id == session_id
        ).delete()
        db_session.commit()
        logger.info(f"从MySQL删除会话 {session_id}: {deleted_count} 条")
    except Exception as e:
        logger.error(f"从MySQL删除会话 {session_id} 失败: {e}")
        db_session.rollback()
        return {"message": "数据库删除失败", "error": str(e)}

    # 2. 删除 Redis 缓存（会话消息体）
    if redis_client:
        try:
            cache_key = f"chat:assistant:{user_id}:{session_id}"
            redis_client.delete(cache_key)
        except Exception as e:
            logger.error(f"从Redis删除缓存 {session_id} 失败: {e}")

    # 3. 更新 Redis 会话索引
    if redis_client:
        try:
            index_key = f"chat:assistant:index:{user_id}"
            session_index = redis_client.get(index_key)
            if session_index:
                sessions = json.loads(session_index)
                if session_id in sessions:
                    del sessions[session_id]
                    redis_client.setex(index_key, 86400, json.dumps(sessions, ensure_ascii=False))
        except Exception as e:
            logger.error(f"从Redis更新索引 {session_id} 失败: {e}")

    return {"message": "会话已删除", "session_id": session_id, "deleted_count": deleted_count}


@router.get("/models")
async def get_available_models():
    """获取可用模型列表"""
    return AVAILABLE_MODELS


@router.get("/health", summary="健康检查")
async def health_check():
    """
    健康检查端点
    
    返回系统健康状态，用于负载均衡器和监控系统
    """
    try:
        # 检查Redis连接
        from app.redis_client import get_redis
        redis_client = get_redis()
        redis_ping = redis_client.ping() if redis_client else False
        
        # 检查数据库连接
        from app.database import SessionLocal
        db_status = False
        try:
            db = SessionLocal()
            try:
                from sqlalchemy import text
                db.execute(text("SELECT 1"))
                db_status = True
            except Exception:
                db_status = False
            finally:
                db.close()
        except Exception:
            db_status = False
        
        # 检查Reactor状态
        from agent.v2.metrics import get_metrics_collector
        reactor_status = True
        try:
            metrics = get_metrics_collector()
            health_status = metrics.get_health_status()
            reactor_status = health_status.get("status") == "healthy"
        except Exception:
            reactor_status = False
        
        # 整体健康状态
        is_healthy = redis_ping and db_status and reactor_status
        
        return {
            "status": "healthy" if is_healthy else "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "components": {
                "redis": "ok" if redis_ping else "error",
                "database": "ok" if db_status else "error",
                "reactor": "ok" if reactor_status else "error"
            }
        }
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return {
            "status": "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }


@router.get("/status", summary="系统状态")
async def system_status(
    reactor=Depends(get_reactor_instance)
):
    """
    系统状态API
    
    返回详细的系统运行状态，包括：
    - 系统信息
    - 组件状态
    - 性能指标
    """
    try:
        # 获取指标收集器
        from agent.v2.metrics import get_metrics_collector
        metrics = get_metrics_collector()
        
        # 获取健康状态
        health_status = metrics.get_health_status()
        
        # 获取所有指标
        all_metrics = metrics.get_all_metrics()
        
        # 系统信息
        import platform
        import psutil
        
        system_info = {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "cpu_count": psutil.cpu_count(),
            "memory_total": psutil.virtual_memory().total,
            "memory_available": psutil.virtual_memory().available,
            "memory_percent": psutil.virtual_memory().percent
        }
        
        return {
            "status": "ok",
            "timestamp": datetime.now().isoformat(),
            "system": system_info,
            "health": health_status,
            "metrics": all_metrics
        }
    except Exception as e:
        logger.error(f"获取系统状态失败: {e}")
        return {
            "status": "error",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }


@router.get("/metrics", summary="系统指标")
async def system_metrics():
    """
    系统指标API
    
    返回系统运行指标，格式兼容Prometheus
    """
    try:
        from agent.v2.metrics import get_metrics_collector
        metrics = get_metrics_collector()
        
        # 获取所有指标
        all_metrics = metrics.get_all_metrics()
        
        # 转换为Prometheus格式
        prometheus_metrics = []
        
        # 工具调用指标
        prometheus_metrics.append(f"# HELP agent_tool_calls_total Total number of tool calls")
        prometheus_metrics.append(f"# TYPE agent_tool_calls_total counter")
        prometheus_metrics.append(f"agent_tool_calls_total {all_metrics['tool_calls']['total']}")
        
        prometheus_metrics.append(f"# HELP agent_tool_calls_success_total Total number of successful tool calls")
        prometheus_metrics.append(f"# TYPE agent_tool_calls_success_total counter")
        prometheus_metrics.append(f"agent_tool_calls_success_total {all_metrics['tool_calls']['success']}")
        
        prometheus_metrics.append(f"# HELP agent_tool_calls_failed_total Total number of failed tool calls")
        prometheus_metrics.append(f"# TYPE agent_tool_calls_failed_total counter")
        prometheus_metrics.append(f"agent_tool_calls_failed_total {all_metrics['tool_calls']['failed']}")
        
        # LLM调用指标
        prometheus_metrics.append(f"# HELP agent_llm_calls_total Total number of LLM calls")
        prometheus_metrics.append(f"# TYPE agent_llm_calls_total counter")
        prometheus_metrics.append(f"agent_llm_calls_total {all_metrics['llm_calls']['total']}")
        
        prometheus_metrics.append(f"# HELP agent_llm_tokens_used_total Total number of LLM tokens used")
        prometheus_metrics.append(f"# TYPE agent_llm_tokens_used_total counter")
        prometheus_metrics.append(f"agent_llm_tokens_used_total {all_metrics['llm_calls']['tokens_used']}")
        
        # 会话指标
        prometheus_metrics.append(f"# HELP agent_active_sessions Number of active sessions")
        prometheus_metrics.append(f"# TYPE agent_active_sessions gauge")
        prometheus_metrics.append(f"agent_active_sessions {all_metrics['sessions']['active']}")
        
        prometheus_metrics.append(f"# HELP agent_messages_processed_total Total number of messages processed")
        prometheus_metrics.append(f"# TYPE agent_messages_processed_total counter")
        prometheus_metrics.append(f"agent_messages_processed_total {all_metrics['sessions']['messages_processed']}")
        
        # 错误指标
        prometheus_metrics.append(f"# HELP agent_errors_total Total number of errors")
        prometheus_metrics.append(f"# TYPE agent_errors_total counter")
        prometheus_metrics.append(f"agent_errors_total {all_metrics['errors']['total']}")
        
        # 延迟指标
        tool_duration_stats = all_metrics['tool_calls']['duration']
        prometheus_metrics.append(f"# HELP agent_tool_call_duration_seconds Tool call duration in seconds")
        prometheus_metrics.append(f"# TYPE agent_tool_call_duration_seconds summary")
        prometheus_metrics.append(f"agent_tool_call_duration_seconds_count {tool_duration_stats['count']}")
        prometheus_metrics.append(f"agent_tool_call_duration_seconds_sum {tool_duration_stats['sum']}")
        prometheus_metrics.append(f"agent_tool_call_duration_seconds{{quantile=\"0.5\"}} {tool_duration_stats['p50']}")
        prometheus_metrics.append(f"agent_tool_call_duration_seconds{{quantile=\"0.95\"}} {tool_duration_stats['p95']}")
        prometheus_metrics.append(f"agent_tool_call_duration_seconds{{quantile=\"0.99\"}} {tool_duration_stats['p99']}")
        
        llm_duration_stats = all_metrics['llm_calls']['duration']
        prometheus_metrics.append(f"# HELP agent_llm_call_duration_seconds LLM call duration in seconds")
        prometheus_metrics.append(f"# TYPE agent_llm_call_duration_seconds summary")
        prometheus_metrics.append(f"agent_llm_call_duration_seconds_count {llm_duration_stats['count']}")
        prometheus_metrics.append(f"agent_llm_call_duration_seconds_sum {llm_duration_stats['sum']}")
        prometheus_metrics.append(f"agent_llm_call_duration_seconds{{quantile=\"0.5\"}} {llm_duration_stats['p50']}")
        prometheus_metrics.append(f"agent_llm_call_duration_seconds{{quantile=\"0.95\"}} {llm_duration_stats['p95']}")
        prometheus_metrics.append(f"agent_llm_call_duration_seconds{{quantile=\"0.99\"}} {llm_duration_stats['p99']}")
        
        return "\n".join(prometheus_metrics)
    except Exception as e:
        logger.error(f"获取系统指标失败: {e}")
        return f"# Error: {str(e)}"
