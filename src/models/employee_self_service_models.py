"""SQLModel classes for employee self-service data models.

These models provide object-relational mapping with type-safe operations
and seamless integration with FastAPI.
"""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import Field as PydanticField
from sqlmodel import Column, Field, Relationship, SQLModel
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import DATERANGE, INET, JSONB, UUID as PGUUID


# =============================================================================
# Enums for EmployeeSelfService
# =============================================================================

class ProfileVisibilityLevel(str, Enum):
    """Visibility levels for employee profile information."""
    PRIVATE = "private"
    TEAM = "team"
    DEPARTMENT = "department"
    ORGANIZATION = "organization"
    PUBLIC = "public"


class NotificationPreference(str, Enum):
    """Notification delivery preferences."""
    EMAIL = "email"
    IN_APP = "in_app"
    BOTH = "both"
    NONE = "none"


# =============================================================================
# Enums for EmployeeUpdateRequest
# =============================================================================

class RequestType(str, Enum):
    """Types of update requests."""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    CORRECTION = "correction"


class FieldCategoryType(str, Enum):
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


class RequestStatus(str, Enum):
    """Status of the update request."""
    DRAFT = "draft"
    PENDING = "pending"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    EXPIRED = "expired"


class ApprovalStatus(str, Enum):
    """Approval status values."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"


class NotificationStatus(str, Enum):
    """Notification status values."""
    NOT_SENT = "not_sent"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"


class PriorityLevel(str, Enum):
    """Priority level values."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


# =============================================================================
# Enums for EmployeeSelfAuditLog
# =============================================================================

class SelfServiceActionType(str, Enum):
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


class AuditSeverity(str, Enum):
    """Severity level of audit events."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


# =============================================================================
# Enums for EmployeeFieldPermission
# =============================================================================

class FieldCategory(str, Enum):
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


class VisibilityLevel(str, Enum):
    """Visibility level for field access."""
    HIDDEN = "hidden"
    READ_ONLY = "read_only"
    READ_WRITE = "read_write"
    ADMIN_ONLY = "admin_only"
    RESTRICTED = "restricted"


class EditPermissionLevel(str, Enum):
    """Permission level for editing fields."""
    NO_EDIT = "no_edit"
    SELF_EDIT = "self_edit"
    MANAGER_EDIT = "manager_edit"
    HR_EDIT = "hr_edit"
    ADMIN_EDIT = "admin_edit"


class ViewPermissionLevel(str, Enum):
    """Permission level for viewing fields."""
    NO_VIEW = "no_view"
    PERSONAL_ONLY = "personal_only"
    SUPERVISED = "supervised"
    PUBLIC = "public"
    RESTRICTED = "restricted"


# =============================================================================
# SQLModel: EmployeeSelfService
# =============================================================================

class EmployeeSelfServiceBase(SQLModel):
    """Base model for EmployeeSelfService with shared fields."""
    
    # Profile visibility settings
    profile_visibility_level: ProfileVisibilityLevel = Field(
        default=ProfileVisibilityLevel.TEAM,
        sa_column=Column(SAEnum(ProfileVisibilityLevel, name="profile_visibility_level_sm")),
    )
    show_email: bool = Field(default=True)
    show_phone: bool = Field(default=False)
    show_location: bool = Field(default=True)
    show_department: bool = Field(default=True)
    show_manager: bool = Field(default=True)
    show_hire_date: bool = Field(default=False)
    
    # Dashboard preferences
    dashboard_preference_json: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSONB),
    )
    default_landing_page: str = Field(default="dashboard", max_length=100)
    items_per_page: int = Field(default=25, ge=1, le=100)
    
    # Notification preferences
    notification_preference: NotificationPreference = Field(
        default=NotificationPreference.BOTH,
        sa_column=Column(SAEnum(NotificationPreference, name="notification_preference_sm")),
    )
    email_notifications_enabled: bool = Field(default=True)
    push_notifications_enabled: bool = Field(default=True)
    notify_on_request_status: bool = Field(default=True)
    notify_on_approval_needed: bool = Field(default=True)
    notification_digest_frequency: str = Field(default="immediate", max_length=20)
    
    # Self-service permissions
    can_edit_personal_info: bool = Field(default=True)
    can_edit_contact_info: bool = Field(default=True)
    can_edit_emergency_contacts: bool = Field(default=True)
    can_view_compensation: bool = Field(default=True)
    can_view_documents: bool = Field(default=True)
    can_upload_documents: bool = Field(default=True)
    
    # Audit and security
    audit_trail_enabled: bool = Field(default=True)
    audit_retention_days: int = Field(default=365, ge=30)
    require_mfa_for_sensitive: bool = Field(default=False)
    session_timeout_minutes: int = Field(default=30, ge=5, le=480)
    
    # Localization
    preferred_language: str = Field(default="en", max_length=10)
    preferred_timezone: str = Field(default="UTC", max_length=50)
    date_format: str = Field(default="YYYY-MM-DD", max_length=20)
    time_format: str = Field(default="24h", max_length=10)


class EmployeeSelfServiceModel(EmployeeSelfServiceBase, table=True):
    """SQLModel table for employee self-service configurations."""
    
    __tablename__ = "employee_self_services_sm"
    
    id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(PGUUID(as_uuid=True), primary_key=True),
    )
    employee_id: int = Field(
        foreign_key="employee.id",
        index=True,
        unique=True,
    )
    
    # Timestamps
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True)),
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True)),
    )
    last_accessed_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True)),
    )


# =============================================================================
# SQLModel: EmployeeUpdateRequest
# =============================================================================

class EmployeeUpdateRequestBase(SQLModel):
    """Base model for EmployeeUpdateRequest with shared fields."""
    
    request_session_id: str = Field(max_length=64, index=True)
    request_reference: str = Field(max_length=50, index=True)
    
    request_type: RequestType = Field(
        default=RequestType.UPDATE,
        sa_column=Column(SAEnum(RequestType, name="request_type_sm")),
    )
    field_category_type: FieldCategoryType = Field(
        sa_column=Column(SAEnum(FieldCategoryType, name="field_category_type_sm")),
    )
    
    # JSONB fields
    update_fields_json: Dict[str, Any] = Field(sa_column=Column(JSONB))
    current_values_json: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSONB),
    )
    proposed_values_json: Dict[str, Any] = Field(sa_column=Column(JSONB))
    
    reason_for_change: Optional[str] = Field(default=None)
    supporting_document_ids: Optional[List[str]] = Field(
        default=None,
        sa_column=Column(JSONB),
    )
    
    # Status
    status: RequestStatus = Field(
        default=RequestStatus.PENDING,
        sa_column=Column(SAEnum(RequestStatus, name="request_status_sm")),
    )
    approval_status: ApprovalStatus = Field(
        default=ApprovalStatus.PENDING,
        sa_column=Column(SAEnum(ApprovalStatus, name="approval_status_sm")),
    )
    notification_status: NotificationStatus = Field(
        default=NotificationStatus.NOT_SENT,
        sa_column=Column(SAEnum(NotificationStatus, name="notification_status_sm")),
    )
    priority_level: PriorityLevel = Field(
        default=PriorityLevel.NORMAL,
        sa_column=Column(SAEnum(PriorityLevel, name="priority_level_sm")),
    )
    
    requires_approval: bool = Field(default=True)
    auto_approved: bool = Field(default=False)
    
    # Approval workflow
    approval_reference_id: Optional[str] = Field(default=None, max_length=64, index=True)
    approver_id: Optional[int] = Field(default=None, foreign_key="employee.id")
    approval_level: int = Field(default=1, ge=1)
    approval_notes: Optional[str] = Field(default=None)
    rejection_reason: Optional[str] = Field(default=None)
    
    is_escalated: bool = Field(default=False)
    escalation_reason: Optional[str] = Field(default=None)


class EmployeeUpdateRequestModel(EmployeeUpdateRequestBase, table=True):
    """SQLModel table for employee update requests."""
    
    __tablename__ = "employee_update_requests_sm"
    
    id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(PGUUID(as_uuid=True), primary_key=True),
    )
    employee_id: int = Field(foreign_key="employee.id", index=True)
    
    # Timestamps
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True)),
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True)),
    )
    submitted_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True)),
    )
    reviewed_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True)),
    )
    completed_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True)),
    )
    expires_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True)),
    )


# =============================================================================
# SQLModel: EmployeeSelfAuditLog
# =============================================================================

class EmployeeSelfAuditLogBase(SQLModel):
    """Base model for EmployeeSelfAuditLog with shared fields."""
    
    session_id: Optional[str] = Field(default=None, max_length=64, index=True)
    
    action_type: SelfServiceActionType = Field(
        sa_column=Column(SAEnum(SelfServiceActionType, name="self_service_action_type_sm")),
    )
    severity: AuditSeverity = Field(
        default=AuditSeverity.INFO,
        sa_column=Column(SAEnum(AuditSeverity, name="audit_severity_sm")),
    )
    
    # Resource information
    resource_accessed: Optional[str] = Field(default=None)
    resource_type: Optional[str] = Field(default=None, max_length=50)
    resource_id: Optional[str] = Field(default=None, max_length=100)
    
    # Request metadata
    access_ip_address: Optional[str] = Field(
        default=None,
        sa_column=Column(INET),
    )
    access_user_agent: Optional[str] = Field(default=None)
    request_method: Optional[str] = Field(default=None, max_length=10)
    request_path: Optional[str] = Field(default=None, max_length=500)
    
    # Action outcome
    action_status: str = Field(default="success", max_length=20)
    error_message: Optional[str] = Field(default=None)
    error_code: Optional[str] = Field(default=None, max_length=50)
    
    # Change tracking
    changes_made: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSONB),
    )
    previous_values: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSONB),
    )
    new_values: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSONB),
    )
    metadata_json: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSONB),
    )
    
    # Device information
    device_type: Optional[str] = Field(default=None, max_length=50)
    browser: Optional[str] = Field(default=None, max_length=100)
    os: Optional[str] = Field(default=None, max_length=100)
    
    # Geolocation
    geo_country: Optional[str] = Field(default=None, max_length=100)
    geo_city: Optional[str] = Field(default=None, max_length=100)
    geo_latitude: Optional[float] = Field(default=None)
    geo_longitude: Optional[float] = Field(default=None)
    
    action_duration_ms: Optional[int] = Field(default=None, ge=0)


class EmployeeSelfAuditLogModel(EmployeeSelfAuditLogBase, table=True):
    """SQLModel table for employee self-service audit logs."""
    
    __tablename__ = "employee_self_audit_logs_sm"
    
    id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(PGUUID(as_uuid=True), primary_key=True),
    )
    employee_id: int = Field(foreign_key="employee.id", index=True)
    
    action_timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True)),
        index=True,
    )


# =============================================================================
# SQLModel: EmployeeFieldPermission
# =============================================================================

class EmployeeFieldPermissionBase(SQLModel):
    """Base model for EmployeeFieldPermission with shared fields."""
    
    profile_field_id: Optional[UUID] = Field(
        default=None,
        sa_column=Column(PGUUID(as_uuid=True)),
    )
    
    field_name: str = Field(max_length=100, index=True)
    field_category: FieldCategory = Field(
        sa_column=Column(SAEnum(FieldCategory, name="field_category_sm")),
    )
    
    # Permission levels
    visibility_level: VisibilityLevel = Field(
        default=VisibilityLevel.READ_ONLY,
        sa_column=Column(SAEnum(VisibilityLevel, name="visibility_level_sm")),
    )
    edit_permission_level: EditPermissionLevel = Field(
        default=EditPermissionLevel.NO_EDIT,
        sa_column=Column(SAEnum(EditPermissionLevel, name="edit_permission_level_sm")),
    )
    view_permission_level: ViewPermissionLevel = Field(
        default=ViewPermissionLevel.PERSONAL_ONLY,
        sa_column=Column(SAEnum(ViewPermissionLevel, name="view_permission_level_sm")),
    )
    
    # Approval workflow
    approval_chain_json: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSONB),
    )
    requires_approval: bool = Field(default=False)
    approval_levels: int = Field(default=1, ge=1)
    
    # Time-based permissions
    effective_date: date = Field(default_factory=date.today)
    expire_date: Optional[date] = Field(default=None)
    validity_range: Optional[Any] = Field(
        default=None,
        sa_column=Column(DATERANGE),
    )
    
    # Permission review tracking
    permission_review_cycle_days: int = Field(default=365, ge=30)
    last_permission_review: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True)),
    )
    next_review_date: Optional[date] = Field(default=None)
    reviewed_by_id: Optional[int] = Field(default=None, foreign_key="employee.id")
    
    # Audit and tracking
    audit_required: bool = Field(default=False)
    exception_count: int = Field(default=0, ge=0)
    exception_notes: Optional[str] = Field(default=None)
    
    # Status
    is_active: bool = Field(default=True)
    is_inherited: bool = Field(default=False)
    inheritance_source: Optional[str] = Field(default=None, max_length=100)


class EmployeeFieldPermissionModel(EmployeeFieldPermissionBase, table=True):
    """SQLModel table for employee field permissions."""
    
    __tablename__ = "employee_field_permissions_sm"
    __table_args__ = (
        UniqueConstraint("employee_id", "field_name", "field_category", name="uq_employee_field_permission_sm"),
        CheckConstraint("permission_review_cycle_days >= 30", name="ck_field_permission_review_cycle_min_sm"),
        CheckConstraint("exception_count >= 0", name="ck_field_permission_exception_count_min_sm"),
    )
    
    id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(PGUUID(as_uuid=True), primary_key=True),
    )
    employee_id: int = Field(foreign_key="employee.id", index=True)
    
    # Timestamps
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True)),
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True)),
    )
    granted_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True)),
    )
    granted_by_id: Optional[int] = Field(default=None, foreign_key="employee.id")


# =============================================================================
# Pydantic Read Models (for API responses)
# =============================================================================

class EmployeeSelfServiceRead(EmployeeSelfServiceBase):
    """Read model for EmployeeSelfService API responses."""
    id: UUID
    employee_id: int
    created_at: datetime
    updated_at: datetime
    last_accessed_at: Optional[datetime]


class EmployeeUpdateRequestRead(EmployeeUpdateRequestBase):
    """Read model for EmployeeUpdateRequest API responses."""
    id: UUID
    employee_id: int
    created_at: datetime
    updated_at: datetime
    submitted_at: Optional[datetime]
    reviewed_at: Optional[datetime]
    completed_at: Optional[datetime]


class EmployeeSelfAuditLogRead(EmployeeSelfAuditLogBase):
    """Read model for EmployeeSelfAuditLog API responses."""
    id: UUID
    employee_id: int
    action_timestamp: datetime


class EmployeeFieldPermissionRead(EmployeeFieldPermissionBase):
    """Read model for EmployeeFieldPermission API responses."""
    id: UUID
    employee_id: int
    created_at: datetime
    updated_at: datetime
    granted_at: Optional[datetime]

