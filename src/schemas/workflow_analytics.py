"""Pydantic models for time-off workflow analytics API endpoint."""

from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# =============================================================================
# Enums
# =============================================================================

class TrendDirection(str, Enum):
    """Trend direction indicator."""
    UP = "up"
    DOWN = "down"
    STABLE = "stable"


class PerformanceLevel(str, Enum):
    """Performance level indicator."""
    EXCELLENT = "excellent"
    GOOD = "good"
    AVERAGE = "average"
    BELOW_AVERAGE = "below_average"
    POOR = "poor"


class RecommendationPriority(str, Enum):
    """Priority for recommendations."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# =============================================================================
# Processing Speed Analytics
# =============================================================================

class TimingDistribution(BaseModel):
    """Distribution of processing times."""
    percentile_25: float = Field(..., description="25th percentile (hours)")
    percentile_50: float = Field(..., description="50th percentile/median (hours)")
    percentile_75: float = Field(..., description="75th percentile (hours)")
    percentile_90: float = Field(..., description="90th percentile (hours)")
    percentile_99: float = Field(..., description="99th percentile (hours)")
    
    # Statistics
    mean: float = Field(..., description="Mean processing time (hours)")
    std_deviation: float = Field(..., description="Standard deviation")
    min_time: float = Field(..., description="Minimum time (hours)")
    max_time: float = Field(..., description="Maximum time (hours)")


class EscalationPattern(BaseModel):
    """Pattern analysis for escalated requests."""
    total_escalated: int = Field(..., description="Total escalated requests")
    escalation_rate: float = Field(..., description="Escalation rate percentage")
    
    # By reason
    by_reason: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Escalations by reason",
    )
    
    # By department
    by_department: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Escalations by department",
    )
    
    # Average time to escalation
    avg_time_to_escalation: float = Field(..., description="Average hours before escalation")
    
    # Resolution after escalation
    avg_resolution_after_escalation: float = Field(
        ...,
        description="Average hours to resolve after escalation",
    )


class ProcessingSpeedAnalytics(BaseModel):
    """Processing speed analytics."""
    total_processed: int = Field(..., description="Total requests processed")
    average_processing_hours: float = Field(..., description="Average processing time")
    
    # SLA compliance
    sla_target_hours: float = Field(..., description="SLA target hours")
    sla_compliance_rate: float = Field(..., description="SLA compliance rate")
    requests_within_sla: int = Field(..., description="Requests within SLA")
    requests_over_sla: int = Field(..., description="Requests over SLA")
    
    # Distribution
    timing_distribution: TimingDistribution = Field(..., description="Timing distribution")
    
    # Escalations
    escalation_patterns: EscalationPattern = Field(..., description="Escalation patterns")
    
    # Trends
    trend_direction: TrendDirection = Field(..., description="Trend direction")
    trend_change_percentage: float = Field(..., description="Trend change percentage")


# =============================================================================
# Volume Pattern Analytics
# =============================================================================

class CategoryVolume(BaseModel):
    """Volume by request category."""
    category: str = Field(..., description="Category name")
    total_requests: int = Field(..., description="Total requests")
    percentage: float = Field(..., description="Percentage of total")
    trend: TrendDirection = Field(..., description="Trend")
    change_from_previous: float = Field(..., description="Change from previous period")


class DepartmentVolume(BaseModel):
    """Volume by department."""
    department_id: int = Field(..., description="Department ID")
    department_name: str = Field(..., description="Department name")
    total_requests: int = Field(..., description="Total requests")
    requests_per_employee: float = Field(..., description="Requests per employee")
    approval_rate: float = Field(..., description="Approval rate")
    avg_processing_time: float = Field(..., description="Average processing time")


class SeasonalPattern(BaseModel):
    """Seasonal volume pattern."""
    period: str = Field(..., description="Period (e.g., 'Q1', 'Summer')")
    total_requests: int = Field(..., description="Total requests")
    avg_daily_requests: float = Field(..., description="Average daily requests")
    peak_days: List[str] = Field(default_factory=list, description="Peak days")
    comparison_to_average: float = Field(..., description="Comparison to annual average")


class VolumePatternAnalytics(BaseModel):
    """Volume pattern analytics."""
    total_requests: int = Field(..., description="Total requests in period")
    avg_daily_requests: float = Field(..., description="Average daily requests")
    
    # By category
    by_category: List[CategoryVolume] = Field(
        default_factory=list,
        description="Volume by category",
    )
    
    # By department
    by_department: List[DepartmentVolume] = Field(
        default_factory=list,
        description="Volume by department",
    )
    
    # Seasonal patterns
    seasonal_patterns: List[SeasonalPattern] = Field(
        default_factory=list,
        description="Seasonal patterns",
    )
    
    # Trend analysis
    monthly_trend: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Monthly volume trend",
    )
    year_over_year_change: Optional[float] = Field(
        default=None,
        description="Year-over-year change",
    )


# =============================================================================
# Approver Effectiveness Analytics
# =============================================================================

class ApproverMetrics(BaseModel):
    """Metrics for an individual approver."""
    approver_id: int = Field(..., description="Approver employee ID")
    approver_name: str = Field(..., description="Approver name")
    department: Optional[str] = Field(default=None, description="Department")
    
    # Volume
    total_decisions: int = Field(..., description="Total decisions")
    approved_count: int = Field(..., description="Approved count")
    denied_count: int = Field(..., description="Denied count")
    
    # Speed
    avg_decision_hours: float = Field(..., description="Average decision time (hours)")
    decision_speed_percentile: float = Field(..., description="Speed percentile vs peers")
    
    # Quality
    policy_compliance_rate: float = Field(..., description="Policy compliance rate")
    escalation_rate: float = Field(..., description="Escalation rate")
    reversal_rate: float = Field(..., description="Decision reversal rate")
    
    # Score
    effectiveness_score: float = Field(..., description="Overall effectiveness score")
    performance_level: PerformanceLevel = Field(..., description="Performance level")


class ApproverEffectivenessAnalytics(BaseModel):
    """Approver effectiveness analytics."""
    total_approvers: int = Field(..., description="Total approvers")
    avg_decision_speed_hours: float = Field(..., description="Average decision speed")
    avg_policy_compliance: float = Field(..., description="Average policy compliance")
    
    # Top performers
    top_performers: List[ApproverMetrics] = Field(
        default_factory=list,
        description="Top performing approvers",
    )
    
    # Needs improvement
    needs_improvement: List[ApproverMetrics] = Field(
        default_factory=list,
        description="Approvers needing improvement",
    )
    
    # All approvers
    all_approvers: List[ApproverMetrics] = Field(
        default_factory=list,
        description="All approver metrics",
    )


# =============================================================================
# Organizational Benchmarking
# =============================================================================

class DepartmentBenchmark(BaseModel):
    """Benchmark data for a department."""
    department_id: int = Field(..., description="Department ID")
    department_name: str = Field(..., description="Department name")
    
    # Metrics
    avg_processing_time: float = Field(..., description="Average processing time")
    approval_rate: float = Field(..., description="Approval rate")
    sla_compliance: float = Field(..., description="SLA compliance")
    
    # Comparison
    vs_organization_avg: Dict[str, float] = Field(
        default_factory=dict,
        description="Comparison to org average",
    )
    
    # Ranking
    rank: int = Field(..., description="Rank among departments")
    performance_level: PerformanceLevel = Field(..., description="Performance level")


class PeriodComparison(BaseModel):
    """Comparison across time periods."""
    period: str = Field(..., description="Period identifier")
    
    # Metrics
    total_requests: int = Field(..., description="Total requests")
    avg_processing_time: float = Field(..., description="Average processing time")
    approval_rate: float = Field(..., description="Approval rate")
    sla_compliance: float = Field(..., description="SLA compliance")
    
    # Changes
    change_from_previous: Dict[str, float] = Field(
        default_factory=dict,
        description="Changes from previous period",
    )


class OrganizationalBenchmarking(BaseModel):
    """Organizational benchmarking data."""
    # Organization-wide metrics
    org_avg_processing_time: float = Field(..., description="Org average processing time")
    org_approval_rate: float = Field(..., description="Org approval rate")
    org_sla_compliance: float = Field(..., description="Org SLA compliance")
    
    # Department benchmarks
    department_benchmarks: List[DepartmentBenchmark] = Field(
        default_factory=list,
        description="Department benchmarks",
    )
    
    # Period comparisons
    period_comparisons: List[PeriodComparison] = Field(
        default_factory=list,
        description="Period comparisons",
    )
    
    # Industry benchmarks (if available)
    industry_comparison: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Industry comparison",
    )


# =============================================================================
# Workflow Optimization Recommendations
# =============================================================================

class OptimizationRecommendation(BaseModel):
    """Workflow optimization recommendation."""
    recommendation_id: str = Field(..., description="Recommendation ID")
    title: str = Field(..., description="Recommendation title")
    description: str = Field(..., description="Detailed description")
    
    # Priority
    priority: RecommendationPriority = Field(..., description="Priority level")
    
    # Impact
    estimated_impact: str = Field(..., description="Estimated impact")
    affected_metric: str = Field(..., description="Primary affected metric")
    potential_improvement: Optional[float] = Field(
        default=None,
        description="Potential improvement percentage",
    )
    
    # Implementation
    implementation_effort: str = Field(..., description="Implementation effort")
    suggested_actions: List[str] = Field(default_factory=list, description="Suggested actions")
    
    # Evidence
    supporting_data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Supporting data",
    )


class BottleneckAnalysis(BaseModel):
    """Bottleneck analysis."""
    bottleneck_id: str = Field(..., description="Bottleneck ID")
    location: str = Field(..., description="Bottleneck location")
    severity: str = Field(..., description="Severity: high, medium, low")
    
    # Impact
    requests_affected: int = Field(..., description="Requests affected")
    avg_delay_hours: float = Field(..., description="Average delay caused")
    
    # Root cause
    root_cause: str = Field(..., description="Root cause analysis")
    contributing_factors: List[str] = Field(
        default_factory=list,
        description="Contributing factors",
    )
    
    # Resolution
    suggested_resolution: str = Field(..., description="Suggested resolution")


# =============================================================================
# Main Response Model
# =============================================================================

class WorkflowAnalyticsResponse(BaseModel):
    """Complete workflow analytics response."""
    # Analysis period
    start_date: date = Field(..., description="Analysis start date")
    end_date: date = Field(..., description="Analysis end date")
    
    # Processing speed
    processing_speed: ProcessingSpeedAnalytics = Field(
        ...,
        description="Processing speed analytics",
    )
    
    # Volume patterns
    volume_patterns: VolumePatternAnalytics = Field(
        ...,
        description="Volume pattern analytics",
    )
    
    # Approver effectiveness
    approver_effectiveness: ApproverEffectivenessAnalytics = Field(
        ...,
        description="Approver effectiveness analytics",
    )
    
    # Organizational benchmarking
    benchmarking: OrganizationalBenchmarking = Field(
        ...,
        description="Organizational benchmarking",
    )
    
    # Bottlenecks
    bottlenecks: List[BottleneckAnalysis] = Field(
        default_factory=list,
        description="Identified bottlenecks",
    )
    
    # Recommendations
    recommendations: List[OptimizationRecommendation] = Field(
        default_factory=list,
        description="Optimization recommendations",
    )
    
    # Filters applied
    filters: Dict[str, Any] = Field(default_factory=dict, description="Filters applied")
    
    # Metadata
    generated_at: datetime = Field(default_factory=datetime.utcnow, description="Generation time")

    class Config:
        json_encoders = {
            date: lambda v: v.isoformat(),
            datetime: lambda v: v.isoformat(),
        }


