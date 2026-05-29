from pydantic import BaseModel, Field, field_validator
from typing import Literal
import re


class SearchRequest(BaseModel):
    q: str = Field(..., min_length=1, max_length=500, description="Search query")
    mode: Literal["hybrid", "keyword", "semantic"] = "hybrid"
    type: Literal["verse", "poem", "poet", "all"] = "verse"
    era: str | None = None
    category: str | None = None
    poet_id: str | None = None
    page: int = Field(1, ge=1, le=100)
    limit: int = Field(20, ge=1, le=50)

    @field_validator("q")
    @classmethod
    def sanitize_query(cls, v: str) -> str:
        v = v.strip()
        # Allow Arabic, English, numbers, spaces, common punctuation
        if len(v) > 500:
            raise ValueError("Query too long")
        return v

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.limit


class SearchHit(BaseModel):
    id: str
    full_verse: str | None = None
    hemistich_1: str | None = None
    hemistich_2: str | None = None
    poet_name_ar: str | None = None
    poem_title_ar: str | None = None
    poem_slug: str | None = None
    poet_id: str | None = None
    poem_id: str | None = None
    is_famous: bool = False
    _score: float = 0.0
    _formatted: dict | None = None


class SearchResponse(BaseModel):
    hits: list[SearchHit]
    estimated_total_hits: int
    query: str
    mode: str
    processing_time_ms: int
    page: int
    total_pages: int


class AutocompleteResponse(BaseModel):
    popular: list[dict]
    verses: list[dict]
    poets: list[dict]
