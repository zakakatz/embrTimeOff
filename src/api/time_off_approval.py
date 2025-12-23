"""API endpoints for time-off request approval and escalation."""

import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.models.employee import Employee
from src.utils.auth import CurrentUser, UserRole, get_mock_current_user
from src.utils.errors import ForbiddenError, NotFoundError, ValidationError


# =============================================================================
# Enums
# =============================================================================

class ApprovalDecision(str, Enum):
    """Approval decision options."""
    
    APPROVE = "approve"
    DENY = "deny"
    REQUEST_INFO = "request_info"


class EscalationLevel(str, Enum):
    """Escalation levels."""
    
    FIRST = "first"           # Skip-level manager
    SECOND = "second"         # Department head
    HR = "hr"                 # HR escalation
    EXECUTIVE = "executive"   # Executive escalation


class EscalationTrigger(str, Enum):
    """Triggers for escalation."""
    
    APPROVAL_DELAY = "approval_delay"
    POLICY_DEADLINE = "policy_deadline"
    BALANCE_ISSUE = "balance_issue"
    CONFLICT_RESOLUTION = "conflict_resolution"
    MANUAL = "manual"


class RequestStatus(str, Enum):
    """Status of time-off request."""
    
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    PENDING_INFO = "pending_info"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    ESCALATED = "escalated"


# =============================================================================
# Request Models
# =============================================================================

class ApprovalRequest(BaseModel):
    """Request to approve or deny a time-off request."""
    
    decision: ApprovalDecision = Field(..., description="Approval decision")
    comments: Optional[str] = Field(
        None,
        max_length=1000,
        description="Approver comments",
    )
    denial_reason: Optional[str] = Field(
        None,
        max_length=500,
        description="Reason for denial (required if denying)",
    )


class EscalationRequest(BaseModel):
    """Request to escalate a time-off request."""
    
    escalation_trigger: EscalationTrigger = Field(
        ...,
        description="Trigger for escalation",
    )
    escalation_level: Optional[EscalationLevel] = Field(
        None,
        description="Target escalation level (auto-determined if not specified)",
    )
    reason: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Reason for escalation",
    )
    notify_stakeholders: bool = Field(
        default=True,
        description="Whether to notify relevant stakeholders",
    )


# =============================================================================
# Response Models
# =============================================================================

class ApproverInfo(BaseModel):
    """Information about an approver."""
    
    id: int
    employee_id: str
    name: str
    title: Optional[str] = None
    approval_level: int = Field(default=1)


class AuditEntry(BaseModel):
    """Audit trail entry."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    action: str
    performed_by_id: int
    performed_by_name: str
    performed_at: datetime = Field(default_factory=datetime.utcnow)
    previous_status: Optional[str] = None
    new_status: Optional[str] = None
    comments: Optional[str] = None
    decision_rationale: Optional[str] = None


class BalanceUpdate(BaseModel):
    """Balance update after approval."""
    
    balance_type: str
    previous_balance: float
    deducted_amount: float
    new_balance: float
    effective_date: datetime


class NotificationInfo(BaseModel):
    """Information about notifications sent."""
    
    recipient_id: int
    recipient_name: str
    notification_type: str
    sent_at: datetime = Field(default_factory=datetime.utcnow)
    channel: str = Field(default="email")


class ApprovalResponse(BaseModel):
    """Response for approval action."""
    
    request_id: int
    decision: str
    new_status: str
    
    # Approver info
    approved_by: ApproverInfo
    
    # Comments
    comments: Optional[str] = None
    denial_reason: Optional[str] = None
    
    # Balance update (if approved)
    balance_update: Optional[BalanceUpdate] = None
    
    # Next approver (if multi-level)
    next_approver: Optional[ApproverInfo] = None
    requires_additional_approval: bool = Field(default=False)
    
    # Audit
    audit_entry: AuditEntry
    
    # Notifications
    notifications_sent: List[NotificationInfo] = Field(default_factory=list)
    
    # Timestamps
    processed_at: datetime = Field(default_factory=datetime.utcnow)
    
    message: str


class EscalationResponse(BaseModel):
    """Response for escalation action."""
    
    request_id: int
    escalation_level: str
    escalation_trigger: str
    
    # Current assignee
    escalated_to: ApproverInfo
    
    # Previous approver
    escalated_from: Optional[ApproverInfo] = None
    
    # Reason
    reason: str
    
    # Stakeholders notified
    stakeholders_notified: List[NotificationInfo] = Field(default_factory=list)
    
    # Audit
    audit_entry: AuditEntry
    
    # New status
    new_status: str
    
    # Timestamps
    escalated_at: datetime = Field(default_factory=datetime.utcnow)
    escalation_deadline: Optional[datetime] = Field(None, description="When this level must respond by")
    
    message: str


# =============================================================================
# Mock Data Store
# =============================================================================

# Mock request storage (simulating database)
_mock_requests: Dict[int, Dict[str, Any]] = {
    1001: {
        "id": 1001,
        "employee_id": 1,
        "employee_name": "John Smith",
        "request_type": "vacation",
        "start_date": datetime.now().date() + timedelta(days=7),
        "end_date": datetime.now().date() + timedelta(days=14),
        "total_days": 5.0,
        "status": "pending_approval",
        "current_approver_id": 2,
        "approval_level": 1,
        "balance_before": 15.0,
        "created_at": datetime.utcnow() - timedelta(days=2),
    }
}

_audit_log: List[AuditEntry] = []


def get_mock_request(request_id: int) -> Optional[Dict[str, Any]]:
    """Get a mock request."""
    return _mock_requests.get(request_id)


def update_mock_request(request_id: int, updates: Dict[str, Any]) -> None:
    """Update a mock request."""
    if request_id in _mock_requests:
        _mock_requests[request_id].update(updates)


# =============================================================================
# Helper Functions
# =============================================================================

def validate_approver_authorization(
    approver_id: int,
    request_data: Dict[str, Any],
    session: Session,
) -> tuple[bool, Optional[str]]:
    """Validate that the approver is authorized to approve this request."""
    # Check if approver is the assigned approver
    if request_data.get("current_approver_id") == approver_id:
        return True, None
    
    # Check if approver is in the approval chain
    approver = session.get(Employee, approver_id)
    if not approver:
        return False, "Approver not found"
    
    # Check if approver is employee's manager
    employee_id = request_data.get("employee_id")
    employee = session.get(Employee, employee_id)
    if employee and employee.manager_id == approver_id:
        return True, None
    
    # Check if approver has HR/Admin role (would be done via role check in real impl)
    return False, "Not authorized to approve this request"


def get_next_approver(
    request_data: Dict[str, Any],
    current_level: int,
    session: Session,
) -> Optional[ApproverInfo]:
    """Get the next approver in the chain."""
    # Multi-level approval logic
    # For simplicity, assume single-level approval
    return None


def update_employee_balance(
    employee_id: int,
    request_type: str,
    days_used: float,
    session: Session,
) -> BalanceUpdate:
    """Update employee's time-off balance."""
    # In real implementation, would update TimeOffBalance table
    previous = 15.0  # Mock previous balance
    
    return BalanceUpdate(
        balance_type=request_type,
        previous_balance=previous,
        deducted_amount=days_used,
        new_balance=previous - days_used,
        effective_date=datetime.utcnow(),
    )


def create_audit_entry(
    action: str,
    performer_id: int,
    performer_name: str,
    previous_status: Optional[str],
    new_status: Optional[str],
    comments: Optional[str] = None,
    rationale: Optional[str] = None,
) -> AuditEntry:
    """Create an audit trail entry."""
    entry = AuditEntry(
        action=action,
        performed_by_id=performer_id,
        performed_by_name=performer_name,
        previous_status=previous_status,
        new_status=new_status,
        comments=comments,
        decision_rationale=rationale,
    )
    _audit_log.append(entry)
    return entry


def determine_escalation_level(
    current_level: int,
    trigger: EscalationTrigger,
) -> EscalationLevel:
    """Determine the appropriate escalation level."""
    if current_level == 1:
        if trigger == EscalationTrigger.BALANCE_ISSUE:
            return EscalationLevel.HR
        return EscalationLevel.FIRST
    elif current_level == 2:
        return EscalationLevel.SECOND
    else:
        return EscalationLevel.EXECUTIVE


def get_escalation_target(
    request_data: Dict[str, Any],
    level: EscalationLevel,
    session: Session,
) -> Optional[ApproverInfo]:
    """Get the target for escalation."""
    employee_id = request_data.get("employee_id")
    employee = session.get(Employee, employee_id)
    
    if not employee:
        return None
    
    if level == EscalationLevel.FIRST:
        # Skip-level manager
        if employee.manager_id:
            manager = session.get(Employee, employee.manager_id)
            if manager and manager.manager_id:
                skip_manager = session.get(Employee, manager.manager_id)
                if skip_manager:
                    return ApproverInfo(
                        id=skip_manager.id,
                        employee_id=skip_manager.employee_id,
                        name=f"{skip_manager.first_name} {skip_manager.last_name}",
                        title=skip_manager.job_title,
                        approval_level=2,
                    )
    
    elif level == EscalationLevel.HR:
        # Would find HR representative
        return ApproverInfo(
            id=999,
            employee_id="HR001",
            name="HR Representative",
            title="HR Manager",
            approval_level=3,
        )
    
    return None


def notify_stakeholders(
    request_id: int,
    action: str,
    stakeholder_ids: List[int],
    session: Session,
) -> List[NotificationInfo]:
    """Notify stakeholders about the action."""
    notifications = []
    
    for sid in stakeholder_ids:
        stakeholder = session.get(Employee, sid)
        if stakeholder:
            notifications.append(NotificationInfo(
                recipient_id=stakeholder.id,
                recipient_name=f"{stakeholder.first_name} {stakeholder.last_name}",
                notification_type=action,
                channel="email",
            ))
    
    return notifications


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

time_off_approval_router = APIRouter(
    prefix="/api/time-off-requests",
    tags=["Time Off Approval"],
)


# =============================================================================
# Endpoints
# =============================================================================

@time_off_approval_router.put(
    "/{request_id}/approve",
    response_model=ApprovalResponse,
    summary="Approve or Deny Time-Off Request",
    description="Process approval decision for a time-off request.",
)
async def process_approval(
    request_id: int,
    approval: ApprovalRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> ApprovalResponse:
    """
    Process approval decision for a time-off request.
    
    - Validates approver authorization
    - Updates request status
    - Updates employee balances (if approved)
    - Progresses workflow to next approver or completion
    - Creates audit trail
    """
    # Get the request
    request_data = get_mock_request(request_id)
    if not request_data:
        raise NotFoundError(message=f"Time-off request {request_id} not found")
    
    # Check request is pending approval
    if request_data["status"] not in ["pending_approval", "escalated"]:
        raise ValidationError(
            message=f"Request is not pending approval (status: {request_data['status']})",
            field_errors=[{"field": "status", "message": "Request not in approvable state"}],
        )
    
    # Validate approver authorization
    approver_id = current_user.employee_id or 0
    is_authorized, auth_error = validate_approver_authorization(
        approver_id,
        request_data,
        session,
    )
    
    if not is_authorized:
        # Check if user has admin/HR role as override
        if not any(r in current_user.roles for r in [UserRole.HR, UserRole.ADMIN]):
            raise ForbiddenError(message=auth_error or "Not authorized to approve")
    
    # Get approver info
    approver = session.get(Employee, approver_id)
    approver_name = f"{approver.first_name} {approver.last_name}" if approver else "Unknown"
    
    approver_info = ApproverInfo(
        id=approver_id,
        employee_id=approver.employee_id if approver else "UNKNOWN",
        name=approver_name,
        title=approver.job_title if approver else None,
        approval_level=request_data.get("approval_level", 1),
    )
    
    # Validate denial has reason
    if approval.decision == ApprovalDecision.DENY and not approval.denial_reason:
        raise ValidationError(
            message="Denial reason is required when denying a request",
            field_errors=[{"field": "denial_reason", "message": "Required for denial"}],
        )
    
    # Process decision
    previous_status = request_data["status"]
    balance_update = None
    next_approver = None
    requires_additional = False
    notifications = []
    
    if approval.decision == ApprovalDecision.APPROVE:
        # Check if multi-level approval needed
        next_approver = get_next_approver(
            request_data,
            request_data.get("approval_level", 1),
            session,
        )
        
        if next_approver:
            new_status = RequestStatus.PENDING_APPROVAL.value
            requires_additional = True
            update_mock_request(request_id, {
                "current_approver_id": next_approver.id,
                "approval_level": next_approver.approval_level,
            })
        else:
            new_status = RequestStatus.APPROVED.value
            
            # Update balance
            balance_update = update_employee_balance(
                request_data["employee_id"],
                request_data["request_type"],
                request_data["total_days"],
                session,
            )
            
            # Notify employee
            notifications = notify_stakeholders(
                request_id,
                "request_approved",
                [request_data["employee_id"]],
                session,
            )
    
    elif approval.decision == ApprovalDecision.DENY:
        new_status = RequestStatus.REJECTED.value
        
        # Notify employee
        notifications = notify_stakeholders(
            request_id,
            "request_denied",
            [request_data["employee_id"]],
            session,
        )
    
    else:  # REQUEST_INFO
        new_status = RequestStatus.PENDING_INFO.value
        
        # Notify employee
        notifications = notify_stakeholders(
            request_id,
            "info_requested",
            [request_data["employee_id"]],
            session,
        )
    
    # Update request status
    update_mock_request(request_id, {
        "status": new_status,
        "approver_notes": approval.comments,
        "rejection_reason": approval.denial_reason,
        f"{approval.decision.value}d_at": datetime.utcnow(),
    })
    
    # Create audit entry
    audit_entry = create_audit_entry(
        action=f"request_{approval.decision.value}d",
        performer_id=approver_id,
        performer_name=approver_name,
        previous_status=previous_status,
        new_status=new_status,
        comments=approval.comments,
        rationale=approval.denial_reason,
    )
    
    return ApprovalResponse(
        request_id=request_id,
        decision=approval.decision.value,
        new_status=new_status,
        approved_by=approver_info,
        comments=approval.comments,
        denial_reason=approval.denial_reason,
        balance_update=balance_update,
        next_approver=next_approver,
        requires_additional_approval=requires_additional,
        audit_entry=audit_entry,
        notifications_sent=notifications,
        message=f"Request {approval.decision.value}d successfully",
    )


@time_off_approval_router.post(
    "/{request_id}/escalate",
    response_model=EscalationResponse,
    summary="Escalate Time-Off Request",
    description="Escalate a time-off request to a higher level.",
)
async def escalate_request(
    request_id: int,
    escalation: EscalationRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> EscalationResponse:
    """
    Escalate a time-off request.
    
    - Evaluates escalation triggers
    - Routes to appropriate escalation level
    - Notifies relevant stakeholders
    - Creates audit trail
    """
    # Get the request
    request_data = get_mock_request(request_id)
    if not request_data:
        raise NotFoundError(message=f"Time-off request {request_id} not found")
    
    # Check request can be escalated
    if request_data["status"] not in ["pending_approval", "pending_info", "escalated"]:
        raise ValidationError(
            message=f"Request cannot be escalated (status: {request_data['status']})",
            field_errors=[{"field": "status", "message": "Request not in escalatable state"}],
        )
    
    # Get current approver info
    current_approver_id = request_data.get("current_approver_id")
    escalated_from = None
    if current_approver_id:
        current_approver = session.get(Employee, current_approver_id)
        if current_approver:
            escalated_from = ApproverInfo(
                id=current_approver.id,
                employee_id=current_approver.employee_id,
                name=f"{current_approver.first_name} {current_approver.last_name}",
                title=current_approver.job_title,
                approval_level=request_data.get("approval_level", 1),
            )
    
    # Determine escalation level
    current_level = request_data.get("approval_level", 1)
    escalation_level = escalation.escalation_level or determine_escalation_level(
        current_level,
        escalation.escalation_trigger,
    )
    
    # Get escalation target
    escalated_to = get_escalation_target(request_data, escalation_level, session)
    
    if not escalated_to:
        raise ValidationError(
            message="Could not determine escalation target",
            field_errors=[{"field": "escalation_level", "message": "No escalation target found"}],
        )
    
    # Get requestor info
    requestor_id = current_user.employee_id or 0
    requestor = session.get(Employee, requestor_id)
    requestor_name = f"{requestor.first_name} {requestor.last_name}" if requestor else "System"
    
    # Update request
    previous_status = request_data["status"]
    new_status = RequestStatus.ESCALATED.value
    
    update_mock_request(request_id, {
        "status": new_status,
        "current_approver_id": escalated_to.id,
        "approval_level": escalated_to.approval_level,
        "escalated_at": datetime.utcnow(),
        "escalation_reason": escalation.reason,
    })
    
    # Notify stakeholders
    stakeholders_notified = []
    if escalation.notify_stakeholders:
        # Notify new approver
        stakeholders_notified.append(NotificationInfo(
            recipient_id=escalated_to.id,
            recipient_name=escalated_to.name,
            notification_type="escalation_assigned",
        ))
        
        # Notify employee
        stakeholders_notified.extend(notify_stakeholders(
            request_id,
            "request_escalated",
            [request_data["employee_id"]],
            session,
        ))
        
        # Notify previous approver
        if escalated_from:
            stakeholders_notified.append(NotificationInfo(
                recipient_id=escalated_from.id,
                recipient_name=escalated_from.name,
                notification_type="escalation_notification",
            ))
    
    # Create audit entry
    audit_entry = create_audit_entry(
        action="request_escalated",
        performer_id=requestor_id,
        performer_name=requestor_name,
        previous_status=previous_status,
        new_status=new_status,
        comments=escalation.reason,
        rationale=f"Escalation trigger: {escalation.escalation_trigger.value}",
    )
    
    # Calculate escalation deadline
    escalation_deadline = datetime.utcnow() + timedelta(days=2)
    if escalation_level == EscalationLevel.EXECUTIVE:
        escalation_deadline = datetime.utcnow() + timedelta(days=1)
    
    return EscalationResponse(
        request_id=request_id,
        escalation_level=escalation_level.value,
        escalation_trigger=escalation.escalation_trigger.value,
        escalated_to=escalated_to,
        escalated_from=escalated_from,
        reason=escalation.reason,
        stakeholders_notified=stakeholders_notified,
        audit_entry=audit_entry,
        new_status=new_status,
        escalation_deadline=escalation_deadline,
        message=f"Request escalated to {escalation_level.value} level",
    )


@time_off_approval_router.get(
    "/{request_id}/audit-trail",
    response_model=List[AuditEntry],
    summary="Get Request Audit Trail",
    description="Get the complete audit trail for a request.",
)
async def get_request_audit_trail(
    request_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> List[AuditEntry]:
    """Get audit trail for a specific request."""
    # In real implementation, filter by request_id from database
    return _audit_log


@time_off_approval_router.get(
    "/pending-approvals",
    summary="Get Pending Approvals",
    description="Get time-off requests pending approval for the current user.",
)
async def get_pending_approvals(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> Dict[str, Any]:
    """Get pending approvals for the current user."""
    approver_id = current_user.employee_id or 0
    
    pending = []
    for req_id, req in _mock_requests.items():
        if req.get("current_approver_id") == approver_id:
            if req["status"] in ["pending_approval", "escalated"]:
                pending.append({
                    "request_id": req["id"],
                    "employee_name": req.get("employee_name", "Unknown"),
                    "request_type": req["request_type"],
                    "start_date": str(req["start_date"]),
                    "end_date": str(req["end_date"]),
                    "total_days": req["total_days"],
                    "status": req["status"],
                    "submitted_at": req.get("created_at", datetime.utcnow()).isoformat(),
                })
    
    return {
        "approver_id": approver_id,
        "pending_count": len(pending),
        "pending_requests": pending,
    }

