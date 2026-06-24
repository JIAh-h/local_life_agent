"""
V2 独立的 Qdrant 客户端管理器

与 v1 的 QdrantClientManager 完全解耦，支持：
1. 本地模式（免 Docker，数据存储在磁盘）
2. 远程服务模式（Docker/远程 Qdrant 服务）
3. 自动重连与健康检查

设计原则：
- 零依赖 v1 代码
- 异步优先
- 优雅降级（Qdrant 不可用时不影响核心功能）
"""

import asyncio
import logging
import os
import time
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# 默认本地数据目录（v2 独立目录，不与 v1 共享）
DEFAULT_LOCAL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "data", "qdrant_v2"
)


class QdrantManager:
    """V2 独立的 Qdrant 客户端管理器

    两种运行模式：
    1. local  — 本地嵌入模式，数据存储在磁盘，无需 Docker（推荐开发用）
    2. server — 连接到独立 Qdrant 服务（Docker 或远程，推荐生产用）

    与 v1 QdrantClientManager 的区别：
    - 数据目录独立（data/qdrant_v2 vs data/qdrant）
    - 异步优先设计
    - 支持从环境变量自动配置
    """

    def __init__(
        self,
        mode: str = "local",
        # local 模式参数
        path: str = None,
        # server 模式参数
        host: str = "localhost",
        port: int = 6333,
        grpc_port: int = 6334,
        prefer_grpc: bool = True,
        timeout: int = 5,
    ):
        self.mode = mode
        self.path = path or DEFAULT_LOCAL_PATH
        self.host = host
        self.port = port
        self.grpc_port = grpc_port
        self.prefer_grpc = prefer_grpc
        self.timeout = timeout

        self.sync_client = None
        self.async_client = None
        self._healthy = False
        self._retry_count = 0
        self._max_retries = 3
        self._retry_delay = 1.0

    @classmethod
    def from_env(cls) -> "QdrantManager":
        """从环境变量创建配置"""
        mode = os.getenv("V2_QDRANT_MODE", "local")
        return cls(
            mode=mode,
            path=os.getenv("V2_QDRANT_PATH", DEFAULT_LOCAL_PATH),
            host=os.getenv("V2_QDRANT_HOST", "localhost"),
            port=int(os.getenv("V2_QDRANT_PORT", "6333")),
            grpc_port=int(os.getenv("V2_QDRANT_GRPC_PORT", "6334")),
            prefer_grpc=os.getenv("V2_QDRANT_PREFER_GRPC", "true").lower() == "true",
            timeout=int(os.getenv("V2_QDRANT_TIMEOUT", "5")),
        )

    async def initialize(self) -> bool:
        """初始化客户端

        Returns:
            bool: 初始化是否成功
        """
        try:
            from qdrant_client import QdrantClient, AsyncQdrantClient
        except ImportError:
            logger.warning("[V2 Qdrant] qdrant-client 未安装，向量检索将降级。安装: pip install qdrant-client")
            self._healthy = False
            return False

        try:
            if self.mode == "local":
                return await self._init_local()
            else:
                return await self._init_server()
        except Exception as e:
            logger.warning(f"[V2 Qdrant] 初始化失败: {e}")
            self._healthy = False
            return False

    async def _init_local(self) -> bool:
        """初始化本地嵌入模式"""
        from qdrant_client import QdrantClient

        # 确保数据目录存在
        os.makedirs(self.path, exist_ok=True)

        self.sync_client = QdrantClient(path=self.path)
        # 本地模式暂不支持 AsyncQdrantClient
        self.async_client = None

        # 验证可用性
        self.sync_client.get_collections()
        self._healthy = True
        self._retry_count = 0
        logger.info(f"[V2 Qdrant] 本地模式初始化成功 (数据目录: {self.path})")
        return True

    async def _init_server(self) -> bool:
        """初始化远程服务模式"""
        from qdrant_client import QdrantClient, AsyncQdrantClient

        self.sync_client = QdrantClient(
            host=self.host, port=self.port,
            grpc_port=self.grpc_port, prefer_grpc=self.prefer_grpc,
            timeout=self.timeout,
        )
        self.async_client = AsyncQdrantClient(
            host=self.host, port=self.port,
            grpc_port=self.grpc_port, prefer_grpc=self.prefer_grpc,
            timeout=self.timeout,
        )
        await self.async_client.get_collections()
        self._healthy = True
        self._retry_count = 0
        logger.info(f"[V2 Qdrant] 服务模式初始化成功 ({self.host}:{self.port})")
        return True

    @property
    def is_healthy(self) -> bool:
        """客户端是否健康"""
        return self._healthy

    @property
    def is_local_mode(self) -> bool:
        """是否为本地模式"""
        return self.mode == "local"

    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        result = {
            "healthy": False,
            "mode": self.mode,
            "latency_ms": 0,
            "collections": [],
        }

        if not self.sync_client and not self.async_client:
            return result

        try:
            start = time.time()
            if self.async_client:
                resp = await self.async_client.get_collections()
                collections = [c.name for c in resp.collections]
            else:
                resp = self.sync_client.get_collections()
                collections = [c.name for c in resp.collections]
            elapsed = int((time.time() - start) * 1000)

            result["healthy"] = True
            result["latency_ms"] = elapsed
            result["collections"] = collections
            self._healthy = True
        except Exception as e:
            self._healthy = False
            result["error"] = str(e)

        return result

    async def auto_reconnect(self):
        """自动重连（指数退避）"""
        if self._healthy:
            return

        delay = self._retry_delay * (2 ** self._retry_count)
        self._retry_count = min(self._retry_count + 1, self._max_retries)
        logger.info(f"[V2 Qdrant] 自动重连 (第{self._retry_count}次，等{delay}s)")
        await asyncio.sleep(delay)
        await self.initialize()

    async def close(self):
        """关闭连接"""
        try:
            if self.sync_client:
                self.sync_client.close()
            if self.async_client:
                await self.async_client.close()
            logger.info("[V2 Qdrant] 客户端已关闭")
        except Exception as e:
            logger.error(f"[V2 Qdrant] 关闭连接出错: {e}")


# ─── 全局单例 ───
_qdrant_manager: Optional[QdrantManager] = None


def get_qdrant_manager(**kwargs) -> QdrantManager:
    """获取 Qdrant 管理器单例（自动从环境变量配置）"""
    global _qdrant_manager
    if _qdrant_manager is None:
        _qdrant_manager = QdrantManager.from_env()
    return _qdrant_manager


def create_qdrant_manager(**kwargs) -> QdrantManager:
    """创建新的 Qdrant 管理器实例（非单例，用于测试或特殊配置）"""
    return QdrantManager(**kwargs)


def reset_qdrant_manager():
    """重置全局单例（用于测试）"""
    global _qdrant_manager
    _qdrant_manager = None
