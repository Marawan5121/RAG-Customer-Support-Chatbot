"""Health-check router.

Reports the readiness of each backing service so orchestrators (Docker Compose
health checks, Kubernetes probes) and the dashboard can surface system status.
"""

from fastapi import APIRouter, Depends

from app.api.deps import (
    get_cache_service,
    get_cosmos_service,
    get_llm_service,
    get_search_service,
)
from app.core.config import get_settings
from app.services.cache_service import CacheService
from app.services.cosmos_service import CosmosService
from app.services.llm_service import LLMService
from app.services.search_service import SearchService

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(
    search: SearchService = Depends(get_search_service),
    cosmos: CosmosService = Depends(get_cosmos_service),
    cache: CacheService = Depends(get_cache_service),
    llm: LLMService = Depends(get_llm_service),
) -> dict:
    """Return overall status plus a per-component readiness breakdown."""
    settings = get_settings()

    components = {
        "ai_search": await search.ping(),
        "cosmos_db": await cosmos.ping(),
        "redis": await cache.ping(),
        "google_genai": await llm.ping(),
    }

    # The service is "healthy" only when every component is reachable.
    overall = "healthy" if all(components.values()) else "degraded"

    return {
        "status": overall,
        "components": components,
        "version": "0.1.0",
        "environment": settings.environment,
    }
