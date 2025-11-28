"""EmployeeSelfService model for employee self-service configurations."""

import enum
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

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
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.models.base import Base


class ProfileVisibilityLevel(enum.Enum):
    """Visibility levels for employee profile information."""
    
    PRIVATE = "private"
    TEAM = "team"
    DEPARTMENT = "department"
    ORGANIZATION = "organization"
    PUBLIC = "public"


class NotificationPreference(enum.Enum):
    """Notification delivery preferences."""
    
    EMAIL = "email"
    IN_APP = "in_app"
    BOTH = "both"
    NONE = "none"


class EmployeeSelfService(Base):
    """
    Configuration model for employee self-service functionality.
    
    Stores personal preferences, visibility settings, notification
    configurations, and other self-service options for each employee.
    """
    
    __tablename__ = "employee_self_services"
    
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
        unique=True,
        index=True,
    )
    
    # Profile visibility settings
    profile_visibility_level: Mapped[ProfileVisibilityLevel] = mapped_column(
        Enum(ProfileVisibilityLevel, name="profile_visibility_level"),
        nullable=False,
        default=ProfileVisibilityLevel.TEAM,
    )
    show_email: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    show_phone: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    show_location: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    show_department: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    show_manager: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    show_hire_date: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    
    # Dashboard preferences
    dashboard_preference_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
        comment="Custom dashboard layout and widget preferences",
    )
    default_landing_page: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="dashboard",
    )
    items_per_page: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=25,
    )
    
    # Notification preferences
    notification_preference: Mapped[NotificationPreference] = mapped_column(
        Enum(NotificationPreference, name="notification_preference"),
        nullable=False,
        default=NotificationPreference.BOTH,
    )
    email_notifications_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    push_notifications_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    notify_on_request_status: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    notify_on_approval_needed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    notification_digest_frequency: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="immediate",
        comment="immediate, daily, weekly",
    )
    
    # Self-service permissions
    can_edit_personal_info: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    can_edit_contact_info: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    can_edit_emergency_contacts: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    can_view_compensation: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    can_view_documents: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    can_upload_documents: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    
    # Audit and security
    audit_trail_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    audit_retention_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=365,
    )
    require_mfa_for_sensitive: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    session_timeout_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=30,
    )
    
    # Localization
    preferred_language: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="en",
    )
    preferred_timezone: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="UTC",
    )
    date_format: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="YYYY-MM-DD",
    )
    time_format: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="24h",
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
    last_accessed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    def __repr__(self) -> str:
        return (
            f"<EmployeeSelfService("
            f"id={self.id}, "
            f"employee_id={self.employee_id}, "
            f"visibility={self.profile_visibility_level.value}"
            f")>"
        )

