from sqlalchemy import Column, String, Boolean, Integer, SmallInteger, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from app.core.database import Base
from app.models.mixins import TimestampMixin


class Poet(Base, TimestampMixin):
    __tablename__ = "poets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name_ar = Column(String(200), nullable=False, index=True)
    name_en = Column(String(200))
    slug = Column(String(200), unique=True, nullable=False, index=True)
    bio_ar = Column(Text)
    bio_en = Column(Text)
    era = Column(String(50), nullable=False, index=True)  # pre_islamic, abbasid, modern...
    birth_year = Column(SmallInteger)
    death_year = Column(SmallInteger)
    birth_place_ar = Column(String(200))
    nationality_ar = Column(String(100))
    image_url = Column(Text)
    is_verified = Column(Boolean, default=False, nullable=False)
    poem_count = Column(Integer, default=0, nullable=False)
    verse_count = Column(Integer, default=0, nullable=False)
    metadata_ = Column("metadata", JSON, default=dict)

    # Relationships
    poems = relationship("Poem", back_populates="poet", lazy="select")
    verses = relationship("Verse", back_populates="poet", lazy="select")

    def __repr__(self) -> str:
        return f"<Poet {self.name_ar}>"
