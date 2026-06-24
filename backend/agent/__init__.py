"""
Agent System — Package Init

当前唯一支持的架构：v2 Thin Harness (ReAct循环引擎)
v1 模块已完全删除，所有路由强制指向 v2。

使用方式：
    from agent.v2 import AgentSystemV2, init_agent_system
    from agent.v2 import get_reactor, ReactorConfig
"""

__version__ = "2.4.0"
__author__ = "Local Life Agent Team"
__architecture__ = "Thin Harness, Fat Skills (ReAct循环引擎)"

# 版本常量（仅保留 v2，v1 已废弃删除）
AGENT_VERSION = "v2"
SUPPORTED_VERSIONS = ["v2"]


def get_agent_version() -> str:
    """获取当前Agent版本（固定为 v2）"""
    return AGENT_VERSION


def get_version_info() -> dict:
    """获取版本信息"""
    return {
        "current_version": AGENT_VERSION,
        "supported_versions": SUPPORTED_VERSIONS,
        "metadata": {
            "version": "2.4.0",
            "architecture": __architecture__,
            "description": "ReAct循环引擎：思考→行动→观察的自主决策模式",
            "core_module": "reactor",
            "memory_system": "增强记忆系统 (滑动窗口 + 智能压缩 + 上下文组装器)",
        }
    }


def get_agent_system_v2():
    """获取v2 AgentSystemV2实例"""
    from .v2 import get_agent_system
    return get_agent_system()


def init_agent_system_v2(
    redis_client=None,
    async_redis_client=None,
    llm_client=None,
    embedding_client=None,
    qdrant_client=None,
    sharded_storage=None,
    config=None,
    skills_dir: str = None,
):
    """初始化v2 AgentSystemV2"""
    from .v2 import init_agent_system
    return init_agent_system(
        redis_client=redis_client,
        async_redis_client=async_redis_client,
        llm_client=llm_client,
        embedding_client=embedding_client,
        qdrant_client=qdrant_client,
        sharded_storage=sharded_storage,
        config=config,
        skills_dir=skills_dir,
    )


__all__ = [
    # 版本管理
    "get_agent_version",
    "get_version_info",
    "AGENT_VERSION",
    "SUPPORTED_VERSIONS",

    # 版本快捷访问
    "get_agent_system_v2",
    "init_agent_system_v2",
]
