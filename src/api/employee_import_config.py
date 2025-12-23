"""API endpoints for import configuration and security framework."""

import uuid
from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel, Field

from src.utils.auth import CurrentUser, UserRole, get_mock_current_user
from src.utils.errors import ForbiddenError


# =============================================================================
# Enums
# =============================================================================

class SecurityLevel(str, Enum):
    """Security level for import operations."""
    
    LOW = "low"           # Basic validation only
    MEDIUM = "medium"     # Standard security checks
    HIGH = "high"         # Full security scanning


class ValidationRuleType(str, Enum):
    """Types of validation rules."""
    
    REQUIRED = "required"
    FORMAT = "format"
    LENGTH = "length"
    RANGE = "range"
    PATTERN = "pattern"
    UNIQUE = "unique"
    REFERENCE = "reference"
    BUSINESS = "business"


class PermissionAction(str, Enum):
    """Import permission actions."""
    
    UPLOAD = "upload"
    VALIDATE = "validate"
    PREVIEW = "preview"
    EXECUTE = "execute"
    ROLLBACK = "rollback"
    VIEW_ERRORS = "view_errors"
    VIEW_CONFIG = "view_config"
    MODIFY_CONFIG = "modify_config"


# =============================================================================
# Response Models
# =============================================================================

class FieldMappingDefault(BaseModel):
    """Default field mapping configuration."""
    
    csv_column_pattern: str = Field(..., description="CSV column name pattern")
    employee_field: str = Field(..., description="Target employee field")
    confidence_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum confidence for auto-mapping"
    )
    is_required: bool = Field(default=False, description="Whether field is required")
    default_value: Optional[str] = Field(None, description="Default value if not provided")


class ValidationRule(BaseModel):
    """Validation rule definition."""
    
    rule_id: str = Field(..., description="Unique rule identifier")
    rule_type: ValidationRuleType = Field(..., description="Type of rule")
    field_name: str = Field(..., description="Field this rule applies to")
    
    # Rule configuration
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Rule parameters")
    error_message: str = Field(..., description="Error message when rule fails")
    
    # Metadata
    is_enabled: bool = Field(default=True, description="Whether rule is active")
    severity: str = Field(default="error", description="Severity (error, warning)")
    business_explanation: str = Field(..., description="Why this rule exists")


class ProcessingLimits(BaseModel):
    """Processing limits and restrictions."""
    
    # File limits
    max_file_size_mb: int = Field(default=10, description="Maximum file size in MB")
    max_rows: int = Field(default=10000, description="Maximum rows per import")
    max_columns: int = Field(default=100, description="Maximum columns allowed")
    
    # Processing limits
    batch_size: int = Field(default=100, description="Records per batch")
    timeout_seconds: int = Field(default=300, description="Processing timeout")
    max_concurrent_imports: int = Field(default=5, description="Max concurrent imports")
    
    # Rate limits
    requests_per_minute: int = Field(default=60, description="API rate limit")
    imports_per_hour: int = Field(default=10, description="Imports per hour limit")
    
    # Retention
    temp_file_retention_hours: int = Field(default=24, description="Temp file retention")
    audit_retention_days: int = Field(default=365, description="Audit log retention")


class SecuritySettings(BaseModel):
    """Security configuration."""
    
    # File security
    allowed_extensions: List[str] = Field(
        default_factory=lambda: [".csv"],
        description="Allowed file extensions"
    )
    allowed_content_types: List[str] = Field(
        default_factory=lambda: ["text/csv", "application/csv", "text/plain"],
        description="Allowed MIME types"
    )
    
    # Content scanning
    enable_malware_scan: bool = Field(default=True, description="Enable malware scanning")
    enable_content_validation: bool = Field(default=True, description="Validate file content")
    block_executable_content: bool = Field(default=True, description="Block executable code")
    block_script_tags: bool = Field(default=True, description="Block script injection")
    
    # Security level
    security_level: SecurityLevel = Field(
        default=SecurityLevel.HIGH,
        description="Overall security level"
    )
    
    # Audit settings
    log_all_operations: bool = Field(default=True, description="Log all operations")
    log_sensitive_data: bool = Field(default=False, description="Log sensitive data")
    require_audit_reason: bool = Field(default=True, description="Require reason for changes")


class RolePermission(BaseModel):
    """Permission configuration for a role."""
    
    role: str = Field(..., description="Role name")
    allowed_actions: List[PermissionAction] = Field(
        default_factory=list,
        description="Allowed actions"
    )
    restrictions: Dict[str, Any] = Field(
        default_factory=dict,
        description="Role-specific restrictions"
    )


class SystemStatus(BaseModel):
    """Current system status."""
    
    is_operational: bool = Field(default=True, description="System operational")
    active_imports: int = Field(default=0, description="Currently active imports")
    queue_depth: int = Field(default=0, description="Jobs in queue")
    
    # Capacity
    capacity_percentage: float = Field(default=0.0, description="Current capacity usage")
    estimated_wait_time_seconds: Optional[int] = Field(None, description="Queue wait time")
    
    # Health
    last_health_check: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last health check"
    )
    database_status: str = Field(default="healthy", description="Database status")
    storage_status: str = Field(default="healthy", description="Storage status")


class ImportConfiguration(BaseModel):
    """Complete import configuration."""
    
    # Identification
    config_version: str = Field(default="1.0.0", description="Config version")
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    
    # Field mappings
    default_mappings: List[FieldMappingDefault] = Field(
        default_factory=list,
        description="Default field mappings"
    )
    
    # Validation rules
    validation_rules: List[ValidationRule] = Field(
        default_factory=list,
        description="Validation rules"
    )
    
    # Limits and security
    processing_limits: ProcessingLimits = Field(
        default_factory=ProcessingLimits,
        description="Processing limits"
    )
    security_settings: SecuritySettings = Field(
        default_factory=SecuritySettings,
        description="Security settings"
    )
    
    # System status
    system_status: SystemStatus = Field(
        default_factory=SystemStatus,
        description="Current system status"
    )


class PermissionsResponse(BaseModel):
    """User's import permissions."""
    
    user_role: str = Field(..., description="User's role")
    allowed_actions: List[PermissionAction] = Field(
        default_factory=list,
        description="Actions user can perform"
    )
    restrictions: Dict[str, Any] = Field(
        default_factory=dict,
        description="User-specific restrictions"
    )
    audit_required: bool = Field(default=True, description="Audit logging required")


class AuditLogEntry(BaseModel):
    """Audit log entry."""
    
    log_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Actor
    user_id: str = Field(..., description="User ID")
    user_role: str = Field(..., description="User role")
    
    # Action
    action: str = Field(..., description="Action performed")
    resource_type: str = Field(..., description="Resource type")
    resource_id: Optional[str] = Field(None, description="Resource ID")
    
    # Context
    ip_address: Optional[str] = Field(None, description="IP address")
    user_agent: Optional[str] = Field(None, description="User agent")
    
    # Result
    success: bool = Field(default=True, description="Action succeeded")
    error_message: Optional[str] = Field(None, description="Error if failed")
    
    # Details
    details: Dict[str, Any] = Field(default_factory=dict, description="Additional details")


# =============================================================================
# Default Configuration
# =============================================================================

DEFAULT_FIELD_MAPPINGS = [
    FieldMappingDefault(
        csv_column_pattern="employee_id|emp_id|id",
        employee_field="employee_id",
        is_required=True,
    ),
    FieldMappingDefault(
        csv_column_pattern="email|work_email|email_address",
        employee_field="email",
        is_required=True,
    ),
    FieldMappingDefault(
        csv_column_pattern="first_name|firstname|given_name",
        employee_field="first_name",
        is_required=True,
    ),
    FieldMappingDefault(
        csv_column_pattern="last_name|lastname|surname|family_name",
        employee_field="last_name",
        is_required=True,
    ),
    FieldMappingDefault(
        csv_column_pattern="hire_date|start_date|hiredate",
        employee_field="hire_date",
        is_required=True,
    ),
    FieldMappingDefault(
        csv_column_pattern="job_title|title|position|role",
        employee_field="job_title",
        is_required=False,
    ),
    FieldMappingDefault(
        csv_column_pattern="department|dept|department_name",
        employee_field="department",
        is_required=False,
    ),
    FieldMappingDefault(
        csv_column_pattern="phone|phone_number|work_phone",
        employee_field="phone_number",
        is_required=False,
    ),
]

DEFAULT_VALIDATION_RULES = [
    ValidationRule(
        rule_id="req_employee_id",
        rule_type=ValidationRuleType.REQUIRED,
        field_name="employee_id",
        error_message="Employee ID is required",
        business_explanation="Each employee must have a unique identifier for system tracking",
    ),
    ValidationRule(
        rule_id="req_email",
        rule_type=ValidationRuleType.REQUIRED,
        field_name="email",
        error_message="Email is required",
        business_explanation="Email is used for authentication and communication",
    ),
    ValidationRule(
        rule_id="fmt_email",
        rule_type=ValidationRuleType.FORMAT,
        field_name="email",
        parameters={"pattern": r"^[^@]+@[^@]+\.[^@]+$"},
        error_message="Invalid email format",
        business_explanation="Email must be valid for system notifications",
    ),
    ValidationRule(
        rule_id="unique_email",
        rule_type=ValidationRuleType.UNIQUE,
        field_name="email",
        error_message="Email address already exists",
        business_explanation="Each employee must have a unique email for identification",
    ),
    ValidationRule(
        rule_id="unique_employee_id",
        rule_type=ValidationRuleType.UNIQUE,
        field_name="employee_id",
        error_message="Employee ID already exists",
        business_explanation="Employee IDs must be unique across the organization",
    ),
    ValidationRule(
        rule_id="fmt_hire_date",
        rule_type=ValidationRuleType.FORMAT,
        field_name="hire_date",
        parameters={"formats": ["YYYY-MM-DD", "MM/DD/YYYY"]},
        error_message="Invalid date format for hire date",
        business_explanation="Hire date is required for tenure calculations and compliance",
    ),
    ValidationRule(
        rule_id="len_first_name",
        rule_type=ValidationRuleType.LENGTH,
        field_name="first_name",
        parameters={"min": 1, "max": 100},
        error_message="First name must be 1-100 characters",
        business_explanation="Name length constraint for database and display compatibility",
    ),
    ValidationRule(
        rule_id="ref_department",
        rule_type=ValidationRuleType.REFERENCE,
        field_name="department",
        parameters={"reference_table": "department"},
        error_message="Department not found in system",
        severity="warning",
        business_explanation="Employees should be assigned to existing departments",
    ),
]

ROLE_PERMISSIONS_CONFIG = {
    UserRole.ADMIN: RolePermission(
        role="admin",
        allowed_actions=list(PermissionAction),
        restrictions={},
    ),
    UserRole.HR_MANAGER: RolePermission(
        role="hr_manager",
        allowed_actions=[
            PermissionAction.UPLOAD,
            PermissionAction.VALIDATE,
            PermissionAction.PREVIEW,
            PermissionAction.EXECUTE,
            PermissionAction.VIEW_ERRORS,
            PermissionAction.VIEW_CONFIG,
        ],
        restrictions={"max_rows_per_import": 5000},
    ),
    UserRole.MANAGER: RolePermission(
        role="manager",
        allowed_actions=[
            PermissionAction.VIEW_CONFIG,
        ],
        restrictions={},
    ),
    UserRole.EMPLOYEE: RolePermission(
        role="employee",
        allowed_actions=[],
        restrictions={},
    ),
}


# =============================================================================
# Helper Functions
# =============================================================================

def get_user_permissions(user_role: UserRole) -> PermissionsResponse:
    """Get permissions for a user role."""
    role_config = ROLE_PERMISSIONS_CONFIG.get(
        user_role,
        ROLE_PERMISSIONS_CONFIG[UserRole.EMPLOYEE]
    )
    
    return PermissionsResponse(
        user_role=user_role.value,
        allowed_actions=role_config.allowed_actions,
        restrictions=role_config.restrictions,
        audit_required=True,
    )


def check_permission(user_role: UserRole, action: PermissionAction) -> bool:
    """Check if user has permission for an action."""
    permissions = get_user_permissions(user_role)
    return action in permissions.allowed_actions


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

employee_import_config_router = APIRouter(
    prefix="/api/employee-import",
    tags=["Employee Import Configuration"],
)


# =============================================================================
# Endpoints
# =============================================================================

@employee_import_config_router.get(
    "/configuration",
    response_model=ImportConfiguration,
    summary="Get Import Configuration",
    description="Get current import configuration including mappings, rules, and limits.",
)
async def get_configuration(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> ImportConfiguration:
    """
    Get import configuration.
    
    - Returns field mapping defaults
    - Includes validation rules with business explanations
    - Shows processing limits and security settings
    - Provides current system status
    """
    user_role = current_user.roles[0] if current_user.roles else UserRole.EMPLOYEE
    
    if not check_permission(user_role, PermissionAction.VIEW_CONFIG):
        raise ForbiddenError(message="You don't have permission to view import configuration")
    
    return ImportConfiguration(
        default_mappings=DEFAULT_FIELD_MAPPINGS,
        validation_rules=DEFAULT_VALIDATION_RULES,
        processing_limits=ProcessingLimits(),
        security_settings=SecuritySettings(),
        system_status=SystemStatus(
            is_operational=True,
            active_imports=2,
            queue_depth=0,
            capacity_percentage=15.0,
        ),
    )


@employee_import_config_router.get(
    "/permissions",
    response_model=PermissionsResponse,
    summary="Get User Permissions",
    description="Get current user's import permissions.",
)
async def get_permissions(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> PermissionsResponse:
    """
    Get user's import permissions.
    
    - Returns allowed actions based on role
    - Shows any role-specific restrictions
    """
    user_role = current_user.roles[0] if current_user.roles else UserRole.EMPLOYEE
    return get_user_permissions(user_role)


@employee_import_config_router.get(
    "/validation-rules",
    summary="Get Validation Rules",
    description="Get all validation rules with explanations.",
)
async def get_validation_rules(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    field_name: Optional[str] = None,
    rule_type: Optional[ValidationRuleType] = None,
) -> Dict[str, Any]:
    """
    Get validation rules.
    
    - Lists all validation rules
    - Filter by field name or rule type
    - Includes business explanations
    """
    rules = DEFAULT_VALIDATION_RULES
    
    if field_name:
        rules = [r for r in rules if r.field_name == field_name]
    
    if rule_type:
        rules = [r for r in rules if r.rule_type == rule_type]
    
    return {
        "rules": [r.model_dump() for r in rules],
        "total_rules": len(rules),
        "rule_types": [t.value for t in ValidationRuleType],
    }


@employee_import_config_router.get(
    "/security-settings",
    response_model=SecuritySettings,
    summary="Get Security Settings",
    description="Get current security configuration.",
)
async def get_security_settings(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> SecuritySettings:
    """
    Get security settings.
    
    - Shows file type restrictions
    - Shows content scanning settings
    - Shows audit configuration
    """
    user_role = current_user.roles[0] if current_user.roles else UserRole.EMPLOYEE
    
    if not check_permission(user_role, PermissionAction.VIEW_CONFIG):
        raise ForbiddenError(message="You don't have permission to view security settings")
    
    return SecuritySettings()


@employee_import_config_router.get(
    "/system-status",
    response_model=SystemStatus,
    summary="Get System Status",
    description="Get current system status and capacity.",
)
async def get_system_status(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> SystemStatus:
    """
    Get system status.
    
    - Shows operational status
    - Shows current capacity usage
    - Shows queue information
    """
    return SystemStatus(
        is_operational=True,
        active_imports=2,
        queue_depth=0,
        capacity_percentage=15.0,
        estimated_wait_time_seconds=None,
        database_status="healthy",
        storage_status="healthy",
    )


@employee_import_config_router.get(
    "/audit-log",
    summary="Get Audit Log",
    description="Get import audit log entries.",
)
async def get_audit_log(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """
    Get audit log entries.
    
    - Returns recent import operations
    - Includes user, action, and result details
    - Supports pagination
    """
    user_role = current_user.roles[0] if current_user.roles else UserRole.EMPLOYEE
    
    if user_role not in [UserRole.ADMIN, UserRole.HR_MANAGER]:
        raise ForbiddenError(message="Only admins and HR managers can view audit logs")
    
    # Mock audit entries
    entries = [
        AuditLogEntry(
            user_id=str(current_user.id),
            user_role=user_role.value,
            action="view_configuration",
            resource_type="import_config",
            success=True,
        ),
    ]
    
    return {
        "entries": [e.model_dump() for e in entries],
        "total": len(entries),
        "limit": limit,
        "offset": offset,
    }

