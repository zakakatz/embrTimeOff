"""EmployeeFieldPermission model for field-level access control."""

import enum
import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import DATERANGE, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from src.models.base import Base


class FieldCategory(enum.Enum):
    """Categories of employee profile fields."""
    
    PERSONAL = "personal"
    CONTACT = "contact"
    EMERGENCY = "emergency"
    EMPLOYMENT = "employment"
    COMPENSATION = "compensation"
    BANKING = "banking"
    TAX = "tax"
    BENEFITS = "benefits"
    PERFORMANCE = "performance"
    DOCUMENTS = "documents"
    CUSTOM = "custom"


class VisibilityLevel(enum.Enum):
    """Visibility level for field access."""
    
    HIDDEN = "hidden"
    READ_ONLY = "read_only"
    READ_WRITE = "read_write"
    ADMIN_ONLY = "admin_only"
    RESTRICTED = "restricted"


class EditPermissionLevel(enum.Enum):
    """Permission level for editing fields."""
    
    NO_EDIT = "no_edit"
    SELF_EDIT = "self_edit"
    MANAGER_EDIT = "manager_edit"
    HR_EDIT = "hr_edit"
    ADMIN_EDIT = "admin_edit"


class ViewPermissionLevel(enum.Enum):
    """Permission level for viewing fields."""
    
    NO_VIEW = "no_view"
    PERSONAL_ONLY = "personal_only"
    SUPERVISED = "supervised"
    PUBLIC = "public"
    RESTRICTED = "restricted"


class EmployeeFieldPermission(Base):
    """
    Field-level permission model for controlling employee profile access.
    
    Provides granular control over what employees can view and edit,
    with support for approval workflows, time-based permissions, and
    periodic permission reviews.
    """
    
    __tablename__ = "employee_field_permissions"
    
    # Primary Key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    
    # Foreign keys
    employee_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("employee.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    profile_field_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="Reference to specific profile field definition",
    )
    
    # Field identification
    field_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    field_category: Mapped[FieldCategory] = mapped_column(
        Enum(FieldCategory, name="field_category"),
        nullable=False,
        index=True,
    )
    
    # Permission levels
    visibility_level: Mapped[VisibilityLevel] = mapped_column(
        Enum(VisibilityLevel, name="visibility_level"),
        nullable=False,
        default=VisibilityLevel.READ_ONLY,
    )
    edit_permission_level: Mapped[EditPermissionLevel] = mapped_column(
        Enum(EditPermissionLevel, name="edit_permission_level"),
        nullable=False,
        default=EditPermissionLevel.NO_EDIT,
    )
    view_permission_level: Mapped[ViewPermissionLevel] = mapped_column(
        Enum(ViewPermissionLevel, name="view_permission_level"),
        nullable=False,
        default=ViewPermissionLevel.PERSONAL_ONLY,
    )
    
    # Approval workflow configuration
    approval_chain_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Workflow configuration for approval chain",
    )
    requires_approval: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    approval_levels: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
    
    # Time-based permissions
    effective_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        server_default=func.current_date(),
    )
    expire_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )
    validity_range: Mapped[Optional[Any]] = mapped_column(
        DATERANGE,
        nullable=True,
        comment="PostgreSQL daterange for permission validity period",
    )
    
    # Permission review tracking
    permission_review_cycle_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=365,
    )
    last_permission_review: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    next_review_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )
    reviewed_by_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("employee.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # Audit and tracking
    audit_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    exception_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    exception_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    
    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    is_inherited: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether permission is inherited from role/group",
    )
    inheritance_source: Mapped[Optional[str]] = mapped_column(
        String(100),
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
    granted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    granted_by_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("employee.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # Table constraints and indexes
    __table_args__ = (
        # Minimum value constraints
        CheckConstraint(
            "permission_review_cycle_days >= 30",
            name="ck_field_permission_review_cycle_min",
        ),
        CheckConstraint(
            "exception_count >= 0",
            name="ck_field_permission_exception_count_min",
        ),
        CheckConstraint(
            "approval_levels >= 1",
            name="ck_field_permission_approval_levels_min",
        ),
        # Unique constraint per employee/field combination
        UniqueConstraint(
            "employee_id",
            "field_name",
            "field_category",
            name="uq_employee_field_permission",
        ),
        # Composite indexes for common queries
        Index("ix_field_permission_employee_category", "employee_id", "field_category"),
        Index("ix_field_permission_employee_active", "employee_id", "is_active"),
        Index("ix_field_permission_review_date", "next_review_date"),
    )
    
    def __repr__(self) -> str:
        return (
            f"<EmployeeFieldPermission("
            f"id={self.id}, "
            f"employee_id={self.employee_id}, "
            f"field={self.field_name}, "
            f"visibility={self.visibility_level.value}"
            f")>"
        )

