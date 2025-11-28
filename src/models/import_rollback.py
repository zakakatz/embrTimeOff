"""ImportRollbackEntity model for entity state restoration."""

import enum
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import (
    Boolean,
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


class ActionPerformed(enum.Enum):
    """Type of action performed on an entity during import."""
    
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"


class RollbackStatus(enum.Enum):
    """Status of rollback processing for an entity."""
    
    NOT_PROCESSED = "not_processed"
    PROCESSED = "processed"
    FAILED = "failed"
    PARTIAL = "partial"


class ImportRollbackEntity(Base):
    """
    Model for storing entity states to enable rollback of imports.
    
    Captures the original and imported states of entities modified
    during an import, allowing complete restoration for disaster
    recovery and data governance requirements.
    
    Note: Foreign key uses SET NULL to maintain rollback records
    for extended retention even if import job is soft-deleted.
    """
    
    __tablename__ = "import_rollback_entities"
    
    # Primary Key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    
    # Foreign key to import job (SET NULL for extended retention)
    import_job_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("import_jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    
    # Rollback identification
    rollback_token: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    
    # Entity identification
    entity_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Type of entity (e.g., employee, department)",
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    
    # Action tracking
    action_performed: Mapped[ActionPerformed] = mapped_column(
        Enum(ActionPerformed, name="action_performed"),
        nullable=False,
    )
    
    # State snapshots
    original_state: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Entity state before import (NULL for created entities)",
    )
    imported_state: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Entity state after import (NULL for deleted entities)",
    )
    
    # Processing status
    is_processed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    rollback_status: Mapped[RollbackStatus] = mapped_column(
        Enum(RollbackStatus, name="rollback_status"),
        nullable=False,
        default=RollbackStatus.NOT_PROCESSED,
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
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    # Relationship
    import_job: Mapped[Optional["ImportJob"]] = relationship(
        "ImportJob",
        back_populates="rollback_entities",
    )
    
    # Composite indexes for common query patterns
    __table_args__ = (
        Index("ix_rollback_token_entity", "rollback_token", "entity_type"),
        Index("ix_rollback_job_status", "import_job_id", "rollback_status"),
        Index("ix_rollback_entity_lookup", "entity_type", "entity_id"),
    )
    
    def __repr__(self) -> str:
        return (
            f"<ImportRollbackEntity("
            f"id={self.id}, "
            f"entity={self.entity_type}:{self.entity_id}, "
            f"action={self.action_performed.value}, "
            f"status={self.rollback_status.value}"
            f")>"
        )


# Avoid circular imports
from src.models.import_job import ImportJob

