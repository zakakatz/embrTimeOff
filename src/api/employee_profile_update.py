"""API endpoints for employee profile updates with approval workflow."""

import uuid
from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.employee_profile import (
    FIELD_DEFINITIONS,
    ROLE_PERMISSIONS,
    FieldCategory,
    FieldPermissionLevel,
    get_field_permissions,
)
from src.database.database import get_db
from src.models.employee import Employee
from src.utils.auth import CurrentUser, UserRole, get_mock_current_user
from src.utils.errors import APIError, ForbiddenError, NotFoundError, ValidationError


# =============================================================================
# Enums
# =============================================================================

class UpdateRequestStatus(str, Enum):
    """Status of an update request."""
    
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class UpdateType(str, Enum):
    """Type of profile update."""
    
    DIRECT = "direct"  # Applied immediately
    APPROVAL_REQUIRED = "approval_required"  # Needs approval


# =============================================================================
# In-Memory State (would be database in production)
# =============================================================================

class UpdateRequestStore:
    """In-memory store for update requests."""
    
    def __init__(self):
        self.requests: Dict[str, Dict[str, Any]] = {}
    
    def create(self, request_id: uuid.UUID, data: Dict[str, Any]) -> Dict[str, Any]:
        self.requests[str(request_id)] = data
        return data
    
    def get(self, request_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        return self.requests.get(str(request_id))
    
    def update(self, request_id: uuid.UUID, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        req = self.requests.get(str(request_id))
        if req:
            req.update(updates)
        return req
    
    def list_by_employee(self, employee_id: int) -> List[Dict[str, Any]]:
        return [r for r in self.requests.values() if r.get("employee_id") == employee_id]


update_store = UpdateRequestStore()


# =============================================================================
# Request/Response Models
# =============================================================================

class FieldUpdate(BaseModel):
    """A single field update."""
    
    field_name: str = Field(..., description="Name of field to update")
    new_value: Any = Field(..., description="New value for the field")
    reason: Optional[str] = Field(None, description="Reason for change (required for some fields)")


class ProfileUpdateRequest(BaseModel):
    """Request to update profile fields."""
    
    updates: List[FieldUpdate] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="List of field updates"
    )
    effective_date: Optional[datetime] = Field(
        None,
        description="When changes should take effect (defaults to immediately)"
    )
    
    @field_validator('updates')
    @classmethod
    def validate_updates(cls, v: List[FieldUpdate]) -> List[FieldUpdate]:
        # Check for duplicate fields
        fields = [u.field_name for u in v]
        if len(fields) != len(set(fields)):
            raise ValueError("Duplicate fields in update request")
        return v


class FieldUpdateResult(BaseModel):
    """Result of a single field update."""
    
    field_name: str = Field(..., description="Field name")
    status: str = Field(..., description="Update status (applied, pending_approval, rejected)")
    old_value: Optional[Any] = Field(None, description="Previous value")
    new_value: Any = Field(..., description="New value")
    message: Optional[str] = Field(None, description="Status message")
    request_id: Optional[uuid.UUID] = Field(None, description="Update request ID if approval required")


class ProfileUpdateResponse(BaseModel):
    """Response for profile update."""
    
    employee_id: str = Field(..., description="Employee identifier")
    direct_updates: List[FieldUpdateResult] = Field(
        default_factory=list,
        description="Updates applied directly"
    )
    approval_requests: List[FieldUpdateResult] = Field(
        default_factory=list,
        description="Updates requiring approval"
    )
    rejected_updates: List[FieldUpdateResult] = Field(
        default_factory=list,
        description="Updates rejected due to permissions"
    )
    summary: Dict[str, int] = Field(
        default_factory=dict,
        description="Summary counts"
    )
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class UpdateRequestDetail(BaseModel):
    """Details of an update request."""
    
    request_id: uuid.UUID = Field(..., description="Request ID")
    employee_id: int = Field(..., description="Employee ID")
    field_name: str = Field(..., description="Field being updated")
    old_value: Optional[Any] = Field(None, description="Current value")
    new_value: Any = Field(..., description="Requested new value")
    reason: Optional[str] = Field(None, description="Reason for change")
    status: UpdateRequestStatus = Field(..., description="Request status")
    requested_by: str = Field(..., description="Who requested the change")
    requested_at: datetime = Field(..., description="When requested")
    reviewed_by: Optional[str] = Field(None, description="Who reviewed")
    reviewed_at: Optional[datetime] = Field(None, description="When reviewed")
    review_notes: Optional[str] = Field(None, description="Review notes")
    effective_date: Optional[datetime] = Field(None, description="When change takes effect")


class UpdateRequestListResponse(BaseModel):
    """List of update requests."""
    
    requests: List[UpdateRequestDetail] = Field(default_factory=list)
    total: int = Field(default=0)
    pending_count: int = Field(default=0)


class ApprovalDecision(BaseModel):
    """Decision on an update request."""
    
    approved: bool = Field(..., description="Whether to approve the request")
    notes: Optional[str] = Field(None, description="Review notes")


class ApprovalResponse(BaseModel):
    """Response for approval decision."""
    
    request_id: uuid.UUID = Field(..., description="Request ID")
    status: UpdateRequestStatus = Field(..., description="New status")
    applied: bool = Field(default=False, description="Whether update was applied")
    message: str = Field(..., description="Result message")


# =============================================================================
# Validation Functions
# =============================================================================

def validate_field_value(field_name: str, value: Any) -> List[str]:
    """Validate a field value."""
    errors = []
    field_def = FIELD_DEFINITIONS.get(field_name)
    
    if not field_def:
        errors.append(f"Unknown field: {field_name}")
        return errors
    
    # Type-specific validation
    if field_name in ["email", "personal_email"]:
        if value and "@" not in str(value):
            errors.append("Invalid email format")
    
    if field_name in ["phone_number", "mobile_number"]:
        if value:
            import re
            if not re.match(r'^[\d\s\-\(\)\+\.]+$', str(value)):
                errors.append("Invalid phone number format")
    
    if field_name in ["date_of_birth", "hire_date", "termination_date"]:
        if value:
            try:
                datetime.fromisoformat(str(value).replace('Z', '+00:00'))
            except ValueError:
                errors.append("Invalid date format (use ISO format)")
    
    return errors


def get_approval_requirements(field_name: str, user_role: UserRole) -> Dict[str, Any]:
    """Determine approval requirements for a field update."""
    role_config = ROLE_PERMISSIONS.get(user_role, ROLE_PERMISSIONS[UserRole.EMPLOYEE])
    
    write_all = "*" in role_config.get("write", [])
    can_write = write_all or field_name in role_config.get("write", [])
    requires_approval = field_name in role_config.get("approval_required", [])
    
    return {
        "can_update": can_write or requires_approval,
        "requires_approval": requires_approval,
        "approver_role": "HR_MANAGER" if requires_approval else None,
    }


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

employee_profile_update_router = APIRouter(
    prefix="/api/employee-profile",
    tags=["Employee Profile Updates"],
)


# =============================================================================
# Endpoints
# =============================================================================

@employee_profile_update_router.put(
    "/my-profile",
    response_model=ProfileUpdateResponse,
    summary="Update My Profile",
    description="Update profile fields with permission validation and approval routing.",
)
async def update_my_profile(
    request: ProfileUpdateRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> ProfileUpdateResponse:
    """
    Update the authenticated employee's profile.
    
    - Validates updates against permission policies
    - Applies direct updates for permitted fields
    - Creates approval requests for restricted fields
    - Rejects updates for unauthorized fields
    - Maintains comprehensive audit trail
    """
    if not current_user.employee_id:
        raise ForbiddenError(message="Employee ID not found in authentication context")
    
    # Fetch employee
    stmt = select(Employee).where(Employee.id == current_user.employee_id)
    result = session.execute(stmt)
    employee = result.scalar_one_or_none()
    
    if not employee:
        raise NotFoundError(message="Employee profile not found")
    
    user_role = current_user.roles[0] if current_user.roles else UserRole.EMPLOYEE
    permissions = get_field_permissions(user_role, is_own_profile=True)
    
    direct_updates: List[FieldUpdateResult] = []
    approval_requests: List[FieldUpdateResult] = []
    rejected_updates: List[FieldUpdateResult] = []
    
    for update in request.updates:
        field_name = update.field_name
        new_value = update.new_value
        
        # Check if field exists
        if field_name not in FIELD_DEFINITIONS:
            rejected_updates.append(FieldUpdateResult(
                field_name=field_name,
                status="rejected",
                new_value=new_value,
                message=f"Unknown field: {field_name}",
            ))
            continue
        
        # Get permission
        permission = permissions.get(field_name)
        if not permission:
            rejected_updates.append(FieldUpdateResult(
                field_name=field_name,
                status="rejected",
                new_value=new_value,
                message="Field not found in permissions",
            ))
            continue
        
        # Check write permission
        if not permission.can_write:
            rejected_updates.append(FieldUpdateResult(
                field_name=field_name,
                status="rejected",
                old_value=getattr(employee, field_name, None),
                new_value=new_value,
                message=f"You don't have permission to update {field_name}",
            ))
            continue
        
        # Validate value
        validation_errors = validate_field_value(field_name, new_value)
        if validation_errors:
            rejected_updates.append(FieldUpdateResult(
                field_name=field_name,
                status="rejected",
                new_value=new_value,
                message="; ".join(validation_errors),
            ))
            continue
        
        old_value = getattr(employee, field_name, None)
        
        # Check if approval required
        if permission.requires_approval:
            # Create approval request
            request_id = uuid.uuid4()
            update_store.create(request_id, {
                "request_id": str(request_id),
                "employee_id": current_user.employee_id,
                "field_name": field_name,
                "old_value": old_value,
                "new_value": new_value,
                "reason": update.reason,
                "status": UpdateRequestStatus.PENDING,
                "requested_by": str(current_user.id),
                "requested_at": datetime.utcnow(),
                "effective_date": request.effective_date,
            })
            
            approval_requests.append(FieldUpdateResult(
                field_name=field_name,
                status="pending_approval",
                old_value=old_value,
                new_value=new_value,
                message="Update request submitted for approval",
                request_id=request_id,
            ))
        else:
            # Apply update directly
            setattr(employee, field_name, new_value)
            
            direct_updates.append(FieldUpdateResult(
                field_name=field_name,
                status="applied",
                old_value=old_value,
                new_value=new_value,
                message="Update applied successfully",
            ))
    
    # Commit direct updates
    if direct_updates:
        session.commit()
    
    return ProfileUpdateResponse(
        employee_id=employee.employee_id,
        direct_updates=direct_updates,
        approval_requests=approval_requests,
        rejected_updates=rejected_updates,
        summary={
            "applied": len(direct_updates),
            "pending_approval": len(approval_requests),
            "rejected": len(rejected_updates),
        },
    )


@employee_profile_update_router.post(
    "/update-request",
    response_model=UpdateRequestDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Create Update Request",
    description="Create an update request for approval-required fields.",
)
async def create_update_request(
    field_name: str,
    new_value: Any,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    reason: Optional[str] = None,
    effective_date: Optional[datetime] = None,
) -> UpdateRequestDetail:
    """
    Create an update request for a field requiring approval.
    
    - Creates request record with pending status
    - Sends notification to approvers
    - Returns request details for tracking
    """
    if not current_user.employee_id:
        raise ForbiddenError(message="Employee ID not found")
    
    # Fetch employee
    stmt = select(Employee).where(Employee.id == current_user.employee_id)
    result = session.execute(stmt)
    employee = result.scalar_one_or_none()
    
    if not employee:
        raise NotFoundError(message="Employee not found")
    
    # Validate field
    if field_name not in FIELD_DEFINITIONS:
        raise ValidationError(message=f"Unknown field: {field_name}")
    
    old_value = getattr(employee, field_name, None)
    request_id = uuid.uuid4()
    
    data = {
        "request_id": str(request_id),
        "employee_id": current_user.employee_id,
        "field_name": field_name,
        "old_value": old_value,
        "new_value": new_value,
        "reason": reason,
        "status": UpdateRequestStatus.PENDING,
        "requested_by": str(current_user.id),
        "requested_at": datetime.utcnow(),
        "effective_date": effective_date,
    }
    
    update_store.create(request_id, data)
    
    return UpdateRequestDetail(
        request_id=request_id,
        employee_id=current_user.employee_id,
        field_name=field_name,
        old_value=old_value,
        new_value=new_value,
        reason=reason,
        status=UpdateRequestStatus.PENDING,
        requested_by=str(current_user.id),
        requested_at=datetime.utcnow(),
        effective_date=effective_date,
    )


@employee_profile_update_router.get(
    "/update-requests",
    response_model=UpdateRequestListResponse,
    summary="List Update Requests",
    description="List update requests for the current employee.",
)
async def list_update_requests(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    status_filter: Optional[UpdateRequestStatus] = None,
) -> UpdateRequestListResponse:
    """
    List update requests for the current employee.
    
    - Returns all update requests (pending, approved, rejected)
    - Optionally filter by status
    """
    if not current_user.employee_id:
        raise ForbiddenError(message="Employee ID not found")
    
    requests = update_store.list_by_employee(current_user.employee_id)
    
    if status_filter:
        requests = [r for r in requests if r.get("status") == status_filter]
    
    details = []
    for r in requests:
        details.append(UpdateRequestDetail(
            request_id=uuid.UUID(r["request_id"]),
            employee_id=r["employee_id"],
            field_name=r["field_name"],
            old_value=r.get("old_value"),
            new_value=r["new_value"],
            reason=r.get("reason"),
            status=r["status"],
            requested_by=r["requested_by"],
            requested_at=r["requested_at"],
            reviewed_by=r.get("reviewed_by"),
            reviewed_at=r.get("reviewed_at"),
            review_notes=r.get("review_notes"),
            effective_date=r.get("effective_date"),
        ))
    
    pending = len([r for r in requests if r.get("status") == UpdateRequestStatus.PENDING])
    
    return UpdateRequestListResponse(
        requests=details,
        total=len(details),
        pending_count=pending,
    )


@employee_profile_update_router.get(
    "/update-requests/{request_id}",
    response_model=UpdateRequestDetail,
    summary="Get Update Request",
    description="Get details of a specific update request.",
)
async def get_update_request(
    request_id: uuid.UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> UpdateRequestDetail:
    """Get details of a specific update request."""
    req = update_store.get(request_id)
    
    if not req:
        raise NotFoundError(message="Update request not found")
    
    # Check ownership or admin
    user_role = current_user.roles[0] if current_user.roles else UserRole.EMPLOYEE
    if req["employee_id"] != current_user.employee_id and user_role not in [UserRole.ADMIN, UserRole.HR_MANAGER]:
        raise ForbiddenError(message="Access denied")
    
    return UpdateRequestDetail(
        request_id=uuid.UUID(req["request_id"]),
        employee_id=req["employee_id"],
        field_name=req["field_name"],
        old_value=req.get("old_value"),
        new_value=req["new_value"],
        reason=req.get("reason"),
        status=req["status"],
        requested_by=req["requested_by"],
        requested_at=req["requested_at"],
        reviewed_by=req.get("reviewed_by"),
        reviewed_at=req.get("reviewed_at"),
        review_notes=req.get("review_notes"),
        effective_date=req.get("effective_date"),
    )


@employee_profile_update_router.post(
    "/update-requests/{request_id}/review",
    response_model=ApprovalResponse,
    summary="Review Update Request",
    description="Approve or reject an update request (requires HR/Admin role).",
)
async def review_update_request(
    request_id: uuid.UUID,
    decision: ApprovalDecision,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> ApprovalResponse:
    """
    Review and approve/reject an update request.
    
    - Requires HR_MANAGER or ADMIN role
    - If approved, applies the update to employee profile
    - Creates audit trail of the decision
    """
    user_role = current_user.roles[0] if current_user.roles else UserRole.EMPLOYEE
    
    if user_role not in [UserRole.ADMIN, UserRole.HR_MANAGER]:
        raise ForbiddenError(message="Only HR managers and admins can review requests")
    
    req = update_store.get(request_id)
    if not req:
        raise NotFoundError(message="Update request not found")
    
    if req["status"] != UpdateRequestStatus.PENDING:
        raise ValidationError(message=f"Request already {req['status'].value}")
    
    applied = False
    
    if decision.approved:
        # Fetch and update employee
        stmt = select(Employee).where(Employee.id == req["employee_id"])
        result = session.execute(stmt)
        employee = result.scalar_one_or_none()
        
        if employee:
            setattr(employee, req["field_name"], req["new_value"])
            session.commit()
            applied = True
        
        new_status = UpdateRequestStatus.APPROVED
        message = "Request approved and update applied"
    else:
        new_status = UpdateRequestStatus.REJECTED
        message = "Request rejected"
    
    update_store.update(request_id, {
        "status": new_status,
        "reviewed_by": str(current_user.id),
        "reviewed_at": datetime.utcnow(),
        "review_notes": decision.notes,
    })
    
    return ApprovalResponse(
        request_id=request_id,
        status=new_status,
        applied=applied,
        message=message,
    )


@employee_profile_update_router.post(
    "/update-requests/{request_id}/cancel",
    response_model=ApprovalResponse,
    summary="Cancel Update Request",
    description="Cancel a pending update request.",
)
async def cancel_update_request(
    request_id: uuid.UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> ApprovalResponse:
    """Cancel a pending update request (by the requester)."""
    req = update_store.get(request_id)
    
    if not req:
        raise NotFoundError(message="Update request not found")
    
    if req["employee_id"] != current_user.employee_id:
        raise ForbiddenError(message="Can only cancel your own requests")
    
    if req["status"] != UpdateRequestStatus.PENDING:
        raise ValidationError(message="Can only cancel pending requests")
    
    update_store.update(request_id, {
        "status": UpdateRequestStatus.CANCELLED,
    })
    
    return ApprovalResponse(
        request_id=request_id,
        status=UpdateRequestStatus.CANCELLED,
        applied=False,
        message="Request cancelled",
    )

