"""
Discovery Router — explicit endpoint for finding poems not in our DB.
Called by the frontend when the main search returns 0 results.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.discovery_service import DiscoveryService
from app.core.database import get_db

router = APIRouter(prefix="/discover", tags=["discover"])


@router.get("/", summary="Discover poems from external sources")
async def discover(
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
