from sqlalchemy import Column, String, Boolean, Integer, SmallInteger, Text, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from app.core.database import Base
from app.models.mixins import TimestampMixin


class Poem(Base, TimestampMixin):
    __tablename__ = "poems"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    poet_id = Column(UUID(as_uuid=True), ForeignKey("poets.id", ondelete="CASCADE"), nullable=False, index=True)
    title_ar = Column(String(500), nullable=False)
    title_en = Column(String(500))
    slug = Column(String(600), unique=True, nullable=False, index=True)
    full_text = Column(Text, nullable=False)
    meter = Column(String(100), index=True)       # البحر الشعري
    rhyme_char = Column(String(10))               # حرف الروي
    verse_count = Column(SmallInteger, default=0)
    era = Column(String(50), index=True)
    source = Column(String(500))
    is_verified = Column(Boolean, default=False, nullable=False)
    is_published = Column(Boolean, default=True, nullable=False, index=True)
    view_count = Column(Integer, default=0, nullable=False)
    metadata_ = Column("metadata", JSON, default=dict)

    # Relationships
    poet = relationship("Poet", back_populates="poems")
    verses = relationship("Verse", back_populates="poem", order_by="Verse.position", lazy="select")
    categories = relationship("Category", secondary="poem_categories", back_populates="poems")

    def __repr__(self) -> str:
        return f"<Poem {self.title_ar}>"
