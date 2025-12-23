"""Pydantic models for approval analytics and monitoring API endpoints."""

from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# =============================================================================
# Enums
# =============================================================================

class TrendDirection(str, Enum):
    """Direction of a trend."""
    UP = "up"
    DOWN = "down"
    STABLE = "stable"


class OverdueSeverity(str, Enum):
    """Severity level for overdue items."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EscalationStatus(str, Enum):
    """Escalation status for overdue items."""
    NOT_ESCALATED = "not_escalated"
    PENDING_ESCALATION = "pending_escalation"
    ESCALATED = "escalated"
    AUTO_ESCALATED = "auto_escalated"


class ImpactLevel(str, Enum):
    """Impact level for approval decisions."""
    MINIMAL = "minimal"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


# =============================================================================
# Analytics Models
# =============================================================================

class ApprovalRateMetric(BaseModel):
    """Approval rate metrics."""
    total_requests: int = Field(..., description="Total requests processed")
    approved_count: int = Field(..., description="Number approved")
    denied_count: int = Field(..., description="Number denied")
    cancelled_count: int = Field(default=0, description="Number cancelled")
    approval_rate: float = Field(..., description="Approval rate percentage")
    denial_rate: float = Field(..., description="Denial rate percentage")
    
    # Comparison
    previous_period_rate: Optional[float] = Field(default=None, description="Previous period rate")
    rate_change: Optional[float] = Field(default=None, description="Rate change from previous")
    trend: TrendDirection = Field(default=TrendDirection.STABLE, description="Trend direction")


class TimelineMetric(BaseModel):
    """Decision timeline metrics."""
    average_hours_to_decision: float = Field(..., description="Average hours to decision")
    median_hours_to_decision: float = Field(..., description="Median hours to decision")
    min_hours_to_decision: float = Field(..., description="Minimum hours")
    max_hours_to_decision: float = Field(..., description="Maximum hours")
    percentile_90: float = Field(..., description="90th percentile hours")
    
    # SLA compliance
    sla_target_hours: Optional[float] = Field(default=None, description="SLA target hours")
    sla_compliance_rate: Optional[float] = Field(default=None, description="SLA compliance rate")
    requests_within_sla: int = Field(default=0, description="Requests within SLA")
    requests_over_sla: int = Field(default=0, description="Requests over SLA")


class PatternDataPoint(BaseModel):
    """Data point for pattern analysis."""
    label: str = Field(..., description="Period label")
    date: Optional[date] = Field(default=None, description="Date")
    count: int = Field(..., description="Request count")
    approved: int = Field(default=0, description="Approved count")
    denied: int = Field(default=0, description="Denied count")
    pending: int = Field(default=0, description="Pending count")
    average_time_to_decision: Optional[float] = Field(default=None, description="Avg time hours")


class PatternAnalysis(BaseModel):
    """Pattern analysis for approvals."""
    pattern_type: str = Field(..., description="Pattern type: daily, weekly, monthly")
    data_points: List[PatternDataPoint] = Field(..., description="Pattern data points")
    peak_period: Optional[str] = Field(default=None, description="Peak period label")
    low_period: Optional[str] = Field(default=None, description="Low period label")
    insights: List[str] = Field(default_factory=list, description="Pattern insights")


class ManagerPerformance(BaseModel):
    """Performance metrics for a manager."""
    manager_id: int = Field(..., description="Manager employee ID")
    manager_name: str = Field(..., description="Manager name")
    department: Optional[str] = Field(default=None, description="Department")
    
    # Volume
    total_decisions: int = Field(..., description="Total decisions made")
    pending_count: int = Field(default=0, description="Currently pending")
    
    # Rates
    approval_rate: float = Field(..., description="Approval rate")
    denial_rate: float = Field(..., description="Denial rate")
    
    # Timeline
    average_decision_hours: float = Field(..., description="Average decision time")
    sla_compliance: float = Field(..., description="SLA compliance rate")
    
    # Comparison
    vs_team_average: Optional[float] = Field(default=None, description="Comparison to team avg")
    vs_company_average: Optional[float] = Field(default=None, description="Comparison to company avg")
    performance_score: Optional[float] = Field(default=None, description="Performance score 0-100")


class OrgUnitAnalytics(BaseModel):
    """Analytics for an organizational unit."""
    unit_id: int = Field(..., description="Org unit ID")
    unit_name: str = Field(..., description="Org unit name")
    unit_type: str = Field(..., description="Type: department, team, division")
    
    # Volume
    total_requests: int = Field(..., description="Total requests")
    pending_requests: int = Field(..., description="Pending requests")
    overdue_requests: int = Field(default=0, description="Overdue requests")
    
    # Rates
    approval_rate: float = Field(..., description="Approval rate")
    average_decision_hours: float = Field(..., description="Average decision time")
    sla_compliance: float = Field(..., description="SLA compliance rate")
    
    # Comparison
    vs_company_average: Optional[float] = Field(default=None, description="Comparison to company")


class ActionableInsight(BaseModel):
    """Actionable insight from analytics."""
    insight_id: str = Field(..., description="Insight identifier")
    category: str = Field(..., description="Category: performance, compliance, trend")
    severity: str = Field(..., description="Severity: info, warning, critical")
    title: str = Field(..., description="Insight title")
    description: str = Field(..., description="Detailed description")
    metric_value: Optional[float] = Field(default=None, description="Related metric value")
    recommended_action: Optional[str] = Field(default=None, description="Recommended action")
    affected_entity: Optional[str] = Field(default=None, description="Affected entity")


class ApprovalAnalyticsResponse(BaseModel):
    """Complete approval analytics response."""
    # Time range
    start_date: date = Field(..., description="Analytics start date")
    end_date: date = Field(..., description="Analytics end date")
    
    # Core metrics
    approval_rates: ApprovalRateMetric = Field(..., description="Approval rate metrics")
    timeline_metrics: TimelineMetric = Field(..., description="Timeline metrics")
    
    # Pattern analysis
    daily_patterns: Optional[PatternAnalysis] = Field(default=None, description="Daily patterns")
    weekly_patterns: Optional[PatternAnalysis] = Field(default=None, description="Weekly patterns")
    monthly_patterns: Optional[PatternAnalysis] = Field(default=None, description="Monthly patterns")
    
    # Breakdowns
    by_request_type: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Analytics by request type",
    )
    by_department: List[OrgUnitAnalytics] = Field(
        default_factory=list,
        description="Analytics by department",
    )
    
    # Comparative analysis
    manager_performance: List[ManagerPerformance] = Field(
        default_factory=list,
        description="Manager performance comparison",
    )
    
    # Insights
    insights: List[ActionableInsight] = Field(
        default_factory=list,
        description="Actionable insights",
    )
    
    # Metadata
    generated_at: datetime = Field(default_factory=datetime.utcnow, description="Generation time")
    
    class Config:
        json_encoders = {
            date: lambda v: v.isoformat(),
            datetime: lambda v: v.isoformat(),
        }


# =============================================================================
# Overdue Request Models
# =============================================================================

class OverdueRequest(BaseModel):
    """Details of an overdue approval request."""
    request_id: int = Field(..., description="Request ID")
    employee_id: int = Field(..., description="Employee ID")
    employee_name: str = Field(..., description="Employee name")
    department: Optional[str] = Field(default=None, description="Department")
    
    # Request details
    request_type: str = Field(..., description="Request type")
    days_requested: float = Field(..., description="Days requested")
    start_date: date = Field(..., description="Requested start date")
    end_date: date = Field(..., description="Requested end date")
    submitted_at: datetime = Field(..., description="Submission time")
    
    # Approver info
    approver_id: int = Field(..., description="Current approver ID")
    approver_name: str = Field(..., description="Current approver name")
    
    # Overdue info
    hours_overdue: float = Field(..., description="Hours overdue")
    days_overdue: float = Field(..., description="Days overdue")
    severity: OverdueSeverity = Field(..., description="Overdue severity")
    
    # Escalation
    escalation_status: EscalationStatus = Field(..., description="Escalation status")
    escalation_target: Optional[str] = Field(default=None, description="Escalation target")
    escalated_at: Optional[datetime] = Field(default=None, description="Escalation time")
    
    # Impact
    impact_level: ImpactLevel = Field(..., description="Impact level")
    impact_factors: List[str] = Field(default_factory=list, description="Impact factors")


class EscalationRecommendation(BaseModel):
    """Escalation recommendation for overdue requests."""
    request_id: int = Field(..., description="Request ID")
    current_approver: str = Field(..., description="Current approver")
    recommended_escalation_to: str = Field(..., description="Recommended escalation target")
    reason: str = Field(..., description="Escalation reason")
    priority: str = Field(..., description="Priority: normal, high, urgent")
    auto_escalate_at: Optional[datetime] = Field(default=None, description="Auto-escalation time")


class OverdueAnalyticsResponse(BaseModel):
    """Complete overdue requests analysis response."""
    # Summary
    total_overdue: int = Field(..., description="Total overdue requests")
    critical_count: int = Field(default=0, description="Critical severity count")
    high_count: int = Field(default=0, description="High severity count")
    medium_count: int = Field(default=0, description="Medium severity count")
    low_count: int = Field(default=0, description="Low severity count")
    
    # Overdue requests
    overdue_requests: List[OverdueRequest] = Field(..., description="Overdue requests")
    
    # Escalation recommendations
    escalation_recommendations: List[EscalationRecommendation] = Field(
        default_factory=list,
        description="Escalation recommendations",
    )
    
    # By approver breakdown
    by_approver: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Overdue counts by approver",
    )
    
    # By department breakdown
    by_department: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Overdue counts by department",
    )
    
    # Impact analysis
    total_affected_employees: int = Field(..., description="Total affected employees")
    total_affected_days: float = Field(..., description="Total days in pending requests")
    high_impact_requests: int = Field(default=0, description="High impact requests")
    
    # Pagination
    page: int = Field(default=1, description="Current page")
    page_size: int = Field(default=20, description="Page size")
    total_pages: int = Field(..., description="Total pages")
    
    # Metadata
    as_of: datetime = Field(default_factory=datetime.utcnow, description="Data as of time")

    class Config:
        json_encoders = {
            date: lambda v: v.isoformat(),
            datetime: lambda v: v.isoformat(),
        }


# =============================================================================
# Summary Models
# =============================================================================

class PendingCountByType(BaseModel):
    """Pending counts by request type."""
    request_type: str = Field(..., description="Request type")
    count: int = Field(..., description="Pending count")
    total_days: float = Field(..., description="Total days pending")
    oldest_request_date: Optional[date] = Field(default=None, description="Oldest request date")


class TeamImpactSummary(BaseModel):
    """Team impact summary for pending approvals."""
    team_id: int = Field(..., description="Team/department ID")
    team_name: str = Field(..., description="Team name")
    pending_count: int = Field(..., description="Pending requests")
    overdue_count: int = Field(default=0, description="Overdue requests")
    employees_waiting: int = Field(..., description="Employees waiting")
    coverage_impact: Optional[str] = Field(default=None, description="Coverage impact")


class TrendComparison(BaseModel):
    """Trend comparison data."""
    metric_name: str = Field(..., description="Metric name")
    current_value: float = Field(..., description="Current value")
    previous_value: Optional[float] = Field(default=None, description="Previous period value")
    change_percentage: Optional[float] = Field(default=None, description="Change percentage")
    trend: TrendDirection = Field(..., description="Trend direction")


class ApprovalSummaryResponse(BaseModel):
    """Real-time approval summary response."""
    # Counts
    total_pending: int = Field(..., description="Total pending approvals")
    total_overdue: int = Field(..., description="Total overdue")
    pending_today: int = Field(default=0, description="Submitted today")
    decisions_today: int = Field(default=0, description="Decisions made today")
    
    # Urgent items
    urgent_items: int = Field(default=0, description="Urgent items requiring attention")
    auto_escalation_pending: int = Field(default=0, description="Pending auto-escalation")
    
    # By type
    pending_by_type: List[PendingCountByType] = Field(
        default_factory=list,
        description="Pending by request type",
    )
    
    # Team impact
    team_impact: List[TeamImpactSummary] = Field(
        default_factory=list,
        description="Team impact summary",
    )
    
    # Trends
    trends: List[TrendComparison] = Field(
        default_factory=list,
        description="Trend comparisons",
    )
    
    # Quick stats
    approval_rate_today: Optional[float] = Field(default=None, description="Today's approval rate")
    average_decision_time_today: Optional[float] = Field(
        default=None,
        description="Today's avg decision time (hours)",
    )
    
    # Alerts
    alerts: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Active alerts",
    )
    
    # Metadata
    as_of: datetime = Field(default_factory=datetime.utcnow, description="Summary as of time")
    
    class Config:
        json_encoders = {
            date: lambda v: v.isoformat(),
            datetime: lambda v: v.isoformat(),
        }


