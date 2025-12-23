"""Pydantic models for balance projections and conflict detection API endpoints."""

from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# =============================================================================
# Enums
# =============================================================================

class ProjectionConfidenceLevel(str, Enum):
    """Confidence level for projections."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class AccrualType(str, Enum):
    """Type of accrual."""
    SCHEDULED = "scheduled"
    TENURE_BONUS = "tenure_bonus"
    CARRYOVER = "carryover"
    ADJUSTMENT = "adjustment"
    GRANT = "grant"


class ConflictType(str, Enum):
    """Type of scheduling conflict."""
    COMPANY_HOLIDAY = "company_holiday"
    BLACKOUT_PERIOD = "blackout_period"
    TEAM_CALENDAR = "team_calendar"
    CONCURRENT_REQUEST = "concurrent_request"
    COVERAGE_REQUIREMENT = "coverage_requirement"
    ORGANIZATIONAL_EVENT = "organizational_event"
    BUSINESS_CRITICAL = "business_critical"


class ConflictSeverity(str, Enum):
    """Severity level of conflict."""
    BLOCKING = "blocking"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ScenarioType(str, Enum):
    """Type of what-if scenario."""
    BASELINE = "baseline"
    WITH_PENDING = "with_pending"
    OPTIMISTIC = "optimistic"
    CONSERVATIVE = "conservative"
    CUSTOM = "custom"


# =============================================================================
# Accrual and Policy Models
# =============================================================================

class ScheduledAccrual(BaseModel):
    """Scheduled accrual information."""
    accrual_date: date = Field(..., description="Accrual date")
    accrual_type: AccrualType = Field(..., description="Type of accrual")
    amount: float = Field(..., description="Accrual amount")
    description: str = Field(..., description="Description")
    policy_id: int = Field(..., description="Associated policy ID")


class PolicyConstraint(BaseModel):
    """Policy constraint information."""
    constraint_type: str = Field(..., description="Constraint type")
    limit_value: Optional[float] = Field(default=None, description="Limit value")
    effective_date: Optional[date] = Field(default=None, description="Effective date")
    description: str = Field(..., description="Constraint description")
    impact_on_balance: Optional[float] = Field(default=None, description="Impact on balance")


class CarryoverInfo(BaseModel):
    """Carryover information."""
    amount: float = Field(..., description="Carryover amount")
    expires_on: Optional[date] = Field(default=None, description="Expiration date")
    is_use_it_or_lose_it: bool = Field(default=False, description="Use it or lose it policy")
    days_until_expiration: Optional[int] = Field(default=None, description="Days until expiration")


# =============================================================================
# Projection Models
# =============================================================================

class ProjectionComponent(BaseModel):
    """Component of balance projection."""
    component_date: date = Field(..., description="Date of component")
    component_type: str = Field(..., description="Type: accrual, request, adjustment, expiration")
    amount: float = Field(..., description="Amount (positive or negative)")
    running_balance: float = Field(..., description="Running balance after this component")
    description: str = Field(..., description="Description")
    request_id: Optional[int] = Field(default=None, description="Associated request ID")


class PolicyProjection(BaseModel):
    """Balance projection for a specific policy."""
    policy_id: int = Field(..., description="Policy ID")
    policy_name: str = Field(..., description="Policy name")
    policy_code: str = Field(..., description="Policy code")
    
    # Current state
    current_balance: float = Field(..., description="Current balance")
    as_of_date: date = Field(..., description="Current balance as of date")
    
    # Projections
    projected_balance: float = Field(..., description="Projected balance at end date")
    projection_date: date = Field(..., description="Projection target date")
    
    # Components
    scheduled_accruals: List[ScheduledAccrual] = Field(
        default_factory=list,
        description="Scheduled accruals",
    )
    total_scheduled_accruals: float = Field(default=0, description="Total scheduled accruals")
    
    # Requests impact
    approved_requests_impact: float = Field(default=0, description="Approved requests impact")
    pending_requests_impact: float = Field(default=0, description="Pending requests impact")
    
    # Carryover
    carryover_info: Optional[CarryoverInfo] = Field(default=None, description="Carryover info")
    
    # Constraints
    constraints_applied: List[PolicyConstraint] = Field(
        default_factory=list,
        description="Constraints applied",
    )
    maximum_balance_limit: Optional[float] = Field(default=None, description="Max balance limit")
    balance_capped: bool = Field(default=False, description="Balance was capped")
    
    # Timeline
    projection_timeline: List[ProjectionComponent] = Field(
        default_factory=list,
        description="Projection timeline",
    )


class WhatIfScenario(BaseModel):
    """What-if scenario analysis."""
    scenario_id: str = Field(..., description="Scenario ID")
    scenario_type: ScenarioType = Field(..., description="Scenario type")
    scenario_name: str = Field(..., description="Scenario name")
    description: str = Field(..., description="Scenario description")
    
    # Assumptions
    assumptions: List[str] = Field(default_factory=list, description="Assumptions")
    
    # Projected balance
    projected_balance: float = Field(..., description="Projected balance")
    
    # Difference from baseline
    difference_from_baseline: float = Field(default=0, description="Difference from baseline")
    
    # Recommendations
    recommendations: List[str] = Field(default_factory=list, description="Recommendations")


class ProjectionConfidence(BaseModel):
    """Confidence scoring for projections."""
    overall_confidence: ProjectionConfidenceLevel = Field(..., description="Overall confidence")
    confidence_score: float = Field(..., description="Confidence score 0-100")
    
    # Factors affecting confidence
    factors: List[Dict[str, Any]] = Field(default_factory=list, description="Confidence factors")
    
    # Uncertainty range
    uncertainty_low: float = Field(..., description="Lower bound")
    uncertainty_high: float = Field(..., description="Upper bound")
    
    # Notes
    confidence_notes: List[str] = Field(default_factory=list, description="Confidence notes")


class BalanceProjectionResponse(BaseModel):
    """Complete balance projection response."""
    employee_id: int = Field(..., description="Employee ID")
    employee_name: str = Field(..., description="Employee name")
    
    # Projection parameters
    projection_start_date: date = Field(..., description="Projection start date")
    projection_end_date: date = Field(..., description="Projection end date")
    
    # Policy projections
    policy_projections: List[PolicyProjection] = Field(
        ...,
        description="Projections by policy",
    )
    
    # Summary
    total_projected_balance: float = Field(..., description="Total projected balance")
    total_scheduled_accruals: float = Field(..., description="Total scheduled accruals")
    total_pending_impact: float = Field(..., description="Total pending requests impact")
    
    # Confidence
    confidence: ProjectionConfidence = Field(..., description="Confidence scoring")
    
    # What-if scenarios
    scenarios: List[WhatIfScenario] = Field(
        default_factory=list,
        description="What-if scenarios",
    )
    
    # Warnings
    warnings: List[str] = Field(default_factory=list, description="Projection warnings")
    
    # Metadata
    calculated_at: datetime = Field(default_factory=datetime.utcnow, description="Calculation time")

    class Config:
        json_encoders = {
            date: lambda v: v.isoformat(),
            datetime: lambda v: v.isoformat(),
        }


# =============================================================================
# Conflict Detection Models
# =============================================================================

class ConflictDetail(BaseModel):
    """Details of a scheduling conflict."""
    conflict_id: str = Field(..., description="Conflict ID")
    conflict_type: ConflictType = Field(..., description="Conflict type")
    severity: ConflictSeverity = Field(..., description="Conflict severity")
    
    # Dates
    conflict_start: date = Field(..., description="Conflict start date")
    conflict_end: date = Field(..., description="Conflict end date")
    overlap_days: int = Field(..., description="Number of overlapping days")
    
    # Description
    title: str = Field(..., description="Conflict title")
    description: str = Field(..., description="Detailed description")
    
    # Related entity
    related_entity_type: Optional[str] = Field(default=None, description="Related entity type")
    related_entity_id: Optional[int] = Field(default=None, description="Related entity ID")
    related_entity_name: Optional[str] = Field(default=None, description="Related entity name")
    
    # Impact
    impact_level: str = Field(..., description="Impact level")
    impact_description: Optional[str] = Field(default=None, description="Impact description")
    
    # Resolution
    can_override: bool = Field(default=False, description="Can be overridden")
    requires_approval: bool = Field(default=False, description="Requires approval")
    resolution_options: List[str] = Field(default_factory=list, description="Resolution options")


class TeamCoverageInfo(BaseModel):
    """Team coverage information."""
    team_id: int = Field(..., description="Team ID")
    team_name: str = Field(..., description="Team name")
    
    # Coverage metrics
    total_team_members: int = Field(..., description="Total team members")
    members_available: int = Field(..., description="Members available")
    members_on_leave: int = Field(..., description="Members on leave")
    members_pending_leave: int = Field(..., description="Members with pending leave")
    
    # Coverage status
    coverage_percentage: float = Field(..., description="Coverage percentage")
    minimum_coverage_required: float = Field(..., description="Minimum coverage required")
    meets_coverage_requirement: bool = Field(..., description="Meets requirement")
    
    # Risk
    coverage_risk_level: str = Field(..., description="Risk level")


class ConcurrentRequestInfo(BaseModel):
    """Information about concurrent requests."""
    request_id: int = Field(..., description="Request ID")
    employee_id: int = Field(..., description="Employee ID")
    employee_name: str = Field(..., description="Employee name")
    start_date: date = Field(..., description="Start date")
    end_date: date = Field(..., description="End date")
    status: str = Field(..., description="Request status")
    overlap_days: int = Field(..., description="Overlap days with proposed request")


class ResolutionRecommendation(BaseModel):
    """Resolution recommendation for conflicts."""
    recommendation_id: str = Field(..., description="Recommendation ID")
    priority: int = Field(..., description="Priority (1 = highest)")
    action: str = Field(..., description="Recommended action")
    description: str = Field(..., description="Action description")
    estimated_resolution_effort: str = Field(..., description="Effort level")
    alternative_dates: Optional[Dict[str, date]] = Field(
        default=None,
        description="Alternative dates suggestion",
    )


class PolicyGuidance(BaseModel):
    """Policy-specific guidance."""
    policy_id: int = Field(..., description="Policy ID")
    policy_name: str = Field(..., description="Policy name")
    guidance_type: str = Field(..., description="Guidance type")
    guidance_text: str = Field(..., description="Guidance text")
    reference_link: Optional[str] = Field(default=None, description="Policy reference link")


class ConflictDetectionResponse(BaseModel):
    """Complete conflict detection response."""
    employee_id: int = Field(..., description="Employee ID")
    employee_name: str = Field(..., description="Employee name")
    
    # Request parameters
    proposed_start_date: date = Field(..., description="Proposed start date")
    proposed_end_date: date = Field(..., description="Proposed end date")
    days_requested: float = Field(..., description="Days requested")
    
    # Conflict summary
    has_conflicts: bool = Field(..., description="Has conflicts")
    total_conflicts: int = Field(..., description="Total conflicts")
    blocking_conflicts: int = Field(default=0, description="Blocking conflicts")
    high_severity_conflicts: int = Field(default=0, description="High severity conflicts")
    
    # Conflict details
    conflicts: List[ConflictDetail] = Field(..., description="Conflict details")
    
    # Team coverage
    team_coverage: Optional[TeamCoverageInfo] = Field(
        default=None,
        description="Team coverage analysis",
    )
    
    # Concurrent requests
    concurrent_requests: List[ConcurrentRequestInfo] = Field(
        default_factory=list,
        description="Concurrent requests in department",
    )
    
    # Recommendations
    resolution_recommendations: List[ResolutionRecommendation] = Field(
        default_factory=list,
        description="Resolution recommendations",
    )
    
    # Policy guidance
    policy_guidance: List[PolicyGuidance] = Field(
        default_factory=list,
        description="Policy-specific guidance",
    )
    
    # Overall assessment
    can_proceed: bool = Field(..., description="Can proceed with request")
    proceed_recommendation: str = Field(..., description="Recommendation")
    overall_risk_level: str = Field(..., description="Overall risk level")
    
    # Metadata
    analyzed_at: datetime = Field(default_factory=datetime.utcnow, description="Analysis time")

    class Config:
        json_encoders = {
            date: lambda v: v.isoformat(),
            datetime: lambda v: v.isoformat(),
        }


