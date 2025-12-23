"""API endpoints for balance projections and conflict detection."""

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.schemas.balance_projections import (
    BalanceProjectionResponse,
    PolicyProjection,
    ScheduledAccrual,
    AccrualType,
    CarryoverInfo,
    PolicyConstraint,
    ProjectionComponent,
    WhatIfScenario,
    ScenarioType,
    ProjectionConfidence,
    ProjectionConfidenceLevel,
    ConflictDetectionResponse,
    ConflictDetail,
    ConflictType,
    ConflictSeverity,
    TeamCoverageInfo,
    ConcurrentRequestInfo,
    ResolutionRecommendation,
    PolicyGuidance,
)


balance_projections_router = APIRouter(
    prefix="/api/time-off-requests",
    tags=["Balance Projections & Conflict Detection"],
)


# =============================================================================
# Helper Functions
# =============================================================================

def get_current_user():
    """Mock function to get current authenticated user."""
    return {
        "id": 1,
        "name": "John Employee",
        "role": "employee",
        "department_id": 100,
        "team_id": 10,
        "manager_id": 50,
        "hire_date": date(2023, 1, 15),
    }


def calculate_scheduled_accruals(
    employee_id: int,
    policy_id: int,
    start_date: date,
    end_date: date,
) -> List[ScheduledAccrual]:
    """Calculate scheduled accruals for a date range."""
    accruals = []
    current = start_date
    
    # Mock monthly accruals
    while current <= end_date:
        # Add accrual on 1st of each month
        if current.day == 1 or current == start_date:
            accrual_date = current.replace(day=1)
            if accrual_date >= start_date and accrual_date <= end_date:
                accruals.append(ScheduledAccrual(
                    accrual_date=accrual_date,
                    accrual_type=AccrualType.SCHEDULED,
                    amount=1.25,
                    description="Monthly accrual",
                    policy_id=policy_id,
                ))
        current += timedelta(days=1)
    
    return accruals


def get_company_holidays(start_date: date, end_date: date) -> List[Dict[str, Any]]:
    """Get company holidays in date range."""
    holidays = [
        {"date": date(2025, 1, 1), "name": "New Year's Day"},
        {"date": date(2025, 1, 20), "name": "MLK Day"},
        {"date": date(2025, 2, 17), "name": "Presidents Day"},
        {"date": date(2025, 5, 26), "name": "Memorial Day"},
        {"date": date(2025, 7, 4), "name": "Independence Day"},
        {"date": date(2025, 9, 1), "name": "Labor Day"},
        {"date": date(2025, 11, 27), "name": "Thanksgiving"},
        {"date": date(2025, 11, 28), "name": "Day after Thanksgiving"},
        {"date": date(2025, 12, 24), "name": "Christmas Eve"},
        {"date": date(2025, 12, 25), "name": "Christmas Day"},
        {"date": date(2025, 12, 31), "name": "New Year's Eve"},
    ]
    
    return [h for h in holidays if start_date <= h["date"] <= end_date]


def get_blackout_periods(start_date: date, end_date: date) -> List[Dict[str, Any]]:
    """Get blackout periods in date range."""
    blackouts = [
        {"id": 1, "name": "Year-End Freeze", "start": date(2025, 12, 15), "end": date(2025, 12, 31)},
        {"id": 2, "name": "Q1 Close", "start": date(2025, 3, 28), "end": date(2025, 4, 5)},
        {"id": 3, "name": "Annual Conference", "start": date(2025, 6, 10), "end": date(2025, 6, 15)},
    ]
    
    conflicts = []
    for blackout in blackouts:
        if not (end_date < blackout["start"] or start_date > blackout["end"]):
            conflicts.append(blackout)
    
    return conflicts


# =============================================================================
# Balance Projections Endpoint
# =============================================================================

@balance_projections_router.get(
    "/balances/projections",
    response_model=BalanceProjectionResponse,
    summary="Get balance projections",
    description="Calculate projected balances with accruals, constraints, and what-if analysis.",
)
async def get_balance_projections(
    employee_id: Optional[int] = Query(default=None, description="Employee ID (default: current user)"),
    policy_id: Optional[int] = Query(default=None, description="Filter by policy ID"),
    projection_date: Optional[date] = Query(default=None, description="Projection end date"),
    include_pending: bool = Query(default=True, description="Include pending requests"),
    include_scenarios: bool = Query(default=True, description="Include what-if scenarios"),
    include_timeline: bool = Query(default=False, description="Include detailed timeline"),
):
    """
    Get balance projections for an employee.
    
    This endpoint provides:
    - Projected balances based on scheduled accruals
    - Policy constraints (max limits, use-it-or-lose-it)
    - Impact of approved and pending requests
    - Confidence scoring
    - What-if scenario analysis
    
    **Features**:
    - Tenure-based accrual adjustments
    - Carryover expiration tracking
    - Multiple scenario comparisons
    """
    current_user = get_current_user()
    target_employee_id = employee_id or current_user["id"]
    
    # Set projection dates
    today = date.today()
    end_date = projection_date or (today + timedelta(days=365))
    
    # Mock current balances by policy
    policies = [
        {"id": 1, "name": "Paid Time Off", "code": "PTO", "balance": 15.0},
        {"id": 2, "name": "Sick Leave", "code": "SICK", "balance": 10.0},
    ]
    
    if policy_id:
        policies = [p for p in policies if p["id"] == policy_id]
    
    policy_projections = []
    total_projected = 0.0
    total_accruals = 0.0
    total_pending = 0.0
    
    for policy in policies:
        # Calculate scheduled accruals
        accruals = calculate_scheduled_accruals(
            target_employee_id,
            policy["id"],
            today,
            end_date,
        )
        total_policy_accruals = sum(a.amount for a in accruals)
        
        # Mock pending requests impact
        pending_impact = 2.0 if include_pending else 0.0
        
        # Calculate projected balance
        projected = policy["balance"] + total_policy_accruals - pending_impact
        
        # Apply constraints
        max_limit = 40.0 if policy["code"] == "PTO" else 20.0
        balance_capped = projected > max_limit
        if balance_capped:
            projected = max_limit
        
        constraints = [
            PolicyConstraint(
                constraint_type="maximum_balance",
                limit_value=max_limit,
                description=f"Maximum balance limit of {max_limit} days",
                impact_on_balance=0 if not balance_capped else projected - max_limit,
            ),
        ]
        
        # Carryover info
        carryover = None
        if policy["code"] == "PTO":
            carryover = CarryoverInfo(
                amount=5.0,
                expires_on=date(today.year + 1, 3, 31),
                is_use_it_or_lose_it=True,
                days_until_expiration=(date(today.year + 1, 3, 31) - today).days,
            )
        
        # Build timeline if requested
        timeline = []
        if include_timeline:
            running = policy["balance"]
            timeline.append(ProjectionComponent(
                component_date=today,
                component_type="current_balance",
                amount=policy["balance"],
                running_balance=running,
                description="Current balance",
            ))
            
            for accrual in accruals[:6]:  # Limit for brevity
                running += accrual.amount
                timeline.append(ProjectionComponent(
                    component_date=accrual.accrual_date,
                    component_type="accrual",
                    amount=accrual.amount,
                    running_balance=running,
                    description=accrual.description,
                ))
        
        policy_projections.append(PolicyProjection(
            policy_id=policy["id"],
            policy_name=policy["name"],
            policy_code=policy["code"],
            current_balance=policy["balance"],
            as_of_date=today,
            projected_balance=projected,
            projection_date=end_date,
            scheduled_accruals=accruals,
            total_scheduled_accruals=total_policy_accruals,
            approved_requests_impact=0.0,
            pending_requests_impact=pending_impact,
            carryover_info=carryover,
            constraints_applied=constraints,
            maximum_balance_limit=max_limit,
            balance_capped=balance_capped,
            projection_timeline=timeline,
        ))
        
        total_projected += projected
        total_accruals += total_policy_accruals
        total_pending += pending_impact
    
    # Confidence scoring
    confidence = ProjectionConfidence(
        overall_confidence=ProjectionConfidenceLevel.HIGH,
        confidence_score=92.5,
        factors=[
            {"factor": "Accrual schedule", "impact": "positive", "description": "Regular accrual pattern"},
            {"factor": "Policy stability", "impact": "positive", "description": "No policy changes expected"},
            {"factor": "Pending requests", "impact": "neutral", "description": "Pending requests may change"},
        ],
        uncertainty_low=total_projected - 2.0,
        uncertainty_high=total_projected + 3.0,
        confidence_notes=[
            "Projection assumes current accrual rates continue",
            "Pending requests are subject to approval decisions",
        ],
    )
    
    # What-if scenarios
    scenarios = []
    if include_scenarios:
        scenarios = [
            WhatIfScenario(
                scenario_id="SCN-001",
                scenario_type=ScenarioType.BASELINE,
                scenario_name="Baseline",
                description="Current projection without changes",
                assumptions=["Current accrual rates", "No additional requests"],
                projected_balance=total_projected,
                difference_from_baseline=0,
                recommendations=[],
            ),
            WhatIfScenario(
                scenario_id="SCN-002",
                scenario_type=ScenarioType.WITH_PENDING,
                scenario_name="With All Pending Approved",
                description="Projection if all pending requests are approved",
                assumptions=["All pending requests approved", "Current accrual rates"],
                projected_balance=total_projected - total_pending,
                difference_from_baseline=-total_pending,
                recommendations=["Plan future requests considering pending approvals"],
            ),
            WhatIfScenario(
                scenario_id="SCN-003",
                scenario_type=ScenarioType.OPTIMISTIC,
                scenario_name="Optimistic",
                description="Best case with maximum accruals",
                assumptions=["Tenure bonus applied", "No unexpected usage"],
                projected_balance=total_projected + 5.0,
                difference_from_baseline=5.0,
                recommendations=["Watch for maximum balance limits"],
            ),
        ]
    
    # Warnings
    warnings = []
    for proj in policy_projections:
        if proj.balance_capped:
            warnings.append(f"Balance will be capped at maximum for {proj.policy_name}")
        if proj.carryover_info and proj.carryover_info.days_until_expiration and proj.carryover_info.days_until_expiration < 90:
            warnings.append(f"Carryover balance for {proj.policy_name} expires in {proj.carryover_info.days_until_expiration} days")
    
    return BalanceProjectionResponse(
        employee_id=target_employee_id,
        employee_name=f"Employee {target_employee_id}",
        projection_start_date=today,
        projection_end_date=end_date,
        policy_projections=policy_projections,
        total_projected_balance=total_projected,
        total_scheduled_accruals=total_accruals,
        total_pending_impact=total_pending,
        confidence=confidence,
        scenarios=scenarios,
        warnings=warnings,
        calculated_at=datetime.utcnow(),
    )


# =============================================================================
# Conflict Detection Endpoint
# =============================================================================

@balance_projections_router.get(
    "/conflicts/detect",
    response_model=ConflictDetectionResponse,
    summary="Detect scheduling conflicts",
    description="Identify conflicts with holidays, blackouts, team calendar, and concurrent requests.",
)
async def detect_conflicts(
    employee_id: Optional[int] = Query(default=None, description="Employee ID (default: current user)"),
    start_date: date = Query(..., description="Proposed start date"),
    end_date: date = Query(..., description="Proposed end date"),
    include_team_coverage: bool = Query(default=True, description="Include team coverage analysis"),
    include_concurrent: bool = Query(default=True, description="Include concurrent requests"),
    department_id: Optional[int] = Query(default=None, description="Department for coverage check"),
):
    """
    Detect scheduling conflicts for a proposed time-off request.
    
    This endpoint identifies:
    - Company holiday conflicts
    - Blackout period conflicts
    - Team calendar event conflicts
    - Concurrent request conflicts
    - Coverage requirement issues
    - Organizational event overlaps
    
    **Features**:
    - Resolution recommendations
    - Policy-specific guidance
    - Risk assessment
    """
    current_user = get_current_user()
    target_employee_id = employee_id or current_user["id"]
    target_department_id = department_id or current_user["department_id"]
    
    # Validate dates
    if end_date < start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_date must be on or after start_date",
        )
    
    days_requested = (end_date - start_date).days + 1
    conflicts = []
    conflict_counter = 0
    
    # Check company holidays
    holidays = get_company_holidays(start_date, end_date)
    for holiday in holidays:
        conflict_counter += 1
        conflicts.append(ConflictDetail(
            conflict_id=f"CONF-{conflict_counter:03d}",
            conflict_type=ConflictType.COMPANY_HOLIDAY,
            severity=ConflictSeverity.LOW,
            conflict_start=holiday["date"],
            conflict_end=holiday["date"],
            overlap_days=1,
            title=f"Company Holiday: {holiday['name']}",
            description=f"Request includes {holiday['name']} which is a company holiday",
            impact_level="low",
            impact_description="Time-off not charged for holidays",
            can_override=True,
            requires_approval=False,
            resolution_options=[
                "No action needed - holiday excluded from request",
                "Adjust dates if only requesting around the holiday",
            ],
        ))
    
    # Check blackout periods
    blackouts = get_blackout_periods(start_date, end_date)
    for blackout in blackouts:
        conflict_counter += 1
        overlap_start = max(start_date, blackout["start"])
        overlap_end = min(end_date, blackout["end"])
        overlap_days = (overlap_end - overlap_start).days + 1
        
        conflicts.append(ConflictDetail(
            conflict_id=f"CONF-{conflict_counter:03d}",
            conflict_type=ConflictType.BLACKOUT_PERIOD,
            severity=ConflictSeverity.HIGH,
            conflict_start=blackout["start"],
            conflict_end=blackout["end"],
            overlap_days=overlap_days,
            title=f"Blackout Period: {blackout['name']}",
            description=f"Request overlaps with blackout period '{blackout['name']}'",
            related_entity_type="blackout_period",
            related_entity_id=blackout["id"],
            related_entity_name=blackout["name"],
            impact_level="high",
            impact_description="Requests during blackout periods require special approval",
            can_override=True,
            requires_approval=True,
            resolution_options=[
                "Request exception approval from management",
                f"Reschedule to avoid {blackout['name']}",
                "Split request to exclude blackout dates",
            ],
        ))
    
    # Check organizational events (mock)
    if start_date <= date(2025, 6, 12) <= end_date:
        conflict_counter += 1
        conflicts.append(ConflictDetail(
            conflict_id=f"CONF-{conflict_counter:03d}",
            conflict_type=ConflictType.ORGANIZATIONAL_EVENT,
            severity=ConflictSeverity.MEDIUM,
            conflict_start=date(2025, 6, 12),
            conflict_end=date(2025, 6, 12),
            overlap_days=1,
            title="All-Hands Meeting",
            description="Request conflicts with quarterly all-hands meeting",
            related_entity_type="event",
            related_entity_name="Q2 All-Hands Meeting",
            impact_level="medium",
            impact_description="Attendance expected at company meetings",
            can_override=True,
            requires_approval=True,
            resolution_options=[
                "Request exception if critical personal matter",
                "Plan to attend remotely if possible",
            ],
        ))
    
    # Team coverage analysis
    team_coverage = None
    if include_team_coverage:
        team_coverage = TeamCoverageInfo(
            team_id=current_user["team_id"],
            team_name="Engineering Team A",
            total_team_members=8,
            members_available=6,
            members_on_leave=1,
            members_pending_leave=1,
            coverage_percentage=75.0,
            minimum_coverage_required=50.0,
            meets_coverage_requirement=True,
            coverage_risk_level="low",
        )
        
        # Check if coverage would fall below minimum
        if team_coverage.coverage_percentage - (1 / team_coverage.total_team_members * 100) < team_coverage.minimum_coverage_required:
            conflict_counter += 1
            conflicts.append(ConflictDetail(
                conflict_id=f"CONF-{conflict_counter:03d}",
                conflict_type=ConflictType.COVERAGE_REQUIREMENT,
                severity=ConflictSeverity.HIGH,
                conflict_start=start_date,
                conflict_end=end_date,
                overlap_days=days_requested,
                title="Team Coverage Below Minimum",
                description="Approving this request would put team coverage below minimum",
                impact_level="high",
                impact_description="Team operations may be impacted",
                can_override=True,
                requires_approval=True,
                resolution_options=[
                    "Coordinate with team members on coverage",
                    "Request partial days instead of full days",
                    "Reschedule to period with better coverage",
                ],
            ))
    
    # Concurrent requests
    concurrent_requests = []
    if include_concurrent:
        # Mock concurrent requests
        concurrent_requests = [
            ConcurrentRequestInfo(
                request_id=5001,
                employee_id=102,
                employee_name="Jane Doe",
                start_date=start_date + timedelta(days=1),
                end_date=start_date + timedelta(days=3),
                status="approved",
                overlap_days=min(3, days_requested - 1),
            ),
        ]
        
        if concurrent_requests:
            conflict_counter += 1
            conflicts.append(ConflictDetail(
                conflict_id=f"CONF-{conflict_counter:03d}",
                conflict_type=ConflictType.CONCURRENT_REQUEST,
                severity=ConflictSeverity.MEDIUM,
                conflict_start=concurrent_requests[0].start_date,
                conflict_end=concurrent_requests[0].end_date,
                overlap_days=concurrent_requests[0].overlap_days,
                title="Overlapping Team Request",
                description=f"{concurrent_requests[0].employee_name} has approved time-off during this period",
                related_entity_type="request",
                related_entity_id=concurrent_requests[0].request_id,
                related_entity_name=concurrent_requests[0].employee_name,
                impact_level="medium",
                impact_description="Multiple team members out simultaneously",
                can_override=True,
                requires_approval=True,
                resolution_options=[
                    "Verify coverage is adequate with both out",
                    "Coordinate with team member on coverage",
                    "Consider alternative dates",
                ],
            ))
    
    # Count conflicts by severity
    blocking_count = sum(1 for c in conflicts if c.severity == ConflictSeverity.BLOCKING)
    high_count = sum(1 for c in conflicts if c.severity == ConflictSeverity.HIGH)
    
    # Resolution recommendations
    recommendations = []
    if conflicts:
        recommendations.append(ResolutionRecommendation(
            recommendation_id="REC-001",
            priority=1,
            action="Review and address high-priority conflicts",
            description="Address blocking and high severity conflicts before submitting",
            estimated_resolution_effort="medium",
        ))
        
        if any(c.conflict_type == ConflictType.BLACKOUT_PERIOD for c in conflicts):
            alt_start = end_date + timedelta(days=7)
            alt_end = alt_start + timedelta(days=days_requested - 1)
            recommendations.append(ResolutionRecommendation(
                recommendation_id="REC-002",
                priority=2,
                action="Consider alternative dates",
                description="Schedule after blackout period to avoid conflicts",
                estimated_resolution_effort="low",
                alternative_dates={"start_date": alt_start, "end_date": alt_end},
            ))
    
    # Policy guidance
    guidance = [
        PolicyGuidance(
            policy_id=1,
            policy_name="Time-Off Request Policy",
            guidance_type="notice_requirement",
            guidance_text="Requests should be submitted at least 5 business days in advance",
        ),
        PolicyGuidance(
            policy_id=2,
            policy_name="Blackout Period Policy",
            guidance_type="exception_process",
            guidance_text="Exceptions require manager and HR approval with business justification",
        ),
    ]
    
    # Overall assessment
    can_proceed = blocking_count == 0
    if blocking_count > 0:
        proceed_rec = "Cannot proceed - resolve blocking conflicts first"
        risk_level = "critical"
    elif high_count > 0:
        proceed_rec = "Can proceed with approval - high priority conflicts require attention"
        risk_level = "high"
    elif conflicts:
        proceed_rec = "Can proceed - review advisory conflicts"
        risk_level = "medium"
    else:
        proceed_rec = "Clear to proceed - no conflicts detected"
        risk_level = "low"
    
    return ConflictDetectionResponse(
        employee_id=target_employee_id,
        employee_name=f"Employee {target_employee_id}",
        proposed_start_date=start_date,
        proposed_end_date=end_date,
        days_requested=float(days_requested),
        has_conflicts=len(conflicts) > 0,
        total_conflicts=len(conflicts),
        blocking_conflicts=blocking_count,
        high_severity_conflicts=high_count,
        conflicts=conflicts,
        team_coverage=team_coverage,
        concurrent_requests=concurrent_requests,
        resolution_recommendations=recommendations,
        policy_guidance=guidance,
        can_proceed=can_proceed,
        proceed_recommendation=proceed_rec,
        overall_risk_level=risk_level,
        analyzed_at=datetime.utcnow(),
    )


