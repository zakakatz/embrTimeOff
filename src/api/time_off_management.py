"""Time-off request management API endpoints.

Provides endpoints for employees to view their request history
and withdraw pending requests with proper access controls and audit trails.
"""

from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.database.database import get_db


# =============================================================================
# Router Setup
# =============================================================================

router = APIRouter(
    prefix="/api/time-off/requests",
    tags=["Time-Off Request Management"],
)


# =============================================================================
# Enums
# =============================================================================

class RequestStatus(str, Enum):
    """Status of a time-off request."""
    
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    CANCELLED = "cancelled"
    WITHDRAWN = "withdrawn"


class SortOrder(str, Enum):
    """Sort order for request listing."""
    
    ASC = "asc"
    DESC = "desc"


class SortField(str, Enum):
    """Fields available for sorting."""
    
    CREATED_AT = "created_at"
    START_DATE = "start_date"
    END_DATE = "end_date"
    STATUS = "status"
    HOURS_REQUESTED = "hours_requested"


# =============================================================================
# Request/Response Models
# =============================================================================

class ApprovalSummary(BaseModel):
    """Summary of an approval action."""
    
    approver_id: UUID
    approver_name: str
    approval_level: int
    status: str
    comments: Optional[str] = None
    action_date: Optional[datetime] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "approver_id": "550e8400-e29b-41d4-a716-446655440000",
                "approver_name": "Jane Manager",
                "approval_level": 1,
                "status": "approved",
                "comments": "Approved",
                "action_date": "2024-03-10T14:30:00Z",
            }
        }


class PolicySummary(BaseModel):
    """Summary of the policy for a request."""
    
    policy_id: UUID
    policy_code: str
    policy_name: str
    request_type: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "policy_id": "660e8400-e29b-41d4-a716-446655440001",
                "policy_code": "VAC-2024",
                "policy_name": "Annual Vacation",
                "request_type": "vacation",
            }
        }


class AuditTrailEntry(BaseModel):
    """An entry in the request audit trail."""
    
    id: UUID
    action: str
    actor_id: UUID
    actor_name: str
    timestamp: datetime
    previous_status: Optional[str] = None
    new_status: Optional[str] = None
    comments: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "770e8400-e29b-41d4-a716-446655440002",
                "action": "submitted",
                "actor_id": "550e8400-e29b-41d4-a716-446655440000",
                "actor_name": "John Doe",
                "timestamp": "2024-03-05T09:00:00Z",
                "previous_status": None,
                "new_status": "pending",
                "comments": None,
            }
        }


class TimeOffRequestDetail(BaseModel):
    """Detailed time-off request information."""
    
    id: UUID
    employee_id: UUID
    policy: Optional[PolicySummary] = None
    request_type: str
    start_date: date
    end_date: date
    hours_requested: float
    status: RequestStatus
    employee_comments: Optional[str] = None
    manager_comments: Optional[str] = None
    approvals: List[ApprovalSummary] = Field(default_factory=list)
    audit_trail: List[AuditTrailEntry] = Field(default_factory=list)
    submitted_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    denied_at: Optional[datetime] = None
    withdrawn_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    # Computed properties
    is_withdrawable: bool = Field(
        default=False,
        description="Whether this request can be withdrawn",
    )
    duration_days: int = Field(
        default=0,
        description="Number of days in the request",
    )
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "880e8400-e29b-41d4-a716-446655440003",
                "employee_id": "550e8400-e29b-41d4-a716-446655440000",
                "policy": {
                    "policy_id": "660e8400-e29b-41d4-a716-446655440001",
                    "policy_code": "VAC-2024",
                    "policy_name": "Annual Vacation",
                    "request_type": "vacation",
                },
                "request_type": "vacation",
                "start_date": "2024-03-15",
                "end_date": "2024-03-22",
                "hours_requested": 56.0,
                "status": "pending",
                "employee_comments": "Family vacation",
                "manager_comments": None,
                "approvals": [],
                "audit_trail": [],
                "submitted_at": "2024-03-05T09:00:00Z",
                "approved_at": None,
                "denied_at": None,
                "withdrawn_at": None,
                "created_at": "2024-03-05T09:00:00Z",
                "updated_at": "2024-03-05T09:00:00Z",
                "is_withdrawable": True,
                "duration_days": 8,
            }
        }


class RequestHistoryResponse(BaseModel):
    """Response model for request history listing."""
    
    items: List[TimeOffRequestDetail] = Field(default_factory=list)
    total: int = Field(..., ge=0)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    total_pages: int = Field(..., ge=0)
    filters_applied: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_schema_extra = {
            "example": {
                "items": [],
                "total": 25,
                "page": 1,
                "page_size": 20,
                "total_pages": 2,
                "filters_applied": {
                    "status": "pending",
                    "start_date_from": "2024-01-01",
                },
            }
        }


class WithdrawRequestBody(BaseModel):
    """Request body for withdrawing a request."""
    
    reason: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Optional reason for withdrawal",
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "reason": "Plans changed, no longer need this time off",
            }
        }


class WithdrawResponse(BaseModel):
    """Response model for withdrawal operation."""
    
    request_id: UUID
    status: str = "withdrawn"
    withdrawn_at: datetime
    message: str
    balance_restored: Optional[float] = None
    approvers_notified: List[str] = Field(default_factory=list)
    
    class Config:
        json_schema_extra = {
            "example": {
                "request_id": "880e8400-e29b-41d4-a716-446655440003",
                "status": "withdrawn",
                "withdrawn_at": "2024-03-08T10:30:00Z",
                "message": "Request successfully withdrawn",
                "balance_restored": 56.0,
                "approvers_notified": ["jane.manager@company.com"],
            }
        }


# =============================================================================
# Authentication Dependencies (Placeholder)
# =============================================================================

class CurrentUser(BaseModel):
    """Current authenticated user."""
    
    id: UUID
    employee_id: str
    email: str
    roles: List[str] = Field(default_factory=list)


async def get_current_user() -> CurrentUser:
    """
    Get the current authenticated user.
    
    In a real implementation, this would validate the JWT token
    and return the authenticated user's information.
    """
    # Placeholder - in production, this would authenticate the request
    return CurrentUser(
        id=UUID("550e8400-e29b-41d4-a716-446655440000"),
        employee_id="EMP001",
        email="employee@company.com",
        roles=["employee"],
    )


# =============================================================================
# API Endpoints
# =============================================================================

@router.get(
    "/employee",
    response_model=RequestHistoryResponse,
    summary="Get Employee Request History",
    description="""
    Retrieve the authenticated employee's time-off request history.
    
    Supports filtering by:
    - Status (pending, approved, denied, cancelled, withdrawn)
    - Date ranges (start_date_from, start_date_to, end_date_from, end_date_to)
    - Policy/request types
    - Creation date range
    
    Results include related approval information, policy details, and audit trails.
    """,
)
async def get_employee_request_history(
    # Filter parameters
    status: Optional[RequestStatus] = Query(
        default=None,
        description="Filter by request status",
    ),
    request_type: Optional[str] = Query(
        default=None,
        description="Filter by request type (vacation, sick, etc.)",
    ),
    policy_id: Optional[UUID] = Query(
        default=None,
        description="Filter by policy ID",
    ),
    start_date_from: Optional[date] = Query(
        default=None,
        description="Filter requests with start date on or after this date",
    ),
    start_date_to: Optional[date] = Query(
        default=None,
        description="Filter requests with start date on or before this date",
    ),
    end_date_from: Optional[date] = Query(
        default=None,
        description="Filter requests with end date on or after this date",
    ),
    end_date_to: Optional[date] = Query(
        default=None,
        description="Filter requests with end date on or before this date",
    ),
    created_from: Optional[date] = Query(
        default=None,
        description="Filter requests created on or after this date",
    ),
    created_to: Optional[date] = Query(
        default=None,
        description="Filter requests created on or before this date",
    ),
    # Pagination parameters
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    # Sorting parameters
    sort_by: SortField = Query(
        default=SortField.CREATED_AT,
        description="Field to sort by",
    ),
    sort_order: SortOrder = Query(
        default=SortOrder.DESC,
        description="Sort order (asc or desc)",
    ),
    # Include flags
    include_audit_trail: bool = Query(
        default=False,
        description="Include full audit trail for each request",
    ),
    include_approvals: bool = Query(
        default=True,
        description="Include approval information",
    ),
    # Dependencies
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RequestHistoryResponse:
    """
    Get the authenticated employee's time-off request history.
    
    Returns paginated list of requests with optional filtering
    and includes related approval information, policy details,
    and audit trails.
    """
    # Build filters dictionary for response
    filters_applied: Dict[str, Any] = {}
    if status:
        filters_applied["status"] = status.value
    if request_type:
        filters_applied["request_type"] = request_type
    if policy_id:
        filters_applied["policy_id"] = str(policy_id)
    if start_date_from:
        filters_applied["start_date_from"] = start_date_from.isoformat()
    if start_date_to:
        filters_applied["start_date_to"] = start_date_to.isoformat()
    if end_date_from:
        filters_applied["end_date_from"] = end_date_from.isoformat()
    if end_date_to:
        filters_applied["end_date_to"] = end_date_to.isoformat()
    if created_from:
        filters_applied["created_from"] = created_from.isoformat()
    if created_to:
        filters_applied["created_to"] = created_to.isoformat()
    
    # In a real implementation:
    # 1. Query TimeOffRequest table filtered by employee_id = current_user.id
    # 2. Apply all filter conditions
    # 3. Join with Policy, Approval, and AuditLog tables as needed
    # 4. Apply pagination and sorting
    # 5. Calculate is_withdrawable for each request
    
    # Placeholder response
    total = 0
    total_pages = 0 if total == 0 else (total + page_size - 1) // page_size
    
    return RequestHistoryResponse(
        items=[],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        filters_applied=filters_applied,
    )


@router.get(
    "/employee/{request_id}",
    response_model=TimeOffRequestDetail,
    summary="Get Request Details",
    description="Retrieve detailed information for a specific time-off request.",
)
async def get_request_details(
    request_id: UUID,
    include_audit_trail: bool = Query(
        default=True,
        description="Include full audit trail",
    ),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TimeOffRequestDetail:
    """
    Get detailed information for a specific time-off request.
    
    Validates that the request belongs to the authenticated employee
    before returning details.
    """
    # In a real implementation:
    # 1. Query TimeOffRequest by request_id
    # 2. Validate request.employee_id == current_user.id
    # 3. Load related Policy, Approvals, and AuditLog
    # 4. Calculate is_withdrawable
    
    # Placeholder - would return 404 if not found or 403 if not owned
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Request {request_id} not found",
    )


@router.put(
    "/{request_id}/withdraw",
    response_model=WithdrawResponse,
    summary="Withdraw Time-Off Request",
    description="""
    Withdraw a pending time-off request.
    
    This operation:
    - Validates the request belongs to the authenticated employee
    - Validates the request is in a withdrawable status (pending)
    - Updates the request status to 'withdrawn'
    - Creates an audit trail entry
    - Reverses any balance holds
    - Notifies relevant approvers
    
    Only pending requests can be withdrawn.
    """,
)
async def withdraw_request(
    request_id: UUID,
    body: WithdrawRequestBody = None,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WithdrawResponse:
    """
    Withdraw a pending time-off request.
    
    Performs all validation, updates status, creates audit trail,
    reverses balance holds, and notifies approvers.
    """
    # In a real implementation:
    # 1. Start database transaction
    try:
        # 2. Query and lock the request for update
        request = _get_request_for_update(db, request_id)
        
        if request is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Request {request_id} not found",
            )
        
        # 3. Validate ownership
        # if request.employee_id != current_user.id:
        #     raise HTTPException(
        #         status_code=status.HTTP_403_FORBIDDEN,
        #         detail="You can only withdraw your own requests",
        #     )
        
        # 4. Validate withdrawable status
        # withdrawable_statuses = [RequestStatus.PENDING]
        # if request.status not in withdrawable_statuses:
        #     raise HTTPException(
        #         status_code=status.HTTP_400_BAD_REQUEST,
        #         detail=f"Request cannot be withdrawn. Current status: {request.status}",
        #     )
        
        # 5. Update request status
        # request.status = RequestStatus.WITHDRAWN
        # request.withdrawn_at = datetime.utcnow()
        # request.updated_at = datetime.utcnow()
        
        # 6. Create audit trail entry
        # _create_audit_entry(
        #     db,
        #     request_id=request_id,
        #     action="withdrawn",
        #     actor_id=current_user.id,
        #     previous_status="pending",
        #     new_status="withdrawn",
        #     comments=body.reason if body else None,
        # )
        
        # 7. Reverse balance hold
        # balance_restored = _reverse_balance_hold(db, request)
        balance_restored = 0.0
        
        # 8. Notify approvers
        # approvers_notified = _notify_approvers_of_withdrawal(request)
        approvers_notified: List[str] = []
        
        # 9. Commit transaction
        # db.commit()
        
        # Placeholder response
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Request {request_id} not found",
        )
        
    except HTTPException:
        raise
    except Exception as e:
        # db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to withdraw request: {str(e)}",
        )


# =============================================================================
# Helper Functions
# =============================================================================

def _get_request_for_update(db: Session, request_id: UUID) -> Optional[Any]:
    """
    Get a request with a lock for update.
    
    In a real implementation, this would query with FOR UPDATE lock.
    """
    # Placeholder
    return None


def _is_withdrawable(request: Any) -> bool:
    """
    Determine if a request can be withdrawn.
    
    A request is withdrawable if:
    - Status is 'pending'
    - Start date has not passed
    """
    if request is None:
        return False
    
    # Check status
    withdrawable_statuses = ["pending"]
    if request.status not in withdrawable_statuses:
        return False
    
    # Check if request period has started
    if hasattr(request, 'start_date') and request.start_date:
        if request.start_date <= date.today():
            return False
    
    return True


def _create_audit_entry(
    db: Session,
    request_id: UUID,
    action: str,
    actor_id: UUID,
    previous_status: Optional[str] = None,
    new_status: Optional[str] = None,
    comments: Optional[str] = None,
) -> None:
    """Create an audit trail entry for a request action."""
    # In a real implementation:
    # audit_entry = RequestAuditLog(
    #     request_id=request_id,
    #     action=action,
    #     actor_id=actor_id,
    #     previous_status=previous_status,
    #     new_status=new_status,
    #     comments=comments,
    #     created_at=datetime.utcnow(),
    # )
    # db.add(audit_entry)
    pass


def _reverse_balance_hold(db: Session, request: Any) -> float:
    """
    Reverse the balance hold for a withdrawn request.
    
    Returns the amount of balance restored.
    """
    # In a real implementation:
    # 1. Find the balance hold record for this request
    # 2. Restore the held amount to available balance
    # 3. Delete or mark the hold as reversed
    # 4. Create balance transaction record
    if request and hasattr(request, 'hours_requested'):
        return float(request.hours_requested)
    return 0.0


def _notify_approvers_of_withdrawal(request: Any) -> List[str]:
    """
    Notify relevant approvers that a request was withdrawn.
    
    Returns list of notified email addresses.
    """
    # In a real implementation:
    # 1. Find pending approvers for this request
    # 2. Send notification emails/messages
    # 3. Return list of notified addresses
    return []


def _calculate_duration_days(start_date: date, end_date: date) -> int:
    """Calculate the number of days in a request."""
    return (end_date - start_date).days + 1


# =============================================================================
# Statistics Endpoints (Bonus)
# =============================================================================

class RequestStatistics(BaseModel):
    """Statistics about employee's time-off requests."""
    
    total_requests: int = 0
    pending_count: int = 0
    approved_count: int = 0
    denied_count: int = 0
    withdrawn_count: int = 0
    cancelled_count: int = 0
    total_hours_approved: float = 0.0
    total_hours_pending: float = 0.0
    
    class Config:
        json_schema_extra = {
            "example": {
                "total_requests": 15,
                "pending_count": 2,
                "approved_count": 10,
                "denied_count": 1,
                "withdrawn_count": 1,
                "cancelled_count": 1,
                "total_hours_approved": 120.0,
                "total_hours_pending": 24.0,
            }
        }


@router.get(
    "/employee/statistics",
    response_model=RequestStatistics,
    summary="Get Request Statistics",
    description="Get statistics about the employee's time-off requests.",
)
async def get_request_statistics(
    year: Optional[int] = Query(
        default=None,
        description="Filter by year (defaults to current year)",
    ),
    policy_id: Optional[UUID] = Query(
        default=None,
        description="Filter by policy ID",
    ),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RequestStatistics:
    """
    Get statistics about the employee's time-off requests.
    
    Can be filtered by year and policy.
    """
    # In a real implementation:
    # 1. Query aggregate statistics for the employee
    # 2. Apply year and policy filters
    
    # Placeholder response
    return RequestStatistics()

