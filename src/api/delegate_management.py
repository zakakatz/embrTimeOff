"""API endpoints for delegate management."""

import uuid
import json
import logging
from datetime import date, datetime
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.models.employee import Employee
from src.models.approval_delegate import (
    ApprovalDelegate,
    DelegateAuditLog,
    DelegateStatus,
    DelegateScope,
)
from src.schemas.delegate_management import (
    CreateDelegateRequest,
    RemoveDelegateRequest,
    CreateDelegateResponse,
    ActiveDelegatesResponse,
    RemoveDelegateResponse,
    DelegateAssignment,
    DelegateStatusEnum,
    DelegateScopeEnum,
    EmployeeInfo,
    ScopeLimitation,
    AuditEntry,
    NotificationSent,
)
from src.utils.auth import CurrentUser, UserRole, get_mock_current_user

logger = logging.getLogger(__name__)


# =============================================================================
# Router Setup
# =============================================================================

delegate_management_router = APIRouter(
    prefix="/api/time-off/approvals/delegates",
    tags=["Delegate Management"],
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

def validate_delegate_permissions(
    delegate_id: int,
    session: Session,
) -> tuple[bool, Optional[str]]:
    """Validate that the delegate has appropriate permissions."""
    delegate = session.get(Employee, delegate_id)
    if not delegate:
        return False, "Delegate employee not found"
    
    if delegate.status != "active":
        return False, "Delegate employee is not active"
    
    # Check if delegate has management role or approval permissions
    # In production, this would check role assignments
    return True, None


def check_delegate_availability(
    delegate_id: int,
    start_date: date,
    end_date: date,
    session: Session,
) -> tuple[bool, Optional[str]]:
    """Check if delegate is available during the period."""
    # Check for conflicting delegations (delegate already has delegations)
    stmt = select(ApprovalDelegate).where(
        ApprovalDelegate.delegate_id == delegate_id,
        ApprovalDelegate.status == DelegateStatus.ACTIVE.value,
        ApprovalDelegate.start_date <= end_date,
        ApprovalDelegate.end_date >= start_date,
    )
    existing = session.execute(stmt).scalars().first()
    
    if existing:
        return False, f"Delegate already has active delegation from {existing.start_date} to {existing.end_date}"
    
    # Check if delegate has approved time-off during the period
    # This would check time-off requests in production
    
    return True, None


def get_employee_info(employee: Employee) -> EmployeeInfo:
    """Convert Employee model to EmployeeInfo."""
    return EmployeeInfo(
        id=employee.id,
        employee_id=employee.employee_id,
        name=f"{employee.first_name} {employee.last_name}",
        email=employee.email,
        job_title=employee.job_title,
        department=employee.department.name if employee.department else None,
    )


def assignment_to_response(
    assignment: ApprovalDelegate,
    session: Session,
) -> DelegateAssignment:
    """Convert ApprovalDelegate model to DelegateAssignment response."""
    delegator = session.get(Employee, assignment.delegator_id)
    delegate = session.get(Employee, assignment.delegate_id)
    
    # Build scope description
    scope_descriptions = {
        DelegateScope.ALL.value: "Full approval authority for all request types",
        DelegateScope.TIME_OFF.value: "Time-off request approvals only",
        DelegateScope.EXPENSE.value: "Expense approvals only",
        DelegateScope.PROFILE_CHANGES.value: "Profile change approvals only",
    }
    
    description = scope_descriptions.get(assignment.scope, "Limited scope")
    if assignment.max_approval_days:
        description += f" (max {assignment.max_approval_days} days)"
    if assignment.team_scope_only:
        description += " - direct team only"
    
    return DelegateAssignment(
        id=assignment.id,
        delegator=get_employee_info(delegator) if delegator else EmployeeInfo(
            id=assignment.delegator_id,
            employee_id="UNKNOWN",
            name="Unknown",
        ),
        delegate=get_employee_info(delegate) if delegate else EmployeeInfo(
            id=assignment.delegate_id,
            employee_id="UNKNOWN",
            name="Unknown",
        ),
        status=DelegateStatusEnum(assignment.status),
        is_currently_active=assignment.is_active,
        start_date=assignment.start_date,
        end_date=assignment.end_date,
        scope_limitations=ScopeLimitation(
            scope=DelegateScopeEnum(assignment.scope),
            max_approval_days=assignment.max_approval_days,
            team_scope_only=assignment.team_scope_only,
            description=description,
        ),
        reason=assignment.reason,
        delegator_contact=assignment.delegator_contact,
        created_at=assignment.created_at,
        created_by=assignment.created_by,
    )


def create_audit_entry(
    assignment_id: int,
    action: str,
    performer_id: int,
    performer_name: str,
    previous_status: Optional[str] = None,
    new_status: Optional[str] = None,
    details: Optional[dict] = None,
    session: Session = None,
) -> DelegateAuditLog:
    """Create audit log entry."""
    audit = DelegateAuditLog(
        delegate_assignment_id=assignment_id,
        action=action,
        performed_by=performer_id,
        performed_by_name=performer_name,
        previous_status=previous_status,
        new_status=new_status,
        details=json.dumps(details) if details else None,
    )
    if session:
        session.add(audit)
    return audit


def send_notifications(
    assignment: ApprovalDelegate,
    action: str,
    session: Session,
) -> List[NotificationSent]:
    """Send notifications for delegate actions."""
    notifications = []
    
    # Notify delegate
    delegate = session.get(Employee, assignment.delegate_id)
    if delegate:
        notifications.append(NotificationSent(
            recipient_id=delegate.id,
            recipient_name=f"{delegate.first_name} {delegate.last_name}",
            notification_type=f"delegate_{action}",
        ))
    
    # Notify delegator
    delegator = session.get(Employee, assignment.delegator_id)
    if delegator and action != "created":
        notifications.append(NotificationSent(
            recipient_id=delegator.id,
            recipient_name=f"{delegator.first_name} {delegator.last_name}",
            notification_type=f"delegation_{action}",
        ))
    
    # Notify HR for tracking
    notifications.append(NotificationSent(
        recipient_id=999,
        recipient_name="HR Department",
        notification_type=f"delegation_{action}_notification",
    ))
    
    return notifications


# =============================================================================
# Endpoints
# =============================================================================

@delegate_management_router.post(
    "",
    response_model=CreateDelegateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create delegate assignment",
    description="Create a delegate approver assignment with validation.",
)
async def create_delegate(
    request: CreateDelegateRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> CreateDelegateResponse:
    """
    Create a delegate approver assignment.
    
    - Validates delegate permissions and availability
    - Establishes delegate relationship with date range and scope
    - Creates audit trail for accountability
    - Sends notifications to affected parties
    """
    delegator_id = current_user.employee_id or 2
    
    # Validate delegator is a manager
    if UserRole.MANAGER not in current_user.roles and UserRole.ADMIN not in current_user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only managers can create delegate assignments",
        )
    
    # Cannot delegate to self
    if request.delegate_id == delegator_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delegate to yourself",
        )
    
    # Validate delegate permissions
    is_valid, error = validate_delegate_permissions(request.delegate_id, session)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error,
        )
    
    # Check delegate availability
    is_available, avail_error = check_delegate_availability(
        request.delegate_id,
        request.start_date,
        request.end_date,
        session,
    )
    if not is_available:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=avail_error,
        )
    
    # Check for existing active delegation from this delegator
    stmt = select(ApprovalDelegate).where(
        ApprovalDelegate.delegator_id == delegator_id,
        ApprovalDelegate.status == DelegateStatus.ACTIVE.value,
        ApprovalDelegate.start_date <= request.end_date,
        ApprovalDelegate.end_date >= request.start_date,
    )
    existing = session.execute(stmt).scalars().first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"You already have an active delegation for this period (ID: {existing.id})",
        )
    
    # Get delegator info
    delegator = session.get(Employee, delegator_id)
    delegator_name = f"{delegator.first_name} {delegator.last_name}" if delegator else "Manager"
    
    # Create assignment
    assignment = ApprovalDelegate(
        delegator_id=delegator_id,
        delegate_id=request.delegate_id,
        scope=request.scope.value,
        status=DelegateStatus.ACTIVE.value,
        start_date=request.start_date,
        end_date=request.end_date,
        max_approval_days=request.max_approval_days,
        team_scope_only=request.team_scope_only,
        reason=request.reason,
        delegator_contact=request.contact_info,
        created_by=delegator_id,
    )
    
    session.add(assignment)
    session.flush()
    
    # Create audit entry
    audit = create_audit_entry(
        assignment_id=assignment.id,
        action="delegate_created",
        performer_id=delegator_id,
        performer_name=delegator_name,
        new_status=DelegateStatus.ACTIVE.value,
        details={
            "delegate_id": request.delegate_id,
            "start_date": request.start_date.isoformat(),
            "end_date": request.end_date.isoformat(),
            "scope": request.scope.value,
        },
        session=session,
    )
    
    session.commit()
    
    # Send notifications
    notifications = send_notifications(assignment, "created", session)
    
    return CreateDelegateResponse(
        assignment=assignment_to_response(assignment, session),
        audit_entry=AuditEntry(
            id=audit.id if hasattr(audit, 'id') else 0,
            action="delegate_created",
            performed_by_name=delegator_name,
            performed_at=datetime.utcnow(),
            details=f"Delegated to employee ID {request.delegate_id}",
        ),
        notifications_sent=notifications,
        message=f"Delegate assignment created successfully for {request.start_date} to {request.end_date}",
    )


@delegate_management_router.get(
    "/active",
    response_model=ActiveDelegatesResponse,
    summary="Get active delegates",
    description="Get active delegate assignments for the authenticated user.",
)
async def get_active_delegates(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    include_expired: bool = Query(default=False, description="Include recently expired"),
) -> ActiveDelegatesResponse:
    """
    Get active delegate assignments for the authenticated user.
    
    Returns:
    - Delegations given to others
    - Delegations received from others
    - Scope limitations and effective dates
    - Escalation contacts for complex scenarios
    """
    employee_id = current_user.employee_id or 2
    
    # Get employee info
    employee = session.get(Employee, employee_id)
    employee_name = f"{employee.first_name} {employee.last_name}" if employee else "Employee"
    
    today = date.today()
    
    # Build status filter
    status_filter = [DelegateStatus.ACTIVE.value]
    if include_expired:
        status_filter.append(DelegateStatus.EXPIRED.value)
    
    # Get delegations given (I delegated to others)
    given_stmt = select(ApprovalDelegate).where(
        ApprovalDelegate.delegator_id == employee_id,
        ApprovalDelegate.status.in_(status_filter),
    ).order_by(ApprovalDelegate.start_date.desc())
    
    delegations_given = session.execute(given_stmt).scalars().all()
    
    # Get delegations received (Others delegated to me)
    received_stmt = select(ApprovalDelegate).where(
        ApprovalDelegate.delegate_id == employee_id,
        ApprovalDelegate.status.in_(status_filter),
    ).order_by(ApprovalDelegate.start_date.desc())
    
    delegations_received = session.execute(received_stmt).scalars().all()
    
    # Count active
    active_given = sum(1 for d in delegations_given if d.is_active)
    active_received = sum(1 for d in delegations_received if d.is_active)
    
    # Build escalation contacts
    escalation_contacts = [
        {
            "role": "HR Department",
            "name": "HR Support",
            "email": "hr@example.com",
            "phone": "555-0100",
            "description": "For policy questions and complex approval scenarios",
        },
        {
            "role": "System Administrator",
            "name": "IT Support",
            "email": "it@example.com",
            "description": "For technical issues with delegation system",
        },
    ]
    
    return ActiveDelegatesResponse(
        employee_id=employee_id,
        employee_name=employee_name,
        delegations_given=[assignment_to_response(d, session) for d in delegations_given],
        delegations_received=[assignment_to_response(d, session) for d in delegations_received],
        total_active_given=active_given,
        total_active_received=active_received,
        escalation_contacts=escalation_contacts,
    )


@delegate_management_router.delete(
    "/{delegate_id}",
    response_model=RemoveDelegateResponse,
    summary="Remove delegate assignment",
    description="Remove a delegate assignment with appropriate transition handling.",
)
async def remove_delegate(
    delegate_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    reason: Optional[str] = Query(default=None, description="Reason for removal"),
    notify_affected: bool = Query(default=True, description="Notify affected employees"),
) -> RemoveDelegateResponse:
    """
    Remove a delegate assignment.
    
    - Validates removal authority
    - Handles pending requests transition
    - Maintains audit trail
    - Sends notifications
    """
    employee_id = current_user.employee_id or 2
    
    # Get assignment
    assignment = session.get(ApprovalDelegate, delegate_id)
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Delegate assignment {delegate_id} not found",
        )
    
    # Validate removal authority (must be delegator or admin)
    if assignment.delegator_id != employee_id:
        if UserRole.ADMIN not in current_user.roles and UserRole.HR not in current_user.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to remove this delegation",
            )
    
    # Check if already revoked
    if assignment.status == DelegateStatus.REVOKED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Delegation has already been revoked",
        )
    
    # Get performer info
    performer = session.get(Employee, employee_id)
    performer_name = f"{performer.first_name} {performer.last_name}" if performer else "User"
    
    # Store previous status
    previous_status = assignment.status
    
    # Update assignment
    assignment.status = DelegateStatus.REVOKED.value
    assignment.revoked_at = datetime.utcnow()
    assignment.revoked_by = employee_id
    assignment.revoke_reason = reason
    
    # Create audit entry
    audit = create_audit_entry(
        assignment_id=assignment.id,
        action="delegate_revoked",
        performer_id=employee_id,
        performer_name=performer_name,
        previous_status=previous_status,
        new_status=DelegateStatus.REVOKED.value,
        details={"reason": reason},
        session=session,
    )
    
    session.commit()
    
    # Send notifications
    notifications = []
    if notify_affected:
        notifications = send_notifications(assignment, "revoked", session)
    
    # Count pending requests (mock - would query actual pending requests)
    pending_affected = 0
    
    return RemoveDelegateResponse(
        assignment_id=delegate_id,
        new_status=DelegateStatusEnum.REVOKED,
        pending_requests_affected=pending_affected,
        requests_transferred_to=None,
        audit_entry=AuditEntry(
            id=audit.id if hasattr(audit, 'id') else 0,
            action="delegate_revoked",
            performed_by_name=performer_name,
            performed_at=datetime.utcnow(),
            details=reason,
        ),
        notifications_sent=notifications,
        message="Delegate assignment removed successfully",
    )


@delegate_management_router.get(
    "/{delegate_id}",
    response_model=DelegateAssignment,
    summary="Get delegate assignment",
    description="Get details of a specific delegate assignment.",
)
async def get_delegate_assignment(
    delegate_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> DelegateAssignment:
    """Get details of a specific delegate assignment."""
    assignment = session.get(ApprovalDelegate, delegate_id)
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Delegate assignment {delegate_id} not found",
        )
    
    employee_id = current_user.employee_id or 2
    
    # Validate access (delegator, delegate, or admin)
    if (assignment.delegator_id != employee_id and 
        assignment.delegate_id != employee_id and
        UserRole.ADMIN not in current_user.roles and
        UserRole.HR not in current_user.roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this delegation",
        )
    
    return assignment_to_response(assignment, session)


