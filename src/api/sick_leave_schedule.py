"""API endpoints for sick leave schedule integration."""

from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.schemas.sick_leave_schedule import (
    DurationCalculationRequest,
    DurationCalculationResponse,
    WorkScheduleInfo,
    WorkScheduleType,
    DayBreakdown,
    TimeAllocationRecommendation,
    TimeUnitPreference,
    PolicyComplianceInfo,
    PolicyComplianceStatus,
    ConflictDetectionRequest,
    ConflictDetectionResponse,
    ConflictDetail,
    ConflictType,
    ConflictSeverity,
    AlternativeSchedule,
    ImpactAnalysis,
)


sick_leave_schedule_router = APIRouter(
    prefix="/api/sick-leave",
    tags=["Sick Leave Schedule Integration"],
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
    }


def get_employee_schedule(employee_id: int) -> WorkScheduleInfo:
    """Get employee work schedule information."""
    # Mock schedule data
    return WorkScheduleInfo(
        schedule_type=WorkScheduleType.STANDARD,
        standard_hours_per_day=8.0,
        standard_hours_per_week=40.0,
        work_days=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
        start_time=time(9, 0),
        end_time=time(17, 0),
        has_flexible_hours=False,
        location_timezone="America/New_York",
    )


def get_day_of_week(d: date) -> str:
    """Get day of week name from date."""
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    return days[d.weekday()]


def is_work_day(d: date, work_days: List[str]) -> bool:
    """Check if date is a work day."""
    return get_day_of_week(d) in work_days


def is_company_holiday(d: date) -> bool:
    """Check if date is a company holiday."""
    # Mock holidays
    holidays = [
        date(2025, 1, 1),   # New Year's Day
        date(2025, 7, 4),   # Independence Day
        date(2025, 12, 25), # Christmas
        date(2025, 12, 26), # Day after Christmas
    ]
    return d in holidays


def is_blackout_period(d: date) -> bool:
    """Check if date is in a blackout period."""
    # Mock blackout periods
    blackouts = [
        (date(2025, 12, 15), date(2025, 12, 31)),  # Year-end freeze
    ]
    for start, end in blackouts:
        if start <= d <= end:
            return True
    return False


def get_existing_requests(employee_id: int, start_date: date, end_date: date) -> List[Dict]:
    """Get existing time-off requests for an employee."""
    # Mock existing requests
    return [
        {
            "request_id": 1001,
            "type": "PTO",
            "start_date": date(2025, 1, 15),
            "end_date": date(2025, 1, 17),
            "status": "approved",
        },
        {
            "request_id": 1002,
            "type": "Sick Leave",
            "start_date": date(2025, 2, 5),
            "end_date": date(2025, 2, 5),
            "status": "approved",
        },
    ]


# =============================================================================
# Duration Calculation Endpoint
# =============================================================================

@sick_leave_schedule_router.post(
    "/calculate-duration",
    response_model=DurationCalculationResponse,
    summary="Calculate sick leave duration",
    description="Calculates optimal time allocation for sick leave based on employee work schedule.",
)
async def calculate_sick_leave_duration(
    request: DurationCalculationRequest,
):
    """
    Calculate sick leave duration based on employee schedule.
    
    This endpoint provides:
    - Optimal time allocation between hours and days
    - Work schedule pattern analysis
    - Daily breakdown of sick leave hours
    - Policy compliance verification
    - Conversion recommendations
    
    **Features**:
    - Considers standard hours, flexible arrangements, and location variations
    - Applies organizational policies for time increments
    - Provides regulatory compliance notes
    """
    current_user = get_current_user()
    
    # Get employee schedule
    schedule = get_employee_schedule(request.employee_id)
    
    # Calculate day-by-day breakdown
    day_breakdown = []
    total_hours = 0.0
    total_days = 0.0
    work_days_count = 0
    
    current_date = request.start_date
    while current_date <= request.end_date:
        day_name = get_day_of_week(current_date)
        is_work = is_work_day(current_date, schedule.work_days)
        is_holiday = is_company_holiday(current_date)
        is_blackout = is_blackout_period(current_date)
        
        # Calculate hours for this day
        if is_work and not is_holiday:
            scheduled_hours = schedule.standard_hours_per_day
            
            # Handle partial day requests
            if request.start_time and current_date == request.start_date:
                # Partial start day
                start_minutes = request.start_time.hour * 60 + request.start_time.minute
                schedule_start_minutes = schedule.start_time.hour * 60 + schedule.start_time.minute if schedule.start_time else 540
                hours_before = max(0, (start_minutes - schedule_start_minutes) / 60)
                scheduled_hours = schedule.standard_hours_per_day - hours_before
            
            if request.end_time and current_date == request.end_date:
                # Partial end day
                end_minutes = request.end_time.hour * 60 + request.end_time.minute
                schedule_end_minutes = schedule.end_time.hour * 60 + schedule.end_time.minute if schedule.end_time else 1020
                hours_after = max(0, (schedule_end_minutes - end_minutes) / 60)
                scheduled_hours -= hours_after
            
            sick_hours = max(0, scheduled_hours)
            sick_days = sick_hours / schedule.standard_hours_per_day
            work_days_count += 1
        else:
            scheduled_hours = 0.0
            sick_hours = 0.0
            sick_days = 0.0
        
        # Determine notes
        notes = None
        if is_holiday:
            notes = "Company holiday - no sick leave charged"
        elif is_blackout:
            notes = "Blackout period - may require special approval"
        elif not is_work:
            notes = "Non-work day"
        
        day_breakdown.append(DayBreakdown(
            date=current_date,
            day_of_week=day_name,
            is_work_day=is_work,
            is_holiday=is_holiday,
            is_blackout=is_blackout,
            scheduled_hours=schedule.standard_hours_per_day if is_work else 0,
            sick_leave_hours=sick_hours,
            sick_leave_days=sick_days,
            notes=notes,
        ))
        
        total_hours += sick_hours
        total_days += sick_days
        current_date += timedelta(days=1)
    
    calendar_days = (request.end_date - request.start_date).days + 1
    
    # Determine recommendation
    if total_hours <= 4:
        recommended_unit = TimeUnitPreference.HOURS
        reason = "Short duration is better tracked in hours for accuracy"
    elif total_days >= 1 and total_days == int(total_days):
        recommended_unit = TimeUnitPreference.DAYS
        reason = "Full day increments align with policy preferences"
    else:
        recommended_unit = TimeUnitPreference.AUTO
        reason = "Mixed duration - system will optimize based on policy"
    
    allocation_recommendation = TimeAllocationRecommendation(
        recommended_unit=recommended_unit,
        reason=reason,
        hours_value=total_hours,
        days_value=total_days,
        is_policy_compliant=total_hours >= 1,  # Minimum 1 hour
    )
    
    # Policy compliance check
    compliance_issues = []
    compliance_suggestions = []
    
    if total_hours < 1:
        compliance_issues.append("Minimum sick leave is 1 hour")
        compliance_suggestions.append("Adjust time to meet minimum requirement")
    
    if total_days > 3 and not request.include_schedule_details:
        compliance_suggestions.append("Extended sick leave may require documentation")
    
    policy_compliance = PolicyComplianceInfo(
        status=PolicyComplianceStatus.COMPLIANT if not compliance_issues else PolicyComplianceStatus.REQUIRES_ADJUSTMENT,
        policy_name="Standard Sick Leave Policy",
        policy_id=1,
        min_increment_hours=1.0,
        max_consecutive_days=5,
        requires_documentation_days=3,
        issues=compliance_issues,
        suggestions=compliance_suggestions,
    )
    
    # Regulatory notes
    regulatory_notes = []
    if total_days > 3:
        regulatory_notes.append("FMLA may apply for extended sick leave")
    if calendar_days > 7:
        regulatory_notes.append("Consider short-term disability for extended illness")
    regulatory_notes.append("Sick leave time must be documented consistently for payroll compliance")
    
    return DurationCalculationResponse(
        employee_id=request.employee_id,
        employee_name=f"Employee {request.employee_id}",
        start_date=request.start_date,
        end_date=request.end_date,
        work_schedule=schedule,
        total_hours=round(total_hours, 2),
        total_days=round(total_days, 2),
        work_days_count=work_days_count,
        calendar_days_count=calendar_days,
        day_breakdown=day_breakdown if request.include_schedule_details else [],
        allocation_recommendation=allocation_recommendation,
        policy_compliance=policy_compliance,
        regulatory_notes=regulatory_notes,
        calculated_at=datetime.utcnow(),
    )


# =============================================================================
# Conflict Detection Endpoint
# =============================================================================

@sick_leave_schedule_router.get(
    "/schedule-conflicts",
    response_model=ConflictDetectionResponse,
    summary="Detect schedule conflicts",
    description="Analyzes proposed sick leave request for conflicts with existing schedules.",
)
async def detect_schedule_conflicts(
    employee_id: int = Query(..., description="Employee ID"),
    start_date: date = Query(..., description="Proposed start date"),
    end_date: date = Query(..., description="Proposed end date"),
    start_time: Optional[str] = Query(default=None, description="Start time (HH:MM format)"),
    end_time: Optional[str] = Query(default=None, description="End time (HH:MM format)"),
    include_alternatives: bool = Query(default=True, description="Include alternative suggestions"),
    include_impact_analysis: bool = Query(default=True, description="Include impact analysis"),
):
    """
    Detect conflicts for a proposed sick leave request.
    
    This endpoint provides:
    - Conflict analysis with existing requests
    - Holiday and blackout period detection
    - Alternative scheduling recommendations
    - Impact analysis and resolution suggestions
    
    **Conflict Types Detected**:
    - Overlapping approved requests
    - Company holidays
    - Blackout periods
    - Team coverage issues
    - Regulatory limits
    """
    current_user = get_current_user()
    
    # Validate date range
    if end_date < start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_date must be on or after start_date",
        )
    
    # Parse times if provided
    parsed_start_time = None
    parsed_end_time = None
    if start_time:
        try:
            parts = start_time.split(":")
            parsed_start_time = time(int(parts[0]), int(parts[1]))
        except (ValueError, IndexError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid start_time format. Use HH:MM",
            )
    if end_time:
        try:
            parts = end_time.split(":")
            parsed_end_time = time(int(parts[0]), int(parts[1]))
        except (ValueError, IndexError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid end_time format. Use HH:MM",
            )
    
    conflicts = []
    conflict_counter = 0
    
    # Check for existing request conflicts
    existing_requests = get_existing_requests(employee_id, start_date, end_date)
    for req in existing_requests:
        req_start = req["start_date"]
        req_end = req["end_date"]
        
        # Check for overlap
        if not (end_date < req_start or start_date > req_end):
            conflict_counter += 1
            overlap_start = max(start_date, req_start)
            overlap_end = min(end_date, req_end)
            overlap_days = (overlap_end - overlap_start).days + 1
            
            conflicts.append(ConflictDetail(
                conflict_id=f"CONF-{conflict_counter:03d}",
                conflict_type=ConflictType.EXISTING_REQUEST,
                severity=ConflictSeverity.BLOCKING,
                affected_start_date=overlap_start,
                affected_end_date=overlap_end,
                overlap_days=overlap_days,
                related_entity_id=req["request_id"],
                related_entity_name=f"{req['type']} Request #{req['request_id']}",
                description=f"Overlaps with existing {req['type'].lower()} request ({req_start} - {req_end})",
                impact_description="Cannot have overlapping time-off requests",
                can_override=False,
                resolution_suggestions=[
                    "Cancel the existing request first",
                    "Modify dates to avoid overlap",
                    f"Request can start after {req_end}",
                ],
            ))
    
    # Check for holidays
    current_date = start_date
    holiday_dates = []
    while current_date <= end_date:
        if is_company_holiday(current_date):
            holiday_dates.append(current_date)
        current_date += timedelta(days=1)
    
    if holiday_dates:
        conflict_counter += 1
        conflicts.append(ConflictDetail(
            conflict_id=f"CONF-{conflict_counter:03d}",
            conflict_type=ConflictType.COMPANY_HOLIDAY,
            severity=ConflictSeverity.INFO,
            affected_start_date=min(holiday_dates),
            affected_end_date=max(holiday_dates),
            overlap_days=len(holiday_dates),
            description=f"Request includes {len(holiday_dates)} company holiday(s)",
            impact_description="Sick leave will not be charged for holidays",
            can_override=True,
            resolution_suggestions=[
                "Consider adjusting dates if requesting time beyond the holiday",
                "No action needed - holidays are automatically excluded",
            ],
        ))
    
    # Check for blackout periods
    current_date = start_date
    blackout_dates = []
    while current_date <= end_date:
        if is_blackout_period(current_date):
            blackout_dates.append(current_date)
        current_date += timedelta(days=1)
    
    if blackout_dates:
        conflict_counter += 1
        conflicts.append(ConflictDetail(
            conflict_id=f"CONF-{conflict_counter:03d}",
            conflict_type=ConflictType.BLACKOUT_PERIOD,
            severity=ConflictSeverity.WARNING,
            affected_start_date=min(blackout_dates),
            affected_end_date=max(blackout_dates),
            overlap_days=len(blackout_dates),
            description=f"Request falls within blackout period ({len(blackout_dates)} days)",
            impact_description="Blackout periods may have restricted approvals",
            can_override=True,
            resolution_suggestions=[
                "Obtain management approval for blackout period requests",
                "Provide documentation for urgent sick leave",
                f"Consider requesting outside blackout period if possible",
            ],
        ))
    
    # Count conflicts by severity
    blocking_count = sum(1 for c in conflicts if c.severity == ConflictSeverity.BLOCKING)
    warning_count = sum(1 for c in conflicts if c.severity == ConflictSeverity.WARNING)
    info_count = sum(1 for c in conflicts if c.severity == ConflictSeverity.INFO)
    
    # Generate alternatives
    alternatives = []
    if include_alternatives and blocking_count > 0:
        # Suggest alternative dates
        request_length = (end_date - start_date).days + 1
        
        # Try dates after last conflicting end date
        max_conflict_end = max(
            (c.affected_end_date for c in conflicts if c.severity == ConflictSeverity.BLOCKING),
            default=end_date,
        )
        alt_start = max_conflict_end + timedelta(days=1)
        alt_end = alt_start + timedelta(days=request_length - 1)
        
        alternatives.append(AlternativeSchedule(
            alternative_id="ALT-001",
            start_date=alt_start,
            end_date=alt_end,
            total_days=float(request_length),
            total_hours=float(request_length * 8),
            conflicts_avoided=blocking_count,
            trade_offs=["Later start date than requested"],
            suitability_score=85.0,
            recommendation_reason="Starts immediately after existing conflicts resolve",
        ))
        
        # Try dates before first conflicting start date
        min_conflict_start = min(
            (c.affected_start_date for c in conflicts if c.severity == ConflictSeverity.BLOCKING),
            default=start_date,
        )
        if min_conflict_start > start_date + timedelta(days=request_length):
            alt_end_before = min_conflict_start - timedelta(days=1)
            alt_start_before = alt_end_before - timedelta(days=request_length - 1)
            
            if alt_start_before >= date.today():
                alternatives.append(AlternativeSchedule(
                    alternative_id="ALT-002",
                    start_date=alt_start_before,
                    end_date=alt_end_before,
                    total_days=float(request_length),
                    total_hours=float(request_length * 8),
                    conflicts_avoided=blocking_count,
                    trade_offs=["Earlier dates than requested"],
                    suitability_score=75.0,
                    recommendation_reason="Ends before existing conflicts begin",
                ))
    
    # Impact analysis
    impact_analysis = None
    if include_impact_analysis:
        request_days = (end_date - start_date).days + 1
        impact_level = "low" if request_days <= 2 else "medium" if request_days <= 5 else "high"
        
        impact_analysis = ImpactAnalysis(
            team_coverage_impact=f"{impact_level.title()} impact - {request_days} day(s) of absence",
            affected_team_members=2 if request_days > 3 else 0,
            workload_redistribution_required=request_days > 2,
            estimated_redistribution_hours=float(request_days * 4) if request_days > 2 else 0,
            project_deadlines_affected=1 if request_days > 5 else 0,
            overall_impact_level=impact_level,
            impact_summary=f"{'Minor' if impact_level == 'low' else 'Moderate' if impact_level == 'medium' else 'Significant'} impact on team operations",
        )
    
    # Policy considerations
    policy_considerations = []
    request_days = (end_date - start_date).days + 1
    if request_days > 3:
        policy_considerations.append("Requests over 3 days may require medical documentation")
    if request_days > 5:
        policy_considerations.append("Extended absences should be coordinated with HR")
    policy_considerations.append("Sick leave is intended for personal illness or caring for sick family members")
    
    # Determine if can proceed
    can_proceed = blocking_count == 0
    if blocking_count > 0:
        proceed_recommendation = "Cannot proceed - resolve blocking conflicts first"
    elif warning_count > 0:
        proceed_recommendation = "Can proceed with caution - review warnings before submitting"
    else:
        proceed_recommendation = "Clear to proceed with request"
    
    return ConflictDetectionResponse(
        employee_id=employee_id,
        employee_name=f"Employee {employee_id}",
        proposed_start_date=start_date,
        proposed_end_date=end_date,
        has_conflicts=len(conflicts) > 0,
        total_conflicts=len(conflicts),
        blocking_conflicts=blocking_count,
        warning_conflicts=warning_count,
        info_conflicts=info_count,
        conflicts=conflicts,
        alternatives=alternatives,
        impact_analysis=impact_analysis,
        policy_considerations=policy_considerations,
        can_proceed=can_proceed,
        proceed_recommendation=proceed_recommendation,
        analyzed_at=datetime.utcnow(),
    )


