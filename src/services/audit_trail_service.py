"""Service for employee audit trail retrieval and processing."""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from src.models.employee_audit_trail import ChangeType, EmployeeAuditTrail
from src.schemas.employee_audit import (
    AuditTrailEntry,
    AuditTrailResponse,
    AuditTrailSummary,
)
from src.utils.auth import CurrentUser, UserRole


# Field display names for better readability
FIELD_DISPLAY_NAMES = {
    "employee_id": "Employee ID",
    "email": "Email Address",
    "first_name": "First Name",
    "middle_name": "Middle Name",
    "last_name": "Last Name",
    "preferred_name": "Preferred Name",
    "date_of_birth": "Date of Birth",
    "gender": "Gender",
    "personal_email": "Personal Email",
    "phone_number": "Phone Number",
    "mobile_number": "Mobile Number",
    "address_line1": "Address Line 1",
    "address_line2": "Address Line 2",
    "city": "City",
    "state_province": "State/Province",
    "postal_code": "Postal Code",
    "country": "Country",
    "department_id": "Department",
    "manager_id": "Manager",
    "location_id": "Location",
    "work_schedule_id": "Work Schedule",
    "job_title": "Job Title",
    "employment_type": "Employment Type",
    "employment_status": "Employment Status",
    "hire_date": "Hire Date",
    "termination_date": "Termination Date",
    "salary": "Salary",
    "hourly_rate": "Hourly Rate",
    "is_active": "Active Status",
}


class AuditTrailService:
    """
    Service for retrieving and processing employee audit trail data.
    
    Provides functionality for:
    - Retrieving chronological change history
    - Filtering and pagination of audit entries
    - Generating audit summaries and statistics
    """
    
    def __init__(self, session: Session):
        """Initialize with database session."""
        self.session = session
    
    # =========================================================================
    # Audit Trail Retrieval
    # =========================================================================
    
    def get_audit_trail(
        self,
        employee_id: int,
        current_user: CurrentUser,
        page: int = 1,
        page_size: int = 50,
        change_type: Optional[ChangeType] = None,
        field_name: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        actor_user_id: Optional[UUID] = None,
    ) -> AuditTrailResponse:
        """
        Get audit trail for an employee.
        
        Returns chronological change history with pagination and filtering.
        """
        # Check permissions
        self._check_audit_view_permission(employee_id, current_user)
        
        # Build query
        stmt = select(EmployeeAuditTrail).where(
            EmployeeAuditTrail.employee_id == employee_id
        )
        
        # Apply filters
        conditions = []
        
        if change_type:
            conditions.append(EmployeeAuditTrail.change_type == change_type)
        
        if field_name:
            conditions.append(EmployeeAuditTrail.changed_field == field_name)
        
        if date_from:
            conditions.append(EmployeeAuditTrail.change_timestamp >= date_from)
        
        if date_to:
            conditions.append(EmployeeAuditTrail.change_timestamp <= date_to)
        
        if actor_user_id:
            conditions.append(EmployeeAuditTrail.changed_by_user_id == actor_user_id)
        
        if conditions:
            stmt = stmt.where(and_(*conditions))
        
        # Get total count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.session.execute(count_stmt).scalar() or 0
        
        # Apply pagination and ordering
        offset = (page - 1) * page_size
        stmt = (
            stmt
            .order_by(EmployeeAuditTrail.change_timestamp.desc())
            .limit(page_size)
            .offset(offset)
        )
        
        # Execute query
        result = self.session.execute(stmt)
        entries = list(result.scalars())
        
        # Build response
        return AuditTrailResponse(
            employee_id=employee_id,
            total_entries=total,
            entries=[self._to_audit_entry(e) for e in entries],
            page=page,
            page_size=page_size,
            has_more=(offset + len(entries)) < total,
        )
    
    def get_audit_summary(
        self,
        employee_id: int,
        current_user: CurrentUser,
    ) -> AuditTrailSummary:
        """
        Get a summary of audit trail for an employee.
        
        Provides quick overview including totals, date ranges, and statistics.
        """
        # Check permissions
        self._check_audit_view_permission(employee_id, current_user)
        
        # Get total changes
        total_stmt = select(func.count()).where(
            EmployeeAuditTrail.employee_id == employee_id
        )
        total = self.session.execute(total_stmt).scalar() or 0
        
        # Get date range
        date_stmt = select(
            func.min(EmployeeAuditTrail.change_timestamp),
            func.max(EmployeeAuditTrail.change_timestamp),
        ).where(EmployeeAuditTrail.employee_id == employee_id)
        date_result = self.session.execute(date_stmt).one()
        first_change, last_change = date_result
        
        # Get change counts by type
        type_stmt = (
            select(
                EmployeeAuditTrail.change_type,
                func.count().label("count"),
            )
            .where(EmployeeAuditTrail.employee_id == employee_id)
            .group_by(EmployeeAuditTrail.change_type)
        )
        type_result = self.session.execute(type_stmt)
        change_counts = {row[0].value: row[1] for row in type_result}
        
        # Get most changed fields
        field_stmt = (
            select(
                EmployeeAuditTrail.changed_field,
                func.count().label("count"),
            )
            .where(EmployeeAuditTrail.employee_id == employee_id)
            .group_by(EmployeeAuditTrail.changed_field)
            .order_by(func.count().desc())
            .limit(5)
        )
        field_result = self.session.execute(field_stmt)
        most_changed = [
            {
                "field": row[0],
                "display_name": FIELD_DISPLAY_NAMES.get(row[0], row[0]),
                "count": row[1],
            }
            for row in field_result
        ]
        
        # Get unique actors count
        actors_stmt = (
            select(func.count(func.distinct(EmployeeAuditTrail.changed_by_user_id)))
            .where(EmployeeAuditTrail.employee_id == employee_id)
        )
        actors_count = self.session.execute(actors_stmt).scalar() or 0
        
        return AuditTrailSummary(
            employee_id=employee_id,
            total_changes=total,
            first_change=first_change,
            last_change=last_change,
            change_counts_by_type=change_counts,
            most_changed_fields=most_changed,
            actors_count=actors_count,
        )
    
    def get_field_history(
        self,
        employee_id: int,
        field_name: str,
        current_user: CurrentUser,
        limit: int = 20,
    ) -> List[AuditTrailEntry]:
        """
        Get change history for a specific field.
        
        Useful for tracking changes to a particular attribute over time.
        """
        # Check permissions
        self._check_audit_view_permission(employee_id, current_user)
        
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
        
        result = self.session.execute(stmt)
        entries = list(result.scalars())
        
        return [self._to_audit_entry(e) for e in entries]
    
    def get_changes_by_user(
        self,
        actor_user_id: UUID,
        current_user: CurrentUser,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AuditTrailEntry]:
        """
        Get all changes made by a specific user.
        
        Requires admin or HR role.
        """
        # Only admin and HR can view changes by user across employees
        if not (current_user.has_role(UserRole.ADMIN) or current_user.has_role(UserRole.HR_MANAGER)):
            from src.utils.errors import ForbiddenError
            raise ForbiddenError(
                message="You don't have permission to view audit logs by user",
            )
        
        stmt = (
            select(EmployeeAuditTrail)
            .where(EmployeeAuditTrail.changed_by_user_id == actor_user_id)
            .order_by(EmployeeAuditTrail.change_timestamp.desc())
            .limit(limit)
            .offset(offset)
        )
        
        result = self.session.execute(stmt)
        entries = list(result.scalars())
        
        return [self._to_audit_entry(e) for e in entries]
    
    # =========================================================================
    # Permission Checking
    # =========================================================================
    
    def _check_audit_view_permission(
        self,
        employee_id: int,
        current_user: CurrentUser,
    ) -> None:
        """Check if user can view audit trail for an employee."""
        from src.utils.errors import ForbiddenError
        
        # Admin and HR can view all
        if current_user.has_role(UserRole.ADMIN) or current_user.has_role(UserRole.HR_MANAGER):
            return
        
        # Users can view their own audit trail
        if current_user.employee_id == employee_id:
            return
        
        # Managers can view their direct reports' audit trails
        if current_user.has_role(UserRole.MANAGER):
            from src.models.employee import Employee
            
            stmt = select(Employee).where(Employee.id == employee_id)
            employee = self.session.execute(stmt).scalar_one_or_none()
            
            if employee and employee.manager_id == current_user.employee_id:
                return
        
        raise ForbiddenError(
            message="You don't have permission to view this audit trail",
            details={"employee_id": employee_id},
        )
    
    # =========================================================================
    # Helpers
    # =========================================================================
    
    def _to_audit_entry(self, audit: EmployeeAuditTrail) -> AuditTrailEntry:
        """Convert EmployeeAuditTrail model to AuditTrailEntry schema."""
        # Determine if this was an automated change
        # (In a real system, this might be stored in the audit record)
        is_automated = False
        if audit.change_reason:
            is_automated = any(
                keyword in audit.change_reason.lower()
                for keyword in ["system", "automated", "import", "sync"]
            )
        
        return AuditTrailEntry(
            id=audit.id,
            employee_id=audit.employee_id,
            changed_field=audit.changed_field,
            previous_value=audit.previous_value,
            new_value=audit.new_value,
            changed_by_user_id=audit.changed_by_user_id,
            change_timestamp=audit.change_timestamp,
            change_type=audit.change_type,
            change_reason=audit.change_reason,
            ip_address=audit.ip_address,
            user_agent=audit.user_agent,
            field_display_name=FIELD_DISPLAY_NAMES.get(
                audit.changed_field, 
                audit.changed_field.replace("_", " ").title()
            ),
            is_automated=is_automated,
        )

