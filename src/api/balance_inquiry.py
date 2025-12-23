"""API endpoints for employee balance inquiry."""

import uuid
import logging
from datetime import date, datetime, timedelta
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.models.employee import Employee
from src.models.time_off_request import TimeOffRequest, TimeOffRequestStatus, TimeOffBalance
from src.models.time_off_policy import TimeOffPolicy, PolicyStatus
from src.schemas.balance_inquiry import (
    EmployeeBalanceResponse,
    BalanceProjectionResponse,
    PolicyBalance,
    PolicyInfo,
    AccrualScheduleInfo,
    ScheduledAccrual,
    PendingRequestInfo,
    ConstraintInfo,
    BalanceStatusEnum,
    AccrualTypeEnum,
    ProjectionRequest,
    PolicyProjection,
    ProjectionComponent,
)
from src.utils.auth import CurrentUser, UserRole, get_mock_current_user

logger = logging.getLogger(__name__)


# =============================================================================
# Router Setup
# =============================================================================

balance_inquiry_router = APIRouter(
    prefix="/api/time-off/balances",
    tags=["Balance Inquiry"],
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
    
    roles = [UserRole.EMPLOYEE]
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


# =============================================================================
# Helper Functions
# =============================================================================

def validate_access(
    current_user: CurrentUser,
    target_employee_id: int,
    session: Session,
) -> bool:
    """
    Validate that the current user has access to view target employee's balance.
    
    Access rules:
    - Employees can view their own balance
    - Managers can view direct reports
    - HR/Admin can view anyone
    """
    # Same user
    if current_user.employee_id == target_employee_id:
        return True
    
    # HR/Admin access
    if UserRole.HR in current_user.roles or UserRole.ADMIN in current_user.roles:
        return True
    
    # Manager access - check if current user is target's manager
    if UserRole.MANAGER in current_user.roles:
        target_employee = session.get(Employee, target_employee_id)
        if target_employee and target_employee.manager_id == current_user.employee_id:
            return True
        
        # Also check skip-level (manager of manager)
        if target_employee and target_employee.manager_id:
            direct_manager = session.get(Employee, target_employee.manager_id)
            if direct_manager and direct_manager.manager_id == current_user.employee_id:
                return True
    
    return False


def get_balance_status(available: float, total: float, max_balance: Optional[float]) -> tuple[BalanceStatusEnum, Optional[str]]:
    """Determine balance status based on values."""
    if available < 0:
        return BalanceStatusEnum.NEGATIVE, "Balance is negative"
    
    if total > 0:
        ratio = available / total
        if ratio <= 0.1:
            return BalanceStatusEnum.CRITICAL, f"Only {available:.1f} days remaining"
        if ratio <= 0.25:
            return BalanceStatusEnum.LOW, f"Low balance: {available:.1f} days"
    
    if max_balance and available >= max_balance:
        return BalanceStatusEnum.HEALTHY, "Balance at maximum - use it or lose it!"
    
    return BalanceStatusEnum.HEALTHY, None


def calculate_scheduled_accruals(
    employee_id: int,
    policy: TimeOffPolicy,
    from_date: date,
    to_date: date,
) -> List[ScheduledAccrual]:
    """Calculate scheduled accruals for a period."""
    accruals = []
    
    if policy.accrual_method == "annual_lump_sum":
        # Annual lump sum typically accrues on anniversary or Jan 1
        next_year = date(from_date.year + 1, 1, 1)
        if from_date <= next_year <= to_date:
            accruals.append(ScheduledAccrual(
                accrual_date=next_year,
                accrual_type=AccrualTypeEnum.REGULAR,
                amount=policy.base_accrual_rate,
                description=f"Annual {policy.name} allocation",
            ))
    
    elif policy.accrual_method == "monthly_accrual":
        monthly_rate = policy.base_accrual_rate / 12
        current = from_date.replace(day=1) + timedelta(days=32)
        current = current.replace(day=1)  # First of next month
        
        while current <= to_date:
            accruals.append(ScheduledAccrual(
                accrual_date=current,
                accrual_type=AccrualTypeEnum.REGULAR,
                amount=monthly_rate,
                description=f"Monthly {policy.name} accrual",
            ))
            current = (current + timedelta(days=32)).replace(day=1)
    
    elif policy.accrual_method == "pay_period_accrual":
        # Assuming bi-weekly pay periods
        biweekly_rate = policy.base_accrual_rate / 26
        current = from_date
        while current <= to_date:
            # Find next Friday (typical pay day)
            days_until_friday = (4 - current.weekday()) % 14
            if days_until_friday == 0:
                days_until_friday = 14
            next_pay = current + timedelta(days=days_until_friday)
            
            if next_pay <= to_date:
                accruals.append(ScheduledAccrual(
                    accrual_date=next_pay,
                    accrual_type=AccrualTypeEnum.REGULAR,
                    amount=biweekly_rate,
                    description=f"Pay period {policy.name} accrual",
                ))
            current = next_pay + timedelta(days=1)
    
    return accruals


def get_employee_balance(
    employee_id: int,
    session: Session,
    as_of_date: Optional[date] = None,
) -> List[PolicyBalance]:
    """Get employee's balance across all applicable policies."""
    if as_of_date is None:
        as_of_date = date.today()
    
    current_year = as_of_date.year
    balances = []
    
    # Get active policies
    stmt = select(TimeOffPolicy).where(
        TimeOffPolicy.status == PolicyStatus.ACTIVE.value
    )
    policies = session.execute(stmt).scalars().all()
    
    for policy in policies:
        # Get balance record
        balance_stmt = select(TimeOffBalance).where(
            TimeOffBalance.employee_id == employee_id,
            TimeOffBalance.balance_type == policy.policy_type,
            TimeOffBalance.year == current_year,
        )
        balance_record = session.execute(balance_stmt).scalars().first()
        
        # Default values
        total_allocated = policy.base_accrual_rate
        used = 0.0
        pending = 0.0
        carried_over = 0.0
        
        if balance_record:
            total_allocated = balance_record.total_allocated
            used = balance_record.used
            pending = balance_record.pending
            carried_over = balance_record.carried_over
        
        available = total_allocated + carried_over - used - pending
        
        # Get pending requests
        pending_stmt = select(TimeOffRequest).where(
            TimeOffRequest.employee_id == employee_id,
            TimeOffRequest.request_type == policy.policy_type,
            TimeOffRequest.status == TimeOffRequestStatus.PENDING_APPROVAL.value,
        )
        pending_requests = session.execute(pending_stmt).scalars().all()
        
        pending_request_info = [
            PendingRequestInfo(
                request_id=req.id,
                start_date=req.start_date,
                end_date=req.end_date,
                days_requested=req.total_days,
                request_type=req.request_type,
                status=req.status,
                submitted_at=req.submitted_at or req.created_at,
            )
            for req in pending_requests
        ]
        
        # Calculate scheduled accruals
        end_of_year = date(current_year, 12, 31)
        scheduled = calculate_scheduled_accruals(
            employee_id, policy, as_of_date, end_of_year
        )
        
        next_accrual = scheduled[0] if scheduled else None
        
        accrual_info = AccrualScheduleInfo(
            next_accrual_date=next_accrual.accrual_date if next_accrual else None,
            next_accrual_amount=next_accrual.amount if next_accrual else 0,
            remaining_accruals_this_year=len(scheduled),
            total_remaining_accrual=sum(s.amount for s in scheduled),
            scheduled_accruals=scheduled[:5],  # Limit to next 5
        )
        
        # Build constraints
        constraints = []
        
        if policy.max_balance:
            constraints.append(ConstraintInfo(
                constraint_type="max_balance",
                limit=policy.max_balance,
                current_value=available,
                is_within_limit=available <= policy.max_balance,
                message=f"Maximum balance: {policy.max_balance} days",
            ))
        
        if policy.min_balance_allowed is not None:
            constraints.append(ConstraintInfo(
                constraint_type="min_balance",
                limit=policy.min_balance_allowed,
                current_value=available,
                is_within_limit=available >= policy.min_balance_allowed,
                message=f"Minimum balance allowed: {policy.min_balance_allowed} days",
            ))
        
        # Determine status
        status, status_message = get_balance_status(available, total_allocated, policy.max_balance)
        
        balances.append(PolicyBalance(
            policy=PolicyInfo(
                policy_id=policy.id,
                policy_name=policy.name,
                policy_code=policy.code,
                policy_type=policy.policy_type,
                accrual_method=policy.accrual_method,
                max_balance=policy.max_balance,
                max_carryover=policy.max_carryover,
            ),
            total_allocated=total_allocated,
            used=used,
            pending=pending,
            available=available,
            carried_over=carried_over,
            balance_status=status,
            status_message=status_message,
            accrual_info=accrual_info,
            pending_requests=pending_request_info,
            constraints=constraints,
            as_of_date=as_of_date,
            year=current_year,
        ))
    
    return balances


def calculate_projection(
    employee_id: int,
    policy: TimeOffPolicy,
    current_balance: float,
    projection_date: date,
    include_pending: bool,
    include_accruals: bool,
    adjustments: List[dict],
    session: Session,
) -> PolicyProjection:
    """Calculate balance projection for a specific policy."""
    today = date.today()
    components = []
    running_balance = current_balance
    
    # Add current balance as starting point
    components.append(ProjectionComponent(
        component_type="starting_balance",
        date=today,
        amount=current_balance,
        running_balance=running_balance,
        description="Starting balance",
    ))
    
    # Add scheduled accruals
    projected_accruals = 0.0
    if include_accruals:
        accruals = calculate_scheduled_accruals(
            employee_id, policy, today, projection_date
        )
        for accrual in accruals:
            running_balance += accrual.amount
            projected_accruals += accrual.amount
            
            # Check max balance cap
            if policy.max_balance and running_balance > policy.max_balance:
                capped_amount = policy.max_balance - (running_balance - accrual.amount)
                running_balance = policy.max_balance
                components.append(ProjectionComponent(
                    component_type="accrual_capped",
                    date=accrual.accrual_date,
                    amount=capped_amount,
                    running_balance=running_balance,
                    description=f"Accrual capped at max balance",
                ))
            else:
                components.append(ProjectionComponent(
                    component_type="accrual",
                    date=accrual.accrual_date,
                    amount=accrual.amount,
                    running_balance=running_balance,
                    description=accrual.description or "Scheduled accrual",
                ))
    
    # Add pending requests
    projected_pending = 0.0
    if include_pending:
        pending_stmt = select(TimeOffRequest).where(
            TimeOffRequest.employee_id == employee_id,
            TimeOffRequest.request_type == policy.policy_type,
            TimeOffRequest.status == TimeOffRequestStatus.PENDING_APPROVAL.value,
            TimeOffRequest.start_date <= projection_date,
        )
        pending = session.execute(pending_stmt).scalars().all()
        
        for req in pending:
            running_balance -= req.total_days
            projected_pending += req.total_days
            components.append(ProjectionComponent(
                component_type="pending_request",
                date=req.start_date,
                amount=-req.total_days,
                running_balance=running_balance,
                description=f"Pending request #{req.id}",
            ))
    
    # Add scenario adjustments
    projected_adjustments = 0.0
    for adj in adjustments:
        if adj.get("effective_date") and adj.get("effective_date") <= projection_date:
            amount = adj.get("amount", 0)
            running_balance += amount
            projected_adjustments += amount
            components.append(ProjectionComponent(
                component_type="adjustment",
                date=adj.get("effective_date"),
                amount=amount,
                running_balance=running_balance,
                description=adj.get("description", "Scenario adjustment"),
            ))
    
    # Check for expiring balance
    will_expire = False
    expiring_amount = 0.0
    expiry_date = None
    
    if policy.carryover_expiry_months:
        # Calculate expiry date for carried over balance
        expiry_date = date(today.year, 1, 1) + timedelta(days=policy.carryover_expiry_months * 30)
        if projection_date >= expiry_date:
            # Some balance may expire
            will_expire = True
            expiring_amount = min(running_balance, policy.max_carryover or 0)
    
    # Sort components by date
    components.sort(key=lambda c: c.date)
    
    return PolicyProjection(
        policy=PolicyInfo(
            policy_id=policy.id,
            policy_name=policy.name,
            policy_code=policy.code,
            policy_type=policy.policy_type,
            accrual_method=policy.accrual_method,
            max_balance=policy.max_balance,
            max_carryover=policy.max_carryover,
        ),
        current_balance=current_balance,
        projected_balance=running_balance,
        projection_date=projection_date,
        projected_accruals=projected_accruals,
        projected_pending=projected_pending,
        projected_adjustments=projected_adjustments,
        projection_components=components,
        at_max_balance=policy.max_balance is not None and running_balance >= policy.max_balance,
        will_expire=will_expire,
        expiring_amount=expiring_amount,
        expiry_date=expiry_date,
    )


# =============================================================================
# Endpoints
# =============================================================================

@balance_inquiry_router.get(
    "/employee",
    response_model=EmployeeBalanceResponse,
    summary="Get current user's balance",
    description="Get authenticated employee's balance across all applicable policies.",
)
async def get_my_balance(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    as_of_date: Optional[date] = Query(default=None, description="Balance as of date"),
) -> EmployeeBalanceResponse:
    """
    Get authenticated employee's balance information.
    
    Returns:
    - Current balances across all applicable policies
    - Scheduled accruals and next accrual dates
    - Pending requests
    - Available balance after pending requests
    """
    employee_id = current_user.employee_id or 1
    
    # Get employee info
    employee = session.get(Employee, employee_id)
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found",
        )
    
    employee_name = f"{employee.first_name} {employee.last_name}"
    
    # Get balances
    balances = get_employee_balance(employee_id, session, as_of_date)
    
    # Calculate totals
    total_available = sum(b.available for b in balances)
    total_pending = sum(b.pending for b in balances)
    
    return EmployeeBalanceResponse(
        employee_id=employee_id,
        employee_name=employee_name,
        balances=balances,
        total_available_days=total_available,
        total_pending_days=total_pending,
    )


@balance_inquiry_router.get(
    "/employee/{employee_id}",
    response_model=EmployeeBalanceResponse,
    summary="Get specific employee's balance",
    description="Get balance for a specific employee with access control validation.",
)
async def get_employee_balance_by_id(
    employee_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    as_of_date: Optional[date] = Query(default=None, description="Balance as of date"),
) -> EmployeeBalanceResponse:
    """
    Get specific employee's balance information.
    
    Access control:
    - Managers can view direct reports
    - HR/Admin can view anyone
    - Employees cannot view others' balances
    """
    # Validate access
    if not validate_access(current_user, employee_id, session):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this employee's balance",
        )
    
    # Get employee info
    employee = session.get(Employee, employee_id)
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee {employee_id} not found",
        )
    
    employee_name = f"{employee.first_name} {employee.last_name}"
    
    # Get balances
    balances = get_employee_balance(employee_id, session, as_of_date)
    
    # Calculate totals
    total_available = sum(b.available for b in balances)
    total_pending = sum(b.pending for b in balances)
    
    return EmployeeBalanceResponse(
        employee_id=employee_id,
        employee_name=employee_name,
        balances=balances,
        total_available_days=total_available,
        total_pending_days=total_pending,
    )


@balance_inquiry_router.get(
    "/projection",
    response_model=BalanceProjectionResponse,
    summary="Get balance projection",
    description="Calculate balance projections with detailed breakdown of components.",
)
async def get_balance_projection(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    projection_date: date = Query(..., description="Date to project balance to"),
    employee_id: Optional[int] = Query(default=None, description="Employee ID"),
    policy_id: Optional[int] = Query(default=None, description="Policy ID"),
    include_pending: bool = Query(default=True, description="Include pending requests"),
    include_accruals: bool = Query(default=True, description="Include scheduled accruals"),
) -> BalanceProjectionResponse:
    """
    Calculate balance projection to a specific date.
    
    Provides detailed breakdown of:
    - Projected accruals
    - Pending requests impact
    - Running balance by date
    """
    target_employee_id = employee_id or current_user.employee_id or 1
    
    # Validate access
    if not validate_access(current_user, target_employee_id, session):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this employee's balance",
        )
    
    # Get employee info
    employee = session.get(Employee, target_employee_id)
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee {target_employee_id} not found",
        )
    
    employee_name = f"{employee.first_name} {employee.last_name}"
    
    # Validate projection date
    if projection_date < date.today():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Projection date must be in the future",
        )
    
    # Get current balances
    current_balances = get_employee_balance(target_employee_id, session)
    
    # Filter to specific policy if requested
    if policy_id:
        current_balances = [b for b in current_balances if b.policy.policy_id == policy_id]
        if not current_balances:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Policy {policy_id} not found or not assigned to employee",
            )
    
    # Calculate projections
    projections = []
    warnings = []
    
    for balance in current_balances:
        policy = session.get(TimeOffPolicy, balance.policy.policy_id)
        if not policy:
            continue
        
        projection = calculate_projection(
            employee_id=target_employee_id,
            policy=policy,
            current_balance=balance.available,
            projection_date=projection_date,
            include_pending=include_pending,
            include_accruals=include_accruals,
            adjustments=[],
            session=session,
        )
        
        projections.append(projection)
        
        # Add warnings
        if projection.at_max_balance:
            warnings.append(f"{policy.name}: Balance will be at maximum - consider using time-off")
        if projection.will_expire:
            warnings.append(f"{policy.name}: {projection.expiring_amount:.1f} days will expire on {projection.expiry_date}")
    
    # Calculate totals
    total_projected = sum(p.projected_balance for p in projections)
    total_accruals = sum(p.projected_accruals for p in projections)
    
    return BalanceProjectionResponse(
        employee_id=target_employee_id,
        employee_name=employee_name,
        projection_date=projection_date,
        scenario_applied=False,
        projections=projections,
        total_projected_balance=total_projected,
        total_projected_accruals=total_accruals,
        warnings=warnings,
    )


@balance_inquiry_router.post(
    "/projection",
    response_model=BalanceProjectionResponse,
    summary="Calculate projection with scenarios",
    description="Calculate balance projection with custom scenario adjustments.",
)
async def calculate_balance_projection(
    request: ProjectionRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> BalanceProjectionResponse:
    """
    Calculate balance projection with scenario adjustments.
    
    Allows modeling "what-if" scenarios by adding adjustments.
    """
    target_employee_id = request.employee_id or current_user.employee_id or 1
    
    # Validate access
    if not validate_access(current_user, target_employee_id, session):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this employee's balance",
        )
    
    # Get employee info
    employee = session.get(Employee, target_employee_id)
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee {target_employee_id} not found",
        )
    
    employee_name = f"{employee.first_name} {employee.last_name}"
    
    # Get current balances
    current_balances = get_employee_balance(target_employee_id, session)
    
    # Filter to specific policy if requested
    if request.policy_id:
        current_balances = [b for b in current_balances if b.policy.policy_id == request.policy_id]
    
    # Convert scenario adjustments
    adjustments = []
    if request.scenario_adjustments:
        adjustments = [adj.dict() for adj in request.scenario_adjustments]
    
    # Calculate projections
    projections = []
    warnings = []
    
    for balance in current_balances:
        policy = session.get(TimeOffPolicy, balance.policy.policy_id)
        if not policy:
            continue
        
        projection = calculate_projection(
            employee_id=target_employee_id,
            policy=policy,
            current_balance=balance.available,
            projection_date=request.projection_date,
            include_pending=request.include_pending_requests,
            include_accruals=request.include_scheduled_accruals,
            adjustments=adjustments,
            session=session,
        )
        
        projections.append(projection)
        
        if projection.at_max_balance:
            warnings.append(f"{policy.name}: Balance will be at maximum")
        if projection.will_expire:
            warnings.append(f"{policy.name}: {projection.expiring_amount:.1f} days will expire")
    
    return BalanceProjectionResponse(
        employee_id=target_employee_id,
        employee_name=employee_name,
        projection_date=request.projection_date,
        scenario_applied=len(adjustments) > 0,
        projections=projections,
        total_projected_balance=sum(p.projected_balance for p in projections),
        total_projected_accruals=sum(p.projected_accruals for p in projections),
        warnings=warnings,
    )

