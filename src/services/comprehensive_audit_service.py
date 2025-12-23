"""
Comprehensive Audit Logging Service

Provides complete audit trail capabilities for compliance and security monitoring
with tamper-proof logging, cryptographic verification, and efficient querying.
"""

import hashlib
import hmac
import json
import logging
import os
from datetime import datetime, date, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

T = TypeVar("T")


# =============================================================================
# Enums and Constants
# =============================================================================

class AuditAction(str, Enum):
    """Types of auditable actions."""
    
    # CRUD Operations
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    
    # Security Events
    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FAILED = "login_failed"
    PASSWORD_CHANGE = "password_change"
    PASSWORD_RESET = "password_reset"
    MFA_ENABLED = "mfa_enabled"
    MFA_DISABLED = "mfa_disabled"
    
    # Authorization Events
    ACCESS_GRANTED = "access_granted"
    ACCESS_DENIED = "access_denied"
    PERMISSION_CHANGE = "permission_change"
    ROLE_ASSIGNED = "role_assigned"
    ROLE_REVOKED = "role_revoked"
    
    # Data Events
    EXPORT = "export"
    IMPORT = "import"
    ARCHIVE = "archive"
    RESTORE = "restore"
    
    # System Events
    CONFIG_CHANGE = "config_change"
    MAINTENANCE = "maintenance"
    BACKUP = "backup"


class AuditCategory(str, Enum):
    """Categories for audit events."""
    
    SECURITY = "security"
    DATA_ACCESS = "data_access"
    DATA_CHANGE = "data_change"
    SYSTEM = "system"
    COMPLIANCE = "compliance"
    USER_ACTIVITY = "user_activity"


class AuditSeverity(str, Enum):
    """Severity levels for audit events."""
    
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class RetentionPolicy(str, Enum):
    """Log retention policies."""
    
    SHORT = "short"      # 90 days
    STANDARD = "standard"  # 1 year
    EXTENDED = "extended"  # 3 years
    PERMANENT = "permanent"  # Never delete


RETENTION_DAYS = {
    RetentionPolicy.SHORT: 90,
    RetentionPolicy.STANDARD: 365,
    RetentionPolicy.EXTENDED: 1095,
    RetentionPolicy.PERMANENT: None,
}


# =============================================================================
# Models
# =============================================================================

class AuditEntry(BaseModel):
    """A single audit log entry."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Action details
    action: AuditAction
    category: AuditCategory
    severity: AuditSeverity = AuditSeverity.INFO
    
    # User information
    user_id: Optional[str] = None
    username: Optional[str] = None
    user_email: Optional[str] = None
    user_role: Optional[str] = None
    
    # Entity information
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    entity_name: Optional[str] = None
    
    # Change tracking
    before_values: Optional[Dict[str, Any]] = None
    after_values: Optional[Dict[str, Any]] = None
    changed_fields: List[str] = Field(default_factory=list)
    
    # Request context
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    request_id: Optional[str] = None
    session_id: Optional[str] = None
    
    # Additional context
    description: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Integrity
    checksum: Optional[str] = None
    previous_checksum: Optional[str] = None
    
    # Retention
    retention_policy: RetentionPolicy = RetentionPolicy.STANDARD
    expires_at: Optional[datetime] = None


class SecurityEvent(BaseModel):
    """A security-specific audit event."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    event_type: str
    severity: AuditSeverity
    
    # User information
    user_id: Optional[str] = None
    username: Optional[str] = None
    
    # Event details
    success: bool = False
    failure_reason: Optional[str] = None
    
    # Context
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    location: Optional[str] = None
    device_id: Optional[str] = None
    
    # Risk indicators
    is_suspicious: bool = False
    risk_score: Optional[int] = None
    risk_factors: List[str] = Field(default_factory=list)
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AuditQueryParams(BaseModel):
    """Parameters for querying audit logs."""
    
    # Filters
    user_id: Optional[str] = None
    username: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    action: Optional[AuditAction] = None
    category: Optional[AuditCategory] = None
    severity: Optional[AuditSeverity] = None
    
    # Date range
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    
    # Search
    search_term: Optional[str] = None
    
    # Pagination
    page: int = 1
    page_size: int = 50
    
    # Sorting
    sort_by: str = "timestamp"
    sort_order: str = "desc"


class AuditQueryResult(BaseModel):
    """Result of an audit query."""
    
    entries: List[AuditEntry]
    total_count: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool


class ComplianceReport(BaseModel):
    """Compliance audit report."""
    
    report_id: str = Field(default_factory=lambda: str(uuid4()))
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    report_type: str
    period_start: datetime
    period_end: datetime
    
    # Summary statistics
    total_events: int = 0
    events_by_category: Dict[str, int] = Field(default_factory=dict)
    events_by_action: Dict[str, int] = Field(default_factory=dict)
    events_by_severity: Dict[str, int] = Field(default_factory=dict)
    
    # User activity
    unique_users: int = 0
    most_active_users: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Security metrics
    security_events: int = 0
    failed_logins: int = 0
    suspicious_activities: int = 0
    
    # Data integrity
    integrity_verified: bool = True
    integrity_errors: List[str] = Field(default_factory=list)
    
    # Export metadata
    format: str = "json"
    file_path: Optional[str] = None


# =============================================================================
# Integrity Verification
# =============================================================================

class IntegrityVerifier:
    """
    Provides cryptographic integrity verification for audit logs.
    
    Uses HMAC-SHA256 for tamper detection with chained checksums.
    """
    
    def __init__(self, secret_key: Optional[str] = None):
        self._secret_key = (
            secret_key or
            os.environ.get("AUDIT_SECRET_KEY") or
            "default-audit-key-change-in-production"
        ).encode()
    
    def compute_checksum(
        self,
        entry: AuditEntry,
        previous_checksum: Optional[str] = None,
    ) -> str:
        """
        Compute HMAC-SHA256 checksum for an audit entry.
        
        Includes previous checksum for chain integrity.
        """
        # Create deterministic string representation
        data = {
            "id": entry.id,
            "timestamp": entry.timestamp.isoformat(),
            "action": entry.action.value,
            "category": entry.category.value,
            "user_id": entry.user_id,
            "entity_type": entry.entity_type,
            "entity_id": entry.entity_id,
            "before_values": entry.before_values,
            "after_values": entry.after_values,
            "previous_checksum": previous_checksum,
        }
        
        data_string = json.dumps(data, sort_keys=True, default=str)
        
        # Compute HMAC
        signature = hmac.new(
            self._secret_key,
            data_string.encode(),
            hashlib.sha256,
        ).hexdigest()
        
        return signature
    
    def verify_checksum(
        self,
        entry: AuditEntry,
        expected_checksum: str,
        previous_checksum: Optional[str] = None,
    ) -> bool:
        """Verify the integrity of an audit entry."""
        computed = self.compute_checksum(entry, previous_checksum)
        return hmac.compare_digest(computed, expected_checksum)
    
    def verify_chain(self, entries: List[AuditEntry]) -> Tuple[bool, List[str]]:
        """
        Verify integrity of a chain of audit entries.
        
        Returns (is_valid, list_of_errors).
        """
        errors = []
        previous_checksum = None
        
        for i, entry in enumerate(entries):
            if not entry.checksum:
                errors.append(f"Entry {entry.id} is missing checksum")
                continue
            
            expected_previous = entry.previous_checksum
            if i > 0 and expected_previous != previous_checksum:
                errors.append(
                    f"Entry {entry.id} has broken chain link "
                    f"(expected {previous_checksum}, got {expected_previous})"
                )
            
            if not self.verify_checksum(entry, entry.checksum, expected_previous):
                errors.append(f"Entry {entry.id} has invalid checksum")
            
            previous_checksum = entry.checksum
        
        return len(errors) == 0, errors


# =============================================================================
# Audit Logging Service
# =============================================================================

class ComprehensiveAuditService:
    """
    Complete audit logging service with tamper-proof storage,
    efficient querying, and compliance reporting.
    """
    
    def __init__(
        self,
        storage_backend: Optional[Any] = None,
        integrity_verifier: Optional[IntegrityVerifier] = None,
    ):
        self._storage = storage_backend or InMemoryAuditStorage()
        self._verifier = integrity_verifier or IntegrityVerifier()
        self._last_checksum: Optional[str] = None
        self._async_enabled = False
    
    # =========================================================================
    # Core Logging Methods
    # =========================================================================
    
    def log(
        self,
        action: AuditAction,
        category: AuditCategory,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        before_values: Optional[Dict[str, Any]] = None,
        after_values: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None,
        severity: AuditSeverity = AuditSeverity.INFO,
        metadata: Optional[Dict[str, Any]] = None,
        request_context: Optional[Dict[str, Any]] = None,
        retention_policy: RetentionPolicy = RetentionPolicy.STANDARD,
    ) -> AuditEntry:
        """
        Log an audit event.
        
        This is the primary method for creating audit log entries.
        """
        # Detect changed fields
        changed_fields = []
        if before_values and after_values:
            changed_fields = self._detect_changes(before_values, after_values)
        
        # Calculate expiration
        expires_at = None
        retention_days = RETENTION_DAYS.get(retention_policy)
        if retention_days:
            expires_at = datetime.now(timezone.utc) + timedelta(days=retention_days)
        
        # Create entry
        entry = AuditEntry(
            action=action,
            category=category,
            severity=severity,
            user_id=user_id,
            username=username,
            entity_type=entity_type,
            entity_id=entity_id,
            before_values=before_values,
            after_values=after_values,
            changed_fields=changed_fields,
            description=description,
            metadata=metadata or {},
            retention_policy=retention_policy,
            expires_at=expires_at,
            previous_checksum=self._last_checksum,
        )
        
        # Add request context
        if request_context:
            entry.ip_address = request_context.get("ip_address")
            entry.user_agent = request_context.get("user_agent")
            entry.request_id = request_context.get("request_id")
            entry.session_id = request_context.get("session_id")
        
        # Compute and add checksum
        entry.checksum = self._verifier.compute_checksum(entry, self._last_checksum)
        self._last_checksum = entry.checksum
        
        # Store entry
        self._storage.store(entry)
        
        logger.debug(f"Logged audit entry: {entry.id} - {action.value}")
        
        return entry
    
    def log_security_event(
        self,
        event_type: str,
        success: bool,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        failure_reason: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        is_suspicious: bool = False,
        risk_score: Optional[int] = None,
        risk_factors: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SecurityEvent:
        """
        Log a security-specific event.
        
        Used for authentication, authorization, and security monitoring.
        """
        severity = AuditSeverity.INFO
        if not success:
            severity = AuditSeverity.WARNING
        if is_suspicious:
            severity = AuditSeverity.ERROR
        
        event = SecurityEvent(
            event_type=event_type,
            severity=severity,
            user_id=user_id,
            username=username,
            success=success,
            failure_reason=failure_reason,
            ip_address=ip_address,
            user_agent=user_agent,
            is_suspicious=is_suspicious,
            risk_score=risk_score,
            risk_factors=risk_factors or [],
            metadata=metadata or {},
        )
        
        self._storage.store_security_event(event)
        
        # Also create a regular audit entry for security events
        action = AuditAction.LOGIN if success else AuditAction.LOGIN_FAILED
        if event_type == "logout":
            action = AuditAction.LOGOUT
        elif event_type == "access_denied":
            action = AuditAction.ACCESS_DENIED
        
        self.log(
            action=action,
            category=AuditCategory.SECURITY,
            user_id=user_id,
            username=username,
            severity=severity,
            description=f"Security event: {event_type}",
            metadata={"security_event_id": event.id, **(metadata or {})},
        )
        
        return event
    
    # =========================================================================
    # Convenience Logging Methods
    # =========================================================================
    
    def log_create(
        self,
        entity_type: str,
        entity_id: str,
        data: Dict[str, Any],
        user_id: Optional[str] = None,
        **kwargs,
    ) -> AuditEntry:
        """Log a CREATE operation."""
        return self.log(
            action=AuditAction.CREATE,
            category=AuditCategory.DATA_CHANGE,
            entity_type=entity_type,
            entity_id=entity_id,
            after_values=data,
            user_id=user_id,
            description=f"Created {entity_type} {entity_id}",
            **kwargs,
        )
    
    def log_read(
        self,
        entity_type: str,
        entity_id: str,
        user_id: Optional[str] = None,
        **kwargs,
    ) -> AuditEntry:
        """Log a READ operation."""
        return self.log(
            action=AuditAction.READ,
            category=AuditCategory.DATA_ACCESS,
            entity_type=entity_type,
            entity_id=entity_id,
            user_id=user_id,
            description=f"Read {entity_type} {entity_id}",
            **kwargs,
        )
    
    def log_update(
        self,
        entity_type: str,
        entity_id: str,
        before: Dict[str, Any],
        after: Dict[str, Any],
        user_id: Optional[str] = None,
        **kwargs,
    ) -> AuditEntry:
        """Log an UPDATE operation."""
        return self.log(
            action=AuditAction.UPDATE,
            category=AuditCategory.DATA_CHANGE,
            entity_type=entity_type,
            entity_id=entity_id,
            before_values=before,
            after_values=after,
            user_id=user_id,
            description=f"Updated {entity_type} {entity_id}",
            **kwargs,
        )
    
    def log_delete(
        self,
        entity_type: str,
        entity_id: str,
        data: Dict[str, Any],
        user_id: Optional[str] = None,
        **kwargs,
    ) -> AuditEntry:
        """Log a DELETE operation."""
        return self.log(
            action=AuditAction.DELETE,
            category=AuditCategory.DATA_CHANGE,
            entity_type=entity_type,
            entity_id=entity_id,
            before_values=data,
            user_id=user_id,
            severity=AuditSeverity.WARNING,
            description=f"Deleted {entity_type} {entity_id}",
            **kwargs,
        )
    
    # =========================================================================
    # Query Methods
    # =========================================================================
    
    def query(self, params: AuditQueryParams) -> AuditQueryResult:
        """
        Query audit logs with filtering and pagination.
        
        Supports filtering by user, date range, entity type, and action.
        """
        return self._storage.query(params)
    
    def get_entry(self, entry_id: str) -> Optional[AuditEntry]:
        """Get a specific audit entry by ID."""
        return self._storage.get(entry_id)
    
    def get_entity_history(
        self,
        entity_type: str,
        entity_id: str,
        limit: int = 100,
    ) -> List[AuditEntry]:
        """Get audit history for a specific entity."""
        params = AuditQueryParams(
            entity_type=entity_type,
            entity_id=entity_id,
            page_size=limit,
        )
        result = self._storage.query(params)
        return result.entries
    
    def get_user_activity(
        self,
        user_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[AuditEntry]:
        """Get audit history for a specific user."""
        params = AuditQueryParams(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            page_size=limit,
        )
        result = self._storage.query(params)
        return result.entries
    
    # =========================================================================
    # Compliance Reporting
    # =========================================================================
    
    def generate_compliance_report(
        self,
        report_type: str,
        start_date: datetime,
        end_date: datetime,
        format: str = "json",
    ) -> ComplianceReport:
        """
        Generate a compliance audit report for the specified period.
        
        Includes summary statistics, user activity, and integrity verification.
        """
        # Query all entries in the period
        params = AuditQueryParams(
            start_date=start_date,
            end_date=end_date,
            page_size=10000,  # Get all entries
        )
        result = self._storage.query(params)
        entries = result.entries
        
        # Calculate statistics
        events_by_category: Dict[str, int] = {}
        events_by_action: Dict[str, int] = {}
        events_by_severity: Dict[str, int] = {}
        user_activity: Dict[str, int] = {}
        
        for entry in entries:
            # By category
            cat = entry.category.value
            events_by_category[cat] = events_by_category.get(cat, 0) + 1
            
            # By action
            act = entry.action.value
            events_by_action[act] = events_by_action.get(act, 0) + 1
            
            # By severity
            sev = entry.severity.value
            events_by_severity[sev] = events_by_severity.get(sev, 0) + 1
            
            # User activity
            if entry.user_id:
                user_activity[entry.user_id] = user_activity.get(entry.user_id, 0) + 1
        
        # Get security events
        security_entries = [e for e in entries if e.category == AuditCategory.SECURITY]
        failed_logins = sum(
            1 for e in security_entries
            if e.action == AuditAction.LOGIN_FAILED
        )
        
        # Most active users
        most_active = sorted(
            user_activity.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:10]
        most_active_users = [
            {"user_id": uid, "event_count": count}
            for uid, count in most_active
        ]
        
        # Verify integrity
        is_valid, integrity_errors = self._verifier.verify_chain(entries)
        
        report = ComplianceReport(
            report_type=report_type,
            period_start=start_date,
            period_end=end_date,
            total_events=len(entries),
            events_by_category=events_by_category,
            events_by_action=events_by_action,
            events_by_severity=events_by_severity,
            unique_users=len(user_activity),
            most_active_users=most_active_users,
            security_events=len(security_entries),
            failed_logins=failed_logins,
            integrity_verified=is_valid,
            integrity_errors=integrity_errors,
            format=format,
        )
        
        return report
    
    def export_audit_log(
        self,
        params: AuditQueryParams,
        format: str = "json",
        file_path: Optional[str] = None,
    ) -> str:
        """
        Export audit logs in the specified format.
        
        Supports JSON, CSV, and XML formats.
        """
        result = self._storage.query(params)
        
        if format == "json":
            data = [entry.model_dump() for entry in result.entries]
            output = json.dumps(data, indent=2, default=str)
        elif format == "csv":
            output = self._entries_to_csv(result.entries)
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        if file_path:
            with open(file_path, "w") as f:
                f.write(output)
        
        return output
    
    # =========================================================================
    # Private Methods
    # =========================================================================
    
    def _detect_changes(
        self,
        before: Dict[str, Any],
        after: Dict[str, Any],
    ) -> List[str]:
        """Detect which fields changed between before and after values."""
        changed = []
        all_keys = set(before.keys()) | set(after.keys())
        
        for key in all_keys:
            before_val = before.get(key)
            after_val = after.get(key)
            
            if before_val != after_val:
                changed.append(key)
        
        return changed
    
    def _entries_to_csv(self, entries: List[AuditEntry]) -> str:
        """Convert entries to CSV format."""
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow([
            "id", "timestamp", "action", "category", "severity",
            "user_id", "username", "entity_type", "entity_id",
            "changed_fields", "description", "ip_address",
        ])
        
        # Data
        for entry in entries:
            writer.writerow([
                entry.id,
                entry.timestamp.isoformat(),
                entry.action.value,
                entry.category.value,
                entry.severity.value,
                entry.user_id,
                entry.username,
                entry.entity_type,
                entry.entity_id,
                ",".join(entry.changed_fields),
                entry.description,
                entry.ip_address,
            ])
        
        return output.getvalue()


# =============================================================================
# Storage Backend
# =============================================================================

class InMemoryAuditStorage:
    """
    In-memory audit storage for development and testing.
    
    In production, replace with database-backed storage.
    """
    
    def __init__(self):
        self._entries: List[AuditEntry] = []
        self._security_events: List[SecurityEvent] = []
        self._index_by_id: Dict[str, AuditEntry] = {}
    
    def store(self, entry: AuditEntry) -> None:
        """Store an audit entry."""
        self._entries.append(entry)
        self._index_by_id[entry.id] = entry
    
    def store_security_event(self, event: SecurityEvent) -> None:
        """Store a security event."""
        self._security_events.append(event)
    
    def get(self, entry_id: str) -> Optional[AuditEntry]:
        """Get an entry by ID."""
        return self._index_by_id.get(entry_id)
    
    def query(self, params: AuditQueryParams) -> AuditQueryResult:
        """Query entries with filtering and pagination."""
        filtered = self._entries.copy()
        
        # Apply filters
        if params.user_id:
            filtered = [e for e in filtered if e.user_id == params.user_id]
        
        if params.username:
            filtered = [e for e in filtered if e.username == params.username]
        
        if params.entity_type:
            filtered = [e for e in filtered if e.entity_type == params.entity_type]
        
        if params.entity_id:
            filtered = [e for e in filtered if e.entity_id == params.entity_id]
        
        if params.action:
            filtered = [e for e in filtered if e.action == params.action]
        
        if params.category:
            filtered = [e for e in filtered if e.category == params.category]
        
        if params.severity:
            filtered = [e for e in filtered if e.severity == params.severity]
        
        if params.start_date:
            filtered = [e for e in filtered if e.timestamp >= params.start_date]
        
        if params.end_date:
            filtered = [e for e in filtered if e.timestamp <= params.end_date]
        
        if params.search_term:
            term = params.search_term.lower()
            filtered = [
                e for e in filtered
                if (e.description and term in e.description.lower()) or
                   (e.entity_type and term in e.entity_type.lower())
            ]
        
        # Sort
        reverse = params.sort_order == "desc"
        filtered.sort(
            key=lambda e: getattr(e, params.sort_by, e.timestamp),
            reverse=reverse,
        )
        
        # Paginate
        total_count = len(filtered)
        total_pages = (total_count + params.page_size - 1) // params.page_size
        start = (params.page - 1) * params.page_size
        end = start + params.page_size
        page_entries = filtered[start:end]
        
        return AuditQueryResult(
            entries=page_entries,
            total_count=total_count,
            page=params.page,
            page_size=params.page_size,
            total_pages=total_pages,
            has_next=params.page < total_pages,
            has_previous=params.page > 1,
        )


# =============================================================================
# Convenience Functions
# =============================================================================

_audit_service: Optional[ComprehensiveAuditService] = None


def get_audit_service() -> ComprehensiveAuditService:
    """Get the audit service singleton."""
    global _audit_service
    if _audit_service is None:
        _audit_service = ComprehensiveAuditService()
    return _audit_service


def audit_log_decorator(
    action: AuditAction,
    category: AuditCategory,
    entity_type_arg: Optional[str] = None,
    entity_id_arg: Optional[str] = None,
):
    """
    Decorator for automatic audit logging of function calls.
    
    Example:
        @audit_log_decorator(AuditAction.UPDATE, AuditCategory.DATA_CHANGE, "employee", "employee_id")
        def update_employee(employee_id: int, data: dict):
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        def wrapper(*args, **kwargs):
            service = get_audit_service()
            
            # Extract entity info from args
            entity_type = entity_type_arg
            entity_id = None
            
            if entity_id_arg and entity_id_arg in kwargs:
                entity_id = str(kwargs[entity_id_arg])
            
            try:
                result = func(*args, **kwargs)
                
                # Log successful operation
                service.log(
                    action=action,
                    category=category,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    description=f"Function {func.__name__} executed successfully",
                )
                
                return result
                
            except Exception as e:
                # Log failed operation
                service.log(
                    action=action,
                    category=category,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    severity=AuditSeverity.ERROR,
                    description=f"Function {func.__name__} failed: {str(e)}",
                )
                raise
        
        return wrapper
    return decorator

