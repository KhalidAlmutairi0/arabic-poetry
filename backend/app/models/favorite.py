from sqlalchemy import Column, String, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from app.core.database import Base
from app.models.mixins import TimestampMixin


class Favorite(Base, TimestampMixin):
    __tablename__ = "favorites"
    __table_args__ = (
        UniqueConstraint("user_id", "entity_type", "entity_id", name="uq_favorite_user_entity"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_type = Column(String(20), nullable=False)   # verse|poem|poet
    entity_id = Column(UUID(as_uuid=True), nullable=False)

    user = relationship("User", back_populates="favorites")

    def __repr__(self) -> str:
        return f"<Favorite {self.entity_type}:{self.entity_id}>"
