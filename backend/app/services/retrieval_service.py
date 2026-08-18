"""检索服务：混合检索 (Vector + BM25) + Reranker"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from rank_bm25 import BM25Okapi

from app.config import settings
from app.services.embedding_service import embedding_service
from app.services.vector_store import vector_store

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    chunk_id: str
    content: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


class BM25Index:
    """内存 BM25 索引，用于关键词检索"""

    def __init__(self):
        self._bm25: BM25Okapi | None = None
        self._chunks: list[dict] = []
        self._built = False

    def build(self, chunks: list[dict]):
        """构建 BM25 索引

        Args:
            chunks: [{chunk_id, content, metadata}]
        """
        self._chunks = chunks
        tokenized = [self._tokenize(c["content"]) for c in chunks]
        if tokenized:
            self._bm25 = BM25Okapi(tokenized)
        else:
            self._bm25 = None
        self._built = True
        logger.info(f"BM25 索引构建完成, {len(chunks)} 条")

    def search(self, query: str, top_k: int = 50) -> list[RetrievalResult]:
        if not self._bm25 or not self._chunks:
            return []

        tokens = self._tokenize(query)
        scores = self._bm25.get_scores(tokens)

        top_indices = np.argsort(scores)[::-1][:top_k]
        results = []
        for idx in top_indices:
            if scores[idx] > 0:
                chunk = self._chunks[idx]
                results.append(RetrievalResult(
                    chunk_id=chunk["chunk_id"],
                    content=chunk["content"],
                    score=float(scores[idx]),
                    metadata=chunk.get("metadata", {}),
                ))
        return results

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """分词策略：
        - 中文按单字切分（BM25 对中文单字匹配效果好）
        - 数字/字母编号保持完整（如 26-040、24056、A100-B）
        - 含分隔符的编号同时保留整体和拆分（让 "26-040"
          也能被 "26" 或 "040" 匹配到）
        """
        tokens: list[str] = []
        # Step 1: 按空白/标点/中文标点分割
        parts = re.split(r"[\s,.;:!?\n\r\t，。；：！？、]+", text)
        for part in parts:
            if not part:
                continue

            has_cjk = bool(re.search(r"[一-鿿]", part))
            if has_cjk:
                # Step 2a: 混合文本 → 分离数字/字母编号 和 中文
                sub_parts = re.split(
                    r"([a-zA-Z0-9]+(?:[-./][a-zA-Z0-9]+)*)", part
                )
                for sp in sub_parts:
                    if not sp:
                        continue
                    if re.match(r"^[a-zA-Z0-9]+(?:[-./][a-zA-Z0-9]+)*$", sp):
                        # 数字/字母编号 → 保留整体
                        tokens.append(sp.lower())
                        # 含分隔符 → 额外拆出各部分（方便部分匹配）
                        for sub in re.split(r"[-./]", sp):
                            if sub and len(sub) >= 2:
                                tokens.append(sub.lower())
                    else:
                        # 中文 → 按字切分
                        tokens.extend(list(sp))
            else:
                # Step 2b: 纯英文/数字 → 保留整体
                tokens.append(part.lower())
                # 含分隔符的编号 → 额外拆出各部分
                if re.search(r"[-./]", part):
                    for sub in re.split(r"[-./]", part):
                        if sub and len(sub) >= 2:
                            tokens.append(sub.lower())

        return tokens

    @property
    def is_built(self) -> bool:
        return self._built


bm25_index = BM25Index()


class RetrievalService:
    """混合检索服务"""

    def __init__(self):
        self.vector_weight = settings.vector_search_weight
        self.bm25_weight = settings.bm25_search_weight

    async def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        where: dict | None = None,
    ) -> list[RetrievalResult]:
        """混合检索：Vector + BM25 + RRF 融合

        Args:
            query: 用户查询
            top_k: 返回数量
            where: 元数据过滤条件

        Returns:
            排序后的检索结果列表
        """
        k = top_k or settings.retrieval_top_k

        query_embedding = await embedding_service.embed(query)

        vec_results = vector_store.query(
            query_embedding=query_embedding,
            top_k=k * 2,
            where=where,
        )

        bm25_results = bm25_index.search(query, k * 2)

        fused = self._rrf_merge(vec_results, bm25_results)

        if settings.reranker_enabled:
            fused = await self._rerank(query, fused)

        return fused[: k if top_k else settings.rerank_top_k]

    def _rrf_merge(
        self,
        vec_results: list[dict],
        bm25_results: list[RetrievalResult],
        rrf_k: int = 60,
    ) -> list[RetrievalResult]:
        """Reciprocal Rank Fusion 融合排序

        使用 RRF 分数仅用于**排序**，每个结果保留其原始最高分
        （向量相似度或 BM25 分），不覆盖为 RRF 分。
        这样下游的阈值判断（如 web search fallback）才能正确工作。
        """
        rrf_scores: dict[str, float] = {}
        best_original_score: dict[str, float] = {}
        chunk_map: dict[str, RetrievalResult] = {}

        for rank, item in enumerate(vec_results):
            cid = item["chunk_id"]
            rrf = self.vector_weight / (rrf_k + rank + 1)
            rrf_scores[cid] = rrf_scores.get(cid, 0) + rrf
            best_original_score[cid] = max(
                best_original_score.get(cid, 0), item["score"]
            )
            chunk_map[cid] = RetrievalResult(
                chunk_id=cid,
                content=item["content"],
                score=item["score"],
                metadata=item.get("metadata", {}),
            )

        for rank, item in enumerate(bm25_results):
            cid = item.chunk_id
            rrf = self.bm25_weight / (rrf_k + rank + 1)
            rrf_scores[cid] = rrf_scores.get(cid, 0) + rrf
            best_original_score[cid] = max(
                best_original_score.get(cid, 0), item.score
            )
            if cid not in chunk_map:
                chunk_map[cid] = item

        # 用 RRF 分数排序，但保留原始最高分作为 score
        sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
        results = []
        for cid in sorted_ids:
            r = chunk_map[cid]
            # 保留原始分数（向量相似度/BM25分），用于下游阈值判断
            r.score = best_original_score[cid]
            results.append(r)

        return results

    async def _rerank(
        self,
        query: str,
        candidates: list[RetrievalResult],
    ) -> list[RetrievalResult]:
        """使用 Cross-Encoder 重排序"""
        try:
            from sentence_transformers import CrossEncoder

            if not hasattr(self, "_reranker_model"):
                self._reranker_model = CrossEncoder(settings.reranker_model)

            pairs = [(query, c.content) for c in candidates[:50]]
            scores = self._reranker_model.predict(pairs)

            for i, score in enumerate(scores):
                candidates[i].score = float(score)

            candidates.sort(key=lambda x: x.score, reverse=True)
            logger.info(f"Reranker 完成, {len(candidates)} 条候选重排序")
        except ImportError:
            logger.warning("sentence-transformers 未安装, 跳过重排序")
        except Exception as e:
            logger.error(f"重排序失败: {e}")

        return candidates


retrieval_service = RetrievalService()
