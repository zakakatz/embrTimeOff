"""Pydantic models for approval management API."""

from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ApprovalStatusEnum(str, Enum):
    """Approval request status."""
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    ESCALATED = "escalated"
    CANCELLED = "cancelled"


class ConflictSeverityEnum(str, Enum):
    """Severity of team conflicts."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# =============================================================================
# Contextual Information Models
# =============================================================================

class TeamConflict(BaseModel):
    """Information about team scheduling conflicts."""
    employee_id: int = Field(..., description="Employee with conflicting time-off")
    employee_name: str = Field(..., description="Employee name")
    conflict_dates: List[date] = Field(..., description="Dates that overlap")
    conflict_type: str = Field(default="overlap", description="Type of conflict")
    severity: ConflictSeverityEnum = Field(default=ConflictSeverityEnum.MEDIUM, description="Severity level")


class CoverageWarning(BaseModel):
    """Warning about team coverage issues."""
    warning_type: str = Field(..., description="Type of warning")
    message: str = Field(..., description="Warning message")
    affected_dates: List[date] = Field(..., description="Dates affected")
    minimum_coverage_required: int = Field(default=1, description="Minimum staff required")
    current_coverage: int = Field(..., description="Current staff scheduled")


class PolicyConsideration(BaseModel):
    """Policy-related information for approval decision."""
    policy_name: str = Field(..., description="Name of the policy")
    rule_description: str = Field(..., description="Description of the rule")
    compliance_status: str = Field(..., description="compliant, warning, violation")
    details: Optional[str] = Field(default=None, description="Additional details")


class BalanceInfo(BaseModel):
    """Employee balance information."""
    balance_type: str = Field(..., description="Type of time-off")
    available: float = Field(..., description="Available balance")
    requested: float = Field(..., description="Amount requested")
    after_approval: float = Field(..., description="Balance after approval")
    year: int = Field(..., description="Balance year")


class EmployeeInfo(BaseModel):
    """Basic employee information."""
    id: int = Field(..., description="Employee ID")
    employee_id: str = Field(..., description="Employee code")
    name: str = Field(..., description="Full name")
    email: str = Field(..., description="Email address")
    department: Optional[str] = Field(default=None, description="Department name")
    job_title: Optional[str] = Field(default=None, description="Job title")


# =============================================================================
# Request Models
# =============================================================================

class ApproveRequest(BaseModel):
    """Request to approve a time-off request."""
    comments: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Approver comments",
    )
    conditions: Optional[List[str]] = Field(
        default=None,
        description="Conditions attached to approval",
    )
    acknowledge_conflicts: bool = Field(
        default=False,
        description="Acknowledge awareness of conflicts",
    )
    acknowledge_coverage_warnings: bool = Field(
        default=False,
        description="Acknowledge awareness of coverage issues",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "comments": "Approved. Enjoy your time off!",
                "conditions": ["Please ensure handoff to John before leaving"],
                "acknowledge_conflicts": True,
            }
        }


class DenyRequest(BaseModel):
    """Request to deny a time-off request."""
    rationale: str = Field(
        ...,
        min_length=10,
        max_length=1000,
        description="Required rationale for denial",
    )
    suggest_alternative_dates: bool = Field(
        default=False,
        description="Whether to suggest alternative dates",
    )
    alternative_start_date: Optional[date] = Field(
        default=None,
        description="Suggested alternative start date",
    )
    alternative_end_date: Optional[date] = Field(
        default=None,
        description="Suggested alternative end date",
    )
    policy_reference: Optional[str] = Field(
        default=None,
        description="Reference to policy justifying denial",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "rationale": "Unable to approve due to critical project deadline during requested dates. Team coverage would fall below minimum requirements.",
                "suggest_alternative_dates": True,
                "alternative_start_date": "2024-02-01",
                "alternative_end_date": "2024-02-05",
            }
        }


# =============================================================================
# Response Models
# =============================================================================

class PendingApprovalRequest(BaseModel):
    """A pending approval request with contextual information."""
    request_id: int = Field(..., description="Request ID")
    employee: EmployeeInfo = Field(..., description="Requesting employee")
    request_type: str = Field(..., description="Type of time-off")
    start_date: date = Field(..., description="Start date")
    end_date: date = Field(..., description="End date")
    total_days: float = Field(..., description="Total days requested")
    reason: Optional[str] = Field(default=None, description="Employee's reason")
    
    # Contextual information
    balance_info: BalanceInfo = Field(..., description="Balance information")
    team_conflicts: List[TeamConflict] = Field(
        default_factory=list,
        description="Team scheduling conflicts",
    )
    coverage_warnings: List[CoverageWarning] = Field(
        default_factory=list,
        description="Team coverage warnings",
    )
    policy_considerations: List[PolicyConsideration] = Field(
        default_factory=list,
        description="Policy considerations",
    )
    
    # Request metadata
    submitted_at: datetime = Field(..., description="Submission timestamp")
    days_pending: int = Field(..., description="Days since submission")
    priority: str = Field(default="normal", description="Request priority")
    requires_escalation: bool = Field(default=False, description="Whether escalation is needed")

    class Config:
        json_encoders = {
            date: lambda v: v.isoformat(),
            datetime: lambda v: v.isoformat(),
        }


class PendingApprovalsResponse(BaseModel):
    """Response containing pending approval requests."""
    manager_id: int = Field(..., description="Manager ID")
    manager_name: str = Field(..., description="Manager name")
    total_pending: int = Field(..., description="Total pending requests")
    pending_requests: List[PendingApprovalRequest] = Field(..., description="Pending requests")
    summary: Dict[str, Any] = Field(default_factory=dict, description="Summary statistics")


class AuditTrailEntry(BaseModel):
    """Audit trail entry for approval decisions."""
    id: str = Field(..., description="Audit entry ID")
    action: str = Field(..., description="Action taken")
    performed_by_id: int = Field(..., description="Actor ID")
    performed_by_name: str = Field(..., description="Actor name")
    performed_at: datetime = Field(..., description="Timestamp")
    decision_rationale: Optional[str] = Field(default=None, description="Rationale")
    contextual_factors: Optional[Dict[str, Any]] = Field(default=None, description="Context")
    previous_status: Optional[str] = Field(default=None, description="Previous status")
    new_status: str = Field(..., description="New status")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class NotificationSent(BaseModel):
    """Information about notification sent."""
    recipient_id: int = Field(..., description="Recipient ID")
    recipient_name: str = Field(..., description="Recipient name")
    recipient_email: str = Field(..., description="Recipient email")
    notification_type: str = Field(..., description="Type of notification")
    channel: str = Field(default="email", description="Notification channel")
    sent_at: datetime = Field(..., description="Sent timestamp")


class ApprovalResultResponse(BaseModel):
    """Response for approval action."""
    request_id: int = Field(..., description="Request ID")
    status: ApprovalStatusEnum = Field(..., description="New status")
    decision: str = Field(..., description="Decision made")
    
    # Decision maker
    approved_by_id: int = Field(..., description="Approver ID")
    approved_by_name: str = Field(..., description="Approver name")
    
    # Decision details
    comments: Optional[str] = Field(default=None, description="Approver comments")
    conditions: Optional[List[str]] = Field(default=None, description="Conditions")
    
    # Balance update
    balance_impact: Optional[Dict[str, float]] = Field(
        default=None,
        description="Impact on employee balance",
    )
    
    # Audit
    audit_entry: AuditTrailEntry = Field(..., description="Audit trail entry")
    
    # Notifications
    notifications_sent: List[NotificationSent] = Field(
        default_factory=list,
        description="Notifications sent",
    )
    
    # Timestamps
    processed_at: datetime = Field(..., description="Processing timestamp")
    
    message: str = Field(..., description="Result message")


class DenialResultResponse(BaseModel):
    """Response for denial action."""
    request_id: int = Field(..., description="Request ID")
    status: ApprovalStatusEnum = Field(default=ApprovalStatusEnum.DENIED, description="New status")
    
    # Decision maker
    denied_by_id: int = Field(..., description="Denier ID")
    denied_by_name: str = Field(..., description="Denier name")
    
    # Denial details
    rationale: str = Field(..., description="Denial rationale")
    policy_reference: Optional[str] = Field(default=None, description="Policy reference")
    
    # Alternative suggestions
    alternative_suggested: bool = Field(default=False, description="Whether alternative suggested")
    alternative_start_date: Optional[date] = Field(default=None, description="Alternative start")
    alternative_end_date: Optional[date] = Field(default=None, description="Alternative end")
    
    # Audit
    audit_entry: AuditTrailEntry = Field(..., description="Audit trail entry")
    
    # Notifications
    notifications_sent: List[NotificationSent] = Field(
        default_factory=list,
        description="Notifications sent",
    )
    
    # Timestamps
    processed_at: datetime = Field(..., description="Processing timestamp")
    
    message: str = Field(..., description="Result message")

    class Config:
        json_encoders = {
            date: lambda v: v.isoformat(),
            datetime: lambda v: v.isoformat(),
        }


class ApprovalErrorResponse(BaseModel):
    """Error response for approval operations."""
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Error details")

