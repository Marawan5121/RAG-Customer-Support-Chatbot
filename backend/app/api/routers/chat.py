"""Chat router - the primary RAG query endpoint (Milestone 2).

End-to-end flow:
    1. Vectorise the user query with Gemini ``text-embedding-004`` (768-dim).
    2. Run hybrid search (BM25 + HNSW vector) with semantic ranking on Azure AI
       Search and take the top-K chunks as grounding context.
    3. Fetch prior messages for the session from Cosmos DB for multi-turn context.
    4. Generate a grounded answer with Gemini ``gemini-2.0-flash`` under strict
       guardrails (context-only, no PII, "I don't know" fallback).
    5. Persist the user and assistant messages back to Cosmos DB.
"""

import time
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import (
    get_cosmos_service,
    get_llm_service,
    get_search_service,
)
from app.core.config import get_settings
from app.schemas.chat import ChatRequest, ChatResponse, SourceChunk
from app.services.cosmos_service import CosmosService
from app.services.llm_service import LLMService
from app.services.search_service import SearchService

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse, status_code=status.HTTP_200_OK)
async def chat(
    payload: ChatRequest,
    search: SearchService = Depends(get_search_service),
    cosmos: CosmosService = Depends(get_cosmos_service),
    llm: LLMService = Depends(get_llm_service),
) -> ChatResponse:
    """Resolve a customer query through the RAG pipeline."""
    settings = get_settings()

    # Retrieval and generation both require their respective integrations.
    if not llm.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google Generative AI is not configured.",
        )
    if not search.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Azure AI Search is not configured.",
        )

    # Reuse the provided session id or create a new one for this conversation.
    session_id = payload.session_id or str(uuid.uuid4())
    started = time.perf_counter()

    try:
        # 1. Vectorise the query (768-dim).
        query_vector = await llm.embed_text(payload.message)

        # 2. Hybrid search + semantic ranking -> top-K grounding chunks.
        chunks = await search.hybrid_search(
            query_text=payload.message,
            query_vector=query_vector,
            top_k=settings.azure_search_top_k,
        )

        # 3. Fetch prior conversation for multi-turn context (graceful if no Cosmos).
        history = await cosmos.get_messages(session_id)

        # 4. Generate the grounded answer under guardrails.
        answer = await llm.generate_rag_response(
            query=payload.message,
            context_chunks=chunks,
            history=history,
        )
    except Exception as exc:  # noqa: BLE001 - surface a clean 502 instead of a stack trace
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"RAG pipeline error: {exc}",
        )

    latency_ms = int((time.perf_counter() - started) * 1000)
    # Treat an explicit "I don't know." as a signal to escalate to a human agent.
    escalated = answer.strip().lower().startswith("i don't know")
    top_intent = chunks[0]["intent_label"] if chunks else None

    # 5. Persist both turns to Cosmos DB (no-ops gracefully when not configured).
    await _persist_turn(cosmos, session_id, payload, answer, top_intent, latency_ms)

    return ChatResponse(
        answer=answer,
        session_id=session_id,
        intent=top_intent,
        confidence=None,
        faithfulness=None,
        latency_ms=latency_ms,
        escalated=escalated,
        cached=False,
        sources=[
            SourceChunk(
                chunk_id=chunk.get("chunk_id"),
                content_text=chunk.get("content_text", ""),
                intent_label=chunk.get("intent_label"),
                category=chunk.get("category"),
                relevance_score=chunk.get("relevance_score"),
            )
            for chunk in chunks
        ],
    )


async def _persist_turn(
    cosmos: CosmosService,
    session_id: str,
    payload: ChatRequest,
    answer: str,
    intent: str | None,
    latency_ms: int,
) -> None:
    """Store the user and assistant messages, and upsert the session document."""
    if not cosmos.is_configured:
        return

    now = datetime.now(timezone.utc).isoformat()

    await cosmos.save_message(
        {
            "message_id": str(uuid.uuid4()),
            "session_id": session_id,
            "role": "user",
            "content": payload.message,
            "timestamp": now,
            "intent": intent,
        }
    )
    await cosmos.save_message(
        {
            "message_id": str(uuid.uuid4()),
            "session_id": session_id,
            "role": "bot",
            "content": answer,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "intent": intent,
            "latency_ms": latency_ms,
        }
    )
    await cosmos.upsert_session(
        {
            "session_id": session_id,
            "customer_id": payload.customer_id,
            "last_activity": now,
        }
    )
