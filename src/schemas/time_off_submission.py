"""Pydantic models for time-off request submission API endpoints."""

from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, validator
import uuid


# =============================================================================
# Enums
# =============================================================================

class TimeOffTypeEnum(str, Enum):
    """Types of time-off requests."""
    PTO = "pto"
    SICK_LEAVE = "sick_leave"
    PERSONAL = "personal"
    BEREAVEMENT = "bereavement"
    JURY_DUTY = "jury_duty"
    PARENTAL = "parental"
    UNPAID = "unpaid"


class ValidationSeverity(str, Enum):
    """Severity of validation issues."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class RequestStatusEnum(str, Enum):
    """Status of a time-off request."""
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    CANCELLED = "cancelled"
    WITHDRAWN = "withdrawn"


# =============================================================================
# Request Models
# =============================================================================

class TimeOffSubmissionRequest(BaseModel):
    """Request model for time-off submission."""
    time_off_type: TimeOffTypeEnum = Field(..., description="Type of time-off")
    start_date: date = Field(..., description="Start date of time-off")
    end_date: date = Field(..., description="End date of time-off")
    
    # Partial day options
    is_partial_start_day: bool = Field(default=False, description="Is partial start day")
    start_day_hours: Optional[float] = Field(default=None, ge=0.5, le=8, description="Hours for partial start day")
    is_partial_end_day: bool = Field(default=False, description="Is partial end day")
    end_day_hours: Optional[float] = Field(default=None, ge=0.5, le=8, description="Hours for partial end day")
    
    # Additional info
    reason: Optional[str] = Field(default=None, max_length=1000, description="Reason for request")
    notes: Optional[str] = Field(default=None, max_length=500, description="Additional notes")
    
    # Emergency/urgent flag
    is_urgent: bool = Field(default=False, description="Is urgent request")
    
    # Attachments
    attachment_ids: Optional[List[str]] = Field(default=None, description="Attachment IDs")

    @validator("end_date")
    def end_date_after_start(cls, v, values):
        if "start_date" in values and v < values["start_date"]:
            raise ValueError("end_date must be on or after start_date")
        return v

    @validator("start_day_hours")
    def validate_start_hours(cls, v, values):
        if values.get("is_partial_start_day") and not v:
            raise ValueError("start_day_hours required when is_partial_start_day is true")
        return v

    @validator("end_day_hours")
    def validate_end_hours(cls, v, values):
        if values.get("is_partial_end_day") and not v:
            raise ValueError("end_day_hours required when is_partial_end_day is true")
        return v


# =============================================================================
# Validation Response Models
# =============================================================================

class FieldError(BaseModel):
    """Field-level error information."""
    field: str = Field(..., description="Field name")
    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    severity: ValidationSeverity = Field(..., description="Error severity")


class PolicyViolation(BaseModel):
    """Policy violation information."""
    policy_id: int = Field(..., description="Policy ID")
    policy_name: str = Field(..., description="Policy name")
    violation_code: str = Field(..., description="Violation code")
    violation_type: str = Field(..., description="Violation type")
    severity: ValidationSeverity = Field(..., description="Severity")
    message: str = Field(..., description="Violation message")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Additional details")
    
    # Resolution
    can_override: bool = Field(default=False, description="Can be overridden")
    override_requires_approval: bool = Field(default=False, description="Override requires approval")


class EligibilityInfo(BaseModel):
    """Employee eligibility information."""
    is_eligible: bool = Field(..., description="Is eligible for time-off type")
    eligibility_date: Optional[date] = Field(default=None, description="Date eligible from")
    eligibility_message: Optional[str] = Field(default=None, description="Eligibility message")
    restrictions: List[str] = Field(default_factory=list, description="Restrictions")


class BalanceProjection(BaseModel):
    """Balance projection information."""
    policy_id: int = Field(..., description="Policy ID")
    policy_name: str = Field(..., description="Policy name")
    
    # Current balance
    current_balance: float = Field(..., description="Current available balance")
    
    # Request impact
    days_requested: float = Field(..., description="Days being requested")
    
    # Projected balance
    projected_balance: float = Field(..., description="Balance after request")
    projected_balance_date: date = Field(..., description="Projection date")
    
    # Accruals before request
    accruals_before_request: float = Field(default=0, description="Accruals before start date")
    
    # Status
    will_go_negative: bool = Field(default=False, description="Will result in negative balance")
    negative_amount: float = Field(default=0, description="Negative amount if applicable")


class BlackoutPeriodInfo(BaseModel):
    """Blackout period information."""
    blackout_id: int = Field(..., description="Blackout period ID")
    name: str = Field(..., description="Blackout name")
    start_date: date = Field(..., description="Blackout start date")
    end_date: date = Field(..., description="Blackout end date")
    overlap_days: int = Field(..., description="Days overlapping with request")
    can_request: bool = Field(default=False, description="Can still request during blackout")
    approval_level: Optional[str] = Field(default=None, description="Required approval level")


class NoticeRequirement(BaseModel):
    """Notice requirement information."""
    required_notice_days: int = Field(..., description="Required notice days")
    actual_notice_days: int = Field(..., description="Actual notice days provided")
    is_satisfied: bool = Field(..., description="Is requirement satisfied")
    waiver_possible: bool = Field(default=False, description="Waiver possible")
    waiver_authority: Optional[str] = Field(default=None, description="Authority to waive")


class ValidationResult(BaseModel):
    """Complete validation result."""
    is_valid: bool = Field(..., description="Is the request valid")
    can_submit: bool = Field(..., description="Can the request be submitted")
    
    # Correlation ID for tracking
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Correlation ID")
    
    # Eligibility
    eligibility: EligibilityInfo = Field(..., description="Eligibility information")
    
    # Balance projections
    balance_projections: List[BalanceProjection] = Field(
        default_factory=list,
        description="Balance projections",
    )
    
    # Policy violations
    policy_violations: List[PolicyViolation] = Field(
        default_factory=list,
        description="Policy violations",
    )
    
    # Field errors
    field_errors: List[FieldError] = Field(
        default_factory=list,
        description="Field-level errors",
    )
    
    # Blackout periods
    blackout_conflicts: List[BlackoutPeriodInfo] = Field(
        default_factory=list,
        description="Blackout period conflicts",
    )
    
    # Notice requirements
    notice_requirement: Optional[NoticeRequirement] = Field(
        default=None,
        description="Notice requirement check",
    )
    
    # Counts
    error_count: int = Field(default=0, description="Total error count")
    warning_count: int = Field(default=0, description="Total warning count")
    info_count: int = Field(default=0, description="Total info count")
    
    # Summary
    validation_summary: str = Field(..., description="Validation summary message")
    
    # Metadata
    validated_at: datetime = Field(default_factory=datetime.utcnow, description="Validation timestamp")

    class Config:
        json_encoders = {
            date: lambda v: v.isoformat(),
            datetime: lambda v: v.isoformat(),
        }


# =============================================================================
# Submission Response Models
# =============================================================================

class ApprovalWorkflowInfo(BaseModel):
    """Approval workflow information."""
    workflow_id: int = Field(..., description="Workflow ID")
    current_step: int = Field(..., description="Current approval step")
    total_steps: int = Field(..., description="Total approval steps")
    current_approver_id: Optional[int] = Field(default=None, description="Current approver ID")
    current_approver_name: Optional[str] = Field(default=None, description="Current approver name")
    estimated_completion: Optional[datetime] = Field(default=None, description="Estimated completion time")


class AuditInfo(BaseModel):
    """Audit trail information."""
    audit_id: str = Field(..., description="Audit ID")
    action: str = Field(..., description="Action taken")
    performed_by: int = Field(..., description="Performed by employee ID")
    performed_at: datetime = Field(..., description="Performed at timestamp")
    changes: Dict[str, Any] = Field(default_factory=dict, description="Change details")


class SubmittedRequest(BaseModel):
    """Submitted time-off request information."""
    request_id: int = Field(..., description="Request ID")
    employee_id: int = Field(..., description="Employee ID")
    employee_name: str = Field(..., description="Employee name")
    
    # Request details
    time_off_type: TimeOffTypeEnum = Field(..., description="Type of time-off")
    start_date: date = Field(..., description="Start date")
    end_date: date = Field(..., description="End date")
    total_days: float = Field(..., description="Total days requested")
    total_hours: float = Field(..., description="Total hours requested")
    
    # Status
    status: RequestStatusEnum = Field(..., description="Request status")
    
    # Reason
    reason: Optional[str] = Field(default=None, description="Reason")
    notes: Optional[str] = Field(default=None, description="Notes")
    
    # Timestamps
    submitted_at: datetime = Field(..., description="Submission timestamp")
    
    # Flags
    is_urgent: bool = Field(default=False, description="Is urgent")
    requires_documentation: bool = Field(default=False, description="Requires documentation")


class TimeOffSubmissionResponse(BaseModel):
    """Response model for successful time-off submission."""
    # Success indicator
    success: bool = Field(..., description="Was submission successful")
    
    # Correlation ID
    correlation_id: str = Field(..., description="Correlation ID for tracking")
    
    # Submitted request
    request: SubmittedRequest = Field(..., description="Submitted request details")
    
    # Balance update
    balance_update: BalanceProjection = Field(..., description="Updated balance information")
    
    # Approval workflow
    approval_workflow: ApprovalWorkflowInfo = Field(..., description="Approval workflow info")
    
    # Audit
    audit: AuditInfo = Field(..., description="Audit trail entry")
    
    # Next steps
    next_steps: List[str] = Field(default_factory=list, description="Recommended next steps")
    
    # Notifications
    notifications_sent: List[str] = Field(default_factory=list, description="Notifications sent")
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")

    class Config:
        json_encoders = {
            date: lambda v: v.isoformat(),
            datetime: lambda v: v.isoformat(),
        }


# =============================================================================
# Error Response Models
# =============================================================================

class SubmissionErrorResponse(BaseModel):
    """Error response for failed submissions."""
    success: bool = Field(default=False, description="Was submission successful")
    
    # Correlation ID
    correlation_id: str = Field(..., description="Correlation ID for tracking")
    
    # Error information
    error_code: str = Field(..., description="Error code")
    error_message: str = Field(..., description="Error message")
    
    # Validation result (if validation failed)
    validation_result: Optional[ValidationResult] = Field(
        default=None,
        description="Validation result if validation failed",
    )
    
    # Field errors (quick access)
    field_errors: List[FieldError] = Field(
        default_factory=list,
        description="Field-level errors",
    )
    
    # Metadata
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")

    class Config:
        json_encoders = {
            date: lambda v: v.isoformat(),
            datetime: lambda v: v.isoformat(),
        }
