"""向量存储服务：支持 NumPy 本地存储和 Milvus 向量数据库

通过 VECTOR_STORE_TYPE 环境变量切换：
- numpy (默认): 基于 NumPy 的轻量实现，持久化到磁盘
- milvus: 使用 Milvus 向量数据库
"""

import json
import logging
import threading
from pathlib import Path
from typing import Any

import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)


# ==================== NumPy 向量存储 ====================

class NumpyVectorStore:
    """基于 NumPy 的向量存储，支持持久化"""

    def __init__(self):
        self.persist_path = Path(settings.chroma_persist_path)
        self.persist_path.mkdir(parents=True, exist_ok=True)

        self._vectors_path = self.persist_path / "vectors.npy"
        self._meta_path = self.persist_path / "metadata.json"

        self._lock = threading.Lock()
        self._ids: list[str] = []
        self._vectors: np.ndarray = np.empty((0, settings.embedding_dim), dtype=np.float32)
        self._documents: list[str] = []
        self._metadatas: list[dict[str, Any]] = []

        self._load()
        logger.info(f"NumpyVectorStore 初始化完成, 已加载 {len(self._ids)} 条向量")

    def _load(self):
        """从磁盘加载持久化数据"""
        if self._vectors_path.exists() and self._meta_path.exists():
            try:
                self._vectors = np.load(self._vectors_path)
                with open(self._meta_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._ids = data["ids"]
                self._documents = data["documents"]
                self._metadatas = data["metadatas"]
                logger.info(f"从磁盘加载 {len(self._ids)} 条向量")
            except Exception as e:
                logger.warning(f"加载向量数据失败，从头开始: {e}")
                self._ids = []
                self._vectors = np.empty((0, settings.embedding_dim), dtype=np.float32)
                self._documents = []
                self._metadatas = []

    def _save(self):
        """持久化到磁盘"""
        np.save(self._vectors_path, self._vectors)
        with open(self._meta_path, "w", encoding="utf-8") as f:
            json.dump({
                "ids": self._ids,
                "documents": self._documents,
                "metadatas": self._metadatas,
            }, f, ensure_ascii=False)

    def add(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict[str, Any]],
    ):
        """批量添加向量"""
        with self._lock:
            existing_id_set = set(self._ids)
            keep_mask = []

            for i, cid in enumerate(ids):
                if cid not in existing_id_set:
                    keep_mask.append(i)

            if not keep_mask:
                logger.info("所有向量已存在，跳过添加")
                return

            filtered_ids = []
            filtered_vectors = []
            filtered_docs = []
            filtered_meta = []

            for i in keep_mask:
                filtered_ids.append(ids[i])
                filtered_vectors.append(embeddings[i])
                filtered_docs.append(documents[i])
                filtered_meta.append(metadatas[i])

            new_vectors = np.array(filtered_vectors, dtype=np.float32)
            if len(self._vectors) == 0:
                self._vectors = new_vectors
            else:
                self._vectors = np.vstack([self._vectors, new_vectors])

            self._ids.extend(filtered_ids)
            self._documents.extend(filtered_docs)
            self._metadatas.extend(filtered_meta)

            self._save()
            logger.info(f"添加 {len(filtered_ids)} 条向量, 总计 {len(self._ids)} 条")

    def query(
        self,
        query_embedding: list[float],
        top_k: int = 50,
        where: dict | None = None,
    ) -> list[dict[str, Any]]:
        """向量检索 (Cosine Similarity)"""
        with self._lock:
            if len(self._vectors) == 0:
                return []

            query_vec = np.array(query_embedding, dtype=np.float32)

            norms = np.linalg.norm(self._vectors, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            normalized = self._vectors / norms

            query_norm = np.linalg.norm(query_vec)
            if query_norm == 0:
                query_norm = 1.0
            query_normalized = query_vec / query_norm

            similarities = normalized @ query_normalized

            if where:
                mask = np.array([
                    all(self._metadatas[i].get(k) == v for k, v in where.items())
                    for i in range(len(self._metadatas))
                ], dtype=bool)
                if not mask.any():
                    return []
                sim_filtered = np.where(mask, similarities, -1.0)
            else:
                sim_filtered = similarities

            k = min(top_k, len(sim_filtered))
            top_indices = np.argsort(sim_filtered)[::-1][:k]

            results = []
            for idx in top_indices:
                if sim_filtered[idx] < 0:
                    continue
                results.append({
                    "chunk_id": self._ids[idx],
                    "content": self._documents[idx],
                    "metadata": self._metadatas[idx],
                    "score": float(sim_filtered[idx]),
                })

            return results

    def delete(self, ids: list[str]):
        """按 ID 删除向量"""
        with self._lock:
            id_set = set(ids)
            keep_mask = [i for i, cid in enumerate(self._ids) if cid not in id_set]

            self._ids = [self._ids[i] for i in keep_mask]
            self._documents = [self._documents[i] for i in keep_mask]
            self._metadatas = [self._metadatas[i] for i in keep_mask]
            if keep_mask:
                self._vectors = self._vectors[keep_mask]
            else:
                self._vectors = np.empty((0, settings.embedding_dim), dtype=np.float32)

            self._save()
            logger.info(f"删除 {len(ids)} 条向量, 剩余 {len(self._ids)} 条")

    def delete_by_doc(self, doc_id: str):
        """按文档 ID 删除所有相关向量"""
        with self._lock:
            keep_mask = [
                i for i, meta in enumerate(self._metadatas)
                if meta.get("doc_id") != doc_id
            ]

            removed = len(self._ids) - len(keep_mask)
            self._ids = [self._ids[i] for i in keep_mask]
            self._documents = [self._documents[i] for i in keep_mask]
            self._metadatas = [self._metadatas[i] for i in keep_mask]
            if keep_mask:
                self._vectors = self._vectors[keep_mask]
            else:
                self._vectors = np.empty((0, settings.embedding_dim), dtype=np.float32)

            self._save()
            logger.info(f"删除文档 {doc_id} 的 {removed} 条向量")

    def count(self) -> int:
        """获取向量总数"""
        return len(self._ids)


# ==================== Milvus 向量存储 ====================

class MilvusVectorStore:
    """基于 Milvus 的向量存储"""

    def __init__(self):
        import warnings
        from pymilvus import (
            connections,
            Collection,
            FieldSchema,
            CollectionSchema,
            DataType,
            utility,
        )

        # 抑制 PyMilvus ORM API 的 deprecation 警告
        warnings.filterwarnings("ignore", message=".*ORM-style PyMilvus API.*")

        self._DataType = DataType
        self._FieldSchema = FieldSchema
        self._CollectionSchema = CollectionSchema
        self._Collection = Collection
        self._utility = utility

        self._host = settings.milvus_host
        self._port = settings.milvus_port
        self._collection_name = settings.milvus_collection_name
        self._dim = settings.embedding_dim

        # 连接 Milvus
        connections.connect(
            alias="default",
            host=self._host,
            port=self._port,
        )
        logger.info(f"Milvus 已连接: {self._host}:{self._port}")

        # 创建或加载 collection
        self._collection = self._get_or_create_collection()
        logger.info(f"MilvusVectorStore 初始化完成, collection={self._collection_name}, "
                    f"entities={self._collection.num_entities}")

    def _get_or_create_collection(self):
        """获取或创建 Milvus collection"""
        if self._utility.has_collection(self._collection_name):
            collection = self._Collection(self._collection_name)
            collection.load()
            logger.info(f"加载已有 collection: {self._collection_name}")
            return collection

        # 定义 schema：chunk_id 作为主键
        fields = [
            self._FieldSchema(name="chunk_id", dtype=self._DataType.VARCHAR,
                              is_primary=True, max_length=64),
            self._FieldSchema(name="embedding", dtype=self._DataType.FLOAT_VECTOR,
                              dim=self._dim),
            self._FieldSchema(name="content", dtype=self._DataType.VARCHAR,
                              max_length=65535),
            self._FieldSchema(name="doc_id", dtype=self._DataType.VARCHAR,
                              max_length=64),
            self._FieldSchema(name="metadata_json", dtype=self._DataType.JSON),
        ]
        schema = self._CollectionSchema(fields, description="RAG knowledge chunks")
        collection = self._Collection(self._collection_name, schema)

        # 创建索引 (AUTOINDEX 自动选择最优索引)
        index_params = {
            "index_type": "AUTOINDEX",
            "metric_type": "COSINE",
        }
        collection.create_index(field_name="embedding", index_params=index_params)
        collection.load()
        logger.info(f"创建新 collection: {self._collection_name}, dim={self._dim}")
        return collection

    def add(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict[str, Any]],
    ):
        """批量添加向量到 Milvus"""
        if not ids:
            return

        # 去重：检查已存在的 chunk_id
        existing_ids: set[str] = set()
        try:
            existing = self._collection.query(
                expr=f'chunk_id in {json.dumps(ids)}',
                output_fields=["chunk_id"],
            )
            existing_ids = {e["chunk_id"] for e in existing}
        except Exception:
            pass

        # 构建插入数据 (row-based: list of dicts)
        data = []
        for i in range(len(ids)):
            if ids[i] in existing_ids:
                continue
            data.append({
                "chunk_id": ids[i],
                "embedding": embeddings[i],
                "content": documents[i][:65535],
                "doc_id": metadatas[i].get("doc_id", ""),
                "metadata_json": metadatas[i],
            })

        if not data:
            logger.info("所有向量已存在，跳过添加")
            return

        self._collection.insert(data)
        self._collection.flush()
        logger.info(f"Milvus 添加 {len(data)} 条向量, "
                    f"总计 {self._collection.num_entities} 条")

    def query(
        self,
        query_embedding: list[float],
        top_k: int = 50,
        where: dict | None = None,
    ) -> list[dict[str, Any]]:
        """Milvus 向量检索 (Cosine Similarity)"""
        if self._collection.num_entities == 0:
            return []

        search_params = {"metric_type": "COSINE", "params": {}}

        # 构建过滤表达式
        expr = None
        if where:
            conditions = []
            for k, v in where.items():
                if isinstance(v, str):
                    conditions.append(f'metadata_json["{k}"] == "{v}"')
                else:
                    conditions.append(f'metadata_json["{k}"] == {v}')
            expr = " && ".join(conditions) if conditions else None

        results = self._collection.search(
            data=[query_embedding],
            anns_field="embedding",
            param=search_params,
            limit=top_k,
            expr=expr,
            output_fields=["chunk_id", "content", "doc_id", "metadata_json"],
        )

        formatted = []
        for hits in results:
            for hit in hits:
                formatted.append({
                    "chunk_id": hit.entity.get("chunk_id"),
                    "content": hit.entity.get("content"),
                    "metadata": hit.entity.get("metadata_json", {}),
                    "score": float(hit.score),
                })

        return formatted

    def delete(self, ids: list[str]):
        """按 chunk_id 删除向量"""
        if not ids:
            return
        expr = f'chunk_id in {json.dumps(ids)}'
        self._collection.delete(expr)
        logger.info(f"Milvus 删除 {len(ids)} 条向量")

    def delete_by_doc(self, doc_id: str):
        """按文档 ID 删除所有相关向量"""
        expr = f'doc_id == "{doc_id}"'
        self._collection.delete(expr)
        logger.info(f"Milvus 删除文档 {doc_id} 的向量")

    def count(self) -> int:
        """获取向量总数"""
        return self._collection.num_entities


# ==================== 工厂函数 ====================

def create_vector_store():
    """根据配置创建向量存储实例"""
    store_type = settings.vector_store_type.lower()
    if store_type == "milvus":
        try:
            return MilvusVectorStore()
        except ImportError as e:
            logger.warning(f"pymilvus 未安装，回退到 NumPy 向量存储: {e}")
            return NumpyVectorStore()
        except Exception as e:
            logger.warning(f"Milvus 连接失败 ({e})，回退到 NumPy 向量存储")
            return NumpyVectorStore()
    else:
        return NumpyVectorStore()


# 模块级单例
vector_store = create_vector_store()
