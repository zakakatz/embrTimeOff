"""API endpoints for employee profile update history and audit trail."""

import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.employee_profile import FieldCategory, FIELD_DEFINITIONS
from src.api.employee_profile_update import update_store, UpdateRequestStatus
from src.database.database import get_db
from src.utils.auth import CurrentUser, UserRole, get_mock_current_user
from src.utils.errors import ForbiddenError, NotFoundError


# =============================================================================
# Enums
# =============================================================================

class ChangeStatus(str, Enum):
    """Status of a profile change."""
    
    APPLIED = "applied"           # Successfully applied
    PENDING = "pending"           # Awaiting approval
    APPROVED = "approved"         # Approved and applied
    REJECTED = "rejected"         # Rejected by approver
    CANCELLED = "cancelled"       # Cancelled by employee


class HistorySortField(str, Enum):
    """Fields available for sorting history."""
    
    DATE = "date"
    FIELD = "field"
    STATUS = "status"
    CATEGORY = "category"


class SortOrder(str, Enum):
    """Sort order direction."""
    
    ASC = "asc"
    DESC = "desc"


# =============================================================================
# In-Memory State (would be database in production)
# =============================================================================

class HistoryStore:
    """In-memory store for change history."""
    
    def __init__(self):
        self.history: Dict[int, List[Dict[str, Any]]] = {}
    
    def add(self, employee_id: int, entry: Dict[str, Any]) -> None:
        if employee_id not in self.history:
            self.history[employee_id] = []
        self.history[employee_id].append(entry)
    
    def get(self, employee_id: int) -> List[Dict[str, Any]]:
        return self.history.get(employee_id, [])


history_store = HistoryStore()


# =============================================================================
# Response Models
# =============================================================================

class ApproverInfo(BaseModel):
    """Information about who approved/rejected a change."""
    
    user_id: str = Field(..., description="Approver user ID")
    name: Optional[str] = Field(None, description="Approver name")
    role: str = Field(..., description="Approver role")
    decision: str = Field(..., description="Decision made")
    decision_date: datetime = Field(..., description="When decision was made")
    notes: Optional[str] = Field(None, description="Decision notes")


class HistoryEntry(BaseModel):
    """A single history entry for a profile change."""
    
    entry_id: uuid.UUID = Field(default_factory=uuid.uuid4, description="Unique entry ID")
    
    # Change information
    field_name: str = Field(..., description="Field that was changed")
    field_display_name: str = Field(..., description="Human-readable field name")
    field_category: FieldCategory = Field(..., description="Field category")
    
    # Values
    previous_value: Optional[Any] = Field(None, description="Value before change")
    new_value: Any = Field(..., description="New/requested value")
    
    # Status and timing
    status: ChangeStatus = Field(..., description="Change status")
    change_date: datetime = Field(..., description="When change was made/requested")
    effective_date: Optional[datetime] = Field(None, description="When change took effect")
    
    # Attribution
    changed_by: str = Field(..., description="Who made the change")
    changed_by_name: Optional[str] = Field(None, description="Name of person who made change")
    change_method: str = Field(
        default="self_service",
        description="How change was made (self_service, admin, import)"
    )
    change_reason: Optional[str] = Field(None, description="Reason for change")
    
    # Approval information (if applicable)
    requires_approval: bool = Field(default=False, description="Whether change required approval")
    approval_info: Optional[ApproverInfo] = Field(None, description="Approval details")
    
    # Audit metadata
    ip_address: Optional[str] = Field(None, description="IP address of requester")
    user_agent: Optional[str] = Field(None, description="User agent")


class PendingChange(BaseModel):
    """A pending change awaiting approval."""
    
    request_id: uuid.UUID = Field(..., description="Update request ID")
    field_name: str = Field(..., description="Field being changed")
    field_display_name: str = Field(..., description="Human-readable field name")
    current_value: Optional[Any] = Field(None, description="Current value")
    requested_value: Any = Field(..., description="Requested new value")
    requested_at: datetime = Field(..., description="When request was made")
    reason: Optional[str] = Field(None, description="Reason for change")
    
    # Approval status
    status: str = Field(default="pending", description="Approval status")
    approver_role: str = Field(..., description="Role that can approve")
    expected_review_by: Optional[datetime] = Field(None, description="Expected review date")


class HistorySummary(BaseModel):
    """Summary of profile change history."""
    
    total_changes: int = Field(default=0, description="Total changes")
    changes_this_month: int = Field(default=0, description="Changes in current month")
    pending_changes: int = Field(default=0, description="Pending approval requests")
    rejected_changes: int = Field(default=0, description="Rejected requests (last 90 days)")
    
    most_changed_fields: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Fields with most changes"
    )
    changes_by_category: Dict[str, int] = Field(
        default_factory=dict,
        description="Change count by category"
    )


class HistoryFilters(BaseModel):
    """Filters applied to history query."""
    
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    field_categories: Optional[List[str]] = None
    change_statuses: Optional[List[str]] = None
    requires_approval: Optional[bool] = None


class UpdateHistoryResponse(BaseModel):
    """Response for update history endpoint."""
    
    employee_id: str = Field(..., description="Employee identifier")
    
    # History entries
    history: List[HistoryEntry] = Field(default_factory=list, description="Change history")
    
    # Pending changes
    pending_changes: List[PendingChange] = Field(
        default_factory=list,
        description="Pending approval requests"
    )
    
    # Summary
    summary: HistorySummary = Field(..., description="History summary")
    
    # Pagination
    total_entries: int = Field(default=0, description="Total history entries")
    page: int = Field(default=1, description="Current page")
    page_size: int = Field(default=50, description="Entries per page")
    has_more: bool = Field(default=False, description="More entries available")
    
    # Filters applied
    filters_applied: HistoryFilters = Field(
        default_factory=HistoryFilters,
        description="Filters that were applied"
    )
    
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class AuditExportRequest(BaseModel):
    """Request for audit data export."""
    
    date_from: datetime = Field(..., description="Start date for export")
    date_to: datetime = Field(..., description="End date for export")
    format: str = Field(default="json", description="Export format (json, csv)")
    include_details: bool = Field(default=True, description="Include full change details")


class AuditExportResponse(BaseModel):
    """Response for audit export."""
    
    export_id: uuid.UUID = Field(default_factory=uuid.uuid4, description="Export job ID")
    status: str = Field(default="ready", description="Export status")
    record_count: int = Field(default=0, description="Number of records")
    download_url: Optional[str] = Field(None, description="Download URL")
    expires_at: datetime = Field(..., description="When download expires")


# =============================================================================
# Helper Functions
# =============================================================================

def get_field_display_name(field_name: str) -> str:
    """Get human-readable field name."""
    field_def = FIELD_DEFINITIONS.get(field_name, {})
    return field_def.get("display", field_name.replace("_", " ").title())


def get_field_category(field_name: str) -> FieldCategory:
    """Get field category."""
    field_def = FIELD_DEFINITIONS.get(field_name, {})
    return field_def.get("category", FieldCategory.CUSTOM)


def generate_mock_history(employee_id: int) -> List[HistoryEntry]:
    """Generate mock history entries for development."""
    entries = []
    base_time = datetime.utcnow()
    
    # Sample history entries
    sample_changes = [
        {"field": "preferred_name", "old": None, "new": "John", "days_ago": 5},
        {"field": "phone_number", "old": "+1-555-0100", "new": "+1-555-0123", "days_ago": 15},
        {"field": "address_line1", "old": "123 Main St", "new": "456 Oak Ave", "days_ago": 30},
        {"field": "personal_email", "old": "john@old.com", "new": "john@new.com", "days_ago": 45},
    ]
    
    for change in sample_changes:
        entries.append(HistoryEntry(
            field_name=change["field"],
            field_display_name=get_field_display_name(change["field"]),
            field_category=get_field_category(change["field"]),
            previous_value=change["old"],
            new_value=change["new"],
            status=ChangeStatus.APPLIED,
            change_date=base_time - timedelta(days=change["days_ago"]),
            effective_date=base_time - timedelta(days=change["days_ago"]),
            changed_by=str(employee_id),
            change_method="self_service",
        ))
    
    return entries


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

employee_profile_history_router = APIRouter(
    prefix="/api/employee-profile",
    tags=["Employee Profile History"],
)


# =============================================================================
# Endpoints
# =============================================================================

@employee_profile_history_router.get(
    "/update-history",
    response_model=UpdateHistoryResponse,
    summary="Get Update History",
    description="Get comprehensive history of profile changes.",
)
async def get_update_history(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    # Pagination
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    # Sorting
    sort_by: HistorySortField = HistorySortField.DATE,
    sort_order: SortOrder = SortOrder.DESC,
    # Filters
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    field_category: Optional[str] = None,
    change_status: Optional[str] = None,
    requires_approval: Optional[bool] = None,
) -> UpdateHistoryResponse:
    """
    Get profile update history for the authenticated employee.
    
    - Returns detailed change history with audit information
    - Includes pending approval requests
    - Supports filtering by date, category, and status
    - Provides summary statistics
    """
    if not current_user.employee_id:
        raise ForbiddenError(message="Employee ID not found")
    
    employee_id = current_user.employee_id
    
    # Get history from store (or generate mock)
    stored_history = history_store.get(employee_id)
    if not stored_history:
        all_history = generate_mock_history(employee_id)
    else:
        all_history = [HistoryEntry(**h) for h in stored_history]
    
    # Get pending changes from update store
    pending_requests = update_store.list_by_employee(employee_id)
    pending_changes = [
        PendingChange(
            request_id=uuid.UUID(r["request_id"]),
            field_name=r["field_name"],
            field_display_name=get_field_display_name(r["field_name"]),
            current_value=r.get("old_value"),
            requested_value=r["new_value"],
            requested_at=r["requested_at"],
            reason=r.get("reason"),
            status=r["status"].value if isinstance(r["status"], UpdateRequestStatus) else r["status"],
            approver_role="HR_MANAGER",
            expected_review_by=r["requested_at"] + timedelta(days=3),
        )
        for r in pending_requests
        if r.get("status") == UpdateRequestStatus.PENDING
    ]
    
    # Apply filters
    filtered_history = all_history
    
    if date_from:
        filtered_history = [h for h in filtered_history if h.change_date >= date_from]
    
    if date_to:
        filtered_history = [h for h in filtered_history if h.change_date <= date_to]
    
    if field_category:
        try:
            cat = FieldCategory(field_category)
            filtered_history = [h for h in filtered_history if h.field_category == cat]
        except ValueError:
            pass
    
    if change_status:
        try:
            status = ChangeStatus(change_status)
            filtered_history = [h for h in filtered_history if h.status == status]
        except ValueError:
            pass
    
    if requires_approval is not None:
        filtered_history = [h for h in filtered_history if h.requires_approval == requires_approval]
    
    # Sort
    reverse = sort_order == SortOrder.DESC
    if sort_by == HistorySortField.DATE:
        filtered_history.sort(key=lambda h: h.change_date, reverse=reverse)
    elif sort_by == HistorySortField.FIELD:
        filtered_history.sort(key=lambda h: h.field_name, reverse=reverse)
    elif sort_by == HistorySortField.STATUS:
        filtered_history.sort(key=lambda h: h.status.value, reverse=reverse)
    elif sort_by == HistorySortField.CATEGORY:
        filtered_history.sort(key=lambda h: h.field_category.value, reverse=reverse)
    
    # Calculate summary
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    ninety_days_ago = now - timedelta(days=90)
    
    # Count by category
    by_category: Dict[str, int] = {}
    for entry in filtered_history:
        cat = entry.field_category.value
        by_category[cat] = by_category.get(cat, 0) + 1
    
    # Count by field
    field_counts: Dict[str, int] = {}
    for entry in filtered_history:
        field_counts[entry.field_name] = field_counts.get(entry.field_name, 0) + 1
    
    most_changed = sorted(
        [{"field": k, "display": get_field_display_name(k), "count": v} for k, v in field_counts.items()],
        key=lambda x: x["count"],
        reverse=True,
    )[:5]
    
    summary = HistorySummary(
        total_changes=len(filtered_history),
        changes_this_month=len([h for h in filtered_history if h.change_date >= month_start]),
        pending_changes=len(pending_changes),
        rejected_changes=len([
            h for h in filtered_history
            if h.status == ChangeStatus.REJECTED and h.change_date >= ninety_days_ago
        ]),
        most_changed_fields=most_changed,
        changes_by_category=by_category,
    )
    
    # Paginate
    total = len(filtered_history)
    start = (page - 1) * page_size
    end = start + page_size
    page_history = filtered_history[start:end]
    
    # Build filters applied
    filters_applied = HistoryFilters(
        date_from=date_from,
        date_to=date_to,
        field_categories=[field_category] if field_category else None,
        change_statuses=[change_status] if change_status else None,
        requires_approval=requires_approval,
    )
    
    return UpdateHistoryResponse(
        employee_id=str(employee_id),
        history=page_history,
        pending_changes=pending_changes,
        summary=summary,
        total_entries=total,
        page=page,
        page_size=page_size,
        has_more=end < total,
        filters_applied=filters_applied,
    )


@employee_profile_history_router.get(
    "/update-history/{entry_id}",
    response_model=HistoryEntry,
    summary="Get History Entry",
    description="Get details of a specific history entry.",
)
async def get_history_entry(
    entry_id: uuid.UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> HistoryEntry:
    """
    Get detailed information about a specific history entry.
    """
    if not current_user.employee_id:
        raise ForbiddenError(message="Employee ID not found")
    
    # In a real implementation, would fetch from database
    # For now, return a mock entry
    return HistoryEntry(
        entry_id=entry_id,
        field_name="phone_number",
        field_display_name="Phone Number",
        field_category=FieldCategory.CONTACT,
        previous_value="+1-555-0100",
        new_value="+1-555-0123",
        status=ChangeStatus.APPLIED,
        change_date=datetime.utcnow() - timedelta(days=5),
        effective_date=datetime.utcnow() - timedelta(days=5),
        changed_by=str(current_user.id),
        change_method="self_service",
    )


@employee_profile_history_router.post(
    "/audit-export",
    response_model=AuditExportResponse,
    summary="Export Audit Data",
    description="Export audit data for compliance reporting.",
)
async def export_audit_data(
    request: AuditExportRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> AuditExportResponse:
    """
    Export audit data for a date range.
    
    - Generates export in requested format
    - Returns download URL
    - Respects employee privacy boundaries
    """
    if not current_user.employee_id:
        raise ForbiddenError(message="Employee ID not found")
    
    # In a real implementation, would generate actual export
    export_id = uuid.uuid4()
    
    return AuditExportResponse(
        export_id=export_id,
        status="ready",
        record_count=25,  # Mock count
        download_url=f"/api/employee-profile/audit-export/{export_id}/download",
        expires_at=datetime.utcnow() + timedelta(hours=1),
    )


@employee_profile_history_router.get(
    "/pending-approvals",
    summary="Get Pending Approvals",
    description="Get all pending approval requests for the employee.",
)
async def get_pending_approvals(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> Dict[str, Any]:
    """
    Get all pending approval requests.
    
    Quick access to pending changes without full history.
    """
    if not current_user.employee_id:
        raise ForbiddenError(message="Employee ID not found")
    
    pending_requests = update_store.list_by_employee(current_user.employee_id)
    pending = [r for r in pending_requests if r.get("status") == UpdateRequestStatus.PENDING]
    
    return {
        "employee_id": str(current_user.employee_id),
        "pending_count": len(pending),
        "requests": [
            {
                "request_id": r["request_id"],
                "field_name": r["field_name"],
                "field_display_name": get_field_display_name(r["field_name"]),
                "requested_value": r["new_value"],
                "requested_at": r["requested_at"].isoformat(),
                "status": "pending",
            }
            for r in pending
        ],
    }

