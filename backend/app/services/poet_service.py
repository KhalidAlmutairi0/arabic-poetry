from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.poet import Poet
from app.models.poem import Poem
from app.models.verse import Verse
from app.core.exceptions import NotFoundException
from app.utils.arabic_normalizer import arabic_to_slug
import logging

logger = logging.getLogger(__name__)


class PoetService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_slug(self, slug: str) -> Poet:
        result = await self.db.execute(select(Poet).where(Poet.slug == slug))
        poet = result.scalar_one_or_none()
        if not poet:
            raise NotFoundException("Poet", slug)
        return poet

    async def get_by_id(self, poet_id: UUID) -> Poet:
        result = await self.db.execute(select(Poet).where(Poet.id == poet_id))
        poet = result.scalar_one_or_none()
        if not poet:
            raise NotFoundException("Poet", str(poet_id))
        return poet

    async def list_poets(
        self,
        era: str | None = None,
        page: int = 1,
        limit: int = 24,
    ) -> dict:
        query = select(Poet)
        count_query = select(func.count(Poet.id))

        if era:
            query = query.where(Poet.era == era)
            count_query = count_query.where(Poet.era == era)

        query = query.order_by(Poet.verse_count.desc()).limit(limit).offset((page - 1) * limit)

        poets_result = await self.db.execute(query)
        total_result = await self.db.execute(count_query)

        poets = list(poets_result.scalars().all())
        total = total_result.scalar_one()

        return {
            "items": poets,
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": (total + limit - 1) // limit,
        }

    async def get_poems(self, poet_id: UUID, limit: int = 20, offset: int = 0) -> list[Poem]:
        result = await self.db.execute(
            select(Poem)
            .where(Poem.poet_id == poet_id, Poem.is_published == True)
            .order_by(Poem.view_count.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_famous_verses(self, poet_id: UUID, limit: int = 10) -> list[Verse]:
        result = await self.db.execute(
            select(Verse)
            .where(Verse.poet_id == poet_id, Verse.is_famous == True)
            .order_by(Verse.view_count.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def create(self, data: dict) -> Poet:
        if not data.get("slug"):
            data["slug"] = arabic_to_slug(data["name_ar"])

        poet = Poet(**data)
        self.db.add(poet)
        await self.db.flush()
        return poet

    async def get_all_slugs(self) -> list[str]:
        result = await self.db.execute(select(Poet.slug))
        return [row[0] for row in result.fetchall()]
