"""EmployeeUpdateRequest model for tracking profile update requests."""

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
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from src.models.base import Base


class RequestType(enum.Enum):
    """Types of update requests."""
    
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    CORRECTION = "correction"


class FieldCategoryType(enum.Enum):
    """Categories of fields being updated."""
    
    PERSONAL_INFO = "personal_info"
    CONTACT_INFO = "contact_info"
    EMERGENCY_CONTACT = "emergency_contact"
    ADDRESS = "address"
    BANKING = "banking"
    TAX = "tax"
    BENEFITS = "benefits"
    DOCUMENTS = "documents"
    OTHER = "other"


class RequestStatus(enum.Enum):
    """Status of the update request."""
    
    DRAFT = "draft"
    PENDING = "pending"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    EXPIRED = "expired"


class EmployeeUpdateRequest(Base):
    """
    Model for tracking employee profile update requests.
    
    Enables self-service updates with approval workflows,
    tracking current and proposed values for audit purposes.
    """
    
    __tablename__ = "employee_update_requests"
    
    # Primary Key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    
    # Foreign key to employee
    employee_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("employee.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Request identification
    request_session_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="Groups related requests in a single session",
    )
    request_reference: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        index=True,
    )
    
    # Request classification
    request_type: Mapped[RequestType] = mapped_column(
        Enum(RequestType, name="request_type"),
        nullable=False,
        default=RequestType.UPDATE,
    )
    field_category_type: Mapped[FieldCategoryType] = mapped_column(
        Enum(FieldCategoryType, name="field_category_type"),
        nullable=False,
    )
    
    # Field data
    update_fields_json: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        comment="List of fields being updated",
    )
    current_values_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Current values before update",
    )
    proposed_values_json: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        comment="Proposed new values",
    )
    
    # Request details
    reason_for_change: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    supporting_document_ids: Mapped[Optional[list]] = mapped_column(
        JSONB,
        nullable=True,
        comment="IDs of uploaded supporting documents",
    )
    
    # Status and workflow
    status: Mapped[RequestStatus] = mapped_column(
        Enum(RequestStatus, name="request_status"),
        nullable=False,
        default=RequestStatus.PENDING,
        index=True,
    )
    requires_approval: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    auto_approved: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    
    # Approval workflow
    approval_reference_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )
    approver_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("employee.id", ondelete="SET NULL"),
        nullable=True,
    )
    approval_level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
    approval_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    rejection_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    
    # Priority and escalation
    priority: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="normal",
        comment="low, normal, high, urgent",
    )
    is_escalated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    escalation_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
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
    submitted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    # Composite indexes
    __table_args__ = (
        Index("ix_update_request_employee_status", "employee_id", "status"),
        Index("ix_update_request_session", "request_session_id", "created_at"),
        Index("ix_update_request_approval", "approval_reference_id", "status"),
    )
    
    def __repr__(self) -> str:
        return (
            f"<EmployeeUpdateRequest("
            f"id={self.id}, "
            f"employee_id={self.employee_id}, "
            f"type={self.request_type.value}, "
            f"status={self.status.value}"
            f")>"
        )

