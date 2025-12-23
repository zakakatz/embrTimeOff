"""Pydantic models for sick leave schedule integration API endpoints."""

from datetime import date, datetime, time
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, validator


# =============================================================================
# Enums
# =============================================================================

class TimeUnitPreference(str, Enum):
    """Preferred time unit for sick leave."""
    HOURS = "hours"
    DAYS = "days"
    AUTO = "auto"


class ConflictType(str, Enum):
    """Type of scheduling conflict."""
    EXISTING_REQUEST = "existing_request"
    COMPANY_HOLIDAY = "company_holiday"
    BLACKOUT_PERIOD = "blackout_period"
    TEAM_COVERAGE = "team_coverage"
    REGULATORY_LIMIT = "regulatory_limit"


class ConflictSeverity(str, Enum):
    """Severity of a scheduling conflict."""
    BLOCKING = "blocking"
    WARNING = "warning"
    INFO = "info"


class PolicyComplianceStatus(str, Enum):
    """Status of policy compliance."""
    COMPLIANT = "compliant"
    REQUIRES_ADJUSTMENT = "requires_adjustment"
    NON_COMPLIANT = "non_compliant"


class WorkScheduleType(str, Enum):
    """Type of work schedule."""
    STANDARD = "standard"
    FLEXIBLE = "flexible"
    COMPRESSED = "compressed"
    PART_TIME = "part_time"
    SHIFT = "shift"


# =============================================================================
# Request Models
# =============================================================================

class DurationCalculationRequest(BaseModel):
    """Request model for sick leave duration calculation."""
    employee_id: int = Field(..., description="Employee ID")
    start_date: date = Field(..., description="Start date of sick leave")
    end_date: date = Field(..., description="End date of sick leave")
    start_time: Optional[time] = Field(default=None, description="Start time for partial day")
    end_time: Optional[time] = Field(default=None, description="End time for partial day")
    preferred_unit: TimeUnitPreference = Field(
        default=TimeUnitPreference.AUTO,
        description="Preferred time unit",
    )
    include_schedule_details: bool = Field(
        default=True,
        description="Include detailed schedule breakdown",
    )

    @validator("end_date")
    def end_date_after_start(cls, v, values):
        if "start_date" in values and v < values["start_date"]:
            raise ValueError("end_date must be on or after start_date")
        return v


class ConflictDetectionRequest(BaseModel):
    """Request model for conflict detection."""
    employee_id: int = Field(..., description="Employee ID")
    start_date: date = Field(..., description="Proposed start date")
    end_date: date = Field(..., description="Proposed end date")
    start_time: Optional[time] = Field(default=None, description="Start time")
    end_time: Optional[time] = Field(default=None, description="End time")
    request_type: str = Field(default="sick_leave", description="Request type")
    include_alternatives: bool = Field(
        default=True,
        description="Include alternative scheduling suggestions",
    )
    include_impact_analysis: bool = Field(
        default=True,
        description="Include impact analysis",
    )


# =============================================================================
# Schedule and Duration Models
# =============================================================================

class WorkScheduleInfo(BaseModel):
    """Employee work schedule information."""
    schedule_type: WorkScheduleType = Field(..., description="Type of schedule")
    standard_hours_per_day: float = Field(..., description="Standard hours per day")
    standard_hours_per_week: float = Field(..., description="Standard hours per week")
    work_days: List[str] = Field(..., description="Work days (e.g., ['Monday', 'Tuesday', ...])")
    start_time: Optional[time] = Field(default=None, description="Standard start time")
    end_time: Optional[time] = Field(default=None, description="Standard end time")
    has_flexible_hours: bool = Field(default=False, description="Has flexible hours")
    location_timezone: str = Field(default="UTC", description="Location timezone")


class DayBreakdown(BaseModel):
    """Breakdown of a single day's time allocation."""
    date: date = Field(..., description="Date")
    day_of_week: str = Field(..., description="Day of week")
    is_work_day: bool = Field(..., description="Is a scheduled work day")
    is_holiday: bool = Field(default=False, description="Is a company holiday")
    is_blackout: bool = Field(default=False, description="Is in blackout period")
    scheduled_hours: float = Field(..., description="Scheduled work hours")
    sick_leave_hours: float = Field(..., description="Sick leave hours for this day")
    sick_leave_days: float = Field(..., description="Sick leave days (fraction)")
    notes: Optional[str] = Field(default=None, description="Notes")


class TimeAllocationRecommendation(BaseModel):
    """Recommendation for time allocation."""
    recommended_unit: TimeUnitPreference = Field(..., description="Recommended unit")
    reason: str = Field(..., description="Reason for recommendation")
    hours_value: float = Field(..., description="Equivalent hours")
    days_value: float = Field(..., description="Equivalent days")
    is_policy_compliant: bool = Field(..., description="Is compliant with policy")


class PolicyComplianceInfo(BaseModel):
    """Policy compliance information."""
    status: PolicyComplianceStatus = Field(..., description="Compliance status")
    policy_name: str = Field(..., description="Applicable policy name")
    policy_id: int = Field(..., description="Policy ID")
    min_increment_hours: Optional[float] = Field(default=None, description="Minimum increment")
    max_consecutive_days: Optional[int] = Field(default=None, description="Max consecutive days")
    requires_documentation_days: Optional[int] = Field(
        default=None,
        description="Days after which documentation required",
    )
    issues: List[str] = Field(default_factory=list, description="Compliance issues")
    suggestions: List[str] = Field(default_factory=list, description="Compliance suggestions")


class DurationCalculationResponse(BaseModel):
    """Response model for duration calculation."""
    # Request info
    employee_id: int = Field(..., description="Employee ID")
    employee_name: str = Field(..., description="Employee name")
    start_date: date = Field(..., description="Start date")
    end_date: date = Field(..., description="End date")
    
    # Schedule info
    work_schedule: WorkScheduleInfo = Field(..., description="Work schedule info")
    
    # Calculated duration
    total_hours: float = Field(..., description="Total hours")
    total_days: float = Field(..., description="Total days")
    work_days_count: int = Field(..., description="Number of work days")
    calendar_days_count: int = Field(..., description="Number of calendar days")
    
    # Breakdown
    day_breakdown: List[DayBreakdown] = Field(
        default_factory=list,
        description="Daily breakdown",
    )
    
    # Recommendations
    allocation_recommendation: TimeAllocationRecommendation = Field(
        ...,
        description="Time allocation recommendation",
    )
    
    # Policy compliance
    policy_compliance: PolicyComplianceInfo = Field(..., description="Policy compliance info")
    
    # Regulatory notes
    regulatory_notes: List[str] = Field(
        default_factory=list,
        description="Regulatory considerations",
    )
    
    # Metadata
    calculated_at: datetime = Field(default_factory=datetime.utcnow, description="Calculation time")

    class Config:
        json_encoders = {
            date: lambda v: v.isoformat(),
            datetime: lambda v: v.isoformat(),
            time: lambda v: v.isoformat(),
        }


# =============================================================================
# Conflict Models
# =============================================================================

class ConflictDetail(BaseModel):
    """Details of a single conflict."""
    conflict_id: str = Field(..., description="Unique conflict ID")
    conflict_type: ConflictType = Field(..., description="Type of conflict")
    severity: ConflictSeverity = Field(..., description="Conflict severity")
    
    # Affected dates
    affected_start_date: date = Field(..., description="Start of conflict period")
    affected_end_date: date = Field(..., description="End of conflict period")
    overlap_days: int = Field(..., description="Number of overlapping days")
    
    # Related entity
    related_entity_id: Optional[int] = Field(default=None, description="Related entity ID")
    related_entity_name: Optional[str] = Field(default=None, description="Related entity name")
    
    # Description
    description: str = Field(..., description="Conflict description")
    impact_description: Optional[str] = Field(default=None, description="Impact description")
    
    # Resolution
    can_override: bool = Field(default=False, description="Can be overridden")
    resolution_suggestions: List[str] = Field(
        default_factory=list,
        description="Resolution suggestions",
    )


class AlternativeSchedule(BaseModel):
    """Alternative scheduling suggestion."""
    alternative_id: str = Field(..., description="Alternative ID")
    start_date: date = Field(..., description="Alternative start date")
    end_date: date = Field(..., description="Alternative end date")
    
    # Duration
    total_days: float = Field(..., description="Total days")
    total_hours: float = Field(..., description="Total hours")
    
    # Conflicts resolved
    conflicts_avoided: int = Field(..., description="Number of conflicts avoided")
    
    # Trade-offs
    trade_offs: List[str] = Field(default_factory=list, description="Trade-offs")
    
    # Score
    suitability_score: float = Field(..., description="Suitability score 0-100")
    recommendation_reason: str = Field(..., description="Recommendation reason")


class ImpactAnalysis(BaseModel):
    """Impact analysis for the proposed request."""
    # Team impact
    team_coverage_impact: str = Field(..., description="Impact on team coverage")
    affected_team_members: int = Field(default=0, description="Number of affected team members")
    
    # Workload impact
    workload_redistribution_required: bool = Field(
        default=False,
        description="Needs workload redistribution",
    )
    estimated_redistribution_hours: float = Field(
        default=0,
        description="Estimated hours to redistribute",
    )
    
    # Project impact
    project_deadlines_affected: int = Field(
        default=0,
        description="Number of project deadlines affected",
    )
    
    # Overall assessment
    overall_impact_level: str = Field(..., description="Overall impact: low, medium, high")
    impact_summary: str = Field(..., description="Summary of impact")


class ConflictDetectionResponse(BaseModel):
    """Response model for conflict detection."""
    # Request info
    employee_id: int = Field(..., description="Employee ID")
    employee_name: str = Field(..., description="Employee name")
    proposed_start_date: date = Field(..., description="Proposed start date")
    proposed_end_date: date = Field(..., description="Proposed end date")
    
    # Conflict summary
    has_conflicts: bool = Field(..., description="Has any conflicts")
    total_conflicts: int = Field(..., description="Total conflict count")
    blocking_conflicts: int = Field(default=0, description="Blocking conflicts count")
    warning_conflicts: int = Field(default=0, description="Warning conflicts count")
    info_conflicts: int = Field(default=0, description="Info conflicts count")
    
    # Conflict details
    conflicts: List[ConflictDetail] = Field(..., description="Conflict details")
    
    # Alternative suggestions
    alternatives: List[AlternativeSchedule] = Field(
        default_factory=list,
        description="Alternative scheduling suggestions",
    )
    
    # Impact analysis
    impact_analysis: Optional[ImpactAnalysis] = Field(
        default=None,
        description="Impact analysis",
    )
    
    # Policy notes
    policy_considerations: List[str] = Field(
        default_factory=list,
        description="Policy considerations",
    )
    
    # Recommendation
    can_proceed: bool = Field(..., description="Can proceed with request")
    proceed_recommendation: str = Field(..., description="Recommendation for proceeding")
    
    # Metadata
    analyzed_at: datetime = Field(default_factory=datetime.utcnow, description="Analysis time")

    class Config:
        json_encoders = {
            date: lambda v: v.isoformat(),
            datetime: lambda v: v.isoformat(),
            time: lambda v: v.isoformat(),
        }


