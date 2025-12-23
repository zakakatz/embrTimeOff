"""API endpoints for time-off request submission."""

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, status

from src.schemas.time_off_submission import (
    TimeOffSubmissionRequest,
    TimeOffSubmissionResponse,
    ValidationResult,
    SubmissionErrorResponse,
    TimeOffTypeEnum,
    ValidationSeverity,
    RequestStatusEnum,
    FieldError,
    PolicyViolation,
    EligibilityInfo,
    BalanceProjection,
    BlackoutPeriodInfo,
    NoticeRequirement,
    SubmittedRequest,
    ApprovalWorkflowInfo,
    AuditInfo,
)


time_off_submission_router = APIRouter(
    prefix="/api/time-off",
    tags=["Time-Off Request Submission"],
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
        "manager_id": 10,
        "hire_date": date(2023, 1, 15),
    }


def get_employee_balance(employee_id: int, time_off_type: TimeOffTypeEnum) -> Dict[str, Any]:
    """Get employee balance for a time-off type."""
    # Mock balance data
    balances = {
        TimeOffTypeEnum.PTO: {"policy_id": 1, "policy_name": "Paid Time Off", "balance": 15.0},
        TimeOffTypeEnum.SICK_LEAVE: {"policy_id": 2, "policy_name": "Sick Leave", "balance": 10.0},
        TimeOffTypeEnum.PERSONAL: {"policy_id": 3, "policy_name": "Personal Days", "balance": 3.0},
        TimeOffTypeEnum.BEREAVEMENT: {"policy_id": 4, "policy_name": "Bereavement", "balance": 5.0},
        TimeOffTypeEnum.JURY_DUTY: {"policy_id": 5, "policy_name": "Jury Duty", "balance": 10.0},
        TimeOffTypeEnum.PARENTAL: {"policy_id": 6, "policy_name": "Parental Leave", "balance": 60.0},
        TimeOffTypeEnum.UNPAID: {"policy_id": 7, "policy_name": "Unpaid Leave", "balance": 999.0},
    }
    return balances.get(time_off_type, {"policy_id": 0, "policy_name": "Unknown", "balance": 0.0})


def calculate_days_requested(
    start_date: date,
    end_date: date,
    is_partial_start: bool = False,
    start_hours: Optional[float] = None,
    is_partial_end: bool = False,
    end_hours: Optional[float] = None,
) -> float:
    """Calculate total days requested."""
    # Simple calculation (in real implementation, would consider work schedule)
    calendar_days = (end_date - start_date).days + 1
    
    # Assume 5-day work week
    work_days = 0
    current = start_date
    while current <= end_date:
        if current.weekday() < 5:  # Monday = 0, Friday = 4
            work_days += 1
        current += timedelta(days=1)
    
    total = float(work_days)
    
    # Adjust for partial days
    if is_partial_start and start_hours:
        total -= (1 - start_hours / 8.0)
    if is_partial_end and end_hours:
        total -= (1 - end_hours / 8.0)
    
    return round(total, 2)


def check_blackout_periods(start_date: date, end_date: date) -> List[BlackoutPeriodInfo]:
    """Check for blackout period conflicts."""
    # Mock blackout periods
    blackouts = [
        {"id": 1, "name": "Year-End Freeze", "start": date(2025, 12, 15), "end": date(2025, 12, 31), "can_request": False},
        {"id": 2, "name": "Q4 Close", "start": date(2025, 9, 28), "end": date(2025, 10, 5), "can_request": True, "approval": "Director"},
    ]
    
    conflicts = []
    for blackout in blackouts:
        if not (end_date < blackout["start"] or start_date > blackout["end"]):
            overlap_start = max(start_date, blackout["start"])
            overlap_end = min(end_date, blackout["end"])
            overlap_days = (overlap_end - overlap_start).days + 1
            
            conflicts.append(BlackoutPeriodInfo(
                blackout_id=blackout["id"],
                name=blackout["name"],
                start_date=blackout["start"],
                end_date=blackout["end"],
                overlap_days=overlap_days,
                can_request=blackout.get("can_request", False),
                approval_level=blackout.get("approval"),
            ))
    
    return conflicts


def check_notice_requirement(start_date: date, time_off_type: TimeOffTypeEnum) -> NoticeRequirement:
    """Check notice requirement for the request."""
    # Different notice requirements by type
    notice_days_required = {
        TimeOffTypeEnum.PTO: 5,
        TimeOffTypeEnum.SICK_LEAVE: 0,  # No notice required
        TimeOffTypeEnum.PERSONAL: 2,
        TimeOffTypeEnum.BEREAVEMENT: 0,
        TimeOffTypeEnum.JURY_DUTY: 1,
        TimeOffTypeEnum.PARENTAL: 30,
        TimeOffTypeEnum.UNPAID: 14,
    }
    
    required = notice_days_required.get(time_off_type, 0)
    actual = (start_date - date.today()).days
    
    return NoticeRequirement(
        required_notice_days=required,
        actual_notice_days=max(0, actual),
        is_satisfied=actual >= required,
        waiver_possible=required > 0 and actual < required,
        waiver_authority="Manager" if required <= 5 else "HR Director",
    )


def validate_request(
    employee_id: int,
    request: TimeOffSubmissionRequest,
) -> ValidationResult:
    """Perform comprehensive validation of the request."""
    correlation_id = str(uuid.uuid4())
    field_errors = []
    policy_violations = []
    
    # Get balance
    balance_info = get_employee_balance(employee_id, request.time_off_type)
    
    # Calculate days requested
    days_requested = calculate_days_requested(
        request.start_date,
        request.end_date,
        request.is_partial_start_day,
        request.start_day_hours,
        request.is_partial_end_day,
        request.end_day_hours,
    )
    
    # Eligibility check (mock)
    hire_date = date(2023, 1, 15)
    days_employed = (date.today() - hire_date).days
    is_eligible = days_employed >= 90  # 90-day eligibility period
    
    eligibility = EligibilityInfo(
        is_eligible=is_eligible,
        eligibility_date=hire_date + timedelta(days=90) if not is_eligible else None,
        eligibility_message="Employee is eligible for time-off" if is_eligible else "Must complete 90-day probation period",
        restrictions=[],
    )
    
    if not is_eligible:
        field_errors.append(FieldError(
            field="employee_id",
            code="ELIGIBILITY_NOT_MET",
            message="Employee has not completed the 90-day probation period",
            severity=ValidationSeverity.ERROR,
        ))
    
    # Date validation
    if request.start_date < date.today():
        field_errors.append(FieldError(
            field="start_date",
            code="DATE_IN_PAST",
            message="Start date cannot be in the past",
            severity=ValidationSeverity.ERROR,
        ))
    
    # Balance projection
    current_balance = balance_info["balance"]
    projected_balance = current_balance - days_requested
    
    balance_projection = BalanceProjection(
        policy_id=balance_info["policy_id"],
        policy_name=balance_info["policy_name"],
        current_balance=current_balance,
        days_requested=days_requested,
        projected_balance=projected_balance,
        projected_balance_date=request.start_date,
        accruals_before_request=0.0,  # Would calculate actual accruals
        will_go_negative=projected_balance < 0,
        negative_amount=abs(projected_balance) if projected_balance < 0 else 0,
    )
    
    # Check for negative balance
    if projected_balance < 0 and request.time_off_type != TimeOffTypeEnum.UNPAID:
        policy_violations.append(PolicyViolation(
            policy_id=balance_info["policy_id"],
            policy_name=balance_info["policy_name"],
            violation_code="INSUFFICIENT_BALANCE",
            violation_type="balance",
            severity=ValidationSeverity.ERROR,
            message=f"Insufficient balance. Current: {current_balance} days, Requested: {days_requested} days",
            details={"current": current_balance, "requested": days_requested, "shortfall": abs(projected_balance)},
            can_override=False,
            override_requires_approval=False,
        ))
    
    # Blackout period check
    blackout_conflicts = check_blackout_periods(request.start_date, request.end_date)
    
    for blackout in blackout_conflicts:
        severity = ValidationSeverity.WARNING if blackout.can_request else ValidationSeverity.ERROR
        policy_violations.append(PolicyViolation(
            policy_id=0,
            policy_name="Blackout Period Policy",
            violation_code="BLACKOUT_PERIOD",
            violation_type="blackout",
            severity=severity,
            message=f"Request overlaps with blackout period: {blackout.name}",
            details={"blackout_id": blackout.blackout_id, "overlap_days": blackout.overlap_days},
            can_override=blackout.can_request,
            override_requires_approval=True,
        ))
    
    # Notice requirement check
    notice_req = check_notice_requirement(request.start_date, request.time_off_type)
    
    if not notice_req.is_satisfied:
        policy_violations.append(PolicyViolation(
            policy_id=0,
            policy_name="Notice Period Policy",
            violation_code="INSUFFICIENT_NOTICE",
            violation_type="notice",
            severity=ValidationSeverity.WARNING,
            message=f"Request does not meet notice requirement. Required: {notice_req.required_notice_days} days, Provided: {notice_req.actual_notice_days} days",
            details={"required": notice_req.required_notice_days, "actual": notice_req.actual_notice_days},
            can_override=notice_req.waiver_possible,
            override_requires_approval=True,
        ))
    
    # Count errors/warnings
    error_count = sum(1 for e in field_errors if e.severity == ValidationSeverity.ERROR)
    error_count += sum(1 for v in policy_violations if v.severity == ValidationSeverity.ERROR)
    warning_count = sum(1 for e in field_errors if e.severity == ValidationSeverity.WARNING)
    warning_count += sum(1 for v in policy_violations if v.severity == ValidationSeverity.WARNING)
    info_count = sum(1 for e in field_errors if e.severity == ValidationSeverity.INFO)
    info_count += sum(1 for v in policy_violations if v.severity == ValidationSeverity.INFO)
    
    # Determine validity
    is_valid = error_count == 0
    can_submit = is_valid or (error_count == 0 and warning_count > 0)
    
    # Summary
    if is_valid and warning_count == 0:
        summary = "Request is valid and ready for submission"
    elif is_valid and warning_count > 0:
        summary = f"Request has {warning_count} warning(s) but can be submitted"
    else:
        summary = f"Request has {error_count} error(s) that must be resolved"
    
    return ValidationResult(
        is_valid=is_valid,
        can_submit=can_submit,
        correlation_id=correlation_id,
        eligibility=eligibility,
        balance_projections=[balance_projection],
        policy_violations=policy_violations,
        field_errors=field_errors,
        blackout_conflicts=blackout_conflicts,
        notice_requirement=notice_req,
        error_count=error_count,
        warning_count=warning_count,
        info_count=info_count,
        validation_summary=summary,
        validated_at=datetime.utcnow(),
    )


# =============================================================================
# Submission Endpoint
# =============================================================================

@time_off_submission_router.post(
    "/requests",
    response_model=TimeOffSubmissionResponse,
    responses={
        400: {"model": SubmissionErrorResponse, "description": "Validation failed"},
        403: {"description": "Access denied"},
    },
    summary="Submit time-off request",
    description="Submit a new time-off request with comprehensive validation.",
)
async def submit_time_off_request(
    request: TimeOffSubmissionRequest,
):
    """
    Submit a new time-off request.
    
    This endpoint:
    - Validates employee eligibility
    - Calculates projected balances
    - Checks policy violations
    - Persists valid requests with pending status
    - Initiates approval workflow
    - Maintains audit trail
    
    **Access Control**: Employees can only submit requests for themselves.
    """
    current_user = get_current_user()
    employee_id = current_user["id"]
    
    # Validate the request
    validation_result = validate_request(employee_id, request)
    
    # If validation failed, return error response
    if not validation_result.can_submit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "correlation_id": validation_result.correlation_id,
                "error_code": "VALIDATION_FAILED",
                "error_message": validation_result.validation_summary,
                "validation_result": validation_result.dict(),
                "field_errors": [e.dict() for e in validation_result.field_errors],
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
    
    # Calculate days
    days_requested = calculate_days_requested(
        request.start_date,
        request.end_date,
        request.is_partial_start_day,
        request.start_day_hours,
        request.is_partial_end_day,
        request.end_day_hours,
    )
    
    # Create the request (mock - would persist to database)
    request_id = 10001  # Mock ID
    now = datetime.utcnow()
    
    submitted_request = SubmittedRequest(
        request_id=request_id,
        employee_id=employee_id,
        employee_name=current_user["name"],
        time_off_type=request.time_off_type,
        start_date=request.start_date,
        end_date=request.end_date,
        total_days=days_requested,
        total_hours=days_requested * 8,
        status=RequestStatusEnum.PENDING,
        reason=request.reason,
        notes=request.notes,
        submitted_at=now,
        is_urgent=request.is_urgent,
        requires_documentation=days_requested > 3 and request.time_off_type == TimeOffTypeEnum.SICK_LEAVE,
    )
    
    # Create approval workflow (mock)
    approval_workflow = ApprovalWorkflowInfo(
        workflow_id=5001,
        current_step=1,
        total_steps=2 if days_requested > 5 else 1,
        current_approver_id=current_user["manager_id"],
        current_approver_name="Jane Manager",
        estimated_completion=now + timedelta(days=2),
    )
    
    # Create audit entry
    audit_entry = AuditInfo(
        audit_id=str(uuid.uuid4()),
        action="TIME_OFF_REQUEST_SUBMITTED",
        performed_by=employee_id,
        performed_at=now,
        changes={
            "request_id": request_id,
            "type": request.time_off_type.value,
            "start_date": request.start_date.isoformat(),
            "end_date": request.end_date.isoformat(),
            "days_requested": days_requested,
        },
    )
    
    # Get balance projection
    balance_projection = validation_result.balance_projections[0] if validation_result.balance_projections else None
    if not balance_projection:
        balance_info = get_employee_balance(employee_id, request.time_off_type)
        balance_projection = BalanceProjection(
            policy_id=balance_info["policy_id"],
            policy_name=balance_info["policy_name"],
            current_balance=balance_info["balance"],
            days_requested=days_requested,
            projected_balance=balance_info["balance"] - days_requested,
            projected_balance_date=request.start_date,
            will_go_negative=False,
            negative_amount=0,
        )
    
    # Build response
    return TimeOffSubmissionResponse(
        success=True,
        correlation_id=validation_result.correlation_id,
        request=submitted_request,
        balance_update=balance_projection,
        approval_workflow=approval_workflow,
        audit=audit_entry,
        next_steps=[
            "Your request has been submitted for approval",
            f"Your manager ({approval_workflow.current_approver_name}) will review your request",
            "You will receive a notification once a decision is made",
        ],
        notifications_sent=[
            f"Email sent to {approval_workflow.current_approver_name}",
            "Confirmation email sent to you",
        ],
        created_at=now,
    )


# =============================================================================
# Validation-Only Endpoint
# =============================================================================

@time_off_submission_router.post(
    "/requests/validate",
    response_model=ValidationResult,
    summary="Validate time-off request",
    description="Validate a time-off request without creating it.",
)
async def validate_time_off_request(
    request: TimeOffSubmissionRequest,
):
    """
    Validate a time-off request without persisting.
    
    This endpoint performs the same validation as the submission endpoint but:
    - Does NOT create a database record
    - Returns only validation results
    - Enables real-time form feedback
    
    **Use Case**: Call this endpoint during form editing to provide 
    real-time validation feedback to the user.
    
    **Access Control**: Employees can only validate requests for themselves.
    """
    current_user = get_current_user()
    employee_id = current_user["id"]
    
    # Perform validation
    validation_result = validate_request(employee_id, request)
    
    return validation_result


