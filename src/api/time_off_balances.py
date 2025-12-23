"""API endpoints for time-off balance inquiry."""

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.schemas.time_off_balances import (
    EmployeeBalancesResponse,
    BalancesSummary,
    PolicyBalanceDetail,
    BalanceStatus,
    ScheduledAccrualInfo,
    AccrualEntry,
    AccrualStatus,
    PendingRequestImpact,
    BalanceProjectionResponse,
    ProjectedBalanceDetail,
    ProjectionScenario,
)


time_off_balances_router = APIRouter(
    prefix="/api/time-off",
    tags=["Time-Off Balance Inquiry"],
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
        "hire_date": date(2023, 1, 15),
    }


def get_employee_policies(employee_id: int) -> List[Dict[str, Any]]:
    """Get policies applicable to an employee."""
    return [
        {
            "id": 1,
            "name": "Paid Time Off",
            "code": "PTO",
            "type": "vacation",
            "allocated": 20.0,
            "used": 5.0,
            "carryover": 3.0,
            "max_balance": 40.0,
            "allows_negative": False,
        },
        {
            "id": 2,
            "name": "Sick Leave",
            "code": "SICK",
            "type": "sick",
            "allocated": 10.0,
            "used": 2.0,
            "carryover": 0.0,
            "max_balance": 20.0,
            "allows_negative": False,
        },
        {
            "id": 3,
            "name": "Personal Days",
            "code": "PERSONAL",
            "type": "personal",
            "allocated": 3.0,
            "used": 1.0,
            "carryover": 0.0,
            "max_balance": None,
            "allows_negative": False,
        },
    ]


def get_pending_requests(employee_id: int, policy_id: int) -> List[PendingRequestImpact]:
    """Get pending requests for an employee and policy."""
    # Mock pending requests
    if policy_id == 1:
        return [
            PendingRequestImpact(
                request_id=1001,
                request_type="PTO",
                start_date=date.today() + timedelta(days=14),
                end_date=date.today() + timedelta(days=16),
                days_requested=3.0,
                status="pending",
                submitted_at=datetime.utcnow() - timedelta(days=2),
            ),
        ]
    return []


def calculate_scheduled_accruals(
    employee_id: int,
    policy_id: int,
    from_date: date,
    to_date: date,
) -> ScheduledAccrualInfo:
    """Calculate scheduled accruals for a date range."""
    # Mock accrual calculation
    accruals = []
    total_remaining = 0.0
    current = from_date
    
    while current <= to_date:
        # Monthly accruals on the 1st
        if current.day == 1:
            accrual_amount = 1.67 if policy_id == 1 else 0.83
            accruals.append(AccrualEntry(
                accrual_id=len(accruals) + 1,
                accrual_date=current,
                amount=accrual_amount,
                accrual_type="monthly",
                status=AccrualStatus.SCHEDULED,
                description="Monthly accrual",
            ))
            total_remaining += accrual_amount
        current += timedelta(days=1)
    
    next_accrual = accruals[0] if accruals else None
    
    return ScheduledAccrualInfo(
        next_accrual_date=next_accrual.accrual_date if next_accrual else None,
        next_accrual_amount=next_accrual.amount if next_accrual else 0,
        remaining_accruals_this_year=len(accruals),
        total_remaining_accrual=round(total_remaining, 2),
        accrual_schedule=accruals[:6],  # Limit to next 6 accruals
    )


def determine_balance_status(
    current: float,
    maximum: Optional[float],
    total_allocated: float,
) -> BalanceStatus:
    """Determine balance status based on current balance."""
    if current < 0:
        return BalanceStatus.NEGATIVE
    if maximum and current >= maximum:
        return BalanceStatus.MAXED
    
    threshold_low = total_allocated * 0.25
    threshold_critical = total_allocated * 0.10
    
    if current <= threshold_critical:
        return BalanceStatus.CRITICAL
    elif current <= threshold_low:
        return BalanceStatus.LOW
    else:
        return BalanceStatus.HEALTHY


# =============================================================================
# Balance Inquiry Endpoint
# =============================================================================

@time_off_balances_router.get(
    "/balances",
    response_model=EmployeeBalancesResponse,
    summary="Get employee time-off balances",
    description="Returns current and projected balance information for the authenticated employee.",
)
async def get_employee_balances(
    include_pending: bool = Query(default=True, description="Include pending request impacts"),
    include_accruals: bool = Query(default=True, description="Include scheduled accruals"),
    policy_id: Optional[int] = Query(default=None, description="Filter by policy ID"),
):
    """
    Get current time-off balances for the authenticated employee.
    
    This endpoint provides:
    - Current balances for all applicable policies
    - Scheduled accrual information
    - Pending request impacts
    - Projected available balances
    - Detailed breakdown for UI display
    
    **Access Control**: Employees can only access their own balance information.
    """
    current_user = get_current_user()
    employee_id = current_user["id"]
    today = date.today()
    year = today.year
    
    # Get policies
    policies = get_employee_policies(employee_id)
    if policy_id:
        policies = [p for p in policies if p["id"] == policy_id]
    
    if not policies:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No policies found for employee",
        )
    
    policy_balances = []
    total_available = 0.0
    total_pending = 0.0
    total_used = 0.0
    
    for policy in policies:
        # Get pending requests
        pending_requests = []
        pending_days = 0.0
        if include_pending:
            pending_requests = get_pending_requests(employee_id, policy["id"])
            pending_days = sum(r.days_requested for r in pending_requests)
        
        # Calculate scheduled accruals
        accruals = ScheduledAccrualInfo(
            next_accrual_date=None,
            next_accrual_amount=0,
            remaining_accruals_this_year=0,
            total_remaining_accrual=0,
            accrual_schedule=[],
        )
        if include_accruals:
            year_end = date(year, 12, 31)
            accruals = calculate_scheduled_accruals(
                employee_id,
                policy["id"],
                today,
                year_end,
            )
        
        # Calculate current balance
        current_balance = (
            policy["allocated"]
            + policy["carryover"]
            - policy["used"]
            - pending_days
        )
        
        # Determine status
        balance_status = determine_balance_status(
            current_balance,
            policy["max_balance"],
            policy["allocated"],
        )
        
        # Status message
        status_messages = {
            BalanceStatus.HEALTHY: "Balance is healthy",
            BalanceStatus.LOW: "Balance is getting low",
            BalanceStatus.CRITICAL: "Balance is critically low",
            BalanceStatus.NEGATIVE: "Balance is negative",
            BalanceStatus.MAXED: "Balance at maximum limit",
        }
        
        policy_balances.append(PolicyBalanceDetail(
            policy_id=policy["id"],
            policy_name=policy["name"],
            policy_code=policy["code"],
            policy_type=policy["type"],
            current_balance=round(current_balance, 2),
            balance_status=balance_status,
            total_allocated=policy["allocated"],
            total_used=policy["used"],
            total_pending=pending_days,
            carryover_balance=policy["carryover"],
            scheduled_accruals=accruals,
            pending_requests=pending_requests,
            maximum_balance=policy["max_balance"],
            minimum_balance=0,
            negative_balance_allowed=policy["allows_negative"],
            expires_on=date(year + 1, 3, 31) if policy["carryover"] > 0 else None,
            days_until_expiration=(date(year + 1, 3, 31) - today).days if policy["carryover"] > 0 else None,
            display_unit="days",
            status_message=status_messages.get(balance_status),
        ))
        
        total_available += current_balance
        total_pending += pending_days
        total_used += policy["used"]
    
    summary = BalancesSummary(
        total_available=round(total_available, 2),
        total_pending=round(total_pending, 2),
        total_used_ytd=round(total_used, 2),
        policies_count=len(policy_balances),
    )
    
    return EmployeeBalancesResponse(
        employee_id=employee_id,
        employee_name=current_user["name"],
        summary=summary,
        policy_balances=policy_balances,
        as_of_date=today,
        balance_year=year,
        retrieved_at=datetime.utcnow(),
    )


# =============================================================================
# Balance Projection Endpoint
# =============================================================================

@time_off_balances_router.get(
    "/balances/projection",
    response_model=BalanceProjectionResponse,
    summary="Get balance projections",
    description="Calculate balance projections for specific dates and scenarios.",
)
async def get_balance_projection(
    projection_date: date = Query(..., description="Date to project balance to"),
    policy_id: Optional[int] = Query(default=None, description="Filter by policy ID"),
    scenario_days: Optional[float] = Query(default=None, ge=0, description="Days for scenario"),
    scenario_date: Optional[date] = Query(default=None, description="Scenario request date"),
):
    """
    Calculate balance projections for a specific date.
    
    This endpoint provides:
    - Projected balances at specified date
    - Scheduled accruals factored in
    - Pending request impacts
    - Optional scenario analysis (what-if)
    
    **Features**:
    - Integrates with accrual calculation engine
    - Factors in all scheduled accruals up to projection date
    - Supports hypothetical request scenarios
    
    **Access Control**: Employees can only access their own projections.
    """
    current_user = get_current_user()
    employee_id = current_user["id"]
    today = date.today()
    
    # Validate projection date
    if projection_date < today:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Projection date must be today or in the future",
        )
    
    # Build scenario if provided
    scenario = None
    if scenario_days is not None:
        scenario = ProjectionScenario(
            scenario_id="SCN-001",
            description=f"Request for {scenario_days} days",
            days_to_request=scenario_days,
            request_date=scenario_date or projection_date,
        )
    
    # Get policies
    policies = get_employee_policies(employee_id)
    if policy_id:
        policies = [p for p in policies if p["id"] == policy_id]
    
    projected_balances = []
    total_projected = 0.0
    total_accruals = 0.0
    warnings = []
    recommendations = []
    
    for policy in policies:
        # Current balance
        pending_impact = sum(
            r.days_requested for r in get_pending_requests(employee_id, policy["id"])
        )
        current = (
            policy["allocated"]
            + policy["carryover"]
            - policy["used"]
            - pending_impact
        )
        
        # Calculate accruals until projection date
        accruals = calculate_scheduled_accruals(
            employee_id,
            policy["id"],
            today,
            projection_date,
        )
        accrual_amount = accruals.total_remaining_accrual
        
        # Scenario deduction
        scenario_deduction = 0.0
        if scenario and (not policy_id or policy["id"] == policy_id):
            scenario_deduction = scenario.days_to_request
        
        # Projected balance
        projected = current + accrual_amount - scenario_deduction
        
        # Check for negative
        will_be_negative = projected < 0
        shortfall = abs(projected) if will_be_negative else 0
        can_accommodate = not will_be_negative
        
        if will_be_negative:
            warnings.append(f"{policy['name']} will be negative by {shortfall:.1f} days")
        
        projected_balances.append(ProjectedBalanceDetail(
            policy_id=policy["id"],
            policy_name=policy["name"],
            current_balance=round(current, 2),
            projection_date=projection_date,
            projected_balance=round(projected, 2),
            scheduled_accruals=round(accrual_amount, 2),
            pending_deductions=round(pending_impact, 2),
            scenario_deductions=round(scenario_deduction, 2),
            will_be_negative=will_be_negative,
            shortfall=round(shortfall, 2),
            can_accommodate_scenario=can_accommodate,
        ))
        
        total_projected += projected
        total_accruals += accrual_amount
    
    # Add recommendations
    if any(p.will_be_negative for p in projected_balances):
        recommendations.append("Consider reducing request days to maintain positive balance")
        recommendations.append("Wait for additional accruals before submitting request")
    
    if total_projected > 30:
        recommendations.append("Consider using some balance before year-end to avoid losing carryover")
    
    return BalanceProjectionResponse(
        employee_id=employee_id,
        employee_name=current_user["name"],
        projection_date=projection_date,
        scenario_applied=scenario,
        projected_balances=projected_balances,
        total_projected_balance=round(total_projected, 2),
        total_scheduled_accruals=round(total_accruals, 2),
        recommendations=recommendations,
        warnings=warnings,
        calculated_at=datetime.utcnow(),
    )


