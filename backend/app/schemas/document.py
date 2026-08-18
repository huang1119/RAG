"""文档相关 Pydantic schemas"""

from datetime import datetime
from pydantic import BaseModel, ConfigDict


class DocumentUploadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    doc_id: str
    file_name: str
    file_format: str
    file_size: int
    status: str
    created_at: datetime


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    doc_id: str
    file_name: str
    file_format: str
    file_size: int
    source: str | None
    category: str | None
    status: str
    chunk_count: int
    error_message: str | None
    created_at: datetime


class DocumentListResponse(BaseModel):
    total: int
    documents: list[DocumentResponse]


class ChunkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    chunk_id: str
    doc_id: str
    chunk_index: int
    content: str
    page_num: int | None
    section_title: str | None
    token_count: int


class StatsResponse(BaseModel):
    document_count: int
    chunk_count: int
    ready_count: int
    processing_count: int
    failed_count: int
    total_size_mb: float
