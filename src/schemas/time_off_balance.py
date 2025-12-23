"""Data models for time-off balance display feature.

This module provides display-specific data models for time-off balance
calculations, projections, and policy compliance validation.
"""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


# =============================================================================
# Enums
# =============================================================================

class AccrualType(str, Enum):
    """Type of accrual event."""
    
    PERIODIC = "periodic"           # Regular periodic accrual (monthly, quarterly)
    ANNIVERSARY = "anniversary"     # Annual anniversary accrual
    TENURE_ADJUSTMENT = "tenure_adjustment"  # Adjustment based on tenure milestone


class PolicyType(str, Enum):
    """Type of time-off policy."""
    
    VACATION = "vacation"
    SICK = "sick"
    PERSONAL = "personal"
    BEREAVEMENT = "bereavement"
    JURY_DUTY = "jury_duty"
    PARENTAL = "parental"
    UNPAID = "unpaid"
    FLOATING_HOLIDAY = "floating_holiday"
    COMPENSATORY = "compensatory"


class BalanceStatus(str, Enum):
    """Status of a balance."""
    
    ACTIVE = "active"
    EXPIRED = "expired"
    CAPPED = "capped"
    NEGATIVE = "negative"


# =============================================================================
# Scheduled Accrual Model
# =============================================================================

class ScheduledAccrual(BaseModel):
    """
    Represents a scheduled accrual event.
    
    Used for displaying upcoming accruals in balance projections.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "accrual_date": "2025-02-01",
                "accrual_amount": "1.25",
                "accrual_type": "periodic",
                "description": "Monthly vacation accrual"
            }
        }
    )
    
    accrual_date: date = Field(
        ...,
        description="Date when the accrual will be credited"
    )
    
    accrual_amount: Decimal = Field(
        ...,
        decimal_places=4,
        ge=Decimal("0"),
        description="Amount to be accrued (in days or hours)"
    )
    
    accrual_type: AccrualType = Field(
        ...,
        description="Type of accrual (periodic, anniversary, tenure_adjustment)"
    )
    
    description: str = Field(
        ...,
        max_length=255,
        description="Human-readable description of the accrual"
    )
    
    # Optional additional fields
    policy_id: Optional[UUID] = Field(
        None,
        description="Associated policy ID"
    )
    
    is_confirmed: bool = Field(
        default=True,
        description="Whether this accrual is confirmed vs tentative"
    )


# =============================================================================
# Policy Balance Detail Model
# =============================================================================

class PolicyBalanceDetail(BaseModel):
    """
    Detailed balance information for a specific policy.
    
    Provides comprehensive view of balance status, accruals, and caps.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "policy_id": "123e4567-e89b-12d3-a456-426614174000",
                "policy_name": "Annual Vacation",
                "policy_type": "vacation",
                "current_balance": "10.50",
                "pending_requests": "3.00",
                "available_balance": "7.50",
                "accrual_rate": "1.25",
                "next_accrual_date": "2025-02-01",
                "next_accrual_amount": "1.25",
                "balance_cap": "20.00",
                "carryover_eligible": "5.00"
            }
        }
    )
    
    # Identifiers
    policy_id: UUID = Field(
        ...,
        description="Unique identifier for the time-off policy"
    )
    
    policy_name: str = Field(
        ...,
        max_length=100,
        description="Display name of the policy"
    )
    
    policy_type: PolicyType = Field(
        ...,
        description="Type of time-off policy"
    )
    
    # Balance fields with appropriate precision
    current_balance: Decimal = Field(
        ...,
        decimal_places=4,
        description="Current accrued balance (total earned minus used)"
    )
    
    pending_requests: Decimal = Field(
        default=Decimal("0"),
        decimal_places=4,
        ge=Decimal("0"),
        description="Balance pending in unapproved requests"
    )
    
    available_balance: Decimal = Field(
        ...,
        decimal_places=4,
        description="Balance available for new requests (current - pending)"
    )
    
    # Accrual information
    accrual_rate: Decimal = Field(
        default=Decimal("0"),
        decimal_places=4,
        ge=Decimal("0"),
        description="Rate of accrual per period"
    )
    
    next_accrual_date: Optional[date] = Field(
        None,
        description="Date of next scheduled accrual"
    )
    
    next_accrual_amount: Optional[Decimal] = Field(
        None,
        decimal_places=4,
        ge=Decimal("0"),
        description="Amount of next scheduled accrual"
    )
    
    # Caps and limits
    balance_cap: Optional[Decimal] = Field(
        None,
        decimal_places=4,
        ge=Decimal("0"),
        description="Maximum balance allowed (cap)"
    )
    
    carryover_eligible: Decimal = Field(
        default=Decimal("0"),
        decimal_places=4,
        ge=Decimal("0"),
        description="Amount eligible for carryover to next period"
    )
    
    # Status and metadata
    status: BalanceStatus = Field(
        default=BalanceStatus.ACTIVE,
        description="Current status of the balance"
    )
    
    is_accruing: bool = Field(
        default=True,
        description="Whether balance is still accruing"
    )
    
    is_near_cap: bool = Field(
        default=False,
        description="Whether balance is approaching the cap"
    )
    
    cap_percentage: Optional[float] = Field(
        None,
        ge=0,
        le=100,
        description="Percentage of cap utilized"
    )
    
    # Year-to-date information
    ytd_accrued: Optional[Decimal] = Field(
        None,
        decimal_places=4,
        ge=Decimal("0"),
        description="Total accrued year-to-date"
    )
    
    ytd_used: Optional[Decimal] = Field(
        None,
        decimal_places=4,
        ge=Decimal("0"),
        description="Total used year-to-date"
    )


# =============================================================================
# Balance Projection Summary Model
# =============================================================================

class BalanceProjectionSummary(BaseModel):
    """
    Summary of balance projections for future dates.
    
    Used for planning and forecasting available time-off.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "policy_id": "123e4567-e89b-12d3-a456-426614174000",
                "projection_date": "2025-06-30",
                "current_balance": "10.50",
                "scheduled_accruals": [
                    {
                        "accrual_date": "2025-02-01",
                        "accrual_amount": "1.25",
                        "accrual_type": "periodic",
                        "description": "Monthly accrual"
                    }
                ],
                "projected_balance": "17.50",
                "pending_usage": "3.00",
                "available_for_request": "14.50"
            }
        }
    )
    
    # Identifiers
    policy_id: UUID = Field(
        ...,
        description="Policy this projection is for"
    )
    
    projection_date: date = Field(
        ...,
        description="Date the projection is calculated for"
    )
    
    # Current state
    current_balance: Decimal = Field(
        ...,
        decimal_places=4,
        description="Balance as of calculation date"
    )
    
    # Scheduled accruals
    scheduled_accruals: List[ScheduledAccrual] = Field(
        default_factory=list,
        description="List of scheduled accruals between now and projection date"
    )
    
    # Projections
    projected_balance: Decimal = Field(
        ...,
        decimal_places=4,
        description="Projected balance at projection date (including accruals)"
    )
    
    pending_usage: Decimal = Field(
        default=Decimal("0"),
        decimal_places=4,
        ge=Decimal("0"),
        description="Approved/pending requests between now and projection date"
    )
    
    available_for_request: Decimal = Field(
        ...,
        decimal_places=4,
        description="Amount available for new requests at projection date"
    )
    
    # Calculation metadata
    total_scheduled_accruals: Decimal = Field(
        default=Decimal("0"),
        decimal_places=4,
        ge=Decimal("0"),
        description="Sum of all scheduled accruals"
    )
    
    projection_confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence level of projection (1.0 = certain)"
    )
    
    assumptions: List[str] = Field(
        default_factory=list,
        description="Assumptions used in projection calculation"
    )


# =============================================================================
# Employee Balance Summary Model
# =============================================================================

class EmployeeBalanceSummary(BaseModel):
    """
    Complete balance summary for an employee.
    
    Aggregates all policy balances and provides overall summary.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "employee_id": "123e4567-e89b-12d3-a456-426614174000",
                "policy_balances": [
                    {
                        "policy_id": "123e4567-e89b-12d3-a456-426614174001",
                        "policy_name": "Annual Vacation",
                        "policy_type": "vacation",
                        "current_balance": "10.50",
                        "pending_requests": "3.00",
                        "available_balance": "7.50",
                        "accrual_rate": "1.25"
                    }
                ],
                "last_updated": "2024-12-01T10:30:00Z",
                "calculation_date": "2024-12-01"
            }
        }
    )
    
    # Employee identifier
    employee_id: UUID = Field(
        ...,
        description="Unique identifier for the employee"
    )
    
    # Optional employee info for display
    employee_name: Optional[str] = Field(
        None,
        max_length=200,
        description="Employee display name"
    )
    
    employee_number: Optional[str] = Field(
        None,
        max_length=50,
        description="Employee number/ID"
    )
    
    # Policy balances
    policy_balances: List[PolicyBalanceDetail] = Field(
        default_factory=list,
        description="List of balance details for each applicable policy"
    )
    
    # Timestamps with timezone consideration
    last_updated: datetime = Field(
        ...,
        description="Timestamp when balances were last calculated (UTC)"
    )
    
    calculation_date: date = Field(
        ...,
        description="Date balances are calculated as of"
    )
    
    # Aggregate summary
    total_available_days: Decimal = Field(
        default=Decimal("0"),
        decimal_places=4,
        ge=Decimal("0"),
        description="Total available balance across all policies"
    )
    
    total_pending_days: Decimal = Field(
        default=Decimal("0"),
        decimal_places=4,
        ge=Decimal("0"),
        description="Total pending requests across all policies"
    )
    
    # Status flags
    has_negative_balance: bool = Field(
        default=False,
        description="Whether any policy has negative balance"
    )
    
    has_expiring_balance: bool = Field(
        default=False,
        description="Whether any balance is expiring soon"
    )
    
    policies_at_cap: int = Field(
        default=0,
        ge=0,
        description="Number of policies at or near cap"
    )
    
    # Upcoming events
    next_accrual_date: Optional[date] = Field(
        None,
        description="Date of next accrual across all policies"
    )
    
    next_expiration_date: Optional[date] = Field(
        None,
        description="Date of next balance expiration"
    )
    
    # Projections
    projections: List[BalanceProjectionSummary] = Field(
        default_factory=list,
        description="Balance projections for future dates"
    )
    
    # Data freshness
    is_stale: bool = Field(
        default=False,
        description="Whether the balance data may be outdated"
    )
    
    cache_ttl_seconds: Optional[int] = Field(
        None,
        ge=0,
        description="Time until this data should be refreshed"
    )


# =============================================================================
# Balance Change Event Model
# =============================================================================

class BalanceChangeEvent(BaseModel):
    """
    Represents a balance change event for audit and display.
    """
    
    event_id: UUID = Field(
        ...,
        description="Unique identifier for the event"
    )
    
    employee_id: UUID = Field(
        ...,
        description="Employee affected"
    )
    
    policy_id: UUID = Field(
        ...,
        description="Policy affected"
    )
    
    event_type: str = Field(
        ...,
        max_length=50,
        description="Type of event (accrual, usage, adjustment, etc.)"
    )
    
    event_date: datetime = Field(
        ...,
        description="When the event occurred"
    )
    
    amount: Decimal = Field(
        ...,
        decimal_places=4,
        description="Amount changed (positive for credit, negative for debit)"
    )
    
    balance_before: Decimal = Field(
        ...,
        decimal_places=4,
        description="Balance before the change"
    )
    
    balance_after: Decimal = Field(
        ...,
        decimal_places=4,
        description="Balance after the change"
    )
    
    description: str = Field(
        ...,
        max_length=500,
        description="Description of the change"
    )
    
    reference_id: Optional[str] = Field(
        None,
        max_length=100,
        description="Reference to related record (request ID, etc.)"
    )


# =============================================================================
# Balance Query Parameters
# =============================================================================

class BalanceQueryParams(BaseModel):
    """
    Parameters for querying balance information.
    """
    
    employee_id: UUID = Field(
        ...,
        description="Employee to query balances for"
    )
    
    as_of_date: Optional[date] = Field(
        None,
        description="Calculate balances as of this date"
    )
    
    include_projections: bool = Field(
        default=False,
        description="Include balance projections"
    )
    
    projection_end_date: Optional[date] = Field(
        None,
        description="End date for projections"
    )
    
    policy_ids: Optional[List[UUID]] = Field(
        None,
        description="Filter to specific policies"
    )
    
    policy_types: Optional[List[PolicyType]] = Field(
        None,
        description="Filter to specific policy types"
    )
    
    include_history: bool = Field(
        default=False,
        description="Include recent balance change history"
    )
    
    history_days: int = Field(
        default=30,
        ge=1,
        le=365,
        description="Number of days of history to include"
    )

