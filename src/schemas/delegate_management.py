"""Pydantic models for delegate management API."""

from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, validator


class DelegateStatusEnum(str, Enum):
    """Status of a delegate assignment."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"
    REVOKED = "revoked"


class DelegateScopeEnum(str, Enum):
    """Scope of delegation."""
    ALL = "all"
    TIME_OFF = "time_off"
    EXPENSE = "expense"
    PROFILE_CHANGES = "profile_changes"


# =============================================================================
# Employee Info Models
# =============================================================================

class EmployeeInfo(BaseModel):
    """Basic employee information."""
    id: int = Field(..., description="Employee ID")
    employee_id: str = Field(..., description="Employee code")
    name: str = Field(..., description="Full name")
    email: Optional[str] = Field(default=None, description="Email address")
    job_title: Optional[str] = Field(default=None, description="Job title")
    department: Optional[str] = Field(default=None, description="Department name")


# =============================================================================
# Request Models
# =============================================================================

class CreateDelegateRequest(BaseModel):
    """Request to create a delegate assignment."""
    delegate_id: int = Field(..., description="Employee ID of the delegate")
    start_date: date = Field(..., description="Start date of delegation")
    end_date: date = Field(..., description="End date of delegation")
    scope: DelegateScopeEnum = Field(
        default=DelegateScopeEnum.ALL,
        description="Scope of delegation",
    )
    reason: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Reason for delegation",
    )
    contact_info: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Contact info during delegation",
    )
    
    # Limitations
    max_approval_days: Optional[int] = Field(
        default=None,
        ge=1,
        description="Maximum days the delegate can approve",
    )
    team_scope_only: bool = Field(
        default=True,
        description="Limit delegation to direct team only",
    )
    
    @validator('end_date')
    def end_date_after_start(cls, v, values):
        if 'start_date' in values and v < values['start_date']:
            raise ValueError('End date must be after start date')
        return v
    
    @validator('start_date')
    def start_date_not_past(cls, v):
        if v < date.today():
            raise ValueError('Start date cannot be in the past')
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "delegate_id": 5,
                "start_date": "2024-01-15",
                "end_date": "2024-01-22",
                "scope": "time_off",
                "reason": "Vacation - please contact delegate for urgent approvals",
                "contact_info": "manager@example.com (email only)",
                "team_scope_only": True,
            }
        }


class RemoveDelegateRequest(BaseModel):
    """Request to remove a delegate assignment."""
    reason: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Reason for removal",
    )
    transfer_pending_to: Optional[int] = Field(
        default=None,
        description="Employee ID to transfer pending requests to",
    )
    notify_affected: bool = Field(
        default=True,
        description="Notify affected employees",
    )


# =============================================================================
# Response Models
# =============================================================================

class ScopeLimitation(BaseModel):
    """Scope limitations for delegation."""
    scope: DelegateScopeEnum = Field(..., description="Delegation scope")
    max_approval_days: Optional[int] = Field(default=None, description="Max days limit")
    team_scope_only: bool = Field(default=True, description="Team scope only")
    description: str = Field(..., description="Human-readable description")


class DelegateAssignment(BaseModel):
    """Complete delegate assignment details."""
    id: int = Field(..., description="Assignment ID")
    
    # Parties
    delegator: EmployeeInfo = Field(..., description="Manager who delegated")
    delegate: EmployeeInfo = Field(..., description="Delegate employee")
    
    # Status
    status: DelegateStatusEnum = Field(..., description="Assignment status")
    is_currently_active: bool = Field(..., description="Whether currently active")
    
    # Dates
    start_date: date = Field(..., description="Start date")
    end_date: date = Field(..., description="End date")
    
    # Scope
    scope_limitations: ScopeLimitation = Field(..., description="Scope limitations")
    
    # Reason and contact
    reason: Optional[str] = Field(default=None, description="Reason for delegation")
    delegator_contact: Optional[str] = Field(default=None, description="Contact info")
    
    # Audit
    created_at: datetime = Field(..., description="Creation timestamp")
    created_by: int = Field(..., description="Created by ID")

    class Config:
        json_encoders = {
            date: lambda v: v.isoformat(),
            datetime: lambda v: v.isoformat(),
        }


class AuditEntry(BaseModel):
    """Audit trail entry."""
    id: int = Field(..., description="Audit entry ID")
    action: str = Field(..., description="Action performed")
    performed_by_name: str = Field(..., description="Actor name")
    performed_at: datetime = Field(..., description="Timestamp")
    details: Optional[str] = Field(default=None, description="Additional details")


class NotificationSent(BaseModel):
    """Notification information."""
    recipient_id: int = Field(..., description="Recipient ID")
    recipient_name: str = Field(..., description="Recipient name")
    notification_type: str = Field(..., description="Type of notification")
    sent_at: datetime = Field(default_factory=datetime.utcnow, description="Sent timestamp")


class CreateDelegateResponse(BaseModel):
    """Response for delegate creation."""
    assignment: DelegateAssignment = Field(..., description="Created assignment")
    audit_entry: AuditEntry = Field(..., description="Audit entry")
    notifications_sent: List[NotificationSent] = Field(
        default_factory=list,
        description="Notifications sent",
    )
    message: str = Field(..., description="Success message")


class ActiveDelegatesResponse(BaseModel):
    """Response for active delegates query."""
    employee_id: int = Field(..., description="Querying employee ID")
    employee_name: str = Field(..., description="Employee name")
    
    # Delegations given (I delegated to others)
    delegations_given: List[DelegateAssignment] = Field(
        default_factory=list,
        description="Delegations assigned to others",
    )
    
    # Delegations received (Others delegated to me)
    delegations_received: List[DelegateAssignment] = Field(
        default_factory=list,
        description="Delegations received from others",
    )
    
    # Summary
    total_active_given: int = Field(default=0, description="Total active delegations given")
    total_active_received: int = Field(default=0, description="Total active delegations received")
    
    # Escalation info
    escalation_contacts: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Escalation contacts for complex scenarios",
    )


class RemoveDelegateResponse(BaseModel):
    """Response for delegate removal."""
    assignment_id: int = Field(..., description="Removed assignment ID")
    new_status: DelegateStatusEnum = Field(..., description="New status")
    
    # Pending request handling
    pending_requests_affected: int = Field(default=0, description="Pending requests affected")
    requests_transferred_to: Optional[EmployeeInfo] = Field(
        default=None,
        description="Employee requests were transferred to",
    )
    
    # Audit
    audit_entry: AuditEntry = Field(..., description="Audit entry")
    
    # Notifications
    notifications_sent: List[NotificationSent] = Field(
        default_factory=list,
        description="Notifications sent",
    )
    
    message: str = Field(..., description="Success message")

    class Config:
        json_encoders = {
            date: lambda v: v.isoformat(),
            datetime: lambda v: v.isoformat(),
        }


class DelegateListResponse(BaseModel):
    """List of delegate assignments."""
    assignments: List[DelegateAssignment] = Field(..., description="Delegate assignments")
    total: int = Field(..., description="Total count")


