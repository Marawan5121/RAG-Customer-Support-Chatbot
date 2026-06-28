"""Chat router - the primary RAG query endpoint.

The endpoint is wired end-to-end (request validation, service injection, response
model) but the retrieval-augmented generation logic is intentionally left as a
placeholder to be completed in Milestone 2.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import (
    get_cache_service,
    get_cosmos_service,
    get_llm_service,
    get_search_service,
)
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.cache_service import CacheService
from app.services.cosmos_service import CosmosService
from app.services.llm_service import LLMService
from app.services.search_service import SearchService

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse, status_code=status.HTTP_200_OK)
async def chat(
    payload: ChatRequest,
    search: SearchService = Depends(get_search_service),
    cosmos: CosmosService = Depends(get_cosmos_service),
    cache: CacheService = Depends(get_cache_service),
    llm: LLMService = Depends(get_llm_service),
) -> ChatResponse:
    """Resolve a customer query through the RAG pipeline.

    Planned flow (Milestone 2):
        1. Check the Redis response cache for a semantically identical query.
        2. Classify the intent (Gemini) and escalate when confidence is low.
        3. Embed the query (768-dim) and run hybrid search + semantic ranking.
        4. Generate a grounded answer with Gemini 1.5 Flash.
        5. Run a faithfulness check, then cache and persist the exchange.
    """
    # Reuse the provided session id or create a new one for this conversation.
    session_id = payload.session_id or str(uuid.uuid4())

    # The pipeline is not implemented yet; fail loudly rather than returning a stub.
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="RAG chat pipeline will be implemented in Milestone 2.",
    )
