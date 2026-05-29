from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.models.verse import Verse
from app.models.verse_explanation import VerseExplanation
from app.models.verse_relation import VerseRelation
from app.models.embedding import Embedding
from app.core.exceptions import NotFoundException
from app.utils.arabic_normalizer import normalizer
import logging

logger = logging.getLogger(__name__)


class VerseService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, verse_id: UUID) -> Verse:
        result = await self.db.execute(select(Verse).where(Verse.id == verse_id))
        verse = result.scalar_one_or_none()
        if not verse:
            raise NotFoundException("Verse", str(verse_id))
        return verse

    async def get_with_all(self, verse_id: UUID) -> Verse:
        """Get verse with explanations and related verses in one query."""
        from sqlalchemy.orm import selectinload

        result = await self.db.execute(
            select(Verse)
            .where(Verse.id == verse_id)
            .options(
                selectinload(Verse.explanations),
                selectinload(Verse.relations_from).selectinload(VerseRelation.related_verse),
            )
        )
        verse = result.scalar_one_or_none()
        if not verse:
            raise NotFoundException("Verse", str(verse_id))
        return verse

    async def get_poem_verses(self, poem_id: UUID) -> list[Verse]:
        result = await self.db.execute(
            select(Verse)
            .where(Verse.poem_id == poem_id)
            .order_by(Verse.position)
        )
        return list(result.scalars().all())

    async def get_explanation(
        self, verse_id: UUID, explanation_type: str = "simple"
    ) -> VerseExplanation | None:
        result = await self.db.execute(
            select(VerseExplanation)
            .where(
                VerseExplanation.verse_id == verse_id,
                VerseExplanation.explanation_type == explanation_type,
            )
        )
        return result.scalar_one_or_none()

    async def save_explanation(
        self,
        verse_id: UUID,
        explanation_type: str,
        explanation_ar: str,
        model_name: str = "qwen2.5:3b",
    ) -> VerseExplanation:
        # Upsert explanation
        existing = await self.get_explanation(verse_id, explanation_type)
        if existing:
            existing.explanation_ar = explanation_ar
            existing.generated_by = model_name
            await self.db.flush()
            return existing

        explanation = VerseExplanation(
            verse_id=verse_id,
            explanation_type=explanation_type,
            explanation_ar=explanation_ar,
            generated_by=model_name,
            is_ai_generated=True,
        )
        self.db.add(explanation)
        await self.db.flush()
        return explanation

    async def increment_view(self, verse_id: UUID) -> None:
        await self.db.execute(
            update(Verse)
            .where(Verse.id == verse_id)
            .values(view_count=Verse.view_count + 1)
        )

    async def get_related(self, verse_id: UUID, limit: int = 6) -> list[dict]:
        """Get pre-computed related verses from verse_relations table."""
        from sqlalchemy.orm import aliased

        related_verse = aliased(Verse)
        result = await self.db.execute(
            select(VerseRelation, related_verse)
            .join(related_verse, VerseRelation.related_id == related_verse.id)
            .where(VerseRelation.verse_id == verse_id)
            .order_by(VerseRelation.similarity.desc())
            .limit(limit)
        )

        rows = result.all()
        return [
            {
                "id": str(row[1].id),
                "full_verse": row[1].full_verse,
                "poet_name_ar": row[1].poet_name_ar,
                "poem_title_ar": row[1].poem_title_ar,
                "poem_slug": row[1].poem_slug,
                "similarity": row[0].similarity,
            }
            for row in rows
        ]

    async def get_famous_verses(self, limit: int = 10) -> list[Verse]:
        result = await self.db.execute(
            select(Verse)
            .where(Verse.is_famous == True)
            .order_by(Verse.view_count.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
