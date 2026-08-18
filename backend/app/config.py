"""应用配置管理"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 应用
    app_name: str = "RAG Knowledge QA"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    secret_key: str = "change-this-to-a-random-secret-key-at-least-32-chars"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # 数据库
    database_url: str = "sqlite+aiosqlite:///./data/rag.db"

    # LLM
    llm_api_base: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"

    # Embedding
    embedding_provider: str = "api"
    embedding_api_base: str = "https://api.openai.com/v1"
    embedding_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536

    # 向量数据库
    vector_store_type: str = "numpy"  # numpy 或 milvus
    chroma_persist_path: str = "./data/chroma"  # numpy 向量存储持久化路径
    chroma_collection_name: str = "knowledge_chunks"

    # Milvus 配置（vector_store_type=milvus 时生效）
    milvus_host: str = "localhost"
    milvus_port: int = 19530
    milvus_collection_name: str = "knowledge_chunks"

    # 文档处理
    upload_dir: str = "./data/uploads"
    chunk_size: int = 512
    chunk_overlap: int = 64
    max_file_size_mb: int = 50

    # 检索
    retrieval_top_k: int = 50
    rerank_top_k: int = 10
    vector_search_weight: float = 0.6
    bm25_search_weight: float = 0.4

    # Reranker
    reranker_enabled: bool = False
    reranker_model: str = "BAAI/bge-reranker-v2-m3"

    # 网络搜索
    web_search_enabled: bool = True
    web_search_max_results: int = 5
    web_search_score_threshold: float = 0.15  # 知识库最高分低于此值时触发网络搜索

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    cache_enabled: bool = False

    @property
    def upload_path(self) -> Path:
        p = Path(self.upload_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def chroma_path(self) -> Path:
        p = Path(self.chroma_persist_path)
        p.mkdir(parents=True, exist_ok=True)
        return p


settings = Settings()
