from fastapi import APIRouter, Depends, Query
from uuid import UUID
from sqlalchemy import update as sa_update
from app.services.verse_service import VerseService
from app.models.verse import Verse
from app.api.v1.dependencies import get_verse_service, get_cache
from app.core.cache import CacheService
from app.core.database import run_in_background
from app.core.exceptions import not_found
import asyncio

router = APIRouter(prefix="/verses", tags=["verses"])


@router.get("/famous", summary="Get famous verses")
async def get_famous_verses(
    limit: int = Query(10, ge=1, le=50),
    verse_service: VerseService = Depends(get_verse_service),
    cache: CacheService = Depends(get_cache),
):
    cache_key = "famous_verses"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    verses = await verse_service.get_famous_verses(limit=limit)
    response = [
        {
            "id": str(v.id),
            "full_verse": v.full_verse,
            "hemistich_1": v.hemistich_1,
            "hemistich_2": v.hemistich_2,
            "poet_name_ar": v.poet_name_ar,
            "poem_title_ar": v.poem_title_ar,
            "poem_slug": v.poem_slug,
            "poet_id": str(v.poet_id),
            "is_famous": v.is_famous,
        }
        for v in verses
    ]

    asyncio.create_task(cache.set(cache_key, response, ttl=3600))
    return response


@router.get("/{verse_id}", summary="Get verse detail")
async def get_verse(
    verse_id: UUID,
    verse_service: VerseService = Depends(get_verse_service),
    cache: CacheService = Depends(get_cache),
):
    cache_key = cache.verse_key(str(verse_id))
    cached = await cache.get(cache_key)
    if cached:
        return cached

    from app.core.exceptions import NotFoundException
    try:
        verse = await verse_service.get_with_all(verse_id)
    except NotFoundException:
        raise not_found("Verse", str(verse_id))
    except Exception as exc:
        import logging
        logging.getLogger(__name__).exception(f"Error fetching verse {verse_id}: {exc}")
        raise not_found("Verse", str(verse_id))

    vid = verse_id
    asyncio.create_task(run_in_background(
        lambda s: s.execute(sa_update(Verse).where(Verse.id == vid).values(view_count=Verse.view_count + 1))
    ))
    related = await verse_service.get_related(verse_id, limit=6)

    response = {
        "id": str(verse.id),
        "full_verse": verse.full_verse,
        "hemistich_1": verse.hemistich_1,
        "hemistich_2": verse.hemistich_2,
        "position": verse.position,
        "is_famous": verse.is_famous,
        "poet_name_ar": verse.poet_name_ar,
        "poem_title_ar": verse.poem_title_ar,
        "poem_slug": verse.poem_slug,
        "poet_slug": verse.poet_slug,
        "poet_id": str(verse.poet_id),
        "poem_id": str(verse.poem_id),
        "explanations": [
            {
                "id": str(e.id),
                "type": e.explanation_type,
                "explanation_ar": e.explanation_ar,
                "difficult_words": e.difficult_words or [],
                "is_ai_generated": e.is_ai_generated,
                "is_reviewed": e.is_reviewed,
            }
            for e in verse.explanations
        ],
        "related_verses": related,
    }

    asyncio.create_task(cache.set(cache_key, response, ttl=86400))
    return response


@router.get("/{verse_id}/related", summary="Get related verses")
async def get_related(
    verse_id: UUID,
    limit: int = Query(6, ge=1, le=20),
    verse_service: VerseService = Depends(get_verse_service),
    cache: CacheService = Depends(get_cache),
):
    cache_key = cache.related_key(str(verse_id))
    cached = await cache.get(cache_key)
    if cached:
        return cached

    related = await verse_service.get_related(verse_id, limit=limit)
    asyncio.create_task(cache.set(cache_key, related, ttl=3600))
    return {"related": related}
