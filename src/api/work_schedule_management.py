"""API endpoints for work schedule management."""

import logging
import uuid
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.schemas.work_schedule import (
    CreateWorkScheduleRequest,
    ScheduleTypeEnum,
    UpdateWorkScheduleRequest,
    WorkScheduleCreateResponse,
    WorkScheduleDeleteResponse,
    WorkScheduleListResponse,
    WorkScheduleResponse,
    WorkScheduleUpdateResponse,
)
from src.services.work_schedule_service import WorkScheduleService
from src.utils.auth import CurrentUser, UserRole, get_mock_current_user

logger = logging.getLogger(__name__)


# =============================================================================
# Router Setup
# =============================================================================

work_schedule_router = APIRouter(
    prefix="/api/organization/work-schedules",
    tags=["Work Schedule Management"],
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
    
    roles = [UserRole.HR_MANAGER]  # Schedule management requires HR role
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


def get_schedule_service(
    session: Annotated[Session, Depends(get_db)],
) -> WorkScheduleService:
    """Get work schedule service instance."""
    return WorkScheduleService(session)


def require_schedule_admin(current_user: CurrentUser) -> CurrentUser:
    """Require HR or Admin role for schedule management."""
    if not any(role in current_user.roles for role in [UserRole.HR_MANAGER, UserRole.ADMIN]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="HR or Admin role required for schedule management",
        )
    return current_user


# =============================================================================
# Endpoints
# =============================================================================

@work_schedule_router.get(
    "",
    response_model=WorkScheduleListResponse,
    summary="List work schedules",
    description="""
    Get work schedule templates with working patterns and employee assignments.
    
    **Filtering Options:**
    - schedule_type: Filter by schedule type (standard, shift, compressed, etc.)
    - min_hours: Minimum weekly hours
    - max_hours: Maximum weekly hours
    - is_active: Filter by active/inactive status
    - has_assignments: Filter by whether employees are assigned
    
    **Response Includes:**
    - Complete schedule configuration
    - Working day patterns
    - Break schedules
    - Employee assignment counts
    - Labor law compliance status
    
    **Access Control:**
    - All authenticated users can view schedules
    - HR/Admin required for modification operations
    """,
    responses={
        200: {"description": "Schedules retrieved successfully"},
        401: {"description": "Authentication required"},
    },
)
async def list_work_schedules(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[WorkScheduleService, Depends(get_schedule_service)],
    schedule_type: Annotated[
        Optional[ScheduleTypeEnum],
        Query(description="Filter by schedule type"),
    ] = None,
    min_hours: Annotated[
        Optional[float],
        Query(ge=0, le=168, description="Minimum weekly hours"),
    ] = None,
    max_hours: Annotated[
        Optional[float],
        Query(ge=0, le=168, description="Maximum weekly hours"),
    ] = None,
    is_active: Annotated[
        Optional[bool],
        Query(description="Filter by active status"),
    ] = None,
    has_assignments: Annotated[
        Optional[bool],
        Query(description="Filter by employee assignment status"),
    ] = None,
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Page size")] = 20,
) -> WorkScheduleListResponse:
    """
    List work schedules with filtering and employee assignment information.
    """
    try:
        schedules, total = service.list_schedules(
            schedule_type=schedule_type.value if schedule_type else None,
            min_hours=min_hours,
            max_hours=max_hours,
            is_active=is_active,
            has_assignments=has_assignments,
            page=page,
            page_size=page_size,
        )
        
        # Build responses
        schedule_responses = [
            service.build_schedule_response(s) for s in schedules
        ]
        
        # Calculate summary
        total_employees = sum(s.assignments.active_assigned for s in schedule_responses)
        type_counts = {}
        for s in schedule_responses:
            type_name = s.schedule_type.value
            type_counts[type_name] = type_counts.get(type_name, 0) + 1
        
        logger.info(
            f"Listed {len(schedule_responses)} work schedules "
            f"for employee {current_user.employee_id}"
        )
        
        return WorkScheduleListResponse(
            schedules=schedule_responses,
            total=total,
            page=page,
            page_size=page_size,
            total_employees_scheduled=total_employees,
            schedule_type_counts=type_counts,
        )
        
    except Exception as e:
        logger.exception(f"Error listing work schedules: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while listing work schedules",
        )


@work_schedule_router.get(
    "/{schedule_id}",
    response_model=WorkScheduleResponse,
    summary="Get work schedule details",
    description="Get complete details for a specific work schedule.",
    responses={
        200: {"description": "Schedule retrieved successfully"},
        401: {"description": "Authentication required"},
        404: {"description": "Schedule not found"},
    },
)
async def get_work_schedule(
    schedule_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[WorkScheduleService, Depends(get_schedule_service)],
) -> WorkScheduleResponse:
    """Get a work schedule by ID."""
    schedule = service.get_schedule(schedule_id)
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule {schedule_id} not found",
        )
    
    return service.build_schedule_response(schedule)


@work_schedule_router.post(
    "",
    response_model=WorkScheduleCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create work schedule",
    description="""
    Create a new work schedule template.
    
    **Validation:**
    - Working hours verified against organizational limits
    - Break schedules validated for regulatory compliance
    - Labor law compliance checking performed
    
    **Labor Law Compliance:**
    - Maximum daily hours (typically 10)
    - Maximum weekly hours (typically 48)
    - Minimum break requirements
    - Jurisdiction-specific rules
    
    **Configuration Options:**
    - Schedule type (standard, shift, compressed, flexible, etc.)
    - Working hours and days
    - Break schedules
    - Overtime eligibility
    - Weekend work permissions
    - Location/department applicability
    """,
    responses={
        201: {"description": "Schedule created successfully"},
        400: {"description": "Validation error or labor law violation"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
async def create_work_schedule(
    request_body: CreateWorkScheduleRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[WorkScheduleService, Depends(get_schedule_service)],
) -> WorkScheduleCreateResponse:
    """
    Create a new work schedule with compliance validation.
    """
    require_schedule_admin(current_user)
    
    try:
        schedule, compliance = service.create_schedule(
            request=request_body,
            current_user=current_user,
        )
        
        logger.info(
            f"Created work schedule {schedule.id}: {schedule.name} "
            f"by employee {current_user.employee_id}"
        )
        
        return WorkScheduleCreateResponse(
            schedule=service.build_schedule_response(schedule),
            compliance_validated=compliance.is_compliant,
            message=f"Work schedule '{schedule.name}' created successfully",
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.exception(f"Error creating work schedule: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating the work schedule",
        )


@work_schedule_router.put(
    "/{schedule_id}",
    response_model=WorkScheduleUpdateResponse,
    summary="Update work schedule",
    description="""
    Update a work schedule with impact assessment.
    
    **Validation:**
    - Changes validated against labor law requirements
    - Impact assessment on assigned employees
    - Schedule transition procedures evaluated
    
    **Impact Assessment:**
    - Number of affected employees
    - Affected departments
    - Transition requirements
    - Risk level evaluation
    
    **Change Management:**
    - Optional transition date for phased rollout
    - Employee notification control
    - Change reason documentation
    """,
    responses={
        200: {"description": "Schedule updated successfully"},
        400: {"description": "Validation error or labor law violation"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Schedule not found"},
    },
)
async def update_work_schedule(
    schedule_id: int,
    request_body: UpdateWorkScheduleRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[WorkScheduleService, Depends(get_schedule_service)],
) -> WorkScheduleUpdateResponse:
    """
    Update a work schedule with validation and impact assessment.
    """
    require_schedule_admin(current_user)
    
    try:
        schedule, impact = service.update_schedule(
            schedule_id=schedule_id,
            request=request_body,
            current_user=current_user,
        )
        
        # Count notifications (mock)
        notifications = impact.employees_affected if request_body.notify_employees else 0
        
        logger.info(
            f"Updated work schedule {schedule_id} "
            f"by employee {current_user.employee_id}, "
            f"{impact.employees_affected} employees affected"
        )
        
        return WorkScheduleUpdateResponse(
            schedule=service.build_schedule_response(schedule),
            impact_assessment=impact,
            notifications_sent=notifications,
            message=f"Work schedule '{schedule.name}' updated successfully",
        )
        
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )
    except Exception as e:
        logger.exception(f"Error updating work schedule: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while updating the work schedule",
        )


@work_schedule_router.delete(
    "/{schedule_id}",
    response_model=WorkScheduleDeleteResponse,
    summary="Deactivate work schedule",
    description="""
    Deactivate a work schedule (soft delete).
    
    **Validation:**
    - Checks for employees currently assigned
    - Identifies reassignment requirements
    - Suggests alternative schedules
    
    **Response:**
    - Number of affected employees
    - Whether reassignment is required
    - Suggested alternative schedules
    - Transition guidance
    
    **Note:**
    Schedules with assigned employees can still be deactivated,
    but employees must be reassigned to maintain valid configurations.
    """,
    responses={
        200: {"description": "Schedule deactivated successfully"},
        400: {"description": "Schedule already inactive"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Schedule not found"},
    },
)
async def delete_work_schedule(
    schedule_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[WorkScheduleService, Depends(get_schedule_service)],
) -> WorkScheduleDeleteResponse:
    """
    Deactivate a work schedule with reassignment validation.
    """
    require_schedule_admin(current_user)
    
    try:
        schedule, affected, alternatives = service.deactivate_schedule(
            schedule_id=schedule_id,
            current_user=current_user,
        )
        
        # Build transition guidance
        if affected > 0:
            guidance = (
                f"{affected} employees need to be reassigned to a new schedule. "
                "Review the suggested alternatives or assign a custom schedule."
            )
        else:
            guidance = "No employees affected. Schedule deactivated successfully."
        
        logger.info(
            f"Deactivated work schedule {schedule_id} "
            f"by employee {current_user.employee_id}, "
            f"{affected} employees affected"
        )
        
        return WorkScheduleDeleteResponse(
            schedule_id=schedule_id,
            deactivated=True,
            employees_affected=affected,
            reassignment_required=affected > 0,
            suggested_alternatives=alternatives,
            transition_guidance=guidance,
            message=f"Work schedule deactivated. {affected} employees require reassignment.",
        )
        
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )
    except Exception as e:
        logger.exception(f"Error deactivating work schedule: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while deactivating the work schedule",
        )


@work_schedule_router.get(
    "/{schedule_id}/compliance",
    summary="Check schedule compliance",
    description="Validate a schedule against labor law requirements.",
    responses={
        200: {"description": "Compliance check completed"},
        404: {"description": "Schedule not found"},
    },
)
async def check_schedule_compliance(
    schedule_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[WorkScheduleService, Depends(get_schedule_service)],
    jurisdiction: Annotated[str, Query(description="Jurisdiction code")] = "default",
) -> dict:
    """Check labor law compliance for a schedule."""
    schedule = service.get_schedule(schedule_id)
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule {schedule_id} not found",
        )
    
    hours_per_day = float(schedule.hours_per_week) / max(schedule.days_per_week, 1)
    
    compliance = service.validate_labor_compliance(
        hours_per_week=float(schedule.hours_per_week),
        hours_per_day=hours_per_day,
        break_minutes=schedule.break_duration_minutes,
        jurisdiction=jurisdiction,
    )
    
    return {
        "schedule_id": schedule_id,
        "schedule_name": schedule.name,
        "compliance": compliance.dict(),
    }


@work_schedule_router.get(
    "/{schedule_id}/assignments",
    summary="Get schedule assignments",
    description="Get details about employees assigned to this schedule.",
    responses={
        200: {"description": "Assignments retrieved"},
        404: {"description": "Schedule not found"},
    },
)
async def get_schedule_assignments(
    schedule_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[WorkScheduleService, Depends(get_schedule_service)],
) -> dict:
    """Get employee assignment details for a schedule."""
    schedule = service.get_schedule(schedule_id)
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule {schedule_id} not found",
        )
    
    summary = service.get_assignment_summary(schedule_id)
    
    return {
        "schedule_id": schedule_id,
        "schedule_name": schedule.name,
        "assignments": summary.dict(),
    }

