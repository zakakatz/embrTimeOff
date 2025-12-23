"""Pydantic schemas for balance analytics and reconciliation API."""

from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class TrendDirectionEnum(str, Enum):
    """Direction of a trend."""
    INCREASING = "increasing"
    DECREASING = "decreasing"
    STABLE = "stable"
    SEASONAL = "seasonal"


class SeasonalPatternEnum(str, Enum):
    """Types of seasonal patterns."""
    SUMMER_PEAK = "summer_peak"
    WINTER_PEAK = "winter_peak"
    QUARTER_END = "quarter_end"
    YEAR_END = "year_end"
    HOLIDAY_DRIVEN = "holiday_driven"
    NO_PATTERN = "no_pattern"


class DiscrepancyTypeEnum(str, Enum):
    """Types of balance discrepancies."""
    ACCRUAL_ERROR = "accrual_error"
    USAGE_MISMATCH = "usage_mismatch"
    CARRYOVER_ERROR = "carryover_error"
    POLICY_CHANGE = "policy_change"
    SYSTEM_ERROR = "system_error"
    MANUAL_ADJUSTMENT = "manual_adjustment"
    DATA_MIGRATION = "data_migration"


class ReconciliationStatusEnum(str, Enum):
    """Status of a reconciliation."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    REQUIRES_APPROVAL = "requires_approval"


class ConfidenceLevelEnum(str, Enum):
    """Confidence level for predictions."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# =============================================================================
# Trend Analysis Models
# =============================================================================

class TrendDataPoint(BaseModel):
    """Single data point in a trend."""
    date: date = Field(..., description="Data point date")
    value: float = Field(..., description="Value at this date")
    period_label: str = Field(..., description="Human-readable period label")


class TrendIdentification(BaseModel):
    """Identified trend in balance data."""
    trend_type: str = Field(..., description="Type of trend identified")
    direction: TrendDirectionEnum = Field(..., description="Trend direction")
    magnitude: float = Field(..., description="Magnitude of change (percentage)")
    start_date: date = Field(..., description="When trend started")
    end_date: Optional[date] = Field(default=None, description="When trend ended")
    confidence: ConfidenceLevelEnum = Field(..., description="Confidence in identification")
    description: str = Field(..., description="Human-readable description")


class SeasonalAnalysis(BaseModel):
    """Seasonal pattern analysis."""
    pattern_type: SeasonalPatternEnum = Field(..., description="Type of seasonal pattern")
    peak_months: List[int] = Field(default_factory=list, description="Peak usage months (1-12)")
    trough_months: List[int] = Field(default_factory=list, description="Low usage months")
    average_peak_increase: float = Field(..., description="Average increase during peaks (%)")
    confidence: ConfidenceLevelEnum = Field(..., description="Confidence in pattern")
    recommendation: str = Field(..., description="Recommendation based on pattern")


class ForecastDataPoint(BaseModel):
    """Forecast data point with confidence interval."""
    date: date = Field(..., description="Forecast date")
    predicted_value: float = Field(..., description="Predicted value")
    lower_bound: float = Field(..., description="Lower confidence bound")
    upper_bound: float = Field(..., description="Upper confidence bound")
    confidence_level: float = Field(default=0.95, description="Confidence level (0-1)")


class BalanceTrendResponse(BaseModel):
    """Response for balance trend analytics."""
    analysis_period_start: date = Field(..., description="Analysis period start")
    analysis_period_end: date = Field(..., description="Analysis period end")
    
    # Historical data
    historical_data: List[TrendDataPoint] = Field(
        default_factory=list,
        description="Historical balance data points",
    )
    
    # Trend identification
    trends: List[TrendIdentification] = Field(
        default_factory=list,
        description="Identified trends",
    )
    
    # Seasonal analysis
    seasonal_analysis: Optional[SeasonalAnalysis] = Field(
        default=None,
        description="Seasonal pattern analysis",
    )
    
    # Forecasting
    forecast: List[ForecastDataPoint] = Field(
        default_factory=list,
        description="Predicted future values",
    )
    forecast_horizon_days: int = Field(default=90, description="Forecast horizon in days")
    
    # Summary statistics
    average_balance: float = Field(..., description="Average balance over period")
    min_balance: float = Field(..., description="Minimum balance observed")
    max_balance: float = Field(..., description="Maximum balance observed")
    standard_deviation: float = Field(..., description="Standard deviation")
    
    # Strategic insights
    insights: List[str] = Field(default_factory=list, description="Strategic insights")
    recommendations: List[str] = Field(default_factory=list, description="Planning recommendations")
    
    # Metadata
    analyzed_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Analysis timestamp",
    )
    data_quality_score: float = Field(
        default=1.0,
        description="Quality score of underlying data (0-1)",
    )

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


# =============================================================================
# Utilization Analytics Models
# =============================================================================

class UtilizationMetric(BaseModel):
    """Utilization metric for a policy."""
    policy_id: int = Field(..., description="Policy ID")
    policy_name: str = Field(..., description="Policy name")
    policy_type: str = Field(..., description="Policy type")
    
    # Utilization rates
    utilization_rate: float = Field(..., description="Overall utilization rate (%)")
    accrual_rate: float = Field(..., description="Accrual efficiency rate (%)")
    carryover_rate: float = Field(..., description="Carryover rate (%)")
    forfeit_rate: float = Field(..., description="Balance forfeit rate (%)")
    
    # Comparisons
    vs_company_average: float = Field(..., description="Compared to company average (%)")
    vs_last_period: float = Field(..., description="Compared to last period (%)")
    
    # Ranking
    percentile_rank: float = Field(..., description="Percentile rank within cohort")


class DepartmentUtilization(BaseModel):
    """Utilization breakdown by department."""
    department_id: int = Field(..., description="Department ID")
    department_name: str = Field(..., description="Department name")
    employee_count: int = Field(..., description="Number of employees")
    average_utilization: float = Field(..., description="Average utilization (%)")
    total_days_used: float = Field(..., description="Total days used")
    total_days_available: float = Field(..., description="Total days available")


class PolicyEffectiveness(BaseModel):
    """Policy effectiveness metrics."""
    policy_id: int = Field(..., description="Policy ID")
    policy_name: str = Field(..., description="Policy name")
    
    # Effectiveness scores
    overall_effectiveness: float = Field(..., description="Overall effectiveness score (0-100)")
    employee_satisfaction_proxy: float = Field(
        ...,
        description="Satisfaction proxy based on usage patterns (0-100)",
    )
    administrative_efficiency: float = Field(
        ...,
        description="Administrative efficiency score (0-100)",
    )
    
    # Issues
    identified_issues: List[str] = Field(
        default_factory=list,
        description="Identified policy issues",
    )
    
    # Recommendations
    optimization_suggestions: List[str] = Field(
        default_factory=list,
        description="Suggestions for improvement",
    )


class OptimizationRecommendation(BaseModel):
    """Recommendation for policy optimization."""
    recommendation_type: str = Field(..., description="Type of recommendation")
    priority: str = Field(..., description="Priority: high, medium, low")
    title: str = Field(..., description="Recommendation title")
    description: str = Field(..., description="Detailed description")
    expected_impact: str = Field(..., description="Expected impact if implemented")
    implementation_guidance: str = Field(..., description="How to implement")
    affected_policies: List[int] = Field(
        default_factory=list,
        description="Policy IDs affected",
    )
    estimated_effort: str = Field(..., description="Estimated implementation effort")


class BalanceUtilizationResponse(BaseModel):
    """Response for balance utilization analytics."""
    analysis_period_start: date = Field(..., description="Analysis period start")
    analysis_period_end: date = Field(..., description="Analysis period end")
    
    # Overall metrics
    company_utilization_rate: float = Field(..., description="Company-wide utilization (%)")
    total_employees_analyzed: int = Field(..., description="Total employees in analysis")
    total_days_allocated: float = Field(..., description="Total days allocated")
    total_days_used: float = Field(..., description="Total days used")
    total_days_forfeited: float = Field(..., description="Total days forfeited")
    
    # Policy metrics
    policy_metrics: List[UtilizationMetric] = Field(
        default_factory=list,
        description="Utilization by policy",
    )
    
    # Department breakdown
    department_breakdown: List[DepartmentUtilization] = Field(
        default_factory=list,
        description="Utilization by department",
    )
    
    # Policy effectiveness
    policy_effectiveness: List[PolicyEffectiveness] = Field(
        default_factory=list,
        description="Policy effectiveness analysis",
    )
    
    # Recommendations
    optimization_recommendations: List[OptimizationRecommendation] = Field(
        default_factory=list,
        description="Optimization recommendations",
    )
    
    # Statistical analysis
    utilization_distribution: Dict[str, float] = Field(
        default_factory=dict,
        description="Distribution of utilization rates",
    )
    
    # Metadata
    analyzed_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Analysis timestamp",
    )

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


# =============================================================================
# Reconciliation Models
# =============================================================================

class BalanceDiscrepancy(BaseModel):
    """Identified balance discrepancy."""
    discrepancy_id: str = Field(..., description="Unique discrepancy ID")
    employee_id: int = Field(..., description="Employee ID")
    employee_name: str = Field(..., description="Employee name")
    policy_id: int = Field(..., description="Policy ID")
    policy_name: str = Field(..., description="Policy name")
    
    # Discrepancy details
    discrepancy_type: DiscrepancyTypeEnum = Field(..., description="Type of discrepancy")
    expected_balance: float = Field(..., description="Expected balance")
    actual_balance: float = Field(..., description="Actual balance")
    difference: float = Field(..., description="Difference (actual - expected)")
    
    # Context
    detected_at: datetime = Field(..., description="When discrepancy was detected")
    probable_cause: str = Field(..., description="Probable cause")
    affected_period: str = Field(..., description="Affected time period")
    
    # Severity
    severity: str = Field(..., description="Severity: critical, high, medium, low")
    requires_immediate_action: bool = Field(default=False, description="Needs immediate action")


class ReconciliationCorrection(BaseModel):
    """Correction to be applied in reconciliation."""
    employee_id: int = Field(..., description="Employee ID")
    policy_id: int = Field(..., description="Policy ID")
    correction_type: str = Field(..., description="Type of correction")
    amount: float = Field(..., description="Correction amount")
    effective_date: date = Field(..., description="Effective date")
    reason: str = Field(..., description="Reason for correction")
    notes: Optional[str] = Field(default=None, description="Additional notes")


class ReconciliationRequest(BaseModel):
    """Request to perform balance reconciliation."""
    scope: str = Field(
        default="all",
        description="Scope: all, department, policy, employee",
    )
    scope_ids: Optional[List[int]] = Field(
        default=None,
        description="IDs for scoped reconciliation",
    )
    as_of_date: Optional[date] = Field(
        default=None,
        description="Reconciliation as of date",
    )
    auto_correct: bool = Field(
        default=False,
        description="Automatically apply corrections",
    )
    correction_threshold: float = Field(
        default=0.5,
        description="Auto-correct only if difference below threshold",
    )
    require_approval_above: float = Field(
        default=2.0,
        description="Require approval for corrections above this amount",
    )
    notes: Optional[str] = Field(default=None, description="Reconciliation notes")


class ReconciliationResult(BaseModel):
    """Result of a reconciliation operation."""
    reconciliation_id: str = Field(..., description="Unique reconciliation ID")
    status: ReconciliationStatusEnum = Field(..., description="Reconciliation status")
    
    # Scope
    scope: str = Field(..., description="Reconciliation scope")
    as_of_date: date = Field(..., description="Reconciliation date")
    
    # Findings
    employees_analyzed: int = Field(..., description="Employees analyzed")
    discrepancies_found: int = Field(..., description="Discrepancies found")
    total_discrepancy_amount: float = Field(..., description="Total discrepancy amount")
    
    # Corrections
    corrections_applied: int = Field(..., description="Corrections applied")
    corrections_pending_approval: int = Field(..., description="Pending approval")
    corrections_failed: int = Field(..., description="Failed corrections")
    
    # Details
    discrepancies: List[BalanceDiscrepancy] = Field(
        default_factory=list,
        description="Identified discrepancies",
    )
    applied_corrections: List[ReconciliationCorrection] = Field(
        default_factory=list,
        description="Applied corrections",
    )
    
    # Audit
    initiated_by: str = Field(..., description="Initiated by (user)")
    initiated_at: datetime = Field(..., description="Initiation timestamp")
    completed_at: Optional[datetime] = Field(default=None, description="Completion timestamp")
    
    # Summary
    summary: str = Field(..., description="Summary of reconciliation")
    recommendations: List[str] = Field(
        default_factory=list,
        description="Recommendations for future prevention",
    )

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


# =============================================================================
# Reconciliation History Models
# =============================================================================

class ReconciliationHistoryEntry(BaseModel):
    """Entry in reconciliation history."""
    reconciliation_id: str = Field(..., description="Reconciliation ID")
    status: ReconciliationStatusEnum = Field(..., description="Status")
    scope: str = Field(..., description="Scope")
    as_of_date: date = Field(..., description="Reconciliation date")
    
    # Summary
    employees_analyzed: int = Field(..., description="Employees analyzed")
    discrepancies_found: int = Field(..., description="Discrepancies found")
    corrections_applied: int = Field(..., description="Corrections applied")
    
    # Audit
    initiated_by: str = Field(..., description="Initiated by")
    initiated_at: datetime = Field(..., description="Initiated at")
    completed_at: Optional[datetime] = Field(default=None, description="Completed at")


class AccuracyAssessment(BaseModel):
    """Assessment of data accuracy."""
    overall_accuracy: float = Field(..., description="Overall accuracy score (0-100)")
    accrual_accuracy: float = Field(..., description="Accrual calculation accuracy")
    usage_accuracy: float = Field(..., description="Usage tracking accuracy")
    carryover_accuracy: float = Field(..., description="Carryover calculation accuracy")
    
    # Trend
    accuracy_trend: TrendDirectionEnum = Field(..., description="Accuracy trend")
    trend_description: str = Field(..., description="Trend description")
    
    # Issues
    common_issues: List[str] = Field(
        default_factory=list,
        description="Common accuracy issues",
    )
    prevention_recommendations: List[str] = Field(
        default_factory=list,
        description="Prevention recommendations",
    )


class ReconciliationTrendAnalysis(BaseModel):
    """Trend analysis of reconciliation activities."""
    period_start: date = Field(..., description="Analysis period start")
    period_end: date = Field(..., description="Analysis period end")
    
    # Volume trends
    reconciliations_per_month: Dict[str, int] = Field(
        default_factory=dict,
        description="Reconciliations by month",
    )
    discrepancies_per_month: Dict[str, int] = Field(
        default_factory=dict,
        description="Discrepancies by month",
    )
    
    # Discrepancy trends
    discrepancy_by_type: Dict[str, int] = Field(
        default_factory=dict,
        description="Discrepancies by type",
    )
    average_discrepancy_amount: float = Field(..., description="Average discrepancy amount")
    
    # Resolution trends
    average_resolution_time_hours: float = Field(..., description="Average resolution time")
    auto_correction_rate: float = Field(..., description="Auto-correction rate (%)")


class ReconciliationHistoryResponse(BaseModel):
    """Response for reconciliation history."""
    # History entries
    entries: List[ReconciliationHistoryEntry] = Field(
        default_factory=list,
        description="History entries",
    )
    total_entries: int = Field(..., description="Total entries")
    page: int = Field(default=1, description="Current page")
    page_size: int = Field(default=20, description="Page size")
    
    # Accuracy assessment
    accuracy_assessment: AccuracyAssessment = Field(
        ...,
        description="Current accuracy assessment",
    )
    
    # Trend analysis
    trend_analysis: ReconciliationTrendAnalysis = Field(
        ...,
        description="Reconciliation trend analysis",
    )
    
    # Summary statistics
    total_reconciliations: int = Field(..., description="Total reconciliations")
    total_discrepancies_resolved: int = Field(..., description="Discrepancies resolved")
    total_corrections_applied: int = Field(..., description="Total corrections applied")
    
    # Metadata
    retrieved_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Retrieval timestamp",
    )

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}

