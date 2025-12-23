"""OrganizationalChange model for tracking structural changes within the organization.

This module provides audit trails and change management capabilities for:
- Department changes (create, modify, delete)
- Location changes (create, modify, delete)
- Reporting relationship changes
- Schedule modifications
"""

import enum
import uuid
from datetime import date, datetime
from typing import Any, Dict, Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.models.base import Base


# =============================================================================
# Enums
# =============================================================================

class ChangeType(enum.Enum):
    """Types of organizational changes that can be tracked."""
    
    # Department Changes
    DEPARTMENT_CREATE = "department_create"
    DEPARTMENT_MODIFY = "department_modify"
    DEPARTMENT_DELETE = "department_delete"
    
    # Location Changes
    LOCATION_CREATE = "location_create"
    LOCATION_MODIFY = "location_modify"
    LOCATION_DELETE = "location_delete"
    
    # Reporting Relationship Changes
    REPORTING_CHANGE = "reporting_change"
    
    # Schedule Changes
    SCHEDULE_CHANGE = "schedule_change"


class ChangeStatus(enum.Enum):
    """Status of an organizational change request."""
    
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    IMPLEMENTED = "implemented"
    ROLLED_BACK = "rolled_back"


# =============================================================================
# OrganizationalChange Model
# =============================================================================

class OrganizationalChange(Base):
    """
    Tracks all structural changes within the organization.
    
    Provides complete audit trails for department, location, reporting,
    and schedule modifications with approval workflow support.
    """
    
    __tablename__ = "organizational_change"
    
    # =========================================================================
    # Primary Key
    # =========================================================================
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    
    # =========================================================================
    # Change Classification
    # =========================================================================
    
    change_type: Mapped[ChangeType] = mapped_column(
        Enum(ChangeType, name="change_type"),
        nullable=False,
        index=True,
        comment="Type of organizational change"
    )
    
    entity_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Type of entity being changed (department, location, employee, schedule)"
    )
    
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="ID of the entity being changed"
    )
    
    # =========================================================================
    # Change Data
    # =========================================================================
    
    previous_state: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="State of the entity before the change"
    )
    
    new_state: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        comment="State of the entity after the change"
    )
    
    change_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Reason or justification for the change"
    )
    
    # =========================================================================
    # Approval Workflow
    # =========================================================================
    
    requested_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("employee.id", ondelete="SET NULL"),
        nullable=False,
        index=True,
        comment="Employee who requested the change"
    )
    
    approved_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("employee.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Employee who approved the change"
    )
    
    change_status: Mapped[ChangeStatus] = mapped_column(
        Enum(ChangeStatus, name="change_status"),
        nullable=False,
        default=ChangeStatus.PENDING,
        index=True,
        comment="Current status of the change request"
    )
    
    # =========================================================================
    # Dates
    # =========================================================================
    
    effective_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="Date when the change should take effect"
    )
    
    implementation_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="Date when the change was actually implemented"
    )
    
    rollback_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="Date when the change was rolled back (if applicable)"
    )
    
    # =========================================================================
    # Impact Assessment
    # =========================================================================
    
    impact_assessment: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Assessment of the change impact on the organization"
    )
    
    affected_employees_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of employees affected by this change"
    )
    
    # =========================================================================
    # Timestamps
    # =========================================================================
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="When the change request was created"
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="When the change request was last updated"
    )
    
    # =========================================================================
    # Indexes
    # =========================================================================
    
    __table_args__ = (
        # Composite index for querying changes by entity
        Index("idx_org_change_entity", "entity_type", "entity_id"),
        # Index for finding pending changes
        Index("idx_org_change_pending", "change_status", "effective_date"),
        # Index for finding changes by date range
        Index("idx_org_change_dates", "created_at", "effective_date"),
    )
    
    # =========================================================================
    # Relationships
    # =========================================================================
    
    # Note: Relationships defined with string references to avoid circular imports
    # These can be accessed when the full ORM is loaded
    
    def __repr__(self) -> str:
        return (
            f"<OrganizationalChange("
            f"id={self.id}, "
            f"type={self.change_type.value}, "
            f"entity={self.entity_type}:{self.entity_id}, "
            f"status={self.change_status.value}"
            f")>"
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": str(self.id),
            "change_type": self.change_type.value,
            "entity_type": self.entity_type,
            "entity_id": str(self.entity_id),
            "previous_state": self.previous_state,
            "new_state": self.new_state,
            "change_reason": self.change_reason,
            "requested_by_id": str(self.requested_by_id) if self.requested_by_id else None,
            "approved_by_id": str(self.approved_by_id) if self.approved_by_id else None,
            "change_status": self.change_status.value,
            "effective_date": self.effective_date.isoformat() if self.effective_date else None,
            "implementation_date": self.implementation_date.isoformat() if self.implementation_date else None,
            "rollback_date": self.rollback_date.isoformat() if self.rollback_date else None,
            "impact_assessment": self.impact_assessment,
            "affected_employees_count": self.affected_employees_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

