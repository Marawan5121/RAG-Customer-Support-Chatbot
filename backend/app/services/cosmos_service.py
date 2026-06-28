"""Azure Cosmos DB service - session and message chat-history persistence.

Configuration placeholder built on the official ``azure-cosmos`` async client.
Containers are referenced via configuration so the same code targets local,
staging and production accounts without change.
"""

from typing import Optional

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class CosmosService:
    """Thin wrapper around the Azure Cosmos DB async client."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = None  # azure.cosmos.aio.CosmosClient
        self._database = None
        self._sessions = None
        self._messages = None

    @property
    def is_configured(self) -> bool:
        """Return True when the Cosmos endpoint and key are present."""
        return self._settings.cosmos_configured

    async def connect(self) -> None:
        """Initialise the Cosmos client and cache container proxies."""
        if not self.is_configured:
            logger.warning("Azure Cosmos DB is not configured; history storage is disabled.")
            return

        # Imported lazily to avoid a hard dependency at import time.
        from azure.cosmos.aio import CosmosClient

        self._client = CosmosClient(
            url=self._settings.cosmos_endpoint,
            credential=self._settings.cosmos_key,
        )
        self._database = self._client.get_database_client(self._settings.cosmos_database)
        self._sessions = self._database.get_container_client(
            self._settings.cosmos_sessions_container
        )
        self._messages = self._database.get_container_client(
            self._settings.cosmos_messages_container
        )
        logger.info(
            "Cosmos DB client initialised for database '%s'.", self._settings.cosmos_database
        )

    async def close(self) -> None:
        """Release the underlying HTTP session."""
        if self._client is not None:
            await self._client.close()
            self._client = None

    async def save_message(self, message: dict) -> None:
        """Persist a single message document (partitioned by session_id)."""
        if self._messages is None:
            logger.warning("save_message called but Cosmos DB client is not ready.")
            return
        # TODO (Milestone 2/3): await self._messages.upsert_item(message)
        raise NotImplementedError("Message persistence will be implemented later.")

    async def get_session(self, session_id: str) -> Optional[dict]:
        """Fetch a session document together with its messages."""
        if self._sessions is None:
            logger.warning("get_session called but Cosmos DB client is not ready.")
            return None
        # TODO (Milestone 2/3): read the session item and its related messages.
        raise NotImplementedError("Session retrieval will be implemented later.")

    async def ping(self) -> bool:
        """Lightweight health probe used by the /health endpoint."""
        return self._client is not None
