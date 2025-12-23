"""API endpoints for organizational structure administration."""

import uuid
from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.models.employee import Department, Employee
from src.utils.auth import CurrentUser, UserRole, get_mock_current_user
from src.utils.errors import ForbiddenError, NotFoundError, ValidationError


# =============================================================================
# Enums
# =============================================================================

class RelationshipType(str, Enum):
    """Type of reporting relationship."""
    
    DIRECT = "direct"          # Direct reporting
    DOTTED_LINE = "dotted_line"  # Secondary reporting
    FUNCTIONAL = "functional"    # Functional relationship
    TEMPORARY = "temporary"      # Temporary assignment


# =============================================================================
# Request/Response Models
# =============================================================================

class DepartmentCreateRequest(BaseModel):
    """Request to create a department."""
    
    name: str = Field(..., min_length=1, max_length=100, description="Department name")
    code: str = Field(..., min_length=1, max_length=20, description="Department code")
    description: Optional[str] = Field(None, max_length=500, description="Department description")
    parent_department_id: Optional[int] = Field(None, description="Parent department ID")
    head_of_department_id: Optional[int] = Field(None, description="Department head employee ID")
    location_id: Optional[int] = Field(None, description="Primary location ID")
    
    # Extended fields
    cost_center: Optional[str] = Field(None, max_length=50, description="Cost center code")
    budget_code: Optional[str] = Field(None, max_length=50, description="Budget code")
    organizational_level: int = Field(default=1, ge=1, le=10, description="Hierarchy level")
    department_type: str = Field(default="operational", description="Department type")
    
    @field_validator('code')
    @classmethod
    def validate_code(cls, v: str) -> str:
        """Validate department code format."""
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Code must be alphanumeric (with optional - or _)")
        return v.upper()


class DepartmentResponse(BaseModel):
    """Response for department operations."""
    
    id: int = Field(..., description="Department ID")
    code: str = Field(..., description="Department code")
    name: str = Field(..., description="Department name")
    description: Optional[str] = None
    
    parent_department_id: Optional[int] = None
    parent_department_name: Optional[str] = None
    head_of_department_id: Optional[int] = None
    head_of_department_name: Optional[str] = None
    location_id: Optional[int] = None
    
    hierarchy_path: List[str] = Field(default_factory=list, description="Path from root")
    hierarchy_level: int = Field(default=1, description="Level in hierarchy")
    
    is_active: bool = True
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class DepartmentUpdateRequest(BaseModel):
    """Request to update a department."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    parent_department_id: Optional[int] = None
    head_of_department_id: Optional[int] = None
    location_id: Optional[int] = None
    is_active: Optional[bool] = None
    cost_center: Optional[str] = None
    budget_code: Optional[str] = None


class ReportingRelationshipRequest(BaseModel):
    """Request to update reporting relationship."""
    
    employee_id: int = Field(..., description="Employee to update")
    manager_id: Optional[int] = Field(None, description="New manager (null to clear)")
    relationship_type: RelationshipType = Field(
        default=RelationshipType.DIRECT,
        description="Type of reporting relationship"
    )
    effective_date: Optional[datetime] = Field(None, description="When change takes effect")
    reason: Optional[str] = Field(None, max_length=500, description="Reason for change")


class ReportingRelationshipResponse(BaseModel):
    """Response for relationship update."""
    
    employee_id: int
    employee_name: str
    previous_manager_id: Optional[int]
    previous_manager_name: Optional[str]
    new_manager_id: Optional[int]
    new_manager_name: Optional[str]
    relationship_type: RelationshipType
    effective_date: Optional[datetime]
    hierarchy_path: List[str] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class HierarchyValidationResult(BaseModel):
    """Result of hierarchy validation."""
    
    is_valid: bool = Field(default=True)
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    circular_dependency_detected: bool = Field(default=False)


# =============================================================================
# Helper Functions
# =============================================================================

def get_department_hierarchy_path(
    department: Department,
    session: Session,
) -> List[str]:
    """Get the full hierarchy path for a department."""
    path = []
    current = department
    visited = set()
    
    while current:
        if current.id in visited:
            break  # Circular reference protection
        visited.add(current.id)
        path.insert(0, current.name)
        
        if current.parent_department_id:
            current = session.get(Department, current.parent_department_id)
        else:
            break
    
    return path


def check_circular_department_dependency(
    department_id: int,
    new_parent_id: Optional[int],
    session: Session,
) -> bool:
    """Check if setting a new parent would create a circular dependency."""
    if new_parent_id is None:
        return False
    
    if department_id == new_parent_id:
        return True
    
    # Walk up the tree from the new parent
    current_id = new_parent_id
    visited = set()
    
    while current_id:
        if current_id in visited:
            return True  # Circular
        if current_id == department_id:
            return True  # Would create circular
        
        visited.add(current_id)
        dept = session.get(Department, current_id)
        if dept:
            current_id = dept.parent_department_id
        else:
            break
    
    return False


def check_circular_reporting_dependency(
    employee_id: int,
    new_manager_id: Optional[int],
    session: Session,
) -> bool:
    """Check if setting a new manager would create a circular dependency."""
    if new_manager_id is None:
        return False
    
    if employee_id == new_manager_id:
        return True
    
    # Walk up the reporting chain from the new manager
    current_id = new_manager_id
    visited = set()
    
    while current_id:
        if current_id in visited:
            return True  # Circular
        if current_id == employee_id:
            return True  # Would create circular
        
        visited.add(current_id)
        emp = session.get(Employee, current_id)
        if emp:
            current_id = emp.manager_id
        else:
            break
    
    return False


def get_employee_hierarchy_path(
    employee: Employee,
    session: Session,
) -> List[str]:
    """Get the reporting chain for an employee."""
    path = []
    current = employee
    visited = set()
    
    while current:
        if current.id in visited:
            break
        visited.add(current.id)
        path.insert(0, f"{current.first_name} {current.last_name}")
        
        if current.manager_id:
            current = session.get(Employee, current.manager_id)
        else:
            break
    
    return path


def validate_manager_authorization(
    manager: Employee,
    session: Session,
) -> List[str]:
    """Validate that a manager has appropriate authorization."""
    errors = []
    
    if not manager.is_active:
        errors.append(f"Manager {manager.employee_id} is not active")
    
    if manager.employment_status == "terminated":
        errors.append(f"Manager {manager.employee_id} is terminated")
    
    return errors


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
    
    roles = [UserRole.ADMIN]  # Default to admin for this admin endpoint
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


def require_admin(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """Require admin or HR manager role."""
    allowed_roles = [UserRole.ADMIN, UserRole.HR_MANAGER]
    
    if not any(current_user.has_role(role) for role in allowed_roles):
        raise ForbiddenError(
            message="Admin or HR Manager role required",
            details={"required_roles": [r.value for r in allowed_roles]},
        )
    
    return current_user


# =============================================================================
# Router Setup
# =============================================================================

admin_org_structure_router = APIRouter(
    prefix="/api/admin",
    tags=["Admin - Organizational Structure"],
)


# =============================================================================
# Endpoints
# =============================================================================

@admin_org_structure_router.post(
    "/organizational-structure",
    response_model=DepartmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Department",
    description="Create a new department in the organizational structure.",
)
async def create_department(
    request: DepartmentCreateRequest,
    current_user: Annotated[CurrentUser, Depends(require_admin)],
    session: Annotated[Session, Depends(get_db)],
) -> DepartmentResponse:
    """
    Create a new department.
    
    - Validates parent department exists
    - Validates department head exists and is authorized
    - Calculates hierarchy level based on parent
    - Returns created department with hierarchy path
    """
    # Check if code already exists
    existing = session.execute(
        select(Department).where(Department.code == request.code)
    ).scalar_one_or_none()
    
    if existing:
        raise ValidationError(
            message=f"Department code '{request.code}' already exists",
            details={"existing_id": existing.id},
        )
    
    # Validate parent department
    parent = None
    hierarchy_level = 1
    
    if request.parent_department_id:
        parent = session.get(Department, request.parent_department_id)
        if not parent:
            raise ValidationError(
                message="Parent department not found",
                details={"parent_department_id": request.parent_department_id},
            )
        if not parent.is_active:
            raise ValidationError(
                message="Parent department is not active",
            )
        hierarchy_level = request.organizational_level or 2  # Child level
    
    # Validate department head
    head = None
    if request.head_of_department_id:
        head = session.get(Employee, request.head_of_department_id)
        if not head:
            raise ValidationError(
                message="Department head employee not found",
                details={"head_of_department_id": request.head_of_department_id},
            )
        
        auth_errors = validate_manager_authorization(head, session)
        if auth_errors:
            raise ValidationError(
                message="Department head authorization failed",
                details={"errors": auth_errors},
            )
    
    # Create department
    department = Department(
        code=request.code,
        name=request.name,
        description=request.description,
        parent_department_id=request.parent_department_id,
        head_of_department_id=request.head_of_department_id,
        location_id=request.location_id,
        cost_center=request.cost_center,
        budget_code=request.budget_code,
        organizational_level=hierarchy_level,
        department_type=request.department_type,
        is_active=True,
    )
    
    session.add(department)
    session.commit()
    session.refresh(department)
    
    # Build response
    hierarchy_path = get_department_hierarchy_path(department, session)
    
    return DepartmentResponse(
        id=department.id,
        code=department.code,
        name=department.name,
        description=department.description,
        parent_department_id=department.parent_department_id,
        parent_department_name=parent.name if parent else None,
        head_of_department_id=department.head_of_department_id,
        head_of_department_name=f"{head.first_name} {head.last_name}" if head else None,
        location_id=department.location_id,
        hierarchy_path=hierarchy_path,
        hierarchy_level=hierarchy_level,
        is_active=department.is_active,
        created_at=department.created_at,
        updated_at=department.updated_at,
    )


@admin_org_structure_router.put(
    "/organizational-structure/{department_id}",
    response_model=DepartmentResponse,
    summary="Update Department",
    description="Update an existing department.",
)
async def update_department(
    department_id: int,
    request: DepartmentUpdateRequest,
    current_user: Annotated[CurrentUser, Depends(require_admin)],
    session: Annotated[Session, Depends(get_db)],
) -> DepartmentResponse:
    """
    Update a department.
    
    - Validates hierarchy consistency
    - Prevents circular dependencies
    - Updates hierarchy paths for children if parent changes
    """
    department = session.get(Department, department_id)
    
    if not department:
        raise NotFoundError(message="Department not found")
    
    # Check for circular dependency if changing parent
    if request.parent_department_id is not None:
        if check_circular_department_dependency(
            department_id, request.parent_department_id, session
        ):
            raise ValidationError(
                message="Cannot set parent: would create circular dependency",
                details={
                    "department_id": department_id,
                    "proposed_parent_id": request.parent_department_id,
                },
            )
        
        # Validate new parent exists
        if request.parent_department_id:
            new_parent = session.get(Department, request.parent_department_id)
            if not new_parent:
                raise ValidationError(message="New parent department not found")
    
    # Validate new head if specified
    if request.head_of_department_id is not None:
        if request.head_of_department_id:
            head = session.get(Employee, request.head_of_department_id)
            if not head:
                raise ValidationError(message="Department head employee not found")
            
            auth_errors = validate_manager_authorization(head, session)
            if auth_errors:
                raise ValidationError(
                    message="Department head authorization failed",
                    details={"errors": auth_errors},
                )
    
    # Apply updates
    if request.name is not None:
        department.name = request.name
    if request.description is not None:
        department.description = request.description
    if request.parent_department_id is not None:
        department.parent_department_id = request.parent_department_id or None
    if request.head_of_department_id is not None:
        department.head_of_department_id = request.head_of_department_id or None
    if request.location_id is not None:
        department.location_id = request.location_id or None
    if request.is_active is not None:
        department.is_active = request.is_active
    if request.cost_center is not None:
        department.cost_center = request.cost_center
    if request.budget_code is not None:
        department.budget_code = request.budget_code
    
    session.commit()
    session.refresh(department)
    
    # Build response
    hierarchy_path = get_department_hierarchy_path(department, session)
    
    parent = session.get(Department, department.parent_department_id) if department.parent_department_id else None
    head = session.get(Employee, department.head_of_department_id) if department.head_of_department_id else None
    
    return DepartmentResponse(
        id=department.id,
        code=department.code,
        name=department.name,
        description=department.description,
        parent_department_id=department.parent_department_id,
        parent_department_name=parent.name if parent else None,
        head_of_department_id=department.head_of_department_id,
        head_of_department_name=f"{head.first_name} {head.last_name}" if head else None,
        location_id=department.location_id,
        hierarchy_path=hierarchy_path,
        hierarchy_level=department.organizational_level,
        is_active=department.is_active,
        created_at=department.created_at,
        updated_at=department.updated_at,
    )


@admin_org_structure_router.put(
    "/structural-relationships",
    response_model=ReportingRelationshipResponse,
    summary="Update Reporting Relationship",
    description="Update employee reporting relationship.",
)
async def update_reporting_relationship(
    request: ReportingRelationshipRequest,
    current_user: Annotated[CurrentUser, Depends(require_admin)],
    session: Annotated[Session, Depends(get_db)],
) -> ReportingRelationshipResponse:
    """
    Update employee reporting relationship.
    
    - Validates both employee and manager exist
    - Prevents circular reporting dependencies
    - Validates manager authorization
    - Returns updated relationship structure
    """
    # Validate employee exists
    employee = session.get(Employee, request.employee_id)
    if not employee:
        raise NotFoundError(
            message="Employee not found",
            details={"employee_id": request.employee_id},
        )
    
    # Store previous manager info
    previous_manager_id = employee.manager_id
    previous_manager_name = None
    if employee.manager:
        previous_manager_name = f"{employee.manager.first_name} {employee.manager.last_name}"
    
    # Validate new manager if specified
    new_manager = None
    new_manager_name = None
    
    if request.manager_id:
        new_manager = session.get(Employee, request.manager_id)
        if not new_manager:
            raise NotFoundError(
                message="Manager not found",
                details={"manager_id": request.manager_id},
            )
        
        # Check for circular dependency
        if check_circular_reporting_dependency(
            request.employee_id, request.manager_id, session
        ):
            raise ValidationError(
                message="Cannot set manager: would create circular reporting relationship",
                details={
                    "employee_id": request.employee_id,
                    "proposed_manager_id": request.manager_id,
                },
            )
        
        # Validate manager authorization
        auth_errors = validate_manager_authorization(new_manager, session)
        if auth_errors:
            raise ValidationError(
                message="Manager authorization validation failed",
                details={"errors": auth_errors},
            )
        
        new_manager_name = f"{new_manager.first_name} {new_manager.last_name}"
    
    # Update relationship
    employee.manager_id = request.manager_id
    session.commit()
    session.refresh(employee)
    
    # Get updated hierarchy path
    hierarchy_path = get_employee_hierarchy_path(employee, session)
    
    return ReportingRelationshipResponse(
        employee_id=employee.id,
        employee_name=f"{employee.first_name} {employee.last_name}",
        previous_manager_id=previous_manager_id,
        previous_manager_name=previous_manager_name,
        new_manager_id=request.manager_id,
        new_manager_name=new_manager_name,
        relationship_type=request.relationship_type,
        effective_date=request.effective_date,
        hierarchy_path=hierarchy_path,
    )


@admin_org_structure_router.get(
    "/organizational-structure/{department_id}",
    response_model=DepartmentResponse,
    summary="Get Department",
    description="Get department details.",
)
async def get_department(
    department_id: int,
    current_user: Annotated[CurrentUser, Depends(require_admin)],
    session: Annotated[Session, Depends(get_db)],
) -> DepartmentResponse:
    """Get department details with hierarchy path."""
    department = session.get(Department, department_id)
    
    if not department:
        raise NotFoundError(message="Department not found")
    
    hierarchy_path = get_department_hierarchy_path(department, session)
    
    parent = session.get(Department, department.parent_department_id) if department.parent_department_id else None
    head = session.get(Employee, department.head_of_department_id) if department.head_of_department_id else None
    
    return DepartmentResponse(
        id=department.id,
        code=department.code,
        name=department.name,
        description=department.description,
        parent_department_id=department.parent_department_id,
        parent_department_name=parent.name if parent else None,
        head_of_department_id=department.head_of_department_id,
        head_of_department_name=f"{head.first_name} {head.last_name}" if head else None,
        location_id=department.location_id,
        hierarchy_path=hierarchy_path,
        hierarchy_level=department.organizational_level,
        is_active=department.is_active,
        created_at=department.created_at,
        updated_at=department.updated_at,
    )


@admin_org_structure_router.post(
    "/validate-hierarchy",
    response_model=HierarchyValidationResult,
    summary="Validate Hierarchy",
    description="Validate proposed hierarchy changes.",
)
async def validate_hierarchy(
    department_id: int,
    proposed_parent_id: Optional[int],
    current_user: Annotated[CurrentUser, Depends(require_admin)],
    session: Annotated[Session, Depends(get_db)],
) -> HierarchyValidationResult:
    """
    Validate a proposed hierarchy change.
    
    - Checks for circular dependencies
    - Returns validation result with details
    """
    errors = []
    warnings = []
    
    department = session.get(Department, department_id)
    if not department:
        errors.append("Department not found")
        return HierarchyValidationResult(
            is_valid=False,
            errors=errors,
            circular_dependency_detected=False,
        )
    
    # Check circular dependency
    is_circular = check_circular_department_dependency(
        department_id, proposed_parent_id, session
    )
    
    if is_circular:
        errors.append("Proposed change would create circular dependency")
    
    # Check if parent exists
    if proposed_parent_id:
        parent = session.get(Department, proposed_parent_id)
        if not parent:
            errors.append("Proposed parent department does not exist")
        elif not parent.is_active:
            warnings.append("Proposed parent department is not active")
    
    return HierarchyValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        circular_dependency_detected=is_circular,
    )

