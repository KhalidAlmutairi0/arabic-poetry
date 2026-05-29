from sqlalchemy import Column, String, Boolean, Integer, SmallInteger, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from app.core.database import Base
from app.models.mixins import TimestampMixin


class Verse(Base, TimestampMixin):
    __tablename__ = "verses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    poem_id = Column(UUID(as_uuid=True), ForeignKey("poems.id", ondelete="CASCADE"), nullable=False, index=True)
    poet_id = Column(UUID(as_uuid=True), ForeignKey("poets.id"), nullable=False, index=True)
    position = Column(SmallInteger, nullable=False)

    # Verse content (Arabic verse = two hemistiches)
    hemistich_1 = Column(Text, nullable=False)   # الصدر
    hemistich_2 = Column(Text)                   # العجز (nullable for modern poetry)
    full_verse = Column(Text, nullable=False)

    # Normalized versions (for search — diacritics removed, hamza normalized)
    hemistich_1_normalized = Column(Text, index=True)
    hemistich_2_normalized = Column(Text)
    full_verse_normalized = Column(Text, index=True)

    # Denormalized for fast queries (avoid joins on hot paths)
    poet_name_ar = Column(String(200))
    poet_slug = Column(String(300))   # added for search result links
    poem_title_ar = Column(String(500))
    poem_slug = Column(String(600))

    is_famous = Column(Boolean, default=False, nullable=False, index=True)
    is_verified = Column(Boolean, default=False, nullable=False)
    view_count = Column(Integer, default=0, nullable=False)
    share_count = Column(Integer, default=0, nullable=False)

    # Relationships
    poem = relationship("Poem", back_populates="verses")
    poet = relationship("Poet", back_populates="verses")
    explanations = relationship("VerseExplanation", back_populates="verse", lazy="select")
    relations_from = relationship(
        "VerseRelation",
        foreign_keys="VerseRelation.verse_id",
        back_populates="verse",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<Verse {self.full_verse[:50]}>"
