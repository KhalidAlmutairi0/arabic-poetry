from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from sqlalchemy.orm import selectinload
from app.models.poem import Poem
from app.models.verse import Verse
from app.models.poet import Poet
from app.models.category import Category, PoemCategory
from app.core.exceptions import NotFoundException
from app.utils.arabic_normalizer import arabic_to_slug, normalizer
import logging

logger = logging.getLogger(__name__)


class PoemService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_slug(self, slug: str, include_verses: bool = True) -> Poem:
        query = select(Poem).where(Poem.slug == slug, Poem.is_published == True)
        if include_verses:
            query = query.options(
                selectinload(Poem.verses),
                selectinload(Poem.poet),
                selectinload(Poem.categories),
            )
        result = await self.db.execute(query)
        poem = result.scalar_one_or_none()
        if not poem:
            raise NotFoundException("Poem", slug)
        return poem

    async def get_by_id(self, poem_id: UUID) -> Poem:
        result = await self.db.execute(select(Poem).where(Poem.id == poem_id))
        poem = result.scalar_one_or_none()
        if not poem:
            raise NotFoundException("Poem", str(poem_id))
        return poem

    async def list_poems(
        self,
        poet_id: UUID | None = None,
        era: str | None = None,
        meter: str | None = None,
        category_slug: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> dict:
        query = select(Poem).where(Poem.is_published == True)
        count_query = select(func.count(Poem.id)).where(Poem.is_published == True)

        if poet_id:
            query = query.where(Poem.poet_id == poet_id)
            count_query = count_query.where(Poem.poet_id == poet_id)
        if era:
            query = query.where(Poem.era == era)
            count_query = count_query.where(Poem.era == era)
        if meter:
            query = query.where(Poem.meter == meter)
            count_query = count_query.where(Poem.meter == meter)
        if category_slug:
            cat_subq = (
                select(PoemCategory.poem_id)
                .join(Category, Category.id == PoemCategory.category_id)
                .where(Category.slug == category_slug)
            )
            query = query.where(Poem.id.in_(cat_subq))
            count_query = count_query.where(Poem.id.in_(cat_subq))

        query = (
            query
            .options(selectinload(Poem.poet))
            .order_by(Poem.view_count.desc())
            .limit(limit)
            .offset((page - 1) * limit)
        )

        poems_result = await self.db.execute(query)
        total_result = await self.db.execute(count_query)

        return {
            "items": list(poems_result.scalars().all()),
            "total": total_result.scalar_one(),
            "page": page,
            "limit": limit,
        }

    async def increment_view(self, poem_id: UUID) -> None:
        await self.db.execute(
            update(Poem).where(Poem.id == poem_id).values(view_count=Poem.view_count + 1)
        )

    async def create_with_verses(self, poem_data: dict, verses_data: list[dict]) -> Poem:
        """Create poem + all its verses atomically."""
        if not poem_data.get("slug"):
            poet_name = poem_data.pop("poet_name_ar", "")
            title = poem_data["title_ar"]
            poem_data["slug"] = arabic_to_slug(f"{poet_name} {title}")

        poem = Poem(**{k: v for k, v in poem_data.items() if hasattr(Poem, k)})
        self.db.add(poem)
        await self.db.flush()  # Get poem.id

        for i, vd in enumerate(verses_data, start=1):
            full_verse = vd.get("full_verse", "")
            verse = Verse(
                poem_id=poem.id,
                poet_id=poem.poet_id,
                position=i,
                hemistich_1=vd.get("hemistich_1", full_verse),
                hemistich_2=vd.get("hemistich_2"),
                full_verse=full_verse,
                full_verse_normalized=normalizer.normalize(full_verse),
                hemistich_1_normalized=normalizer.normalize(vd.get("hemistich_1", "")),
                hemistich_2_normalized=normalizer.normalize(vd.get("hemistich_2", "") or ""),
                poet_name_ar=vd.get("poet_name_ar"),
                poem_title_ar=poem.title_ar,
                poem_slug=poem.slug,
            )
            self.db.add(verse)

        poem.verse_count = len(verses_data)
        await self.db.flush()
        return poem

    async def get_all_slugs(self) -> list[str]:
        result = await self.db.execute(select(Poem.slug))
        return [row[0] for row in result.fetchall()]
