from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.search_service import SearchService
from app.services.discovery_service import DiscoveryService
from app.api.v1.dependencies import get_search_service, get_cache
from app.core.database import get_db
from app.core.cache import CacheService
from app.schemas.search import SearchResponse
import asyncio
import json

router = APIRouter(prefix="/search", tags=["search"])

DISCOVERY_THRESHOLD = 3


@router.get("/", summary="Search Arabic poetry")
async def search(
    q: str = Query(..., min_length=1, max_length=500, description="البحث في الشعر العربي"),
    mode: str = Query("hybrid", description="keyword | semantic | hybrid"),
    type: str = Query("verse", description="verse | poem | poet | all"),
    era: str | None = Query(None, description="تصفية بالعصر"),
    poet_id: str | None = Query(None, description="تصفية بالشاعر"),
    is_famous: bool | None = Query(None, description="الأبيات المشهورة فقط"),
    page: int = Query(1, ge=1, le=100),
    limit: int = Query(20, ge=1, le=50),
    search_service: SearchService = Depends(get_search_service),
    cache: CacheService = Depends(get_cache),
    db: AsyncSession = Depends(get_db),
):
    filters = {}
    if era:
        filters["era"] = era
    if poet_id:
        filters["poet_id"] = poet_id
    if is_famous is not None:
        filters["is_famous"] = is_famous

    filters_str = json.dumps(filters, sort_keys=True)
    cache_key = cache.search_key(q, mode, filters_str, page)
    cached = await cache.get(cache_key)
    if cached:
        return cached

    result = await search_service.search_verses(
        query=q,
        mode=mode,
        filters=filters,
        limit=limit,
        offset=(page - 1) * limit,
    )

    local_hits = result.get("hits", [])
    total_hits = result.get("estimated_total_hits", 0)
    discovery_source = None

    # If local DB returned too few results, search external APIs
    if len(local_hits) < DISCOVERY_THRESHOLD and page == 1 and not is_famous:
        discovery = DiscoveryService(db)
        discovered = await discovery.discover_and_save(q, limit=limit)
        external_hits = discovered.get("hits", [])

        if external_hits:
            # Merge: local results first, then discovered ones
            seen_ids = {h.get("id") for h in local_hits}
            for hit in external_hits:
                if hit.get("id") not in seen_ids:
                    # Remove internal fields before sending to client
                    hit.pop("_all_verses", None)
                    local_hits.append(hit)
                    seen_ids.add(hit.get("id"))

            total_hits = max(total_hits, len(local_hits))
            discovery_source = discovered.get("source")

    response = {
        "hits": local_hits[:limit],
        "estimated_total_hits": total_hits,
        "query": q,
        "mode": result.get("mode", mode),
        "processing_time_ms": result.get("processing_time_ms", 0),
        "page": page,
        "total_pages": (total_hits + limit - 1) // limit if limit > 0 else 0,
    }

    if discovery_source:
        response["discovery_source"] = discovery_source

    # Cache non-empty results (short TTL for discovery results so fresh DB data takes over)
    if response["hits"]:
        ttl = 600 if discovery_source else 3600
        asyncio.create_task(cache.set(cache_key, response, ttl=ttl))

    return response


@router.get("/autocomplete", summary="Search autocomplete")
async def autocomplete(
    q: str = Query(..., min_length=1, max_length=100),
    search_service: SearchService = Depends(get_search_service),
    cache: CacheService = Depends(get_cache),
):
    cache_key = cache.autocomplete_key(q)
    cached = await cache.get(cache_key)
    if cached:
        return cached

    result = await search_service.autocomplete(q)
    asyncio.create_task(cache.set(cache_key, result, ttl=300))
    return result
