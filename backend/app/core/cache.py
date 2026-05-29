import redis.asyncio as aioredis
from app.core.config import settings
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Global Redis client
redis_client: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global redis_client
    if redis_client is None:
        redis_client = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=5,
        )
    return redis_client


async def close_redis():
    global redis_client
    if redis_client:
        await redis_client.aclose()
        redis_client = None


class CacheService:
    def __init__(self, redis: aioredis.Redis):
        self.redis = redis

    # ── Keys ──────────────────────────────────────────
    def search_key(self, query: str, mode: str, filters: str, page: int) -> str:
        import hashlib
        h = hashlib.md5(f"{query}:{mode}:{filters}:{page}".encode()).hexdigest()[:12]
        return f"search:{h}"

    def poet_key(self, slug: str) -> str:
        return f"poet:{slug}"

    def poem_key(self, slug: str) -> str:
        return f"poem:{slug}"

    def verse_key(self, verse_id: str) -> str:
        return f"verse:{verse_id}"

    def explanation_key(self, verse_id: str, exp_type: str) -> str:
        return f"exp:{verse_id}:{exp_type}"

    def autocomplete_key(self, prefix: str) -> str:
        return f"ac:{prefix[:20]}"

    def related_key(self, verse_id: str) -> str:
        return f"related:{verse_id}"

    # ── Operations ────────────────────────────────────
    async def get(self, key: str) -> Any | None:
        try:
            value = await self.redis.get(key)
            if value:
                return json.loads(value)
        except Exception as e:
            logger.warning(f"Cache GET error for {key}: {e}")
        return None

    async def set(self, key: str, value: Any, ttl: int | None = 3600) -> bool:
        try:
            serialized = json.dumps(value, ensure_ascii=False)
            if ttl is None or ttl == 0:
                await self.redis.set(key, serialized)
            else:
                await self.redis.setex(key, ttl, serialized)
            return True
        except Exception as e:
            logger.warning(f"Cache SET error for {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        try:
            await self.redis.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Cache DELETE error for {key}: {e}")
            return False

    async def delete_pattern(self, pattern: str) -> int:
        try:
            deleted = 0
            async for key in self.redis.scan_iter(match=pattern, count=100):
                await self.redis.delete(key)
                deleted += 1
            return deleted
        except Exception as e:
            logger.warning(f"Cache DELETE_PATTERN error for {pattern}: {e}")
        return 0

    async def ping(self) -> bool:
        try:
            await self.redis.ping()
            return True
        except Exception:
            return False
