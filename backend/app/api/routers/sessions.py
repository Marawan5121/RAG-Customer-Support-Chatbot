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
    """Return a session transcript by id.

    Retrieval from Cosmos DB is wired but not yet implemented (Milestone 2/3).
    """
    if not cosmos.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cosmos DB is not configured.",
        )

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Session retrieval will be implemented in a later milestone.",
    )
