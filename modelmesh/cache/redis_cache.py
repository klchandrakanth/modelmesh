"""Redis-backed prompt cache for ModelMesh.

Cache key: SHA-256 of (model + sorted messages JSON).
TTL is configurable per-instance (default 1 hour).

If Redis is unavailable, all operations fail silently (no-op).
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class RedisCache:
    def __init__(self, url: str = "redis://localhost:6379", ttl: int = 3600) -> None:
        self._url = url
        self._ttl = ttl
        self._redis: Any = None

    async def connect(self) -> None:
        """Initialize the Redis connection (called from lifespan)."""
        try:
            import redis.asyncio as aioredis  # type: ignore

            self._redis = await aioredis.from_url(
                self._url, encoding="utf-8", decode_responses=True
            )
            await self._redis.ping()
            logger.info("Redis cache connected: %s", self._url)
        except Exception as exc:
            logger.warning("Redis cache unavailable (%s) — caching disabled", exc)
            self._redis = None

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()

    def _cache_key(self, model: str, messages: list) -> str:
        payload = json.dumps(
            {"model": model, "messages": messages}, sort_keys=True, ensure_ascii=False
        )
        digest = hashlib.sha256(payload.encode()).hexdigest()
        return f"modelmesh:chat:{digest}"

    async def get(self, model: str, messages: list) -> Optional[dict]:
        if self._redis is None:
            return None
        try:
            key = self._cache_key(model, messages)
            value = await self._redis.get(key)
            if value:
                logger.debug("Cache HIT for key %s", key[:16])
                return json.loads(value)
        except Exception as exc:
            logger.debug("Cache GET error: %s", exc)
        return None

    async def set(self, model: str, messages: list, response: dict) -> None:
        if self._redis is None:
            return
        try:
            key = self._cache_key(model, messages)
            await self._redis.setex(key, self._ttl, json.dumps(response))
            logger.debug("Cache SET key %s (ttl=%ds)", key[:16], self._ttl)
        except Exception as exc:
            logger.debug("Cache SET error: %s", exc)

    async def health_check(self) -> bool:
        if self._redis is None:
            return False
        try:
            await self._redis.ping()
            return True
        except Exception:
            return False

    @property
    def is_available(self) -> bool:
        return self._redis is not None
