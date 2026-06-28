"""Request and response schemas for the chat endpoint."""

from typing import List, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Incoming customer query payload."""

    message: str = Field(..., min_length=1, max_length=500, description="Customer query text")
    session_id: Optional[str] = Field(
        default=None, description="Existing session id; a new session is created when omitted"
    )
    customer_id: Optional[str] = Field(default=None, description="Optional authenticated customer id")


class SourceChunk(BaseModel):
    """A single knowledge-base chunk used to ground the generated answer."""

    chunk_id: str
    content_text: str
    intent_label: Optional[str] = None
    category: Optional[str] = None
    relevance_score: Optional[float] = None


class ChatResponse(BaseModel):
    """Generated answer plus retrieval and observability metadata."""

    answer: str
    session_id: str
    intent: Optional[str] = None
    confidence: Optional[float] = None
    faithfulness: Optional[float] = None
    latency_ms: Optional[int] = None
    escalated: bool = False
    cached: bool = False
    sources: List[SourceChunk] = Field(default_factory=list)
