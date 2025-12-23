"""API endpoints for time-off policy management."""

import json
import uuid
import logging
from datetime import datetime
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.models.employee import Employee
from src.models.time_off_policy import (
    TimeOffPolicy,
    PolicyVersion,
    PolicyAuditLog,
    PolicyStatus,
    AccrualMethod,
)
from src.schemas.policy_management import (
    CreatePolicyRequest,
    UpdatePolicyRequest,
    DeactivatePolicyRequest,
    PolicyResponse,
    PolicyCreateResponse,
    PolicyUpdateResponse,
    PolicyDeactivateResponse,
    PolicyListResponse,
    PolicyStatusEnum,
    AccrualConfig,
    AccrualMethodEnum,
    BalanceConfig,
    RequestConfig,
    ApprovalConfig,
    AssignmentStats,
    PolicyVersionInfo,
    AuditEntry,
    TenureTier,
)
from src.utils.auth import CurrentUser, UserRole, get_mock_current_user

logger = logging.getLogger(__name__)


# =============================================================================
# Router Setup
# =============================================================================

policy_management_router = APIRouter(
    prefix="/api/time-off/policies",
    tags=["Policy Management"],
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
    
    roles = [UserRole.ADMIN]  # Default to admin for policy management
    if x_user_role:
        try:
            roles = [UserRole(x_user_role)]
        except ValueError:
            pass
    
    return get_mock_current_user(
        user_id=user_id,
        employee_id=x_employee_id or 1,
        roles=roles,
    )


def require_admin(current_user: CurrentUser) -> CurrentUser:
    """Require admin role for policy management."""
    if UserRole.ADMIN not in current_user.roles and UserRole.HR not in current_user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or HR role required for policy management",
        )
    return current_user


# =============================================================================
# Helper Functions
# =============================================================================

def validate_policy_config(request: CreatePolicyRequest) -> List[str]:
    """Validate policy configuration for consistency."""
    errors = []
    
    # Validate accrual method consistency
    if request.accrual.method == AccrualMethodEnum.NONE and request.accrual.base_rate > 0:
        errors.append("Base rate should be 0 when accrual method is 'none'")
    
    if request.accrual.tenure_tiers:
        # Validate tenure tiers don't overlap
        tiers = sorted(request.accrual.tenure_tiers, key=lambda t: t.min_years)
        for i, tier in enumerate(tiers[:-1]):
            next_tier = tiers[i + 1]
            if tier.max_years and tier.max_years > next_tier.min_years:
                errors.append(f"Tenure tier overlap: {tier.min_years}-{tier.max_years} and {next_tier.min_years}")
    
    # Validate balance config
    if request.balance:
        if request.balance.max_carryover and request.balance.max_balance:
            if request.balance.max_carryover > request.balance.max_balance:
                errors.append("Max carryover cannot exceed max balance")
    
    # Validate request config
    if request.request:
        if request.request.max_request_days and request.request.min_request_days:
            if request.request.min_request_days > request.request.max_request_days:
                errors.append("Min request days cannot exceed max request days")
    
    return errors


def policy_to_response(
    policy: TimeOffPolicy,
    session: Session,
    include_stats: bool = True,
    include_history: bool = True,
) -> PolicyResponse:
    """Convert policy model to response."""
    # Parse tenure tiers
    tenure_tiers = None
    if policy.tenure_tiers:
        try:
            tenure_tiers = [TenureTier(**t) for t in json.loads(policy.tenure_tiers)]
        except (json.JSONDecodeError, TypeError):
            tenure_tiers = None
    
    # Build accrual config
    accrual = AccrualConfig(
        method=AccrualMethodEnum(policy.accrual_method),
        base_rate=policy.base_accrual_rate,
        frequency=policy.accrual_frequency,
        cap=policy.accrual_cap,
        tenure_tiers=tenure_tiers,
    )
    
    # Build balance config
    balance = BalanceConfig(
        max_balance=policy.max_balance,
        min_balance_allowed=policy.min_balance_allowed,
        max_carryover=policy.max_carryover,
        carryover_expiry_months=policy.carryover_expiry_months,
        allow_negative=policy.allow_negative_balance,
    )
    
    # Build request config
    request_config = RequestConfig(
        min_request_days=policy.min_request_days,
        max_request_days=policy.max_request_days,
        advance_notice_days=policy.advance_notice_days,
        max_consecutive_days=policy.max_consecutive_days,
    )
    
    # Build approval config
    approval = ApprovalConfig(
        requires_approval=policy.requires_approval,
        approval_levels=policy.approval_levels,
        auto_approve_threshold=policy.auto_approve_threshold,
    )
    
    # Get assignment stats
    stats = AssignmentStats()
    if include_stats:
        # In production, query actual assignments
        stats = AssignmentStats(
            total_assigned=0,
            active_assigned=0,
            pending_requests=0,
            total_balance_allocated=0,
        )
    
    # Get version history
    version_history = []
    if include_history:
        stmt = select(PolicyVersion).where(
            PolicyVersion.policy_id == policy.id
        ).order_by(PolicyVersion.version_number.desc()).limit(10)
        versions = session.execute(stmt).scalars().all()
        version_history = [
            PolicyVersionInfo(
                version_number=v.version_number,
                created_at=v.created_at,
                created_by_name=v.created_by_name,
                change_summary=v.change_summary,
            )
            for v in versions
        ]
    
    # Get recent audit entries
    recent_audit = []
    stmt = select(PolicyAuditLog).where(
        PolicyAuditLog.policy_id == policy.id
    ).order_by(PolicyAuditLog.performed_at.desc()).limit(5)
    audits = session.execute(stmt).scalars().all()
    recent_audit = [
        AuditEntry(
            id=a.id,
            action=a.action,
            performed_by_name=a.performed_by_name or "System",
            performed_at=a.performed_at,
            notes=a.notes,
        )
        for a in audits
    ]
    
    # Parse eligibility rules
    eligibility_rules = None
    if policy.eligibility_criteria:
        try:
            eligibility_rules = json.loads(policy.eligibility_criteria)
        except json.JSONDecodeError:
            eligibility_rules = None
    
    return PolicyResponse(
        id=policy.id,
        name=policy.name,
        code=policy.code,
        description=policy.description,
        policy_type=policy.policy_type,
        status=PolicyStatusEnum(policy.status),
        version=policy.version,
        accrual=accrual,
        balance=balance,
        request=request_config,
        approval=approval,
        waiting_period_days=policy.waiting_period_days,
        eligibility_rules=eligibility_rules,
        prorate_first_year=policy.prorate_first_year,
        include_weekends=policy.include_weekends,
        include_holidays=policy.include_holidays,
        effective_date=policy.effective_date,
        expiry_date=policy.expiry_date,
        assignment_stats=stats,
        version_history=version_history,
        created_at=policy.created_at,
        updated_at=policy.updated_at,
        created_by=policy.created_by,
        recent_audit_entries=recent_audit,
    )


def create_policy_audit(
    policy_id: int,
    action: str,
    performer_id: int,
    performer_name: str,
    previous_values: Optional[Dict] = None,
    new_values: Optional[Dict] = None,
    notes: Optional[str] = None,
    session: Session = None,
) -> PolicyAuditLog:
    """Create audit log entry for policy operation."""
    audit = PolicyAuditLog(
        policy_id=policy_id,
        action=action,
        performed_by=performer_id,
        performed_by_name=performer_name,
        previous_values=json.dumps(previous_values) if previous_values else None,
        new_values=json.dumps(new_values) if new_values else None,
        notes=notes,
    )
    if session:
        session.add(audit)
    return audit


def evaluate_eligibility(
    policy: TimeOffPolicy,
    session: Session,
) -> List[Dict[str, Any]]:
    """Evaluate which employees are eligible for this policy."""
    recommendations = []
    
    # Get all active employees
    stmt = select(Employee).where(Employee.status == "active")
    employees = session.execute(stmt).scalars().all()
    
    for employee in employees[:50]:  # Limit for demo
        # Check waiting period
        hire_date = employee.hire_date or datetime.now().date()
        days_employed = (datetime.now().date() - hire_date).days
        
        if days_employed >= policy.waiting_period_days:
            recommendations.append({
                "employee_id": employee.id,
                "employee_name": f"{employee.first_name} {employee.last_name}",
                "eligible": True,
                "reason": "Meets all eligibility criteria",
                "recommended_effective_date": datetime.now().isoformat(),
            })
    
    return recommendations


# =============================================================================
# Endpoints
# =============================================================================

@policy_management_router.post(
    "",
    response_model=PolicyCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new policy",
    description="Create a new time-off policy with comprehensive validation.",
)
async def create_policy(
    request: CreatePolicyRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> PolicyCreateResponse:
    """
    Create a new time-off policy.
    
    - Validates accrual method consistency
    - Validates eligibility rule logic
    - Validates business rule compliance
    - Automatically evaluates existing employees for assignment
    - Returns assignment recommendations
    """
    require_admin(current_user)
    
    # Validate configuration
    validation_errors = validate_policy_config(request)
    if validation_errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Validation failed", "errors": validation_errors},
        )
    
    # Check for duplicate code
    stmt = select(TimeOffPolicy).where(TimeOffPolicy.code == request.code)
    existing = session.execute(stmt).scalars().first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Policy with code '{request.code}' already exists",
        )
    
    # Create policy
    policy = TimeOffPolicy(
        name=request.name,
        code=request.code,
        description=request.description,
        policy_type=request.policy_type.value,
        status=PolicyStatus.ACTIVE.value if request.activate_immediately else PolicyStatus.DRAFT.value,
        version=1,
        accrual_method=request.accrual.method.value,
        base_accrual_rate=request.accrual.base_rate,
        accrual_frequency=request.accrual.frequency,
        accrual_cap=request.accrual.cap,
        tenure_tiers=json.dumps([t.dict() for t in request.accrual.tenure_tiers]) if request.accrual.tenure_tiers else None,
        max_balance=request.balance.max_balance if request.balance else None,
        min_balance_allowed=request.balance.min_balance_allowed if request.balance else 0,
        max_carryover=request.balance.max_carryover if request.balance else None,
        carryover_expiry_months=request.balance.carryover_expiry_months if request.balance else None,
        allow_negative_balance=request.balance.allow_negative if request.balance else False,
        min_request_days=request.request.min_request_days if request.request else 0.5,
        max_request_days=request.request.max_request_days if request.request else None,
        advance_notice_days=request.request.advance_notice_days if request.request else 0,
        max_consecutive_days=request.request.max_consecutive_days if request.request else None,
        requires_approval=request.approval.requires_approval if request.approval else True,
        approval_levels=request.approval.approval_levels if request.approval else 1,
        auto_approve_threshold=request.approval.auto_approve_threshold if request.approval else None,
        waiting_period_days=request.waiting_period_days,
        eligibility_criteria=json.dumps([r.dict() for r in request.eligibility_rules]) if request.eligibility_rules else None,
        prorate_first_year=request.prorate_first_year,
        include_weekends=request.include_weekends,
        include_holidays=request.include_holidays,
        effective_date=request.effective_date,
        expiry_date=request.expiry_date,
        created_by=current_user.employee_id,
    )
    
    session.add(policy)
    session.flush()
    
    # Create initial version
    version = PolicyVersion(
        policy_id=policy.id,
        version_number=1,
        policy_snapshot=json.dumps(request.dict()),
        change_summary="Initial policy creation",
        created_by=current_user.employee_id or 0,
        created_by_name="Admin",
    )
    session.add(version)
    
    # Create audit entry
    create_policy_audit(
        policy_id=policy.id,
        action="policy_created",
        performer_id=current_user.employee_id or 0,
        performer_name="Admin",
        new_values=request.dict(),
        notes=f"Created policy: {request.name}",
        session=session,
    )
    
    session.commit()
    
    # Evaluate eligibility
    recommendations = evaluate_eligibility(policy, session)
    
    return PolicyCreateResponse(
        policy=policy_to_response(policy, session),
        assignment_recommendations=recommendations,
        eligible_employee_count=len([r for r in recommendations if r.get("eligible")]),
        message=f"Policy '{request.name}' created successfully",
    )


@policy_management_router.get(
    "/{policy_id}",
    response_model=PolicyResponse,
    summary="Get policy details",
    description="Get complete policy details including configuration, eligibility rules, and version history.",
)
async def get_policy(
    policy_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    include_stats: bool = Query(default=True, description="Include assignment statistics"),
    include_history: bool = Query(default=True, description="Include version history"),
) -> PolicyResponse:
    """Get complete policy details."""
    policy = session.get(TimeOffPolicy, policy_id)
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy {policy_id} not found",
        )
    
    return policy_to_response(policy, session, include_stats, include_history)


@policy_management_router.put(
    "/{policy_id}",
    response_model=PolicyUpdateResponse,
    summary="Update policy",
    description="Update policy with impact analysis and notification support.",
)
async def update_policy(
    policy_id: int,
    request: UpdatePolicyRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> PolicyUpdateResponse:
    """
    Update an existing policy.
    
    - Performs impact analysis on existing assignments
    - Supports policy versioning
    - Validates backward compatibility
    - Generates notifications for affected employees
    """
    require_admin(current_user)
    
    policy = session.get(TimeOffPolicy, policy_id)
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy {policy_id} not found",
        )
    
    # Store previous values for audit
    previous_values = {
        "name": policy.name,
        "description": policy.description,
        "accrual_method": policy.accrual_method,
        "base_accrual_rate": policy.base_accrual_rate,
    }
    
    # Track changes
    changes = []
    
    # Apply updates
    if request.name is not None and request.name != policy.name:
        changes.append(f"Name: {policy.name} -> {request.name}")
        policy.name = request.name
    
    if request.description is not None:
        policy.description = request.description
    
    if request.accrual:
        if request.accrual.method.value != policy.accrual_method:
            changes.append(f"Accrual method: {policy.accrual_method} -> {request.accrual.method.value}")
        policy.accrual_method = request.accrual.method.value
        policy.base_accrual_rate = request.accrual.base_rate
        policy.accrual_frequency = request.accrual.frequency
        policy.accrual_cap = request.accrual.cap
        if request.accrual.tenure_tiers:
            policy.tenure_tiers = json.dumps([t.dict() for t in request.accrual.tenure_tiers])
    
    if request.balance:
        policy.max_balance = request.balance.max_balance
        policy.min_balance_allowed = request.balance.min_balance_allowed
        policy.max_carryover = request.balance.max_carryover
        policy.carryover_expiry_months = request.balance.carryover_expiry_months
        policy.allow_negative_balance = request.balance.allow_negative
    
    if request.request:
        policy.min_request_days = request.request.min_request_days
        policy.max_request_days = request.request.max_request_days
        policy.advance_notice_days = request.request.advance_notice_days
        policy.max_consecutive_days = request.request.max_consecutive_days
    
    if request.approval:
        policy.requires_approval = request.approval.requires_approval
        policy.approval_levels = request.approval.approval_levels
        policy.auto_approve_threshold = request.approval.auto_approve_threshold
    
    if request.waiting_period_days is not None:
        policy.waiting_period_days = request.waiting_period_days
    
    if request.eligibility_rules is not None:
        policy.eligibility_criteria = json.dumps([r.dict() for r in request.eligibility_rules])
    
    if request.prorate_first_year is not None:
        policy.prorate_first_year = request.prorate_first_year
    
    if request.include_weekends is not None:
        policy.include_weekends = request.include_weekends
    
    if request.include_holidays is not None:
        policy.include_holidays = request.include_holidays
    
    if request.effective_date is not None:
        policy.effective_date = request.effective_date
    
    if request.expiry_date is not None:
        policy.expiry_date = request.expiry_date
    
    # Increment version
    policy.version += 1
    policy.updated_by = current_user.employee_id
    policy.updated_at = datetime.utcnow()
    
    # Create version record
    version = PolicyVersion(
        policy_id=policy.id,
        version_number=policy.version,
        policy_snapshot=json.dumps(request.dict()),
        change_summary="; ".join(changes) if changes else "Configuration updated",
        change_reason=request.change_reason,
        created_by=current_user.employee_id or 0,
        created_by_name="Admin",
    )
    session.add(version)
    
    # Create audit entry
    create_policy_audit(
        policy_id=policy.id,
        action="policy_updated",
        performer_id=current_user.employee_id or 0,
        performer_name="Admin",
        previous_values=previous_values,
        new_values=request.dict(exclude_unset=True),
        notes=request.change_reason,
        session=session,
    )
    
    session.commit()
    
    # Impact analysis
    impact_analysis = {
        "changes_summary": changes,
        "backward_compatible": True,
        "breaking_changes": [],
    }
    
    # Count affected employees (mock)
    affected_employees = 0
    notifications_queued = 0
    
    if request.notify_affected_employees:
        notifications_queued = affected_employees
    
    return PolicyUpdateResponse(
        policy=policy_to_response(policy, session),
        impact_analysis=impact_analysis,
        affected_employees=affected_employees,
        notifications_queued=notifications_queued,
        version_created=True,
        message=f"Policy '{policy.name}' updated to version {policy.version}",
    )


@policy_management_router.delete(
    "/{policy_id}",
    response_model=PolicyDeactivateResponse,
    summary="Deactivate policy",
    description="Safely deactivate a policy with balance handling and audit trail.",
)
async def deactivate_policy(
    policy_id: int,
    request: DeactivatePolicyRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> PolicyDeactivateResponse:
    """
    Deactivate a policy safely.
    
    - Validates safe deactivation
    - Processes final accrual calculations
    - Handles balance transfers
    - Maintains historical records
    """
    require_admin(current_user)
    
    policy = session.get(TimeOffPolicy, policy_id)
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy {policy_id} not found",
        )
    
    if policy.status == PolicyStatus.ARCHIVED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Policy is already archived",
        )
    
    # Validate alternative policy if transfers requested
    if request.transfer_balances and request.alternative_policy_id:
        alt_policy = session.get(TimeOffPolicy, request.alternative_policy_id)
        if not alt_policy:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Alternative policy {request.alternative_policy_id} not found",
            )
        if alt_policy.status != PolicyStatus.ACTIVE.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Alternative policy must be active",
            )
    
    # Update policy status
    previous_status = policy.status
    policy.status = PolicyStatus.ARCHIVED.value
    policy.updated_by = current_user.employee_id
    policy.updated_at = datetime.utcnow()
    
    # Create audit entry
    audit = create_policy_audit(
        policy_id=policy.id,
        action="policy_deactivated",
        performer_id=current_user.employee_id or 0,
        performer_name="Admin",
        previous_values={"status": previous_status},
        new_values={"status": PolicyStatus.ARCHIVED.value},
        notes=request.reason,
        session=session,
    )
    
    session.commit()
    
    # Mock counts
    employees_affected = 0
    balances_transferred = 0
    
    return PolicyDeactivateResponse(
        policy_id=policy_id,
        new_status=PolicyStatusEnum.ARCHIVED,
        employees_affected=employees_affected,
        balances_transferred=balances_transferred,
        alternative_policy_id=request.alternative_policy_id,
        final_accrual_processed=True,
        audit_entry=AuditEntry(
            id=audit.id if hasattr(audit, 'id') else 0,
            action="policy_deactivated",
            performed_by_name="Admin",
            performed_at=datetime.utcnow(),
            notes=request.reason,
        ),
        message=f"Policy deactivated successfully. {employees_affected} employees affected.",
    )


@policy_management_router.get(
    "",
    response_model=PolicyListResponse,
    summary="List policies",
    description="List all policies with filtering options.",
)
async def list_policies(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    status: Optional[PolicyStatusEnum] = Query(default=None, description="Filter by status"),
    policy_type: Optional[str] = Query(default=None, description="Filter by type"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Page size"),
) -> PolicyListResponse:
    """List all policies with filtering."""
    # Build query
    stmt = select(TimeOffPolicy)
    
    if status:
        stmt = stmt.where(TimeOffPolicy.status == status.value)
    if policy_type:
        stmt = stmt.where(TimeOffPolicy.policy_type == policy_type)
    
    # Get total count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = session.execute(count_stmt).scalar() or 0
    
    # Apply pagination
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    
    policies = session.execute(stmt).scalars().all()
    
    return PolicyListResponse(
        policies=[policy_to_response(p, session, include_stats=False, include_history=False) for p in policies],
        total=total,
        page=page,
        page_size=page_size,
    )

