"""API endpoint for organizational analytics and hierarchy analysis."""

from datetime import date, datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.schemas.organizational_analytics import (
    OrganizationalAnalyticsResponse,
    ReportingSpanMetrics,
    ManagerSpanMetric,
    SpanDistribution,
    ManagementDensityAnalysis,
    DepartmentDensity,
    ManagementEffectivenessAssessment,
    AuthorityClarity,
    DecisionEfficiency,
    CommunicationPattern,
    OrganizationalEfficiencyEvaluation,
    CollaborationEffectiveness,
    StructuralRecommendation,
    PerformancePlanningData,
    EfficiencyLevel,
    RecommendationCategory,
    RecommendationPriority,
)


organizational_analytics_router = APIRouter(
    prefix="/api/admin/organizational-analytics",
    tags=["Organizational Analytics"],
)


# =============================================================================
# Helper Functions
# =============================================================================

def get_current_user():
    """Mock function to get current authenticated user."""
    return {
        "id": 1,
        "name": "Admin User",
        "role": "admin",
        "is_hr": True,
    }


def validate_admin_access(user: Dict[str, Any]) -> bool:
    """Validate admin access."""
    return user.get("role") == "admin" or user.get("is_hr", False)


def determine_efficiency_level(score: float) -> EfficiencyLevel:
    """Determine efficiency level from score."""
    if score >= 90:
        return EfficiencyLevel.OPTIMAL
    elif score >= 75:
        return EfficiencyLevel.GOOD
    elif score >= 60:
        return EfficiencyLevel.ADEQUATE
    elif score >= 40:
        return EfficiencyLevel.NEEDS_IMPROVEMENT
    else:
        return EfficiencyLevel.CRITICAL


# =============================================================================
# Hierarchy Analytics Endpoint
# =============================================================================

@organizational_analytics_router.get(
    "/hierarchy",
    response_model=OrganizationalAnalyticsResponse,
    summary="Get organizational hierarchy analytics",
    description="Comprehensive hierarchy analysis with span metrics, density analysis, and recommendations.",
)
async def get_hierarchy_analytics(
    department_id: Optional[int] = Query(default=None, description="Filter by department"),
    include_recommendations: bool = Query(default=True, description="Include recommendations"),
    min_span_threshold: int = Query(default=3, ge=1, description="Min span for underutilized"),
    max_span_threshold: int = Query(default=12, ge=5, description="Max span for overextended"),
):
    """
    Get organizational hierarchy analytics.
    
    This endpoint provides:
    - Reporting span metrics with optimization recommendations
    - Management density analysis by department
    - Management effectiveness assessment
    - Organizational efficiency scores
    - Restructuring suggestions
    - Performance improvement planning data
    
    **Access Control**: Only administrators and HR can access this endpoint.
    """
    current_user = get_current_user()
    
    if not validate_admin_access(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or HR privileges required",
        )
    
    # =============================================================================
    # Reporting Span Metrics
    # =============================================================================
    
    # Mock manager data
    managers = [
        ManagerSpanMetric(
            manager_id=10,
            manager_name="CEO",
            title="Chief Executive Officer",
            department="Executive",
            direct_reports=6,
            total_subordinates=250,
            levels_below=5,
            span_efficiency=EfficiencyLevel.GOOD,
            is_overextended=False,
            is_underutilized=False,
            recommended_span=6,
            recommendation=None,
        ),
        ManagerSpanMetric(
            manager_id=20,
            manager_name="VP Engineering",
            title="VP of Engineering",
            department="Engineering",
            direct_reports=8,
            total_subordinates=80,
            levels_below=3,
            span_efficiency=EfficiencyLevel.OPTIMAL,
            is_overextended=False,
            is_underutilized=False,
            recommended_span=7,
            recommendation=None,
        ),
        ManagerSpanMetric(
            manager_id=30,
            manager_name="Sales Director",
            title="Director of Sales",
            department="Sales",
            direct_reports=15,
            total_subordinates=45,
            levels_below=2,
            span_efficiency=EfficiencyLevel.NEEDS_IMPROVEMENT,
            is_overextended=True,
            is_underutilized=False,
            recommended_span=8,
            recommendation="Consider creating team lead positions to reduce span",
        ),
        ManagerSpanMetric(
            manager_id=40,
            manager_name="Marketing Manager",
            title="Marketing Manager",
            department="Marketing",
            direct_reports=2,
            total_subordinates=2,
            levels_below=1,
            span_efficiency=EfficiencyLevel.NEEDS_IMPROVEMENT,
            is_overextended=False,
            is_underutilized=True,
            recommended_span=6,
            recommendation="Consider consolidating with another management role",
        ),
    ]
    
    overextended = [m for m in managers if m.is_overextended]
    underutilized = [m for m in managers if m.is_underutilized]
    
    reporting_span_metrics = ReportingSpanMetrics(
        total_managers=len(managers),
        avg_span_of_control=7.75,
        median_span=7.0,
        min_span=2,
        max_span=15,
        std_deviation=4.2,
        optimal_span_min=5,
        optimal_span_max=9,
        span_distribution=[
            SpanDistribution(range_label="1-3", min_span=1, max_span=3, count=5, percentage=12.5),
            SpanDistribution(range_label="4-6", min_span=4, max_span=6, count=15, percentage=37.5),
            SpanDistribution(range_label="7-9", min_span=7, max_span=9, count=12, percentage=30.0),
            SpanDistribution(range_label="10-12", min_span=10, max_span=12, count=6, percentage=15.0),
            SpanDistribution(range_label="13+", min_span=13, max_span=99, count=2, percentage=5.0),
        ],
        overextended_managers=overextended,
        underutilized_managers=underutilized,
    )
    
    # =============================================================================
    # Management Density Analysis
    # =============================================================================
    
    department_densities = [
        DepartmentDensity(
            department_id=100,
            department_name="Engineering",
            total_employees=80,
            total_managers=10,
            individual_contributors=70,
            manager_to_employee_ratio=0.125,
            ic_to_manager_ratio=7.0,
            density_efficiency=EfficiencyLevel.OPTIMAL,
            is_top_heavy=False,
            vs_org_average=-2.5,
        ),
        DepartmentDensity(
            department_id=101,
            department_name="Sales",
            total_employees=50,
            total_managers=8,
            individual_contributors=42,
            manager_to_employee_ratio=0.16,
            ic_to_manager_ratio=5.25,
            density_efficiency=EfficiencyLevel.ADEQUATE,
            is_top_heavy=False,
            vs_org_average=6.7,
        ),
        DepartmentDensity(
            department_id=102,
            department_name="Marketing",
            total_employees=25,
            total_managers=6,
            individual_contributors=19,
            manager_to_employee_ratio=0.24,
            ic_to_manager_ratio=3.17,
            density_efficiency=EfficiencyLevel.NEEDS_IMPROVEMENT,
            is_top_heavy=True,
            vs_org_average=60.0,
        ),
        DepartmentDensity(
            department_id=103,
            department_name="Finance",
            total_employees=20,
            total_managers=3,
            individual_contributors=17,
            manager_to_employee_ratio=0.15,
            ic_to_manager_ratio=5.67,
            density_efficiency=EfficiencyLevel.GOOD,
            is_top_heavy=False,
            vs_org_average=0.0,
        ),
    ]
    
    management_density = ManagementDensityAnalysis(
        total_employees=250,
        total_managers=40,
        total_ics=210,
        org_manager_ratio=0.16,
        org_ic_to_manager_ratio=5.25,
        industry_benchmark_ratio=0.15,
        department_densities=department_densities,
        top_heavy_departments=["Marketing"],
    )
    
    # =============================================================================
    # Management Effectiveness Assessment
    # =============================================================================
    
    authority_clarity = AuthorityClarity(
        clarity_score=82.5,
        clear_reporting_lines_percentage=94.0,
        dual_reporting_count=8,
        matrix_structures_count=3,
        orphan_positions_count=2,
        authority_issues=[
            {"issue": "Dual reporting in Product team", "severity": "medium", "affected": 5},
            {"issue": "Unclear authority in cross-functional projects", "severity": "low", "affected": 12},
        ],
    )
    
    decision_efficiency = DecisionEfficiency(
        efficiency_score=75.0,
        avg_approval_layers=3.2,
        max_approval_layers=6,
        avg_decision_time_hours=48.0,
        bottleneck_positions=["VP Finance", "Legal Director"],
        streamlining_opportunities=[
            "Reduce approval layers for purchases under $5000",
            "Implement auto-approval for standard HR requests",
        ],
    )
    
    communication_patterns = CommunicationPattern(
        pattern_score=78.0,
        avg_communication_hops=2.8,
        silos_identified=2,
        cross_functional_connections=45,
        communication_barriers=[
            "Limited visibility between Sales and Product teams",
            "Inconsistent meeting cadence across departments",
        ],
    )
    
    management_effectiveness = ManagementEffectivenessAssessment(
        overall_effectiveness_score=78.5,
        effectiveness_level=EfficiencyLevel.GOOD,
        authority_clarity=authority_clarity,
        decision_efficiency=decision_efficiency,
        communication_patterns=communication_patterns,
    )
    
    # =============================================================================
    # Organizational Efficiency
    # =============================================================================
    
    collaboration = CollaborationEffectiveness(
        effectiveness_score=72.0,
        cross_department_collaboration_rate=0.35,
        avg_team_size=6.5,
        remote_collaboration_support=85.0,
        collaboration_strengths=[
            "Strong within-team collaboration",
            "Effective use of collaboration tools",
        ],
        improvement_areas=[
            "Cross-departmental project coordination",
            "Knowledge sharing between teams",
        ],
    )
    
    organizational_efficiency = OrganizationalEfficiencyEvaluation(
        overall_efficiency_score=76.0,
        efficiency_level=EfficiencyLevel.GOOD,
        structural_efficiency=78.0,
        operational_efficiency=74.0,
        resource_utilization=76.0,
        collaboration=collaboration,
    )
    
    # =============================================================================
    # Recommendations
    # =============================================================================
    
    recommendations = []
    if include_recommendations:
        recommendations = [
            StructuralRecommendation(
                recommendation_id="REC-001",
                category=RecommendationCategory.SPAN_OPTIMIZATION,
                priority=RecommendationPriority.HIGH,
                title="Reduce Sales Director Reporting Span",
                description="Current span of 15 direct reports exceeds optimal range",
                rationale="Overextended managers have lower engagement scores and delayed response times",
                affected_employees=45,
                affected_departments=["Sales"],
                estimated_efficiency_gain=12.0,
                implementation_complexity="Medium",
                implementation_steps=[
                    "Identify 2-3 high-performing senior reps for promotion",
                    "Create Team Lead positions with 5-6 direct reports each",
                    "Restructure reporting lines",
                    "Update job descriptions and compensation",
                ],
                estimated_timeline="2-3 months",
                risks=["Temporary disruption during transition", "Additional compensation costs"],
            ),
            StructuralRecommendation(
                recommendation_id="REC-002",
                category=RecommendationCategory.MANAGEMENT_CONSOLIDATION,
                priority=RecommendationPriority.MEDIUM,
                title="Consolidate Marketing Management",
                description="Marketing has high management density with underutilized spans",
                rationale="Reducing management overhead improves cost efficiency",
                affected_employees=25,
                affected_departments=["Marketing"],
                estimated_efficiency_gain=8.0,
                implementation_complexity="High",
                implementation_steps=[
                    "Analyze current manager responsibilities",
                    "Identify consolidation opportunities",
                    "Develop transition plan for affected managers",
                    "Execute consolidation with clear communication",
                ],
                estimated_timeline="3-4 months",
                risks=["Manager morale impact", "Knowledge loss during transition"],
            ),
            StructuralRecommendation(
                recommendation_id="REC-003",
                category=RecommendationCategory.AUTHORITY_CLARIFICATION,
                priority=RecommendationPriority.MEDIUM,
                title="Clarify Product Team Reporting Structure",
                description="Dual reporting creates confusion and delays",
                rationale="Clear authority improves decision speed and accountability",
                affected_employees=12,
                affected_departments=["Product", "Engineering"],
                estimated_efficiency_gain=5.0,
                implementation_complexity="Low",
                implementation_steps=[
                    "Document current dual-reporting scenarios",
                    "Define primary vs dotted-line relationships",
                    "Update org chart and communicate changes",
                ],
                estimated_timeline="1 month",
                risks=["Minor adjustment period"],
            ),
        ]
    
    # =============================================================================
    # Performance Planning
    # =============================================================================
    
    performance_planning = PerformancePlanningData(
        current_efficiency_score=76.0,
        target_efficiency_score=85.0,
        improvement_potential=9.0,
        quick_wins=[
            "Clarify dual-reporting relationships",
            "Implement standard meeting cadence",
            "Update org chart documentation",
        ],
        medium_term_initiatives=[
            "Restructure Sales team reporting",
            "Implement cross-functional collaboration programs",
            "Streamline approval processes",
        ],
        long_term_transformations=[
            "Consolidate Marketing management structure",
            "Develop management training program",
            "Implement org health monitoring dashboard",
        ],
        tracking_kpis=[
            {"kpi": "Average Span of Control", "current": 7.75, "target": 7.0},
            {"kpi": "Management Ratio", "current": 0.16, "target": 0.14},
            {"kpi": "Decision Time (hours)", "current": 48.0, "target": 36.0},
            {"kpi": "Employee Satisfaction", "current": 72.0, "target": 80.0},
        ],
    )
    
    return OrganizationalAnalyticsResponse(
        reporting_span_metrics=reporting_span_metrics,
        management_density=management_density,
        organizational_efficiency=organizational_efficiency,
        management_effectiveness=management_effectiveness,
        recommendations=recommendations,
        performance_planning=performance_planning,
        total_employees=250,
        total_departments=8,
        hierarchy_depth=5,
        analysis_date=date.today(),
        generated_at=datetime.utcnow(),
    )


