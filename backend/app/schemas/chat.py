"""对话相关 Pydantic schemas"""

from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class CitationItem(BaseModel):
    chunk_id: str = ""
    doc_id: str = ""
    file_name: str = ""
    page_num: int | None = None
    section_title: str | None = None
    content: str = ""
    score: float = 0.0
    source_type: str = "document"  # "document" 知识库文档, "web" 网络搜索
    url: str | None = None  # 网络搜索结果的链接


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4096)
    conv_id: str | None = None
    top_k: int = Field(default=5, ge=1, le=20)


class ChatResponse(BaseModel):
    answer: str
    conv_id: str
    citations: list[CitationItem] = []


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    msg_id: str
    role: str
    content: str
    citations: dict | None
    created_at: datetime


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    conv_id: str
    title: str | None
    created_at: datetime
    updated_at: datetime


class ConversationListResponse(BaseModel):
    total: int
    conversations: list[ConversationResponse]


class ConversationDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    conv_id: str
    title: str | None
    messages: list[MessageResponse]
    created_at: datetime
