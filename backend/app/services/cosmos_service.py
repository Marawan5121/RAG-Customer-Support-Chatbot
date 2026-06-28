"""Azure Cosmos DB service - session and message chat-history persistence.

Built on the official ``azure-cosmos`` async client. Messages are partitioned by
``session_id`` so the multi-turn history for a conversation can be fetched in a
single, efficient partition query. Containers are created on connect when missing
so the service is runnable out of the box.
"""

from typing import List, Optional

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
        """Initialise the Cosmos client and ensure database/containers exist."""
        if not self.is_configured:
            logger.warning("Azure Cosmos DB is not configured; history storage is disabled.")
            return

        # Imported lazily to avoid a hard dependency at import time.
        from azure.cosmos import PartitionKey
        from azure.cosmos.aio import CosmosClient

        self._client = CosmosClient(
            url=self._settings.cosmos_endpoint,
            credential=self._settings.cosmos_key,
        )

        # Create database and containers if they do not exist (idempotent).
        # Both containers are partitioned by /session_id for single-partition reads.
        try:
            self._database = await self._client.create_database_if_not_exists(
                id=self._settings.cosmos_database
            )
            self._sessions = await self._database.create_container_if_not_exists(
                id=self._settings.cosmos_sessions_container,
                partition_key=PartitionKey(path="/session_id"),
            )
            self._messages = await self._database.create_container_if_not_exists(
                id=self._settings.cosmos_messages_container,
                partition_key=PartitionKey(path="/session_id"),
            )
            logger.info(
                "Cosmos DB ready (database='%s', containers='%s','%s').",
                self._settings.cosmos_database,
                self._settings.cosmos_sessions_container,
                self._settings.cosmos_messages_container,
            )
        except Exception as exc:  # noqa: BLE001 - never block startup on provisioning
            logger.error("Cosmos DB provisioning failed: %s", exc)

    async def close(self) -> None:
        """Release the underlying HTTP session."""
        if self._client is not None:
            await self._client.close()
            self._client = None

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------
    async def save_message(self, message: dict) -> None:
        """Persist a single message document (partitioned by session_id).

        The message must contain ``message_id``, ``session_id``, ``role`` and
        ``content``. Failures are logged but never raised so they cannot break a
        chat response that has already been generated.
        """
        if self._messages is None:
            logger.warning("save_message called but Cosmos DB client is not ready.")
            return
        try:
            # Cosmos requires an 'id' field; mirror the message_id into it.
            document = {**message, "id": message["message_id"]}
            await self._messages.upsert_item(document)
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to save message %s: %s", message.get("message_id"), exc)

    async def upsert_session(self, session: dict) -> None:
        """Create or update a session document (partitioned by session_id)."""
        if self._sessions is None:
            return
        try:
            document = {**session, "id": session["session_id"]}
            await self._sessions.upsert_item(document)
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to upsert session %s: %s", session.get("session_id"), exc)

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------
    async def get_messages(self, session_id: str, limit: int = 20) -> List[dict]:
        """Fetch the most recent messages for a session, in chronological order.

        Runs a single-partition query (partition key = session_id). Returns an
        empty list when Cosmos is unavailable so the chat flow degrades gracefully.
        """
        if self._messages is None:
            return []
        try:
            query = (
                "SELECT c.message_id, c.role, c.content, c.timestamp "
                "FROM c WHERE c.session_id = @session_id ORDER BY c.timestamp ASC"
            )
            parameters = [{"name": "@session_id", "value": session_id}]
            items: List[dict] = []
            async for item in self._messages.query_items(
                query=query,
                parameters=parameters,
                partition_key=session_id,
            ):
                items.append(item)
            # Keep only the last ``limit`` turns to bound prompt size.
            return items[-limit:]
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to fetch messages for session %s: %s", session_id, exc)
            return []

    async def get_session(self, session_id: str) -> Optional[dict]:
        """Return a session document together with its full message transcript."""
        if self._sessions is None or self._messages is None:
            return None

        from azure.cosmos.exceptions import CosmosResourceNotFoundError

        session_doc: Optional[dict] = None
        try:
            session_doc = await self._sessions.read_item(
                item=session_id, partition_key=session_id
            )
        except CosmosResourceNotFoundError:
            session_doc = None
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to read session %s: %s", session_id, exc)

        messages = await self.get_messages(session_id, limit=1000)
        if session_doc is None and not messages:
            return None

        result = session_doc or {"session_id": session_id}
        result["messages"] = messages
        return result

    async def ping(self) -> bool:
        """Lightweight health probe used by the /health endpoint."""
        return self._client is not None
