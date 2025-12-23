"""API endpoints for approval contextual information."""

import uuid
import logging
from datetime import date, datetime, timedelta
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.models.employee import Employee
from src.models.time_off_request import TimeOffRequest, TimeOffRequestStatus
from src.schemas.approval_context import (
    ApprovalContextResponse,
    TeamCalendarResponse,
    ConflictDetail,
    ConflictSummary,
    ConflictTypeEnum,
    ImpactLevelEnum,
    CoverageAnalysis,
    CoverageStatusEnum,
    DailyCoverage,
    PolicyAnalysis,
    PolicyCheck,
    PolicyComplianceEnum,
    BalanceProjection,
    HistoricalPattern,
    OrganizationalEvent,
    TeamMemberInfo,
    TeamMemberAvailability,
    CalendarEntry,
)
from src.utils.auth import CurrentUser, UserRole, get_mock_current_user

logger = logging.getLogger(__name__)


# =============================================================================
# Router Setup
# =============================================================================

approval_context_router = APIRouter(
    prefix="/api/time-off/approvals",
    tags=["Approval Context"],
)


# =============================================================================
# Dependencies
# =============================================================================

def get_current_user(
    request: Request,
    x_user_id: Annotated[Optional[str], Header(alias="X-User-ID")] = None,
    x_employee_id: Annotated[Optional[int], Header(alias="X-Employee-ID")] = None,
    x_user_role: Annotated[Optional[str], Header(alias="X-User-Role")] = None,
) -> CurrentUser:
    """Get current user from request headers."""
    user_id = None
    if x_user_id:
        try:
            user_id = uuid.UUID(x_user_id)
        except ValueError:
            pass
    
    roles = [UserRole.MANAGER]
    if x_user_role:
        try:
            roles = [UserRole(x_user_role)]
        except ValueError:
            pass
    
    return get_mock_current_user(
        user_id=user_id,
        employee_id=x_employee_id or 2,
        roles=roles,
    )


# =============================================================================
# Helper Functions
# =============================================================================

def get_team_members(manager_id: int, session: Session) -> List[Employee]:
    """Get all team members under a manager."""
    stmt = select(Employee).where(Employee.manager_id == manager_id)
    return list(session.execute(stmt).scalars().all())


def analyze_conflicts(
    request: TimeOffRequest,
    team_members: List[Employee],
    session: Session,
) -> tuple[List[ConflictDetail], ConflictSummary]:
    """Analyze conflicts with team members."""
    conflicts = []
    
    # Get time-off requests from team members in overlapping period
    for member in team_members:
        if member.id == request.employee_id:
            continue
        
        stmt = select(TimeOffRequest).where(
            TimeOffRequest.employee_id == member.id,
            TimeOffRequest.status.in_([
                TimeOffRequestStatus.APPROVED.value,
                TimeOffRequestStatus.PENDING_APPROVAL.value,
            ]),
            TimeOffRequest.start_date <= request.end_date,
            TimeOffRequest.end_date >= request.start_date,
        )
        overlapping = session.execute(stmt).scalars().all()
        
        for other_req in overlapping:
            # Calculate overlap
            overlap_start = max(request.start_date, other_req.start_date)
            overlap_end = min(request.end_date, other_req.end_date)
            overlap_days = (overlap_end - overlap_start).days + 1
            
            # Generate overlap dates
            overlap_dates = [
                overlap_start + timedelta(days=i)
                for i in range(overlap_days)
            ]
            
            # Determine impact level
            impact_level = ImpactLevelEnum.LOW
            if overlap_days > 3:
                impact_level = ImpactLevelEnum.MEDIUM
            if overlap_days > 5:
                impact_level = ImpactLevelEnum.HIGH
            
            conflicts.append(ConflictDetail(
                conflict_id=str(uuid.uuid4()),
                conflict_type=ConflictTypeEnum.OVERLAP,
                conflicting_employee=TeamMemberInfo(
                    id=member.id,
                    employee_id=member.employee_id,
                    name=f"{member.first_name} {member.last_name}",
                    job_title=member.job_title,
                    is_critical_function=False,
                    functions=[],
                ),
                overlap_dates=overlap_dates,
                total_overlap_days=overlap_days,
                impact_level=impact_level,
                impact_description=f"{overlap_days} days overlap with {member.first_name}",
                resolution_options=[
                    "Adjust request dates",
                    "Coordinate coverage plan",
                    "Stagger time-off periods",
                ],
            ))
    
    # Build summary
    critical_count = sum(1 for c in conflicts if c.impact_level == ImpactLevelEnum.CRITICAL)
    high_count = sum(1 for c in conflicts if c.impact_level == ImpactLevelEnum.HIGH)
    
    overall_impact = ImpactLevelEnum.LOW
    if critical_count > 0:
        overall_impact = ImpactLevelEnum.CRITICAL
    elif high_count > 0:
        overall_impact = ImpactLevelEnum.HIGH
    elif len(conflicts) > 2:
        overall_impact = ImpactLevelEnum.MEDIUM
    
    recommendation = "No significant conflicts detected"
    if overall_impact == ImpactLevelEnum.CRITICAL:
        recommendation = "Consider denying or requesting alternative dates"
    elif overall_impact == ImpactLevelEnum.HIGH:
        recommendation = "Review coverage plan before approving"
    elif overall_impact == ImpactLevelEnum.MEDIUM:
        recommendation = "Minor conflicts - consider team workload"
    
    summary = ConflictSummary(
        total_conflicts=len(conflicts),
        critical_conflicts=critical_count,
        high_conflicts=high_count,
        conflicts_by_type={ConflictTypeEnum.OVERLAP.value: len(conflicts)},
        overall_impact=overall_impact,
        recommendation=recommendation,
    )
    
    return conflicts, summary


def analyze_coverage(
    request: TimeOffRequest,
    team_members: List[Employee],
    session: Session,
) -> CoverageAnalysis:
    """Analyze team coverage during requested period."""
    daily_coverage = []
    critical_days = []
    days_below_minimum = 0
    
    minimum_required = max(1, len(team_members) // 2)  # 50% minimum
    
    current_date = request.start_date
    while current_date <= request.end_date:
        is_workday = current_date.weekday() < 5
        
        if is_workday:
            # Count available team members
            available_count = len(team_members)
            absent_employees = []
            
            for member in team_members:
                # Check if member has approved time-off
                stmt = select(TimeOffRequest).where(
                    TimeOffRequest.employee_id == member.id,
                    TimeOffRequest.status == TimeOffRequestStatus.APPROVED.value,
                    TimeOffRequest.start_date <= current_date,
                    TimeOffRequest.end_date >= current_date,
                )
                is_absent = session.execute(stmt).scalars().first() is not None
                
                if is_absent:
                    available_count -= 1
                    absent_employees.append(f"{member.first_name} {member.last_name}")
            
            # Subtract the requesting employee
            available_count -= 1
            
            # Determine status
            if available_count >= minimum_required:
                coverage_status = CoverageStatusEnum.ADEQUATE
            elif available_count >= minimum_required - 1:
                coverage_status = CoverageStatusEnum.MARGINAL
            elif available_count > 0:
                coverage_status = CoverageStatusEnum.INSUFFICIENT
                days_below_minimum += 1
            else:
                coverage_status = CoverageStatusEnum.CRITICAL
                days_below_minimum += 1
                critical_days.append(current_date)
            
            daily_coverage.append(DailyCoverage(
                date=current_date,
                is_workday=True,
                total_team_size=len(team_members),
                available_count=available_count,
                minimum_required=minimum_required,
                coverage_status=coverage_status,
                critical_functions_covered=available_count > 0,
                absent_employees=absent_employees,
            ))
        
        current_date += timedelta(days=1)
    
    # Determine overall status
    overall_status = CoverageStatusEnum.ADEQUATE
    if critical_days:
        overall_status = CoverageStatusEnum.CRITICAL
    elif days_below_minimum > 0:
        overall_status = CoverageStatusEnum.INSUFFICIENT
    elif any(dc.coverage_status == CoverageStatusEnum.MARGINAL for dc in daily_coverage):
        overall_status = CoverageStatusEnum.MARGINAL
    
    # Build warnings
    warnings = []
    if days_below_minimum > 0:
        warnings.append(f"{days_below_minimum} days will be below minimum staffing")
    if critical_days:
        warnings.append(f"Critical coverage issues on: {', '.join(str(d) for d in critical_days[:3])}")
    
    impact = "Minimal impact on team operations"
    if overall_status == CoverageStatusEnum.CRITICAL:
        impact = "Significant negative impact on team operations expected"
    elif overall_status == CoverageStatusEnum.INSUFFICIENT:
        impact = "Some team functions may be affected"
    elif overall_status == CoverageStatusEnum.MARGINAL:
        impact = "Team will operate at reduced capacity"
    
    return CoverageAnalysis(
        analysis_period_start=request.start_date,
        analysis_period_end=request.end_date,
        daily_coverage=daily_coverage,
        overall_status=overall_status,
        days_below_minimum=days_below_minimum,
        critical_days=critical_days,
        warnings=warnings,
        impact_assessment=impact,
    )


def analyze_policies(
    request: TimeOffRequest,
    session: Session,
) -> PolicyAnalysis:
    """Analyze policy compliance for the request."""
    policy_checks = []
    blocking_issues = []
    warnings = []
    
    # Check advance notice
    days_notice = (request.start_date - datetime.now().date()).days
    notice_status = PolicyComplianceEnum.COMPLIANT
    if days_notice < 14:
        notice_status = PolicyComplianceEnum.WARNING
        warnings.append("Request submitted with less than 2 weeks notice")
    if days_notice < 2:
        notice_status = PolicyComplianceEnum.VIOLATION
        blocking_issues.append("Insufficient advance notice")
    
    policy_checks.append(PolicyCheck(
        policy_id="notice",
        policy_name="Advance Notice Requirement",
        rule_description="Vacation requests require 2 weeks advance notice",
        compliance_status=notice_status,
        details=f"Submitted {days_notice} days in advance",
    ))
    
    # Check consecutive days
    consecutive_status = PolicyComplianceEnum.COMPLIANT
    if request.total_days > 10:
        consecutive_status = PolicyComplianceEnum.EXCEPTION_REQUIRED
        warnings.append("Request exceeds 10 consecutive days - requires HR approval")
    elif request.total_days > 5:
        consecutive_status = PolicyComplianceEnum.WARNING
        warnings.append("Extended leave request - consider coverage plan")
    
    policy_checks.append(PolicyCheck(
        policy_id="consecutive",
        policy_name="Extended Leave Policy",
        rule_description="Requests over 10 days require HR approval",
        compliance_status=consecutive_status,
        details=f"Requesting {request.total_days} days",
    ))
    
    # Check blackout periods (mock)
    policy_checks.append(PolicyCheck(
        policy_id="blackout",
        policy_name="Blackout Period Policy",
        rule_description="No time-off during critical business periods",
        compliance_status=PolicyComplianceEnum.COMPLIANT,
        details="No blackout periods affected",
    ))
    
    # Balance projection
    current_balance = request.balance_before or 15.0
    projected_balance = current_balance - request.total_days
    
    balance_projection = BalanceProjection(
        balance_type=request.request_type,
        current_balance=current_balance,
        requested_amount=request.total_days,
        projected_balance=projected_balance,
        projected_year_end_balance=projected_balance + 2.0,  # Mock accruals
        accruals_remaining=2.0,
        is_sufficient=projected_balance >= 0,
    )
    
    if not balance_projection.is_sufficient:
        blocking_issues.append("Insufficient balance")
        policy_checks.append(PolicyCheck(
            policy_id="balance",
            policy_name="Balance Sufficiency",
            rule_description="Must have sufficient balance",
            compliance_status=PolicyComplianceEnum.VIOLATION,
            details=f"Balance would be negative: {projected_balance}",
            required_action="Request fewer days or wait for accruals",
        ))
    
    # Determine overall compliance
    overall = PolicyComplianceEnum.COMPLIANT
    if blocking_issues:
        overall = PolicyComplianceEnum.VIOLATION
    elif any(pc.compliance_status == PolicyComplianceEnum.EXCEPTION_REQUIRED for pc in policy_checks):
        overall = PolicyComplianceEnum.EXCEPTION_REQUIRED
    elif warnings:
        overall = PolicyComplianceEnum.WARNING
    
    return PolicyAnalysis(
        policy_checks=policy_checks,
        balance_projection=balance_projection,
        overall_compliance=overall,
        blocking_issues=blocking_issues,
        warnings=warnings,
        exceptions_required=[],
    )


def get_organizational_events(
    start_date: date,
    end_date: date,
) -> List[OrganizationalEvent]:
    """Get organizational events in the period."""
    # Mock organizational events
    events = []
    
    # Check for common events (this would come from database in production)
    # Example: end of quarter
    for month_end in [3, 6, 9, 12]:
        month_end_date = date(start_date.year, month_end, 28)
        if start_date <= month_end_date <= end_date:
            events.append(OrganizationalEvent(
                event_id=f"qtr-end-{month_end}",
                event_name=f"Q{month_end // 3} Close",
                event_type="business_critical",
                start_date=month_end_date - timedelta(days=2),
                end_date=month_end_date + timedelta(days=2),
                is_mandatory=False,
                overlap_days=[month_end_date],
                impact="medium",
            ))
    
    return events


def get_historical_patterns(
    employee_id: int,
    session: Session,
) -> List[HistoricalPattern]:
    """Get historical patterns for the employee."""
    return [
        HistoricalPattern(
            pattern_type="request_frequency",
            description="Employee typically requests time-off quarterly",
            frequency="quarterly",
            relevance="informational",
        ),
        HistoricalPattern(
            pattern_type="approval_rate",
            description="Historical approval rate: 95%",
            frequency="overall",
            relevance="informational",
        ),
    ]


# =============================================================================
# Endpoints
# =============================================================================

@approval_context_router.get(
    "/{request_id}/context",
    response_model=ApprovalContextResponse,
    summary="Get approval context",
    description="Aggregates comprehensive contextual information for approval decision.",
)
async def get_approval_context(
    request_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    include_conflicts: bool = Query(default=True, description="Include conflict analysis"),
    include_coverage: bool = Query(default=True, description="Include coverage analysis"),
    include_policy: bool = Query(default=True, description="Include policy analysis"),
    include_history: bool = Query(default=True, description="Include historical patterns"),
    include_events: bool = Query(default=True, description="Include organizational events"),
) -> ApprovalContextResponse:
    """
    Get comprehensive contextual information for an approval decision.
    
    Aggregates data from multiple sources:
    - Team calendars for conflict identification
    - Organizational charts for coverage analysis
    - Policy configurations for compliance checks
    - Historical patterns for decision support
    """
    manager_id = current_user.employee_id or 2
    
    # Get the request
    time_off_request = session.get(TimeOffRequest, request_id)
    if not time_off_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Time-off request {request_id} not found",
        )
    
    # Get employee info
    employee = session.get(Employee, time_off_request.employee_id)
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found",
        )
    
    # Get team members
    team_members = get_team_members(employee.manager_id or manager_id, session)
    
    # Analyze conflicts
    conflicts = []
    conflict_summary = ConflictSummary(
        total_conflicts=0,
        critical_conflicts=0,
        high_conflicts=0,
        conflicts_by_type={},
        overall_impact=ImpactLevelEnum.LOW,
        recommendation="No conflicts detected",
    )
    if include_conflicts:
        conflicts, conflict_summary = analyze_conflicts(time_off_request, team_members, session)
    
    # Analyze coverage
    coverage_analysis = CoverageAnalysis(
        analysis_period_start=time_off_request.start_date,
        analysis_period_end=time_off_request.end_date,
        daily_coverage=[],
        overall_status=CoverageStatusEnum.ADEQUATE,
        days_below_minimum=0,
        critical_days=[],
        warnings=[],
        impact_assessment="Coverage analysis not performed",
    )
    if include_coverage:
        coverage_analysis = analyze_coverage(time_off_request, team_members, session)
    
    # Analyze policies
    policy_analysis = PolicyAnalysis(
        policy_checks=[],
        balance_projection=BalanceProjection(
            balance_type=time_off_request.request_type,
            current_balance=15.0,
            requested_amount=time_off_request.total_days,
            projected_balance=15.0 - time_off_request.total_days,
            projected_year_end_balance=15.0,
            accruals_remaining=0,
            is_sufficient=True,
        ),
        overall_compliance=PolicyComplianceEnum.COMPLIANT,
        blocking_issues=[],
        warnings=[],
        exceptions_required=[],
    )
    if include_policy:
        policy_analysis = analyze_policies(time_off_request, session)
    
    # Get historical patterns
    historical_patterns = []
    if include_history:
        historical_patterns = get_historical_patterns(time_off_request.employee_id, session)
    
    # Get organizational events
    organizational_events = []
    if include_events:
        organizational_events = get_organizational_events(
            time_off_request.start_date,
            time_off_request.end_date,
        )
    
    # Determine recommendation
    recommendation = "approve"
    key_considerations = []
    
    if policy_analysis.blocking_issues:
        recommendation = "deny"
        key_considerations.extend(policy_analysis.blocking_issues)
    elif conflict_summary.overall_impact in [ImpactLevelEnum.CRITICAL, ImpactLevelEnum.HIGH]:
        recommendation = "review_required"
        key_considerations.append(conflict_summary.recommendation)
    elif coverage_analysis.overall_status == CoverageStatusEnum.CRITICAL:
        recommendation = "deny"
        key_considerations.append(coverage_analysis.impact_assessment)
    elif coverage_analysis.overall_status == CoverageStatusEnum.INSUFFICIENT:
        recommendation = "review_required"
        key_considerations.append(coverage_analysis.impact_assessment)
    
    # Add any warnings
    key_considerations.extend(policy_analysis.warnings[:3])
    key_considerations.extend(coverage_analysis.warnings[:2])
    
    return ApprovalContextResponse(
        request_id=request_id,
        employee_id=employee.id,
        employee_name=f"{employee.first_name} {employee.last_name}",
        request_type=time_off_request.request_type,
        start_date=time_off_request.start_date,
        end_date=time_off_request.end_date,
        total_days=time_off_request.total_days,
        conflicts=conflicts,
        conflict_summary=conflict_summary,
        coverage_analysis=coverage_analysis,
        policy_analysis=policy_analysis,
        historical_patterns=historical_patterns,
        organizational_events=organizational_events,
        approval_recommendation=recommendation,
        key_considerations=key_considerations,
        data_sources=[
            "team_calendar",
            "organizational_chart",
            "policy_engine",
            "historical_data",
            "organizational_events",
        ],
    )


@approval_context_router.get(
    "/team-calendar",
    response_model=TeamCalendarResponse,
    summary="Get team calendar",
    description="Returns team calendar with approved requests, pending approvals, and conflicts.",
)
async def get_team_calendar(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    start_date: date = Query(default=None, description="Start date (default: today)"),
    end_date: date = Query(default=None, description="End date (default: 30 days)"),
    include_pending: bool = Query(default=True, description="Include pending requests"),
    include_coverage: bool = Query(default=True, description="Include coverage analysis"),
) -> TeamCalendarResponse:
    """
    Get team calendar showing availability, conflicts, and coverage.
    
    Provides:
    - Team member availability
    - Approved time-off requests
    - Pending approval requests
    - Conflict highlighting
    - Coverage analysis by date
    """
    manager_id = current_user.employee_id or 2
    
    # Set date range
    if not start_date:
        start_date = date.today()
    if not end_date:
        end_date = start_date + timedelta(days=30)
    
    # Get manager info
    manager = session.get(Employee, manager_id)
    team_name = f"{manager.first_name}'s Team" if manager else "Team"
    
    # Get team members
    team_members = get_team_members(manager_id, session)
    
    # Build team member availability
    team_availability = []
    approved_entries = []
    pending_entries = []
    
    for member in team_members:
        # Get approved requests
        approved_stmt = select(TimeOffRequest).where(
            TimeOffRequest.employee_id == member.id,
            TimeOffRequest.status == TimeOffRequestStatus.APPROVED.value,
            TimeOffRequest.start_date <= end_date,
            TimeOffRequest.end_date >= start_date,
        )
        approved = list(session.execute(approved_stmt).scalars().all())
        
        # Get pending requests
        pending_stmt = select(TimeOffRequest).where(
            TimeOffRequest.employee_id == member.id,
            TimeOffRequest.status == TimeOffRequestStatus.PENDING_APPROVAL.value,
            TimeOffRequest.start_date <= end_date,
            TimeOffRequest.end_date >= start_date,
        )
        pending = list(session.execute(pending_stmt).scalars().all())
        
        # Calculate available/unavailable dates
        unavailable_dates = set()
        for req in approved:
            current = req.start_date
            while current <= req.end_date:
                if start_date <= current <= end_date:
                    unavailable_dates.add(current)
                current += timedelta(days=1)
        
        all_dates = set()
        current = start_date
        while current <= end_date:
            if current.weekday() < 5:  # Workdays
                all_dates.add(current)
            current += timedelta(days=1)
        
        available_dates = all_dates - unavailable_dates
        
        team_availability.append(TeamMemberAvailability(
            employee=TeamMemberInfo(
                id=member.id,
                employee_id=member.employee_id,
                name=f"{member.first_name} {member.last_name}",
                job_title=member.job_title,
                is_critical_function=False,
                functions=[],
            ),
            dates_available=sorted(available_dates),
            dates_unavailable=sorted(unavailable_dates),
            approved_requests=[{
                "id": r.id,
                "type": r.request_type,
                "start": r.start_date.isoformat(),
                "end": r.end_date.isoformat(),
            } for r in approved],
            pending_requests=[{
                "id": r.id,
                "type": r.request_type,
                "start": r.start_date.isoformat(),
                "end": r.end_date.isoformat(),
            } for r in pending],
        ))
        
        # Add calendar entries
        for req in approved:
            approved_entries.append(CalendarEntry(
                id=f"approved-{req.id}",
                employee_id=member.id,
                employee_name=f"{member.first_name} {member.last_name}",
                entry_type="approved",
                start_date=req.start_date,
                end_date=req.end_date,
                request_type=req.request_type,
                status="approved",
                has_conflict=False,
            ))
        
        if include_pending:
            for req in pending:
                pending_entries.append(CalendarEntry(
                    id=f"pending-{req.id}",
                    employee_id=member.id,
                    employee_name=f"{member.first_name} {member.last_name}",
                    entry_type="pending",
                    start_date=req.start_date,
                    end_date=req.end_date,
                    request_type=req.request_type,
                    status="pending",
                    has_conflict=False,
                ))
    
    # Build coverage by date
    coverage_by_date = {}
    if include_coverage:
        current = start_date
        while current <= end_date:
            if current.weekday() < 5:
                available_count = 0
                absent_list = []
                
                for avail in team_availability:
                    if current in avail.dates_available:
                        available_count += 1
                    else:
                        absent_list.append(avail.employee.name)
                
                minimum_required = max(1, len(team_members) // 2)
                
                if available_count >= minimum_required:
                    cov_status = CoverageStatusEnum.ADEQUATE
                elif available_count >= minimum_required - 1:
                    cov_status = CoverageStatusEnum.MARGINAL
                elif available_count > 0:
                    cov_status = CoverageStatusEnum.INSUFFICIENT
                else:
                    cov_status = CoverageStatusEnum.CRITICAL
                
                coverage_by_date[current.isoformat()] = DailyCoverage(
                    date=current,
                    is_workday=True,
                    total_team_size=len(team_members),
                    available_count=available_count,
                    minimum_required=minimum_required,
                    coverage_status=cov_status,
                    critical_functions_covered=available_count > 0,
                    absent_employees=absent_list,
                )
            
            current += timedelta(days=1)
    
    # Get organizational events
    org_events = get_organizational_events(start_date, end_date)
    
    # Build summary
    summary = {
        "team_size": len(team_members),
        "total_approved": len(approved_entries),
        "total_pending": len(pending_entries),
        "days_with_conflicts": 0,
        "days_below_minimum": sum(
            1 for dc in coverage_by_date.values()
            if dc.coverage_status in [CoverageStatusEnum.INSUFFICIENT, CoverageStatusEnum.CRITICAL]
        ),
    }
    
    return TeamCalendarResponse(
        manager_id=manager_id,
        team_name=team_name,
        start_date=start_date,
        end_date=end_date,
        team_members=team_availability,
        approved_entries=approved_entries,
        pending_entries=pending_entries,
        conflicts=[],
        coverage_by_date=coverage_by_date,
        summary=summary,
        organizational_events=org_events,
    )

