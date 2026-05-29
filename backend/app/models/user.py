from sqlalchemy import Column, String, Boolean, Text, JSON, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from app.core.database import Base
from app.models.mixins import TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(300), unique=True, nullable=False, index=True)
    hashed_password = Column(String(200))
    name = Column(String(200))
    avatar_url = Column(Text)
    role = Column(String(20), default="user", nullable=False)   # user|admin|moderator
    is_active = Column(Boolean, default=True, nullable=False)
    last_login_at = Column(DateTime(timezone=True))
    metadata_ = Column("metadata", JSON, default=dict)

    favorites = relationship("Favorite", back_populates="user", lazy="select")

    def __repr__(self) -> str:
        return f"<User {self.email}>"
