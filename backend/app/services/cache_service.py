"""Azure Cache for Redis service - response caching.

Configuration placeholder built on the ``redis`` asyncio client. TLS is enabled
via the ``redis_ssl`` setting so the same code targets a local Redis container
(no TLS) and Azure Cache for Redis (TLS on port 6380).
"""

import json
from typing import Optional

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class CacheService:
    """Thin wrapper around the Redis async client for response caching."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = None  # redis.asyncio.Redis

    async def connect(self) -> None:
        """Initialise the async Redis client."""
        # Imported lazily to keep import-time dependencies minimal.
        import redis.asyncio as redis

        self._client = redis.Redis(
            host=self._settings.redis_host,
            port=self._settings.redis_port,
            password=self._settings.redis_password or None,
            ssl=self._settings.redis_ssl,
            db=self._settings.redis_db,
            decode_responses=True,
        )
        logger.info(
            "Redis client initialised (%s:%s, ssl=%s).",
            self._settings.redis_host,
            self._settings.redis_port,
            self._settings.redis_ssl,
        )

    async def close(self) -> None:
        """Release the underlying connection pool."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def get(self, key: str) -> Optional[dict]:
        """Return a cached JSON value for ``key`` or None on a cache miss."""
        if self._client is None:
            return None
        raw = await self._client.get(key)
        return json.loads(raw) if raw else None

    async def set(self, key: str, value: dict, ttl_seconds: Optional[int] = None) -> None:
        """Store a JSON-serialisable value with a TTL (defaults to configured TTL)."""
        if self._client is None:
            return
        ttl = ttl_seconds or self._settings.redis_cache_ttl_seconds
        await self._client.set(key, json.dumps(value), ex=ttl)

    async def ping(self) -> bool:
        """Lightweight health probe used by the /health endpoint."""
        if self._client is None:
            return False
        try:
            return bool(await self._client.ping())
        except Exception as exc:  # noqa: BLE001 - health check must never raise
            logger.warning("Redis ping failed: %s", exc)
            return False
