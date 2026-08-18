"""文档分块服务：智能分块策略

- 对表格结构化文本（每行是 "表头：值" 格式），按行分组，不切断单行
- 对普通文本段落，按句子切分，带重叠窗口
"""

import re
import uuid
from dataclasses import dataclass

from app.config import settings


@dataclass
class ChunkData:
    chunk_id: str
    content: str
    page_num: int | None
    section_title: str | None
    chunk_index: int
    token_count: int
    parent_chunk_id: str | None = None


def estimate_tokens(text: str) -> int:
    """粗略估算 token 数（中文约 1.5 字/token，英文约 4 字符/token）"""
    chinese_chars = len(re.findall(r"[一-鿿]", text))
    other_chars = len(text) - chinese_chars
    return int(chinese_chars * 1.5 + other_chars / 4)


def _is_structured_row(line: str) -> bool:
    """检测是否为表格转换的结构化行（"表头：值" 格式）"""
    # 一行中包含 2 个及以上 "：" 或 ":"，说明是表格行转换的键值对
    colon_count = line.count("：") + line.count(":")
    return colon_count >= 2


def split_text_by_tokens(text: str, chunk_size: int, overlap: int) -> list[str]:
    """按 token 预算切分文本，带重叠窗口

    结构化文本行（表格转换的）不会被切割，始终作为整体保留。
    """
    if not text.strip():
        return []

    # 检测是否为结构化文本（表格转换的）
    lines = text.split("\n")
    has_structured = any(_is_structured_row(line) for line in lines)

    if has_structured:
        # 结构化文本 → 按行分组，不切断单行
        return _split_structured(lines, chunk_size, overlap)

    # 普通文本 → 按句子切分
    sentences = re.split(r"(?<=[。！？.!?\n])\s*", text)
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        return []

    return _group_by_token_budget(sentences, chunk_size, overlap)


def _split_structured(
    lines: list[str], chunk_size: int, overlap: int
) -> list[str]:
    """按 token 预算将结构化文本行分组，不切断单行"""
    # 过滤空行
    rows = [line.strip() for line in lines if line.strip()]
    if not rows:
        return []

    return _group_by_token_budget(rows, chunk_size, overlap)


def _group_by_token_budget(
    units: list[str], chunk_size: int, overlap: int
) -> list[str]:
    """将文本单元按 token 预算分组，保持单元完整性"""
    chunks: list[str] = []
    current_group: list[str] = []
    current_tokens = 0

    for unit in units:
        unit_tokens = estimate_tokens(unit)

        # 如果单个单元超过 chunk_size，尝试按字符拆分
        if unit_tokens > chunk_size:
            if current_group:
                chunks.append("\n".join(current_group))
                current_group = []
                current_tokens = 0
            chars = list(unit)
            sub_chunk: list[str] = []
            sub_tokens = 0
            for ch in chars:
                ct = estimate_tokens(ch)
                if sub_tokens + ct > chunk_size and sub_chunk:
                    chunks.append("".join(sub_chunk))
                    # 重叠：保留最后几个字符
                    overlap_chars = max(1, int(len(sub_chunk) * overlap / chunk_size))
                    sub_chunk = (
                        sub_chunk[-overlap_chars:]
                        if overlap_chars < len(sub_chunk)
                        else []
                    )
                    sub_tokens = sum(estimate_tokens(c) for c in sub_chunk)
                sub_chunk.append(ch)
                sub_tokens += ct
            if sub_chunk:
                current_group = sub_chunk
                current_tokens = sub_tokens
            continue

        # token 超预算 → 输出当前组，开始新组
        if current_tokens + unit_tokens > chunk_size and current_group:
            chunks.append("\n".join(current_group))
            # 重叠：保留最后一两行
            overlap_tokens = 0
            keep_parts: list[str] = []
            for part in reversed(current_group):
                pt = estimate_tokens(part)
                if overlap_tokens + pt > overlap:
                    break
                keep_parts.insert(0, part)
                overlap_tokens += pt
            current_group = keep_parts
            current_tokens = overlap_tokens

        current_group.append(unit)
        current_tokens += unit_tokens

    if current_group:
        chunks.append("\n".join(current_group))

    return chunks


def chunk_document(
    pages: list[dict],
    doc_id: str,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[ChunkData]:
    """
    将解析后的文档页面列表分块

    Args:
        pages: [{page_num, content, section_title}]
        doc_id: 文档 ID
        chunk_size: 分块大小 (tokens)
        chunk_overlap: 重叠大小 (tokens)

    Returns:
        list[ChunkData]
    """
    cs = chunk_size or settings.chunk_size
    co = chunk_overlap or settings.chunk_overlap

    all_chunks: list[ChunkData] = []
    chunk_index = 0

    for page in pages:
        text = page.get("content", "").strip()
        if not text:
            continue

        page_num = page.get("page_num")
        section_title = page.get("section_title")

        text_chunks = split_text_by_tokens(text, cs, co)

        parent_chunk_id = str(uuid.uuid4())
        for tc in text_chunks:
            chunk = ChunkData(
                chunk_id=str(uuid.uuid4()),
                content=tc,
                page_num=page_num,
                section_title=section_title,
                chunk_index=chunk_index,
                token_count=estimate_tokens(tc),
                parent_chunk_id=parent_chunk_id,
            )
            all_chunks.append(chunk)
            chunk_index += 1

    return all_chunks
