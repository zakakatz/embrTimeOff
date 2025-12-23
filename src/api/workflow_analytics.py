"""API endpoint for time-off workflow analytics."""

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.schemas.workflow_analytics import (
    WorkflowAnalyticsResponse,
    ProcessingSpeedAnalytics,
    TimingDistribution,
    EscalationPattern,
    VolumePatternAnalytics,
    CategoryVolume,
    DepartmentVolume,
    SeasonalPattern,
    ApproverEffectivenessAnalytics,
    ApproverMetrics,
    OrganizationalBenchmarking,
    DepartmentBenchmark,
    PeriodComparison,
    BottleneckAnalysis,
    OptimizationRecommendation,
    TrendDirection,
    PerformanceLevel,
    RecommendationPriority,
)


workflow_analytics_router = APIRouter(
    prefix="/api/time-off-requests/workflow",
    tags=["Workflow Analytics"],
)


# =============================================================================
# Helper Functions
# =============================================================================

def get_current_user():
    """Mock function to get current authenticated user."""
    return {
        "id": 1,
        "name": "HR Manager",
        "role": "hr_manager",
        "is_hr": True,
        "is_management": True,
        "department_id": 100,
    }


def validate_analytics_access(user: Dict[str, Any]) -> bool:
    """Validate access to analytics."""
    return user.get("is_hr", False) or user.get("is_management", False) or user.get("role") == "admin"


def calculate_performance_level(score: float) -> PerformanceLevel:
    """Calculate performance level from score."""
    if score >= 90:
        return PerformanceLevel.EXCELLENT
    elif score >= 75:
        return PerformanceLevel.GOOD
    elif score >= 60:
        return PerformanceLevel.AVERAGE
    elif score >= 40:
        return PerformanceLevel.BELOW_AVERAGE
    else:
        return PerformanceLevel.POOR


# =============================================================================
# Analytics Endpoint
# =============================================================================

@workflow_analytics_router.get(
    "/analytics",
    response_model=WorkflowAnalyticsResponse,
    summary="Get workflow analytics",
    description="Analyze time-off request workflow performance and patterns.",
)
async def get_workflow_analytics(
    start_date: Optional[date] = Query(default=None, description="Analysis start date"),
    end_date: Optional[date] = Query(default=None, description="Analysis end date"),
    department_id: Optional[int] = Query(default=None, description="Filter by department"),
    request_type: Optional[str] = Query(default=None, description="Filter by request type"),
    approver_id: Optional[int] = Query(default=None, description="Filter by approver"),
    include_recommendations: bool = Query(default=True, description="Include recommendations"),
    include_benchmarking: bool = Query(default=True, description="Include benchmarking"),
):
    """
    Get comprehensive workflow analytics.
    
    This endpoint provides:
    - Processing speed analysis with timing distributions
    - Request volume patterns by category, department, and season
    - Approver effectiveness metrics
    - Organizational benchmarking
    - Workflow optimization recommendations
    - Bottleneck identification
    
    **Access Control**: Only HR personnel and management can access this endpoint.
    """
    current_user = get_current_user()
    
    if not validate_analytics_access(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only HR and management can access workflow analytics",
        )
    
    # Set date range (default: last 90 days)
    end_dt = end_date or date.today()
    start_dt = start_date or (end_dt - timedelta(days=90))
    
    # Build filters
    filters = {}
    if department_id:
        filters["department_id"] = department_id
    if request_type:
        filters["request_type"] = request_type
    if approver_id:
        filters["approver_id"] = approver_id
    
    # =============================================================================
    # Processing Speed Analytics
    # =============================================================================
    
    timing_distribution = TimingDistribution(
        percentile_25=8.5,
        percentile_50=16.0,
        percentile_75=28.0,
        percentile_90=48.0,
        percentile_99=96.0,
        mean=22.5,
        std_deviation=18.2,
        min_time=0.5,
        max_time=120.0,
    )
    
    escalation_patterns = EscalationPattern(
        total_escalated=45,
        escalation_rate=5.2,
        by_reason=[
            {"reason": "SLA breach", "count": 20, "percentage": 44.4},
            {"reason": "Manager unavailable", "count": 15, "percentage": 33.3},
            {"reason": "Policy exception", "count": 10, "percentage": 22.2},
        ],
        by_department=[
            {"department": "Engineering", "count": 15, "rate": 4.5},
            {"department": "Sales", "count": 18, "rate": 6.2},
            {"department": "Marketing", "count": 12, "rate": 5.8},
        ],
        avg_time_to_escalation=52.0,
        avg_resolution_after_escalation=24.0,
    )
    
    processing_speed = ProcessingSpeedAnalytics(
        total_processed=865,
        average_processing_hours=22.5,
        sla_target_hours=48.0,
        sla_compliance_rate=92.5,
        requests_within_sla=800,
        requests_over_sla=65,
        timing_distribution=timing_distribution,
        escalation_patterns=escalation_patterns,
        trend_direction=TrendDirection.DOWN,  # Processing time improving
        trend_change_percentage=-8.5,
    )
    
    # =============================================================================
    # Volume Pattern Analytics
    # =============================================================================
    
    volume_patterns = VolumePatternAnalytics(
        total_requests=865,
        avg_daily_requests=9.6,
        by_category=[
            CategoryVolume(
                category="PTO",
                total_requests=520,
                percentage=60.1,
                trend=TrendDirection.STABLE,
                change_from_previous=2.3,
            ),
            CategoryVolume(
                category="Sick Leave",
                total_requests=215,
                percentage=24.9,
                trend=TrendDirection.UP,
                change_from_previous=12.5,
            ),
            CategoryVolume(
                category="Personal",
                total_requests=85,
                percentage=9.8,
                trend=TrendDirection.DOWN,
                change_from_previous=-5.2,
            ),
            CategoryVolume(
                category="Other",
                total_requests=45,
                percentage=5.2,
                trend=TrendDirection.STABLE,
                change_from_previous=0.8,
            ),
        ],
        by_department=[
            DepartmentVolume(
                department_id=100,
                department_name="Engineering",
                total_requests=335,
                requests_per_employee=4.2,
                approval_rate=85.5,
                avg_processing_time=18.5,
            ),
            DepartmentVolume(
                department_id=101,
                department_name="Sales",
                total_requests=290,
                requests_per_employee=5.8,
                approval_rate=82.0,
                avg_processing_time=24.0,
            ),
            DepartmentVolume(
                department_id=102,
                department_name="Marketing",
                total_requests=205,
                requests_per_employee=5.1,
                approval_rate=88.0,
                avg_processing_time=20.5,
            ),
        ],
        seasonal_patterns=[
            SeasonalPattern(
                period="Q1",
                total_requests=180,
                avg_daily_requests=6.0,
                peak_days=["Friday", "Monday"],
                comparison_to_average=-15.0,
            ),
            SeasonalPattern(
                period="Q2",
                total_requests=220,
                avg_daily_requests=7.3,
                peak_days=["Friday"],
                comparison_to_average=5.0,
            ),
            SeasonalPattern(
                period="Summer",
                total_requests=350,
                avg_daily_requests=11.7,
                peak_days=["Friday", "Monday", "Thursday"],
                comparison_to_average=45.0,
            ),
        ],
        monthly_trend=[
            {"month": "Jan", "requests": 85, "change": None},
            {"month": "Feb", "requests": 78, "change": -8.2},
            {"month": "Mar", "requests": 92, "change": 17.9},
        ],
        year_over_year_change=8.5,
    )
    
    # =============================================================================
    # Approver Effectiveness Analytics
    # =============================================================================
    
    approvers = [
        ApproverMetrics(
            approver_id=10,
            approver_name="Jane Director",
            department="Engineering",
            total_decisions=145,
            approved_count=125,
            denied_count=20,
            avg_decision_hours=12.5,
            decision_speed_percentile=92.0,
            policy_compliance_rate=98.5,
            escalation_rate=2.1,
            reversal_rate=0.5,
            effectiveness_score=94.0,
            performance_level=PerformanceLevel.EXCELLENT,
        ),
        ApproverMetrics(
            approver_id=11,
            approver_name="Bob Manager",
            department="Sales",
            total_decisions=120,
            approved_count=95,
            denied_count=25,
            avg_decision_hours=28.0,
            decision_speed_percentile=45.0,
            policy_compliance_rate=92.0,
            escalation_rate=6.5,
            reversal_rate=2.0,
            effectiveness_score=68.0,
            performance_level=PerformanceLevel.AVERAGE,
        ),
        ApproverMetrics(
            approver_id=12,
            approver_name="Alice Lead",
            department="Marketing",
            total_decisions=85,
            approved_count=75,
            denied_count=10,
            avg_decision_hours=18.0,
            decision_speed_percentile=78.0,
            policy_compliance_rate=96.0,
            escalation_rate=3.2,
            reversal_rate=1.0,
            effectiveness_score=82.0,
            performance_level=PerformanceLevel.GOOD,
        ),
    ]
    
    approver_effectiveness = ApproverEffectivenessAnalytics(
        total_approvers=len(approvers),
        avg_decision_speed_hours=19.5,
        avg_policy_compliance=95.5,
        top_performers=[a for a in approvers if a.performance_level in [PerformanceLevel.EXCELLENT, PerformanceLevel.GOOD]],
        needs_improvement=[a for a in approvers if a.performance_level in [PerformanceLevel.BELOW_AVERAGE, PerformanceLevel.POOR]],
        all_approvers=approvers,
    )
    
    # =============================================================================
    # Organizational Benchmarking
    # =============================================================================
    
    benchmarking = OrganizationalBenchmarking(
        org_avg_processing_time=22.5,
        org_approval_rate=84.5,
        org_sla_compliance=92.5,
        department_benchmarks=[],
        period_comparisons=[],
        industry_comparison=None,
    )
    
    if include_benchmarking:
        benchmarking = OrganizationalBenchmarking(
            org_avg_processing_time=22.5,
            org_approval_rate=84.5,
            org_sla_compliance=92.5,
            department_benchmarks=[
                DepartmentBenchmark(
                    department_id=100,
                    department_name="Engineering",
                    avg_processing_time=18.5,
                    approval_rate=85.5,
                    sla_compliance=95.0,
                    vs_organization_avg={
                        "processing_time": -17.8,
                        "approval_rate": 1.2,
                        "sla_compliance": 2.7,
                    },
                    rank=1,
                    performance_level=PerformanceLevel.EXCELLENT,
                ),
                DepartmentBenchmark(
                    department_id=102,
                    department_name="Marketing",
                    avg_processing_time=20.5,
                    approval_rate=88.0,
                    sla_compliance=93.0,
                    vs_organization_avg={
                        "processing_time": -8.9,
                        "approval_rate": 4.1,
                        "sla_compliance": 0.5,
                    },
                    rank=2,
                    performance_level=PerformanceLevel.GOOD,
                ),
                DepartmentBenchmark(
                    department_id=101,
                    department_name="Sales",
                    avg_processing_time=24.0,
                    approval_rate=82.0,
                    sla_compliance=88.0,
                    vs_organization_avg={
                        "processing_time": 6.7,
                        "approval_rate": -3.0,
                        "sla_compliance": -4.9,
                    },
                    rank=3,
                    performance_level=PerformanceLevel.AVERAGE,
                ),
            ],
            period_comparisons=[
                PeriodComparison(
                    period="Current Quarter",
                    total_requests=320,
                    avg_processing_time=22.5,
                    approval_rate=84.5,
                    sla_compliance=92.5,
                    change_from_previous={
                        "total_requests": 8.5,
                        "avg_processing_time": -12.0,
                        "approval_rate": 2.3,
                        "sla_compliance": 3.5,
                    },
                ),
                PeriodComparison(
                    period="Previous Quarter",
                    total_requests=295,
                    avg_processing_time=25.5,
                    approval_rate=82.6,
                    sla_compliance=89.4,
                    change_from_previous={},
                ),
            ],
            industry_comparison={
                "avg_processing_time": {"org": 22.5, "industry": 28.0, "vs_industry": -19.6},
                "approval_rate": {"org": 84.5, "industry": 82.0, "vs_industry": 3.0},
                "sla_compliance": {"org": 92.5, "industry": 88.0, "vs_industry": 5.1},
            },
        )
    
    # =============================================================================
    # Bottleneck Analysis
    # =============================================================================
    
    bottlenecks = [
        BottleneckAnalysis(
            bottleneck_id="BN-001",
            location="Sales Department Approvals",
            severity="medium",
            requests_affected=45,
            avg_delay_hours=12.5,
            root_cause="Single approver with high volume",
            contributing_factors=[
                "High request volume per approver",
                "Approver frequently out of office",
                "No backup approver configured",
            ],
            suggested_resolution="Add secondary approver or delegate",
        ),
        BottleneckAnalysis(
            bottleneck_id="BN-002",
            location="Extended Leave Requests",
            severity="low",
            requests_affected=15,
            avg_delay_hours=24.0,
            root_cause="Multi-level approval requirement",
            contributing_factors=[
                "Requires HR review for >5 days",
                "Sequential approval process",
            ],
            suggested_resolution="Consider parallel approval for faster processing",
        ),
    ]
    
    # =============================================================================
    # Optimization Recommendations
    # =============================================================================
    
    recommendations = []
    if include_recommendations:
        recommendations = [
            OptimizationRecommendation(
                recommendation_id="REC-001",
                title="Add Delegate Approvers for Sales",
                description="Configure backup approvers for the Sales department to reduce bottlenecks",
                priority=RecommendationPriority.HIGH,
                estimated_impact="Reduce avg processing time by 15-20%",
                affected_metric="Processing Time",
                potential_improvement=18.0,
                implementation_effort="Low",
                suggested_actions=[
                    "Identify 2-3 potential delegates per primary approver",
                    "Configure delegation rules in system",
                    "Train delegates on approval criteria",
                ],
                supporting_data={
                    "current_bottleneck_delays": 12.5,
                    "affected_requests_monthly": 45,
                },
            ),
            OptimizationRecommendation(
                recommendation_id="REC-002",
                title="Implement Auto-Approval for Short Requests",
                description="Enable auto-approval for requests under 2 days with positive balance",
                priority=RecommendationPriority.MEDIUM,
                estimated_impact="Reduce approval volume by 25-30%",
                affected_metric="Approver Workload",
                potential_improvement=28.0,
                implementation_effort="Medium",
                suggested_actions=[
                    "Define auto-approval eligibility criteria",
                    "Configure balance thresholds",
                    "Set up audit logging for auto-approvals",
                ],
                supporting_data={
                    "short_requests_percentage": 35.0,
                    "avg_balance_for_short_requests": 12.5,
                },
            ),
            OptimizationRecommendation(
                recommendation_id="REC-003",
                title="Send Daily Digest to Approvers",
                description="Implement daily email digest of pending approvals to reduce oversight",
                priority=RecommendationPriority.LOW,
                estimated_impact="Improve SLA compliance by 2-3%",
                affected_metric="SLA Compliance",
                potential_improvement=2.5,
                implementation_effort="Low",
                suggested_actions=[
                    "Design digest email template",
                    "Schedule daily sends at 9 AM",
                    "Include direct approval links",
                ],
                supporting_data={
                    "requests_missed_due_to_oversight": 8,
                    "avg_delay_from_oversight": 18.0,
                },
            ),
        ]
    
    return WorkflowAnalyticsResponse(
        start_date=start_dt,
        end_date=end_dt,
        processing_speed=processing_speed,
        volume_patterns=volume_patterns,
        approver_effectiveness=approver_effectiveness,
        benchmarking=benchmarking,
        bottlenecks=bottlenecks,
        recommendations=recommendations,
        filters=filters,
        generated_at=datetime.utcnow(),
    )


