from sqlalchemy import Column, String, Boolean, SmallInteger, Text, JSON, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from app.core.database import Base
from app.models.mixins import TimestampMixin


class VerseExplanation(Base, TimestampMixin):
    __tablename__ = "verse_explanations"
    __table_args__ = (
        UniqueConstraint("verse_id", "explanation_type", name="uq_verse_explanation_type"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    verse_id = Column(UUID(as_uuid=True), ForeignKey("verses.id", ondelete="CASCADE"), nullable=False, index=True)
    explanation_type = Column(String(20), nullable=False, default="simple")  # simple|literary|linguistic

    explanation_ar = Column(Text, nullable=False)
    explanation_en = Column(Text)
    difficult_words = Column(JSON, default=list)      # [{word, meaning_ar, root}]
    literary_devices = Column(JSON, default=list)     # [{device, example, explanation}]

    generated_by = Column(String(100))                # e.g. "qwen2.5:3b"
    is_ai_generated = Column(Boolean, default=True, nullable=False)
    is_reviewed = Column(Boolean, default=False, nullable=False)
    quality_score = Column(SmallInteger)              # 1-10

    # Relationships
    verse = relationship("Verse", back_populates="explanations")

    def __repr__(self) -> str:
        return f"<VerseExplanation {self.explanation_type} for {self.verse_id}>"
