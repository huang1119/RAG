"""Embedding 向量化服务：支持 API 和本地模型"""

import logging
from typing import Union

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """统一 Embedding 接口，支持 OpenAI 兼容 API"""

    def __init__(self):
        self.api_base = settings.embedding_api_base.rstrip("/")
        self.api_key = settings.embedding_api_key
        self.model = settings.embedding_model
        self.dim = settings.embedding_dim
        self._client = httpx.AsyncClient(
            base_url=self.api_base,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=60.0,
        )

    async def embed(self, text: str) -> list[float]:
        """生成单条文本的向量"""
        embeddings = await self.embed_batch([text])
        return embeddings[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """批量生成向量"""
        if not texts:
            return []

        results: list[list[float]] = []
        batch_size = 64

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            try:
                resp = await self._client.post(
                    "/embeddings",
                    json={"model": self.model, "input": batch},
                )
                resp.raise_for_status()
                data = resp.json()
                batch_embeddings = [item["embedding"] for item in data["data"]]
                results.extend(batch_embeddings)
            except Exception as e:
                logger.error(f"Embedding API 调用失败: {e}")
                raise

        return results

    async def close(self):
        await self._client.aclose()


embedding_service = EmbeddingService()
