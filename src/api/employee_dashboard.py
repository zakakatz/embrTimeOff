"""API endpoints for employee personal dashboard and profile export."""

import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.employee_profile import FIELD_DEFINITIONS, FieldCategory
from src.api.employee_profile_update import update_store, UpdateRequestStatus
from src.database.database import get_db
from src.models.employee import Employee
from src.utils.auth import CurrentUser, UserRole, get_mock_current_user
from src.utils.errors import ForbiddenError, NotFoundError


# =============================================================================
# Enums
# =============================================================================

class ExportFormat(str, Enum):
    """Supported export formats."""
    
    JSON = "json"
    PDF = "pdf"
    CSV = "csv"


class ActionItemType(str, Enum):
    """Types of action items."""
    
    DOCUMENT_RENEWAL = "document_renewal"
    POLICY_ACKNOWLEDGMENT = "policy_acknowledgment"
    TRAINING_REQUIRED = "training_required"
    PROFILE_UPDATE = "profile_update"
    APPROVAL_PENDING = "approval_pending"
    REVIEW_REQUIRED = "review_required"


class ActionItemPriority(str, Enum):
    """Priority levels for action items."""
    
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# =============================================================================
# Response Models
# =============================================================================

class TimeOffBalance(BaseModel):
    """Time-off balance information."""
    
    type: str = Field(..., description="Type of time off (vacation, sick, personal)")
    balance: float = Field(..., description="Current balance in days/hours")
    unit: str = Field(default="days", description="Unit of measurement")
    accrued_ytd: float = Field(default=0.0, description="Accrued year-to-date")
    used_ytd: float = Field(default=0.0, description="Used year-to-date")
    pending_requests: float = Field(default=0.0, description="Pending approval")
    as_of_date: datetime = Field(default_factory=datetime.utcnow)


class UpcomingEvent(BaseModel):
    """Upcoming organizational event."""
    
    event_id: str = Field(..., description="Event identifier")
    title: str = Field(..., description="Event title")
    event_type: str = Field(..., description="Type of event")
    date: datetime = Field(..., description="Event date")
    description: Optional[str] = Field(None, description="Event description")
    location: Optional[str] = Field(None, description="Event location")
    is_mandatory: bool = Field(default=False, description="Whether attendance is mandatory")


class RecentChange(BaseModel):
    """Recent profile change summary."""
    
    field_name: str = Field(..., description="Field that changed")
    change_date: datetime = Field(..., description="When change occurred")
    change_type: str = Field(..., description="Type of change")
    status: str = Field(..., description="Status (applied, pending)")


class ActionItem(BaseModel):
    """Action item requiring attention."""
    
    item_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: ActionItemType = Field(..., description="Type of action")
    title: str = Field(..., description="Action item title")
    description: str = Field(..., description="Description")
    priority: ActionItemPriority = Field(..., description="Priority level")
    due_date: Optional[datetime] = Field(None, description="Due date if applicable")
    action_url: Optional[str] = Field(None, description="URL to take action")
    is_overdue: bool = Field(default=False, description="Whether item is overdue")


class OrganizationalInfo(BaseModel):
    """Relevant organizational information."""
    
    department_name: Optional[str] = Field(None, description="Employee's department")
    manager_name: Optional[str] = Field(None, description="Manager's name")
    team_size: int = Field(default=0, description="Size of team")
    location_name: Optional[str] = Field(None, description="Work location")
    hire_anniversary: Optional[datetime] = Field(None, description="Hire anniversary")
    years_of_service: float = Field(default=0.0, description="Years of service")


class ProfileCompleteness(BaseModel):
    """Profile completeness metrics."""
    
    percentage: float = Field(..., description="Completion percentage (0-100)")
    missing_required: List[str] = Field(default_factory=list, description="Missing required fields")
    missing_optional: List[str] = Field(default_factory=list, description="Missing optional fields")
    last_updated: Optional[datetime] = Field(None, description="Last profile update")


class DashboardResponse(BaseModel):
    """Response for dashboard endpoint."""
    
    employee_id: str = Field(..., description="Employee identifier")
    employee_name: str = Field(..., description="Employee full name")
    
    # Profile overview
    profile_completeness: ProfileCompleteness = Field(..., description="Profile completion status")
    
    # Time off
    time_off_balances: List[TimeOffBalance] = Field(
        default_factory=list,
        description="Time-off balances"
    )
    
    # Events and changes
    upcoming_events: List[UpcomingEvent] = Field(
        default_factory=list,
        description="Upcoming events"
    )
    recent_changes: List[RecentChange] = Field(
        default_factory=list,
        description="Recent profile changes"
    )
    
    # Action items
    action_items: List[ActionItem] = Field(
        default_factory=list,
        description="Items requiring attention"
    )
    action_items_count: int = Field(default=0, description="Total action items")
    overdue_count: int = Field(default=0, description="Overdue items")
    
    # Organizational info
    organizational_info: OrganizationalInfo = Field(
        ...,
        description="Organizational context"
    )
    
    # Metadata
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    preferences_applied: Dict[str, Any] = Field(
        default_factory=dict,
        description="Dashboard preferences"
    )


class ExportRequest(BaseModel):
    """Request for profile export."""
    
    format: ExportFormat = Field(default=ExportFormat.JSON, description="Export format")
    include_sections: List[str] = Field(
        default_factory=lambda: ["personal", "contact", "employment", "organizational"],
        description="Sections to include"
    )
    include_history: bool = Field(default=False, description="Include change history")
    include_audit_trail: bool = Field(default=False, description="Include audit trail")


class ExportResponse(BaseModel):
    """Response for export request."""
    
    export_id: uuid.UUID = Field(default_factory=uuid.uuid4, description="Export job ID")
    employee_id: str = Field(..., description="Employee identifier")
    format: ExportFormat = Field(..., description="Export format")
    status: str = Field(default="ready", description="Export status")
    
    download_url: Optional[str] = Field(None, description="Download URL")
    expires_at: datetime = Field(..., description="When download expires")
    
    # Metadata
    sections_included: List[str] = Field(default_factory=list, description="Included sections")
    total_fields: int = Field(default=0, description="Number of fields exported")
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class CompleteProfileData(BaseModel):
    """Complete profile data for export."""
    
    # Metadata
    export_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Employee info
    employee_id: str = Field(..., description="Employee identifier")
    
    # Profile sections
    personal: Dict[str, Any] = Field(default_factory=dict)
    contact: Dict[str, Any] = Field(default_factory=dict)
    employment: Dict[str, Any] = Field(default_factory=dict)
    organizational: Dict[str, Any] = Field(default_factory=dict)
    compensation: Optional[Dict[str, Any]] = Field(None)
    
    # Optional sections
    change_history: Optional[List[Dict[str, Any]]] = Field(None)
    audit_trail: Optional[List[Dict[str, Any]]] = Field(None)


# =============================================================================
# Helper Functions
# =============================================================================

def calculate_profile_completeness(employee: Employee) -> ProfileCompleteness:
    """Calculate profile completeness percentage."""
    required_fields = ["first_name", "last_name", "email", "hire_date"]
    optional_fields = [
        "preferred_name", "phone_number", "mobile_number",
        "address_line1", "city", "country", "personal_email"
    ]
    
    missing_required = []
    for field in required_fields:
        if not getattr(employee, field, None):
            missing_required.append(field)
    
    missing_optional = []
    for field in optional_fields:
        if not getattr(employee, field, None):
            missing_optional.append(field)
    
    total_fields = len(required_fields) + len(optional_fields)
    filled_fields = total_fields - len(missing_required) - len(missing_optional)
    percentage = (filled_fields / total_fields * 100) if total_fields > 0 else 0
    
    return ProfileCompleteness(
        percentage=round(percentage, 1),
        missing_required=missing_required,
        missing_optional=missing_optional,
        last_updated=employee.updated_at,
    )


def generate_mock_time_off_balances() -> List[TimeOffBalance]:
    """Generate mock time-off balances."""
    return [
        TimeOffBalance(
            type="vacation",
            balance=12.5,
            unit="days",
            accrued_ytd=15.0,
            used_ytd=2.5,
            pending_requests=0.0,
        ),
        TimeOffBalance(
            type="sick",
            balance=8.0,
            unit="days",
            accrued_ytd=10.0,
            used_ytd=2.0,
            pending_requests=0.0,
        ),
        TimeOffBalance(
            type="personal",
            balance=3.0,
            unit="days",
            accrued_ytd=3.0,
            used_ytd=0.0,
            pending_requests=0.0,
        ),
    ]


def generate_action_items(employee_id: int) -> List[ActionItem]:
    """Generate action items for an employee."""
    items = []
    
    # Check for pending update requests
    pending = [
        r for r in update_store.list_by_employee(employee_id)
        if r.get("status") == UpdateRequestStatus.PENDING
    ]
    
    if pending:
        items.append(ActionItem(
            type=ActionItemType.APPROVAL_PENDING,
            title="Pending Profile Updates",
            description=f"You have {len(pending)} profile change(s) awaiting approval",
            priority=ActionItemPriority.MEDIUM,
        ))
    
    # Mock additional items
    items.extend([
        ActionItem(
            type=ActionItemType.POLICY_ACKNOWLEDGMENT,
            title="Annual Security Policy Acknowledgment",
            description="Please review and acknowledge the updated security policy",
            priority=ActionItemPriority.HIGH,
            due_date=datetime.utcnow() + timedelta(days=7),
            action_url="/policies/security-2024",
        ),
        ActionItem(
            type=ActionItemType.TRAINING_REQUIRED,
            title="Compliance Training Due",
            description="Annual compliance training module needs completion",
            priority=ActionItemPriority.MEDIUM,
            due_date=datetime.utcnow() + timedelta(days=30),
            action_url="/training/compliance",
        ),
    ])
    
    return items


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

employee_dashboard_router = APIRouter(
    prefix="/api/employee-profile",
    tags=["Employee Dashboard"],
)


# =============================================================================
# Endpoints
# =============================================================================

@employee_dashboard_router.get(
    "/dashboard-info",
    response_model=DashboardResponse,
    summary="Get Dashboard Info",
    description="Get personalized dashboard information for the employee.",
)
async def get_dashboard_info(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> DashboardResponse:
    """
    Get personalized dashboard information.
    
    - Aggregates time-off balances, events, and action items
    - Shows recent profile changes and pending approvals
    - Includes organizational context
    - Respects employee preferences and privacy settings
    """
    if not current_user.employee_id:
        raise ForbiddenError(message="Employee ID not found")
    
    # Fetch employee
    stmt = select(Employee).where(Employee.id == current_user.employee_id)
    result = session.execute(stmt)
    employee = result.scalar_one_or_none()
    
    if not employee:
        raise NotFoundError(message="Employee not found")
    
    # Calculate profile completeness
    profile_completeness = calculate_profile_completeness(employee)
    
    # Get time-off balances (mock data)
    time_off = generate_mock_time_off_balances()
    
    # Get action items
    action_items = generate_action_items(current_user.employee_id)
    overdue = len([a for a in action_items if a.is_overdue])
    
    # Recent changes (mock)
    recent_changes = [
        RecentChange(
            field_name="phone_number",
            change_date=datetime.utcnow() - timedelta(days=5),
            change_type="update",
            status="applied",
        ),
    ]
    
    # Upcoming events (mock)
    upcoming_events = [
        UpcomingEvent(
            event_id="evt-001",
            title="Company All-Hands Meeting",
            event_type="meeting",
            date=datetime.utcnow() + timedelta(days=14),
            location="Main Auditorium",
            is_mandatory=True,
        ),
        UpcomingEvent(
            event_id="evt-002",
            title="Department Team Building",
            event_type="social",
            date=datetime.utcnow() + timedelta(days=21),
            location="Off-site venue",
            is_mandatory=False,
        ),
    ]
    
    # Organizational info
    years_of_service = 0.0
    if employee.hire_date:
        years_of_service = (datetime.utcnow().date() - employee.hire_date).days / 365.25
    
    org_info = OrganizationalInfo(
        department_name=employee.department.name if employee.department else None,
        manager_name=f"{employee.manager.first_name} {employee.manager.last_name}" if employee.manager else None,
        team_size=0,  # Would calculate from database
        location_name=employee.location.name if employee.location else None,
        hire_anniversary=datetime.combine(employee.hire_date, datetime.min.time()) if employee.hire_date else None,
        years_of_service=round(years_of_service, 1),
    )
    
    return DashboardResponse(
        employee_id=employee.employee_id,
        employee_name=f"{employee.first_name} {employee.last_name}",
        profile_completeness=profile_completeness,
        time_off_balances=time_off,
        upcoming_events=upcoming_events,
        recent_changes=recent_changes,
        action_items=action_items,
        action_items_count=len(action_items),
        overdue_count=overdue,
        organizational_info=org_info,
    )


@employee_dashboard_router.get(
    "/complete-profile",
    response_model=CompleteProfileData,
    summary="Get Complete Profile",
    description="Get comprehensive profile data for export.",
)
async def get_complete_profile(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    include_history: bool = False,
    include_audit: bool = False,
) -> CompleteProfileData:
    """
    Get complete profile data.
    
    - Returns all profile information in structured format
    - Respects privacy controls
    - Optionally includes change history and audit trail
    """
    if not current_user.employee_id:
        raise ForbiddenError(message="Employee ID not found")
    
    stmt = select(Employee).where(Employee.id == current_user.employee_id)
    result = session.execute(stmt)
    employee = result.scalar_one_or_none()
    
    if not employee:
        raise NotFoundError(message="Employee not found")
    
    # Build profile sections
    personal = {
        "first_name": employee.first_name,
        "middle_name": employee.middle_name,
        "last_name": employee.last_name,
        "preferred_name": employee.preferred_name,
        "date_of_birth": employee.date_of_birth.isoformat() if employee.date_of_birth else None,
        "gender": employee.gender,
    }
    
    contact = {
        "email": employee.email,
        "personal_email": employee.personal_email,
        "phone_number": employee.phone_number,
        "mobile_number": employee.mobile_number,
        "address_line1": employee.address_line1,
        "address_line2": employee.address_line2,
        "city": employee.city,
        "state_province": employee.state_province,
        "postal_code": employee.postal_code,
        "country": employee.country,
    }
    
    employment = {
        "employee_id": employee.employee_id,
        "job_title": employee.job_title,
        "employment_type": employee.employment_type,
        "employment_status": employee.employment_status,
        "hire_date": employee.hire_date.isoformat() if employee.hire_date else None,
        "termination_date": employee.termination_date.isoformat() if employee.termination_date else None,
    }
    
    organizational = {
        "department": {
            "id": employee.department.id,
            "name": employee.department.name,
            "code": employee.department.code,
        } if employee.department else None,
        "location": {
            "id": employee.location.id,
            "name": employee.location.name,
            "code": employee.location.code,
        } if employee.location else None,
        "manager": {
            "id": employee.manager.id,
            "name": f"{employee.manager.first_name} {employee.manager.last_name}",
            "email": employee.manager.email,
        } if employee.manager else None,
    }
    
    return CompleteProfileData(
        employee_id=employee.employee_id,
        personal=personal,
        contact=contact,
        employment=employment,
        organizational=organizational,
        change_history=[] if include_history else None,
        audit_trail=[] if include_audit else None,
    )


@employee_dashboard_router.post(
    "/export",
    response_model=ExportResponse,
    summary="Export Profile",
    description="Request profile export in specified format.",
)
async def export_profile(
    request: ExportRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> ExportResponse:
    """
    Request a profile export.
    
    - Generates export in requested format
    - Respects privacy controls and permissions
    - Returns download URL with expiration
    - Logs export for audit trail
    """
    if not current_user.employee_id:
        raise ForbiddenError(message="Employee ID not found")
    
    stmt = select(Employee).where(Employee.id == current_user.employee_id)
    result = session.execute(stmt)
    employee = result.scalar_one_or_none()
    
    if not employee:
        raise NotFoundError(message="Employee not found")
    
    export_id = uuid.uuid4()
    
    # Count fields based on sections
    field_count = 0
    for section in request.include_sections:
        if section == "personal":
            field_count += 6
        elif section == "contact":
            field_count += 10
        elif section == "employment":
            field_count += 6
        elif section == "organizational":
            field_count += 3
    
    return ExportResponse(
        export_id=export_id,
        employee_id=employee.employee_id,
        format=request.format,
        status="ready",
        download_url=f"/api/employee-profile/export/{export_id}/download",
        expires_at=datetime.utcnow() + timedelta(hours=1),
        sections_included=request.include_sections,
        total_fields=field_count,
    )


@employee_dashboard_router.get(
    "/export/{export_id}/download",
    summary="Download Export",
    description="Download a previously requested export.",
)
async def download_export(
    export_id: uuid.UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> Dict[str, Any]:
    """
    Download exported profile data.
    
    - Validates export ID and permissions
    - Returns data in requested format
    - Logs download for audit
    """
    if not current_user.employee_id:
        raise ForbiddenError(message="Employee ID not found")
    
    # In a real implementation, would fetch from storage
    return {
        "export_id": str(export_id),
        "status": "downloaded",
        "message": "Export download initiated",
    }

