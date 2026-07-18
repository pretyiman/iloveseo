from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class User(Base):
    """A user account. Primary key mirrors the Clerk user id (`sub` claim)
    so we never need a separate mapping table between our auth provider
    and our own records."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # Clerk user id
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
