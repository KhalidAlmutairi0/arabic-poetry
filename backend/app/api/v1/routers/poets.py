from fastapi import APIRouter, Depends, Query
from uuid import UUID
from app.services.poet_service import PoetService
from app.api.v1.dependencies import get_poet_service, get_cache
from app.core.cache import CacheService
from app.core.exceptions import not_found
import asyncio

router = APIRouter(prefix="/poets", tags=["poets"])


@router.get("/", summary="List poets")
async def list_poets(
    era: str | None = Query(None, description="تصفية بالعصر"),
    page: int = Query(1, ge=1),
    limit: int = Query(24, ge=1, le=100),
    poet_service: PoetService = Depends(get_poet_service),
):
    data = await poet_service.list_poets(era=era, page=page, limit=limit)
    # Serialize SQLAlchemy models to plain dicts
    return {
        "items": [
            {
                "id": str(p.id),
                "name_ar": p.name_ar,
                "name_en": p.name_en,
                "slug": p.slug,
                "bio_ar": p.bio_ar,
                "era": p.era,
                "birth_year": p.birth_year,
                "death_year": p.death_year,
                "birth_place_ar": p.birth_place_ar,
                "image_url": p.image_url,
                "poem_count": p.poem_count,
                "verse_count": p.verse_count,
                "is_verified": p.is_verified,
                "famous_verses": [],
            }
            for p in data["items"]
        ],
        "total": data["total"],
        "page": data["page"],
        "size": data["limit"],
    }


@router.get("/slugs", summary="Get all poet slugs (for sitemap)")
async def get_poet_slugs(
    poet_service: PoetService = Depends(get_poet_service),
):
    slugs = await poet_service.get_all_slugs()
    return {"slugs": slugs}


@router.get("/{slug}", summary="Get poet by slug")
async def get_poet(
    slug: str,
    poet_service: PoetService = Depends(get_poet_service),
    cache: CacheService = Depends(get_cache),
):
    cache_key = cache.poet_key(slug)
    cached = await cache.get(cache_key)
    if cached:
        return cached

    try:
        poet = await poet_service.get_by_slug(slug)
    except Exception:
        raise not_found("Poet", slug)

    famous_verses = await poet_service.get_famous_verses(poet.id, limit=6)

    response = {
        "id": str(poet.id),
        "name_ar": poet.name_ar,
        "name_en": poet.name_en,
        "slug": poet.slug,
        "bio_ar": poet.bio_ar,
        "era": poet.era,
        "birth_year": poet.birth_year,
        "death_year": poet.death_year,
        "birth_place_ar": poet.birth_place_ar,
        "image_url": poet.image_url,
        "poem_count": poet.poem_count,
        "verse_count": poet.verse_count,
        "is_verified": poet.is_verified,
        "famous_verses": [
            {
                "id": str(v.id),
                "full_verse": v.full_verse,
                "poem_title_ar": v.poem_title_ar,
                "poem_slug": v.poem_slug,
            }
            for v in famous_verses
        ],
    }

    asyncio.create_task(cache.set(cache_key, response, ttl=86400))
    return response


@router.get("/{slug}/poems", summary="Get poet's poems")
async def get_poet_poems(
    slug: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    poet_service: PoetService = Depends(get_poet_service),
):
    try:
        poet = await poet_service.get_by_slug(slug)
    except Exception:
        raise not_found("Poet", slug)

    poems = await poet_service.get_poems(poet.id, limit=limit, offset=(page - 1) * limit)
    return {
        "poet_id": str(poet.id),
        "poet_name_ar": poet.name_ar,
        "poems": [
            {
                "id": str(p.id),
                "title_ar": p.title_ar,
                "slug": p.slug,
                "verse_count": p.verse_count,
                "meter": p.meter,
                "view_count": p.view_count,
            }
            for p in poems
        ],
    }
