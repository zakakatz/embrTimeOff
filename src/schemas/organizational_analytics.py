"""Pydantic models for organizational analytics and hierarchy analysis API endpoint."""

from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# =============================================================================
# Enums
# =============================================================================

class EfficiencyLevel(str, Enum):
    """Efficiency level indicator."""
    OPTIMAL = "optimal"
    GOOD = "good"
    ADEQUATE = "adequate"
    NEEDS_IMPROVEMENT = "needs_improvement"
    CRITICAL = "critical"


class RecommendationCategory(str, Enum):
    """Category of recommendation."""
    SPAN_OPTIMIZATION = "span_optimization"
    HIERARCHY_FLATTENING = "hierarchy_flattening"
    MANAGEMENT_CONSOLIDATION = "management_consolidation"
    AUTHORITY_CLARIFICATION = "authority_clarification"
    COMMUNICATION_IMPROVEMENT = "communication_improvement"
    RESTRUCTURING = "restructuring"


class RecommendationPriority(str, Enum):
    """Priority level."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# =============================================================================
# Reporting Span Models
# =============================================================================

class ManagerSpanMetric(BaseModel):
    """Span of control metric for a manager."""
    manager_id: int = Field(..., description="Manager employee ID")
    manager_name: str = Field(..., description="Manager name")
    title: str = Field(..., description="Job title")
    department: Optional[str] = Field(default=None, description="Department")
    
    # Span metrics
    direct_reports: int = Field(..., description="Number of direct reports")
    total_subordinates: int = Field(..., description="Total subordinates (all levels)")
    levels_below: int = Field(..., description="Organizational levels below")
    
    # Assessment
    span_efficiency: EfficiencyLevel = Field(..., description="Span efficiency rating")
    is_overextended: bool = Field(default=False, description="Is overextended")
    is_underutilized: bool = Field(default=False, description="Is underutilized")
    
    # Recommendations
    recommended_span: int = Field(..., description="Recommended span")
    recommendation: Optional[str] = Field(default=None, description="Recommendation")


class SpanDistribution(BaseModel):
    """Distribution of reporting spans."""
    range_label: str = Field(..., description="Range label (e.g., '1-3')")
    min_span: int = Field(..., description="Minimum span in range")
    max_span: int = Field(..., description="Maximum span in range")
    count: int = Field(..., description="Number of managers in range")
    percentage: float = Field(..., description="Percentage of total")


class ReportingSpanMetrics(BaseModel):
    """Overall reporting span metrics."""
    # Statistics
    total_managers: int = Field(..., description="Total managers in organization")
    avg_span_of_control: float = Field(..., description="Average span of control")
    median_span: float = Field(..., description="Median span")
    min_span: int = Field(..., description="Minimum span")
    max_span: int = Field(..., description="Maximum span")
    std_deviation: float = Field(..., description="Standard deviation")
    
    # Benchmarks
    optimal_span_min: int = Field(default=5, description="Optimal minimum span")
    optimal_span_max: int = Field(default=9, description="Optimal maximum span")
    
    # Distribution
    span_distribution: List[SpanDistribution] = Field(
        default_factory=list,
        description="Span distribution",
    )
    
    # Problem areas
    overextended_managers: List[ManagerSpanMetric] = Field(
        default_factory=list,
        description="Managers with too many reports",
    )
    underutilized_managers: List[ManagerSpanMetric] = Field(
        default_factory=list,
        description="Managers with too few reports",
    )


# =============================================================================
# Management Density Models
# =============================================================================

class DepartmentDensity(BaseModel):
    """Management density for a department."""
    department_id: int = Field(..., description="Department ID")
    department_name: str = Field(..., description="Department name")
    
    # Counts
    total_employees: int = Field(..., description="Total employees")
    total_managers: int = Field(..., description="Total managers")
    individual_contributors: int = Field(..., description="Individual contributors")
    
    # Ratios
    manager_to_employee_ratio: float = Field(..., description="Manager:employee ratio")
    ic_to_manager_ratio: float = Field(..., description="IC:manager ratio")
    
    # Assessment
    density_efficiency: EfficiencyLevel = Field(..., description="Density efficiency")
    is_top_heavy: bool = Field(default=False, description="Is top-heavy")
    
    # Comparison
    vs_org_average: float = Field(..., description="Comparison to org average")


class ManagementDensityAnalysis(BaseModel):
    """Management density analysis."""
    # Organization-wide metrics
    total_employees: int = Field(..., description="Total employees")
    total_managers: int = Field(..., description="Total managers")
    total_ics: int = Field(..., description="Total individual contributors")
    
    # Ratios
    org_manager_ratio: float = Field(..., description="Org-wide manager ratio")
    org_ic_to_manager_ratio: float = Field(..., description="Org IC:manager ratio")
    
    # Benchmarks
    industry_benchmark_ratio: float = Field(default=0.15, description="Industry benchmark")
    
    # By department
    department_densities: List[DepartmentDensity] = Field(
        default_factory=list,
        description="Density by department",
    )
    
    # Issues
    top_heavy_departments: List[str] = Field(
        default_factory=list,
        description="Top-heavy departments",
    )


# =============================================================================
# Management Effectiveness Models
# =============================================================================

class AuthorityClarity(BaseModel):
    """Authority clarity metrics."""
    clarity_score: float = Field(..., description="Clarity score (0-100)")
    
    # Metrics
    clear_reporting_lines_percentage: float = Field(
        ...,
        description="Percentage with clear reporting lines",
    )
    dual_reporting_count: int = Field(default=0, description="Dual reporting instances")
    matrix_structures_count: int = Field(default=0, description="Matrix structures")
    orphan_positions_count: int = Field(default=0, description="Positions without manager")
    
    # Issues
    authority_issues: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Identified authority issues",
    )


class DecisionEfficiency(BaseModel):
    """Decision-making efficiency metrics."""
    efficiency_score: float = Field(..., description="Efficiency score (0-100)")
    
    # Metrics
    avg_approval_layers: float = Field(..., description="Average approval layers")
    max_approval_layers: int = Field(..., description="Maximum approval layers")
    avg_decision_time_hours: float = Field(..., description="Average decision time")
    
    # Analysis
    bottleneck_positions: List[str] = Field(
        default_factory=list,
        description="Decision bottleneck positions",
    )
    streamlining_opportunities: List[str] = Field(
        default_factory=list,
        description="Streamlining opportunities",
    )


class CommunicationPattern(BaseModel):
    """Communication pattern analysis."""
    pattern_score: float = Field(..., description="Pattern health score (0-100)")
    
    # Metrics
    avg_communication_hops: float = Field(..., description="Average hops for info flow")
    silos_identified: int = Field(default=0, description="Communication silos")
    cross_functional_connections: int = Field(
        ...,
        description="Cross-functional connections",
    )
    
    # Analysis
    communication_barriers: List[str] = Field(
        default_factory=list,
        description="Identified barriers",
    )


class ManagementEffectivenessAssessment(BaseModel):
    """Management effectiveness assessment."""
    overall_effectiveness_score: float = Field(..., description="Overall score (0-100)")
    effectiveness_level: EfficiencyLevel = Field(..., description="Effectiveness level")
    
    # Components
    authority_clarity: AuthorityClarity = Field(..., description="Authority clarity")
    decision_efficiency: DecisionEfficiency = Field(..., description="Decision efficiency")
    communication_patterns: CommunicationPattern = Field(
        ...,
        description="Communication patterns",
    )


# =============================================================================
# Organizational Efficiency Models
# =============================================================================

class CollaborationEffectiveness(BaseModel):
    """Collaboration effectiveness metrics."""
    effectiveness_score: float = Field(..., description="Score (0-100)")
    
    # Metrics
    cross_department_collaboration_rate: float = Field(
        ...,
        description="Cross-department collaboration rate",
    )
    avg_team_size: float = Field(..., description="Average team size")
    remote_collaboration_support: float = Field(
        ...,
        description="Remote collaboration support score",
    )
    
    # Analysis
    collaboration_strengths: List[str] = Field(
        default_factory=list,
        description="Collaboration strengths",
    )
    improvement_areas: List[str] = Field(
        default_factory=list,
        description="Areas for improvement",
    )


class OrganizationalEfficiencyEvaluation(BaseModel):
    """Organizational efficiency evaluation."""
    overall_efficiency_score: float = Field(..., description="Overall score (0-100)")
    efficiency_level: EfficiencyLevel = Field(..., description="Efficiency level")
    
    # Components
    structural_efficiency: float = Field(..., description="Structural efficiency")
    operational_efficiency: float = Field(..., description="Operational efficiency")
    resource_utilization: float = Field(..., description="Resource utilization")
    
    # Collaboration
    collaboration: CollaborationEffectiveness = Field(
        ...,
        description="Collaboration effectiveness",
    )


# =============================================================================
# Recommendations Models
# =============================================================================

class StructuralRecommendation(BaseModel):
    """Structural improvement recommendation."""
    recommendation_id: str = Field(..., description="Recommendation ID")
    category: RecommendationCategory = Field(..., description="Category")
    priority: RecommendationPriority = Field(..., description="Priority")
    
    # Details
    title: str = Field(..., description="Recommendation title")
    description: str = Field(..., description="Detailed description")
    rationale: str = Field(..., description="Business rationale")
    
    # Impact
    affected_employees: int = Field(..., description="Employees affected")
    affected_departments: List[str] = Field(
        default_factory=list,
        description="Departments affected",
    )
    estimated_efficiency_gain: Optional[float] = Field(
        default=None,
        description="Estimated efficiency gain percentage",
    )
    
    # Implementation
    implementation_complexity: str = Field(..., description="Complexity level")
    implementation_steps: List[str] = Field(
        default_factory=list,
        description="Implementation steps",
    )
    estimated_timeline: Optional[str] = Field(default=None, description="Timeline")
    
    # Risks
    risks: List[str] = Field(default_factory=list, description="Potential risks")


class PerformancePlanningData(BaseModel):
    """Data for performance improvement planning."""
    # Current state
    current_efficiency_score: float = Field(..., description="Current efficiency")
    
    # Targets
    target_efficiency_score: float = Field(..., description="Target efficiency")
    improvement_potential: float = Field(..., description="Improvement potential")
    
    # Timeline
    quick_wins: List[str] = Field(default_factory=list, description="Quick wins")
    medium_term_initiatives: List[str] = Field(
        default_factory=list,
        description="Medium-term initiatives",
    )
    long_term_transformations: List[str] = Field(
        default_factory=list,
        description="Long-term transformations",
    )
    
    # KPIs to track
    tracking_kpis: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="KPIs for tracking progress",
    )


# =============================================================================
# Main Response Model
# =============================================================================

class OrganizationalAnalyticsResponse(BaseModel):
    """Complete organizational analytics response."""
    # Reporting span metrics
    reporting_span_metrics: ReportingSpanMetrics = Field(
        ...,
        description="Reporting span metrics",
    )
    
    # Management density
    management_density: ManagementDensityAnalysis = Field(
        ...,
        description="Management density analysis",
    )
    
    # Organizational efficiency
    organizational_efficiency: OrganizationalEfficiencyEvaluation = Field(
        ...,
        description="Organizational efficiency",
    )
    
    # Management effectiveness
    management_effectiveness: ManagementEffectivenessAssessment = Field(
        ...,
        description="Management effectiveness",
    )
    
    # Recommendations
    recommendations: List[StructuralRecommendation] = Field(
        default_factory=list,
        description="Improvement recommendations",
    )
    
    # Performance planning
    performance_planning: PerformancePlanningData = Field(
        ...,
        description="Performance planning data",
    )
    
    # Organization summary
    total_employees: int = Field(..., description="Total employees analyzed")
    total_departments: int = Field(..., description="Total departments")
    hierarchy_depth: int = Field(..., description="Maximum hierarchy depth")
    
    # Metadata
    analysis_date: date = Field(..., description="Analysis date")
    generated_at: datetime = Field(default_factory=datetime.utcnow, description="Generation time")

    class Config:
        json_encoders = {
            date: lambda v: v.isoformat(),
            datetime: lambda v: v.isoformat(),
        }


