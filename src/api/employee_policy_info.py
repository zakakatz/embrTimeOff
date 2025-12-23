"""API endpoints for employee time-off policy information."""

import logging
import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.schemas.employee_policy_info import (
    EmployeePoliciesListResponse,
    PolicyConstraintsResponse,
)
from src.services.policy_engine_service import PolicyEngineService
from src.utils.auth import CurrentUser, UserRole, get_mock_current_user

logger = logging.getLogger(__name__)


# =============================================================================
# Router Setup
# =============================================================================

employee_policy_info_router = APIRouter(
    prefix="/api/time-off/policies",
    tags=["Employee Policy Information"],
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
    """
    Get current user from request headers.
    
    In production, this would verify JWT tokens or session cookies.
    For development, it uses headers to simulate different users/roles.
    """
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


def get_policy_engine(
    session: Annotated[Session, Depends(get_db)],
) -> PolicyEngineService:
    """Get policy engine service instance."""
    return PolicyEngineService(session)


# =============================================================================
# Endpoints
# =============================================================================

@employee_policy_info_router.get(
    "/employee",
    response_model=EmployeePoliciesListResponse,
    summary="Get applicable policies for employee",
    description="""
    Returns all applicable time-off policies for the authenticated employee.
    
    This endpoint evaluates policy eligibility based on:
    - Employee's location
    - Employment type (full-time, part-time, contractor)
    - Tenure/length of service
    - Department
    - Any custom eligibility rules defined in the policy
    
    The response includes:
    - Complete policy details with accrual rates and rules
    - Current balances and pending request totals
    - Balance caps and carryover rules
    - Blackout dates affecting the employee
    - Approval requirements
    - Human-readable descriptions suitable for UI display
    
    **Role-Based Access:**
    - Employees can only see policies applicable to them
    - Managers can view their direct reports' policies (not implemented in this endpoint)
    - HR/Admin can view all employee policies (not implemented in this endpoint)
    """,
    responses={
        200: {
            "description": "Successfully retrieved applicable policies",
            "content": {
                "application/json": {
                    "example": {
                        "employee_id": 123,
                        "employee_name": "John Smith",
                        "policies": [
                            {
                                "id": 1,
                                "name": "Standard Vacation",
                                "code": "VAC-STD",
                                "policy_type": "vacation",
                                "employee_eligible": True,
                                "current_balance": 12.5,
                                "available_balance": 10.5,
                            }
                        ],
                        "total_policies": 3,
                        "total_available_days": 22.5,
                    }
                }
            },
        },
        401: {"description": "Authentication required"},
        404: {"description": "Employee not found"},
    },
)
async def get_employee_policies(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    policy_engine: Annotated[PolicyEngineService, Depends(get_policy_engine)],
) -> EmployeePoliciesListResponse:
    """
    Get all applicable time-off policies for the authenticated employee.
    
    Returns comprehensive policy information including:
    - Accrual rates and methods
    - Balance caps and carryover rules
    - Blackout dates
    - Approval requirements
    - Current balances and availability
    
    The response is formatted with human-readable descriptions
    suitable for direct display in the user interface.
    """
    # Validate employee is authenticated
    if not current_user.employee_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Employee authentication required to access policy information",
        )
    
    try:
        response = policy_engine.get_employee_policies(
            employee_id=current_user.employee_id,
        )
        
        logger.info(
            f"Retrieved {response.total_policies} policies for employee {current_user.employee_id}"
        )
        
        return response
        
    except ValueError as e:
        logger.error(f"Employee not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.exception(f"Error retrieving employee policies: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving policy information",
        )


@employee_policy_info_router.get(
    "/{policy_id}/constraints",
    response_model=PolicyConstraintsResponse,
    summary="Get policy constraints and rules",
    description="""
    Returns detailed constraint information for a specific time-off policy.
    
    This endpoint provides all the information needed to guide employees
    when submitting time-off requests, including:
    
    **Blackout Dates:**
    - Periods when time-off cannot be taken
    - Whether exceptions are possible
    - How to request exceptions
    
    **Notice Requirements:**
    - Required advance notice by request duration
    - Minimum and maximum request lengths
    
    **Usage Restrictions:**
    - Minimum/maximum days per request
    - Consecutive day limits
    - Balance requirements
    
    **Documentation Requirements:**
    - Required documents by policy type
    - When documentation is needed
    - How to submit documentation
    
    **Approval Information:**
    - Approval chain for the employee
    - Escalation rules
    - Expected approval timeline
    
    **UI Guidance:**
    - Warnings about upcoming blackouts
    - Tips for successful requests
    - Informational messages
    
    **Role-Based Access:**
    - Employees can only access constraints for policies they are eligible for
    - The response is personalized based on the employee's attributes
    """,
    responses={
        200: {
            "description": "Successfully retrieved policy constraints",
            "content": {
                "application/json": {
                    "example": {
                        "policy_id": 1,
                        "policy_name": "Standard Vacation",
                        "blackout_periods": [
                            {
                                "name": "Year-End Close",
                                "start_date": "2024-12-23",
                                "end_date": "2025-01-02",
                            }
                        ],
                        "notice_requirements": [
                            {
                                "min_days": 1,
                                "max_days": 3,
                                "notice_required": 3,
                            }
                        ],
                        "approval_chain": ["Direct Manager", "Department Head"],
                    }
                }
            },
        },
        401: {"description": "Authentication required"},
        403: {"description": "Not authorized to view this policy"},
        404: {"description": "Policy not found"},
    },
)
async def get_policy_constraints(
    policy_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    policy_engine: Annotated[PolicyEngineService, Depends(get_policy_engine)],
) -> PolicyConstraintsResponse:
    """
    Get detailed constraint information for a specific policy.
    
    Returns all constraints, rules, and guidance needed to help
    employees make informed decisions when requesting time-off.
    
    The response includes:
    - Blackout dates and periods
    - Notice requirements by duration
    - Usage restrictions
    - Documentation requirements
    - Approval chain specific to the employee
    - UI warnings and helpful tips
    """
    # Validate employee is authenticated
    if not current_user.employee_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Employee authentication required to access policy constraints",
        )
    
    try:
        response = policy_engine.get_policy_constraints(
            policy_id=policy_id,
            employee_id=current_user.employee_id,
        )
        
        logger.info(
            f"Retrieved constraints for policy {policy_id} for employee {current_user.employee_id}"
        )
        
        return response
        
    except ValueError as e:
        error_message = str(e)
        if "Policy" in error_message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Policy {policy_id} not found",
            )
        elif "Employee" in error_message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Employee not found",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_message,
            )
    except Exception as e:
        logger.exception(f"Error retrieving policy constraints: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving policy constraints",
        )


@employee_policy_info_router.get(
    "/{policy_id}/eligibility",
    summary="Check employee eligibility for a policy",
    description="""
    Quick check to determine if the authenticated employee is eligible
    for a specific time-off policy.
    
    Returns:
    - Whether the employee is eligible
    - Status message explaining eligibility
    - If in waiting period, when eligibility begins
    - Any restrictions that apply
    """,
    responses={
        200: {
            "description": "Eligibility check result",
            "content": {
                "application/json": {
                    "example": {
                        "policy_id": 1,
                        "policy_name": "Standard Vacation",
                        "is_eligible": True,
                        "status": "Eligible",
                        "eligibility_start_date": "2024-01-15",
                        "waiting_period_remaining": None,
                        "restrictions": [],
                    }
                }
            },
        },
        401: {"description": "Authentication required"},
        404: {"description": "Policy not found"},
    },
)
async def check_policy_eligibility(
    policy_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    policy_engine: Annotated[PolicyEngineService, Depends(get_policy_engine)],
    session: Annotated[Session, Depends(get_db)],
) -> dict:
    """
    Quick eligibility check for a specific policy.
    
    Useful for UI validation before showing request form.
    """
    from src.models.employee import Employee
    from src.models.time_off_policy import TimeOffPolicy
    
    # Validate employee is authenticated
    if not current_user.employee_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Employee authentication required",
        )
    
    # Get employee and policy
    employee = session.get(Employee, current_user.employee_id)
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found",
        )
    
    policy = session.get(TimeOffPolicy, policy_id)
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy {policy_id} not found",
        )
    
    # Evaluate eligibility
    is_eligible, status_message, eligibility_date, waiting_remaining = (
        policy_engine.evaluate_employee_eligibility(employee, policy)
    )
    
    # Build restrictions list
    restrictions = []
    if not is_eligible:
        restrictions.append(status_message)
    
    return {
        "policy_id": policy_id,
        "policy_name": policy.name,
        "is_eligible": is_eligible,
        "status": status_message,
        "eligibility_start_date": eligibility_date.isoformat() if eligibility_date else None,
        "waiting_period_remaining": waiting_remaining,
        "restrictions": restrictions,
    }

