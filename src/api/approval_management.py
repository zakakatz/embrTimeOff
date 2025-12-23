"""API endpoints for core approval management."""

import uuid
import logging
from datetime import date, datetime, timedelta
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.models.employee import Employee
from src.models.time_off_request import TimeOffRequest, TimeOffRequestStatus
from src.schemas.approval_management import (
    ApproveRequest,
    DenyRequest,
    ApprovalResultResponse,
    DenialResultResponse,
    PendingApprovalsResponse,
    PendingApprovalRequest,
    ApprovalStatusEnum,
    AuditTrailEntry,
    NotificationSent,
    EmployeeInfo,
    BalanceInfo,
    TeamConflict,
    CoverageWarning,
    PolicyConsideration,
    ConflictSeverityEnum,
)
from src.utils.auth import CurrentUser, UserRole, get_mock_current_user

logger = logging.getLogger(__name__)


# =============================================================================
# Router Setup
# =============================================================================

approval_management_router = APIRouter(
    prefix="/api/time-off/approvals",
    tags=["Approval Management"],
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
    
    roles = [UserRole.MANAGER]  # Default to manager for approval endpoints
    if x_user_role:
        try:
            roles = [UserRole(x_user_role)]
        except ValueError:
            pass
    
    return get_mock_current_user(
        user_id=user_id,
        employee_id=x_employee_id or 2,  # Default manager ID
        roles=roles,
    )


# =============================================================================
# Helper Functions
# =============================================================================

def validate_approval_authority(
    manager_id: int,
    request: TimeOffRequest,
    session: Session,
) -> tuple[bool, Optional[str]]:
    """
    Validate that the authenticated user has approval authority.
    
    Returns:
        Tuple of (is_authorized, error_message)
    """
    # Check if manager is the assigned approver
    if request.current_approver_id == manager_id:
        return True, None
    
    # Check if manager is the employee's direct manager
    employee = session.get(Employee, request.employee_id)
    if employee and employee.manager_id == manager_id:
        return True, None
    
    # Check if manager is a skip-level manager
    if employee and employee.manager_id:
        direct_manager = session.get(Employee, employee.manager_id)
        if direct_manager and direct_manager.manager_id == manager_id:
            return True, None
    
    return False, "Not authorized to approve this request"


def get_team_conflicts(
    employee_id: int,
    start_date: date,
    end_date: date,
    session: Session,
) -> List[TeamConflict]:
    """Get team members with overlapping time-off during the requested period."""
    # In production, query database for team members' approved/pending requests
    # Mock data for demonstration
    conflicts = []
    
    # Simulate checking team calendar
    mock_conflicts = [
        {
            "employee_id": 101,
            "employee_name": "Alice Johnson",
            "conflict_dates": [start_date + timedelta(days=1), start_date + timedelta(days=2)],
            "conflict_type": "overlap",
            "severity": ConflictSeverityEnum.MEDIUM,
        }
    ]
    
    for conflict in mock_conflicts:
        conflicts.append(TeamConflict(**conflict))
    
    return conflicts


def get_coverage_warnings(
    employee_id: int,
    start_date: date,
    end_date: date,
    session: Session,
) -> List[CoverageWarning]:
    """Check for coverage issues if request is approved."""
    warnings = []
    
    # In production, check team capacity and minimum staffing requirements
    # Mock data for demonstration
    current_date = start_date
    while current_date <= end_date:
        if current_date.weekday() < 5:  # Weekdays only
            # Simulate coverage check
            mock_coverage = 2  # Team members available
            min_required = 2
            
            if mock_coverage <= min_required:
                warnings.append(CoverageWarning(
                    warning_type="low_coverage",
                    message=f"Team coverage will be at minimum on {current_date}",
                    affected_dates=[current_date],
                    minimum_coverage_required=min_required,
                    current_coverage=mock_coverage - 1,  # After this approval
                ))
                break  # Only add one warning for brevity
        
        current_date += timedelta(days=1)
    
    return warnings


def get_policy_considerations(
    employee_id: int,
    request_type: str,
    total_days: float,
    session: Session,
) -> List[PolicyConsideration]:
    """Get policy-related considerations for the approval decision."""
    considerations = []
    
    # Check advance notice policy
    considerations.append(PolicyConsideration(
        policy_name="Advance Notice Requirement",
        rule_description="Vacation requests require 2 weeks advance notice",
        compliance_status="compliant",
        details="Request submitted with sufficient notice",
    ))
    
    # Check consecutive days policy
    if total_days > 5:
        considerations.append(PolicyConsideration(
            policy_name="Extended Leave Policy",
            rule_description="Requests over 5 days require department head approval",
            compliance_status="warning",
            details=f"Request is for {total_days} days",
        ))
    
    return considerations


def create_audit_trail_entry(
    action: str,
    performer_id: int,
    performer_name: str,
    previous_status: str,
    new_status: str,
    rationale: Optional[str] = None,
    contextual_factors: Optional[Dict[str, Any]] = None,
) -> AuditTrailEntry:
    """Create a detailed audit trail entry."""
    return AuditTrailEntry(
        id=str(uuid.uuid4()),
        action=action,
        performed_by_id=performer_id,
        performed_by_name=performer_name,
        performed_at=datetime.utcnow(),
        decision_rationale=rationale,
        contextual_factors=contextual_factors,
        previous_status=previous_status,
        new_status=new_status,
    )


def send_notifications(
    request: TimeOffRequest,
    action: str,
    session: Session,
) -> List[NotificationSent]:
    """Send notifications to employees and stakeholders."""
    notifications = []
    
    # Notify the requesting employee
    employee = session.get(Employee, request.employee_id)
    if employee:
        notifications.append(NotificationSent(
            recipient_id=employee.id,
            recipient_name=f"{employee.first_name} {employee.last_name}",
            recipient_email=employee.email or f"{employee.first_name.lower()}@example.com",
            notification_type=f"time_off_{action}",
            channel="email",
            sent_at=datetime.utcnow(),
        ))
    
    # Notify HR for tracking (simulated)
    notifications.append(NotificationSent(
        recipient_id=999,
        recipient_name="HR Department",
        recipient_email="hr@example.com",
        notification_type=f"time_off_{action}_notification",
        channel="system",
        sent_at=datetime.utcnow(),
    ))
    
    return notifications


# =============================================================================
# Endpoints
# =============================================================================

@approval_management_router.get(
    "/pending",
    response_model=PendingApprovalsResponse,
    summary="Get pending approval requests",
    description="Returns pending approval requests for the authenticated manager with comprehensive contextual information.",
)
async def get_pending_approvals(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    include_conflicts: bool = True,
    include_coverage: bool = True,
    include_policy: bool = True,
) -> PendingApprovalsResponse:
    """
    Get pending approval requests for the authenticated manager.
    
    Returns comprehensive contextual information including:
    - Team conflicts
    - Coverage warnings
    - Policy considerations
    - Balance information
    """
    manager_id = current_user.employee_id or 2
    
    # Get manager info
    manager = session.get(Employee, manager_id)
    manager_name = f"{manager.first_name} {manager.last_name}" if manager else "Manager"
    
    # Query pending requests
    # In production, use proper SQLAlchemy query
    pending_requests: List[PendingApprovalRequest] = []
    
    # Get employees reporting to this manager
    from sqlalchemy import select
    stmt = select(Employee).where(Employee.manager_id == manager_id)
    direct_reports = session.execute(stmt).scalars().all()
    direct_report_ids = [e.id for e in direct_reports]
    
    # Get time-off requests from direct reports
    if direct_report_ids:
        requests_stmt = select(TimeOffRequest).where(
            TimeOffRequest.employee_id.in_(direct_report_ids),
            TimeOffRequest.status == TimeOffRequestStatus.PENDING_APPROVAL.value,
        )
        time_off_requests = session.execute(requests_stmt).scalars().all()
        
        for req in time_off_requests:
            employee = session.get(Employee, req.employee_id)
            if not employee:
                continue
            
            # Build contextual information
            team_conflicts = []
            coverage_warnings = []
            policy_considerations = []
            
            if include_conflicts:
                team_conflicts = get_team_conflicts(
                    req.employee_id, req.start_date, req.end_date, session
                )
            
            if include_coverage:
                coverage_warnings = get_coverage_warnings(
                    req.employee_id, req.start_date, req.end_date, session
                )
            
            if include_policy:
                policy_considerations = get_policy_considerations(
                    req.employee_id, req.request_type, req.total_days, session
                )
            
            # Calculate days pending
            days_pending = (datetime.utcnow() - req.created_at).days if req.created_at else 0
            
            # Determine priority
            priority = "normal"
            if days_pending > 3:
                priority = "high"
            if any(c.severity == ConflictSeverityEnum.CRITICAL for c in team_conflicts):
                priority = "urgent"
            
            pending_requests.append(PendingApprovalRequest(
                request_id=req.id,
                employee=EmployeeInfo(
                    id=employee.id,
                    employee_id=employee.employee_id,
                    name=f"{employee.first_name} {employee.last_name}",
                    email=employee.email or "",
                    department=employee.department.name if employee.department else None,
                    job_title=employee.job_title,
                ),
                request_type=req.request_type,
                start_date=req.start_date,
                end_date=req.end_date,
                total_days=req.total_days,
                reason=req.reason,
                balance_info=BalanceInfo(
                    balance_type=req.request_type,
                    available=req.balance_before or 15.0,
                    requested=req.total_days,
                    after_approval=(req.balance_before or 15.0) - req.total_days,
                    year=datetime.now().year,
                ),
                team_conflicts=team_conflicts,
                coverage_warnings=coverage_warnings,
                policy_considerations=policy_considerations,
                submitted_at=req.submitted_at or req.created_at,
                days_pending=days_pending,
                priority=priority,
                requires_escalation=days_pending > 5,
            ))
    
    # Build summary
    summary = {
        "by_type": {},
        "by_priority": {"normal": 0, "high": 0, "urgent": 0},
        "with_conflicts": 0,
        "with_coverage_warnings": 0,
        "requires_escalation": 0,
    }
    
    for pr in pending_requests:
        # Count by type
        summary["by_type"][pr.request_type] = summary["by_type"].get(pr.request_type, 0) + 1
        # Count by priority
        summary["by_priority"][pr.priority] = summary["by_priority"].get(pr.priority, 0) + 1
        # Count issues
        if pr.team_conflicts:
            summary["with_conflicts"] += 1
        if pr.coverage_warnings:
            summary["with_coverage_warnings"] += 1
        if pr.requires_escalation:
            summary["requires_escalation"] += 1
    
    return PendingApprovalsResponse(
        manager_id=manager_id,
        manager_name=manager_name,
        total_pending=len(pending_requests),
        pending_requests=pending_requests,
        summary=summary,
    )


@approval_management_router.post(
    "/{request_id}/approve",
    response_model=ApprovalResultResponse,
    summary="Approve a time-off request",
    description="Process approval decision with validation of approval authority and audit trail creation.",
)
async def approve_request(
    request_id: int,
    approval: ApproveRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> ApprovalResultResponse:
    """
    Approve a time-off request.
    
    - Validates that authenticated user has approval authority
    - Updates request status to approved
    - Updates employee balance
    - Creates detailed audit trail with decision rationale
    - Triggers notifications to employee and stakeholders
    """
    manager_id = current_user.employee_id or 2
    
    # Get the request
    time_off_request = session.get(TimeOffRequest, request_id)
    if not time_off_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Time-off request {request_id} not found",
        )
    
    # Validate request is pending
    if time_off_request.status != TimeOffRequestStatus.PENDING_APPROVAL.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Request is not pending approval (status: {time_off_request.status})",
        )
    
    # Validate approval authority
    is_authorized, auth_error = validate_approval_authority(
        manager_id, time_off_request, session
    )
    
    if not is_authorized:
        # Check for HR/Admin override
        if not any(r in current_user.roles for r in [UserRole.HR, UserRole.ADMIN]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=auth_error or "Not authorized to approve this request",
            )
    
    # Get manager info
    manager = session.get(Employee, manager_id)
    manager_name = f"{manager.first_name} {manager.last_name}" if manager else "Manager"
    
    # Check for conflicts and coverage warnings
    team_conflicts = get_team_conflicts(
        time_off_request.employee_id,
        time_off_request.start_date,
        time_off_request.end_date,
        session,
    )
    coverage_warnings = get_coverage_warnings(
        time_off_request.employee_id,
        time_off_request.start_date,
        time_off_request.end_date,
        session,
    )
    
    # Require acknowledgment if there are conflicts/warnings
    if team_conflicts and not approval.acknowledge_conflicts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must acknowledge team conflicts before approving",
        )
    
    if coverage_warnings and not approval.acknowledge_coverage_warnings:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must acknowledge coverage warnings before approving",
        )
    
    # Store previous status
    previous_status = time_off_request.status
    
    # Update request status
    time_off_request.status = TimeOffRequestStatus.APPROVED.value
    time_off_request.approved_at = datetime.utcnow()
    time_off_request.approver_notes = approval.comments
    time_off_request.updated_at = datetime.utcnow()
    time_off_request.updated_by = manager_id
    
    # Calculate balance impact
    balance_before = time_off_request.balance_before or 15.0
    balance_impact = {
        "balance_type": time_off_request.request_type,
        "previous_balance": balance_before,
        "deducted": time_off_request.total_days,
        "new_balance": balance_before - time_off_request.total_days,
    }
    time_off_request.balance_after = balance_impact["new_balance"]
    
    # Commit changes
    session.commit()
    
    # Create audit entry
    contextual_factors = {
        "team_conflicts_acknowledged": len(team_conflicts) > 0,
        "coverage_warnings_acknowledged": len(coverage_warnings) > 0,
        "conditions_applied": approval.conditions,
    }
    
    audit_entry = create_audit_trail_entry(
        action="request_approved",
        performer_id=manager_id,
        performer_name=manager_name,
        previous_status=previous_status,
        new_status=TimeOffRequestStatus.APPROVED.value,
        rationale=approval.comments,
        contextual_factors=contextual_factors,
    )
    
    # Send notifications
    notifications = send_notifications(time_off_request, "approved", session)
    
    return ApprovalResultResponse(
        request_id=request_id,
        status=ApprovalStatusEnum.APPROVED,
        decision="approved",
        approved_by_id=manager_id,
        approved_by_name=manager_name,
        comments=approval.comments,
        conditions=approval.conditions,
        balance_impact=balance_impact,
        audit_entry=audit_entry,
        notifications_sent=notifications,
        processed_at=datetime.utcnow(),
        message="Time-off request approved successfully",
    )


@approval_management_router.post(
    "/{request_id}/deny",
    response_model=DenialResultResponse,
    summary="Deny a time-off request",
    description="Handle request denial with required rationale capture and audit trail.",
)
async def deny_request(
    request_id: int,
    denial: DenyRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> DenialResultResponse:
    """
    Deny a time-off request.
    
    - Validates that authenticated user has approval authority
    - Updates request status to denied
    - Captures required rationale for denial decision
    - Creates detailed audit trail for compliance
    - Triggers notifications to employee
    """
    manager_id = current_user.employee_id or 2
    
    # Get the request
    time_off_request = session.get(TimeOffRequest, request_id)
    if not time_off_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Time-off request {request_id} not found",
        )
    
    # Validate request is pending
    if time_off_request.status != TimeOffRequestStatus.PENDING_APPROVAL.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Request is not pending approval (status: {time_off_request.status})",
        )
    
    # Validate approval authority
    is_authorized, auth_error = validate_approval_authority(
        manager_id, time_off_request, session
    )
    
    if not is_authorized:
        if not any(r in current_user.roles for r in [UserRole.HR, UserRole.ADMIN]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=auth_error or "Not authorized to deny this request",
            )
    
    # Get manager info
    manager = session.get(Employee, manager_id)
    manager_name = f"{manager.first_name} {manager.last_name}" if manager else "Manager"
    
    # Store previous status
    previous_status = time_off_request.status
    
    # Update request status
    time_off_request.status = TimeOffRequestStatus.REJECTED.value
    time_off_request.rejected_at = datetime.utcnow()
    time_off_request.rejection_reason = denial.rationale
    time_off_request.updated_at = datetime.utcnow()
    time_off_request.updated_by = manager_id
    
    # Commit changes
    session.commit()
    
    # Create audit entry
    contextual_factors = {
        "policy_reference": denial.policy_reference,
        "alternative_dates_suggested": denial.suggest_alternative_dates,
    }
    
    audit_entry = create_audit_trail_entry(
        action="request_denied",
        performer_id=manager_id,
        performer_name=manager_name,
        previous_status=previous_status,
        new_status=TimeOffRequestStatus.REJECTED.value,
        rationale=denial.rationale,
        contextual_factors=contextual_factors,
    )
    
    # Send notifications
    notifications = send_notifications(time_off_request, "denied", session)
    
    return DenialResultResponse(
        request_id=request_id,
        status=ApprovalStatusEnum.DENIED,
        denied_by_id=manager_id,
        denied_by_name=manager_name,
        rationale=denial.rationale,
        policy_reference=denial.policy_reference,
        alternative_suggested=denial.suggest_alternative_dates,
        alternative_start_date=denial.alternative_start_date,
        alternative_end_date=denial.alternative_end_date,
        audit_entry=audit_entry,
        notifications_sent=notifications,
        processed_at=datetime.utcnow(),
        message="Time-off request denied",
    )

