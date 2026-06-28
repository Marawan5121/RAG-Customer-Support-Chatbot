"""FastAPI application entrypoint.

Creates the app, configures middleware, registers routers and manages the
lifecycle of the shared services (Azure AI Search, Cosmos DB, Redis, Gemini,
plus the preprocessing/indexing orchestration) via the lifespan context manager.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import chat, health, index, sessions
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.services.cache_service import CacheService
from app.services.cosmos_service import CosmosService
from app.services.indexing_service import IndexingService
from app.services.llm_service import LLMService
from app.services.preprocessing_service import PreprocessingService
from app.services.search_service import SearchService

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise services on startup and dispose of them on shutdown."""
    settings = get_settings()
    configure_logging()
    logger.info("Starting %s (environment=%s).", settings.app_name, settings.environment)

    # Instantiate the shared services and store them on the application state.
    app.state.search_service = SearchService(settings)
    app.state.cosmos_service = CosmosService(settings)
    app.state.cache_service = CacheService(settings)
    app.state.llm_service = LLMService(settings)
    app.state.preprocessing_service = PreprocessingService(settings)
    app.state.indexing_service = IndexingService(
        settings=settings,
        search_service=app.state.search_service,
        llm_service=app.state.llm_service,
        preprocessing_service=app.state.preprocessing_service,
    )

    # Establish connections (each gracefully no-ops when not configured).
    await app.state.search_service.connect()
    await app.state.cosmos_service.connect()
    await app.state.cache_service.connect()
    await app.state.llm_service.connect()

    yield

    # Cleanly release every connection on shutdown.
    await app.state.search_service.close()
    await app.state.cosmos_service.close()
    await app.state.cache_service.close()
    await app.state.llm_service.close()
    logger.info("Shutdown complete.")


def create_app() -> FastAPI:
    """Application factory - builds and configures the FastAPI instance."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        debug=settings.debug,
        lifespan=lifespan,
    )

    # Allow the Next.js frontend to call the API from the browser.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers under the versioned API prefix.
    app.include_router(health.router, prefix=settings.api_v1_prefix)
    app.include_router(chat.router, prefix=settings.api_v1_prefix)
    app.include_router(sessions.router, prefix=settings.api_v1_prefix)
    app.include_router(index.router, prefix=settings.api_v1_prefix)

    return app


app = create_app()
