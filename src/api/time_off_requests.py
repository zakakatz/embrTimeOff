"""API endpoints for time-off request creation and retrieval."""

import json
import uuid
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, Query, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.models.employee import Employee
from src.utils.auth import CurrentUser, UserRole, get_mock_current_user
from src.utils.errors import ForbiddenError, NotFoundError, ValidationError


# =============================================================================
# Enums
# =============================================================================

class TimeOffType(str, Enum):
    """Types of time off."""
    
    VACATION = "vacation"
    SICK = "sick"
    PERSONAL = "personal"
    BEREAVEMENT = "bereavement"
    JURY_DUTY = "jury_duty"
    PARENTAL = "parental"
    UNPAID = "unpaid"
    FLOATING_HOLIDAY = "floating_holiday"
    COMPENSATORY = "compensatory"


class RequestStatus(str, Enum):
    """Status of time-off request."""
    
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


# =============================================================================
# Request Models
# =============================================================================

class CreateTimeOffRequest(BaseModel):
    """Request to create a time-off request."""
    
    employee_id: int = Field(..., description="Employee submitting the request")
    request_type: TimeOffType = Field(..., description="Type of time off")
    start_date: date = Field(..., description="Start date")
    end_date: date = Field(..., description="End date")
    
    # Optional half-day handling
    is_half_day: bool = Field(default=False, description="Is this a half day request")
    half_day_period: Optional[str] = Field(
        None,
        description="For half days: 'morning' or 'afternoon'",
    )
    
    # Reason and notes
    reason: Optional[str] = Field(None, max_length=1000, description="Reason for time off")
    notes: Optional[str] = Field(None, max_length=2000, description="Additional notes")
    
    # Submit immediately or save as draft
    submit: bool = Field(default=True, description="Submit immediately or save as draft")
    
    @field_validator("end_date")
    @classmethod
    def validate_dates(cls, v: date, info) -> date:
        """Validate end date is not before start date."""
        start = info.data.get("start_date")
        if start and v < start:
            raise ValueError("End date cannot be before start date")
        return v
    
    @field_validator("half_day_period")
    @classmethod
    def validate_half_day_period(cls, v: Optional[str], info) -> Optional[str]:
        """Validate half day period is set when is_half_day is True."""
        is_half = info.data.get("is_half_day")
        if is_half and not v:
            raise ValueError("Half day period required when is_half_day is True")
        if v and v not in ("morning", "afternoon"):
            raise ValueError("Half day period must be 'morning' or 'afternoon'")
        return v


# =============================================================================
# Response Models
# =============================================================================

class BalanceImpact(BaseModel):
    """Impact on time-off balance."""
    
    balance_type: str
    current_balance: float
    requested_days: float
    projected_remaining: float
    sufficient_balance: bool = Field(default=True)
    warning_message: Optional[str] = None


class ConflictInfo(BaseModel):
    """Information about scheduling conflicts."""
    
    conflict_type: str = Field(..., description="Type of conflict")
    description: str = Field(..., description="Conflict description")
    dates: List[date] = Field(default_factory=list, description="Affected dates")
    is_blocking: bool = Field(default=False, description="Whether conflict blocks request")


class ApproverInfo(BaseModel):
    """Information about assigned approver."""
    
    approver_id: int
    approver_name: str
    approver_title: Optional[str] = None
    approval_level: int = Field(default=1)


class ApprovalHistoryEntry(BaseModel):
    """Entry in approval history."""
    
    action: str
    performed_by: str
    performed_at: datetime
    notes: Optional[str] = None
    previous_status: Optional[str] = None
    new_status: Optional[str] = None


class TimeOffRequestResponse(BaseModel):
    """Response for a time-off request."""
    
    id: int
    employee_id: int
    employee_name: Optional[str] = None
    
    # Request details
    request_type: str
    start_date: date
    end_date: date
    total_days: float
    is_half_day: bool = Field(default=False)
    half_day_period: Optional[str] = None
    
    # Content
    reason: Optional[str] = None
    notes: Optional[str] = None
    
    # Status
    status: str
    
    # Approver
    approver: Optional[ApproverInfo] = None
    approver_notes: Optional[str] = None
    rejection_reason: Optional[str] = None
    
    # Balance impact
    balance_impact: Optional[BalanceImpact] = None
    
    # Conflicts
    conflicts: List[ConflictInfo] = Field(default_factory=list)
    
    # Approval history
    approval_history: List[ApprovalHistoryEntry] = Field(default_factory=list)
    
    # Timestamps
    created_at: datetime
    submitted_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None


class CreateTimeOffResponse(BaseModel):
    """Response after creating a time-off request."""
    
    request: TimeOffRequestResponse
    message: str = Field(default="Time-off request created successfully")
    audit_id: Optional[str] = None


class TimeOffRequestListResponse(BaseModel):
    """List of time-off requests."""
    
    requests: List[TimeOffRequestResponse]
    total: int
    page: int = Field(default=1)
    page_size: int = Field(default=20)


# =============================================================================
# Mock Data Store (In-memory for demo)
# =============================================================================

# In a real implementation, these would be database operations
_request_counter = 1000
_requests: Dict[int, Dict[str, Any]] = {}
_audit_log: List[Dict[str, Any]] = []


def get_next_request_id() -> int:
    """Get next request ID."""
    global _request_counter
    _request_counter += 1
    return _request_counter


# =============================================================================
# Helper Functions
# =============================================================================

def calculate_business_days(start: date, end: date) -> float:
    """Calculate business days between two dates."""
    if start > end:
        return 0
    
    days = 0
    current = start
    while current <= end:
        # Skip weekends (5 = Saturday, 6 = Sunday)
        if current.weekday() < 5:
            days += 1
        current += timedelta(days=1)
    
    return float(days)


def get_employee_balance(
    employee_id: int,
    balance_type: str,
    session: Session,
) -> float:
    """Get employee's current time-off balance."""
    # In a real implementation, query TimeOffBalance table
    # For demo, return mock balance
    balances = {
        TimeOffType.VACATION.value: 15.0,
        TimeOffType.SICK.value: 10.0,
        TimeOffType.PERSONAL.value: 3.0,
    }
    return balances.get(balance_type, 0.0)


def check_employee_eligibility(
    employee_id: int,
    request_type: str,
    session: Session,
) -> tuple[bool, Optional[str]]:
    """Check if employee is eligible for this type of time off."""
    # Get employee
    employee = session.get(Employee, employee_id)
    if not employee:
        return False, "Employee not found"
    
    if not employee.is_active:
        return False, "Employee is not active"
    
    # Check probation period (example: no vacation in first 90 days)
    if employee.hire_date:
        days_employed = (date.today() - employee.hire_date).days
        if request_type == TimeOffType.VACATION.value and days_employed < 90:
            return False, "Vacation requests not allowed during probationary period"
    
    return True, None


def detect_conflicts(
    employee_id: int,
    start: date,
    end: date,
    session: Session,
) -> List[ConflictInfo]:
    """Detect scheduling conflicts for requested dates."""
    conflicts = []
    
    # Check for existing requests (mock)
    for req_id, req in _requests.items():
        if req["employee_id"] == employee_id:
            if req["status"] not in ("rejected", "cancelled"):
                req_start = req["start_date"]
                req_end = req["end_date"]
                
                # Check for overlap
                if start <= req_end and end >= req_start:
                    conflicts.append(ConflictInfo(
                        conflict_type="existing_request",
                        description=f"Overlaps with existing {req['request_type']} request",
                        dates=[start, end],
                        is_blocking=True,
                    ))
    
    # Check for blackout dates (mock - December 25)
    current = start
    blackout_dates = []
    while current <= end:
        if current.month == 12 and current.day == 25:
            blackout_dates.append(current)
        current += timedelta(days=1)
    
    if blackout_dates:
        conflicts.append(ConflictInfo(
            conflict_type="blackout_date",
            description="Request includes company blackout dates",
            dates=blackout_dates,
            is_blocking=False,
        ))
    
    return conflicts


def get_approver_for_employee(
    employee_id: int,
    session: Session,
) -> Optional[ApproverInfo]:
    """Get the approver for an employee's time-off request."""
    employee = session.get(Employee, employee_id)
    if not employee or not employee.manager_id:
        return None
    
    manager = session.get(Employee, employee.manager_id)
    if not manager:
        return None
    
    return ApproverInfo(
        approver_id=manager.id,
        approver_name=f"{manager.first_name} {manager.last_name}",
        approver_title=manager.job_title,
        approval_level=1,
    )


def create_audit_entry(
    request_id: int,
    action: str,
    performed_by: int,
    performed_by_name: str,
    previous_status: Optional[str] = None,
    new_status: Optional[str] = None,
    notes: Optional[str] = None,
) -> str:
    """Create an audit trail entry."""
    audit_id = str(uuid.uuid4())
    entry = {
        "id": audit_id,
        "request_id": request_id,
        "action": action,
        "performed_by": performed_by,
        "performed_by_name": performed_by_name,
        "previous_status": previous_status,
        "new_status": new_status,
        "notes": notes,
        "performed_at": datetime.utcnow(),
    }
    _audit_log.append(entry)
    return audit_id


def get_request_audit_history(request_id: int) -> List[ApprovalHistoryEntry]:
    """Get audit history for a request."""
    history = []
    for entry in _audit_log:
        if entry["request_id"] == request_id:
            history.append(ApprovalHistoryEntry(
                action=entry["action"],
                performed_by=entry["performed_by_name"],
                performed_at=entry["performed_at"],
                notes=entry.get("notes"),
                previous_status=entry.get("previous_status"),
                new_status=entry.get("new_status"),
            ))
    return sorted(history, key=lambda x: x.performed_at)


# =============================================================================
# Dependency Injection
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
    
    roles = [UserRole.EMPLOYEE]
    if x_user_role:
        try:
            roles = [UserRole(x_user_role)]
        except ValueError:
            pass
    
    return get_mock_current_user(
        user_id=user_id,
        employee_id=x_employee_id,
        roles=roles,
    )


# =============================================================================
# Router Setup
# =============================================================================

time_off_router = APIRouter(
    prefix="/api/time-off-requests",
    tags=["Time Off Requests"],
)


# =============================================================================
# Endpoints
# =============================================================================

@time_off_router.post(
    "",
    response_model=CreateTimeOffResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Time-Off Request",
    description="Submit a new time-off request.",
)
async def create_time_off_request(
    request: CreateTimeOffRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> CreateTimeOffResponse:
    """
    Create a new time-off request.
    
    - Validates employee eligibility
    - Calculates balance impact
    - Detects scheduling conflicts
    - Initiates approval workflow
    - Creates audit trail entry
    """
    # Verify the request is for self or user has permission
    if request.employee_id != current_user.employee_id:
        if not any(r in current_user.roles for r in [UserRole.HR, UserRole.ADMIN]):
            raise ForbiddenError(message="Cannot create requests for other employees")
    
    # Check employee eligibility
    eligible, error_msg = check_employee_eligibility(
        request.employee_id,
        request.request_type.value,
        session,
    )
    
    if not eligible:
        raise ValidationError(
            message=error_msg or "Employee not eligible",
            field_errors=[{"field": "employee_id", "message": error_msg}],
        )
    
    # Calculate total days
    total_days = calculate_business_days(request.start_date, request.end_date)
    if request.is_half_day:
        total_days = 0.5
    
    # Check balance
    current_balance = get_employee_balance(
        request.employee_id,
        request.request_type.value,
        session,
    )
    projected_remaining = current_balance - total_days
    sufficient_balance = projected_remaining >= 0
    
    balance_impact = BalanceImpact(
        balance_type=request.request_type.value,
        current_balance=current_balance,
        requested_days=total_days,
        projected_remaining=projected_remaining,
        sufficient_balance=sufficient_balance,
        warning_message=None if sufficient_balance else "Insufficient balance for this request",
    )
    
    # Detect conflicts
    conflicts = detect_conflicts(
        request.employee_id,
        request.start_date,
        request.end_date,
        session,
    )
    
    # Check for blocking conflicts
    blocking_conflicts = [c for c in conflicts if c.is_blocking]
    if blocking_conflicts:
        raise ValidationError(
            message="Request has blocking conflicts",
            field_errors=[
                {"field": "dates", "message": c.description}
                for c in blocking_conflicts
            ],
        )
    
    # Get approver
    approver = get_approver_for_employee(request.employee_id, session)
    
    # Determine initial status
    initial_status = RequestStatus.DRAFT.value if not request.submit else RequestStatus.PENDING_APPROVAL.value
    
    # Create the request
    request_id = get_next_request_id()
    now = datetime.utcnow()
    
    # Get employee name
    employee = session.get(Employee, request.employee_id)
    employee_name = f"{employee.first_name} {employee.last_name}" if employee else None
    
    request_data = {
        "id": request_id,
        "employee_id": request.employee_id,
        "employee_name": employee_name,
        "request_type": request.request_type.value,
        "start_date": request.start_date,
        "end_date": request.end_date,
        "total_days": total_days,
        "is_half_day": request.is_half_day,
        "half_day_period": request.half_day_period,
        "reason": request.reason,
        "notes": request.notes,
        "status": initial_status,
        "approver": approver,
        "balance_impact": balance_impact,
        "conflicts": conflicts,
        "created_at": now,
        "submitted_at": now if request.submit else None,
    }
    
    _requests[request_id] = request_data
    
    # Create audit entry
    audit_id = create_audit_entry(
        request_id=request_id,
        action="created" if not request.submit else "submitted",
        performed_by=current_user.employee_id or 0,
        performed_by_name=employee_name or "System",
        previous_status=None,
        new_status=initial_status,
        notes=f"Request created for {total_days} days of {request.request_type.value}",
    )
    
    # Build response
    response = TimeOffRequestResponse(
        id=request_id,
        employee_id=request.employee_id,
        employee_name=employee_name,
        request_type=request.request_type.value,
        start_date=request.start_date,
        end_date=request.end_date,
        total_days=total_days,
        is_half_day=request.is_half_day,
        half_day_period=request.half_day_period,
        reason=request.reason,
        notes=request.notes,
        status=initial_status,
        approver=approver,
        balance_impact=balance_impact,
        conflicts=conflicts,
        approval_history=get_request_audit_history(request_id),
        created_at=now,
        submitted_at=now if request.submit else None,
    )
    
    return CreateTimeOffResponse(
        request=response,
        message="Time-off request submitted successfully" if request.submit else "Draft saved",
        audit_id=audit_id,
    )


@time_off_router.get(
    "/{request_id}",
    response_model=TimeOffRequestResponse,
    summary="Get Time-Off Request",
    description="Retrieve details of a specific time-off request.",
)
async def get_time_off_request(
    request_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> TimeOffRequestResponse:
    """
    Get a specific time-off request.
    
    - Enforces access controls
    - Returns comprehensive request details
    - Includes balance impact and approval history
    """
    # Check if request exists
    if request_id not in _requests:
        raise NotFoundError(message=f"Time-off request {request_id} not found")
    
    request_data = _requests[request_id]
    
    # Check access
    can_view = False
    
    # Employee can view their own
    if request_data["employee_id"] == current_user.employee_id:
        can_view = True
    
    # Approver can view
    approver = request_data.get("approver")
    if approver and approver.approver_id == current_user.employee_id:
        can_view = True
    
    # HR/Admin can view all
    if any(r in current_user.roles for r in [UserRole.HR, UserRole.ADMIN]):
        can_view = True
    
    # Manager can view their reports
    if UserRole.MANAGER in current_user.roles:
        # Check if the employee reports to this manager
        employee = session.get(Employee, request_data["employee_id"])
        if employee and employee.manager_id == current_user.employee_id:
            can_view = True
    
    if not can_view:
        raise ForbiddenError(message="Not authorized to view this request")
    
    return TimeOffRequestResponse(
        id=request_data["id"],
        employee_id=request_data["employee_id"],
        employee_name=request_data.get("employee_name"),
        request_type=request_data["request_type"],
        start_date=request_data["start_date"],
        end_date=request_data["end_date"],
        total_days=request_data["total_days"],
        is_half_day=request_data.get("is_half_day", False),
        half_day_period=request_data.get("half_day_period"),
        reason=request_data.get("reason"),
        notes=request_data.get("notes"),
        status=request_data["status"],
        approver=request_data.get("approver"),
        approver_notes=request_data.get("approver_notes"),
        rejection_reason=request_data.get("rejection_reason"),
        balance_impact=request_data.get("balance_impact"),
        conflicts=request_data.get("conflicts", []),
        approval_history=get_request_audit_history(request_id),
        created_at=request_data["created_at"],
        submitted_at=request_data.get("submitted_at"),
        approved_at=request_data.get("approved_at"),
        rejected_at=request_data.get("rejected_at"),
    )


@time_off_router.get(
    "",
    response_model=TimeOffRequestListResponse,
    summary="List Time-Off Requests",
    description="List time-off requests with filtering.",
)
async def list_time_off_requests(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    employee_id: Optional[int] = Query(None, description="Filter by employee"),
    status: Optional[str] = Query(None, description="Filter by status"),
    start_date: Optional[date] = Query(None, description="Filter by start date"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> TimeOffRequestListResponse:
    """List time-off requests with access controls."""
    results = []
    
    for req_id, req in _requests.items():
        # Apply filters
        if employee_id and req["employee_id"] != employee_id:
            continue
        if status and req["status"] != status:
            continue
        if start_date and req["start_date"] < start_date:
            continue
        
        # Check access
        can_view = False
        if req["employee_id"] == current_user.employee_id:
            can_view = True
        if any(r in current_user.roles for r in [UserRole.HR, UserRole.ADMIN]):
            can_view = True
        if UserRole.MANAGER in current_user.roles:
            employee = session.get(Employee, req["employee_id"])
            if employee and employee.manager_id == current_user.employee_id:
                can_view = True
        
        if can_view:
            results.append(TimeOffRequestResponse(
                id=req["id"],
                employee_id=req["employee_id"],
                employee_name=req.get("employee_name"),
                request_type=req["request_type"],
                start_date=req["start_date"],
                end_date=req["end_date"],
                total_days=req["total_days"],
                is_half_day=req.get("is_half_day", False),
                half_day_period=req.get("half_day_period"),
                reason=req.get("reason"),
                notes=req.get("notes"),
                status=req["status"],
                approver=req.get("approver"),
                balance_impact=req.get("balance_impact"),
                conflicts=req.get("conflicts", []),
                approval_history=get_request_audit_history(req_id),
                created_at=req["created_at"],
                submitted_at=req.get("submitted_at"),
            ))
    
    # Paginate
    total = len(results)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paged_results = results[start_idx:end_idx]
    
    return TimeOffRequestListResponse(
        requests=paged_results,
        total=total,
        page=page,
        page_size=page_size,
    )

