"""EmployeeAuditTrail model for tracking employee profile changes."""

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from src.models.base import Base


class ChangeType(enum.Enum):
    """Types of changes tracked in audit trail."""
    
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


class EmployeeAuditTrail(Base):
    """
    Immutable audit trail record for employee profile changes.
    
    Captures field-level changes with previous and new values,
    user attribution, and timestamp for compliance tracking.
    """
    
    __tablename__ = "employee_audit_trail"
    
    # Primary Key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    
    # Reference to employee
    employee_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("employee.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Field-level change tracking
    changed_field: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    previous_value: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    new_value: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    
    # Change metadata
    changed_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    change_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    change_type: Mapped[ChangeType] = mapped_column(
        Enum(ChangeType, name="change_type"),
        nullable=False,
        index=True,
    )
    
    # Optional context
    change_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True,
    )
    user_agent: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    
    # Composite indexes for common query patterns
    __table_args__ = (
        Index("idx_audit_employee_timestamp", "employee_id", "change_timestamp"),
    )
    
    def __repr__(self) -> str:
        return (
            f"<EmployeeAuditTrail("
            f"id={self.id}, "
            f"employee_id={self.employee_id}, "
            f"field={self.changed_field}, "
            f"type={self.change_type.value}"
            f")>"
        )

