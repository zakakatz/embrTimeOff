"""ActivityLog model for tracking employee-related activities."""

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


class ActivityType(enum.Enum):
    """Types of activities that can be logged."""
    
    # Profile activities
    PROFILE_VIEW = "profile_view"
    PROFILE_UPDATE = "profile_update"
    PROFILE_CREATE = "profile_create"
    
    # Employment activities
    STATUS_CHANGE = "status_change"
    DEPARTMENT_CHANGE = "department_change"
    ROLE_CHANGE = "role_change"
    MANAGER_CHANGE = "manager_change"
    
    # Request activities
    REQUEST_SUBMITTED = "request_submitted"
    REQUEST_APPROVED = "request_approved"
    REQUEST_REJECTED = "request_rejected"
    
    # System activities
    SYSTEM_UPDATE = "system_update"
    IMPORT_COMPLETED = "import_completed"
    EXPORT_GENERATED = "export_generated"
    
    # Login/Security
    LOGIN = "login"
    LOGOUT = "logout"
    PASSWORD_CHANGE = "password_change"


class ActivitySource(enum.Enum):
    """Source of the activity."""
    
    USER = "user"
    SYSTEM = "system"
    INTEGRATION = "integration"
    IMPORT = "import"


class ActivityLog(Base):
    """
    Activity log for tracking employee-related activities.
    
    Provides activity summaries including profile updates, policy changes,
    request submissions, and system interactions.
    """
    
    __tablename__ = "activity_logs"
    
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
    
    # Activity type and source
    activity_type: Mapped[ActivityType] = mapped_column(
        Enum(ActivityType, name="activity_type"),
        nullable=False,
        index=True,
    )
    activity_source: Mapped[ActivitySource] = mapped_column(
        Enum(ActivitySource, name="activity_source"),
        nullable=False,
        default=ActivitySource.USER,
    )
    
    # Activity details
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    
    # Context and metadata
    details: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
    )
    related_entity_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    related_entity_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    
    # Actor information
    actor_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    actor_name: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
    )
    
    # Flags
    is_automated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    is_visible: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    
    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    
    # Request metadata (optional)
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True,
    )
    user_agent: Mapped[Optional[str]] = mapped_column(
        String(512),
        nullable=True,
    )
    
    # Composite indexes for common query patterns
    __table_args__ = (
        Index("idx_activity_employee_timestamp", "employee_id", "created_at"),
        Index("idx_activity_type_timestamp", "activity_type", "created_at"),
        Index("idx_activity_actor_timestamp", "actor_user_id", "created_at"),
    )
    
    def __repr__(self) -> str:
        return (
            f"<ActivityLog("
            f"id={self.id}, "
            f"employee_id={self.employee_id}, "
            f"type={self.activity_type.value}, "
            f"title={self.title}"
            f")>"
        )

