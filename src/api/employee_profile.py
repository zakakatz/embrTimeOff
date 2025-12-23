"""API endpoints for employee profile access and field permissions."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.models.employee import Employee, Department, Location, WorkSchedule
from src.utils.auth import CurrentUser, UserRole, get_mock_current_user
from src.utils.errors import APIError, ForbiddenError, NotFoundError


# =============================================================================
# Enums
# =============================================================================

class FieldPermissionLevel(str, Enum):
    """Permission levels for field access."""
    
    NONE = "none"
    READ = "read"
    WRITE = "write"
    WRITE_WITH_APPROVAL = "write_with_approval"


class FieldCategory(str, Enum):
    """Categories of profile fields."""
    
    PERSONAL = "personal"
    CONTACT = "contact"
    EMPLOYMENT = "employment"
    COMPENSATION = "compensation"
    EMERGENCY = "emergency"
    ORGANIZATIONAL = "organizational"
    CUSTOM = "custom"


# =============================================================================
# Response Models
# =============================================================================

class DepartmentInfo(BaseModel):
    """Department information."""
    id: int
    code: str
    name: str
    
    class Config:
        from_attributes = True


class LocationInfo(BaseModel):
    """Location information."""
    id: int
    code: str
    name: str
    city: Optional[str] = None
    country: Optional[str] = None
    timezone: Optional[str] = None
    
    class Config:
        from_attributes = True


class ManagerInfo(BaseModel):
    """Manager information."""
    id: int
    employee_id: str
    full_name: str
    email: str
    job_title: Optional[str] = None
    
    class Config:
        from_attributes = True


class EmergencyContact(BaseModel):
    """Emergency contact information."""
    name: str
    relationship: str
    phone_number: str
    email: Optional[str] = None
    is_primary: bool = False


class PersonalInformation(BaseModel):
    """Personal information section."""
    first_name: str
    middle_name: Optional[str] = None
    last_name: str
    preferred_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None


class ContactInformation(BaseModel):
    """Contact information section."""
    email: str
    personal_email: Optional[str] = None
    phone_number: Optional[str] = None
    mobile_number: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state_province: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None


class EmploymentInformation(BaseModel):
    """Employment information section."""
    employee_id: str
    job_title: Optional[str] = None
    employment_type: Optional[str] = None
    employment_status: str
    hire_date: date
    termination_date: Optional[date] = None
    department: Optional[DepartmentInfo] = None
    location: Optional[LocationInfo] = None
    manager: Optional[ManagerInfo] = None


class CompensationInformation(BaseModel):
    """Compensation information section (restricted)."""
    salary: Optional[float] = None
    hourly_rate: Optional[float] = None
    pay_frequency: Optional[str] = None
    currency: str = "USD"


class ProfileResponse(BaseModel):
    """Complete employee profile response."""
    
    id: int = Field(..., description="Employee primary key")
    employee_id: str = Field(..., description="Employee identifier")
    
    personal: PersonalInformation = Field(..., description="Personal information")
    contact: ContactInformation = Field(..., description="Contact information")
    employment: EmploymentInformation = Field(..., description="Employment details")
    compensation: Optional[CompensationInformation] = Field(None, description="Compensation (if permitted)")
    emergency_contacts: List[EmergencyContact] = Field(default_factory=list, description="Emergency contacts")
    custom_fields: Dict[str, Any] = Field(default_factory=dict, description="Organization-specific fields")
    
    is_active: bool = Field(default=True, description="Active status")
    created_at: datetime = Field(..., description="Profile creation date")
    updated_at: datetime = Field(..., description="Last update date")
    
    class Config:
        from_attributes = True


class FieldPermission(BaseModel):
    """Permission details for a single field."""
    
    field_name: str = Field(..., description="Field name")
    display_name: str = Field(..., description="Human-readable field name")
    category: FieldCategory = Field(..., description="Field category")
    permission_level: FieldPermissionLevel = Field(..., description="Permission level")
    can_read: bool = Field(default=False, description="Can read this field")
    can_write: bool = Field(default=False, description="Can write this field")
    requires_approval: bool = Field(default=False, description="Requires approval for changes")
    approval_reason: Optional[str] = Field(None, description="Why approval is required")
    permission_rationale: str = Field(..., description="Explanation of permission level")
    is_sensitive: bool = Field(default=False, description="Whether field contains sensitive data")


class FieldPermissionsResponse(BaseModel):
    """Complete field permissions matrix response."""
    
    employee_id: str = Field(..., description="Employee identifier")
    role: str = Field(..., description="Employee's role")
    
    readable_fields: List[str] = Field(default_factory=list, description="All readable field names")
    editable_fields: List[str] = Field(default_factory=list, description="All editable field names")
    approval_required_fields: List[str] = Field(default_factory=list, description="Fields requiring approval")
    
    permissions_by_field: List[FieldPermission] = Field(
        default_factory=list,
        description="Detailed permissions for each field"
    )
    permissions_by_category: Dict[str, List[FieldPermission]] = Field(
        default_factory=dict,
        description="Permissions grouped by category"
    )
    
    policy_version: str = Field(default="1.0", description="Permission policy version")
    last_policy_update: datetime = Field(default_factory=datetime.utcnow, description="Last policy update")


# =============================================================================
# Field Configuration
# =============================================================================

FIELD_DEFINITIONS = {
    # Personal Information
    "first_name": {"display": "First Name", "category": FieldCategory.PERSONAL, "sensitive": False},
    "middle_name": {"display": "Middle Name", "category": FieldCategory.PERSONAL, "sensitive": False},
    "last_name": {"display": "Last Name", "category": FieldCategory.PERSONAL, "sensitive": False},
    "preferred_name": {"display": "Preferred Name", "category": FieldCategory.PERSONAL, "sensitive": False},
    "date_of_birth": {"display": "Date of Birth", "category": FieldCategory.PERSONAL, "sensitive": True},
    "gender": {"display": "Gender", "category": FieldCategory.PERSONAL, "sensitive": True},
    
    # Contact Information
    "email": {"display": "Work Email", "category": FieldCategory.CONTACT, "sensitive": False},
    "personal_email": {"display": "Personal Email", "category": FieldCategory.CONTACT, "sensitive": True},
    "phone_number": {"display": "Phone Number", "category": FieldCategory.CONTACT, "sensitive": False},
    "mobile_number": {"display": "Mobile Number", "category": FieldCategory.CONTACT, "sensitive": True},
    "address_line1": {"display": "Street Address", "category": FieldCategory.CONTACT, "sensitive": True},
    "address_line2": {"display": "Address Line 2", "category": FieldCategory.CONTACT, "sensitive": True},
    "city": {"display": "City", "category": FieldCategory.CONTACT, "sensitive": False},
    "state_province": {"display": "State/Province", "category": FieldCategory.CONTACT, "sensitive": False},
    "postal_code": {"display": "Postal Code", "category": FieldCategory.CONTACT, "sensitive": True},
    "country": {"display": "Country", "category": FieldCategory.CONTACT, "sensitive": False},
    
    # Employment Information
    "employee_id": {"display": "Employee ID", "category": FieldCategory.EMPLOYMENT, "sensitive": False},
    "job_title": {"display": "Job Title", "category": FieldCategory.EMPLOYMENT, "sensitive": False},
    "employment_type": {"display": "Employment Type", "category": FieldCategory.EMPLOYMENT, "sensitive": False},
    "employment_status": {"display": "Status", "category": FieldCategory.EMPLOYMENT, "sensitive": False},
    "hire_date": {"display": "Hire Date", "category": FieldCategory.EMPLOYMENT, "sensitive": False},
    "termination_date": {"display": "Termination Date", "category": FieldCategory.EMPLOYMENT, "sensitive": True},
    "department_id": {"display": "Department", "category": FieldCategory.ORGANIZATIONAL, "sensitive": False},
    "location_id": {"display": "Location", "category": FieldCategory.ORGANIZATIONAL, "sensitive": False},
    "manager_id": {"display": "Manager", "category": FieldCategory.ORGANIZATIONAL, "sensitive": False},
    
    # Compensation
    "salary": {"display": "Salary", "category": FieldCategory.COMPENSATION, "sensitive": True},
    "hourly_rate": {"display": "Hourly Rate", "category": FieldCategory.COMPENSATION, "sensitive": True},
}

# Role-based permission configuration
ROLE_PERMISSIONS = {
    UserRole.ADMIN: {
        "read": ["*"],
        "write": ["*"],
        "approval_required": [],
    },
    UserRole.HR_MANAGER: {
        "read": ["*"],
        "write": [
            "first_name", "middle_name", "last_name", "preferred_name", "date_of_birth", "gender",
            "email", "personal_email", "phone_number", "mobile_number",
            "address_line1", "address_line2", "city", "state_province", "postal_code", "country",
            "job_title", "employment_type", "employment_status", "hire_date", "termination_date",
            "department_id", "location_id", "manager_id",
        ],
        "approval_required": ["salary", "hourly_rate"],
    },
    UserRole.MANAGER: {
        "read": [
            "first_name", "last_name", "preferred_name", "email", "phone_number",
            "job_title", "employment_type", "employment_status", "hire_date",
            "department_id", "location_id", "manager_id",
        ],
        "write": [],
        "approval_required": [],
    },
    UserRole.EMPLOYEE: {
        "read": [
            "first_name", "middle_name", "last_name", "preferred_name", "date_of_birth", "gender",
            "email", "personal_email", "phone_number", "mobile_number",
            "address_line1", "address_line2", "city", "state_province", "postal_code", "country",
            "employee_id", "job_title", "employment_type", "employment_status", "hire_date",
            "department_id", "location_id", "manager_id",
        ],
        "write": [
            "preferred_name", "personal_email", "phone_number", "mobile_number",
            "address_line1", "address_line2", "city", "state_province", "postal_code", "country",
        ],
        "approval_required": [],
    },
}

# Fields that employees can view their own compensation
SELF_VIEWABLE_COMPENSATION = ["salary", "hourly_rate"]


# =============================================================================
# Helper Functions
# =============================================================================

def get_field_permissions(user_role: UserRole, is_own_profile: bool = True) -> Dict[str, FieldPermission]:
    """Get field permissions based on user role."""
    role_config = ROLE_PERMISSIONS.get(user_role, ROLE_PERMISSIONS[UserRole.EMPLOYEE])
    permissions = {}
    
    for field_name, field_def in FIELD_DEFINITIONS.items():
        read_all = "*" in role_config.get("read", [])
        write_all = "*" in role_config.get("write", [])
        
        can_read = read_all or field_name in role_config.get("read", [])
        can_write = write_all or field_name in role_config.get("write", [])
        requires_approval = field_name in role_config.get("approval_required", [])
        
        # Self-viewable compensation
        if is_own_profile and field_name in SELF_VIEWABLE_COMPENSATION:
            can_read = True
        
        # Determine permission level
        if can_write and not requires_approval:
            permission_level = FieldPermissionLevel.WRITE
        elif can_write and requires_approval:
            permission_level = FieldPermissionLevel.WRITE_WITH_APPROVAL
        elif can_read:
            permission_level = FieldPermissionLevel.READ
        else:
            permission_level = FieldPermissionLevel.NONE
        
        # Generate rationale
        if permission_level == FieldPermissionLevel.WRITE:
            rationale = f"Your role ({user_role.value}) allows editing this field"
        elif permission_level == FieldPermissionLevel.WRITE_WITH_APPROVAL:
            rationale = f"Your role ({user_role.value}) allows editing with manager approval"
        elif permission_level == FieldPermissionLevel.READ:
            rationale = f"Your role ({user_role.value}) allows viewing this field"
        else:
            rationale = f"Your role ({user_role.value}) does not have access to this field"
        
        permissions[field_name] = FieldPermission(
            field_name=field_name,
            display_name=field_def["display"],
            category=field_def["category"],
            permission_level=permission_level,
            can_read=can_read,
            can_write=can_write,
            requires_approval=requires_approval,
            approval_reason="Compensation changes require HR approval" if requires_approval else None,
            permission_rationale=rationale,
            is_sensitive=field_def.get("sensitive", False),
        )
    
    return permissions


def apply_privacy_filter(
    employee: Employee,
    permissions: Dict[str, FieldPermission],
) -> Dict[str, Any]:
    """Apply privacy filters to employee data based on permissions."""
    filtered = {}
    
    for field_name, permission in permissions.items():
        if permission.can_read and hasattr(employee, field_name):
            value = getattr(employee, field_name)
            # Convert special types
            if isinstance(value, (date, datetime)):
                filtered[field_name] = value.isoformat() if value else None
            elif isinstance(value, Decimal):
                filtered[field_name] = float(value) if value else None
            else:
                filtered[field_name] = value
    
    return filtered


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
    
    roles = [UserRole.EMPLOYEE]  # Default to employee
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

employee_profile_router = APIRouter(
    prefix="/api/employee-profile",
    tags=["Employee Profile"],
)


# =============================================================================
# Endpoints
# =============================================================================

@employee_profile_router.get(
    "/my-profile",
    response_model=ProfileResponse,
    summary="Get My Profile",
    description="Get authenticated employee's complete profile with privacy filters applied.",
)
async def get_my_profile(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> ProfileResponse:
    """
    Get the authenticated employee's profile.
    
    - Returns complete profile with privacy filters applied
    - Includes personal, contact, employment, and compensation data
    - Field visibility based on organizational permission levels
    - Employees can only access their own profile
    """
    if not current_user.employee_id:
        raise ForbiddenError(
            message="Employee ID not found in authentication context",
            details={"hint": "Ensure X-Employee-ID header is set"},
        )
    
    # Fetch employee
    stmt = select(Employee).where(Employee.id == current_user.employee_id)
    result = session.execute(stmt)
    employee = result.scalar_one_or_none()
    
    if not employee:
        raise NotFoundError(
            message="Employee profile not found",
            details={"employee_id": current_user.employee_id},
        )
    
    # Get permissions
    user_role = current_user.roles[0] if current_user.roles else UserRole.EMPLOYEE
    permissions = get_field_permissions(user_role, is_own_profile=True)
    
    # Build response with privacy filters
    personal = PersonalInformation(
        first_name=employee.first_name if permissions["first_name"].can_read else "[RESTRICTED]",
        middle_name=employee.middle_name if permissions.get("middle_name", FieldPermission(
            field_name="", display_name="", category=FieldCategory.PERSONAL,
            permission_level=FieldPermissionLevel.NONE, permission_rationale=""
        )).can_read else None,
        last_name=employee.last_name if permissions["last_name"].can_read else "[RESTRICTED]",
        preferred_name=employee.preferred_name,
        date_of_birth=employee.date_of_birth if permissions.get("date_of_birth") and permissions["date_of_birth"].can_read else None,
        gender=employee.gender if permissions.get("gender") and permissions["gender"].can_read else None,
    )
    
    contact = ContactInformation(
        email=employee.email,
        personal_email=employee.personal_email if permissions.get("personal_email") and permissions["personal_email"].can_read else None,
        phone_number=employee.phone_number,
        mobile_number=employee.mobile_number if permissions.get("mobile_number") and permissions["mobile_number"].can_read else None,
        address_line1=employee.address_line1 if permissions.get("address_line1") and permissions["address_line1"].can_read else None,
        address_line2=employee.address_line2 if permissions.get("address_line2") and permissions["address_line2"].can_read else None,
        city=employee.city,
        state_province=employee.state_province,
        postal_code=employee.postal_code if permissions.get("postal_code") and permissions["postal_code"].can_read else None,
        country=employee.country,
    )
    
    # Fetch related entities
    department_info = None
    if employee.department:
        department_info = DepartmentInfo(
            id=employee.department.id,
            code=employee.department.code,
            name=employee.department.name,
        )
    
    location_info = None
    if employee.location:
        location_info = LocationInfo(
            id=employee.location.id,
            code=employee.location.code,
            name=employee.location.name,
            city=employee.location.city,
            country=employee.location.country,
            timezone=employee.location.timezone,
        )
    
    manager_info = None
    if employee.manager:
        manager_info = ManagerInfo(
            id=employee.manager.id,
            employee_id=employee.manager.employee_id,
            full_name=f"{employee.manager.first_name} {employee.manager.last_name}",
            email=employee.manager.email,
            job_title=employee.manager.job_title,
        )
    
    employment = EmploymentInformation(
        employee_id=employee.employee_id,
        job_title=employee.job_title,
        employment_type=employee.employment_type,
        employment_status=employee.employment_status,
        hire_date=employee.hire_date,
        termination_date=employee.termination_date if permissions.get("termination_date") and permissions["termination_date"].can_read else None,
        department=department_info,
        location=location_info,
        manager=manager_info,
    )
    
    # Compensation (only if permitted)
    compensation = None
    if permissions.get("salary") and permissions["salary"].can_read:
        compensation = CompensationInformation(
            salary=float(employee.salary) if employee.salary else None,
            hourly_rate=float(employee.hourly_rate) if employee.hourly_rate else None,
        )
    
    return ProfileResponse(
        id=employee.id,
        employee_id=employee.employee_id,
        personal=personal,
        contact=contact,
        employment=employment,
        compensation=compensation,
        emergency_contacts=[],  # Would fetch from separate table
        custom_fields={},
        is_active=employee.is_active,
        created_at=employee.created_at,
        updated_at=employee.updated_at,
    )


@employee_profile_router.get(
    "/field-permissions",
    response_model=FieldPermissionsResponse,
    summary="Get Field Permissions",
    description="Get comprehensive permission matrix for profile fields.",
)
async def get_field_permissions_endpoint(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> FieldPermissionsResponse:
    """
    Get field-level permissions for the authenticated employee.
    
    - Returns comprehensive permission matrix
    - Shows readable fields, editable fields, and approval requirements
    - Includes permission rationale for each field
    - Evaluates organizational policies against employee's role
    """
    if not current_user.employee_id:
        raise ForbiddenError(
            message="Employee ID not found in authentication context",
        )
    
    user_role = current_user.roles[0] if current_user.roles else UserRole.EMPLOYEE
    permissions = get_field_permissions(user_role, is_own_profile=True)
    
    # Build lists
    readable = [f for f, p in permissions.items() if p.can_read]
    editable = [f for f, p in permissions.items() if p.can_write]
    approval_required = [f for f, p in permissions.items() if p.requires_approval]
    
    # Group by category
    by_category: Dict[str, List[FieldPermission]] = {}
    for field_name, permission in permissions.items():
        category = permission.category.value
        if category not in by_category:
            by_category[category] = []
        by_category[category].append(permission)
    
    return FieldPermissionsResponse(
        employee_id=str(current_user.employee_id),
        role=user_role.value,
        readable_fields=readable,
        editable_fields=editable,
        approval_required_fields=approval_required,
        permissions_by_field=list(permissions.values()),
        permissions_by_category=by_category,
    )


# =============================================================================
# Exception Handler
# =============================================================================

async def profile_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """Handle API errors for profile endpoints."""
    response = exc.to_response()
    return JSONResponse(
        status_code=response.status_code,
        content=response.to_dict(),
    )

