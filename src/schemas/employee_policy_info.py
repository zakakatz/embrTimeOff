"""Pydantic schemas for employee time-off policy information API."""

from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PolicyTypeDisplay(str, Enum):
    """Display-friendly policy types."""
    VACATION = "vacation"
    SICK = "sick"
    PERSONAL = "personal"
    BEREAVEMENT = "bereavement"
    PARENTAL = "parental"
    JURY_DUTY = "jury_duty"
    FLOATING_HOLIDAY = "floating_holiday"
    UNPAID = "unpaid"


class AccrualMethodDisplay(str, Enum):
    """Display-friendly accrual methods."""
    ANNUAL_LUMP_SUM = "annual_lump_sum"
    MONTHLY_ACCRUAL = "monthly_accrual"
    PAY_PERIOD_ACCRUAL = "pay_period_accrual"
    HOURS_WORKED = "hours_worked"
    NONE = "none"


# =============================================================================
# Employee-Facing Policy Display Models
# =============================================================================

class AccrualInfo(BaseModel):
    """Accrual information for display to employees."""
    method: AccrualMethodDisplay = Field(..., description="How time-off accrues")
    method_description: str = Field(..., description="Human-readable description of accrual method")
    annual_rate: float = Field(..., description="Annual accrual rate in days")
    current_tier_rate: Optional[float] = Field(
        default=None,
        description="Current rate based on employee tenure"
    )
    next_tier_rate: Optional[float] = Field(
        default=None,
        description="Rate at next tenure milestone"
    )
    next_tier_date: Optional[date] = Field(
        default=None,
        description="Date when employee reaches next tier"
    )
    frequency_description: str = Field(
        default="Annually",
        description="How often time-off is accrued"
    )
    cap: Optional[float] = Field(
        default=None,
        description="Maximum that can be accrued per period"
    )


class BalanceInfo(BaseModel):
    """Balance limits and carryover rules for display."""
    max_balance: Optional[float] = Field(
        default=None,
        description="Maximum balance that can be accumulated"
    )
    max_balance_description: str = Field(
        default="No limit",
        description="Human-readable max balance description"
    )
    carryover_allowed: bool = Field(
        default=False,
        description="Whether unused time can be carried over"
    )
    max_carryover: Optional[float] = Field(
        default=None,
        description="Maximum days that can be carried over"
    )
    carryover_expiry: Optional[str] = Field(
        default=None,
        description="When carried over time expires"
    )
    carryover_description: str = Field(
        default="No carryover allowed",
        description="Human-readable carryover rules"
    )
    allows_negative: bool = Field(
        default=False,
        description="Whether negative balance is permitted"
    )


class RequestRules(BaseModel):
    """Request rules and constraints for display."""
    min_request_days: float = Field(
        default=0.5,
        description="Minimum days per request"
    )
    min_request_description: str = Field(
        default="Half day minimum",
        description="Human-readable minimum request"
    )
    max_request_days: Optional[float] = Field(
        default=None,
        description="Maximum days per request"
    )
    max_request_description: str = Field(
        default="No maximum",
        description="Human-readable maximum request"
    )
    advance_notice_days: int = Field(
        default=0,
        description="Required advance notice in days"
    )
    advance_notice_description: str = Field(
        default="No advance notice required",
        description="Human-readable notice requirement"
    )
    max_consecutive_days: Optional[int] = Field(
        default=None,
        description="Maximum consecutive days allowed"
    )
    consecutive_description: str = Field(
        default="No limit on consecutive days",
        description="Human-readable consecutive days limit"
    )
    includes_weekends: bool = Field(
        default=False,
        description="Whether weekends count against balance"
    )
    includes_holidays: bool = Field(
        default=False,
        description="Whether holidays count against balance"
    )


class ApprovalInfo(BaseModel):
    """Approval workflow information for display."""
    requires_approval: bool = Field(
        default=True,
        description="Whether approval is required"
    )
    approval_levels: int = Field(
        default=1,
        description="Number of approval levels"
    )
    approval_description: str = Field(
        default="Manager approval required",
        description="Human-readable approval process"
    )
    auto_approve_threshold: Optional[float] = Field(
        default=None,
        description="Days threshold for auto-approval"
    )
    auto_approve_description: Optional[str] = Field(
        default=None,
        description="Auto-approval rules if applicable"
    )
    typical_approval_time: str = Field(
        default="1-2 business days",
        description="Expected time for approval"
    )


class BlackoutPeriod(BaseModel):
    """Blackout period when time-off cannot be taken."""
    id: int = Field(..., description="Blackout period ID")
    name: str = Field(..., description="Name of the blackout period")
    start_date: date = Field(..., description="Start date")
    end_date: date = Field(..., description="End date")
    reason: str = Field(..., description="Reason for blackout")
    is_recurring: bool = Field(default=False, description="Whether this recurs annually")
    applies_to_policy_types: List[str] = Field(
        default_factory=list,
        description="Policy types this blackout applies to"
    )
    severity: str = Field(
        default="hard",
        description="hard = no exceptions, soft = exceptions possible"
    )


class UsageRestriction(BaseModel):
    """Usage restrictions and special rules."""
    restriction_type: str = Field(..., description="Type of restriction")
    description: str = Field(..., description="Human-readable description")
    applies_to: Optional[str] = Field(default=None, description="What this applies to")
    guidance: str = Field(..., description="Guidance for the employee")


class EmployeePolicyResponse(BaseModel):
    """Complete policy information for an employee."""
    id: int = Field(..., description="Policy ID")
    name: str = Field(..., description="Policy name")
    code: str = Field(..., description="Policy code")
    description: Optional[str] = Field(default=None, description="Policy description")
    policy_type: PolicyTypeDisplay = Field(..., description="Type of time-off")
    policy_type_display: str = Field(..., description="Human-readable type name")
    
    # Accrual information
    accrual: AccrualInfo = Field(..., description="Accrual information")
    
    # Balance information
    balance: BalanceInfo = Field(..., description="Balance limits and rules")
    
    # Request rules
    request_rules: RequestRules = Field(..., description="Request constraints")
    
    # Approval information
    approval: ApprovalInfo = Field(..., description="Approval workflow")
    
    # Eligibility
    employee_eligible: bool = Field(
        default=True,
        description="Whether current employee is eligible"
    )
    eligibility_status: str = Field(
        default="Eligible",
        description="Human-readable eligibility status"
    )
    eligibility_start_date: Optional[date] = Field(
        default=None,
        description="Date when eligibility began"
    )
    waiting_period_remaining: Optional[int] = Field(
        default=None,
        description="Days remaining in waiting period"
    )
    
    # Current employee-specific info
    current_balance: Optional[float] = Field(
        default=None,
        description="Employee's current balance"
    )
    pending_requests_days: Optional[float] = Field(
        default=None,
        description="Days in pending requests"
    )
    available_balance: Optional[float] = Field(
        default=None,
        description="Balance minus pending requests"
    )
    
    # Effective dates
    policy_effective_date: Optional[date] = Field(
        default=None,
        description="When policy became/becomes effective"
    )
    policy_expiry_date: Optional[date] = Field(
        default=None,
        description="When policy expires if applicable"
    )
    
    # UI guidance
    icon: str = Field(default="calendar", description="Icon identifier for UI")
    color: str = Field(default="#4A90D9", description="Color for UI display")
    priority: int = Field(default=0, description="Display priority (lower = higher)")

    class Config:
        json_schema_extra = {
            "example": {
                "id": 1,
                "name": "Standard Vacation",
                "code": "VAC-STD",
                "description": "Standard vacation policy for full-time employees",
                "policy_type": "vacation",
                "policy_type_display": "Vacation",
                "accrual": {
                    "method": "annual_lump_sum",
                    "method_description": "Full balance granted at start of year",
                    "annual_rate": 15.0,
                    "current_tier_rate": 15.0,
                    "frequency_description": "Annually on January 1st",
                },
                "balance": {
                    "max_balance": 40.0,
                    "max_balance_description": "Maximum 40 days",
                    "carryover_allowed": True,
                    "max_carryover": 5.0,
                    "carryover_description": "Up to 5 days may be carried over",
                },
                "request_rules": {
                    "min_request_days": 0.5,
                    "advance_notice_days": 14,
                    "advance_notice_description": "14 days advance notice required",
                },
                "approval": {
                    "requires_approval": True,
                    "approval_levels": 1,
                    "approval_description": "Manager approval required",
                },
                "employee_eligible": True,
                "eligibility_status": "Eligible",
                "current_balance": 12.5,
                "pending_requests_days": 2.0,
                "available_balance": 10.5,
            }
        }


class EmployeePoliciesListResponse(BaseModel):
    """Response containing all applicable policies for an employee."""
    employee_id: int = Field(..., description="Employee ID")
    employee_name: str = Field(..., description="Employee name")
    policies: List[EmployeePolicyResponse] = Field(
        default_factory=list,
        description="List of applicable policies"
    )
    total_policies: int = Field(default=0, description="Total number of policies")
    
    # Summary information
    total_available_days: float = Field(
        default=0,
        description="Total available days across all policies"
    )
    upcoming_blackouts: List[BlackoutPeriod] = Field(
        default_factory=list,
        description="Upcoming blackout periods"
    )
    
    # Metadata
    last_updated: datetime = Field(
        default_factory=datetime.utcnow,
        description="When this information was last calculated"
    )
    guidance_message: Optional[str] = Field(
        default=None,
        description="General guidance for the employee"
    )

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


# =============================================================================
# Policy Constraints Response Models
# =============================================================================

class DateConstraint(BaseModel):
    """Date-based constraint for time-off requests."""
    constraint_type: str = Field(..., description="Type: blackout, peak, holiday")
    start_date: date = Field(..., description="Start date")
    end_date: date = Field(..., description="End date")
    name: str = Field(..., description="Name of the constraint period")
    description: str = Field(..., description="Human-readable description")
    severity: str = Field(
        default="hard",
        description="hard = blocked, soft = warning, info = informational"
    )
    can_request_exception: bool = Field(
        default=False,
        description="Whether employee can request an exception"
    )
    exception_process: Optional[str] = Field(
        default=None,
        description="How to request an exception"
    )


class NoticeRequirement(BaseModel):
    """Notice requirement for different request durations."""
    min_days: float = Field(..., description="Minimum days in request")
    max_days: Optional[float] = Field(default=None, description="Maximum days")
    notice_required: int = Field(..., description="Days of notice required")
    description: str = Field(..., description="Human-readable description")


class DocumentRequirement(BaseModel):
    """Documentation requirements for time-off requests."""
    requirement_type: str = Field(..., description="Type of document required")
    description: str = Field(..., description="What is required")
    when_required: str = Field(..., description="When this is needed")
    how_to_submit: str = Field(..., description="How to submit the document")
    is_mandatory: bool = Field(default=False, description="Whether this is mandatory")


class PolicyConstraintsResponse(BaseModel):
    """Detailed constraint information for a specific policy."""
    policy_id: int = Field(..., description="Policy ID")
    policy_name: str = Field(..., description="Policy name")
    policy_code: str = Field(..., description="Policy code")
    
    # Blackout dates
    blackout_periods: List[BlackoutPeriod] = Field(
        default_factory=list,
        description="Periods when time-off cannot be taken"
    )
    
    # Date constraints
    date_constraints: List[DateConstraint] = Field(
        default_factory=list,
        description="Date-based restrictions"
    )
    
    # Notice requirements
    notice_requirements: List[NoticeRequirement] = Field(
        default_factory=list,
        description="Notice requirements by duration"
    )
    
    # Usage restrictions
    usage_restrictions: List[UsageRestriction] = Field(
        default_factory=list,
        description="Usage restrictions and rules"
    )
    
    # Documentation requirements
    documentation_requirements: List[DocumentRequirement] = Field(
        default_factory=list,
        description="Required documentation"
    )
    
    # Balance-related constraints
    minimum_balance_required: float = Field(
        default=0,
        description="Minimum balance required to make a request"
    )
    allows_negative_balance: bool = Field(
        default=False,
        description="Whether requests can go negative"
    )
    max_negative_allowed: Optional[float] = Field(
        default=None,
        description="Maximum negative balance if allowed"
    )
    
    # Team coverage constraints
    team_coverage_required: bool = Field(
        default=False,
        description="Whether team coverage is required"
    )
    max_team_absent_percentage: Optional[float] = Field(
        default=None,
        description="Maximum percentage of team absent"
    )
    coverage_description: Optional[str] = Field(
        default=None,
        description="Team coverage requirements"
    )
    
    # Request timing
    earliest_request_date: date = Field(
        default_factory=date.today,
        description="Earliest date that can be requested"
    )
    latest_request_date: Optional[date] = Field(
        default=None,
        description="Latest date that can be requested"
    )
    request_window_description: str = Field(
        default="No restriction on request dates",
        description="Description of request window"
    )
    
    # Approval requirements for this policy
    approval_chain: List[str] = Field(
        default_factory=list,
        description="List of approvers in order"
    )
    escalation_rules: Optional[str] = Field(
        default=None,
        description="When/how requests escalate"
    )
    
    # Special conditions
    special_conditions: List[str] = Field(
        default_factory=list,
        description="Special conditions or notes"
    )
    
    # UI guidance
    ui_warnings: List[str] = Field(
        default_factory=list,
        description="Warnings to display in the UI"
    )
    ui_info_messages: List[str] = Field(
        default_factory=list,
        description="Informational messages for UI"
    )
    tips: List[str] = Field(
        default_factory=list,
        description="Tips for the employee"
    )
    
    # Metadata
    last_updated: datetime = Field(
        default_factory=datetime.utcnow,
        description="When constraints were last updated"
    )
    effective_date: Optional[date] = Field(
        default=None,
        description="When these constraints became effective"
    )

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
        json_schema_extra = {
            "example": {
                "policy_id": 1,
                "policy_name": "Standard Vacation",
                "policy_code": "VAC-STD",
                "blackout_periods": [
                    {
                        "id": 1,
                        "name": "Year-End Close",
                        "start_date": "2024-12-23",
                        "end_date": "2025-01-02",
                        "reason": "Annual financial close period",
                        "is_recurring": True,
                        "severity": "hard",
                    }
                ],
                "notice_requirements": [
                    {
                        "min_days": 1,
                        "max_days": 3,
                        "notice_required": 3,
                        "description": "3 days notice for 1-3 day requests",
                    },
                    {
                        "min_days": 4,
                        "max_days": None,
                        "notice_required": 14,
                        "description": "14 days notice for 4+ day requests",
                    },
                ],
                "approval_chain": ["Direct Manager", "Department Head"],
                "tips": [
                    "Submit requests early during peak seasons",
                    "Check team calendar before requesting",
                ],
            }
        }

