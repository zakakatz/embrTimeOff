"""ImportJob model for tracking file import operations."""

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
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.models.base import Base


class ImportJobStatus(enum.Enum):
    """Status values for import job processing."""
    
    PENDING = "pending"
    VALIDATING = "validating"
    MAPPING = "mapping"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ROLLED_BACK = "rolled_back"


class ImportJob(Base):
    """
    Model for tracking import jobs and file upload processing.
    
    Tracks the lifecycle of a file import including validation,
    mapping, processing status, and rollback capability.
    """
    
    __tablename__ = "import_jobs"
    
    # Primary Key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    
    # Reference and identification
    import_reference_id: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )
    
    # Foreign keys
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    
    # File information
    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    file_size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    file_checksum: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    
    # Status
    status: Mapped[ImportJobStatus] = mapped_column(
        Enum(ImportJobStatus, name="import_job_status"),
        nullable=False,
        default=ImportJobStatus.PENDING,
        index=True,
    )
    
    # Row counters
    total_rows: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
    )
    processed_rows: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
    )
    successful_rows: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
    )
    error_rows: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
    )
    
    # JSONB fields for flexible data storage
    validation_errors: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
    )
    mapping_config: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
    )
    field_mappings: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
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
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    # Rollback support
    rollback_token: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )
    rollback_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    rolled_back_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    rolled_back_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    
    # Soft delete
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    # Relationships
    rows: Mapped[List["ImportRow"]] = relationship(
        "ImportRow",
        back_populates="import_job",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    validation_error_records: Mapped[List["ImportValidationError"]] = relationship(
        "ImportValidationError",
        back_populates="import_job",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    audit_logs: Mapped[List["ImportAuditLog"]] = relationship(
        "ImportAuditLog",
        back_populates="import_job",
        lazy="dynamic",
    )
    rollback_entities: Mapped[List["ImportRollbackEntity"]] = relationship(
        "ImportRollbackEntity",
        back_populates="import_job",
        lazy="dynamic",
    )
    statistics: Mapped[Optional["ImportStatistics"]] = relationship(
        "ImportStatistics",
        back_populates="import_job",
        uselist=False,
        cascade="all, delete-orphan",
    )
    
    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "file_size_bytes >= 1 AND file_size_bytes <= 104857600",
            name="ck_import_job_file_size_range",
        ),
        Index("ix_import_jobs_checksum_status", "file_checksum", "status"),
    )
    
    def __repr__(self) -> str:
        return f"<ImportJob(id={self.id}, reference={self.import_reference_id}, status={self.status.value})>"


# Import here to avoid circular imports
from src.models.import_audit import ImportAuditLog
from src.models.import_rollback import ImportRollbackEntity
from src.models.import_row import ImportRow
from src.models.import_statistics import ImportStatistics
from src.models.validation_error import ImportValidationError

