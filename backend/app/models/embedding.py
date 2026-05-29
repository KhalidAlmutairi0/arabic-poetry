from sqlalchemy import Column, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector
import uuid
from app.core.database import Base
from app.models.mixins import TimestampMixin
from app.core.config import settings


class Embedding(Base, TimestampMixin):
    __tablename__ = "embeddings"
    __table_args__ = (
        UniqueConstraint("entity_type", "entity_id", "model_name", name="uq_embedding_entity_model"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type = Column(String(20), nullable=False, index=True)   # verse|poem|poet
    entity_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    model_name = Column(String(100), nullable=False)
    vector = Column(Vector(settings.embedding_dimensions), nullable=False)

    def __repr__(self) -> str:
        return f"<Embedding {self.entity_type}:{self.entity_id}>"
