"""ImportAuditLog model for tracking import activities."""

import enum
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.models.base import Base


class ActionType(enum.Enum):
    """Types of actions tracked in import audit log."""
    
    CREATED = "created"
    UPLOADED = "uploaded"
    VALIDATED = "validated"
    PROCESSING_STARTED = "processing_started"
    PROCESSING_COMPLETED = "processing_completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ROLLBACK_REQUESTED = "rollback_requested"
    ROLLBACK_COMPLETED = "rollback_completed"


class ActorRole(enum.Enum):
    """Role of the actor performing the action."""
    
    ADMIN = "admin"
    HR_ADMIN = "hr_admin"
    USER = "user"
    SYSTEM = "system"


class ImportAuditLog(Base):
    """
    Audit log for tracking all import-related activities.
    
    Provides comprehensive tracking of who performed what action,
    when, and from where for compliance and governance requirements.
    
    Note: Foreign key to import_jobs uses SET NULL to maintain audit
    records even if the import job is soft-deleted for compliance.
    """
    
    __tablename__ = "import_audit_logs"
    
    # Primary Key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    
    # Foreign key to import job (SET NULL to preserve audit on soft delete)
    import_job_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("import_jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    
    # Actor information
    actor_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    actor_role: Mapped[ActorRole] = mapped_column(
        Enum(ActorRole, name="actor_role"),
        nullable=False,
    )
    
    # Action details
    action_type: Mapped[ActionType] = mapped_column(
        Enum(ActionType, name="action_type"),
        nullable=False,
        index=True,
    )
    action_details: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
        comment="Additional context about the action",
    )
    
    # Request metadata (optional)
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True,
        comment="IPv4 or IPv6 address",
    )
    user_agent: Mapped[Optional[str]] = mapped_column(
        String(512),
        nullable=True,
    )
    
    # Timestamp
    action_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    
    # Relationship
    import_job: Mapped[Optional["ImportJob"]] = relationship(
        "ImportJob",
        back_populates="audit_logs",
    )
    
    # Composite indexes for common query patterns
    __table_args__ = (
        Index("ix_audit_log_job_timestamp", "import_job_id", "action_timestamp"),
        Index("ix_audit_log_actor_timestamp", "actor_user_id", "action_timestamp"),
        Index("ix_audit_log_action_timestamp", "action_type", "action_timestamp"),
    )
    
    def __repr__(self) -> str:
        return (
            f"<ImportAuditLog("
            f"id={self.id}, "
            f"job_id={self.import_job_id}, "
            f"action={self.action_type.value}, "
            f"actor={self.actor_user_id}"
            f")>"
        )


# Avoid circular imports
from src.models.import_job import ImportJob

