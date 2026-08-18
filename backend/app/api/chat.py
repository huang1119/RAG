"""对话问答 API：支持 SSE 流式输出，知识库+网络搜索混合"""

import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.document import Document, Chunk
from app.models.conversation import Conversation, Message
from app.core.deps import get_current_user
from app.config import settings
from app.schemas.chat import ChatRequest, CitationItem, ConversationListResponse, ConversationResponse, ConversationDetailResponse, MessageResponse
from app.services.embedding_service import embedding_service
from app.services.retrieval_service import retrieval_service
from app.services.llm_service import llm_service
from app.services.web_search_service import web_search_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])


async def _ensure_conversation(
    user: User, conv_id: str | None, question: str, db: AsyncSession
) -> Conversation:
    """获取或创建对话"""
    if conv_id:
        result = await db.execute(
            select(Conversation).where(
                Conversation.conv_id == conv_id, Conversation.user_id == user.user_id
            )
        )
        conv = result.scalar_one_or_none()
        if conv:
            return conv

    conv = Conversation(
        user_id=user.user_id,
        title=question[:50] + ("..." if len(question) > 50 else ""),
    )
    db.add(conv)
    await db.flush()
    return conv


async def _do_retrieval(question: str, top_k: int) -> tuple[list, str, str]:
    """执行混合检索：知识库优先，不够则补充网络搜索

    Returns:
        (citations, context, citation_text)
    """
    citations: list[CitationItem] = []
    context_parts: list[str] = []
    citation_list_parts: list[str] = []

    # --- 第一步：知识库检索 ---
    kb_results = await retrieval_service.retrieve(question, top_k=top_k)

    for i, r in enumerate(kb_results):
        meta = r.metadata or {}
        file_name = meta.get("file_name", "未知")
        page_num = meta.get("page_num") or None
        section_title = meta.get("section_title") or None
        doc_id = meta.get("doc_id", "")

        citations.append(CitationItem(
            chunk_id=r.chunk_id,
            doc_id=doc_id,
            file_name=file_name,
            page_num=page_num if isinstance(page_num, int) and page_num > 0 else None,
            section_title=section_title if section_title else None,
            content=r.content[:500],
            score=round(r.score, 4),
            source_type="document",
        ))

        context_parts.append(f"[知识库][{i + 1}] {r.content}")
        citation_list_parts.append(f"[{i + 1}] 来源: 知识库 - {file_name}" + (f", 第{page_num}页" if page_num else ""))

    # --- 第二步：判断是否需要网络搜索 ---
    kb_top_score = kb_results[0].score if kb_results else 0.0
    need_web_search = False

    if not kb_results:
        need_web_search = True
        logger.info("知识库无结果，触发网络搜索")
    elif kb_top_score < settings.web_search_score_threshold:
        need_web_search = True
        logger.info(f"知识库最高分 {kb_top_score:.4f} < {settings.web_search_score_threshold}，触发网络搜索补充")

    # --- 第三步：网络搜索 ---
    if need_web_search and settings.web_search_enabled:
        web_results = await web_search_service.search(
            question, max_results=settings.web_search_max_results
        )

        offset = len(citations)
        for j, wr in enumerate(web_results):
            idx = offset + j + 1
            citations.append(CitationItem(
                chunk_id=f"web_{j}",
                doc_id="",
                file_name=wr.title[:80],
                page_num=None,
                section_title=None,
                content=wr.snippet[:500],
                score=0.5,
                source_type="web",
                url=wr.url,
            ))

            context_parts.append(f"[网络][{idx}] {wr.title}\n{wr.snippet}")
            citation_list_parts.append(f"[{idx}] 来源: 网络 - {wr.title[:50]}")

    return citations, "\n\n".join(context_parts), "\n".join(citation_list_parts)


@router.post("/chat")
async def chat(
    data: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """知识问答接口 (SSE 流式输出)

    检索策略：知识库优先 -> 不够则网络搜索补充 -> LLM 生成

    返回 SSE 事件流:
    - {"type": "citations", "citations": [...]}
    - {"type": "token", "content": "..."}
    - {"type": "done", "conv_id": "...", "answer": "..."}
    """
    conv = await _ensure_conversation(user, data.conv_id, data.question, db)
    conv_id = conv.conv_id

    user_msg = Message(conv_id=conv_id, role="user", content=data.question)
    db.add(user_msg)
    await db.flush()

    citations, context, citation_text = await _do_retrieval(data.question, data.top_k)

    if not citations:
        no_result_answer = "未找到相关信息。请尝试上传相关文档、调整查询后重试，或稍后再问。"
        assistant_msg = Message(
            conv_id=conv_id, role="assistant", content=no_result_answer,
            citations={"items": []},
        )
        db.add(assistant_msg)
        await db.flush()

        async def no_result_stream():
            yield f"data: {json.dumps({'type': 'citations', 'citations': []})}\n\n"
            yield f"data: {json.dumps({'type': 'token', 'content': no_result_answer})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'conv_id': conv_id, 'answer': no_result_answer})}\n\n"

        return StreamingResponse(no_result_stream(), media_type="text/event-stream")

    messages = llm_service.build_prompt(data.question, context, citation_text)

    history_result = await db.execute(
        select(Message)
        .where(Message.conv_id == conv_id, Message.role == "user")
        .order_by(Message.created_at.desc())
        .limit(5)
    )
    recent_msgs = list(reversed(history_result.scalars().all()))

    async def stream_response() -> AsyncGenerator[str, None]:
        yield f"data: {json.dumps({'type': 'citations', 'citations': [c.model_dump() for c in citations]})}\n\n"

        full_answer = ""
        try:
            async for token in llm_service.generate_stream(messages):
                full_answer += token
                yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
        except Exception as e:
            logger.error(f"流式生成失败: {e}", exc_info=True)
            error_msg = f"\n\n[生成中断: {e}]"
            full_answer += error_msg
            yield f"data: {json.dumps({'type': 'token', 'content': error_msg})}\n\n"

        async with get_db_session() as session:
            assistant_msg = Message(
                conv_id=conv_id,
                role="assistant",
                content=full_answer,
                citations={"items": [c.model_dump() for c in citations]},
            )
            session.add(assistant_msg)
            await session.commit()

        yield f"data: {json.dumps({'type': 'done', 'conv_id': conv_id, 'answer': full_answer})}\n\n"

    return StreamingResponse(stream_response(), media_type="text/event-stream")


from contextlib import asynccontextmanager


@asynccontextmanager
async def get_db_session():
    from app.database import async_session
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取对话列表"""
    from sqlalchemy import func
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user.user_id)
        .order_by(Conversation.updated_at.desc())
    )
    convs = result.scalars().all()
    return ConversationListResponse(
        total=len(convs),
        conversations=[ConversationResponse.model_validate(c) for c in convs],
    )


@router.get("/conversations/{conv_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conv_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取对话详情（含所有消息）"""
    result = await db.execute(
        select(Conversation).where(
            Conversation.conv_id == conv_id, Conversation.user_id == user.user_id
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="对话不存在")

    msg_result = await db.execute(
        select(Message).where(Message.conv_id == conv_id).order_by(Message.created_at)
    )
    messages = msg_result.scalars().all()

    return ConversationDetailResponse(
        conv_id=conv.conv_id,
        title=conv.title,
        messages=[MessageResponse.model_validate(m) for m in messages],
        created_at=conv.created_at,
    )


@router.delete("/conversations/{conv_id}")
async def delete_conversation(
    conv_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除对话"""
    from sqlalchemy import delete as sql_delete
    result = await db.execute(
        select(Conversation).where(
            Conversation.conv_id == conv_id, Conversation.user_id == user.user_id
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="对话不存在")

    await db.execute(sql_delete(Message).where(Message.conv_id == conv_id))
    await db.execute(sql_delete(Conversation).where(Conversation.conv_id == conv_id))

    return {"message": "对话已删除"}
