"""API endpoints for approval analytics and monitoring."""

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.schemas.approval_analytics import (
    ApprovalAnalyticsResponse,
    ApprovalRateMetric,
    TimelineMetric,
    PatternAnalysis,
    PatternDataPoint,
    ManagerPerformance,
    OrgUnitAnalytics,
    ActionableInsight,
    OverdueAnalyticsResponse,
    OverdueRequest,
    OverdueSeverity,
    EscalationStatus,
    EscalationRecommendation,
    ImpactLevel,
    ApprovalSummaryResponse,
    PendingCountByType,
    TeamImpactSummary,
    TrendComparison,
    TrendDirection,
)


approval_analytics_router = APIRouter(
    prefix="/api/time-off/approvals",
    tags=["Approval Analytics"],
)


# =============================================================================
# Helper Functions
# =============================================================================

def get_current_user():
    """Mock function to get current authenticated user."""
    return {
        "id": 1,
        "name": "John Manager",
        "role": "manager",
        "department_id": 100,
        "is_hr": True,
        "is_admin": False,
        "direct_reports": [101, 102, 103, 104, 105],
    }


def validate_analytics_access(user: Dict[str, Any]) -> bool:
    """Validate that the user has access to analytics."""
    return user.get("role") in ["manager", "admin"] or user.get("is_hr", False)


def calculate_severity(hours_overdue: float) -> OverdueSeverity:
    """Calculate severity based on hours overdue."""
    if hours_overdue >= 72:
        return OverdueSeverity.CRITICAL
    elif hours_overdue >= 48:
        return OverdueSeverity.HIGH
    elif hours_overdue >= 24:
        return OverdueSeverity.MEDIUM
    else:
        return OverdueSeverity.LOW


def calculate_impact_level(
    days_requested: float,
    hours_overdue: float,
    start_date: date,
) -> ImpactLevel:
    """Calculate impact level for a request."""
    today = date.today()
    days_until_start = (start_date - today).days
    
    # Critical if start date is soon and request is significantly overdue
    if days_until_start <= 2 and hours_overdue >= 24:
        return ImpactLevel.CRITICAL
    elif days_until_start <= 5 and hours_overdue >= 24:
        return ImpactLevel.HIGH
    elif days_until_start <= 7 or hours_overdue >= 48:
        return ImpactLevel.MODERATE
    elif hours_overdue >= 24:
        return ImpactLevel.LOW
    else:
        return ImpactLevel.MINIMAL


# =============================================================================
# Analytics Endpoint
# =============================================================================

@approval_analytics_router.get(
    "/analytics",
    response_model=ApprovalAnalyticsResponse,
    summary="Get approval analytics and performance metrics",
    description="Generates approval analytics including rates, timelines, patterns, and comparative analysis.",
)
async def get_approval_analytics(
    start_date: Optional[date] = Query(default=None, description="Start date for analytics"),
    end_date: Optional[date] = Query(default=None, description="End date for analytics"),
    department_id: Optional[int] = Query(default=None, description="Filter by department"),
    manager_id: Optional[int] = Query(default=None, description="Filter by manager"),
    request_type: Optional[str] = Query(default=None, description="Filter by request type"),
    include_patterns: bool = Query(default=True, description="Include pattern analysis"),
    include_manager_comparison: bool = Query(default=True, description="Include manager comparison"),
    include_insights: bool = Query(default=True, description="Include actionable insights"),
):
    """
    Get comprehensive approval analytics and performance metrics.
    
    This endpoint provides:
    - Approval/denial rates with trends
    - Decision timeline metrics and SLA compliance
    - Pattern analysis (daily, weekly, monthly)
    - Manager performance comparison
    - Organizational unit analytics
    - Actionable insights for process improvement
    
    **Access Control**: Managers, HR, and administrators can access analytics.
    """
    current_user = get_current_user()
    
    if not validate_analytics_access(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to approval analytics",
        )
    
    # Default date range: last 30 days
    end_dt = end_date or date.today()
    start_dt = start_date or (end_dt - timedelta(days=30))
    
    # Mock approval rate metrics
    approval_rates = ApprovalRateMetric(
        total_requests=245,
        approved_count=198,
        denied_count=35,
        cancelled_count=12,
        approval_rate=80.8,
        denial_rate=14.3,
        previous_period_rate=78.5,
        rate_change=2.3,
        trend=TrendDirection.UP,
    )
    
    # Mock timeline metrics
    timeline_metrics = TimelineMetric(
        average_hours_to_decision=18.5,
        median_hours_to_decision=12.0,
        min_hours_to_decision=0.5,
        max_hours_to_decision=96.0,
        percentile_90=36.0,
        sla_target_hours=48.0,
        sla_compliance_rate=92.5,
        requests_within_sla=227,
        requests_over_sla=18,
    )
    
    # Mock pattern analysis
    daily_patterns = None
    weekly_patterns = None
    monthly_patterns = None
    
    if include_patterns:
        # Daily pattern (by day of week)
        daily_patterns = PatternAnalysis(
            pattern_type="daily",
            data_points=[
                PatternDataPoint(label="Monday", count=52, approved=42, denied=8, pending=2, average_time_to_decision=20.0),
                PatternDataPoint(label="Tuesday", count=48, approved=40, denied=6, pending=2, average_time_to_decision=18.0),
                PatternDataPoint(label="Wednesday", count=45, approved=36, denied=7, pending=2, average_time_to_decision=17.5),
                PatternDataPoint(label="Thursday", count=42, approved=34, denied=6, pending=2, average_time_to_decision=19.0),
                PatternDataPoint(label="Friday", count=58, approved=46, denied=8, pending=4, average_time_to_decision=22.0),
            ],
            peak_period="Friday",
            low_period="Thursday",
            insights=[
                "Request volume peaks on Fridays",
                "Decision times are fastest mid-week",
                "Consider additional capacity for Friday submissions",
            ],
        )
        
        # Weekly pattern
        weekly_patterns = PatternAnalysis(
            pattern_type="weekly",
            data_points=[
                PatternDataPoint(label="Week 1", date=start_dt, count=58, approved=47, denied=9, pending=2),
                PatternDataPoint(label="Week 2", date=start_dt + timedelta(days=7), count=62, approved=50, denied=10, pending=2),
                PatternDataPoint(label="Week 3", date=start_dt + timedelta(days=14), count=55, approved=44, denied=8, pending=3),
                PatternDataPoint(label="Week 4", date=start_dt + timedelta(days=21), count=70, approved=57, denied=8, pending=5),
            ],
            peak_period="Week 4",
            low_period="Week 3",
            insights=[
                "Volume tends to increase toward month-end",
                "Approval rates remain consistent across weeks",
            ],
        )
    
    # Mock analytics by request type
    by_request_type = [
        {"request_type": "PTO", "count": 150, "approval_rate": 82.0, "avg_decision_hours": 16.5},
        {"request_type": "Sick Leave", "count": 60, "approval_rate": 95.0, "avg_decision_hours": 8.0},
        {"request_type": "Personal", "count": 25, "approval_rate": 72.0, "avg_decision_hours": 24.0},
        {"request_type": "Bereavement", "count": 10, "approval_rate": 100.0, "avg_decision_hours": 2.0},
    ]
    
    # Mock department analytics
    by_department = [
        OrgUnitAnalytics(
            unit_id=100,
            unit_name="Engineering",
            unit_type="department",
            total_requests=85,
            pending_requests=5,
            overdue_requests=1,
            approval_rate=81.5,
            average_decision_hours=17.0,
            sla_compliance=93.0,
            vs_company_average=0.7,
        ),
        OrgUnitAnalytics(
            unit_id=101,
            unit_name="Sales",
            unit_type="department",
            total_requests=65,
            pending_requests=4,
            overdue_requests=0,
            approval_rate=78.5,
            average_decision_hours=20.0,
            sla_compliance=90.0,
            vs_company_average=-2.3,
        ),
        OrgUnitAnalytics(
            unit_id=102,
            unit_name="Marketing",
            unit_type="department",
            total_requests=45,
            pending_requests=2,
            overdue_requests=1,
            approval_rate=84.0,
            average_decision_hours=15.0,
            sla_compliance=95.0,
            vs_company_average=3.2,
        ),
    ]
    
    # Mock manager performance
    manager_performance = []
    if include_manager_comparison:
        manager_performance = [
            ManagerPerformance(
                manager_id=1,
                manager_name="John Manager",
                department="Engineering",
                total_decisions=45,
                pending_count=3,
                approval_rate=82.0,
                denial_rate=16.0,
                average_decision_hours=15.5,
                sla_compliance=95.0,
                vs_team_average=3.5,
                vs_company_average=1.2,
                performance_score=88.0,
            ),
            ManagerPerformance(
                manager_id=2,
                manager_name="Jane Lead",
                department="Engineering",
                total_decisions=38,
                pending_count=2,
                approval_rate=78.5,
                denial_rate=18.5,
                average_decision_hours=18.0,
                sla_compliance=92.0,
                vs_team_average=-0.5,
                vs_company_average=-2.3,
                performance_score=82.0,
            ),
            ManagerPerformance(
                manager_id=3,
                manager_name="Bob Director",
                department="Sales",
                total_decisions=55,
                pending_count=4,
                approval_rate=80.0,
                denial_rate=14.5,
                average_decision_hours=22.0,
                sla_compliance=88.0,
                vs_team_average=1.5,
                vs_company_average=-0.8,
                performance_score=78.0,
            ),
        ]
    
    # Mock actionable insights
    insights = []
    if include_insights:
        insights = [
            ActionableInsight(
                insight_id="INS-001",
                category="performance",
                severity="info",
                title="Approval rates improving",
                description="Approval rates have increased 2.3% compared to previous period",
                metric_value=2.3,
                recommended_action="Continue current approval practices",
            ),
            ActionableInsight(
                insight_id="INS-002",
                category="compliance",
                severity="warning",
                title="SLA compliance below target in Sales",
                description="Sales department SLA compliance is 90%, below 95% target",
                metric_value=90.0,
                recommended_action="Review Sales team approval workflows",
                affected_entity="Sales Department",
            ),
            ActionableInsight(
                insight_id="INS-003",
                category="trend",
                severity="info",
                title="Friday volume spike pattern detected",
                description="Request submissions are 25% higher on Fridays",
                metric_value=25.0,
                recommended_action="Consider staggered submission deadlines",
            ),
        ]
    
    return ApprovalAnalyticsResponse(
        start_date=start_dt,
        end_date=end_dt,
        approval_rates=approval_rates,
        timeline_metrics=timeline_metrics,
        daily_patterns=daily_patterns,
        weekly_patterns=weekly_patterns,
        monthly_patterns=monthly_patterns,
        by_request_type=by_request_type,
        by_department=by_department,
        manager_performance=manager_performance,
        insights=insights,
        generated_at=datetime.utcnow(),
    )


# =============================================================================
# Overdue Endpoint
# =============================================================================

@approval_analytics_router.get(
    "/overdue",
    response_model=OverdueAnalyticsResponse,
    summary="Get overdue approval requests",
    description="Identifies overdue requests with impact assessment and escalation recommendations.",
)
async def get_overdue_approvals(
    severity: Optional[OverdueSeverity] = Query(default=None, description="Filter by severity"),
    department_id: Optional[int] = Query(default=None, description="Filter by department"),
    approver_id: Optional[int] = Query(default=None, description="Filter by approver"),
    min_hours_overdue: Optional[float] = Query(default=None, ge=0, description="Min hours overdue"),
    include_escalation_recommendations: bool = Query(default=True, description="Include recommendations"),
    sort_by: str = Query(default="hours_overdue", description="Sort field"),
    sort_order: str = Query(default="desc", description="Sort order: asc, desc"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Page size"),
):
    """
    Get overdue approval requests with impact assessment.
    
    This endpoint provides:
    - List of overdue requests with severity levels
    - Impact assessment for each request
    - Escalation recommendations
    - Breakdown by approver and department
    
    **Access Control**: Managers, HR, and administrators can access overdue analysis.
    """
    current_user = get_current_user()
    
    if not validate_analytics_access(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to overdue approval data",
        )
    
    # Mock overdue requests
    today = date.today()
    now = datetime.utcnow()
    
    overdue_requests = []
    for i in range(15):
        hours_over = 12.0 + (i * 8)
        request_severity = calculate_severity(hours_over)
        start_dt = today + timedelta(days=3 + i)
        impact = calculate_impact_level(2.0 + (i % 3), hours_over, start_dt)
        
        request = OverdueRequest(
            request_id=1000 + i,
            employee_id=200 + i,
            employee_name=f"Employee {200 + i}",
            department=["Engineering", "Sales", "Marketing"][i % 3],
            request_type=["PTO", "Personal", "Sick Leave"][i % 3],
            days_requested=2.0 + (i % 3),
            start_date=start_dt,
            end_date=start_dt + timedelta(days=1 + (i % 3)),
            submitted_at=now - timedelta(hours=hours_over + 24),
            approver_id=1 + (i % 3),
            approver_name=["John Manager", "Jane Lead", "Bob Director"][i % 3],
            hours_overdue=hours_over,
            days_overdue=hours_over / 24,
            severity=request_severity,
            escalation_status=EscalationStatus.ESCALATED if hours_over >= 48 else EscalationStatus.NOT_ESCALATED,
            escalation_target="HR Director" if hours_over >= 72 else None,
            escalated_at=now - timedelta(hours=hours_over - 48) if hours_over >= 48 else None,
            impact_level=impact,
            impact_factors=[
                "Start date approaching" if (start_dt - today).days <= 5 else None,
                "Extended absence" if (i % 3) == 2 else None,
                "Coverage concern" if i % 4 == 0 else None,
            ],
        )
        # Clean up None values from impact factors
        request.impact_factors = [f for f in request.impact_factors if f]
        overdue_requests.append(request)
    
    # Apply filters
    if severity:
        overdue_requests = [r for r in overdue_requests if r.severity == severity]
    if department_id:
        # Mock filter
        pass
    if approver_id:
        overdue_requests = [r for r in overdue_requests if r.approver_id == approver_id]
    if min_hours_overdue:
        overdue_requests = [r for r in overdue_requests if r.hours_overdue >= min_hours_overdue]
    
    # Sort
    reverse = sort_order == "desc"
    if sort_by == "hours_overdue":
        overdue_requests.sort(key=lambda r: r.hours_overdue, reverse=reverse)
    elif sort_by == "severity":
        severity_order = {OverdueSeverity.CRITICAL: 0, OverdueSeverity.HIGH: 1, OverdueSeverity.MEDIUM: 2, OverdueSeverity.LOW: 3}
        overdue_requests.sort(key=lambda r: severity_order[r.severity], reverse=reverse)
    elif sort_by == "start_date":
        overdue_requests.sort(key=lambda r: r.start_date, reverse=reverse)
    
    # Count by severity
    critical_count = sum(1 for r in overdue_requests if r.severity == OverdueSeverity.CRITICAL)
    high_count = sum(1 for r in overdue_requests if r.severity == OverdueSeverity.HIGH)
    medium_count = sum(1 for r in overdue_requests if r.severity == OverdueSeverity.MEDIUM)
    low_count = sum(1 for r in overdue_requests if r.severity == OverdueSeverity.LOW)
    
    # Pagination
    total_requests = len(overdue_requests)
    total_pages = (total_requests + page_size - 1) // page_size
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated_requests = overdue_requests[start_idx:end_idx]
    
    # Mock escalation recommendations
    escalation_recommendations = []
    if include_escalation_recommendations:
        for req in paginated_requests:
            if req.severity in [OverdueSeverity.HIGH, OverdueSeverity.CRITICAL] and req.escalation_status == EscalationStatus.NOT_ESCALATED:
                escalation_recommendations.append(EscalationRecommendation(
                    request_id=req.request_id,
                    current_approver=req.approver_name,
                    recommended_escalation_to="HR Director" if req.severity == OverdueSeverity.CRITICAL else "Department Head",
                    reason=f"Request overdue by {req.hours_overdue:.1f} hours with {req.impact_level.value} impact",
                    priority="urgent" if req.severity == OverdueSeverity.CRITICAL else "high",
                    auto_escalate_at=now + timedelta(hours=4) if req.severity == OverdueSeverity.CRITICAL else None,
                ))
    
    # Mock breakdown by approver
    by_approver = [
        {"approver_id": 1, "approver_name": "John Manager", "overdue_count": 5, "critical_count": 1},
        {"approver_id": 2, "approver_name": "Jane Lead", "overdue_count": 5, "critical_count": 2},
        {"approver_id": 3, "approver_name": "Bob Director", "overdue_count": 5, "critical_count": 1},
    ]
    
    # Mock breakdown by department
    by_department = [
        {"department_id": 100, "department_name": "Engineering", "overdue_count": 5},
        {"department_id": 101, "department_name": "Sales", "overdue_count": 5},
        {"department_id": 102, "department_name": "Marketing", "overdue_count": 5},
    ]
    
    # Impact analysis
    total_affected_employees = len(set(r.employee_id for r in overdue_requests))
    total_affected_days = sum(r.days_requested for r in overdue_requests)
    high_impact_count = sum(1 for r in overdue_requests if r.impact_level in [ImpactLevel.HIGH, ImpactLevel.CRITICAL])
    
    return OverdueAnalyticsResponse(
        total_overdue=total_requests,
        critical_count=critical_count,
        high_count=high_count,
        medium_count=medium_count,
        low_count=low_count,
        overdue_requests=paginated_requests,
        escalation_recommendations=escalation_recommendations,
        by_approver=by_approver,
        by_department=by_department,
        total_affected_employees=total_affected_employees,
        total_affected_days=total_affected_days,
        high_impact_requests=high_impact_count,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        as_of=now,
    )


# =============================================================================
# Summary Endpoint
# =============================================================================

@approval_analytics_router.get(
    "/summary",
    response_model=ApprovalSummaryResponse,
    summary="Get real-time approval summary",
    description="Provides real-time summary with pending counts, overdue items, and team impact.",
)
async def get_approval_summary(
    department_id: Optional[int] = Query(default=None, description="Filter by department"),
    manager_id: Optional[int] = Query(default=None, description="Filter by manager (for direct reports)"),
    include_trends: bool = Query(default=True, description="Include trend comparisons"),
    include_team_impact: bool = Query(default=True, description="Include team impact analysis"),
):
    """
    Get real-time approval summary for dashboards.
    
    This endpoint provides:
    - Current pending and overdue counts
    - Breakdown by request type
    - Team impact analysis
    - Trend comparisons
    - Active alerts
    
    **Access Control**: Managers, HR, and administrators can access summaries.
    """
    current_user = get_current_user()
    
    if not validate_analytics_access(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to approval summaries",
        )
    
    now = datetime.utcnow()
    today = date.today()
    
    # Mock pending by type
    pending_by_type = [
        PendingCountByType(
            request_type="PTO",
            count=12,
            total_days=28.5,
            oldest_request_date=today - timedelta(days=3),
        ),
        PendingCountByType(
            request_type="Sick Leave",
            count=3,
            total_days=5.0,
            oldest_request_date=today - timedelta(days=1),
        ),
        PendingCountByType(
            request_type="Personal",
            count=5,
            total_days=8.0,
            oldest_request_date=today - timedelta(days=4),
        ),
    ]
    
    # Mock team impact
    team_impact = []
    if include_team_impact:
        team_impact = [
            TeamImpactSummary(
                team_id=100,
                team_name="Engineering",
                pending_count=8,
                overdue_count=2,
                employees_waiting=7,
                coverage_impact="Low - adequate coverage",
            ),
            TeamImpactSummary(
                team_id=101,
                team_name="Sales",
                pending_count=6,
                overdue_count=1,
                employees_waiting=5,
                coverage_impact="Moderate - monitor closely",
            ),
            TeamImpactSummary(
                team_id=102,
                team_name="Marketing",
                pending_count=6,
                overdue_count=1,
                employees_waiting=4,
                coverage_impact="Low - adequate coverage",
            ),
        ]
    
    # Mock trends
    trends = []
    if include_trends:
        trends = [
            TrendComparison(
                metric_name="Pending Requests",
                current_value=20,
                previous_value=18,
                change_percentage=11.1,
                trend=TrendDirection.UP,
            ),
            TrendComparison(
                metric_name="Approval Rate",
                current_value=82.5,
                previous_value=80.0,
                change_percentage=3.1,
                trend=TrendDirection.UP,
            ),
            TrendComparison(
                metric_name="Avg Decision Time (hrs)",
                current_value=16.5,
                previous_value=18.0,
                change_percentage=-8.3,
                trend=TrendDirection.DOWN,
            ),
            TrendComparison(
                metric_name="Overdue Requests",
                current_value=4,
                previous_value=6,
                change_percentage=-33.3,
                trend=TrendDirection.DOWN,
            ),
        ]
    
    # Mock alerts
    alerts = [
        {
            "alert_id": "ALT-001",
            "type": "overdue",
            "severity": "high",
            "message": "2 requests are critically overdue (>72 hours)",
            "created_at": (now - timedelta(hours=2)).isoformat(),
        },
        {
            "alert_id": "ALT-002",
            "type": "coverage",
            "severity": "medium",
            "message": "Sales team may have coverage issues next week",
            "created_at": (now - timedelta(hours=6)).isoformat(),
        },
    ]
    
    return ApprovalSummaryResponse(
        total_pending=20,
        total_overdue=4,
        pending_today=5,
        decisions_today=12,
        urgent_items=2,
        auto_escalation_pending=1,
        pending_by_type=pending_by_type,
        team_impact=team_impact,
        trends=trends,
        approval_rate_today=83.3,
        average_decision_time_today=14.5,
        alerts=alerts,
        as_of=now,
    )


