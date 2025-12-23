"""Pydantic models for employee balance inquiry API."""

from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class BalanceStatusEnum(str, Enum):
    """Status of an employee's balance."""
    HEALTHY = "healthy"
    LOW = "low"
    CRITICAL = "critical"
    NEGATIVE = "negative"


class AccrualTypeEnum(str, Enum):
    """Types of accruals."""
    REGULAR = "regular"
    TENURE_BONUS = "tenure_bonus"
    CARRYOVER = "carryover"
    ADJUSTMENT = "adjustment"
    PRORATION = "proration"


# =============================================================================
# Accrual Information Models
# =============================================================================

class ScheduledAccrual(BaseModel):
    """Information about a scheduled accrual."""
    accrual_date: date = Field(..., description="Date of accrual")
    accrual_type: AccrualTypeEnum = Field(..., description="Type of accrual")
    amount: float = Field(..., description="Amount to be accrued")
    description: Optional[str] = Field(default=None, description="Description")


class AccrualScheduleInfo(BaseModel):
    """Accrual schedule information."""
    next_accrual_date: Optional[date] = Field(default=None, description="Next accrual date")
    next_accrual_amount: float = Field(default=0, description="Next accrual amount")
    remaining_accruals_this_year: int = Field(default=0, description="Remaining accruals this year")
    total_remaining_accrual: float = Field(default=0, description="Total remaining accrual this year")
    scheduled_accruals: List[ScheduledAccrual] = Field(
        default_factory=list,
        description="List of scheduled accruals",
    )


# =============================================================================
# Request Information Models
# =============================================================================

class PendingRequestInfo(BaseModel):
    """Information about a pending time-off request."""
    request_id: int = Field(..., description="Request ID")
    start_date: date = Field(..., description="Start date")
    end_date: date = Field(..., description="End date")
    days_requested: float = Field(..., description="Days requested")
    request_type: str = Field(..., description="Request type")
    status: str = Field(..., description="Request status")
    submitted_at: datetime = Field(..., description="Submission timestamp")


# =============================================================================
# Policy Information Models
# =============================================================================

class PolicyInfo(BaseModel):
    """Policy information for balance context."""
    policy_id: int = Field(..., description="Policy ID")
    policy_name: str = Field(..., description="Policy name")
    policy_code: str = Field(..., description="Policy code")
    policy_type: str = Field(..., description="Type of time-off")
    accrual_method: str = Field(..., description="Accrual method")
    max_balance: Optional[float] = Field(default=None, description="Maximum balance")
    max_carryover: Optional[float] = Field(default=None, description="Maximum carryover")


# =============================================================================
# Constraint Information Models
# =============================================================================

class ConstraintInfo(BaseModel):
    """Constraint validation information."""
    constraint_type: str = Field(..., description="Type of constraint")
    limit: Optional[float] = Field(default=None, description="Limit value")
    current_value: float = Field(..., description="Current value")
    is_within_limit: bool = Field(..., description="Whether within limit")
    message: Optional[str] = Field(default=None, description="Constraint message")


# =============================================================================
# Balance Information Models
# =============================================================================

class PolicyBalance(BaseModel):
    """Balance information for a specific policy."""
    policy: PolicyInfo = Field(..., description="Policy information")
    
    # Balance values
    total_allocated: float = Field(..., description="Total allocated balance")
    used: float = Field(..., description="Used balance")
    pending: float = Field(default=0, description="Pending requests")
    available: float = Field(..., description="Available balance")
    carried_over: float = Field(default=0, description="Carried over from previous year")
    
    # Status
    balance_status: BalanceStatusEnum = Field(..., description="Balance status")
    status_message: Optional[str] = Field(default=None, description="Status message")
    
    # Accrual information
    accrual_info: AccrualScheduleInfo = Field(..., description="Accrual schedule")
    
    # Pending requests
    pending_requests: List[PendingRequestInfo] = Field(
        default_factory=list,
        description="Pending time-off requests",
    )
    
    # Constraints
    constraints: List[ConstraintInfo] = Field(
        default_factory=list,
        description="Constraint validation",
    )
    
    # As of date
    as_of_date: date = Field(..., description="Balance as of date")
    year: int = Field(..., description="Balance year")


class EmployeeBalanceResponse(BaseModel):
    """Complete balance response for an employee."""
    employee_id: int = Field(..., description="Employee ID")
    employee_name: str = Field(..., description="Employee name")
    
    # Balance by policy
    balances: List[PolicyBalance] = Field(..., description="Balance by policy")
    
    # Summary
    total_available_days: float = Field(..., description="Total available days across policies")
    total_pending_days: float = Field(..., description="Total pending days")
    
    # Metadata
    retrieved_at: datetime = Field(default_factory=datetime.utcnow, description="Retrieval timestamp")

    class Config:
        json_encoders = {
            date: lambda v: v.isoformat(),
            datetime: lambda v: v.isoformat(),
        }


# =============================================================================
# Projection Models
# =============================================================================

class ScenarioAdjustment(BaseModel):
    """Adjustment for projection scenario."""
    adjustment_type: str = Field(..., description="Type: request, adjustment, accrual")
    amount: float = Field(..., description="Amount")
    effective_date: date = Field(..., description="Effective date")
    description: Optional[str] = Field(default=None, description="Description")


class ProjectionRequest(BaseModel):
    """Request for balance projection."""
    employee_id: Optional[int] = Field(default=None, description="Employee ID (uses current user if not provided)")
    policy_id: Optional[int] = Field(default=None, description="Policy ID (projects all if not provided)")
    projection_date: date = Field(..., description="Date to project balance to")
    scenario_adjustments: Optional[List[ScenarioAdjustment]] = Field(
        default=None,
        description="Scenario adjustments to apply",
    )
    include_pending_requests: bool = Field(default=True, description="Include pending requests")
    include_scheduled_accruals: bool = Field(default=True, description="Include scheduled accruals")


class ProjectionComponent(BaseModel):
    """Component of balance projection."""
    component_type: str = Field(..., description="Component type")
    date: date = Field(..., description="Effective date")
    amount: float = Field(..., description="Amount")
    running_balance: float = Field(..., description="Running balance after this component")
    description: str = Field(..., description="Description")


class PolicyProjection(BaseModel):
    """Balance projection for a specific policy."""
    policy: PolicyInfo = Field(..., description="Policy information")
    
    # Current values
    current_balance: float = Field(..., description="Current balance")
    
    # Projection
    projected_balance: float = Field(..., description="Projected balance")
    projection_date: date = Field(..., description="Projection date")
    
    # Breakdown
    projected_accruals: float = Field(default=0, description="Projected accruals")
    projected_pending: float = Field(default=0, description="Projected pending")
    projected_adjustments: float = Field(default=0, description="Scenario adjustments")
    
    # Components
    projection_components: List[ProjectionComponent] = Field(
        default_factory=list,
        description="Detailed projection components",
    )
    
    # Constraints
    at_max_balance: bool = Field(default=False, description="Will hit max balance")
    will_expire: bool = Field(default=False, description="Has expiring balance")
    expiring_amount: float = Field(default=0, description="Amount expiring")
    expiry_date: Optional[date] = Field(default=None, description="Expiry date")


class BalanceProjectionResponse(BaseModel):
    """Complete balance projection response."""
    employee_id: int = Field(..., description="Employee ID")
    employee_name: str = Field(..., description="Employee name")
    
    # Projection parameters
    projection_date: date = Field(..., description="Projection date")
    scenario_applied: bool = Field(default=False, description="Whether scenario was applied")
    
    # Projections by policy
    projections: List[PolicyProjection] = Field(..., description="Projections by policy")
    
    # Summary
    total_projected_balance: float = Field(..., description="Total projected balance")
    total_projected_accruals: float = Field(..., description="Total projected accruals")
    
    # Warnings
    warnings: List[str] = Field(default_factory=list, description="Projection warnings")
    
    # Metadata
    calculated_at: datetime = Field(default_factory=datetime.utcnow, description="Calculation timestamp")

    class Config:
        json_encoders = {
            date: lambda v: v.isoformat(),
            datetime: lambda v: v.isoformat(),
        }

