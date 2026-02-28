"""Document metadata model."""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from backend.database import Base


class Document(Base):
    """Processed document tracking model."""

    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)

    # Ownership
    owner_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="documents")

    # Metadata
    original_filename = Column(String, nullable=False)
    operation_type = Column(String, nullable=False)

    # File statistics
    input_size_mb = Column(String, nullable=True)
    output_size_mb = Column(String, nullable=True)
    page_count = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
