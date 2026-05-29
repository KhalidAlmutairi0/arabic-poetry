from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID


class VerseBase(BaseModel):
    hemistich_1: str = Field(..., min_length=1)
    hemistich_2: str | None = None
    full_verse: str = Field(..., min_length=1)
    position: int = Field(..., ge=1)
    is_famous: bool = False


class VerseCreate(VerseBase):
    poem_id: UUID
    poet_id: UUID


class VerseInDB(VerseBase):
    id: UUID
    poem_id: UUID
    poet_id: UUID
    poet_name_ar: str | None
    poem_title_ar: str | None
    poem_slug: str | None
    view_count: int
    share_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ExplanationSchema(BaseModel):
    id: UUID
    explanation_type: str
    explanation_ar: str
    difficult_words: list[dict]
    literary_devices: list[dict]
    is_ai_generated: bool
    is_reviewed: bool

    model_config = {"from_attributes": True}


class RelatedVerseSchema(BaseModel):
    id: UUID
    full_verse: str
    poet_name_ar: str | None
    poem_title_ar: str | None
    poem_slug: str | None
    similarity: float


class VerseDetail(VerseInDB):
    """Full verse with explanations and related."""
    poem_slug: str | None = None
    poet_slug: str | None = None
    era: str | None = None
    meter: str | None = None
    explanations: list[ExplanationSchema] = []
    related_verses: list[RelatedVerseSchema] = []


class VerseCard(BaseModel):
    """Minimal verse info for search results / cards."""
    id: UUID
    full_verse: str
    hemistich_1: str
    hemistich_2: str | None
    poet_name_ar: str | None
    poem_title_ar: str | None
    poem_slug: str | None
    poet_id: UUID | None
    is_famous: bool

    model_config = {"from_attributes": True}
