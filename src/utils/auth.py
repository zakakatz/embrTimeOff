"""Authentication and authorization utilities."""

import uuid
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, Callable, List, Optional, Set

from src.utils.errors import ForbiddenError, UnauthorizedError


class UserRole(str, Enum):
    """User role definitions for access control."""
    
    ADMIN = "admin"
    HR_MANAGER = "hr_manager"
    MANAGER = "manager"
    EMPLOYEE = "employee"


# Field visibility by role
# Fields that each role can view (read access)
ROLE_VIEWABLE_FIELDS: dict[UserRole, Set[str]] = {
    UserRole.ADMIN: {
        # All fields
        "id", "employee_id", "email", "first_name", "middle_name", "last_name",
        "preferred_name", "date_of_birth", "gender", "personal_email", "phone_number",
        "mobile_number", "address_line1", "address_line2", "city", "state_province",
        "postal_code", "country", "department_id", "manager_id", "location_id",
        "work_schedule_id", "job_title", "employment_type", "employment_status",
        "hire_date", "termination_date", "salary", "hourly_rate", "is_active",
        "created_at", "updated_at", "department", "location", "manager", "work_schedule",
    },
    UserRole.HR_MANAGER: {
        # All fields except some sensitive ones
        "id", "employee_id", "email", "first_name", "middle_name", "last_name",
        "preferred_name", "date_of_birth", "gender", "personal_email", "phone_number",
        "mobile_number", "address_line1", "address_line2", "city", "state_province",
        "postal_code", "country", "department_id", "manager_id", "location_id",
        "work_schedule_id", "job_title", "employment_type", "employment_status",
        "hire_date", "termination_date", "salary", "hourly_rate", "is_active",
        "created_at", "updated_at", "department", "location", "manager", "work_schedule",
    },
    UserRole.MANAGER: {
        # Can see direct reports' basic info
        "id", "employee_id", "email", "first_name", "middle_name", "last_name",
        "preferred_name", "phone_number", "mobile_number", "department_id",
        "manager_id", "location_id", "work_schedule_id", "job_title",
        "employment_type", "employment_status", "hire_date", "is_active",
        "department", "location", "manager", "work_schedule",
    },
    UserRole.EMPLOYEE: {
        # Can see basic directory info
        "id", "employee_id", "email", "first_name", "last_name", "preferred_name",
        "phone_number", "department_id", "location_id", "job_title", "employment_status",
        "department", "location", "manager",
    },
}

# Fields that each role can edit (write access)
ROLE_EDITABLE_FIELDS: dict[UserRole, Set[str]] = {
    UserRole.ADMIN: {
        # All editable fields
        "employee_id", "email", "first_name", "middle_name", "last_name",
        "preferred_name", "date_of_birth", "gender", "personal_email", "phone_number",
        "mobile_number", "address_line1", "address_line2", "city", "state_province",
        "postal_code", "country", "department_id", "manager_id", "location_id",
        "work_schedule_id", "job_title", "employment_type", "employment_status",
        "hire_date", "termination_date", "salary", "hourly_rate", "is_active",
    },
    UserRole.HR_MANAGER: {
        # HR fields
        "employee_id", "email", "first_name", "middle_name", "last_name",
        "preferred_name", "date_of_birth", "gender", "personal_email", "phone_number",
        "mobile_number", "address_line1", "address_line2", "city", "state_province",
        "postal_code", "country", "department_id", "manager_id", "location_id",
        "work_schedule_id", "job_title", "employment_type", "employment_status",
        "hire_date", "termination_date", "salary", "hourly_rate", "is_active",
    },
    UserRole.MANAGER: {
        # Limited fields for direct reports
        "work_schedule_id", "job_title",
    },
    UserRole.EMPLOYEE: {
        # Self-service fields
        "preferred_name", "personal_email", "phone_number", "mobile_number",
        "address_line1", "address_line2", "city", "state_province", "postal_code", "country",
    },
}


@dataclass
class CurrentUser:
    """Represents the currently authenticated user."""
    
    id: uuid.UUID
    employee_id: Optional[int] = None  # DB employee.id if user is also an employee
    roles: List[UserRole] = field(default_factory=lambda: [UserRole.EMPLOYEE])
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    
    @property
    def primary_role(self) -> UserRole:
        """Get the user's highest-priority role."""
        role_priority = [UserRole.ADMIN, UserRole.HR_MANAGER, UserRole.MANAGER, UserRole.EMPLOYEE]
        for role in role_priority:
            if role in self.roles:
                return role
        return UserRole.EMPLOYEE
    
    def has_role(self, role: UserRole) -> bool:
        """Check if user has a specific role."""
        return role in self.roles
    
    def can_view_field(self, field_name: str) -> bool:
        """Check if user can view a specific field."""
        viewable = self.get_viewable_fields()
        return field_name in viewable
    
    def can_edit_field(self, field_name: str) -> bool:
        """Check if user can edit a specific field."""
        editable = self.get_editable_fields()
        return field_name in editable
    
    def get_viewable_fields(self) -> Set[str]:
        """Get all fields this user can view based on their roles."""
        viewable: Set[str] = set()
        for role in self.roles:
            viewable.update(ROLE_VIEWABLE_FIELDS.get(role, set()))
        return viewable
    
    def get_editable_fields(self) -> Set[str]:
        """Get all fields this user can edit based on their roles."""
        editable: Set[str] = set()
        for role in self.roles:
            editable.update(ROLE_EDITABLE_FIELDS.get(role, set()))
        return editable


def filter_employee_response(employee_data: dict, user: CurrentUser) -> dict:
    """
    Filter employee response data based on user's role.
    
    Only includes fields the user is authorized to view.
    """
    viewable_fields = user.get_viewable_fields()
    
    filtered = {}
    for key, value in employee_data.items():
        if key in viewable_fields:
            # Handle nested objects (department, location, etc.)
            if isinstance(value, dict) and key in {"department", "location", "manager", "work_schedule"}:
                filtered[key] = value  # Include full nested object if field is viewable
            else:
                filtered[key] = value
    
    return filtered


def require_roles(*required_roles: UserRole) -> Callable:
    """
    Decorator to require specific roles for endpoint access.
    
    Usage:
        @require_roles(UserRole.ADMIN, UserRole.HR_MANAGER)
        async def my_endpoint(current_user: CurrentUser):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            current_user: Optional[CurrentUser] = kwargs.get("current_user")
            
            if current_user is None:
                raise UnauthorizedError("Authentication required")
            
            if not any(current_user.has_role(role) for role in required_roles):
                raise ForbiddenError(
                    message="Insufficient permissions",
                    details={"required_roles": [r.value for r in required_roles]},
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def get_mock_current_user(
    user_id: Optional[uuid.UUID] = None,
    employee_id: Optional[int] = None,
    roles: Optional[List[UserRole]] = None,
) -> CurrentUser:
    """
    Create a mock current user for development/testing.
    
    In production, this should be replaced with actual authentication.
    """
    return CurrentUser(
        id=user_id or uuid.uuid4(),
        employee_id=employee_id,
        roles=roles or [UserRole.ADMIN],
    )

