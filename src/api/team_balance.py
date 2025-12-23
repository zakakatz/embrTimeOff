"""API endpoints for team and department balance management."""

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.schemas.team_balance import (
    TeamBalanceResponse,
    TeamMemberBalance,
    TeamBalanceSummary,
    TeamAvailabilityPeriod,
    CoverageRiskInfo,
    CoverageRiskLevel,
    DepartmentBalanceResponse,
    DepartmentBalanceSummary,
    PolicyUsageMetric,
    BalanceDistribution,
    UsagePattern,
    TrendAnalysis,
    TrendDataPoint,
    ComparativeMetric,
    UsageTrend,
    SortField,
    SortOrder,
)
from src.schemas.balance_inquiry import BalanceStatusEnum


team_balance_router = APIRouter(prefix="/api/time-off/balances", tags=["Team & Department Balances"])


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
        "is_hr": False,
        "is_senior_manager": False,
        "direct_reports": [101, 102, 103, 104, 105],
    }


def validate_manager_access(user: Dict[str, Any], team_member_ids: List[int]) -> bool:
    """Validate that the user has manager access to the specified team members."""
    if user.get("role") == "admin":
        return True
    if user.get("role") == "manager":
        direct_reports = user.get("direct_reports", [])
        return all(member_id in direct_reports for member_id in team_member_ids)
    return False


def validate_department_access(user: Dict[str, Any], department_id: int) -> bool:
    """Validate that the user has access to department-level data."""
    # HR personnel have access to all departments
    if user.get("is_hr"):
        return True
    # Senior managers have access to their own department hierarchy
    if user.get("is_senior_manager"):
        # In a real implementation, check department hierarchy
        return True
    # Regular managers only have access to their own department
    if user.get("role") == "manager" and user.get("department_id") == department_id:
        return True
    # Admins have full access
    if user.get("role") == "admin":
        return True
    return False


def calculate_coverage_risk(
    team_members: List[TeamMemberBalance],
    analysis_days: int,
) -> CoverageRiskInfo:
    """Calculate coverage risk based on team member availability."""
    risk_factors = []
    affected_dates = []
    recommendations = []
    
    # Mock risk calculation
    pending_count = sum(len(m.pending_requests) for m in team_members)
    low_balance_count = sum(1 for m in team_members if m.balance_status == BalanceStatusEnum.LOW)
    critical_count = sum(1 for m in team_members if m.balance_status == BalanceStatusEnum.CRITICAL)
    
    risk_score = 0.0
    
    if pending_count > 2:
        risk_factors.append(f"{pending_count} pending time-off requests")
        risk_score += 20
    
    if low_balance_count > 0:
        risk_factors.append(f"{low_balance_count} team members with low balance")
        risk_score += 10 * low_balance_count
    
    if critical_count > 0:
        risk_factors.append(f"{critical_count} team members with critical balance")
        risk_score += 15 * critical_count
        recommendations.append("Review critical balance situations with affected team members")
    
    # Determine risk level
    if risk_score >= 60:
        risk_level = CoverageRiskLevel.CRITICAL
        recommendations.append("Immediate attention required for coverage planning")
    elif risk_score >= 40:
        risk_level = CoverageRiskLevel.HIGH
        recommendations.append("Consider proactive coverage planning")
    elif risk_score >= 20:
        risk_level = CoverageRiskLevel.MEDIUM
        recommendations.append("Monitor upcoming time-off requests closely")
    else:
        risk_level = CoverageRiskLevel.LOW
    
    return CoverageRiskInfo(
        risk_level=risk_level,
        risk_score=min(100, risk_score),
        risk_factors=risk_factors,
        affected_dates=affected_dates,
        recommendations=recommendations,
    )


def generate_coverage_analysis(
    team_members: List[TeamMemberBalance],
    days_ahead: int,
) -> List[TeamAvailabilityPeriod]:
    """Generate coverage analysis for upcoming periods."""
    analysis = []
    today = date.today()
    total_members = len(team_members)
    
    # Generate weekly analysis
    for week in range(0, days_ahead // 7 + 1):
        start_date = today + timedelta(days=week * 7)
        end_date = start_date + timedelta(days=6)
        
        # Mock calculation - in real implementation, check actual schedules
        members_on_leave = week % 3  # Mock data
        members_pending = 1 if week > 1 else 0
        available = total_members - members_on_leave - members_pending
        
        availability_pct = (available / total_members * 100) if total_members > 0 else 100
        
        if availability_pct >= 80:
            risk = CoverageRiskLevel.LOW
        elif availability_pct >= 60:
            risk = CoverageRiskLevel.MEDIUM
        elif availability_pct >= 40:
            risk = CoverageRiskLevel.HIGH
        else:
            risk = CoverageRiskLevel.CRITICAL
        
        analysis.append(TeamAvailabilityPeriod(
            start_date=start_date,
            end_date=end_date,
            total_team_members=total_members,
            available_members=available,
            members_on_leave=members_on_leave,
            members_pending_leave=members_pending,
            availability_percentage=round(availability_pct, 1),
            coverage_risk=risk,
        ))
    
    return analysis


# =============================================================================
# Team Balance Endpoint
# =============================================================================

@team_balance_router.get(
    "/team",
    response_model=TeamBalanceResponse,
    summary="Get team balance summary",
    description="Returns team balance summaries for managers including direct report balance information, "
                "team availability analysis, and coverage planning support.",
)
async def get_team_balances(
    policy_id: Optional[int] = Query(default=None, description="Filter by policy ID"),
    balance_status: Optional[BalanceStatusEnum] = Query(default=None, description="Filter by balance status"),
    has_pending_requests: Optional[bool] = Query(default=None, description="Filter by pending requests"),
    min_available_balance: Optional[float] = Query(default=None, ge=0, description="Minimum available balance"),
    max_available_balance: Optional[float] = Query(default=None, ge=0, description="Maximum available balance"),
    coverage_analysis_days: int = Query(default=30, ge=7, le=90, description="Days to analyze for coverage"),
    sort_by: SortField = Query(default=SortField.EMPLOYEE_NAME, description="Sort field"),
    sort_order: SortOrder = Query(default=SortOrder.ASC, description="Sort order"),
    include_upcoming_accruals: bool = Query(default=True, description="Include accrual information"),
):
    """
    Get team balance summary for the current manager.
    
    This endpoint provides:
    - Balance information for all direct reports
    - Team availability analysis
    - Coverage risk assessment
    - Summary statistics
    
    **Access Control**: Only managers can access this endpoint for their direct reports.
    """
    current_user = get_current_user()
    
    # Validate manager role
    if current_user.get("role") not in ["manager", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only managers can access team balance information",
        )
    
    # Get direct reports
    direct_report_ids = current_user.get("direct_reports", [])
    if not direct_report_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No direct reports found for this manager",
        )
    
    # Mock team member data
    team_members = []
    for i, emp_id in enumerate(direct_report_ids):
        available = 15.0 - (i * 2)
        pending = 2.0 if i % 2 == 0 else 0.0
        used = 5.0 + i
        
        # Determine status
        if available >= 10:
            status_val = BalanceStatusEnum.HEALTHY
            status_msg = "Balance is healthy"
        elif available >= 5:
            status_val = BalanceStatusEnum.LOW
            status_msg = "Balance is getting low"
        else:
            status_val = BalanceStatusEnum.CRITICAL
            status_msg = "Balance is critically low"
        
        member = TeamMemberBalance(
            employee_id=emp_id,
            employee_name=f"Employee {emp_id}",
            job_title=f"Software Engineer {i + 1}",
            department="Engineering",
            total_available=available,
            total_pending=pending,
            total_used_ytd=used,
            policy_balances=[
                {
                    "policy_id": 1,
                    "policy_name": "PTO",
                    "available": available * 0.6,
                    "pending": pending * 0.6,
                },
                {
                    "policy_id": 2,
                    "policy_name": "Sick Leave",
                    "available": available * 0.4,
                    "pending": pending * 0.4,
                },
            ],
            balance_status=status_val,
            status_message=status_msg,
            upcoming_time_off=[
                {
                    "start_date": (date.today() + timedelta(days=10 + i * 5)).isoformat(),
                    "end_date": (date.today() + timedelta(days=12 + i * 5)).isoformat(),
                    "days": 2,
                    "type": "PTO",
                }
            ] if i % 2 == 0 else [],
            pending_requests=[
                {
                    "request_id": 1000 + i,
                    "days_requested": pending,
                    "submitted_at": datetime.utcnow().isoformat(),
                }
            ] if pending > 0 else [],
            next_accrual_date=date.today() + timedelta(days=30) if include_upcoming_accruals else None,
            next_accrual_amount=1.25 if include_upcoming_accruals else 0,
        )
        team_members.append(member)
    
    # Apply filters
    if balance_status:
        team_members = [m for m in team_members if m.balance_status == balance_status]
    
    if has_pending_requests is not None:
        if has_pending_requests:
            team_members = [m for m in team_members if m.total_pending > 0]
        else:
            team_members = [m for m in team_members if m.total_pending == 0]
    
    if min_available_balance is not None:
        team_members = [m for m in team_members if m.total_available >= min_available_balance]
    
    if max_available_balance is not None:
        team_members = [m for m in team_members if m.total_available <= max_available_balance]
    
    # Sort
    reverse = sort_order == SortOrder.DESC
    if sort_by == SortField.EMPLOYEE_NAME:
        team_members.sort(key=lambda m: m.employee_name, reverse=reverse)
    elif sort_by == SortField.AVAILABLE_BALANCE:
        team_members.sort(key=lambda m: m.total_available, reverse=reverse)
    elif sort_by == SortField.PENDING_REQUESTS:
        team_members.sort(key=lambda m: m.total_pending, reverse=reverse)
    elif sort_by == SortField.BALANCE_STATUS:
        status_order = {BalanceStatusEnum.CRITICAL: 0, BalanceStatusEnum.LOW: 1, BalanceStatusEnum.HEALTHY: 2}
        team_members.sort(key=lambda m: status_order.get(m.balance_status, 3), reverse=reverse)
    
    # Calculate summary
    total_available = sum(m.total_available for m in team_members)
    total_pending = sum(m.total_pending for m in team_members)
    pending_count = sum(1 for m in team_members if m.total_pending > 0)
    
    summary = TeamBalanceSummary(
        total_team_members=len(team_members),
        total_available_balance=total_available,
        average_available_balance=total_available / len(team_members) if team_members else 0,
        total_pending_requests=total_pending,
        pending_request_count=pending_count,
        members_with_healthy_balance=sum(1 for m in team_members if m.balance_status == BalanceStatusEnum.HEALTHY),
        members_with_low_balance=sum(1 for m in team_members if m.balance_status == BalanceStatusEnum.LOW),
        members_with_critical_balance=sum(1 for m in team_members if m.balance_status == BalanceStatusEnum.CRITICAL),
        total_upcoming_accruals=sum(m.next_accrual_amount for m in team_members),
        members_with_upcoming_accruals=sum(1 for m in team_members if m.next_accrual_amount > 0),
    )
    
    # Generate coverage analysis
    coverage_analysis = generate_coverage_analysis(team_members, coverage_analysis_days)
    
    # Calculate coverage risk
    coverage_risk = calculate_coverage_risk(team_members, coverage_analysis_days)
    
    # Build filters applied
    filters_applied = {}
    if policy_id:
        filters_applied["policy_id"] = policy_id
    if balance_status:
        filters_applied["balance_status"] = balance_status.value
    if has_pending_requests is not None:
        filters_applied["has_pending_requests"] = has_pending_requests
    if min_available_balance is not None:
        filters_applied["min_available_balance"] = min_available_balance
    if max_available_balance is not None:
        filters_applied["max_available_balance"] = max_available_balance
    
    return TeamBalanceResponse(
        manager_id=current_user["id"],
        manager_name=current_user["name"],
        team_members=team_members,
        summary=summary,
        coverage_analysis=coverage_analysis,
        coverage_risk=coverage_risk,
        filters=filters_applied,
        as_of_date=date.today(),
        retrieved_at=datetime.utcnow(),
    )


# =============================================================================
# Department Balance Endpoint
# =============================================================================

@team_balance_router.get(
    "/department/{department_id}",
    response_model=DepartmentBalanceResponse,
    summary="Get department balance analytics",
    description="Provides department-level balance analytics including aggregate balance information, "
                "usage patterns, policy effectiveness metrics, and trend analysis.",
)
async def get_department_balances(
    department_id: int,
    year: Optional[int] = Query(default=None, description="Year for data (defaults to current year)"),
    include_sub_departments: bool = Query(default=False, description="Include sub-department data"),
    policy_ids: Optional[str] = Query(default=None, description="Comma-separated policy IDs to filter"),
    include_trends: bool = Query(default=True, description="Include trend analysis"),
    include_comparisons: bool = Query(default=True, description="Include comparative metrics"),
    usage_pattern_granularity: str = Query(default="monthly", description="Pattern granularity: monthly, quarterly"),
):
    """
    Get department-level balance analytics.
    
    This endpoint provides:
    - Aggregate balance information
    - Usage patterns by policy
    - Policy effectiveness metrics
    - Balance distribution analysis
    - Trend analysis and forecasting
    - Comparative reporting
    
    **Access Control**: HR personnel and senior managers can access this endpoint.
    """
    current_user = get_current_user()
    
    # Validate access
    if not validate_department_access(current_user, department_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this department's balance data",
        )
    
    # Parse policy IDs if provided
    filter_policy_ids = None
    if policy_ids:
        try:
            filter_policy_ids = [int(pid.strip()) for pid in policy_ids.split(",")]
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid policy_ids format. Use comma-separated integers.",
            )
    
    # Default to current year
    data_year = year or date.today().year
    
    # Mock department data
    department_name = f"Department {department_id}"
    department_code = f"DEPT-{department_id}"
    
    # Mock summary
    total_employees = 50
    summary = DepartmentBalanceSummary(
        total_employees=total_employees,
        total_available_balance=625.0,
        average_available_balance=12.5,
        total_pending_days=45.0,
        total_used_ytd=280.0,
        employees_healthy_balance=35,
        employees_low_balance=10,
        employees_critical_balance=5,
        total_upcoming_accruals=62.5,
        average_accrual_utilization=0.72,
    )
    
    # Mock policy metrics
    policy_metrics = [
        PolicyUsageMetric(
            policy_id=1,
            policy_name="Paid Time Off",
            policy_code="PTO",
            total_allocated=750.0,
            total_used=200.0,
            total_available=520.0,
            total_pending=30.0,
            utilization_rate=26.7,
            accrual_utilization_rate=0.68,
            employees_enrolled=48,
            employees_used=35,
            effectiveness_score=85.5,
        ),
        PolicyUsageMetric(
            policy_id=2,
            policy_name="Sick Leave",
            policy_code="SICK",
            total_allocated=250.0,
            total_used=80.0,
            total_available=155.0,
            total_pending=15.0,
            utilization_rate=32.0,
            accrual_utilization_rate=0.78,
            employees_enrolled=50,
            employees_used=25,
            effectiveness_score=92.0,
        ),
    ]
    
    # Filter by policy IDs if specified
    if filter_policy_ids:
        policy_metrics = [pm for pm in policy_metrics if pm.policy_id in filter_policy_ids]
    
    # Mock balance distribution
    balance_distribution = BalanceDistribution(
        min_balance=2.0,
        max_balance=25.0,
        mean_balance=12.5,
        median_balance=11.0,
        std_deviation=4.2,
        percentile_25=8.5,
        percentile_75=16.0,
        percentile_90=20.0,
        distribution_buckets=[
            {"range": "0-5", "count": 8, "percentage": 16.0},
            {"range": "5-10", "count": 12, "percentage": 24.0},
            {"range": "10-15", "count": 18, "percentage": 36.0},
            {"range": "15-20", "count": 9, "percentage": 18.0},
            {"range": "20+", "count": 3, "percentage": 6.0},
        ],
    )
    
    # Mock usage patterns
    usage_patterns = []
    if usage_pattern_granularity == "monthly":
        months = ["January", "February", "March", "April", "May", "June",
                  "July", "August", "September", "October", "November", "December"]
        for i, month in enumerate(months[:date.today().month]):
            usage_patterns.append(UsagePattern(
                period=month,
                total_requests=15 + (i % 5) * 3,
                total_days_requested=45.0 + (i % 5) * 10,
                average_request_length=3.0 + (i % 3) * 0.5,
                peak_usage_dates=[
                    date(data_year, i + 1, 15),
                    date(data_year, i + 1, 20),
                ],
                trend=UsageTrend.INCREASING if i > 6 else UsageTrend.STABLE,
            ))
    else:  # quarterly
        quarters = ["Q1", "Q2", "Q3", "Q4"]
        current_quarter = (date.today().month - 1) // 3 + 1
        for i, quarter in enumerate(quarters[:current_quarter]):
            usage_patterns.append(UsagePattern(
                period=quarter,
                total_requests=45 + i * 10,
                total_days_requested=150.0 + i * 30,
                average_request_length=3.3 + i * 0.2,
                peak_usage_dates=[],
                trend=UsageTrend.STABLE,
            ))
    
    # Mock trends
    trends = []
    if include_trends:
        # Balance trend
        balance_trend_points = []
        for i in range(6):
            month_date = date(data_year, max(1, date.today().month - 5 + i), 1)
            balance_trend_points.append(TrendDataPoint(
                period=month_date.strftime("%B"),
                date=month_date,
                value=600.0 + i * 10 + (i % 2) * 5,
                change_from_previous=10.0 if i > 0 else None,
            ))
        
        trends.append(TrendAnalysis(
            metric_name="Total Available Balance",
            trend_direction=UsageTrend.STABLE,
            data_points=balance_trend_points,
            forecast_next_period=650.0,
            year_over_year_change=5.2,
        ))
        
        # Utilization trend
        util_trend_points = []
        for i in range(6):
            month_date = date(data_year, max(1, date.today().month - 5 + i), 1)
            util_trend_points.append(TrendDataPoint(
                period=month_date.strftime("%B"),
                date=month_date,
                value=25.0 + i * 2,
                change_from_previous=2.0 if i > 0 else None,
            ))
        
        trends.append(TrendAnalysis(
            metric_name="Utilization Rate",
            trend_direction=UsageTrend.INCREASING,
            data_points=util_trend_points,
            forecast_next_period=38.0,
            year_over_year_change=8.5,
        ))
    
    # Mock comparative metrics
    comparative_metrics = []
    if include_comparisons:
        comparative_metrics = [
            ComparativeMetric(
                metric_name="Average Balance Per Employee",
                department_value=12.5,
                company_average=11.8,
                industry_benchmark=12.0,
                variance_from_average=5.9,
                performance_indicator="above",
            ),
            ComparativeMetric(
                metric_name="Utilization Rate",
                department_value=26.7,
                company_average=30.5,
                industry_benchmark=28.0,
                variance_from_average=-12.5,
                performance_indicator="below",
            ),
            ComparativeMetric(
                metric_name="Accrual Utilization",
                department_value=72.0,
                company_average=68.0,
                industry_benchmark=70.0,
                variance_from_average=5.9,
                performance_indicator="above",
            ),
        ]
    
    # Mock sub-department summaries
    sub_department_summaries = []
    if include_sub_departments:
        sub_department_summaries = [
            {
                "department_id": department_id * 10 + 1,
                "department_name": f"Sub-Department {department_id}-A",
                "employee_count": 20,
                "total_available": 250.0,
                "utilization_rate": 28.5,
            },
            {
                "department_id": department_id * 10 + 2,
                "department_name": f"Sub-Department {department_id}-B",
                "employee_count": 30,
                "total_available": 375.0,
                "utilization_rate": 25.2,
            },
        ]
    
    return DepartmentBalanceResponse(
        department_id=department_id,
        department_name=department_name,
        department_code=department_code,
        summary=summary,
        policy_metrics=policy_metrics,
        balance_distribution=balance_distribution,
        usage_patterns=usage_patterns,
        trends=trends,
        comparative_metrics=comparative_metrics,
        sub_department_summaries=sub_department_summaries,
        year=data_year,
        as_of_date=date.today(),
        retrieved_at=datetime.utcnow(),
    )


