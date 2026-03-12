"""Document metadata model."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.base import Base

if TYPE_CHECKING:
    from backend.models.user import User


class Document(Base):
    """Processed document tracking model."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Ownership
    owner_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), index=True)

    # Metadata
    original_filename: Mapped[str] = mapped_column(String, nullable=False)
    operation_type: Mapped[str] = mapped_column(String, nullable=False)

    # File statistics
    input_size_mb: Mapped[str | None] = mapped_column(String, nullable=True)
    output_size_mb: Mapped[str | None] = mapped_column(String, nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    # Relationships
    owner: Mapped["User | None"] = relationship("User", back_populates="documents")
