from sqlalchemy import Column, String, Integer, SmallInteger, Text, Float, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from app.core.database import Base


class Category(Base):
    __tablename__ = "categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name_ar = Column(String(100), unique=True, nullable=False)
    name_en = Column(String(100))
    slug = Column(String(100), unique=True, nullable=False, index=True)
    description_ar = Column(Text)
    icon = Column(String(50))
    color = Column(String(7))          # Hex e.g. "#E74C3C"
    display_order = Column(SmallInteger, default=0)
    poem_count = Column(Integer, default=0, nullable=False)

    # Relationships
    poems = relationship("Poem", secondary="poem_categories", back_populates="categories")

    def __repr__(self) -> str:
        return f"<Category {self.name_ar}>"


class PoemCategory(Base):
    __tablename__ = "poem_categories"

    poem_id = Column(UUID(as_uuid=True), ForeignKey("poems.id", ondelete="CASCADE"), primary_key=True)
    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True)
    confidence = Column(Float, default=1.0)
    is_ai_tagged = Column(Boolean, default=False)
