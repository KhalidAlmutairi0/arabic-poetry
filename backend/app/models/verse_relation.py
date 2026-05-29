from sqlalchemy import Column, String, Float, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.mixins import TimestampMixin


class VerseRelation(Base):  # No TimestampMixin — verse_relations has no created_at/updated_at
    __tablename__ = "verse_relations"

    verse_id = Column(UUID(as_uuid=True), ForeignKey("verses.id", ondelete="CASCADE"), primary_key=True)
    related_id = Column(UUID(as_uuid=True), ForeignKey("verses.id", ondelete="CASCADE"), primary_key=True)
    similarity = Column(Float, nullable=False)
    relation_type = Column(String(50), default="semantic")  # semantic|thematic|same_poet

    # Relationships
    verse = relationship("Verse", foreign_keys=[verse_id], back_populates="relations_from")
    related_verse = relationship("Verse", foreign_keys=[related_id])
