"""API 路由聚合"""

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import router as auth_router
from app.api.documents import router as documents_router
from app.api.chat import router as chat_router
from app.api.admin import router as admin_router
from app.core.deps import get_current_user
from app.models.user import User
from app.database import get_db
from app.schemas.document import StatsResponse

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(documents_router)
api_router.include_router(chat_router)
api_router.include_router(admin_router)


@api_router.get("/stats", response_model=StatsResponse)
async def get_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取知识库统计信息 (顶层路由，所有登录用户可查看)"""
    from app.models.document import Document, Chunk

    total_docs = (await db.execute(select(func.count()).select_from(Document))).scalar() or 0
    total_chunks = (
        await db.execute(
            select(func.count())
            .select_from(Chunk)
            .join(Document, Chunk.doc_id == Document.doc_id)
        )
    ).scalar() or 0
    ready_count = (
        await db.execute(select(func.count()).select_from(Document).where(Document.status == "ready"))
    ).scalar() or 0
    processing_count = (
        await db.execute(select(func.count()).select_from(Document).where(Document.status == "processing"))
    ).scalar() or 0
    failed_count = (
        await db.execute(select(func.count()).select_from(Document).where(Document.status == "failed"))
    ).scalar() or 0
    total_size = (
        await db.execute(select(func.coalesce(func.sum(Document.file_size), 0)))
    ).scalar() or 0

    return StatsResponse(
        document_count=total_docs,
        chunk_count=total_chunks,
        ready_count=ready_count,
        processing_count=processing_count,
        failed_count=failed_count,
        total_size_mb=round(total_size / 1024 / 1024, 2),
    )
