"""API route definitions for employee endpoints."""

from datetime import date
from typing import Annotated, Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.employees.models import EmployeeCreateRequest, EmployeeUpdateRequest
from src.services.employee_service import EmployeeService
from src.utils.auth import CurrentUser, UserRole, get_mock_current_user
from src.utils.errors import APIError


# =============================================================================
# Request/Response Models for API
# =============================================================================

class TerminateEmployeeRequest(BaseModel):
    """Request body for employee termination."""
    
    termination_date: Optional[date] = Field(
        default=None,
        description="Date of termination. Defaults to today if not provided.",
    )
    reason: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Reason for termination.",
    )


class SuccessResponse(BaseModel):
    """Generic success response wrapper."""
    
    data: Dict[str, Any]
    message: Optional[str] = None


class DirectoryResponse(BaseModel):
    """Response for employee directory listing."""
    
    data: list
    pagination: Dict[str, Any]


class SearchRequest(BaseModel):
    """Request body for employee search."""
    
    query: str = Field(default="", description="Search query string")
    filters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Filter criteria (department, location, status, etc.)",
    )
    limit: int = Field(default=50, ge=1, le=200, description="Maximum results")
    fuzzy: bool = Field(default=True, description="Enable fuzzy matching")


class SearchResponse(BaseModel):
    """Response for employee search."""
    
    data: list
    total: int
    query: str


# =============================================================================
# Dependency Injection
# =============================================================================

def get_employee_service(
    session: Annotated[Session, Depends(get_db)],
) -> EmployeeService:
    """Get employee service instance."""
    return EmployeeService(session)


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
    # Parse user ID
    user_id = None
    if x_user_id:
        try:
            user_id = UUID(x_user_id)
        except ValueError:
            pass
    
    # Parse role
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

employee_router = APIRouter(prefix="/employees", tags=["Employees"])
api_router = APIRouter(prefix="/api")


# =============================================================================
# Employee Directory Endpoints
# =============================================================================

@employee_router.get(
    "",
    response_model=DirectoryResponse,
    summary="Get Employee Directory",
    description="Get paginated employee directory with filtering and sorting.",
)
async def get_employee_directory(
    service: Annotated[EmployeeService, Depends(get_employee_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
    search: Annotated[Optional[str], Query(description="Search query")] = None,
    department: Annotated[Optional[int], Query(description="Department ID filter")] = None,
    location: Annotated[Optional[int], Query(description="Location ID filter")] = None,
    status: Annotated[Optional[str], Query(description="Employment status filter")] = "active",
    sort_by: Annotated[str, Query(description="Sort field")] = "last_name",
    sort_order: Annotated[str, Query(description="Sort order (asc/desc)")] = "asc",
) -> DirectoryResponse:
    """
    Get paginated employee directory.
    
    - Applies role-based visibility controls
    - Shows only employees the user is authorized to view
    - Supports filtering by department, location, and status
    - Supports sorting by various fields
    """
    result = service.get_directory(
        current_user=current_user,
        page=page,
        page_size=page_size,
        search=search,
        department_id=department,
        location_id=location,
        status=status,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return DirectoryResponse(data=result["data"], pagination=result["pagination"])


# =============================================================================
# Employee Search Endpoints
# =============================================================================

@employee_router.post(
    "/search",
    response_model=SearchResponse,
    summary="Search Employees",
    description="Advanced employee search with fuzzy matching and filtering.",
)
async def search_employees(
    search_request: SearchRequest,
    service: Annotated[EmployeeService, Depends(get_employee_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> SearchResponse:
    """
    Search employees with advanced options.
    
    - Supports fuzzy matching
    - Field-specific searches
    - Complex filtering combinations
    - Results ranked by relevance
    - Respects access controls
    """
    result = service.search_employees(
        current_user=current_user,
        query=search_request.query,
        filters=search_request.filters,
        limit=search_request.limit,
        fuzzy=search_request.fuzzy,
    )
    return SearchResponse(
        data=result["data"],
        total=result["total"],
        query=result["query"],
    )


@employee_router.get(
    "/suggestions",
    summary="Get Search Suggestions",
    description="Get autocomplete suggestions based on partial query.",
)
async def get_search_suggestions(
    service: Annotated[EmployeeService, Depends(get_employee_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    q: Annotated[str, Query(min_length=2, description="Search query")],
    limit: Annotated[int, Query(ge=1, le=10, description="Max suggestions")] = 5,
) -> list:
    """
    Get search suggestions for autocomplete.
    
    - Returns basic employee info
    - Respects visibility controls
    - Requires minimum 2 characters
    """
    return service.get_search_suggestions(
        current_user=current_user,
        query=q,
        limit=limit,
    )


# =============================================================================
# Reference Data Endpoints
# =============================================================================

@api_router.get(
    "/departments",
    summary="Get Departments",
    description="Get all active departments for filtering.",
    tags=["Reference Data"],
)
async def get_departments(
    service: Annotated[EmployeeService, Depends(get_employee_service)],
) -> list:
    """Get all active departments."""
    return service.get_departments()


@api_router.get(
    "/locations",
    summary="Get Locations",
    description="Get all active locations for filtering.",
    tags=["Reference Data"],
)
async def get_locations(
    service: Annotated[EmployeeService, Depends(get_employee_service)],
) -> list:
    """Get all active locations."""
    return service.get_locations()


# =============================================================================
# Employee CRUD Endpoints
# =============================================================================

@employee_router.post(
    "",
    response_model=SuccessResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Employee",
    description="Create a new employee profile with validation.",
)
async def create_employee(
    data: EmployeeCreateRequest,
    service: Annotated[EmployeeService, Depends(get_employee_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> SuccessResponse:
    """
    Create a new employee profile.
    
    - Validates employee_id uniqueness
    - Validates email format and uniqueness
    - Validates foreign key references (department, manager, location, work schedule)
    - Creates audit trail
    
    Returns complete employee profile with HTTP 201 on success.
    """
    employee = service.create_employee(data, current_user)
    return SuccessResponse(data=employee, message="Employee created successfully")


@employee_router.get(
    "/{employee_id}",
    response_model=SuccessResponse,
    summary="Get Employee",
    description="Retrieve an employee profile by ID.",
)
async def get_employee(
    employee_id: int,
    service: Annotated[EmployeeService, Depends(get_employee_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> SuccessResponse:
    """
    Get employee profile by database ID.
    
    - Returns only fields the requesting user is authorized to view
    - Role-based field filtering applied
    - Returns 404 if employee not found
    """
    employee = service.get_employee(employee_id, current_user)
    return SuccessResponse(data=employee)


@employee_router.get(
    "/by-employee-id/{employee_id_str}",
    response_model=SuccessResponse,
    summary="Get Employee by Employee ID",
    description="Retrieve an employee profile by employee_id string.",
)
async def get_employee_by_employee_id(
    employee_id_str: str,
    service: Annotated[EmployeeService, Depends(get_employee_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> SuccessResponse:
    """
    Get employee profile by employee_id string (e.g., "EMP001").
    
    - Returns only fields the requesting user is authorized to view
    - Role-based field filtering applied
    - Returns 404 if employee not found
    """
    employee = service.get_employee_by_employee_id(employee_id_str, current_user)
    return SuccessResponse(data=employee)


@employee_router.put(
    "/{employee_id}",
    response_model=SuccessResponse,
    summary="Update Employee",
    description="Update an employee profile.",
)
async def update_employee(
    employee_id: int,
    data: EmployeeUpdateRequest,
    service: Annotated[EmployeeService, Depends(get_employee_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> SuccessResponse:
    """
    Update employee profile.
    
    - Validates field-level permissions
    - Validates uniqueness for employee_id and email changes
    - Validates foreign key references
    - Creates audit trail showing what changed, when, and by whom
    - Returns 404 if employee not found
    - Returns 400 for validation errors
    - Returns 403 if user lacks permission for specific fields
    """
    employee = service.update_employee(employee_id, data, current_user)
    return SuccessResponse(data=employee, message="Employee updated successfully")


@employee_router.delete(
    "/{employee_id}",
    response_model=SuccessResponse,
    summary="Terminate Employee",
    description="Terminate an employee (soft delete).",
)
async def terminate_employee(
    employee_id: int,
    service: Annotated[EmployeeService, Depends(get_employee_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    termination_data: Optional[TerminateEmployeeRequest] = None,
) -> SuccessResponse:
    """
    Terminate an employee.
    
    - Sets employment_status to 'terminated'
    - Sets is_active to False
    - Records termination_date
    - Preserves historical records (soft delete)
    - Creates audit trail
    - Returns 404 if employee not found
    - Returns 400 if already terminated
    """
    data = termination_data or TerminateEmployeeRequest()
    employee = service.terminate_employee(
        employee_id=employee_id,
        termination_date=data.termination_date,
        current_user=current_user,
        reason=data.reason,
    )
    return SuccessResponse(data=employee, message="Employee terminated successfully")


# =============================================================================
# Register Routes
# =============================================================================

api_router.include_router(employee_router)


# =============================================================================
# Exception Handlers (to be registered with FastAPI app)
# =============================================================================

async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """Handle API errors and return structured responses."""
    response = exc.to_response()
    return JSONResponse(
        status_code=response.status_code,
        content=response.to_dict(),
    )

