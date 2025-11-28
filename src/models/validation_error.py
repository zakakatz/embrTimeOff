"""ImportValidationError model for tracking detailed validation errors."""

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.models.base import Base


class ErrorType(enum.Enum):
    """Types of validation errors that can occur during import."""
    
    STRUCTURAL = "structural"
    DATA_TYPE = "data_type"
    CONSTRAINT_VIOLATION = "constraint_violation"
    BUSINESS_RULE = "business_rule"
    DUPLICATE_RECORD = "duplicate_record"
    REFERENCE_ERROR = "reference_error"


class Severity(enum.Enum):
    """Severity levels for validation errors."""
    
    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ResolutionStatus(enum.Enum):
    """Status of error resolution."""
    
    UNRESOLVED = "unresolved"
    RESOLVED = "resolved"
    IGNORED = "ignored"
    AUTO_CORRECTED = "auto_corrected"


class ImportValidationError(Base):
    """
    Model for tracking detailed validation errors during imports.
    
    Provides comprehensive error reporting with resolution guidance,
    enabling users to understand and fix data issues.
    """
    
    __tablename__ = "import_validation_errors"
    
    # Primary Key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    
    # Foreign keys
    import_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("import_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    row_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("import_rows.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    
    # Error classification
    error_type: Mapped[ErrorType] = mapped_column(
        Enum(ErrorType, name="error_type"),
        nullable=False,
        index=True,
    )
    severity: Mapped[Severity] = mapped_column(
        Enum(Severity, name="severity"),
        nullable=False,
        index=True,
    )
    
    # Error details
    error_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    error_message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    
    # Field-specific information (optional)
    field_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    field_value: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    
    # Resolution guidance
    expected_format: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Description of the expected format or value",
    )
    suggested_correction: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Suggested fix for the error",
    )
    
    # Resolution tracking
    resolution_status: Mapped[ResolutionStatus] = mapped_column(
        Enum(ResolutionStatus, name="resolution_status"),
        nullable=False,
        default=ResolutionStatus.UNRESOLVED,
    )
    requires_manual_review: Mapped[bool] = mapped_column(
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
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    # Relationships
    import_job: Mapped["ImportJob"] = relationship(
        "ImportJob",
        back_populates="validation_error_records",
    )
    import_row: Mapped[Optional["ImportRow"]] = relationship(
        "ImportRow",
        back_populates="validation_errors",
    )
    
    # Composite indexes for common query patterns
    __table_args__ = (
        Index("ix_validation_error_job_severity", "import_job_id", "severity"),
        Index("ix_validation_error_job_type", "import_job_id", "error_type"),
        Index("ix_validation_error_resolution", "resolution_status", "requires_manual_review"),
    )
    
    def __repr__(self) -> str:
        return (
            f"<ImportValidationError("
            f"id={self.id}, "
            f"type={self.error_type.value}, "
            f"severity={self.severity.value}, "
            f"code={self.error_code}"
            f")>"
        )


# Avoid circular imports
from src.models.import_job import ImportJob
from src.models.import_row import ImportRow

