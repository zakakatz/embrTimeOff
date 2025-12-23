"""API endpoints for employee organizational relationships."""

import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Header, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.schemas.employee_org import (
    DirectReportsResponse,
    OrgChartResponse,
)
from src.services.employee_org_service import EmployeeOrgService
from src.utils.auth import CurrentUser, UserRole, get_mock_current_user
from src.utils.errors import APIError


# =============================================================================
# Response Models
# =============================================================================

class DirectReportsResponseWrapper(BaseModel):
    """Response wrapper for direct reports."""
    
    data: DirectReportsResponse


class OrgChartResponseWrapper(BaseModel):
    """Response wrapper for org chart."""
    
    data: OrgChartResponse


# =============================================================================
# Dependency Injection
# =============================================================================

def get_org_service(
    session: Annotated[Session, Depends(get_db)],
) -> EmployeeOrgService:
    """Get employee org service instance."""
    return EmployeeOrgService(session)


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

employee_org_router = APIRouter(
    prefix="/api/employees",
    tags=["Employee Organizational Relationships"],
)


# =============================================================================
# Direct Reports Endpoint
# =============================================================================

@employee_org_router.get(
    "/{employee_id}/direct-reports",
    response_model=DirectReportsResponseWrapper,
    summary="Get Direct Reports",
    description="Get direct reports for a manager, including complete team member profiles.",
)
async def get_direct_reports(
    employee_id: int,
    service: Annotated[EmployeeOrgService, Depends(get_org_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> DirectReportsResponseWrapper:
    """
    Get direct reports for a manager.
    
    - Returns complete team member profiles with organizational data
    - Validates requesting user has permission to view team information
    - Includes job titles, departments, and hire dates
    - Respects organizational hierarchy visibility rules
    """
    result = service.get_direct_reports(
        employee_id=employee_id,
        current_user=current_user,
    )
    return DirectReportsResponseWrapper(data=result)


# =============================================================================
# Org Chart Endpoint
# =============================================================================

@employee_org_router.get(
    "/{employee_id}/org-chart",
    response_model=OrgChartResponseWrapper,
    summary="Get Organizational Chart",
    description="Get organizational chart data showing reporting relationships.",
)
async def get_org_chart(
    employee_id: int,
    service: Annotated[EmployeeOrgService, Depends(get_org_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    depth: Annotated[int, Query(ge=1, le=5, description="Levels deep to traverse")] = 3,
) -> OrgChartResponseWrapper:
    """
    Get organizational chart data for an employee.
    
    - Shows reporting relationships up to specified depth (default 3 levels)
    - Includes manager chains, peer relationships, and direct report trees
    - Returns hierarchical data structure suitable for visualization
    - Respects access controls and organizational visibility rules
    - Includes job titles, departments, and reporting start dates
    """
    result = service.get_org_chart(
        employee_id=employee_id,
        current_user=current_user,
        depth=depth,
    )
    return OrgChartResponseWrapper(data=result)


# =============================================================================
# Exception Handler
# =============================================================================

async def org_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """Handle API errors for organizational endpoints."""
    response = exc.to_response()
    return JSONResponse(
        status_code=response.status_code,
        content=response.to_dict(),
    )

