"""
Audit Logs API Endpoints

Provides query interface for audit logs with filtering, pagination,
and compliance reporting capabilities.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.services.comprehensive_audit_service import (
    AuditAction,
    AuditCategory,
    AuditSeverity,
    AuditEntry,
    AuditQueryParams,
    AuditQueryResult,
    ComplianceReport,
    SecurityEvent,
    get_audit_service,
)

router = APIRouter(prefix="/api/v1/audit", tags=["Audit"])


# =============================================================================
# Response Models
# =============================================================================

class AuditEntryResponse(BaseModel):
    """API response model for audit entries."""
    
    id: str
    timestamp: datetime
    action: str
    category: str
    severity: str
    user_id: Optional[str] = None
    username: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    changed_fields: List[str] = []
    description: Optional[str] = None
    ip_address: Optional[str] = None
    
    @classmethod
    def from_entry(cls, entry: AuditEntry) -> "AuditEntryResponse":
        return cls(
            id=entry.id,
            timestamp=entry.timestamp,
            action=entry.action.value,
            category=entry.category.value,
            severity=entry.severity.value,
            user_id=entry.user_id,
            username=entry.username,
            entity_type=entry.entity_type,
            entity_id=entry.entity_id,
            changed_fields=entry.changed_fields,
            description=entry.description,
            ip_address=entry.ip_address,
        )


class AuditQueryResponse(BaseModel):
    """Paginated audit query response."""
    
    entries: List[AuditEntryResponse]
    total_count: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool


class AuditEntryDetailResponse(AuditEntryResponse):
    """Detailed audit entry with before/after values."""
    
    before_values: Optional[Dict[str, Any]] = None
    after_values: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = {}
    request_id: Optional[str] = None
    session_id: Optional[str] = None
    user_agent: Optional[str] = None
    checksum: Optional[str] = None
    
    @classmethod
    def from_entry(cls, entry: AuditEntry) -> "AuditEntryDetailResponse":
        return cls(
            id=entry.id,
            timestamp=entry.timestamp,
            action=entry.action.value,
            category=entry.category.value,
            severity=entry.severity.value,
            user_id=entry.user_id,
            username=entry.username,
            entity_type=entry.entity_type,
            entity_id=entry.entity_id,
            changed_fields=entry.changed_fields,
            description=entry.description,
            ip_address=entry.ip_address,
            before_values=entry.before_values,
            after_values=entry.after_values,
            metadata=entry.metadata,
            request_id=entry.request_id,
            session_id=entry.session_id,
            user_agent=entry.user_agent,
            checksum=entry.checksum,
        )


class ComplianceReportResponse(BaseModel):
    """Compliance report response."""
    
    report_id: str
    generated_at: datetime
    report_type: str
    period_start: datetime
    period_end: datetime
    
    total_events: int
    events_by_category: Dict[str, int]
    events_by_action: Dict[str, int]
    events_by_severity: Dict[str, int]
    
    unique_users: int
    most_active_users: List[Dict[str, Any]]
    
    security_events: int
    failed_logins: int
    
    integrity_verified: bool
    integrity_errors: List[str]


class ExportRequest(BaseModel):
    """Request model for audit log export."""
    
    start_date: datetime
    end_date: datetime
    user_id: Optional[str] = None
    entity_type: Optional[str] = None
    action: Optional[str] = None
    category: Optional[str] = None
    format: str = Field(default="json", description="Export format: json or csv")


# =============================================================================
# Endpoints
# =============================================================================

@router.get(
    "/logs",
    response_model=AuditQueryResponse,
    summary="Query audit logs",
    description="Search and filter audit logs with pagination",
)
async def query_audit_logs(
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    username: Optional[str] = Query(None, description="Filter by username"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    entity_id: Optional[str] = Query(None, description="Filter by entity ID"),
    action: Optional[str] = Query(None, description="Filter by action type"),
    category: Optional[str] = Query(None, description="Filter by category"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    start_date: Optional[datetime] = Query(None, description="Start of date range"),
    end_date: Optional[datetime] = Query(None, description="End of date range"),
    search: Optional[str] = Query(None, description="Search in description"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=500, description="Results per page"),
    sort_by: str = Query("timestamp", description="Field to sort by"),
    sort_order: str = Query("desc", description="Sort order: asc or desc"),
) -> AuditQueryResponse:
    """
    Query audit logs with comprehensive filtering.
    
    Supports filtering by:
    - User (ID or username)
    - Entity (type and ID)
    - Action type
    - Category
    - Severity level
    - Date range
    - Free text search
    
    Results are paginated and sorted.
    """
    service = get_audit_service()
    
    # Build query params
    params = AuditQueryParams(
        user_id=user_id,
        username=username,
        entity_type=entity_type,
        entity_id=entity_id,
        action=AuditAction(action) if action else None,
        category=AuditCategory(category) if category else None,
        severity=AuditSeverity(severity) if severity else None,
        start_date=start_date,
        end_date=end_date,
        search_term=search,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    
    result = service.query(params)
    
    return AuditQueryResponse(
        entries=[AuditEntryResponse.from_entry(e) for e in result.entries],
        total_count=result.total_count,
        page=result.page,
        page_size=result.page_size,
        total_pages=result.total_pages,
        has_next=result.has_next,
        has_previous=result.has_previous,
    )


@router.get(
    "/logs/{entry_id}",
    response_model=AuditEntryDetailResponse,
    summary="Get audit entry details",
    description="Get detailed information for a specific audit entry",
)
async def get_audit_entry(entry_id: str) -> AuditEntryDetailResponse:
    """Get detailed audit entry including before/after values."""
    service = get_audit_service()
    entry = service.get_entry(entry_id)
    
    if not entry:
        raise HTTPException(status_code=404, detail="Audit entry not found")
    
    return AuditEntryDetailResponse.from_entry(entry)


@router.get(
    "/entity/{entity_type}/{entity_id}/history",
    response_model=List[AuditEntryResponse],
    summary="Get entity audit history",
    description="Get audit history for a specific entity",
)
async def get_entity_history(
    entity_type: str,
    entity_id: str,
    limit: int = Query(100, ge=1, le=1000),
) -> List[AuditEntryResponse]:
    """Get complete audit history for an entity."""
    service = get_audit_service()
    entries = service.get_entity_history(entity_type, entity_id, limit)
    return [AuditEntryResponse.from_entry(e) for e in entries]


@router.get(
    "/user/{user_id}/activity",
    response_model=List[AuditEntryResponse],
    summary="Get user activity log",
    description="Get audit log of user activities",
)
async def get_user_activity(
    user_id: str,
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
) -> List[AuditEntryResponse]:
    """Get audit log for a specific user."""
    service = get_audit_service()
    entries = service.get_user_activity(user_id, start_date, end_date, limit)
    return [AuditEntryResponse.from_entry(e) for e in entries]


@router.post(
    "/reports/compliance",
    response_model=ComplianceReportResponse,
    summary="Generate compliance report",
    description="Generate a compliance audit report for a date range",
)
async def generate_compliance_report(
    report_type: str = Query(..., description="Type of report"),
    start_date: datetime = Query(..., description="Report start date"),
    end_date: datetime = Query(..., description="Report end date"),
) -> ComplianceReportResponse:
    """
    Generate a compliance audit report.
    
    Includes:
    - Event statistics by category, action, and severity
    - User activity summary
    - Security event summary
    - Data integrity verification
    """
    service = get_audit_service()
    report = service.generate_compliance_report(report_type, start_date, end_date)
    
    return ComplianceReportResponse(
        report_id=report.report_id,
        generated_at=report.generated_at,
        report_type=report.report_type,
        period_start=report.period_start,
        period_end=report.period_end,
        total_events=report.total_events,
        events_by_category=report.events_by_category,
        events_by_action=report.events_by_action,
        events_by_severity=report.events_by_severity,
        unique_users=report.unique_users,
        most_active_users=report.most_active_users,
        security_events=report.security_events,
        failed_logins=report.failed_logins,
        integrity_verified=report.integrity_verified,
        integrity_errors=report.integrity_errors,
    )


@router.post(
    "/export",
    summary="Export audit logs",
    description="Export audit logs in JSON or CSV format",
)
async def export_audit_logs(request: ExportRequest) -> Dict[str, Any]:
    """
    Export audit logs for the specified criteria.
    
    Supports JSON and CSV formats.
    """
    service = get_audit_service()
    
    params = AuditQueryParams(
        start_date=request.start_date,
        end_date=request.end_date,
        user_id=request.user_id,
        entity_type=request.entity_type,
        action=AuditAction(request.action) if request.action else None,
        category=AuditCategory(request.category) if request.category else None,
        page_size=10000,  # Export all matching
    )
    
    output = service.export_audit_log(params, format=request.format)
    
    return {
        "format": request.format,
        "start_date": request.start_date.isoformat(),
        "end_date": request.end_date.isoformat(),
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "data": output if request.format == "json" else None,
        "csv_data": output if request.format == "csv" else None,
    }


@router.get(
    "/statistics",
    summary="Get audit statistics",
    description="Get summary statistics for audit logs",
)
async def get_audit_statistics(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
) -> Dict[str, Any]:
    """Get summary statistics for audit logs."""
    service = get_audit_service()
    
    # Default to last 30 days
    if not end_date:
        end_date = datetime.now(timezone.utc)
    if not start_date:
        from datetime import timedelta
        start_date = end_date - timedelta(days=30)
    
    report = service.generate_compliance_report("statistics", start_date, end_date)
    
    return {
        "period": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
        },
        "total_events": report.total_events,
        "events_by_category": report.events_by_category,
        "events_by_action": report.events_by_action,
        "events_by_severity": report.events_by_severity,
        "unique_users": report.unique_users,
        "security_events": report.security_events,
        "failed_logins": report.failed_logins,
        "data_integrity": {
            "verified": report.integrity_verified,
            "errors": len(report.integrity_errors),
        },
    }


@router.get(
    "/actions",
    summary="List available actions",
    description="Get list of available audit action types",
)
async def list_audit_actions() -> Dict[str, List[str]]:
    """List all available audit action and category types."""
    return {
        "actions": [a.value for a in AuditAction],
        "categories": [c.value for c in AuditCategory],
        "severities": [s.value for s in AuditSeverity],
    }

