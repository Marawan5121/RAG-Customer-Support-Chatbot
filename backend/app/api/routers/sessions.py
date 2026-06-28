"""Sessions router - retrieve conversation history from Cosmos DB."""

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_cosmos_service
from app.services.cosmos_service import CosmosService

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("/{session_id}")
async def get_session(
    session_id: str,
    cosmos: CosmosService = Depends(get_cosmos_service),
) -> dict:
    """Return a session transcript (session document + ordered messages)."""
    if not cosmos.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cosmos DB is not configured.",
        )

    session = await cosmos.get_session(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )
    return session
