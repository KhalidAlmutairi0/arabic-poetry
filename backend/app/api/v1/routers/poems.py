from fastapi import APIRouter, Depends, Query
from uuid import UUID
from sqlalchemy import update as sa_update
from app.services.poem_service import PoemService
from app.models.poem import Poem
from app.api.v1.dependencies import get_poem_service, get_cache
from app.core.cache import CacheService
from app.core.database import run_in_background
from app.core.exceptions import not_found
import asyncio

router = APIRouter(prefix="/poems", tags=["poems"])


@router.get("/", summary="List poems")
async def list_poems(
    poet_id: str | None = Query(None),
    era: str | None = Query(None),
    meter: str | None = Query(None),
    category: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    poem_service: PoemService = Depends(get_poem_service),
):
    return await poem_service.list_poems(
        poet_id=UUID(poet_id) if poet_id else None,
        era=era,
        meter=meter,
        category_slug=category,
        page=page,
        limit=limit,
    )


@router.get("/slugs", summary="Get all poem slugs (for sitemap)")
async def get_poem_slugs(
    poem_service: PoemService = Depends(get_poem_service),
):
    slugs = await poem_service.get_all_slugs()
    return {"slugs": slugs}


@router.get("/{slug}", summary="Get full poem with verses")
async def get_poem(
    slug: str,
    poem_service: PoemService = Depends(get_poem_service),
    cache: CacheService = Depends(get_cache),
):
    cache_key = cache.poem_key(slug)
    cached = await cache.get(cache_key)
    if cached:
        return cached

    try:
        poem = await poem_service.get_by_slug(slug, include_verses=True)
    except Exception:
        raise not_found("Poem", slug)

    # Increment view count (non-blocking, own session)
    poem_id = poem.id
    asyncio.create_task(run_in_background(
        lambda s: s.execute(sa_update(Poem).where(Poem.id == poem_id).values(view_count=Poem.view_count + 1))
    ))

    response = {
        "id": str(poem.id),
        "title_ar": poem.title_ar,
        "title_en": poem.title_en,
        "slug": poem.slug,
        "meter": poem.meter,
        "rhyme_char": poem.rhyme_char,
        "era": poem.era,
        "is_verified": poem.is_verified,
        "view_count": poem.view_count,
        "poet": {
            "id": str(poem.poet.id),
            "name_ar": poem.poet.name_ar,
            "slug": poem.poet.slug,
            "era": poem.poet.era,
        },
        "categories": [
            {"id": str(c.id), "name_ar": c.name_ar, "slug": c.slug}
            for c in (poem.categories or [])
        ],
        "verses": [
            {
                "id": str(v.id),
                "position": v.position,
                "hemistich_1": v.hemistich_1,
                "hemistich_2": v.hemistich_2,
                "full_verse": v.full_verse,
                "is_famous": v.is_famous,
            }
            for v in poem.verses
        ],
    }

    asyncio.create_task(cache.set(cache_key, response, ttl=86400))
    return response
