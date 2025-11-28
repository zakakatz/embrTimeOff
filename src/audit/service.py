"""Audit service for tracking employee profile changes."""

import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Sequence
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from src.models.employee_audit_trail import ChangeType, EmployeeAuditTrail


# Fields that contain sensitive information and should be masked in certain contexts
SENSITIVE_FIELDS = frozenset({
    "salary",
    "hourly_rate",
    "date_of_birth",
    "personal_email",
    "phone_number",
    "mobile_number",
    "address_line1",
    "address_line2",
})


@dataclass
class AuditContext:
    """Context information for audit logging."""
    
    user_id: UUID
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    change_reason: Optional[str] = None


class AuditService:
    """
    Service for creating and querying employee audit trail records.
    
    Provides field-level change detection and immutable audit logging
    for compliance and history tracking.
    """
    
    def __init__(self, session: Session):
        """Initialize audit service with database session."""
        self.session = session
    
    @staticmethod
    def _serialize_value(value: Any) -> Optional[str]:
        """
        Serialize a value to JSON string for storage.
        
        Handles special types like dates, decimals, and UUIDs.
        """
        if value is None:
            return None
        
        if isinstance(value, datetime):
            return json.dumps(value.isoformat())
        elif isinstance(value, date):
            return json.dumps(value.isoformat())
        elif isinstance(value, Decimal):
            return json.dumps(str(value))
        elif isinstance(value, UUID):
            return json.dumps(str(value))
        elif isinstance(value, (dict, list)):
            return json.dumps(value)
        else:
            return json.dumps(value)
    
    @staticmethod
    def _mask_sensitive_value(field: str, value: Optional[str]) -> Optional[str]:
        """Mask sensitive field values for display purposes."""
        if value is None or field not in SENSITIVE_FIELDS:
            return value
        
        # Return masked indicator for sensitive fields
        return '"[REDACTED]"'
    
    def _detect_changes(
        self,
        old_data: Optional[Dict[str, Any]],
        new_data: Dict[str, Any],
        change_type: ChangeType,
    ) -> List[tuple[str, Optional[str], Optional[str]]]:
        """
        Detect field-level changes between old and new data.
        
        Returns list of (field_name, previous_value, new_value) tuples.
        """
        changes: List[tuple[str, Optional[str], Optional[str]]] = []
        
        if change_type == ChangeType.CREATE:
            # For CREATE, all non-null fields are "changes"
            for field, value in new_data.items():
                if value is not None and not field.startswith("_"):
                    changes.append((
                        field,
                        None,
                        self._serialize_value(value),
                    ))
        
        elif change_type == ChangeType.DELETE:
            # For DELETE, record all existing fields
            if old_data:
                for field, value in old_data.items():
                    if value is not None and not field.startswith("_"):
                        changes.append((
                            field,
                            self._serialize_value(value),
                            None,
                        ))
        
        elif change_type == ChangeType.UPDATE:
            # For UPDATE, compare old and new values
            if old_data is None:
                old_data = {}
            
            all_fields = set(old_data.keys()) | set(new_data.keys())
            
            for field in all_fields:
                if field.startswith("_"):
                    continue
                
                old_value = old_data.get(field)
                new_value = new_data.get(field)
                
                # Skip if values are equal
                if old_value == new_value:
                    continue
                
                # Skip system fields that auto-update
                if field in ("updated_at",):
                    continue
                
                changes.append((
                    field,
                    self._serialize_value(old_value),
                    self._serialize_value(new_value),
                ))
        
        return changes
    
    def log_create(
        self,
        employee_id: int,
        employee_data: Dict[str, Any],
        context: AuditContext,
    ) -> List[EmployeeAuditTrail]:
        """
        Log audit records for employee creation.
        
        Creates an audit record for each field with a non-null value.
        """
        changes = self._detect_changes(None, employee_data, ChangeType.CREATE)
        return self._create_audit_records(
            employee_id=employee_id,
            changes=changes,
            change_type=ChangeType.CREATE,
            context=context,
        )
    
    def log_update(
        self,
        employee_id: int,
        old_data: Dict[str, Any],
        new_data: Dict[str, Any],
        context: AuditContext,
    ) -> List[EmployeeAuditTrail]:
        """
        Log audit records for employee update.
        
        Creates an audit record for each field that changed.
        """
        changes = self._detect_changes(old_data, new_data, ChangeType.UPDATE)
        return self._create_audit_records(
            employee_id=employee_id,
            changes=changes,
            change_type=ChangeType.UPDATE,
            context=context,
        )
    
    def log_delete(
        self,
        employee_id: int,
        employee_data: Dict[str, Any],
        context: AuditContext,
    ) -> List[EmployeeAuditTrail]:
        """
        Log audit records for employee deletion.
        
        Creates an audit record for each field that had a value.
        """
        changes = self._detect_changes(employee_data, {}, ChangeType.DELETE)
        return self._create_audit_records(
            employee_id=employee_id,
            changes=changes,
            change_type=ChangeType.DELETE,
            context=context,
        )
    
    def _create_audit_records(
        self,
        employee_id: int,
        changes: List[tuple[str, Optional[str], Optional[str]]],
        change_type: ChangeType,
        context: AuditContext,
    ) -> List[EmployeeAuditTrail]:
        """Create audit trail records for detected changes."""
        records: List[EmployeeAuditTrail] = []
        
        for field, previous_value, new_value in changes:
            record = EmployeeAuditTrail(
                employee_id=employee_id,
                changed_field=field,
                previous_value=previous_value,
                new_value=new_value,
                changed_by_user_id=context.user_id,
                change_type=change_type,
                change_reason=context.change_reason,
                ip_address=context.ip_address,
                user_agent=context.user_agent,
            )
            self.session.add(record)
            records.append(record)
        
        return records
    
    # =========================================================================
    # Query Methods
    # =========================================================================
    
    def get_employee_history(
        self,
        employee_id: int,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[EmployeeAuditTrail]:
        """
        Get audit history for a specific employee.
        
        Returns records ordered by timestamp descending (most recent first).
        """
        stmt = (
            select(EmployeeAuditTrail)
            .where(EmployeeAuditTrail.employee_id == employee_id)
            .order_by(EmployeeAuditTrail.change_timestamp.desc())
            .limit(limit)
            .offset(offset)
        )
        return self.session.scalars(stmt).all()
    
    def get_history_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        employee_id: Optional[int] = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> Sequence[EmployeeAuditTrail]:
        """
        Get audit records within a date range.
        
        Optionally filter by employee_id.
        """
        conditions = [
            EmployeeAuditTrail.change_timestamp >= start_date,
            EmployeeAuditTrail.change_timestamp <= end_date,
        ]
        
        if employee_id is not None:
            conditions.append(EmployeeAuditTrail.employee_id == employee_id)
        
        stmt = (
            select(EmployeeAuditTrail)
            .where(and_(*conditions))
            .order_by(EmployeeAuditTrail.change_timestamp.desc())
            .limit(limit)
            .offset(offset)
        )
        return self.session.scalars(stmt).all()
    
    def get_field_history(
        self,
        employee_id: int,
        field_name: str,
        limit: int = 50,
    ) -> Sequence[EmployeeAuditTrail]:
        """Get change history for a specific field on an employee."""
        stmt = (
            select(EmployeeAuditTrail)
            .where(
                and_(
                    EmployeeAuditTrail.employee_id == employee_id,
                    EmployeeAuditTrail.changed_field == field_name,
                )
            )
            .order_by(EmployeeAuditTrail.change_timestamp.desc())
            .limit(limit)
        )
        return self.session.scalars(stmt).all()
    
    def get_changes_by_user(
        self,
        user_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[EmployeeAuditTrail]:
        """Get all changes made by a specific user."""
        stmt = (
            select(EmployeeAuditTrail)
            .where(EmployeeAuditTrail.changed_by_user_id == user_id)
            .order_by(EmployeeAuditTrail.change_timestamp.desc())
            .limit(limit)
            .offset(offset)
        )
        return self.session.scalars(stmt).all()
    
    def get_recent_changes(
        self,
        change_type: Optional[ChangeType] = None,
        limit: int = 100,
    ) -> Sequence[EmployeeAuditTrail]:
        """Get most recent audit records, optionally filtered by change type."""
        stmt = select(EmployeeAuditTrail)
        
        if change_type is not None:
            stmt = stmt.where(EmployeeAuditTrail.change_type == change_type)
        
        stmt = (
            stmt
            .order_by(EmployeeAuditTrail.change_timestamp.desc())
            .limit(limit)
        )
        return self.session.scalars(stmt).all()
    
    def get_sensitive_field_changes(
        self,
        employee_id: int,
        mask_values: bool = True,
    ) -> Sequence[Dict[str, Any]]:
        """
        Get changes to sensitive fields for an employee.
        
        If mask_values is True, actual values are redacted.
        """
        stmt = (
            select(EmployeeAuditTrail)
            .where(
                and_(
                    EmployeeAuditTrail.employee_id == employee_id,
                    EmployeeAuditTrail.changed_field.in_(SENSITIVE_FIELDS),
                )
            )
            .order_by(EmployeeAuditTrail.change_timestamp.desc())
        )
        records = self.session.scalars(stmt).all()
        
        results: List[Dict[str, Any]] = []
        for record in records:
            result = {
                "id": str(record.id),
                "employee_id": record.employee_id,
                "changed_field": record.changed_field,
                "changed_by_user_id": str(record.changed_by_user_id),
                "change_timestamp": record.change_timestamp.isoformat(),
                "change_type": record.change_type.value,
            }
            
            if mask_values:
                result["previous_value"] = self._mask_sensitive_value(
                    record.changed_field, record.previous_value
                )
                result["new_value"] = self._mask_sensitive_value(
                    record.changed_field, record.new_value
                )
            else:
                result["previous_value"] = record.previous_value
                result["new_value"] = record.new_value
            
            results.append(result)
        
        return results

