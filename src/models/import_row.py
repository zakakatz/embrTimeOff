"""ImportRow model for tracking individual rows within an import job."""

import enum
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.models.base import Base


class ValidationStatus(enum.Enum):
    """Validation status values for import rows."""
    
    PENDING = "pending"
    VALID = "valid"
    INVALID = "invalid"
    WARNING = "warning"


class ImportRow(Base):
    """
    Model for tracking individual rows within an import job.
    
    Stores source data, validation results, mapped data,
    and processing status for each row in an import file.
    """
    
    __tablename__ = "import_rows"
    
    # Primary Key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    
    # Foreign key to import job
    import_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("import_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Row identification
    row_number: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    
    # Source and mapped data
    source_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
    )
    mapped_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
    )
    
    # Validation
    validation_status: Mapped[ValidationStatus] = mapped_column(
        Enum(ValidationStatus, name="validation_status"),
        nullable=False,
        default=ValidationStatus.PENDING,
    )
    error_details: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
    )
    
    # Processing status
    is_processed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    
    # Relationships
    import_job: Mapped["ImportJob"] = relationship(
        "ImportJob",
        back_populates="rows",
    )
    validation_errors: Mapped[List["ImportValidationError"]] = relationship(
        "ImportValidationError",
        back_populates="import_row",
        cascade="all, delete-orphan",
    )
    
    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "row_number >= 1",
            name="ck_import_row_row_number_min",
        ),
        UniqueConstraint(
            "import_job_id",
            "row_number",
            name="uq_import_row_job_row_number",
        ),
        Index("ix_import_rows_validation_status", "validation_status"),
        Index("ix_import_rows_is_processed", "is_processed"),
    )
    
    def __repr__(self) -> str:
        return f"<ImportRow(id={self.id}, job_id={self.import_job_id}, row={self.row_number}, status={self.validation_status.value})>"


# Import here to avoid circular imports
from src.models.import_job import ImportJob
from src.models.validation_error import ImportValidationError

