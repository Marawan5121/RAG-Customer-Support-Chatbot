"""Schemas describing chat sessions and their stored messages."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class Message(BaseModel):
    """A single message exchanged within a session."""

    message_id: str
    role: str = Field(..., description="'user' or 'bot'")
    content: str
    timestamp: datetime
    intent: Optional[str] = None
    confidence: Optional[float] = None
    latency_ms: Optional[int] = None


class Session(BaseModel):
    """A customer conversation session persisted in Cosmos DB."""

    session_id: str
    customer_id: Optional[str] = None
    started_at: datetime
    ended_at: Optional[datetime] = None
    channel: str = Field(default="web")
    csat_score: Optional[int] = None
    escalated: bool = False
    messages: List[Message] = Field(default_factory=list)
