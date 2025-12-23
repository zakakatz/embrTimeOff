"""API endpoints for department assignment and override management."""

import uuid
from datetime import datetime, date
from enum import Enum
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, Query, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.models.employee import Employee, Department
from src.utils.auth import CurrentUser, UserRole, get_mock_current_user
from src.utils.errors import ForbiddenError, NotFoundError, ValidationError


# =============================================================================
# Enums
# =============================================================================

class AssignmentType(str, Enum):
    """Type of department assignment."""
    
    PRIMARY = "primary"         # Main department
    SECONDARY = "secondary"     # Secondary/matrix assignment
    TEMPORARY = "temporary"     # Temporary assignment
    PROJECT = "project"         # Project-based assignment


class AssignmentStatus(str, Enum):
    """Status of department assignment."""
    
    ACTIVE = "active"
    PENDING = "pending"
    ENDED = "ended"
    CANCELLED = "cancelled"


class OverrideType(str, Enum):
    """Type of department override."""
    
    REPORTING_STRUCTURE = "reporting_structure"
    POLICY = "policy"
    APPROVAL_WORKFLOW = "approval_workflow"
    ACCESS_PERMISSIONS = "access_permissions"
    BUDGET = "budget"


class AuthorityLevel(str, Enum):
    """Authority level for head assignments."""
    
    FULL = "full"           # Full departmental authority
    LIMITED = "limited"     # Limited authority (specific functions)
    ACTING = "acting"       # Acting/interim authority
    DELEGATE = "delegate"   # Delegated authority


# =============================================================================
# Request Models
# =============================================================================

class DepartmentAssignmentRequest(BaseModel):
    """Request to assign an employee to a department."""
    
    employee_id: int = Field(..., description="Employee to assign")
    department_id: int = Field(..., description="Target department")
    assignment_type: AssignmentType = Field(
        default=AssignmentType.PRIMARY,
        description="Type of assignment",
    )
    
    # Effective dates
    effective_date: Optional[date] = Field(
        None,
        description="When assignment takes effect (defaults to today)",
    )
    end_date: Optional[date] = Field(
        None,
        description="When assignment ends (for temporary/project)",
    )
    
    # Additional info
    reason: Optional[str] = Field(None, max_length=500, description="Reason for assignment")
    notes: Optional[str] = Field(None, max_length=1000, description="Additional notes")
    
    # Manager assignment
    reporting_manager_id: Optional[int] = Field(
        None,
        description="Override reporting manager (if different from department head)",
    )
    
    @field_validator("end_date")
    @classmethod
    def validate_end_date(cls, v: Optional[date], info) -> Optional[date]:
        """Validate end date is after effective date."""
        effective = info.data.get("effective_date") or date.today()
        if v and v < effective:
            raise ValueError("End date cannot be before effective date")
        return v


class HeadOfDepartmentRequest(BaseModel):
    """Request to assign an employee as head of department."""
    
    employee_id: int = Field(..., description="Employee to assign as head")
    department_id: int = Field(..., description="Department to head")
    authority_level: AuthorityLevel = Field(
        default=AuthorityLevel.FULL,
        description="Level of authority granted",
    )
    
    # Effective dates
    effective_date: Optional[date] = Field(None, description="When assignment takes effect")
    end_date: Optional[date] = Field(None, description="When assignment ends (for acting/interim)")
    
    # Requirements
    requires_approval: bool = Field(default=True, description="Whether approval is required")
    reason: str = Field(..., min_length=1, max_length=500, description="Reason for assignment")


class DepartmentOverrideRequest(BaseModel):
    """Request to create/update a department configuration override."""
    
    department_id: int = Field(..., description="Target department")
    override_type: OverrideType = Field(..., description="Type of override")
    
    # Override configuration
    configuration: Dict[str, Any] = Field(
        ...,
        description="Override configuration parameters",
    )
    
    # Effective period
    effective_date: Optional[date] = Field(None, description="When override takes effect")
    expiration_date: Optional[date] = Field(None, description="When override expires")
    
    # Reason and approval
    reason: str = Field(..., min_length=1, max_length=500, description="Reason for override")
    requires_approval: bool = Field(default=False)
    
    @field_validator("configuration")
    @classmethod
    def validate_configuration(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """Validate configuration is not empty."""
        if not v:
            raise ValueError("Configuration cannot be empty")
        return v


# =============================================================================
# Response Models
# =============================================================================

class DepartmentInfo(BaseModel):
    """Department information."""
    
    id: int
    code: str
    name: str
    parent_department_id: Optional[int] = None
    parent_department_name: Optional[str] = None
    head_of_department_id: Optional[int] = None
    head_of_department_name: Optional[str] = None


class EmployeeInfo(BaseModel):
    """Employee information."""
    
    id: int
    employee_id: str
    full_name: str
    job_title: Optional[str] = None
    current_department_id: Optional[int] = None
    current_department_name: Optional[str] = None
    is_manager: bool = Field(default=False)


class DepartmentAssignmentResponse(BaseModel):
    """Response for department assignment."""
    
    assignment_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    employee: EmployeeInfo
    department: DepartmentInfo
    assignment_type: str
    assignment_status: str
    
    effective_date: date
    end_date: Optional[date] = None
    
    reporting_manager_id: Optional[int] = None
    reporting_manager_name: Optional[str] = None
    
    reason: Optional[str] = None
    notes: Optional[str] = None
    
    # Previous assignment info
    previous_department_id: Optional[int] = None
    previous_department_name: Optional[str] = None
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: Optional[str] = None
    
    message: str = Field(default="Department assignment successful")


class HeadOfDepartmentResponse(BaseModel):
    """Response for head of department assignment."""
    
    assignment_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    employee: EmployeeInfo
    department: DepartmentInfo
    authority_level: str
    
    effective_date: date
    end_date: Optional[date] = None
    
    # Previous head info
    previous_head_id: Optional[int] = None
    previous_head_name: Optional[str] = None
    
    requires_approval: bool = Field(default=True)
    approval_status: str = Field(default="pending")
    
    reason: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    message: str = Field(default="Head of department assignment submitted")


class DepartmentOverrideResponse(BaseModel):
    """Response for department override."""
    
    override_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    department_id: int
    department_name: str
    override_type: str
    
    configuration: Dict[str, Any]
    
    effective_date: Optional[date] = None
    expiration_date: Optional[date] = None
    
    status: str = Field(default="active")
    requires_approval: bool = Field(default=False)
    approval_status: Optional[str] = None
    
    reason: str
    
    # Validation results
    validation_passed: bool = Field(default=True)
    validation_warnings: List[str] = Field(default_factory=list)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: Optional[str] = None
    
    message: str = Field(default="Department override created successfully")


class ValidationResult(BaseModel):
    """Validation result."""
    
    is_valid: bool
    error_message: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)


# =============================================================================
# Helper Functions
# =============================================================================

def validate_employee_exists(
    employee_id: int,
    session: Session,
) -> tuple[bool, Optional[Employee], Optional[str]]:
    """Validate employee exists and is active."""
    employee = session.get(Employee, employee_id)
    if not employee:
        return False, None, f"Employee {employee_id} not found"
    if not employee.is_active:
        return False, employee, f"Employee {employee_id} is not active"
    return True, employee, None


def validate_department_exists(
    department_id: int,
    session: Session,
) -> tuple[bool, Optional[Department], Optional[str]]:
    """Validate department exists and is active."""
    department = session.get(Department, department_id)
    if not department:
        return False, None, f"Department {department_id} not found"
    if not department.is_active:
        return False, department, f"Department {department_id} is not active"
    return True, department, None


def check_circular_reporting(
    employee_id: int,
    potential_manager_id: int,
    session: Session,
) -> tuple[bool, Optional[str]]:
    """Check for circular reporting relationships."""
    if employee_id == potential_manager_id:
        return True, "Employee cannot report to themselves"
    
    # Walk up the manager chain to check for cycles
    current_id = potential_manager_id
    visited = {employee_id}
    max_depth = 20  # Prevent infinite loops
    
    for _ in range(max_depth):
        if current_id in visited:
            return True, f"Circular reporting detected: {current_id} is in the reporting chain"
        
        current = session.get(Employee, current_id)
        if not current or not current.manager_id:
            break
        
        visited.add(current_id)
        current_id = current.manager_id
    
    return False, None


def validate_head_authority(
    employee: Employee,
    department: Department,
    authority_level: AuthorityLevel,
) -> ValidationResult:
    """Validate employee has appropriate authority for head assignment."""
    warnings = []
    
    # Check if employee has manager capabilities
    is_manager = employee.job_title and any(
        title in employee.job_title.lower()
        for title in ["manager", "director", "head", "lead", "chief", "vp", "president"]
    )
    
    if not is_manager and authority_level == AuthorityLevel.FULL:
        warnings.append(
            "Employee job title does not indicate management role; "
            "consider LIMITED or ACTING authority level"
        )
    
    # Check for existing head
    if department.head_of_department_id:
        if department.head_of_department_id != employee.id:
            warnings.append(
                f"Department already has an assigned head (ID: {department.head_of_department_id})"
            )
    
    return ValidationResult(
        is_valid=True,
        warnings=warnings,
    )


def validate_override_configuration(
    override_type: OverrideType,
    config: Dict[str, Any],
    department: Department,
) -> ValidationResult:
    """Validate override configuration for policy compliance."""
    warnings = []
    
    if override_type == OverrideType.REPORTING_STRUCTURE:
        if "alternate_report_to" in config:
            if config["alternate_report_to"] == department.id:
                return ValidationResult(
                    is_valid=False,
                    error_message="Department cannot report to itself",
                )
    
    elif override_type == OverrideType.APPROVAL_WORKFLOW:
        if "bypass_approval" in config and config["bypass_approval"]:
            warnings.append("Bypassing approval workflow may violate compliance requirements")
    
    elif override_type == OverrideType.BUDGET:
        if "budget_override" in config:
            override_amount = config.get("budget_override", 0)
            if override_amount > 1000000:
                warnings.append("Large budget override requires executive approval")
    
    return ValidationResult(
        is_valid=True,
        warnings=warnings,
    )


def build_employee_info(employee: Employee) -> EmployeeInfo:
    """Build employee info response."""
    is_manager = False
    # Check if employee has any direct reports
    # In real implementation, query direct_reports count
    if employee.job_title:
        is_manager = any(
            title in employee.job_title.lower()
            for title in ["manager", "director", "head", "lead"]
        )
    
    return EmployeeInfo(
        id=employee.id,
        employee_id=employee.employee_id,
        full_name=f"{employee.first_name} {employee.last_name}",
        job_title=employee.job_title,
        current_department_id=employee.department_id,
        current_department_name=employee.department.name if employee.department else None,
        is_manager=is_manager,
    )


def build_department_info(
    department: Department,
    session: Session,
) -> DepartmentInfo:
    """Build department info response."""
    parent_name = None
    if department.parent_department_id:
        parent = session.get(Department, department.parent_department_id)
        if parent:
            parent_name = parent.name
    
    head_name = None
    if department.head_of_department_id:
        head = session.get(Employee, department.head_of_department_id)
        if head:
            head_name = f"{head.first_name} {head.last_name}"
    
    return DepartmentInfo(
        id=department.id,
        code=department.code,
        name=department.name,
        parent_department_id=department.parent_department_id,
        parent_department_name=parent_name,
        head_of_department_id=department.head_of_department_id,
        head_of_department_name=head_name,
    )


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


def require_admin(current_user: CurrentUser) -> CurrentUser:
    """Require admin role."""
    if not any(r in current_user.roles for r in [UserRole.ADMIN, UserRole.HR]):
        raise ForbiddenError(message="Admin access required for this operation")
    return current_user


# =============================================================================
# Router Setup
# =============================================================================

department_assignments_router = APIRouter(
    prefix="/api/admin",
    tags=["Department Assignments"],
)


# =============================================================================
# Endpoints
# =============================================================================

@department_assignments_router.post(
    "/department-assignments",
    response_model=DepartmentAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Assign Employee to Department",
    description="Assign an employee to a department.",
)
async def assign_employee_to_department(
    request: DepartmentAssignmentRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> DepartmentAssignmentResponse:
    """
    Assign an employee to a department.
    
    - Validates employee and department exist
    - Checks for circular reporting relationships
    - Handles primary, secondary, and temporary assignments
    """
    require_admin(current_user)
    
    # Validate employee
    emp_valid, employee, emp_error = validate_employee_exists(request.employee_id, session)
    if not emp_valid:
        raise ValidationError(
            message=emp_error or "Invalid employee",
            field_errors=[{"field": "employee_id", "message": emp_error}],
        )
    
    # Validate department
    dept_valid, department, dept_error = validate_department_exists(request.department_id, session)
    if not dept_valid:
        raise ValidationError(
            message=dept_error or "Invalid department",
            field_errors=[{"field": "department_id", "message": dept_error}],
        )
    
    # Check for circular reporting if manager specified
    if request.reporting_manager_id:
        is_circular, circular_error = check_circular_reporting(
            request.employee_id,
            request.reporting_manager_id,
            session,
        )
        if is_circular:
            raise ValidationError(
                message=circular_error or "Circular reporting detected",
                field_errors=[{"field": "reporting_manager_id", "message": circular_error}],
            )
    
    # Store previous department info
    previous_dept_id = employee.department_id
    previous_dept_name = None
    if previous_dept_id:
        prev_dept = session.get(Department, previous_dept_id)
        if prev_dept:
            previous_dept_name = prev_dept.name
    
    # Determine effective date
    effective = request.effective_date or date.today()
    
    # Update employee's department (for primary assignments)
    if request.assignment_type == AssignmentType.PRIMARY:
        employee.department_id = request.department_id
        
        # Update manager if specified
        if request.reporting_manager_id:
            employee.manager_id = request.reporting_manager_id
        elif department.head_of_department_id:
            employee.manager_id = department.head_of_department_id
        
        session.commit()
        session.refresh(employee)
    
    # Get reporting manager name
    reporting_manager_name = None
    if employee.manager_id:
        manager = session.get(Employee, employee.manager_id)
        if manager:
            reporting_manager_name = f"{manager.first_name} {manager.last_name}"
    
    return DepartmentAssignmentResponse(
        employee=build_employee_info(employee),
        department=build_department_info(department, session),
        assignment_type=request.assignment_type.value,
        assignment_status=AssignmentStatus.ACTIVE.value,
        effective_date=effective,
        end_date=request.end_date,
        reporting_manager_id=employee.manager_id,
        reporting_manager_name=reporting_manager_name,
        reason=request.reason,
        notes=request.notes,
        previous_department_id=previous_dept_id,
        previous_department_name=previous_dept_name,
        created_by=str(current_user.user_id) if current_user.user_id else None,
        message=f"Employee assigned to {department.name} department",
    )


@department_assignments_router.post(
    "/head-of-department",
    response_model=HeadOfDepartmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Assign Head of Department",
    description="Assign an employee as head of a department.",
)
async def assign_head_of_department(
    request: HeadOfDepartmentRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> HeadOfDepartmentResponse:
    """
    Assign an employee as head of department.
    
    - Validates employee authority level
    - Handles acting/interim assignments
    - Requires admin approval for permanent assignments
    """
    require_admin(current_user)
    
    # Validate employee
    emp_valid, employee, emp_error = validate_employee_exists(request.employee_id, session)
    if not emp_valid:
        raise ValidationError(
            message=emp_error or "Invalid employee",
            field_errors=[{"field": "employee_id", "message": emp_error}],
        )
    
    # Validate department
    dept_valid, department, dept_error = validate_department_exists(request.department_id, session)
    if not dept_valid:
        raise ValidationError(
            message=dept_error or "Invalid department",
            field_errors=[{"field": "department_id", "message": dept_error}],
        )
    
    # Validate authority level
    validation = validate_head_authority(employee, department, request.authority_level)
    if not validation.is_valid:
        raise ValidationError(
            message=validation.error_message or "Authority validation failed",
            field_errors=[{"field": "authority_level", "message": validation.error_message}],
        )
    
    # Store previous head info
    previous_head_id = department.head_of_department_id
    previous_head_name = None
    if previous_head_id:
        prev_head = session.get(Employee, previous_head_id)
        if prev_head:
            previous_head_name = f"{prev_head.first_name} {prev_head.last_name}"
    
    # Determine effective date
    effective = request.effective_date or date.today()
    
    # Update department head (if not requiring approval)
    if not request.requires_approval:
        department.head_of_department_id = request.employee_id
        
        # Also ensure employee is in this department
        if employee.department_id != department.id:
            employee.department_id = department.id
        
        session.commit()
        session.refresh(department)
        session.refresh(employee)
    
    return HeadOfDepartmentResponse(
        employee=build_employee_info(employee),
        department=build_department_info(department, session),
        authority_level=request.authority_level.value,
        effective_date=effective,
        end_date=request.end_date,
        previous_head_id=previous_head_id,
        previous_head_name=previous_head_name,
        requires_approval=request.requires_approval,
        approval_status="pending" if request.requires_approval else "approved",
        reason=request.reason,
        message=(
            "Head of department assignment pending approval"
            if request.requires_approval
            else f"Employee assigned as head of {department.name}"
        ),
    )


@department_assignments_router.put(
    "/department-overrides",
    response_model=DepartmentOverrideResponse,
    summary="Create/Update Department Override",
    description="Create or update a department configuration override.",
)
async def create_department_override(
    request: DepartmentOverrideRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> DepartmentOverrideResponse:
    """
    Create or update a department override.
    
    - Validates policy compliance
    - Maintains organizational consistency
    - Supports various override types
    """
    require_admin(current_user)
    
    # Validate department
    dept_valid, department, dept_error = validate_department_exists(request.department_id, session)
    if not dept_valid:
        raise ValidationError(
            message=dept_error or "Invalid department",
            field_errors=[{"field": "department_id", "message": dept_error}],
        )
    
    # Validate override configuration
    validation = validate_override_configuration(
        request.override_type,
        request.configuration,
        department,
    )
    
    if not validation.is_valid:
        raise ValidationError(
            message=validation.error_message or "Override validation failed",
            field_errors=[{"field": "configuration", "message": validation.error_message}],
        )
    
    # Determine status
    override_status = "active"
    approval_status = None
    
    if request.requires_approval:
        override_status = "pending_approval"
        approval_status = "pending"
    
    return DepartmentOverrideResponse(
        department_id=department.id,
        department_name=department.name,
        override_type=request.override_type.value,
        configuration=request.configuration,
        effective_date=request.effective_date,
        expiration_date=request.expiration_date,
        status=override_status,
        requires_approval=request.requires_approval,
        approval_status=approval_status,
        reason=request.reason,
        validation_passed=validation.is_valid,
        validation_warnings=validation.warnings,
        created_by=str(current_user.user_id) if current_user.user_id else None,
        message=(
            "Override pending approval"
            if request.requires_approval
            else "Department override created successfully"
        ),
    )


@department_assignments_router.get(
    "/department-assignments/{employee_id}",
    summary="Get Employee Department Assignments",
    description="Get all department assignments for an employee.",
)
async def get_employee_assignments(
    employee_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> Dict[str, Any]:
    """Get department assignments for an employee."""
    employee = session.get(Employee, employee_id)
    if not employee:
        raise NotFoundError(message=f"Employee {employee_id} not found")
    
    # Build current assignment info
    current_assignment = None
    if employee.department_id:
        department = session.get(Department, employee.department_id)
        if department:
            current_assignment = {
                "department": build_department_info(department, session).model_dump(),
                "assignment_type": "primary",
                "status": "active",
            }
    
    return {
        "employee": build_employee_info(employee).model_dump(),
        "current_assignment": current_assignment,
        "assignment_history": [],  # Would be populated from audit log
    }

