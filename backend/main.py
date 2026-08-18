"""FastAPI 应用入口"""

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.api.router import api_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化"""
    logger.info("正在初始化数据库...")
    await init_db()

    logger.info("正在加载 BM25 索引...")
    try:
        from sqlalchemy import select
        from app.database import async_session
        from app.models.document import Chunk
        from app.services.retrieval_service import bm25_index

        async with async_session() as session:
            result = await session.execute(select(Chunk.chunk_id, Chunk.content))
            rows = result.all()
            chunks = [{"chunk_id": r[0], "content": r[1], "metadata": {}} for r in rows]
            bm25_index.build(chunks)
            logger.info(f"BM25 索引加载完成: {len(chunks)} 条")
    except Exception as e:
        logger.warning(f"BM25 索引加载跳过: {e}")

    logger.info(f"{settings.app_name} 启动完成")
    yield

    logger.info("应用关闭中...")


app = FastAPI(
    title=settings.app_name,
    description="企业级 RAG 个人知识问答系统 API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": settings.app_name}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_env == "development",
    )
