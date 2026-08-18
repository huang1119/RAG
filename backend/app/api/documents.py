"""文档管理 API"""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.models.document import Document, Chunk
from app.core.deps import get_current_user, get_admin_user
from app.schemas.document import (
    DocumentUploadResponse,
    DocumentResponse,
    DocumentListResponse,
    StatsResponse,
)
from app.services.document_service import compute_file_hash, get_file_format, parse_document
from app.services.chunk_service import chunk_document
from app.services.embedding_service import embedding_service
from app.services.vector_store import vector_store
from app.services.retrieval_service import bm25_index

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])

SUPPORTED_FORMATS = {"pdf", "docx", "doc", "md", "markdown", "txt", "html", "htm"}


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    category: str | None = None,
    user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """上传文档并自动处理：解析 -> 分块 -> 向量化 -> 入库"""
    file_name = file.filename or "unknown"
    file_format = get_file_format(file_name)

    if file_format not in SUPPORTED_FORMATS:
        raise HTTPException(status_code=400, detail=f"不支持的文件格式: {file_format}")

    content = await file.read()
    if len(content) > settings.max_file_size_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"文件大小超过限制 ({settings.max_file_size_mb}MB)")

    file_hash = compute_file_hash.__wrapped__ if hasattr(compute_file_hash, "__wrapped__") else None
    import hashlib
    file_hash = hashlib.sha256(content).hexdigest()

    result = await db.execute(
        select(Document).where(Document.file_hash == file_hash, Document.user_id == user.user_id)
    )
    existing = result.scalar_one_or_none()
    if existing:
        return DocumentUploadResponse.model_validate(existing)

    doc = Document(
        user_id=user.user_id,
        file_name=file_name,
        file_format=file_format,
        file_path="",
        file_hash=file_hash,
        file_size=len(content),
        source=file_name,
        category=category,
        status="processing",
    )
    db.add(doc)
    await db.flush()

    save_path = settings.upload_path / f"{doc.doc_id}_{file_name}"
    with open(save_path, "wb") as f:
        f.write(content)
    doc.file_path = str(save_path)

    try:
        pages = parse_document(str(save_path), file_format)

        chunks_data = chunk_document(pages, doc.doc_id)

        if not chunks_data:
            doc.status = "failed"
            doc.error_message = "文档内容为空或解析失败"
            raise HTTPException(status_code=422, detail="文档内容为空或解析失败")

        chunk_records = []
        texts = []
        for cd in chunks_data:
            chunk = Chunk(
                chunk_id=cd.chunk_id,
                doc_id=doc.doc_id,
                parent_chunk_id=cd.parent_chunk_id,
                chunk_index=cd.chunk_index,
                content=cd.content,
                page_num=cd.page_num,
                section_title=cd.section_title,
                token_count=cd.token_count,
            )
            chunk_records.append(chunk)
            texts.append(cd.content)

        db.add_all(chunk_records)

        embeddings = await embedding_service.embed_batch(texts)

        metadatas = []
        for cd in chunks_data:
            metadatas.append({
                "doc_id": doc.doc_id,
                "file_name": file_name,
                "page_num": cd.page_num or 0,
                "section_title": cd.section_title or "",
                "chunk_index": cd.chunk_index,
                "category": category or "",
            })

        vector_store.add(
            ids=[cd.chunk_id for cd in chunks_data],
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )

        await _rebuild_bm25_index()

        doc.chunk_count = len(chunks_data)
        doc.status = "ready"
        await db.flush()

        logger.info(f"文档处理完成: {file_name}, {len(chunks_data)} chunks")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"文档处理失败: {e}", exc_info=True)
        doc.status = "failed"
        doc.error_message = str(e)
        await db.flush()
        raise HTTPException(status_code=500, detail=f"文档处理失败: {e}")

    await db.refresh(doc)  # 加载 MySQL 服务端生成的 created_at / updated_at
    return DocumentUploadResponse.model_validate(doc)


async def _rebuild_bm25_index():
    """重建 BM25 索引（从数据库加载所有 chunk）"""
    from app.database import async_session

    async with async_session() as session:
        result = await session.execute(select(Chunk.chunk_id, Chunk.content))
        rows = result.all()
        chunks = [{"chunk_id": r[0], "content": r[1], "metadata": {}} for r in rows]
        bm25_index.build(chunks)
        logger.info(f"BM25 索引已重建, {len(chunks)} 条")


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取文档列表（所有用户可查看共享知识库）"""
    offset = (page - 1) * page_size
    count_result = await db.execute(
        select(func.count()).select_from(Document)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(Document)
        .order_by(Document.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    docs = result.scalars().all()

    return DocumentListResponse(total=total, documents=[DocumentResponse.model_validate(d) for d in docs])


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: str,
    user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """删除文档及其所有分块和向量（仅管理员）"""
    result = await db.execute(
        select(Document).where(Document.doc_id == doc_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    try:
        vector_store.delete_by_doc(doc_id)
    except Exception as e:
        logger.warning(f"删除向量失败: {e}")

    import os
    if doc.file_path and os.path.exists(doc.file_path):
        os.remove(doc.file_path)

    await db.execute(delete(Chunk).where(Chunk.doc_id == doc_id))
    await db.execute(delete(Document).where(Document.doc_id == doc_id))

    await _rebuild_bm25_index()

    return {"message": "文档已删除"}


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取知识库统计信息（所有用户可查看）"""
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
