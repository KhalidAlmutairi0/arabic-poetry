"""
FastAPI dependency injection — shared dependencies across routers.
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from meilisearch_python_sdk import AsyncClient as MeiliClient
from app.core.database import get_db
from app.core.cache import CacheService, get_redis
from app.core.config import settings
from app.services.search_service import SearchService
from app.services.ai_service import AIService
from app.services.poet_service import PoetService
from app.services.poem_service import PoemService
from app.services.verse_service import VerseService
import redis.asyncio as aioredis

# ── Meilisearch client (singleton) ────────────────────
_meili_client: MeiliClient | None = None


async def get_meili() -> MeiliClient:
    global _meili_client
    if _meili_client is None:
        _meili_client = MeiliClient(
            url=settings.meilisearch_url,
            api_key=settings.meilisearch_key,
        )
    return _meili_client


async def get_meili_client():
    """AsyncClient must be used as context manager to init httpx session."""
    async with AsyncClient(
        url=settings.meilisearch_url,
        api_key=settings.meilisearch_key,
    ) as client:
        yield client


# ── Service dependencies ───────────────────────────────

def get_ai_service() -> AIService:
    return AIService()


async def get_cache(redis: aioredis.Redis = Depends(get_redis)) -> CacheService:
    return CacheService(redis)


async def get_search_service(
    db: AsyncSession = Depends(get_db),
    meili: MeiliClient = Depends(get_meili_client),
    ai: AIService = Depends(get_ai_service),
) -> SearchService:
    return SearchService(db, meili, ai)


async def get_poet_service(db: AsyncSession = Depends(get_db)) -> PoetService:
    return PoetService(db)


async def get_poem_service(db: AsyncSession = Depends(get_db)) -> PoemService:
    return PoemService(db)


async def get_verse_service(db: AsyncSession = Depends(get_db)) -> VerseService:
    return VerseService(db)
