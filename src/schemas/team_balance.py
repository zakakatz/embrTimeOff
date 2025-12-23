"""Pydantic models for team and department balance API endpoints."""

from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from src.schemas.balance_inquiry import BalanceStatusEnum, PolicyInfo


# =============================================================================
# Enums
# =============================================================================

class CoverageRiskLevel(str, Enum):
    """Risk level for team coverage."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class UsageTrend(str, Enum):
    """Usage trend indicators."""
    INCREASING = "increasing"
    STABLE = "stable"
    DECREASING = "decreasing"


class SortField(str, Enum):
    """Available fields for sorting team balances."""
    EMPLOYEE_NAME = "employee_name"
    AVAILABLE_BALANCE = "available_balance"
    PENDING_REQUESTS = "pending_requests"
    BALANCE_STATUS = "balance_status"


class SortOrder(str, Enum):
    """Sort order options."""
    ASC = "asc"
    DESC = "desc"


# =============================================================================
# Team Balance Models
# =============================================================================

class TeamMemberBalance(BaseModel):
    """Balance information for a team member."""
    employee_id: int = Field(..., description="Employee ID")
    employee_name: str = Field(..., description="Employee name")
    job_title: Optional[str] = Field(default=None, description="Job title")
    department: Optional[str] = Field(default=None, description="Department name")
    
    # Balance summary
    total_available: float = Field(..., description="Total available balance across all policies")
    total_pending: float = Field(default=0, description="Total pending requests")
    total_used_ytd: float = Field(default=0, description="Total used year-to-date")
    
    # Policy balances
    policy_balances: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Balance breakdown by policy",
    )
    
    # Status
    balance_status: BalanceStatusEnum = Field(..., description="Overall balance status")
    status_message: Optional[str] = Field(default=None, description="Status message")
    
    # Upcoming
    upcoming_time_off: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Upcoming approved time off",
    )
    pending_requests: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Pending time-off requests",
    )
    
    # Accruals
    next_accrual_date: Optional[date] = Field(default=None, description="Next accrual date")
    next_accrual_amount: float = Field(default=0, description="Next accrual amount")


class TeamAvailabilityPeriod(BaseModel):
    """Team availability for a specific period."""
    start_date: date = Field(..., description="Period start date")
    end_date: date = Field(..., description="Period end date")
    total_team_members: int = Field(..., description="Total team members")
    available_members: int = Field(..., description="Available members")
    members_on_leave: int = Field(..., description="Members on approved leave")
    members_pending_leave: int = Field(..., description="Members with pending leave requests")
    availability_percentage: float = Field(..., description="Availability percentage")
    coverage_risk: CoverageRiskLevel = Field(..., description="Coverage risk level")


class CoverageRiskInfo(BaseModel):
    """Coverage risk analysis."""
    risk_level: CoverageRiskLevel = Field(..., description="Overall risk level")
    risk_score: float = Field(..., description="Risk score (0-100)")
    risk_factors: List[str] = Field(default_factory=list, description="Contributing risk factors")
    affected_dates: List[date] = Field(default_factory=list, description="Dates with coverage issues")
    recommendations: List[str] = Field(default_factory=list, description="Recommendations")


class TeamBalanceSummary(BaseModel):
    """Summary statistics for team balances."""
    total_team_members: int = Field(..., description="Total team members")
    total_available_balance: float = Field(..., description="Total available balance")
    average_available_balance: float = Field(..., description="Average available balance per member")
    total_pending_requests: float = Field(..., description="Total pending days")
    pending_request_count: int = Field(..., description="Number of pending requests")
    
    # Status breakdown
    members_with_healthy_balance: int = Field(default=0, description="Members with healthy balance")
    members_with_low_balance: int = Field(default=0, description="Members with low balance")
    members_with_critical_balance: int = Field(default=0, description="Members with critical balance")
    
    # Upcoming accruals
    total_upcoming_accruals: float = Field(default=0, description="Total upcoming accruals")
    members_with_upcoming_accruals: int = Field(default=0, description="Members with upcoming accruals")


class TeamBalanceResponse(BaseModel):
    """Complete team balance response for managers."""
    manager_id: int = Field(..., description="Manager employee ID")
    manager_name: str = Field(..., description="Manager name")
    
    # Team members
    team_members: List[TeamMemberBalance] = Field(..., description="Team member balances")
    
    # Summary
    summary: TeamBalanceSummary = Field(..., description="Team summary statistics")
    
    # Coverage analysis
    coverage_analysis: List[TeamAvailabilityPeriod] = Field(
        default_factory=list,
        description="Coverage analysis for upcoming periods",
    )
    coverage_risk: CoverageRiskInfo = Field(..., description="Coverage risk assessment")
    
    # Filters applied
    filters: Dict[str, Any] = Field(default_factory=dict, description="Applied filters")
    
    # Metadata
    as_of_date: date = Field(..., description="Data as of date")
    retrieved_at: datetime = Field(default_factory=datetime.utcnow, description="Retrieval timestamp")

    class Config:
        json_encoders = {
            date: lambda v: v.isoformat(),
            datetime: lambda v: v.isoformat(),
        }


# =============================================================================
# Department Balance Models
# =============================================================================

class PolicyUsageMetric(BaseModel):
    """Usage metrics for a specific policy."""
    policy_id: int = Field(..., description="Policy ID")
    policy_name: str = Field(..., description="Policy name")
    policy_code: str = Field(..., description="Policy code")
    
    # Usage statistics
    total_allocated: float = Field(..., description="Total allocated across employees")
    total_used: float = Field(..., description="Total used")
    total_available: float = Field(..., description="Total available")
    total_pending: float = Field(..., description="Total pending")
    
    # Rates
    utilization_rate: float = Field(..., description="Utilization rate percentage")
    accrual_utilization_rate: float = Field(..., description="Accrual utilization rate")
    
    # Employees
    employees_enrolled: int = Field(..., description="Employees enrolled in policy")
    employees_used: int = Field(..., description="Employees who have used balance")
    
    # Effectiveness
    effectiveness_score: Optional[float] = Field(default=None, description="Policy effectiveness score")


class BalanceDistribution(BaseModel):
    """Balance distribution statistics."""
    min_balance: float = Field(..., description="Minimum balance")
    max_balance: float = Field(..., description="Maximum balance")
    mean_balance: float = Field(..., description="Mean balance")
    median_balance: float = Field(..., description="Median balance")
    std_deviation: float = Field(..., description="Standard deviation")
    
    # Percentiles
    percentile_25: float = Field(..., description="25th percentile")
    percentile_75: float = Field(..., description="75th percentile")
    percentile_90: float = Field(..., description="90th percentile")
    
    # Distribution buckets
    distribution_buckets: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Balance distribution by range",
    )


class UsagePattern(BaseModel):
    """Usage pattern analysis."""
    period: str = Field(..., description="Period identifier (e.g., 'Q1', 'January')")
    total_requests: int = Field(..., description="Total requests in period")
    total_days_requested: float = Field(..., description="Total days requested")
    average_request_length: float = Field(..., description="Average request length")
    peak_usage_dates: List[date] = Field(default_factory=list, description="Peak usage dates")
    trend: UsageTrend = Field(..., description="Usage trend")


class DepartmentBalanceSummary(BaseModel):
    """Summary statistics for department balances."""
    total_employees: int = Field(..., description="Total employees in department")
    total_available_balance: float = Field(..., description="Total available balance")
    average_available_balance: float = Field(..., description="Average available balance")
    total_pending_days: float = Field(..., description="Total pending days")
    total_used_ytd: float = Field(..., description="Total used year-to-date")
    
    # Status breakdown
    employees_healthy_balance: int = Field(default=0, description="Employees with healthy balance")
    employees_low_balance: int = Field(default=0, description="Employees with low balance")
    employees_critical_balance: int = Field(default=0, description="Employees with critical balance")
    
    # Accruals
    total_upcoming_accruals: float = Field(default=0, description="Total upcoming accruals")
    average_accrual_utilization: float = Field(default=0, description="Average accrual utilization rate")


class TrendDataPoint(BaseModel):
    """Data point for trend analysis."""
    period: str = Field(..., description="Period label")
    date: date = Field(..., description="Period date")
    value: float = Field(..., description="Metric value")
    change_from_previous: Optional[float] = Field(default=None, description="Change from previous period")


class TrendAnalysis(BaseModel):
    """Trend analysis for department balances."""
    metric_name: str = Field(..., description="Metric being analyzed")
    trend_direction: UsageTrend = Field(..., description="Overall trend direction")
    data_points: List[TrendDataPoint] = Field(..., description="Trend data points")
    forecast_next_period: Optional[float] = Field(default=None, description="Forecast for next period")
    year_over_year_change: Optional[float] = Field(default=None, description="Year-over-year change")


class ComparativeMetric(BaseModel):
    """Comparative metric against benchmarks."""
    metric_name: str = Field(..., description="Metric name")
    department_value: float = Field(..., description="Department value")
    company_average: Optional[float] = Field(default=None, description="Company average")
    industry_benchmark: Optional[float] = Field(default=None, description="Industry benchmark")
    variance_from_average: Optional[float] = Field(default=None, description="Variance from company average")
    performance_indicator: str = Field(..., description="Performance indicator (above/at/below)")


class DepartmentBalanceResponse(BaseModel):
    """Complete department balance analytics response."""
    department_id: int = Field(..., description="Department ID")
    department_name: str = Field(..., description="Department name")
    department_code: Optional[str] = Field(default=None, description="Department code")
    
    # Summary
    summary: DepartmentBalanceSummary = Field(..., description="Department summary")
    
    # Policy metrics
    policy_metrics: List[PolicyUsageMetric] = Field(
        default_factory=list,
        description="Usage metrics by policy",
    )
    
    # Distribution
    balance_distribution: BalanceDistribution = Field(..., description="Balance distribution")
    
    # Usage patterns
    usage_patterns: List[UsagePattern] = Field(
        default_factory=list,
        description="Usage patterns by period",
    )
    
    # Trends
    trends: List[TrendAnalysis] = Field(
        default_factory=list,
        description="Trend analysis",
    )
    
    # Comparative metrics
    comparative_metrics: List[ComparativeMetric] = Field(
        default_factory=list,
        description="Comparative metrics",
    )
    
    # Sub-departments (if hierarchical)
    sub_department_summaries: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Sub-department summaries",
    )
    
    # Metadata
    year: int = Field(..., description="Data year")
    as_of_date: date = Field(..., description="Data as of date")
    retrieved_at: datetime = Field(default_factory=datetime.utcnow, description="Retrieval timestamp")

    class Config:
        json_encoders = {
            date: lambda v: v.isoformat(),
            datetime: lambda v: v.isoformat(),
        }


# =============================================================================
# Query Parameter Models
# =============================================================================

class TeamBalanceQueryParams(BaseModel):
    """Query parameters for team balance endpoint."""
    policy_id: Optional[int] = Field(default=None, description="Filter by policy ID")
    balance_status: Optional[BalanceStatusEnum] = Field(default=None, description="Filter by status")
    has_pending_requests: Optional[bool] = Field(default=None, description="Filter by pending requests")
    min_available_balance: Optional[float] = Field(default=None, description="Minimum available balance")
    max_available_balance: Optional[float] = Field(default=None, description="Maximum available balance")
    coverage_analysis_days: int = Field(default=30, description="Days to analyze for coverage")
    sort_by: SortField = Field(default=SortField.EMPLOYEE_NAME, description="Sort field")
    sort_order: SortOrder = Field(default=SortOrder.ASC, description="Sort order")
    include_upcoming_accruals: bool = Field(default=True, description="Include accrual info")


class DepartmentBalanceQueryParams(BaseModel):
    """Query parameters for department balance endpoint."""
    year: Optional[int] = Field(default=None, description="Year for data")
    include_sub_departments: bool = Field(default=False, description="Include sub-departments")
    policy_ids: Optional[List[int]] = Field(default=None, description="Filter by policy IDs")
    include_trends: bool = Field(default=True, description="Include trend analysis")
    include_comparisons: bool = Field(default=True, description="Include comparative metrics")
    usage_pattern_granularity: str = Field(default="monthly", description="Pattern granularity")


