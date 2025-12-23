"""Pydantic models for time-off balance inquiry API endpoints."""

from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# =============================================================================
# Enums
# =============================================================================

class BalanceStatus(str, Enum):
    """Status of a balance."""
    HEALTHY = "healthy"
    LOW = "low"
    CRITICAL = "critical"
    NEGATIVE = "negative"
    MAXED = "maxed"


class AccrualStatus(str, Enum):
    """Status of accrual."""
    SCHEDULED = "scheduled"
    APPLIED = "applied"
    PENDING = "pending"
    CANCELLED = "cancelled"


# =============================================================================
# Accrual Models
# =============================================================================

class AccrualEntry(BaseModel):
    """Individual accrual entry."""
    accrual_id: int = Field(..., description="Accrual ID")
    accrual_date: date = Field(..., description="Accrual date")
    amount: float = Field(..., description="Accrual amount")
    accrual_type: str = Field(..., description="Accrual type")
    status: AccrualStatus = Field(..., description="Accrual status")
    description: str = Field(..., description="Description")


class ScheduledAccrualInfo(BaseModel):
    """Scheduled accrual information."""
    next_accrual_date: Optional[date] = Field(default=None, description="Next accrual date")
    next_accrual_amount: float = Field(default=0, description="Next accrual amount")
    remaining_accruals_this_year: int = Field(default=0, description="Remaining accruals this year")
    total_remaining_accrual: float = Field(default=0, description="Total remaining accrual")
    accrual_schedule: List[AccrualEntry] = Field(
        default_factory=list,
        description="Scheduled accruals",
    )


# =============================================================================
# Request Impact Models
# =============================================================================

class PendingRequestImpact(BaseModel):
    """Impact of a pending request on balance."""
    request_id: int = Field(..., description="Request ID")
    request_type: str = Field(..., description="Request type")
    start_date: date = Field(..., description="Start date")
    end_date: date = Field(..., description="End date")
    days_requested: float = Field(..., description="Days requested")
    status: str = Field(..., description="Request status")
    submitted_at: datetime = Field(..., description="Submission time")


# =============================================================================
# Policy Balance Models
# =============================================================================

class PolicyBalanceDetail(BaseModel):
    """Detailed balance information for a policy."""
    policy_id: int = Field(..., description="Policy ID")
    policy_name: str = Field(..., description="Policy name")
    policy_code: str = Field(..., description="Policy code")
    policy_type: str = Field(..., description="Policy type (e.g., PTO, Sick)")
    
    # Current balance
    current_balance: float = Field(..., description="Current available balance")
    balance_status: BalanceStatus = Field(..., description="Balance status")
    
    # Balance breakdown
    total_allocated: float = Field(..., description="Total allocated for year")
    total_used: float = Field(..., description="Total used year-to-date")
    total_pending: float = Field(default=0, description="Total pending")
    carryover_balance: float = Field(default=0, description="Carryover from previous year")
    
    # Scheduled accruals
    scheduled_accruals: ScheduledAccrualInfo = Field(..., description="Scheduled accruals")
    
    # Pending requests
    pending_requests: List[PendingRequestImpact] = Field(
        default_factory=list,
        description="Pending requests impacting balance",
    )
    
    # Constraints
    maximum_balance: Optional[float] = Field(default=None, description="Maximum balance")
    minimum_balance: float = Field(default=0, description="Minimum balance")
    negative_balance_allowed: bool = Field(default=False, description="Negative balance allowed")
    
    # Expiration
    expires_on: Optional[date] = Field(default=None, description="Balance expiration date")
    days_until_expiration: Optional[int] = Field(default=None, description="Days until expiration")
    
    # UI display
    display_unit: str = Field(default="days", description="Display unit")
    status_message: Optional[str] = Field(default=None, description="Status message for UI")


# =============================================================================
# Balance Response Models
# =============================================================================

class BalancesSummary(BaseModel):
    """Summary of all balances."""
    total_available: float = Field(..., description="Total available across all policies")
    total_pending: float = Field(default=0, description="Total pending requests")
    total_used_ytd: float = Field(..., description="Total used year-to-date")
    policies_count: int = Field(..., description="Number of policies")


class EmployeeBalancesResponse(BaseModel):
    """Response model for employee balances."""
    employee_id: int = Field(..., description="Employee ID")
    employee_name: str = Field(..., description="Employee name")
    
    # Summary
    summary: BalancesSummary = Field(..., description="Balance summary")
    
    # Policy balances
    policy_balances: List[PolicyBalanceDetail] = Field(
        ...,
        description="Balance by policy",
    )
    
    # As of date
    as_of_date: date = Field(..., description="Balances as of date")
    balance_year: int = Field(..., description="Balance year")
    
    # Metadata
    retrieved_at: datetime = Field(default_factory=datetime.utcnow, description="Retrieval time")

    class Config:
        json_encoders = {
            date: lambda v: v.isoformat(),
            datetime: lambda v: v.isoformat(),
        }


# =============================================================================
# Projection Models
# =============================================================================

class ProjectionScenario(BaseModel):
    """Scenario for projection calculation."""
    scenario_id: str = Field(..., description="Scenario ID")
    description: str = Field(..., description="Scenario description")
    days_to_request: float = Field(..., description="Days being requested")
    request_date: date = Field(..., description="Intended request date")


class ProjectedBalanceDetail(BaseModel):
    """Projected balance for a specific policy."""
    policy_id: int = Field(..., description="Policy ID")
    policy_name: str = Field(..., description="Policy name")
    
    # Current
    current_balance: float = Field(..., description="Current balance")
    
    # Projection
    projection_date: date = Field(..., description="Projection date")
    projected_balance: float = Field(..., description="Projected balance")
    
    # Components
    scheduled_accruals: float = Field(default=0, description="Accruals by projection date")
    pending_deductions: float = Field(default=0, description="Pending request deductions")
    scenario_deductions: float = Field(default=0, description="Scenario deductions")
    
    # Analysis
    will_be_negative: bool = Field(default=False, description="Will be negative")
    shortfall: float = Field(default=0, description="Shortfall amount if negative")
    can_accommodate_scenario: bool = Field(default=True, description="Can accommodate scenario")


class BalanceProjectionResponse(BaseModel):
    """Response model for balance projections."""
    employee_id: int = Field(..., description="Employee ID")
    employee_name: str = Field(..., description="Employee name")
    
    # Projection parameters
    projection_date: date = Field(..., description="Projection target date")
    scenario_applied: Optional[ProjectionScenario] = Field(
        default=None,
        description="Scenario applied",
    )
    
    # Projections by policy
    projected_balances: List[ProjectedBalanceDetail] = Field(
        ...,
        description="Projected balances by policy",
    )
    
    # Summary
    total_projected_balance: float = Field(..., description="Total projected balance")
    total_scheduled_accruals: float = Field(..., description="Total scheduled accruals")
    
    # Recommendations
    recommendations: List[str] = Field(default_factory=list, description="Recommendations")
    
    # Warnings
    warnings: List[str] = Field(default_factory=list, description="Warnings")
    
    # Metadata
    calculated_at: datetime = Field(default_factory=datetime.utcnow, description="Calculation time")

    class Config:
        json_encoders = {
            date: lambda v: v.isoformat(),
            datetime: lambda v: v.isoformat(),
        }


