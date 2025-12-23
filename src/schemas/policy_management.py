"""Pydantic models for policy management API."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, validator


class AccrualMethodEnum(str, Enum):
    """Methods for accruing time-off."""
    ANNUAL_LUMP_SUM = "annual_lump_sum"
    MONTHLY_ACCRUAL = "monthly_accrual"
    PAY_PERIOD_ACCRUAL = "pay_period_accrual"
    HOURS_WORKED = "hours_worked"
    NONE = "none"


class PolicyStatusEnum(str, Enum):
    """Status of a policy."""
    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


class PolicyTypeEnum(str, Enum):
    """Types of time-off policies."""
    VACATION = "vacation"
    SICK = "sick"
    PERSONAL = "personal"
    BEREAVEMENT = "bereavement"
    PARENTAL = "parental"
    JURY_DUTY = "jury_duty"
    FLOATING_HOLIDAY = "floating_holiday"
    UNPAID = "unpaid"


# =============================================================================
# Configuration Models
# =============================================================================

class TenureTier(BaseModel):
    """Tenure-based accrual tier."""
    min_years: float = Field(..., ge=0, description="Minimum years of service")
    max_years: Optional[float] = Field(default=None, description="Maximum years (null for unlimited)")
    accrual_rate: float = Field(..., ge=0, description="Annual accrual rate for this tier")
    description: Optional[str] = Field(default=None, description="Tier description")


class EligibilityRule(BaseModel):
    """Eligibility rule for policy assignment."""
    rule_type: str = Field(..., description="Type of rule")
    field: str = Field(..., description="Employee field to check")
    operator: str = Field(..., description="Comparison operator")
    value: Any = Field(..., description="Value to compare against")
    description: Optional[str] = Field(default=None, description="Rule description")


class AccrualConfig(BaseModel):
    """Accrual configuration."""
    method: AccrualMethodEnum = Field(..., description="Accrual method")
    base_rate: float = Field(..., ge=0, description="Base accrual rate (days/year)")
    frequency: Optional[str] = Field(default=None, description="Accrual frequency")
    cap: Optional[float] = Field(default=None, description="Maximum accrual cap")
    tenure_tiers: Optional[List[TenureTier]] = Field(default=None, description="Tenure-based tiers")


class BalanceConfig(BaseModel):
    """Balance configuration."""
    max_balance: Optional[float] = Field(default=None, description="Maximum balance allowed")
    min_balance_allowed: float = Field(default=0, description="Minimum balance allowed")
    max_carryover: Optional[float] = Field(default=None, description="Maximum carryover days")
    carryover_expiry_months: Optional[int] = Field(default=None, description="Months until carryover expires")
    allow_negative: bool = Field(default=False, description="Allow negative balance")


class RequestConfig(BaseModel):
    """Request configuration."""
    min_request_days: float = Field(default=0.5, ge=0, description="Minimum days per request")
    max_request_days: Optional[float] = Field(default=None, description="Maximum days per request")
    advance_notice_days: int = Field(default=0, ge=0, description="Required advance notice")
    max_consecutive_days: Optional[int] = Field(default=None, description="Maximum consecutive days")


class ApprovalConfig(BaseModel):
    """Approval workflow configuration."""
    requires_approval: bool = Field(default=True, description="Whether approval is required")
    approval_levels: int = Field(default=1, ge=1, le=5, description="Number of approval levels")
    auto_approve_threshold: Optional[float] = Field(default=None, description="Auto-approve if under threshold")


# =============================================================================
# Request Models
# =============================================================================

class CreatePolicyRequest(BaseModel):
    """Request to create a new policy."""
    name: str = Field(..., min_length=1, max_length=100, description="Policy name")
    code: str = Field(..., min_length=1, max_length=20, description="Policy code")
    description: Optional[str] = Field(default=None, description="Policy description")
    policy_type: PolicyTypeEnum = Field(..., description="Type of time-off")
    
    # Configuration
    accrual: AccrualConfig = Field(..., description="Accrual configuration")
    balance: Optional[BalanceConfig] = Field(default=None, description="Balance configuration")
    request: Optional[RequestConfig] = Field(default=None, description="Request configuration")
    approval: Optional[ApprovalConfig] = Field(default=None, description="Approval configuration")
    
    # Eligibility
    waiting_period_days: int = Field(default=0, ge=0, description="Waiting period in days")
    eligibility_rules: Optional[List[EligibilityRule]] = Field(default=None, description="Eligibility rules")
    
    # Additional settings
    prorate_first_year: bool = Field(default=True, description="Prorate for first year")
    include_weekends: bool = Field(default=False, description="Count weekends")
    include_holidays: bool = Field(default=False, description="Count holidays")
    
    # Dates
    effective_date: Optional[datetime] = Field(default=None, description="Policy effective date")
    expiry_date: Optional[datetime] = Field(default=None, description="Policy expiry date")
    
    # Initial status
    activate_immediately: bool = Field(default=False, description="Activate upon creation")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Standard Vacation Policy",
                "code": "VAC-STD",
                "description": "Standard vacation policy for full-time employees",
                "policy_type": "vacation",
                "accrual": {
                    "method": "annual_lump_sum",
                    "base_rate": 15,
                    "tenure_tiers": [
                        {"min_years": 0, "max_years": 3, "accrual_rate": 15},
                        {"min_years": 3, "max_years": 7, "accrual_rate": 20},
                        {"min_years": 7, "max_years": None, "accrual_rate": 25},
                    ]
                },
                "balance": {
                    "max_balance": 40,
                    "max_carryover": 5,
                },
                "waiting_period_days": 90,
                "activate_immediately": True,
            }
        }


class UpdatePolicyRequest(BaseModel):
    """Request to update an existing policy."""
    name: Optional[str] = Field(default=None, max_length=100, description="Policy name")
    description: Optional[str] = Field(default=None, description="Policy description")
    
    # Configuration updates
    accrual: Optional[AccrualConfig] = Field(default=None, description="Accrual configuration")
    balance: Optional[BalanceConfig] = Field(default=None, description="Balance configuration")
    request: Optional[RequestConfig] = Field(default=None, description="Request configuration")
    approval: Optional[ApprovalConfig] = Field(default=None, description="Approval configuration")
    
    # Eligibility updates
    waiting_period_days: Optional[int] = Field(default=None, description="Waiting period")
    eligibility_rules: Optional[List[EligibilityRule]] = Field(default=None, description="Eligibility rules")
    
    # Additional settings
    prorate_first_year: Optional[bool] = Field(default=None, description="Prorate for first year")
    include_weekends: Optional[bool] = Field(default=None, description="Count weekends")
    include_holidays: Optional[bool] = Field(default=None, description="Count holidays")
    
    # Dates
    effective_date: Optional[datetime] = Field(default=None, description="Policy effective date")
    expiry_date: Optional[datetime] = Field(default=None, description="Policy expiry date")
    
    # Change management
    change_reason: Optional[str] = Field(default=None, description="Reason for changes")
    notify_affected_employees: bool = Field(default=True, description="Notify affected employees")


class DeactivatePolicyRequest(BaseModel):
    """Request to deactivate a policy."""
    reason: str = Field(..., min_length=10, description="Reason for deactivation")
    alternative_policy_id: Optional[int] = Field(default=None, description="Alternative policy for reassignment")
    transfer_balances: bool = Field(default=True, description="Transfer balances to alternative")
    effective_date: Optional[datetime] = Field(default=None, description="Deactivation effective date")
    notify_employees: bool = Field(default=True, description="Notify affected employees")


# =============================================================================
# Response Models
# =============================================================================

class PolicyVersionInfo(BaseModel):
    """Policy version information."""
    version_number: int = Field(..., description="Version number")
    created_at: datetime = Field(..., description="Version creation timestamp")
    created_by_name: Optional[str] = Field(default=None, description="Creator name")
    change_summary: Optional[str] = Field(default=None, description="Change summary")


class AssignmentStats(BaseModel):
    """Policy assignment statistics."""
    total_assigned: int = Field(default=0, description="Total employees assigned")
    active_assigned: int = Field(default=0, description="Active employees assigned")
    pending_requests: int = Field(default=0, description="Pending time-off requests")
    total_balance_allocated: float = Field(default=0, description="Total balance allocated")


class AuditEntry(BaseModel):
    """Audit trail entry."""
    id: int = Field(..., description="Audit entry ID")
    action: str = Field(..., description="Action performed")
    performed_by_name: str = Field(..., description="Actor name")
    performed_at: datetime = Field(..., description="Timestamp")
    notes: Optional[str] = Field(default=None, description="Notes")


class PolicyResponse(BaseModel):
    """Complete policy details response."""
    id: int = Field(..., description="Policy ID")
    name: str = Field(..., description="Policy name")
    code: str = Field(..., description="Policy code")
    description: Optional[str] = Field(default=None, description="Policy description")
    policy_type: str = Field(..., description="Type of time-off")
    status: PolicyStatusEnum = Field(..., description="Policy status")
    version: int = Field(..., description="Current version")
    
    # Configuration
    accrual: AccrualConfig = Field(..., description="Accrual configuration")
    balance: BalanceConfig = Field(..., description="Balance configuration")
    request: RequestConfig = Field(..., description="Request configuration")
    approval: ApprovalConfig = Field(..., description="Approval configuration")
    
    # Eligibility
    waiting_period_days: int = Field(..., description="Waiting period")
    eligibility_rules: Optional[List[EligibilityRule]] = Field(default=None, description="Eligibility rules")
    
    # Additional settings
    prorate_first_year: bool = Field(..., description="Prorate for first year")
    include_weekends: bool = Field(..., description="Count weekends")
    include_holidays: bool = Field(..., description="Count holidays")
    
    # Dates
    effective_date: Optional[datetime] = Field(default=None, description="Effective date")
    expiry_date: Optional[datetime] = Field(default=None, description="Expiry date")
    
    # Statistics
    assignment_stats: AssignmentStats = Field(..., description="Assignment statistics")
    
    # Version history
    version_history: List[PolicyVersionInfo] = Field(default_factory=list, description="Version history")
    
    # Audit
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(default=None, description="Last update timestamp")
    created_by: Optional[int] = Field(default=None, description="Creator ID")
    recent_audit_entries: List[AuditEntry] = Field(default_factory=list, description="Recent audit entries")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class PolicyCreateResponse(BaseModel):
    """Response for policy creation."""
    policy: PolicyResponse = Field(..., description="Created policy")
    assignment_recommendations: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Recommended employee assignments based on eligibility",
    )
    eligible_employee_count: int = Field(default=0, description="Number of eligible employees")
    message: str = Field(..., description="Success message")


class PolicyUpdateResponse(BaseModel):
    """Response for policy update."""
    policy: PolicyResponse = Field(..., description="Updated policy")
    impact_analysis: Dict[str, Any] = Field(default_factory=dict, description="Impact analysis")
    affected_employees: int = Field(default=0, description="Number of affected employees")
    notifications_queued: int = Field(default=0, description="Notifications queued")
    version_created: bool = Field(default=True, description="Whether new version was created")
    message: str = Field(..., description="Success message")


class PolicyDeactivateResponse(BaseModel):
    """Response for policy deactivation."""
    policy_id: int = Field(..., description="Deactivated policy ID")
    new_status: PolicyStatusEnum = Field(..., description="New status")
    employees_affected: int = Field(..., description="Employees affected")
    balances_transferred: int = Field(default=0, description="Balances transferred")
    alternative_policy_id: Optional[int] = Field(default=None, description="Alternative policy")
    final_accrual_processed: bool = Field(default=True, description="Final accruals processed")
    audit_entry: AuditEntry = Field(..., description="Audit entry")
    message: str = Field(..., description="Success message")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class PolicyListResponse(BaseModel):
    """Response for policy list."""
    policies: List[PolicyResponse] = Field(..., description="List of policies")
    total: int = Field(..., description="Total count")
    page: int = Field(default=1, description="Current page")
    page_size: int = Field(default=20, description="Page size")


class ValidationError(BaseModel):
    """Validation error detail."""
    field: str = Field(..., description="Field with error")
    message: str = Field(..., description="Error message")
    code: str = Field(..., description="Error code")

