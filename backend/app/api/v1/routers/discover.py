"""
Discovery Router — explicit endpoint for finding poems not in our DB.
Called by the frontend when the main search returns 0 results.
"""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.discovery_service import DiscoveryService
from app.core.database import get_db
from app.core.config import settings
from slowapi import Limiter
from slowapi.util import get_remote_address

router = APIRouter(prefix="/discover", tags=["discover"])
limiter = Limiter(key_func=get_remote_address)


@router.get("/", summary="Discover poems from external sources")
@limiter.limit(settings.rate_limit_ai)
async def discover(
    request: Request,
    q: str = Query(..., min_length=2, max_length=300, description="ابحث عن قصائد جديدة"),
    limit: int = Query(10, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
):
    """
    Search external poetry APIs for poems not in our database.
    Found poems are automatically saved to the DB for future searches.
    """
    discovery = DiscoveryService(db)
    result = await discovery.discover_and_save(q, limit=limit)

    hits = result.get("hits", [])
    for hit in hits:
        hit.pop("_all_verses", None)

    return {
        "hits": hits,
        "total": len(hits),
        "query": q,
        "source": result.get("source", "none"),
        "message": "تم إضافة النتائج إلى قاعدة البيانات تلقائياً" if hits else "لم يتم العثور على نتائج",
    }
