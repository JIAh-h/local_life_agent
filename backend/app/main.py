from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from app.api.v1.router import api_router
from app.config import settings
from app.database import get_db
from app.redis_client import get_redis, get_async_redis, close_async_redis
import logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化 Agent v2 系统，关闭时清理资源"""
    logger.info("[Agent] 正在初始化 Agent v2 系统 (Thin Harness, Fat Skills)...")

    # 1. 初始化共享组件（与 v1 完全解耦）
    from agent.llm_client import llm_client
    from agent.embedding import embedding_service

    # LLM Client（阿里百炼 + 小米 MiMo 双引擎）
    llm_client.configure(
        api_keys={
            "DASHSCOPE_API_KEY": settings.DASHSCOPE_API_KEY,
            "XIAOMI_API_KEY": settings.XIAOMI_API_KEY,
        },
        default_provider="xiaomi",
        default_model="mimo-v2.5-pro",
    )
    app.state.agent_llm_client = llm_client

    # Embedding Service（使用阿里百炼 API）— 共享组件，已从 v1 迁移至 agent 根目录
    embedding_service.api_key = settings.DASHSCOPE_API_KEY
    await embedding_service.initialize()
    app.state.agent_embedding = embedding_service

    # 对话摘要压缩器（使用 LLM 进行智能压缩）— 共享组件，已从 v1 迁移至 agent 根目录
    from agent.conversation_compressor import conversation_compressor
    conversation_compressor.llm_client = llm_client
    app.state.conversation_compressor = conversation_compressor

    # 2. 初始化 Agent v2 系统
    from agent.v2 import init_agent_system, ReactorConfig

    config = ReactorConfig()

    # 获取异步Redis客户端
    async_redis = await get_async_redis()

    # 初始化分片存储（可选，用于水平扩展）
    sharded_storage = None
    try:
        from agent.v2.memory import get_sharded_storage, ShardConfig
        # 默认使用单分片（当前Redis实例）
        default_shard = ShardConfig(
            shard_id="default",
            host="localhost",
            port=6379,
            db=0
        )
        sharded_storage = get_sharded_storage(shards=[default_shard])
        logger.info("[Agent] 分片存储初始化完成")
    except Exception as e:
        logger.warning(f"[Agent] 分片存储初始化失败（不影响核心功能）: {e}")

    # 初始化Agent系统
    # v2 内部自动创建独立的 QdrantManager，不依赖任何 v1 组件
    agent_system = init_agent_system(
        redis_client=get_redis(),
        async_redis_client=async_redis,
        llm_client=llm_client,
        embedding_client=embedding_service,
        qdrant_client=None,  # v2 将自动创建独立 Qdrant 实例
        sharded_storage=sharded_storage,
        config=config
    )

    # 将Reactor存储到app.state
    app.state.reactor = agent_system.reactor
    app.state.agent_system_v2 = agent_system

    system_info = agent_system.get_system_info()
    logger.info(f"[Agent] v2 系统初始化完成: {system_info}")

    yield  # 应用运行中...

    # ─── 关闭：清理资源 ───
    logger.info("[Agent] 正在关闭 Agent v2 系统...")
    # 清理 v2 独立的 Qdrant 管理器
    try:
        from agent.v2.memory import reset_qdrant_manager
        reset_qdrant_manager()
    except Exception as e:
        logger.warning(f"[Agent] 清理 Qdrant 管理器时警告: {e}")
    await close_async_redis()


app = FastAPI(
    title="小紫薯AI Agent API",
    description="基于地理位置的本地生活娱乐AI Agent API",
    version="2.0.0",
    lifespan=lifespan,
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 包含API路由
app.include_router(api_router, prefix="/api/v1")

# ─── 请求体验证错误详情日志（422） ───
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"[422] 请求校验失败: {request.method} {request.url}\n"
                 f"  参数: {dict(request.query_params)}\n"
                 f"  错误: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )

@app.get("/")
async def root():
    return {"message": "小紫薯AI Agent API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
