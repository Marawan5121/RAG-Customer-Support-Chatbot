"""FastAPI dependency providers.

Services are created once during application startup and stored on
``app.state``. These dependency functions expose them to routers, keeping the
endpoints free of any client-construction logic.
"""

from fastapi import Request

from app.services.cache_service import CacheService
from app.services.cosmos_service import CosmosService
from app.services.indexing_service import IndexingService
from app.services.llm_service import LLMService
from app.services.search_service import SearchService


def get_search_service(request: Request) -> SearchService:
    """Return the shared Azure AI Search service instance."""
    return request.app.state.search_service


def get_cosmos_service(request: Request) -> CosmosService:
    """Return the shared Azure Cosmos DB service instance."""
    return request.app.state.cosmos_service


def get_cache_service(request: Request) -> CacheService:
    """Return the shared Azure Cache for Redis service instance."""
    return request.app.state.cache_service


def get_llm_service(request: Request) -> LLMService:
    """Return the shared Google Generative AI service instance."""
    return request.app.state.llm_service


def get_indexing_service(request: Request) -> IndexingService:
    """Return the shared indexing orchestration service instance."""
    return request.app.state.indexing_service
