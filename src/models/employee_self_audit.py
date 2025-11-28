"""EmployeeSelfAuditLog model for tracking self-service actions."""

import enum
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from src.models.base import Base


class SelfServiceActionType(enum.Enum):
    """Types of self-service actions tracked."""
    
    LOGIN = "login"
    LOGOUT = "logout"
    VIEW_PROFILE = "view_profile"
    EDIT_PROFILE = "edit_profile"
    SUBMIT_REQUEST = "submit_request"
    CANCEL_REQUEST = "cancel_request"
    VIEW_DOCUMENTS = "view_documents"
    UPLOAD_DOCUMENT = "upload_document"
    DELETE_DOCUMENT = "delete_document"
    DOWNLOAD_DOCUMENT = "download_document"
    VIEW_COMPENSATION = "view_compensation"
    VIEW_BENEFITS = "view_benefits"
    UPDATE_PREFERENCES = "update_preferences"
    UPDATE_NOTIFICATIONS = "update_notifications"
    VIEW_AUDIT_LOG = "view_audit_log"
    EXPORT_DATA = "export_data"
    PASSWORD_CHANGE = "password_change"
    MFA_SETUP = "mfa_setup"
    SESSION_EXPIRED = "session_expired"
    FAILED_AUTH = "failed_auth"


class AuditSeverity(enum.Enum):
    """Severity level of the audit event."""
    
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class EmployeeSelfAuditLog(Base):
    """
    Audit log for employee self-service actions.
    
    Provides comprehensive tracking of all self-service activities
    including resource access, IP addresses, and detailed metadata.
    """
    
    __tablename__ = "employee_self_audit_logs"
    
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
    
    # Session tracking
    session_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )
    
    # Action details
    action_type: Mapped[SelfServiceActionType] = mapped_column(
        Enum(SelfServiceActionType, name="self_service_action_type"),
        nullable=False,
        index=True,
    )
    severity: Mapped[AuditSeverity] = mapped_column(
        Enum(AuditSeverity, name="audit_severity"),
        nullable=False,
        default=AuditSeverity.INFO,
    )
    
    # Resource information
    resource_accessed: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Path or identifier of accessed resource",
    )
    resource_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Type of resource (profile, document, etc.)",
    )
    resource_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    
    # Request metadata
    access_ip_address: Mapped[Optional[str]] = mapped_column(
        INET,
        nullable=True,
    )
    access_user_agent: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    request_method: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
        comment="HTTP method (GET, POST, etc.)",
    )
    request_path: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    
    # Action outcome
    action_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="success",
        comment="success, failure, partial",
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    error_code: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    
    # Change tracking
    changes_made: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Details of changes if applicable",
    )
    previous_values: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
    )
    new_values: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
    )
    
    # Additional metadata
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional context-specific metadata",
    )
    
    # Device information
    device_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="desktop, mobile, tablet",
    )
    browser: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    os: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    
    # Geolocation (optional)
    geo_country: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    geo_city: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    
    # Timestamp
    action_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    
    # Duration tracking
    action_duration_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Duration of action in milliseconds",
    )
    
    # Composite indexes
    __table_args__ = (
        Index("ix_self_audit_employee_timestamp", "employee_id", "action_timestamp"),
        Index("ix_self_audit_action_timestamp", "action_type", "action_timestamp"),
        Index("ix_self_audit_session", "session_id", "action_timestamp"),
        Index("ix_self_audit_ip", "access_ip_address"),
    )
    
    def __repr__(self) -> str:
        return (
            f"<EmployeeSelfAuditLog("
            f"id={self.id}, "
            f"employee_id={self.employee_id}, "
            f"action={self.action_type.value}, "
            f"status={self.action_status}"
            f")>"
        )

