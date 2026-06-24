"""
嵌入服务 —— 文本向量化（阿里百炼 DashScope API）
模型: tongyi-embedding-vision-plus-2026-03-06
说明：该模型为多模态模型，须使用 MultiModalEmbedding 接口

此模块为共享组件，供 Agent v2 及应用层使用，与已废弃的 v1 模块完全解耦。
"""
import logging
import asyncio

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "tongyi-embedding-vision-plus-2026-03-06"


class EmbeddingService:
    """文本向量化服务（通过阿里百炼 DashScope MultiModalEmbedding API）"""

    def __init__(self, model_name: str = None, api_key: str = ""):
        self.model_name = model_name or DEFAULT_MODEL
        self.api_key = api_key
        self._cache: dict[str, list[float]] = {}
        self._initialized = False
        self._zero_vector_count = 0  # 【诊断】连续零向量计数器

    async def initialize(self):
        """初始化（验证 API key 有效性）"""
        if self._initialized:
            return

        if not self.api_key:
            logger.warning("阿里百炼 API Key 未配置，嵌入服务将降级返回零向量")
            self._initialized = True
            return

        try:
            import dashscope

            dashscope.api_key = self.api_key

            # 验证调用
            resp = dashscope.MultiModalEmbedding.call(
                model=self.model_name,
                input=[{"text": "验证"}],
            )
            if resp.status_code == 200:
                self._initialized = True
                logger.info(f"阿里百炼嵌入服务初始化成功 (model: {self.model_name})")
            else:
                logger.warning(f"阿里百炼 API 验证失败: {resp.code} {resp.message}")
                self._initialized = True

        except ImportError:
            logger.warning("dashscope SDK 未安装。安装: pip install dashscope")
            self._initialized = True
        except Exception as e:
            logger.warning(f"阿里百炼 API 连接异常: {e}")
            self._initialized = True

    async def embed(self, text: str) -> list[float]:
        """单文本 → 向量"""
        if not text or not text.strip():
            return [0.0] * 1152

        if text in self._cache:
            return self._cache[text]

        vec = await self._call_api(text)
        if vec:
            self._cache[text] = vec
            return vec

        # 【诊断】连续返回零向量时日志聚合报警
        self._zero_vector_count += 1
        if self._zero_vector_count >= 5:
            logger.error(f"嵌入服务连续 {self._zero_vector_count} 次返回零向量，"
                         f"向量聚类可能已坍缩！请检查 DashScope API Key 状态及网络连接")
        logger.warning(f"嵌入 API 调用失败，返回零向量 (累计: {self._zero_vector_count})")
        return [0.0] * 1152

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """批量文本 → 向量"""
        if not texts:
            return []

        uncached = [t for t in texts if t and t not in self._cache]
        if uncached:
            vecs = await self._call_api_batch(uncached)
            if vecs:
                for t, v in zip(uncached, vecs):
                    self._cache[t] = v
            else:
                for t in uncached:
                    # 【诊断】批量回退零向量时记录
                    self._zero_vector_count += 1
                    self._cache[t] = [0.0] * 1152

        if self._zero_vector_count > 0:
            logger.warning(f"当前会话累计零向量回退 {self._zero_vector_count} 次")

        return [self._cache.get(t, [0.0] * 1152) for t in texts]

    def _call_single_sync(self, text: str) -> list[float]:
        """同步调用 MultiModalEmbedding（单条）"""
        import dashscope
        dashscope.api_key = self.api_key

        resp = dashscope.MultiModalEmbedding.call(
            model=self.model_name,
            input=[{"text": text}],
        )
        if resp.status_code == 200:
            return resp.output.embeddings[0].embedding
        logger.error(f"DashScope API 错误: {resp.code} {resp.message}")
        return None

    def _call_batch_sync(self, texts: list[str]) -> list[list[float]]:
        """同步调用 MultiModalEmbedding（批量）"""
        import dashscope
        dashscope.api_key = self.api_key

        # MultiModalEmbedding 不支持一次传多条，逐条调用
        results = []
        for text in texts:
            resp = dashscope.MultiModalEmbedding.call(
                model=self.model_name,
                input=[{"text": text}],
            )
            if resp.status_code == 200:
                results.append(resp.output.embeddings[0].embedding)
            else:
                logger.error(f"DashScope API 错误: {resp.code} {resp.message}")
                results.append([0.0] * 1152)
        return results

    async def _call_api(self, text: str) -> list[float]:
        try:
            return await asyncio.to_thread(self._call_single_sync, text)
        except Exception as e:
            logger.error(f"嵌入 API 调用异常: {e}")
            return None

    async def _call_api_batch(self, texts: list[str]) -> list[list[float]]:
        try:
            return await asyncio.to_thread(self._call_batch_sync, texts)
        except Exception as e:
            logger.error(f"批量嵌入 API 调用异常: {e}")
            return None

    @property
    def dimension(self) -> int:
        return 1152

    @property
    def is_ready(self) -> bool:
        return self._initialized and bool(self.api_key)


# 全局单例（API key 在 main.py 中设置）
embedding_service = EmbeddingService()
