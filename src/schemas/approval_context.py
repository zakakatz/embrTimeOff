"""Pydantic models for approval context API."""

from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ConflictTypeEnum(str, Enum):
    """Types of scheduling conflicts."""
    OVERLAP = "overlap"
    ADJACENT = "adjacent"
    SAME_FUNCTION = "same_function"
    CRITICAL_COVERAGE = "critical_coverage"


class ImpactLevelEnum(str, Enum):
    """Impact level for conflicts."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CoverageStatusEnum(str, Enum):
    """Team coverage status."""
    ADEQUATE = "adequate"
    MARGINAL = "marginal"
    INSUFFICIENT = "insufficient"
    CRITICAL = "critical"


class PolicyComplianceEnum(str, Enum):
    """Policy compliance status."""
    COMPLIANT = "compliant"
    WARNING = "warning"
    VIOLATION = "violation"
    EXCEPTION_REQUIRED = "exception_required"


# =============================================================================
# Team Member Models
# =============================================================================

class TeamMemberInfo(BaseModel):
    """Information about a team member."""
    id: int = Field(..., description="Employee ID")
    employee_id: str = Field(..., description="Employee code")
    name: str = Field(..., description="Full name")
    job_title: Optional[str] = Field(default=None, description="Job title")
    is_critical_function: bool = Field(default=False, description="Has critical function")
    functions: List[str] = Field(default_factory=list, description="Job functions covered")


class TeamMemberAvailability(BaseModel):
    """Availability information for a team member."""
    employee: TeamMemberInfo = Field(..., description="Employee info")
    dates_available: List[date] = Field(..., description="Available dates")
    dates_unavailable: List[date] = Field(..., description="Unavailable dates")
    unavailable_reason: Optional[str] = Field(default=None, description="Reason for unavailability")
    approved_requests: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Approved time-off requests",
    )
    pending_requests: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Pending time-off requests",
    )


# =============================================================================
# Conflict Models
# =============================================================================

class ConflictDetail(BaseModel):
    """Detailed conflict information."""
    conflict_id: str = Field(..., description="Unique conflict identifier")
    conflict_type: ConflictTypeEnum = Field(..., description="Type of conflict")
    conflicting_employee: TeamMemberInfo = Field(..., description="Employee with conflict")
    overlap_dates: List[date] = Field(..., description="Dates of overlap")
    total_overlap_days: int = Field(..., description="Number of overlapping days")
    impact_level: ImpactLevelEnum = Field(..., description="Impact severity")
    impact_description: str = Field(..., description="Description of impact")
    resolution_options: List[str] = Field(default_factory=list, description="Possible resolutions")


class ConflictSummary(BaseModel):
    """Summary of all conflicts."""
    total_conflicts: int = Field(default=0, description="Total number of conflicts")
    critical_conflicts: int = Field(default=0, description="Number of critical conflicts")
    high_conflicts: int = Field(default=0, description="Number of high-impact conflicts")
    conflicts_by_type: Dict[str, int] = Field(default_factory=dict, description="Conflicts by type")
    overall_impact: ImpactLevelEnum = Field(default=ImpactLevelEnum.LOW, description="Overall impact")
    recommendation: str = Field(default="", description="Recommendation based on conflicts")


# =============================================================================
# Coverage Models
# =============================================================================

class DailyCoverage(BaseModel):
    """Coverage information for a specific day."""
    date: date = Field(..., description="Date")
    is_workday: bool = Field(default=True, description="Is a workday")
    total_team_size: int = Field(..., description="Total team members")
    available_count: int = Field(..., description="Available team members")
    minimum_required: int = Field(..., description="Minimum staff required")
    coverage_status: CoverageStatusEnum = Field(..., description="Coverage status")
    critical_functions_covered: bool = Field(default=True, description="Critical functions covered")
    absent_employees: List[str] = Field(default_factory=list, description="Absent employee names")


class CoverageAnalysis(BaseModel):
    """Comprehensive coverage analysis."""
    analysis_period_start: date = Field(..., description="Analysis start date")
    analysis_period_end: date = Field(..., description="Analysis end date")
    daily_coverage: List[DailyCoverage] = Field(..., description="Daily breakdown")
    overall_status: CoverageStatusEnum = Field(..., description="Overall coverage status")
    days_below_minimum: int = Field(default=0, description="Days below minimum staffing")
    critical_days: List[date] = Field(default_factory=list, description="Critical coverage days")
    warnings: List[str] = Field(default_factory=list, description="Coverage warnings")
    impact_assessment: str = Field(default="", description="Impact assessment")


# =============================================================================
# Policy Models
# =============================================================================

class PolicyCheck(BaseModel):
    """Result of a policy check."""
    policy_id: str = Field(..., description="Policy identifier")
    policy_name: str = Field(..., description="Policy name")
    rule_description: str = Field(..., description="Rule being checked")
    compliance_status: PolicyComplianceEnum = Field(..., description="Compliance status")
    details: Optional[str] = Field(default=None, description="Additional details")
    required_action: Optional[str] = Field(default=None, description="Required action if any")


class BalanceProjection(BaseModel):
    """Balance projection after approval."""
    balance_type: str = Field(..., description="Type of balance")
    current_balance: float = Field(..., description="Current balance")
    requested_amount: float = Field(..., description="Amount requested")
    projected_balance: float = Field(..., description="Balance after approval")
    projected_year_end_balance: float = Field(..., description="Projected year-end balance")
    accruals_remaining: float = Field(default=0, description="Remaining accruals this year")
    is_sufficient: bool = Field(default=True, description="Balance is sufficient")


class PolicyAnalysis(BaseModel):
    """Comprehensive policy analysis."""
    policy_checks: List[PolicyCheck] = Field(..., description="Individual policy checks")
    balance_projection: BalanceProjection = Field(..., description="Balance projection")
    overall_compliance: PolicyComplianceEnum = Field(..., description="Overall compliance")
    blocking_issues: List[str] = Field(default_factory=list, description="Issues blocking approval")
    warnings: List[str] = Field(default_factory=list, description="Policy warnings")
    exceptions_required: List[str] = Field(default_factory=list, description="Exceptions needed")


# =============================================================================
# Historical Pattern Models
# =============================================================================

class HistoricalPattern(BaseModel):
    """Historical patterns for decision support."""
    pattern_type: str = Field(..., description="Type of pattern")
    description: str = Field(..., description="Pattern description")
    frequency: str = Field(..., description="How often this occurs")
    relevance: str = Field(default="informational", description="Relevance to decision")


# =============================================================================
# Organizational Event Models
# =============================================================================

class OrganizationalEvent(BaseModel):
    """Organizational event that may conflict."""
    event_id: str = Field(..., description="Event ID")
    event_name: str = Field(..., description="Event name")
    event_type: str = Field(..., description="Event type")
    start_date: date = Field(..., description="Start date")
    end_date: date = Field(..., description="End date")
    is_mandatory: bool = Field(default=False, description="Mandatory attendance")
    overlap_days: List[date] = Field(default_factory=list, description="Overlapping days")
    impact: str = Field(default="low", description="Impact of overlap")


# =============================================================================
# Context Response Models
# =============================================================================

class ApprovalContextResponse(BaseModel):
    """Comprehensive contextual information for approval decision."""
    request_id: int = Field(..., description="Request ID")
    
    # Employee information
    employee_id: int = Field(..., description="Requesting employee ID")
    employee_name: str = Field(..., description="Requesting employee name")
    
    # Request details
    request_type: str = Field(..., description="Type of time-off")
    start_date: date = Field(..., description="Start date")
    end_date: date = Field(..., description="End date")
    total_days: float = Field(..., description="Total days requested")
    
    # Conflict information
    conflicts: List[ConflictDetail] = Field(default_factory=list, description="Detailed conflicts")
    conflict_summary: ConflictSummary = Field(..., description="Conflict summary")
    
    # Coverage analysis
    coverage_analysis: CoverageAnalysis = Field(..., description="Coverage analysis")
    
    # Policy analysis
    policy_analysis: PolicyAnalysis = Field(..., description="Policy analysis")
    
    # Historical patterns
    historical_patterns: List[HistoricalPattern] = Field(
        default_factory=list,
        description="Historical patterns",
    )
    
    # Organizational events
    organizational_events: List[OrganizationalEvent] = Field(
        default_factory=list,
        description="Relevant organizational events",
    )
    
    # Decision support
    approval_recommendation: str = Field(
        default="review_required",
        description="Recommendation: approve, deny, review_required",
    )
    key_considerations: List[str] = Field(
        default_factory=list,
        description="Key points to consider",
    )
    
    # Metadata
    generated_at: datetime = Field(default_factory=datetime.utcnow, description="Generation timestamp")
    data_sources: List[str] = Field(default_factory=list, description="Data sources used")

    class Config:
        json_encoders = {
            date: lambda v: v.isoformat(),
            datetime: lambda v: v.isoformat(),
        }


# =============================================================================
# Team Calendar Models
# =============================================================================

class CalendarEntry(BaseModel):
    """Calendar entry for team view."""
    id: str = Field(..., description="Entry ID")
    employee_id: int = Field(..., description="Employee ID")
    employee_name: str = Field(..., description="Employee name")
    entry_type: str = Field(..., description="Type: approved, pending, holiday")
    start_date: date = Field(..., description="Start date")
    end_date: date = Field(..., description="End date")
    request_type: Optional[str] = Field(default=None, description="Time-off type if applicable")
    status: str = Field(..., description="Status")
    has_conflict: bool = Field(default=False, description="Has scheduling conflict")
    conflict_with: List[str] = Field(default_factory=list, description="Conflicting entries")


class TeamCalendarResponse(BaseModel):
    """Team calendar with conflicts and coverage."""
    manager_id: int = Field(..., description="Manager ID")
    team_name: str = Field(..., description="Team name")
    
    # Date range
    start_date: date = Field(..., description="Calendar start date")
    end_date: date = Field(..., description="Calendar end date")
    
    # Team members
    team_members: List[TeamMemberAvailability] = Field(..., description="Team member availability")
    
    # Calendar entries
    approved_entries: List[CalendarEntry] = Field(..., description="Approved time-off")
    pending_entries: List[CalendarEntry] = Field(..., description="Pending requests")
    
    # Conflicts
    conflicts: List[Dict[str, Any]] = Field(default_factory=list, description="Identified conflicts")
    
    # Coverage summary
    coverage_by_date: Dict[str, DailyCoverage] = Field(
        default_factory=dict,
        description="Coverage by date (ISO format key)",
    )
    
    # Summary statistics
    summary: Dict[str, Any] = Field(default_factory=dict, description="Calendar summary")
    
    # Organizational events
    organizational_events: List[OrganizationalEvent] = Field(
        default_factory=list,
        description="Organizational events in period",
    )

    class Config:
        json_encoders = {
            date: lambda v: v.isoformat(),
            datetime: lambda v: v.isoformat(),
        }

