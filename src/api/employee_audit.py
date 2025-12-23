"""API endpoints for employee audit trail and activity."""

import uuid
from datetime import datetime
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Header, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.models.employee_audit_trail import ChangeType
from src.schemas.employee_audit import (
    ActivityEntry,
    ActivityFilters,
    ActivityResponse,
    ActivityType,
    AuditTrailEntry,
    AuditTrailResponse,
    AuditTrailSummary,
)
from src.services.activity_service import ActivityService
from src.services.audit_trail_service import AuditTrailService
from src.utils.auth import CurrentUser, UserRole, get_mock_current_user
from src.utils.errors import APIError


# =============================================================================
# Response Models
# =============================================================================

class AuditTrailResponseWrapper(BaseModel):
    """Response wrapper for audit trail."""
    
    data: AuditTrailResponse


class AuditSummaryResponseWrapper(BaseModel):
    """Response wrapper for audit summary."""
    
    data: AuditTrailSummary


class ActivityResponseWrapper(BaseModel):
    """Response wrapper for activity."""
    
    data: ActivityResponse


class FieldHistoryResponseWrapper(BaseModel):
    """Response wrapper for field history."""
    
    data: List[AuditTrailEntry]


# =============================================================================
# Dependency Injection
# =============================================================================

def get_audit_service(
    session: Annotated[Session, Depends(get_db)],
) -> AuditTrailService:
    """Get audit trail service instance."""
    return AuditTrailService(session)


def get_activity_service(
    session: Annotated[Session, Depends(get_db)],
) -> ActivityService:
    """Get activity service instance."""
    return ActivityService(session)


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
    
    roles = [UserRole.ADMIN]  # Default for development
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

employee_audit_router = APIRouter(
    prefix="/api/employees",
    tags=["Employee Audit & Activity"],
)


# =============================================================================
# Audit Trail Endpoints
# =============================================================================

@employee_audit_router.get(
    "/{employee_id}/audit-trail",
    response_model=AuditTrailResponseWrapper,
    summary="Get Audit Trail",
    description="Get complete audit trail for an employee with field-level change history.",
)
async def get_audit_trail(
    employee_id: int,
    service: Annotated[AuditTrailService, Depends(get_audit_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 50,
    change_type: Annotated[Optional[str], Query(description="Filter by change type")] = None,
    field_name: Annotated[Optional[str], Query(description="Filter by field name")] = None,
    date_from: Annotated[Optional[datetime], Query(description="Filter from date")] = None,
    date_to: Annotated[Optional[datetime], Query(description="Filter to date")] = None,
    actor_id: Annotated[Optional[str], Query(description="Filter by actor user ID")] = None,
) -> AuditTrailResponseWrapper:
    """
    Get audit trail for an employee.
    
    - Returns chronological change history showing what changed, who made changes, and when
    - Includes field-level changes with before and after values
    - Distinguishes between automated and manual changes
    - Applies access controls based on user role
    - Supports filtering by change type, field, date range, and actor
    """
    # Parse change type
    parsed_change_type = None
    if change_type:
        try:
            parsed_change_type = ChangeType(change_type)
        except ValueError:
            pass
    
    # Parse actor ID
    parsed_actor_id = None
    if actor_id:
        try:
            parsed_actor_id = uuid.UUID(actor_id)
        except ValueError:
            pass
    
    result = service.get_audit_trail(
        employee_id=employee_id,
        current_user=current_user,
        page=page,
        page_size=page_size,
        change_type=parsed_change_type,
        field_name=field_name,
        date_from=date_from,
        date_to=date_to,
        actor_user_id=parsed_actor_id,
    )
    
    return AuditTrailResponseWrapper(data=result)


@employee_audit_router.get(
    "/{employee_id}/audit-trail/summary",
    response_model=AuditSummaryResponseWrapper,
    summary="Get Audit Trail Summary",
    description="Get summary statistics for an employee's audit trail.",
)
async def get_audit_summary(
    employee_id: int,
    service: Annotated[AuditTrailService, Depends(get_audit_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> AuditSummaryResponseWrapper:
    """
    Get audit trail summary for an employee.
    
    - Returns total changes, date ranges, and statistics
    - Includes change counts by type and most changed fields
    - Shows number of unique actors who made changes
    """
    result = service.get_audit_summary(
        employee_id=employee_id,
        current_user=current_user,
    )
    
    return AuditSummaryResponseWrapper(data=result)


@employee_audit_router.get(
    "/{employee_id}/audit-trail/field/{field_name}",
    response_model=FieldHistoryResponseWrapper,
    summary="Get Field History",
    description="Get change history for a specific field.",
)
async def get_field_history(
    employee_id: int,
    field_name: str,
    service: Annotated[AuditTrailService, Depends(get_audit_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=100, description="Max entries")] = 20,
) -> FieldHistoryResponseWrapper:
    """
    Get change history for a specific field.
    
    - Returns chronological history of changes to a single field
    - Useful for tracking specific attribute changes over time
    """
    result = service.get_field_history(
        employee_id=employee_id,
        field_name=field_name,
        current_user=current_user,
        limit=limit,
    )
    
    return FieldHistoryResponseWrapper(data=result)


# =============================================================================
# Activity Endpoints
# =============================================================================

@employee_audit_router.get(
    "/{employee_id}/activity",
    response_model=ActivityResponseWrapper,
    summary="Get Activity Feed",
    description="Get recent activity summary for an employee.",
)
async def get_activity(
    employee_id: int,
    service: Annotated[ActivityService, Depends(get_activity_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 50,
    activity_types: Annotated[Optional[str], Query(description="Comma-separated activity types")] = None,
    date_from: Annotated[Optional[datetime], Query(description="Filter from date")] = None,
    date_to: Annotated[Optional[datetime], Query(description="Filter to date")] = None,
    include_automated: Annotated[bool, Query(description="Include automated activities")] = True,
) -> ActivityResponseWrapper:
    """
    Get activity feed for an employee.
    
    - Returns recent activity including profile updates, status changes, and system interactions
    - Supports filtering by activity type and date range
    - Includes relevant context and links to related operations
    - Applies access controls based on user role
    """
    # Parse activity types
    parsed_types = None
    if activity_types:
        try:
            parsed_types = [
                ActivityType(t.strip())
                for t in activity_types.split(",")
                if t.strip()
            ]
        except ValueError:
            pass
    
    filters = ActivityFilters(
        activity_types=parsed_types,
        date_from=date_from,
        date_to=date_to,
        include_automated=include_automated,
    )
    
    result = service.get_employee_activities(
        employee_id=employee_id,
        current_user=current_user,
        filters=filters,
        page=page,
        page_size=page_size,
    )
    
    return ActivityResponseWrapper(data=result)


# =============================================================================
# Exception Handler
# =============================================================================

async def audit_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """Handle API errors for audit endpoints."""
    response = exc.to_response()
    return JSONResponse(
        status_code=response.status_code,
        content=response.to_dict(),
    )

