"""API endpoints for privacy controls and access management."""

import uuid
from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.models.employee import Employee, Department
from src.utils.auth import CurrentUser, UserRole, get_mock_current_user
from src.utils.errors import ForbiddenError, NotFoundError


# =============================================================================
# Enums
# =============================================================================

class AccessLevel(str, Enum):
    """Access level for employee data."""
    
    PUBLIC = "public"           # Name, title, department
    INTERNAL = "internal"       # Contact info, org relationships
    RESTRICTED = "restricted"   # Sensitive data (compensation, PII)
    CONFIDENTIAL = "confidential"  # Highest sensitivity


class PrivacyPreference(str, Enum):
    """Employee privacy preference."""
    
    PUBLIC = "public"           # Visible to all employees
    DEPARTMENT = "department"   # Visible to same department
    TEAM = "team"               # Visible to direct team only
    MANAGER_ONLY = "manager_only"  # Visible to manager chain only
    PRIVATE = "private"         # Visible only to HR/Admin


class RelationshipType(str, Enum):
    """Type of organizational relationship."""
    
    SELF = "self"
    DIRECT_MANAGER = "direct_manager"
    SKIP_LEVEL_MANAGER = "skip_level_manager"
    DIRECT_REPORT = "direct_report"
    PEER = "peer"
    SAME_DEPARTMENT = "same_department"
    SAME_LOCATION = "same_location"
    NONE = "none"


class AccessDecision(str, Enum):
    """Access decision outcome."""
    
    GRANTED = "granted"
    DENIED = "denied"
    PARTIAL = "partial"
    REQUIRES_APPROVAL = "requires_approval"


# =============================================================================
# Request Models
# =============================================================================

class PrivacyControlsRequest(BaseModel):
    """Request to check privacy controls."""
    
    target_employee_id: int = Field(..., description="Employee being accessed")
    requested_fields: List[str] = Field(
        default_factory=list,
        description="Specific fields being requested",
    )
    access_purpose: Optional[str] = Field(None, description="Reason for access")


# =============================================================================
# Response Models
# =============================================================================

class FieldPermission(BaseModel):
    """Permission for a specific field."""
    
    field_name: str
    access_level: AccessLevel
    can_view: bool = Field(default=False)
    can_edit: bool = Field(default=False)
    masked_value: Optional[str] = Field(None, description="Masked value if partial access")
    reason: Optional[str] = Field(None, description="Reason for restriction")


class OrganizationalRelationship(BaseModel):
    """Relationship between requestor and target."""
    
    relationship_type: RelationshipType
    relationship_strength: float = Field(default=0.0, ge=0.0, le=1.0)
    relationship_path: List[str] = Field(default_factory=list)
    is_same_department: bool = Field(default=False)
    is_same_location: bool = Field(default=False)
    reporting_distance: Optional[int] = Field(None, description="Levels in org hierarchy")


class RoleBasedPermission(BaseModel):
    """Role-based access control analysis."""
    
    role: str
    permissions: List[str] = Field(default_factory=list)
    restricted_fields: List[str] = Field(default_factory=list)
    access_level: AccessLevel


class PolicyRequirement(BaseModel):
    """Policy requirement for access."""
    
    policy_id: str
    policy_name: str
    is_satisfied: bool = Field(default=False)
    requirement_details: str
    failure_reason: Optional[str] = None


class ComplianceCheck(BaseModel):
    """Regulatory compliance check result."""
    
    regulation: str = Field(..., description="Regulation name (e.g., GDPR, CCPA)")
    is_compliant: bool = Field(default=True)
    requirements_met: List[str] = Field(default_factory=list)
    requirements_failed: List[str] = Field(default_factory=list)
    remediation_required: Optional[str] = None


class AccessLogEntry(BaseModel):
    """Entry for access audit log."""
    
    log_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    requestor_id: int
    requestor_name: Optional[str] = None
    target_employee_id: int
    target_employee_name: Optional[str] = None
    access_type: str
    fields_accessed: List[str] = Field(default_factory=list)
    access_decision: AccessDecision
    denial_reason: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class PrivacyControlsResponse(BaseModel):
    """Comprehensive privacy controls response."""
    
    # Access decision
    access_decision: AccessDecision
    access_level: AccessLevel
    
    # Target info (limited based on access)
    target_employee_id: int
    target_employee_name: Optional[str] = None
    
    # Relationship analysis
    organizational_relationship: OrganizationalRelationship
    
    # Role-based permissions
    role_permissions: RoleBasedPermission
    
    # Field-level permissions
    field_permissions: List[FieldPermission] = Field(default_factory=list)
    
    # Policy compliance
    policy_requirements: List[PolicyRequirement] = Field(default_factory=list)
    all_policies_satisfied: bool = Field(default=True)
    
    # Regulatory compliance
    compliance_checks: List[ComplianceCheck] = Field(default_factory=list)
    is_regulatory_compliant: bool = Field(default=True)
    
    # Privacy preferences
    target_privacy_preference: PrivacyPreference = PrivacyPreference.DEPARTMENT
    preference_allows_access: bool = Field(default=True)
    
    # Visibility filtering
    visible_fields: List[str] = Field(default_factory=list)
    hidden_fields: List[str] = Field(default_factory=list)
    masked_fields: List[str] = Field(default_factory=list)
    
    # Audit
    access_logged: bool = Field(default=True)
    audit_log_id: Optional[str] = None
    
    # Metadata
    checked_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = Field(None, description="When this permission check expires")


# =============================================================================
# In-Memory Storage for Demo
# =============================================================================

_access_logs: List[AccessLogEntry] = []
_privacy_preferences: Dict[int, PrivacyPreference] = {}


# =============================================================================
# Helper Functions
# =============================================================================

def determine_relationship(
    requestor_id: int,
    target_id: int,
    session: Session,
) -> OrganizationalRelationship:
    """Determine organizational relationship between two employees."""
    if requestor_id == target_id:
        return OrganizationalRelationship(
            relationship_type=RelationshipType.SELF,
            relationship_strength=1.0,
            relationship_path=["self"],
        )
    
    requestor = session.get(Employee, requestor_id)
    target = session.get(Employee, target_id)
    
    if not requestor or not target:
        return OrganizationalRelationship(
            relationship_type=RelationshipType.NONE,
            relationship_strength=0.0,
        )
    
    # Check if requestor is target's manager
    if target.manager_id == requestor_id:
        return OrganizationalRelationship(
            relationship_type=RelationshipType.DIRECT_MANAGER,
            relationship_strength=0.9,
            relationship_path=["direct_manager"],
            reporting_distance=1,
            is_same_department=requestor.department_id == target.department_id,
            is_same_location=requestor.location_id == target.location_id,
        )
    
    # Check if target is requestor's manager
    if requestor.manager_id == target_id:
        return OrganizationalRelationship(
            relationship_type=RelationshipType.DIRECT_REPORT,
            relationship_strength=0.8,
            relationship_path=["direct_report"],
            reporting_distance=1,
            is_same_department=requestor.department_id == target.department_id,
            is_same_location=requestor.location_id == target.location_id,
        )
    
    # Check same department
    if requestor.department_id == target.department_id:
        # Check if same manager (peers)
        if requestor.manager_id == target.manager_id:
            return OrganizationalRelationship(
                relationship_type=RelationshipType.PEER,
                relationship_strength=0.7,
                relationship_path=["same_manager"],
                is_same_department=True,
                is_same_location=requestor.location_id == target.location_id,
            )
        
        return OrganizationalRelationship(
            relationship_type=RelationshipType.SAME_DEPARTMENT,
            relationship_strength=0.5,
            relationship_path=["same_department"],
            is_same_department=True,
            is_same_location=requestor.location_id == target.location_id,
        )
    
    # Check same location only
    if requestor.location_id == target.location_id:
        return OrganizationalRelationship(
            relationship_type=RelationshipType.SAME_LOCATION,
            relationship_strength=0.3,
            relationship_path=["same_location"],
            is_same_department=False,
            is_same_location=True,
        )
    
    return OrganizationalRelationship(
        relationship_type=RelationshipType.NONE,
        relationship_strength=0.1,
        relationship_path=[],
        is_same_department=False,
        is_same_location=False,
    )


def get_role_permissions(role: UserRole) -> RoleBasedPermission:
    """Get permissions for a role."""
    permissions_map = {
        UserRole.ADMIN: RoleBasedPermission(
            role=role.value,
            permissions=["view_all", "edit_all", "export", "manage_access"],
            restricted_fields=[],
            access_level=AccessLevel.CONFIDENTIAL,
        ),
        UserRole.HR: RoleBasedPermission(
            role=role.value,
            permissions=["view_all", "edit_employee", "export"],
            restricted_fields=["password", "security_questions"],
            access_level=AccessLevel.RESTRICTED,
        ),
        UserRole.MANAGER: RoleBasedPermission(
            role=role.value,
            permissions=["view_team", "view_reports", "approve_requests"],
            restricted_fields=["salary_history", "ssn", "compensation"],
            access_level=AccessLevel.INTERNAL,
        ),
        UserRole.EMPLOYEE: RoleBasedPermission(
            role=role.value,
            permissions=["view_directory", "view_self"],
            restricted_fields=["salary", "ssn", "compensation", "performance_reviews"],
            access_level=AccessLevel.PUBLIC,
        ),
    }
    return permissions_map.get(role, permissions_map[UserRole.EMPLOYEE])


def get_field_permissions(
    role: UserRole,
    relationship: OrganizationalRelationship,
    target_preference: PrivacyPreference,
) -> List[FieldPermission]:
    """Get field-level permissions based on role and relationship."""
    # Define all fields and their default access levels
    fields = {
        "first_name": AccessLevel.PUBLIC,
        "last_name": AccessLevel.PUBLIC,
        "email": AccessLevel.PUBLIC,
        "job_title": AccessLevel.PUBLIC,
        "department": AccessLevel.PUBLIC,
        "location": AccessLevel.PUBLIC,
        "phone_number": AccessLevel.INTERNAL,
        "mobile_number": AccessLevel.INTERNAL,
        "hire_date": AccessLevel.INTERNAL,
        "manager": AccessLevel.INTERNAL,
        "address": AccessLevel.RESTRICTED,
        "date_of_birth": AccessLevel.RESTRICTED,
        "emergency_contact": AccessLevel.RESTRICTED,
        "salary": AccessLevel.CONFIDENTIAL,
        "ssn": AccessLevel.CONFIDENTIAL,
        "bank_account": AccessLevel.CONFIDENTIAL,
        "performance_rating": AccessLevel.CONFIDENTIAL,
    }
    
    permissions = []
    role_perm = get_role_permissions(role)
    
    for field_name, default_level in fields.items():
        can_view = False
        can_edit = False
        reason = None
        
        # Self access
        if relationship.relationship_type == RelationshipType.SELF:
            can_view = True
            can_edit = field_name not in ["ssn", "hire_date", "salary"]
        
        # Admin/HR access
        elif role in [UserRole.ADMIN, UserRole.HR]:
            can_view = True
            can_edit = role == UserRole.ADMIN or field_name not in ["ssn"]
        
        # Manager access
        elif role == UserRole.MANAGER and relationship.relationship_type in [
            RelationshipType.DIRECT_MANAGER,
            RelationshipType.SKIP_LEVEL_MANAGER,
        ]:
            if default_level in [AccessLevel.PUBLIC, AccessLevel.INTERNAL]:
                can_view = True
            elif default_level == AccessLevel.RESTRICTED:
                can_view = True
                reason = "Restricted access for manager"
            else:
                can_view = False
                reason = "Confidential data not accessible"
        
        # Same department
        elif relationship.is_same_department:
            if default_level == AccessLevel.PUBLIC:
                can_view = True
            elif default_level == AccessLevel.INTERNAL:
                can_view = target_preference in [
                    PrivacyPreference.PUBLIC,
                    PrivacyPreference.DEPARTMENT,
                ]
                if not can_view:
                    reason = "Hidden by privacy preference"
        
        # General employee
        else:
            if default_level == AccessLevel.PUBLIC:
                can_view = target_preference != PrivacyPreference.PRIVATE
                if not can_view:
                    reason = "Employee profile is private"
            else:
                reason = "Insufficient access level"
        
        permissions.append(FieldPermission(
            field_name=field_name,
            access_level=default_level,
            can_view=can_view,
            can_edit=can_edit,
            reason=reason,
        ))
    
    return permissions


def check_policy_requirements(
    requestor: Employee,
    target: Employee,
    relationship: OrganizationalRelationship,
) -> List[PolicyRequirement]:
    """Check organizational policy requirements."""
    requirements = []
    
    # Active employee policy
    requirements.append(PolicyRequirement(
        policy_id="POL001",
        policy_name="Active Employee Requirement",
        is_satisfied=requestor.is_active,
        requirement_details="Requestor must be an active employee",
        failure_reason=None if requestor.is_active else "Requestor is not active",
    ))
    
    # Same organization policy
    requirements.append(PolicyRequirement(
        policy_id="POL002",
        policy_name="Same Organization",
        is_satisfied=True,  # In single-org context, always true
        requirement_details="Requestor and target must be in same organization",
    ))
    
    # Legitimate business need
    legitimate_need = (
        relationship.relationship_type != RelationshipType.NONE
        or relationship.is_same_department
        or relationship.is_same_location
    )
    requirements.append(PolicyRequirement(
        policy_id="POL003",
        policy_name="Legitimate Business Need",
        is_satisfied=legitimate_need,
        requirement_details="Access must support legitimate business purpose",
        failure_reason=None if legitimate_need else "No organizational relationship found",
    ))
    
    return requirements


def check_compliance(
    requestor_id: int,
    target_id: int,
    fields_accessed: List[str],
) -> List[ComplianceCheck]:
    """Check regulatory compliance requirements."""
    checks = []
    
    # GDPR-style compliance
    sensitive_fields = {"date_of_birth", "address", "ssn", "bank_account"}
    accessed_sensitive = set(fields_accessed) & sensitive_fields
    
    checks.append(ComplianceCheck(
        regulation="Data Protection (GDPR-style)",
        is_compliant=True,  # Simplified - would involve more complex checks
        requirements_met=["Access logging enabled", "User authenticated"],
        requirements_failed=[],
    ))
    
    # SOX compliance for financial data
    financial_fields = {"salary", "bank_account", "compensation"}
    accessed_financial = set(fields_accessed) & financial_fields
    
    if accessed_financial:
        checks.append(ComplianceCheck(
            regulation="Financial Data Protection (SOX)",
            is_compliant=True,
            requirements_met=["Audit trail created", "Access authenticated"],
            requirements_failed=[],
        ))
    
    return checks


def log_access(
    requestor: CurrentUser,
    target_id: int,
    target_name: Optional[str],
    fields: List[str],
    decision: AccessDecision,
    denial_reason: Optional[str],
    request: Request,
) -> str:
    """Log access for audit purposes."""
    log_entry = AccessLogEntry(
        requestor_id=requestor.employee_id or 0,
        requestor_name=None,  # Would be populated from user context
        target_employee_id=target_id,
        target_employee_name=target_name,
        access_type="directory_view",
        fields_accessed=fields,
        access_decision=decision,
        denial_reason=denial_reason,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    
    _access_logs.append(log_entry)
    return log_entry.log_id


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

privacy_controls_router = APIRouter(
    prefix="/api/employee-directory",
    tags=["Privacy Controls"],
)


# =============================================================================
# Endpoints
# =============================================================================

@privacy_controls_router.get(
    "/privacy-controls",
    response_model=PrivacyControlsResponse,
    summary="Verify Privacy Controls",
    description="Verify access permissions and privacy controls for employee data.",
)
async def verify_privacy_controls(
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    target_employee_id: int = Query(..., description="Target employee ID"),
    requested_fields: Optional[str] = Query(None, description="Comma-separated fields"),
    access_purpose: Optional[str] = Query(None, description="Purpose for access"),
) -> PrivacyControlsResponse:
    """
    Verify privacy controls for accessing employee data.
    
    - Validates organizational relationships
    - Applies role-based access control
    - Checks employee privacy preferences
    - Validates policy requirements
    - Ensures regulatory compliance
    - Logs access for audit
    """
    # Parse requested fields
    fields_list = []
    if requested_fields:
        fields_list = [f.strip() for f in requested_fields.split(",")]
    
    # Get target employee
    target = session.get(Employee, target_employee_id)
    if not target:
        raise NotFoundError(message=f"Employee {target_employee_id} not found")
    
    target_name = f"{target.first_name} {target.last_name}"
    
    # Get requestor
    requestor = None
    if current_user.employee_id:
        requestor = session.get(Employee, current_user.employee_id)
    
    # Determine relationship
    requestor_id = current_user.employee_id or 0
    relationship = determine_relationship(requestor_id, target_employee_id, session)
    
    # Get role permissions
    primary_role = current_user.roles[0] if current_user.roles else UserRole.EMPLOYEE
    role_permissions = get_role_permissions(primary_role)
    
    # Get target's privacy preference
    target_preference = _privacy_preferences.get(
        target_employee_id,
        PrivacyPreference.DEPARTMENT,
    )
    
    # Check if preference allows access
    preference_allows = True
    if target_preference == PrivacyPreference.PRIVATE:
        preference_allows = primary_role in [UserRole.HR, UserRole.ADMIN]
    elif target_preference == PrivacyPreference.MANAGER_ONLY:
        preference_allows = (
            relationship.relationship_type in [
                RelationshipType.SELF,
                RelationshipType.DIRECT_MANAGER,
                RelationshipType.SKIP_LEVEL_MANAGER,
            ]
            or primary_role in [UserRole.HR, UserRole.ADMIN]
        )
    elif target_preference == PrivacyPreference.TEAM:
        preference_allows = (
            relationship.relationship_type in [
                RelationshipType.SELF,
                RelationshipType.DIRECT_MANAGER,
                RelationshipType.DIRECT_REPORT,
                RelationshipType.PEER,
            ]
            or primary_role in [UserRole.HR, UserRole.ADMIN]
        )
    elif target_preference == PrivacyPreference.DEPARTMENT:
        preference_allows = (
            relationship.is_same_department
            or relationship.relationship_type == RelationshipType.SELF
            or primary_role in [UserRole.HR, UserRole.ADMIN, UserRole.MANAGER]
        )
    
    # Get field permissions
    field_permissions = get_field_permissions(
        primary_role,
        relationship,
        target_preference,
    )
    
    # Categorize fields
    visible_fields = [fp.field_name for fp in field_permissions if fp.can_view]
    hidden_fields = [fp.field_name for fp in field_permissions if not fp.can_view]
    masked_fields = []  # Would contain partially visible fields
    
    # Check policy requirements
    policy_requirements = []
    if requestor:
        policy_requirements = check_policy_requirements(requestor, target, relationship)
    all_policies_satisfied = all(pr.is_satisfied for pr in policy_requirements)
    
    # Check compliance
    compliance_checks = check_compliance(
        requestor_id,
        target_employee_id,
        fields_list if fields_list else visible_fields,
    )
    is_compliant = all(cc.is_compliant for cc in compliance_checks)
    
    # Determine access decision
    if not preference_allows:
        access_decision = AccessDecision.DENIED
        denial_reason = "Privacy preference restricts access"
    elif not all_policies_satisfied:
        access_decision = AccessDecision.DENIED
        denial_reason = "Policy requirements not met"
    elif not is_compliant:
        access_decision = AccessDecision.DENIED
        denial_reason = "Compliance requirements not met"
    elif hidden_fields and visible_fields:
        access_decision = AccessDecision.PARTIAL
        denial_reason = None
    elif not visible_fields:
        access_decision = AccessDecision.DENIED
        denial_reason = "No accessible fields"
    else:
        access_decision = AccessDecision.GRANTED
        denial_reason = None
    
    # Log access
    audit_log_id = log_access(
        requestor=current_user,
        target_id=target_employee_id,
        target_name=target_name,
        fields=fields_list if fields_list else visible_fields,
        decision=access_decision,
        denial_reason=denial_reason,
        request=request,
    )
    
    return PrivacyControlsResponse(
        access_decision=access_decision,
        access_level=role_permissions.access_level,
        target_employee_id=target_employee_id,
        target_employee_name=target_name if access_decision != AccessDecision.DENIED else None,
        organizational_relationship=relationship,
        role_permissions=role_permissions,
        field_permissions=field_permissions,
        policy_requirements=policy_requirements,
        all_policies_satisfied=all_policies_satisfied,
        compliance_checks=compliance_checks,
        is_regulatory_compliant=is_compliant,
        target_privacy_preference=target_preference,
        preference_allows_access=preference_allows,
        visible_fields=visible_fields,
        hidden_fields=hidden_fields,
        masked_fields=masked_fields,
        access_logged=True,
        audit_log_id=audit_log_id,
    )


@privacy_controls_router.get(
    "/privacy-controls/audit-log",
    response_model=List[AccessLogEntry],
    summary="Get Access Audit Log",
    description="Retrieve access audit log for compliance monitoring.",
)
async def get_access_audit_log(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    target_employee_id: Optional[int] = Query(None, description="Filter by target"),
    requestor_id: Optional[int] = Query(None, description="Filter by requestor"),
    limit: int = Query(100, ge=1, le=1000),
) -> List[AccessLogEntry]:
    """
    Get access audit log.
    
    Requires HR or Admin role.
    """
    if not any(r in current_user.roles for r in [UserRole.HR, UserRole.ADMIN]):
        raise ForbiddenError(message="Admin or HR access required")
    
    results = _access_logs.copy()
    
    # Apply filters
    if target_employee_id:
        results = [r for r in results if r.target_employee_id == target_employee_id]
    if requestor_id:
        results = [r for r in results if r.requestor_id == requestor_id]
    
    # Sort by timestamp descending
    results.sort(key=lambda x: x.timestamp, reverse=True)
    
    return results[:limit]


@privacy_controls_router.put(
    "/privacy-controls/preferences/{employee_id}",
    summary="Update Privacy Preferences",
    description="Update employee privacy preferences.",
)
async def update_privacy_preferences(
    employee_id: int,
    preference: PrivacyPreference,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> Dict[str, Any]:
    """
    Update privacy preferences for an employee.
    
    Employees can update their own preferences.
    HR/Admin can update any employee's preferences.
    """
    # Check permissions
    if employee_id != current_user.employee_id:
        if not any(r in current_user.roles for r in [UserRole.HR, UserRole.ADMIN]):
            raise ForbiddenError(message="Cannot update other employees' preferences")
    
    # Verify employee exists
    employee = session.get(Employee, employee_id)
    if not employee:
        raise NotFoundError(message=f"Employee {employee_id} not found")
    
    # Update preference
    _privacy_preferences[employee_id] = preference
    
    return {
        "employee_id": employee_id,
        "privacy_preference": preference.value,
        "updated_at": datetime.utcnow().isoformat(),
        "message": "Privacy preference updated successfully",
    }

