"""Pydantic models for employee audit trail and activity endpoints."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# =============================================================================
# Audit Trail Schemas
# =============================================================================

class ChangeType(str, Enum):
    """Types of changes tracked in audit trail."""
    
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


class AuditTrailEntry(BaseModel):
    """A single audit trail entry representing a field-level change."""
    
    id: UUID = Field(..., description="Unique identifier for the audit entry")
    employee_id: int = Field(..., description="ID of the employee whose profile was changed")
    changed_field: str = Field(..., description="Name of the field that was changed")
    previous_value: Optional[str] = Field(None, description="Value before the change (JSON string)")
    new_value: Optional[str] = Field(None, description="Value after the change (JSON string)")
    changed_by_user_id: UUID = Field(..., description="ID of the user who made the change")
    change_timestamp: datetime = Field(..., description="When the change occurred")
    change_type: ChangeType = Field(..., description="Type of change (CREATE, UPDATE, DELETE)")
    change_reason: Optional[str] = Field(None, description="Reason for the change if provided")
    ip_address: Optional[str] = Field(None, description="IP address of the actor")
    user_agent: Optional[str] = Field(None, description="User agent of the actor")
    
    # Computed/denormalized fields for display
    changed_by_name: Optional[str] = Field(None, description="Name of the user who made the change")
    field_display_name: Optional[str] = Field(None, description="Human-readable field name")
    is_automated: bool = Field(default=False, description="Whether this was an automated change")
    
    class Config:
        from_attributes = True


class AuditTrailResponse(BaseModel):
    """Response for audit trail endpoint."""
    
    employee_id: int = Field(..., description="ID of the employee")
    total_entries: int = Field(..., description="Total number of audit entries")
    entries: List[AuditTrailEntry] = Field(
        default_factory=list,
        description="List of audit trail entries"
    )
    page: int = Field(default=1, description="Current page number")
    page_size: int = Field(default=50, description="Number of entries per page")
    has_more: bool = Field(default=False, description="Whether there are more entries")


class AuditTrailSummary(BaseModel):
    """Summary of audit trail for quick overview."""
    
    employee_id: int
    total_changes: int
    first_change: Optional[datetime]
    last_change: Optional[datetime]
    change_counts_by_type: Dict[str, int]
    most_changed_fields: List[Dict[str, Any]]
    actors_count: int


# =============================================================================
# Activity Log Schemas
# =============================================================================

class ActivityType(str, Enum):
    """Types of activities."""
    
    PROFILE_VIEW = "profile_view"
    PROFILE_UPDATE = "profile_update"
    PROFILE_CREATE = "profile_create"
    STATUS_CHANGE = "status_change"
    DEPARTMENT_CHANGE = "department_change"
    ROLE_CHANGE = "role_change"
    MANAGER_CHANGE = "manager_change"
    REQUEST_SUBMITTED = "request_submitted"
    REQUEST_APPROVED = "request_approved"
    REQUEST_REJECTED = "request_rejected"
    SYSTEM_UPDATE = "system_update"
    IMPORT_COMPLETED = "import_completed"
    EXPORT_GENERATED = "export_generated"
    LOGIN = "login"
    LOGOUT = "logout"
    PASSWORD_CHANGE = "password_change"


class ActivitySource(str, Enum):
    """Source of the activity."""
    
    USER = "user"
    SYSTEM = "system"
    INTEGRATION = "integration"
    IMPORT = "import"


class ActivityEntry(BaseModel):
    """A single activity log entry."""
    
    id: UUID = Field(..., description="Unique identifier for the activity")
    employee_id: int = Field(..., description="ID of the employee this activity relates to")
    activity_type: ActivityType = Field(..., description="Type of activity")
    activity_source: ActivitySource = Field(..., description="Source of the activity")
    title: str = Field(..., description="Short title describing the activity")
    description: Optional[str] = Field(None, description="Detailed description")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional context")
    related_entity_type: Optional[str] = Field(None, description="Type of related entity")
    related_entity_id: Optional[str] = Field(None, description="ID of related entity")
    actor_user_id: Optional[UUID] = Field(None, description="User who performed the activity")
    actor_name: Optional[str] = Field(None, description="Name of the actor")
    is_automated: bool = Field(default=False, description="Whether this was automated")
    created_at: datetime = Field(..., description="When the activity occurred")
    
    class Config:
        from_attributes = True


class ActivityResponse(BaseModel):
    """Response for activity endpoint."""
    
    employee_id: int = Field(..., description="ID of the employee")
    total_activities: int = Field(..., description="Total number of activities")
    activities: List[ActivityEntry] = Field(
        default_factory=list,
        description="List of activity entries"
    )
    page: int = Field(default=1, description="Current page number")
    page_size: int = Field(default=50, description="Number of entries per page")
    has_more: bool = Field(default=False, description="Whether there are more entries")


class ActivityFilters(BaseModel):
    """Filters for activity queries."""
    
    activity_types: Optional[List[ActivityType]] = Field(
        None,
        description="Filter by activity types"
    )
    date_from: Optional[datetime] = Field(
        None,
        description="Start date for date range filter"
    )
    date_to: Optional[datetime] = Field(
        None,
        description="End date for date range filter"
    )
    actor_user_id: Optional[UUID] = Field(
        None,
        description="Filter by actor"
    )
    include_automated: bool = Field(
        default=True,
        description="Include automated activities"
    )

