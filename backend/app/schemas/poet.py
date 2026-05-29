from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID


class PoetBase(BaseModel):
    name_ar: str = Field(..., min_length=1, max_length=200)
    name_en: str | None = None
    bio_ar: str | None = None
    bio_en: str | None = None
    era: str
    birth_year: int | None = None
    death_year: int | None = None
    birth_place_ar: str | None = None
    nationality_ar: str | None = None
    image_url: str | None = None


class PoetCreate(PoetBase):
    slug: str | None = None  # Auto-generated if not provided


class PoetUpdate(BaseModel):
    name_ar: str | None = None
    name_en: str | None = None
    bio_ar: str | None = None
    era: str | None = None
    image_url: str | None = None


class PoetInDB(PoetBase):
    id: UUID
    slug: str
    is_verified: bool
    poem_count: int
    verse_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PoetCard(BaseModel):
    """Minimal poet info for cards/lists."""
    id: UUID
    name_ar: str
    name_en: str | None
    slug: str
    era: str
    image_url: str | None
    poem_count: int
    verse_count: int

    model_config = {"from_attributes": True}


class PoetDetail(PoetInDB):
    """Full poet profile with recent poems."""
    recent_poems: list | None = []
    famous_verses: list | None = []
