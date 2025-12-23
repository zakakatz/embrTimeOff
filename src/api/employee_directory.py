"""API endpoints for employee directory listing and search."""

import uuid
from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.models.employee import Employee, Department, Location
from src.schemas.employee_directory import (
    DirectoryEmployeeResponse,
    DirectoryListResponse,
    DepartmentInfo,
    LocationInfo,
    ManagerInfo,
    ContactInfo,
)
from src.schemas.employee_directory_search import (
    DirectorySearchRequest,
    DirectorySearchResponse,
    DirectorySearchResultItem,
    PaginationInfo,
    SearchFacets,
    SearchFacet,
    FacetValue,
    SearchSuggestion,
)
from src.utils.auth import CurrentUser, UserRole, get_mock_current_user
from src.utils.errors import ForbiddenError


# =============================================================================
# Enums
# =============================================================================

class PrivacyLevel(str, Enum):
    """Privacy level for field visibility."""
    
    PUBLIC = "public"
    INTERNAL = "internal"
    RESTRICTED = "restricted"
    PRIVATE = "private"


# =============================================================================
# Helper Functions
# =============================================================================

def apply_privacy_filter(
    employee: Employee,
    viewer_role: UserRole,
    include_contact: bool = True,
) -> Dict[str, Any]:
    """Apply privacy filters to employee data based on viewer role."""
    
    # Build base data (always visible)
    data = {
        "id": employee.id,
        "employee_id": employee.employee_id,
        "full_name": f"{employee.first_name} {employee.last_name}",
        "first_name": employee.first_name,
        "last_name": employee.last_name,
        "preferred_name": employee.preferred_name,
        "display_first_name": employee.preferred_name or employee.first_name,
        "job_title": employee.job_title,
        "employment_type": employee.employment_type,
        "employment_status": employee.employment_status,
        "hire_date": employee.hire_date,
        "is_active": employee.is_active,
    }
    
    # Contact info based on role
    if include_contact:
        if viewer_role in [UserRole.ADMIN, UserRole.HR_MANAGER]:
            data["email"] = employee.email
            data["phone_number"] = employee.phone_number
            data["mobile_number"] = employee.mobile_number
        elif viewer_role == UserRole.MANAGER:
            data["email"] = employee.email
            data["phone_number"] = employee.phone_number
            data["mobile_number"] = None  # Redact
        else:
            data["email"] = employee.email
            data["phone_number"] = None  # Redact
            data["mobile_number"] = None  # Redact
    
    return data


def calculate_relevance_score(
    employee: Employee,
    query: Optional[str],
    viewer_department_id: Optional[int],
) -> float:
    """Calculate search relevance score."""
    score = 0.5  # Base score
    
    if query:
        query_lower = query.lower()
        name = f"{employee.first_name} {employee.last_name}".lower()
        
        # Exact name match
        if query_lower == name:
            score += 0.5
        # Partial name match
        elif query_lower in name:
            score += 0.3
        # Job title match
        elif employee.job_title and query_lower in employee.job_title.lower():
            score += 0.2
        # Email match
        elif query_lower in employee.email.lower():
            score += 0.1
    
    # Organizational proximity bonus
    if viewer_department_id and employee.department_id == viewer_department_id:
        score += 0.1
    
    return min(score, 1.0)


def build_search_suggestions(
    query: str,
    employees: List[Employee],
) -> List[SearchSuggestion]:
    """Build search suggestions from results."""
    suggestions = []
    
    # Name suggestions
    seen_names = set()
    for emp in employees[:5]:
        name = f"{emp.first_name} {emp.last_name}"
        if name not in seen_names:
            suggestions.append(SearchSuggestion(
                text=name,
                type="name",
                employee_id=emp.id,
                relevance_score=0.9,
            ))
            seen_names.add(name)
    
    # Job title suggestions
    seen_titles = set()
    for emp in employees[:10]:
        if emp.job_title and emp.job_title not in seen_titles:
            suggestions.append(SearchSuggestion(
                text=emp.job_title,
                type="job_title",
                relevance_score=0.7,
            ))
            seen_titles.add(emp.job_title)
    
    return suggestions[:10]


def build_facets(session: Session, base_query) -> SearchFacets:
    """Build search facets from data."""
    facets = SearchFacets()
    
    # Department facet
    dept_counts = session.execute(
        select(Employee.department_id, func.count())
        .where(Employee.is_active == True)
        .group_by(Employee.department_id)
    ).all()
    
    for dept_id, count in dept_counts:
        if dept_id:
            dept = session.get(Department, dept_id)
            if dept:
                facets.departments.values.append(FacetValue(
                    value=str(dept_id),
                    label=dept.name,
                    count=count,
                ))
    
    # Location facet
    loc_counts = session.execute(
        select(Employee.location_id, func.count())
        .where(Employee.is_active == True)
        .group_by(Employee.location_id)
    ).all()
    
    for loc_id, count in loc_counts:
        if loc_id:
            loc = session.get(Location, loc_id)
            if loc:
                facets.locations.values.append(FacetValue(
                    value=str(loc_id),
                    label=loc.name,
                    count=count,
                ))
    
    # Employment type facet
    type_counts = session.execute(
        select(Employee.employment_type, func.count())
        .where(Employee.is_active == True)
        .where(Employee.employment_type.isnot(None))
        .group_by(Employee.employment_type)
    ).all()
    
    for emp_type, count in type_counts:
        if emp_type:
            facets.employment_types.values.append(FacetValue(
                value=emp_type,
                label=emp_type.replace("_", " ").title(),
                count=count,
            ))
    
    return facets


# =============================================================================
# Dependency Injection
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
        employee_id=x_employee_id,
        roles=roles,
    )


# =============================================================================
# Router Setup
# =============================================================================

employee_directory_router = APIRouter(
    prefix="/api/employee-directory",
    tags=["Employee Directory"],
)


# =============================================================================
# Endpoints
# =============================================================================

@employee_directory_router.get(
    "/directory",
    response_model=DirectoryListResponse,
    summary="List Directory",
    description="Get paginated employee directory listing with filters.",
)
async def list_directory(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    # Pagination
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    # Filters
    department_id: Optional[int] = None,
    location_id: Optional[int] = None,
    manager_id: Optional[int] = None,
    employment_status: Optional[str] = None,
    employment_type: Optional[str] = None,
    is_active: Optional[bool] = True,
    # Sorting
    sort_by: str = "last_name",
    sort_order: str = "asc",
) -> DirectoryListResponse:
    """
    Get paginated employee directory listing.
    
    - Returns employees with organizational context
    - Applies privacy controls based on viewer role
    - Supports filtering by department, location, manager, status
    - Includes contact information with privacy filtering
    """
    user_role = current_user.roles[0] if current_user.roles else UserRole.EMPLOYEE
    
    # Build base query
    stmt = select(Employee)
    
    # Apply filters
    conditions = []
    
    if is_active is not None:
        conditions.append(Employee.is_active == is_active)
    
    if department_id:
        conditions.append(Employee.department_id == department_id)
    
    if location_id:
        conditions.append(Employee.location_id == location_id)
    
    if manager_id:
        conditions.append(Employee.manager_id == manager_id)
    
    if employment_status:
        conditions.append(Employee.employment_status == employment_status)
    
    if employment_type:
        conditions.append(Employee.employment_type == employment_type)
    
    if conditions:
        stmt = stmt.where(and_(*conditions))
    
    # Get total count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = session.execute(count_stmt).scalar() or 0
    
    # Apply sorting
    sort_column = getattr(Employee, sort_by, Employee.last_name)
    if sort_order.lower() == "desc":
        stmt = stmt.order_by(sort_column.desc())
    else:
        stmt = stmt.order_by(sort_column.asc())
    
    # Apply pagination
    offset = (page - 1) * page_size
    stmt = stmt.limit(page_size).offset(offset)
    
    # Execute query
    result = session.execute(stmt)
    employees = list(result.scalars())
    
    # Build response
    directory_employees = []
    for emp in employees:
        # Get department info
        dept_info = None
        if emp.department:
            dept_info = DepartmentInfo(
                id=emp.department.id,
                code=emp.department.code,
                name=emp.department.name,
            )
        
        # Get location info
        loc_info = None
        if emp.location:
            loc_info = LocationInfo(
                id=emp.location.id,
                code=emp.location.code,
                name=emp.location.name,
                city=emp.location.city,
                country=emp.location.country,
            )
        
        # Get manager info
        mgr_info = None
        if emp.manager:
            mgr_info = ManagerInfo(
                id=emp.manager.id,
                employee_id=emp.manager.employee_id,
                full_name=f"{emp.manager.first_name} {emp.manager.last_name}",
                job_title=emp.manager.job_title,
            )
        
        # Build contact info with privacy
        contact = ContactInfo(
            email=emp.email,
            phone_number=emp.phone_number if user_role in [UserRole.ADMIN, UserRole.HR_MANAGER, UserRole.MANAGER] else None,
            mobile_number=emp.mobile_number if user_role in [UserRole.ADMIN, UserRole.HR_MANAGER] else None,
        )
        
        # Count direct reports
        direct_reports = session.execute(
            select(func.count()).where(Employee.manager_id == emp.id)
        ).scalar() or 0
        
        directory_employees.append(DirectoryEmployeeResponse(
            id=emp.id,
            employee_id=emp.employee_id,
            full_name=f"{emp.first_name} {emp.last_name}",
            first_name=emp.first_name,
            last_name=emp.last_name,
            preferred_name=emp.preferred_name,
            display_first_name=emp.preferred_name or emp.first_name,
            job_title=emp.job_title,
            employment_type=emp.employment_type,
            employment_status=emp.employment_status,
            department=dept_info,
            location=loc_info,
            manager=mgr_info,
            contact_info=contact,
            organizational_level=0,  # Would calculate from hierarchy
            direct_reports_count=direct_reports,
            hire_date=emp.hire_date,
            is_active=emp.is_active,
            is_manager=direct_reports > 0,
        ))
    
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0
    
    return DirectoryListResponse(
        employees=directory_employees,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_previous=page > 1,
        filters_applied={
            "department_id": department_id,
            "location_id": location_id,
            "manager_id": manager_id,
            "employment_status": employment_status,
            "employment_type": employment_type,
            "is_active": is_active,
        },
    )


@employee_directory_router.post(
    "/search",
    response_model=DirectorySearchResponse,
    summary="Search Directory",
    description="Search employees with multi-criteria queries and fuzzy matching.",
)
async def search_directory(
    request: DirectorySearchRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> DirectorySearchResponse:
    """
    Search employee directory.
    
    - Supports multi-criteria search queries
    - Provides fuzzy matching across names, titles, departments
    - Returns ranked results with relevance scoring
    - Includes search suggestions and facets
    """
    import time
    start_time = time.time()
    
    user_role = current_user.roles[0] if current_user.roles else UserRole.EMPLOYEE
    
    # Build base query
    stmt = select(Employee)
    conditions = []
    
    # Active filter
    if not request.include_inactive:
        conditions.append(Employee.is_active == True)
    
    # Text search
    if request.query:
        query = f"%{request.query}%"
        conditions.append(or_(
            Employee.first_name.ilike(query),
            Employee.last_name.ilike(query),
            Employee.preferred_name.ilike(query),
            Employee.email.ilike(query),
            Employee.job_title.ilike(query),
            Employee.employee_id.ilike(query),
        ))
    
    # Department filter
    if request.department_ids:
        if request.include_sub_departments:
            # Would include sub-departments in real implementation
            conditions.append(Employee.department_id.in_(request.department_ids))
        else:
            conditions.append(Employee.department_id.in_(request.department_ids))
    
    # Location filter
    if request.location_ids:
        conditions.append(Employee.location_id.in_(request.location_ids))
    
    # Employment type filter
    if request.employment_types:
        conditions.append(Employee.employment_type.in_(request.employment_types))
    
    # Employment status filter
    if request.employment_statuses:
        conditions.append(Employee.employment_status.in_(request.employment_statuses))
    
    # Job title keywords
    if request.job_title_keywords:
        title_conditions = []
        for keyword in request.job_title_keywords:
            title_conditions.append(Employee.job_title.ilike(f"%{keyword}%"))
        conditions.append(or_(*title_conditions))
    
    # Manager filter
    if request.manager_id:
        conditions.append(Employee.manager_id == request.manager_id)
    
    # Hire date range
    if request.hire_date_range:
        if request.hire_date_range.start_date:
            conditions.append(Employee.hire_date >= request.hire_date_range.start_date)
        if request.hire_date_range.end_date:
            conditions.append(Employee.hire_date <= request.hire_date_range.end_date)
    
    if conditions:
        stmt = stmt.where(and_(*conditions))
    
    # Get total count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    filtered_count = session.execute(count_stmt).scalar() or 0
    
    # Get total active count
    total_count = session.execute(
        select(func.count()).where(Employee.is_active == True)
    ).scalar() or 0
    
    # Apply sorting
    sort_column = Employee.last_name
    if request.sort_by.value == "hire_date":
        sort_column = Employee.hire_date
    elif request.sort_by.value == "first_name":
        sort_column = Employee.first_name
    elif request.sort_by.value == "job_title":
        sort_column = Employee.job_title
    
    if request.sort_order.value == "desc":
        stmt = stmt.order_by(sort_column.desc())
    else:
        stmt = stmt.order_by(sort_column.asc())
    
    # Apply pagination
    offset = (request.page - 1) * request.page_size
    stmt = stmt.limit(request.page_size).offset(offset)
    
    # Execute query
    result = session.execute(stmt)
    employees = list(result.scalars())
    
    # Build results with relevance scoring
    results = []
    viewer_dept_id = None
    if current_user.employee_id:
        viewer = session.get(Employee, current_user.employee_id)
        if viewer:
            viewer_dept_id = viewer.department_id
    
    for emp in employees:
        relevance = calculate_relevance_score(emp, request.query, viewer_dept_id)
        
        # Determine matched fields
        matched = []
        if request.query:
            query_lower = request.query.lower()
            if query_lower in f"{emp.first_name} {emp.last_name}".lower():
                matched.append("name")
            if emp.job_title and query_lower in emp.job_title.lower():
                matched.append("job_title")
            if query_lower in emp.email.lower():
                matched.append("email")
        
        results.append(DirectorySearchResultItem(
            id=emp.id,
            employee_id=emp.employee_id,
            full_name=f"{emp.first_name} {emp.last_name}",
            first_name=emp.first_name,
            last_name=emp.last_name,
            preferred_name=emp.preferred_name,
            email=emp.email,
            job_title=emp.job_title,
            department_id=emp.department_id,
            department_name=emp.department.name if emp.department else None,
            location_id=emp.location_id,
            location_name=emp.location.name if emp.location else None,
            manager_id=emp.manager_id,
            manager_name=f"{emp.manager.first_name} {emp.manager.last_name}" if emp.manager else None,
            employment_type=emp.employment_type,
            employment_status=emp.employment_status,
            hire_date=emp.hire_date,
            is_active=emp.is_active,
            relevance_score=relevance,
            matched_fields=matched if matched else None,
        ))
    
    # Sort by relevance if searching
    if request.query and request.sort_by.value == "relevance":
        results.sort(key=lambda r: r.relevance_score or 0, reverse=True)
    
    # Build pagination
    pagination = PaginationInfo.from_query(
        page=request.page,
        page_size=request.page_size,
        total_items=filtered_count,
    )
    
    # Build facets if requested
    facets = None
    if request.include_facets:
        facets = build_facets(session, stmt)
    
    # Build suggestions if requested
    suggestions = None
    if request.include_suggestions and request.query:
        suggestions = build_search_suggestions(request.query, employees)
    
    search_time = (time.time() - start_time) * 1000
    
    return DirectorySearchResponse(
        results=results,
        total_count=total_count,
        filtered_count=filtered_count,
        pagination=pagination,
        facets=facets,
        search_suggestions=suggestions,
        query_echo=request.query,
        search_time_ms=search_time,
    )


@employee_directory_router.get(
    "/employee/{employee_id}",
    summary="Get Employee Details",
    description="Get directory details for a specific employee.",
)
async def get_employee_details(
    employee_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> Dict[str, Any]:
    """
    Get directory entry for a specific employee.
    
    - Returns full directory information
    - Applies privacy controls
    """
    user_role = current_user.roles[0] if current_user.roles else UserRole.EMPLOYEE
    
    employee = session.get(Employee, employee_id)
    
    if not employee:
        from src.utils.errors import NotFoundError
        raise NotFoundError(message="Employee not found")
    
    data = apply_privacy_filter(employee, user_role)
    
    # Add relationships
    if employee.department:
        data["department"] = {
            "id": employee.department.id,
            "name": employee.department.name,
            "code": employee.department.code,
        }
    
    if employee.location:
        data["location"] = {
            "id": employee.location.id,
            "name": employee.location.name,
            "city": employee.location.city,
        }
    
    if employee.manager:
        data["manager"] = {
            "id": employee.manager.id,
            "name": f"{employee.manager.first_name} {employee.manager.last_name}",
        }
    
    return data


@employee_directory_router.get(
    "/departments",
    summary="List Departments",
    description="Get list of departments for filtering.",
)
async def list_departments(
    session: Annotated[Session, Depends(get_db)],
) -> Dict[str, Any]:
    """Get all active departments."""
    result = session.execute(
        select(Department).where(Department.is_active == True).order_by(Department.name)
    )
    departments = list(result.scalars())
    
    return {
        "departments": [
            {"id": d.id, "code": d.code, "name": d.name}
            for d in departments
        ],
        "total": len(departments),
    }


@employee_directory_router.get(
    "/locations",
    summary="List Locations",
    description="Get list of locations for filtering.",
)
async def list_locations(
    session: Annotated[Session, Depends(get_db)],
) -> Dict[str, Any]:
    """Get all active locations."""
    result = session.execute(
        select(Location).where(Location.is_active == True).order_by(Location.name)
    )
    locations = list(result.scalars())
    
    return {
        "locations": [
            {"id": l.id, "code": l.code, "name": l.name, "city": l.city, "country": l.country}
            for l in locations
        ],
        "total": len(locations),
    }

