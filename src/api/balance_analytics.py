"""API endpoints for balance analytics and reconciliation."""

import logging
import uuid
from datetime import date
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.schemas.balance_analytics import (
    BalanceTrendResponse,
    BalanceUtilizationResponse,
    ReconciliationHistoryResponse,
    ReconciliationRequest,
    ReconciliationResult,
)
from src.services.balance_analytics_service import BalanceAnalyticsService
from src.utils.auth import CurrentUser, UserRole, get_mock_current_user

logger = logging.getLogger(__name__)


# =============================================================================
# Router Setup
# =============================================================================

balance_analytics_router = APIRouter(
    prefix="/api/balances",
    tags=["Balance Analytics"],
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
    
    roles = [UserRole.HR_MANAGER]  # Analytics typically require HR/Admin
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


def get_analytics_service(
    session: Annotated[Session, Depends(get_db)],
) -> BalanceAnalyticsService:
    """Get balance analytics service instance."""
    return BalanceAnalyticsService(session)


def require_analytics_access(current_user: CurrentUser) -> CurrentUser:
    """Require HR or Admin role for analytics access."""
    if not any(role in current_user.roles for role in [UserRole.HR_MANAGER, UserRole.ADMIN]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="HR or Admin role required for analytics access",
        )
    return current_user


# =============================================================================
# Trend Analytics Endpoints
# =============================================================================

@balance_analytics_router.get(
    "/analytics/trends",
    response_model=BalanceTrendResponse,
    summary="Analyze balance trends",
    description="""
    Analyze historical balance data with comprehensive trend identification.
    
    **Trend Analysis Features:**
    - Historical balance data aggregation by period
    - Trend direction identification (increasing, decreasing, stable, seasonal)
    - Magnitude and confidence assessment
    - Multi-period comparison (recent vs. overall)
    
    **Seasonal Analysis:**
    - Pattern recognition (summer peak, year-end, holiday-driven)
    - Peak and trough month identification
    - Seasonal variation quantification
    
    **Predictive Forecasting:**
    - Balance projections with confidence intervals
    - Configurable forecast horizon
    - Trend-adjusted predictions
    
    **Strategic Insights:**
    - Actionable insights based on identified patterns
    - Workforce planning recommendations
    - Data quality assessment
    
    **Use Cases:**
    - Strategic workforce planning
    - Policy optimization decisions
    - Budget forecasting
    - Coverage planning
    """,
    responses={
        200: {"description": "Trend analysis completed successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
async def analyze_balance_trends(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[BalanceAnalyticsService, Depends(get_analytics_service)],
    policy_id: Annotated[
        Optional[int],
        Query(description="Filter by specific policy"),
    ] = None,
    department_id: Annotated[
        Optional[int],
        Query(description="Filter by department"),
    ] = None,
    start_date: Annotated[
        Optional[date],
        Query(description="Analysis start date (defaults to 12 months ago)"),
    ] = None,
    end_date: Annotated[
        Optional[date],
        Query(description="Analysis end date (defaults to today)"),
    ] = None,
    forecast_days: Annotated[
        int,
        Query(ge=30, le=365, description="Forecast horizon in days"),
    ] = 90,
) -> BalanceTrendResponse:
    """
    Analyze historical balance data with trend identification.
    
    Performs seasonal analysis with pattern recognition and returns
    predictive forecasting with confidence intervals for strategic
    workforce planning.
    """
    require_analytics_access(current_user)
    
    try:
        response = service.analyze_balance_trends(
            current_user=current_user,
            policy_id=policy_id,
            department_id=department_id,
            start_date=start_date,
            end_date=end_date,
            forecast_days=forecast_days,
        )
        
        logger.info(
            f"Trend analysis completed for {len(response.historical_data)} periods "
            f"by employee {current_user.employee_id}"
        )
        
        return response
        
    except Exception as e:
        logger.exception(f"Error analyzing balance trends: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while analyzing balance trends",
        )


# =============================================================================
# Utilization Analytics Endpoints
# =============================================================================

@balance_analytics_router.get(
    "/analytics/utilization",
    response_model=BalanceUtilizationResponse,
    summary="Analyze balance utilization",
    description="""
    Calculate comprehensive utilization rates with statistical analysis.
    
    **Utilization Metrics:**
    - Overall company utilization rate
    - Per-policy utilization breakdown
    - Accrual efficiency rates
    - Carryover and forfeit rates
    - Comparative metrics (vs. average, vs. last period)
    - Percentile rankings
    
    **Department Analysis:**
    - Utilization by department
    - Cross-department comparisons
    - Employee count and totals
    
    **Policy Effectiveness:**
    - Overall effectiveness scores
    - Employee satisfaction proxy metrics
    - Administrative efficiency
    - Identified issues and suggestions
    
    **Optimization Recommendations:**
    - Prioritized recommendations
    - Implementation guidance
    - Expected impact analysis
    - Effort estimates
    
    **Statistical Analysis:**
    - Utilization distribution
    - Variance analysis
    - Trend comparisons
    """,
    responses={
        200: {"description": "Utilization analysis completed successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
async def analyze_utilization(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[BalanceAnalyticsService, Depends(get_analytics_service)],
    start_date: Annotated[
        Optional[date],
        Query(description="Analysis start date (defaults to start of year)"),
    ] = None,
    end_date: Annotated[
        Optional[date],
        Query(description="Analysis end date (defaults to today)"),
    ] = None,
    department_ids: Annotated[
        Optional[str],
        Query(description="Comma-separated department IDs"),
    ] = None,
    policy_ids: Annotated[
        Optional[str],
        Query(description="Comma-separated policy IDs"),
    ] = None,
) -> BalanceUtilizationResponse:
    """
    Calculate utilization rates with statistical analysis.
    
    Evaluates policy effectiveness with comparative metrics and returns
    optimization recommendations with implementation guidance.
    """
    require_analytics_access(current_user)
    
    # Parse comma-separated IDs
    dept_list = None
    if department_ids:
        dept_list = [int(x.strip()) for x in department_ids.split(",")]
    
    policy_list = None
    if policy_ids:
        policy_list = [int(x.strip()) for x in policy_ids.split(",")]
    
    try:
        response = service.analyze_utilization(
            current_user=current_user,
            start_date=start_date,
            end_date=end_date,
            department_ids=dept_list,
            policy_ids=policy_list,
        )
        
        logger.info(
            f"Utilization analysis completed: {response.company_utilization_rate}% "
            f"across {response.total_employees_analyzed} employees "
            f"by employee {current_user.employee_id}"
        )
        
        return response
        
    except Exception as e:
        logger.exception(f"Error analyzing utilization: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while analyzing utilization",
        )


# =============================================================================
# Reconciliation Endpoints
# =============================================================================

@balance_analytics_router.post(
    "/reconciliation",
    response_model=ReconciliationResult,
    summary="Perform balance reconciliation",
    description="""
    Perform comprehensive balance reconciliation with discrepancy identification.
    
    **Discrepancy Identification:**
    - Comprehensive validation of balance calculations
    - Accrual error detection
    - Usage mismatch identification
    - Carryover calculation verification
    - Policy change impact analysis
    
    **Correction Processing:**
    - Automatic corrections for minor discrepancies
    - Approval workflow for significant corrections
    - Configurable thresholds
    - Detailed audit trail generation
    
    **Reconciliation Scopes:**
    - all: All employees and policies
    - department: Specific departments
    - policy: Specific policies
    - employee: Specific employees
    
    **Audit Trail:**
    - Timestamps and user information
    - Before/after values
    - Correction reasons and notes
    - Full audit compliance
    
    **Configuration:**
    - auto_correct: Enable automatic corrections
    - correction_threshold: Max amount for auto-correction
    - require_approval_above: Threshold requiring approval
    """,
    responses={
        200: {"description": "Reconciliation completed successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
        400: {"description": "Invalid reconciliation request"},
    },
)
async def perform_reconciliation(
    request_body: ReconciliationRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[BalanceAnalyticsService, Depends(get_analytics_service)],
) -> ReconciliationResult:
    """
    Perform balance reconciliation with comprehensive validation.
    
    Identifies discrepancies through validation, processes corrections
    with appropriate authorization, and maintains reconciliation records
    with detailed documentation and audit trails.
    """
    require_analytics_access(current_user)
    
    try:
        response = service.perform_reconciliation(
            request=request_body,
            current_user=current_user,
        )
        
        logger.info(
            f"Reconciliation {response.reconciliation_id} completed: "
            f"{response.discrepancies_found} discrepancies, "
            f"{response.corrections_applied} corrections "
            f"by employee {current_user.employee_id}"
        )
        
        return response
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.exception(f"Error performing reconciliation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during reconciliation",
        )


@balance_analytics_router.get(
    "/reconciliation/history",
    response_model=ReconciliationHistoryResponse,
    summary="Get reconciliation history",
    description="""
    Retrieve reconciliation history with detailed correction information.
    
    **History Information:**
    - Past reconciliation runs
    - Scope and date information
    - Discrepancies found and corrections applied
    - Initiator and timing details
    
    **Accuracy Assessment:**
    - Overall accuracy score
    - Component accuracy (accrual, usage, carryover)
    - Accuracy trend analysis
    - Common issues identification
    - Prevention recommendations
    
    **Trend Analysis:**
    - Reconciliation volume over time
    - Discrepancy trends by month
    - Discrepancy distribution by type
    - Resolution time metrics
    - Auto-correction rates
    
    **Comprehensive Reporting:**
    - Summary statistics
    - Trend visualization data
    - Actionable insights
    """,
    responses={
        200: {"description": "History retrieved successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
async def get_reconciliation_history(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[BalanceAnalyticsService, Depends(get_analytics_service)],
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Page size")] = 20,
    start_date: Annotated[
        Optional[date],
        Query(description="Filter history from this date"),
    ] = None,
    end_date: Annotated[
        Optional[date],
        Query(description="Filter history to this date"),
    ] = None,
) -> ReconciliationHistoryResponse:
    """
    Retrieve reconciliation history with audit trail analysis.
    
    Provides accuracy assessment with trend analysis and comprehensive
    reconciliation reporting for data integrity maintenance.
    """
    require_analytics_access(current_user)
    
    try:
        response = service.get_reconciliation_history(
            current_user=current_user,
            page=page,
            page_size=page_size,
            start_date=start_date,
            end_date=end_date,
        )
        
        logger.info(
            f"Reconciliation history retrieved: {response.total_entries} entries "
            f"by employee {current_user.employee_id}"
        )
        
        return response
        
    except Exception as e:
        logger.exception(f"Error retrieving reconciliation history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving reconciliation history",
        )


@balance_analytics_router.get(
    "/reconciliation/{reconciliation_id}",
    response_model=ReconciliationResult,
    summary="Get reconciliation details",
    description="Get detailed information about a specific reconciliation run.",
    responses={
        200: {"description": "Reconciliation details retrieved"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Reconciliation not found"},
    },
)
async def get_reconciliation_details(
    reconciliation_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[BalanceAnalyticsService, Depends(get_analytics_service)],
) -> ReconciliationResult:
    """Get details of a specific reconciliation run."""
    require_analytics_access(current_user)
    
    # In production, this would query the database
    # For now, return a mock result
    from src.schemas.balance_analytics import ReconciliationStatusEnum
    
    return ReconciliationResult(
        reconciliation_id=reconciliation_id,
        status=ReconciliationStatusEnum.COMPLETED,
        scope="all",
        as_of_date=date.today(),
        employees_analyzed=150,
        discrepancies_found=5,
        total_discrepancy_amount=3.5,
        corrections_applied=3,
        corrections_pending_approval=2,
        corrections_failed=0,
        discrepancies=[],
        applied_corrections=[],
        initiated_by="System",
        initiated_at=datetime.now(),
        completed_at=datetime.now(),
        summary="Reconciliation completed with 5 discrepancies found.",
        recommendations=["Review carryover calculations"],
    )


# Import datetime for the last endpoint
from datetime import datetime

