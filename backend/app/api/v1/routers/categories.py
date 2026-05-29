from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.category import Category
from app.core.database import get_db
from app.core.exceptions import not_found

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("/", summary="List all categories")
async def list_categories(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Category).order_by(Category.display_order)
    )
    categories = result.scalars().all()
    # Return plain list (not wrapped dict) so frontend can consume directly
    return [
        {
            "id": str(c.id),
            "name_ar": c.name_ar,
            "name_en": c.name_en,
            "slug": c.slug,
            "icon": c.icon,
            "color": c.color,
            "description_ar": c.description_ar,
            "poem_count": c.poem_count,
        }
        for c in categories
    ]


@router.get("/{slug}", summary="Get category detail")
async def get_category(slug: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Category).where(Category.slug == slug))
    category = result.scalar_one_or_none()
    if not category:
        raise not_found("Category", slug)
    return {
        "id": str(category.id),
        "name_ar": category.name_ar,
        "name_en": category.name_en,
        "slug": category.slug,
        "description_ar": category.description_ar if hasattr(category, "description_ar") else None,
        "icon": category.icon,
        "color": category.color,
        "poem_count": category.poem_count,
    }
