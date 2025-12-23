"""Service for employee activity logging and retrieval."""

from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from src.models.activity_log import ActivityLog, ActivitySource, ActivityType
from src.schemas.employee_audit import (
    ActivityEntry,
    ActivityFilters,
    ActivityResponse,
)
from src.utils.auth import CurrentUser, UserRole


class ActivityService:
    """
    Service for managing employee activity logs.
    
    Provides functionality for:
    - Creating activity log entries
    - Retrieving activity feeds with filtering
    - Aggregating activity statistics
    """
    
    def __init__(self, session: Session):
        """Initialize with database session."""
        self.session = session
    
    # =========================================================================
    # Activity Creation
    # =========================================================================
    
    def log_activity(
        self,
        employee_id: int,
        activity_type: ActivityType,
        title: str,
        description: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        actor_user_id: Optional[UUID] = None,
        actor_name: Optional[str] = None,
        activity_source: ActivitySource = ActivitySource.USER,
        is_automated: bool = False,
        related_entity_type: Optional[str] = None,
        related_entity_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> ActivityLog:
        """Create a new activity log entry."""
        activity = ActivityLog(
            employee_id=employee_id,
            activity_type=activity_type,
            activity_source=activity_source,
            title=title,
            description=description,
            details=details,
            actor_user_id=actor_user_id,
            actor_name=actor_name,
            is_automated=is_automated,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.session.add(activity)
        return activity
    
    def log_profile_view(
        self,
        employee_id: int,
        viewer: CurrentUser,
    ) -> ActivityLog:
        """Log a profile view activity."""
        return self.log_activity(
            employee_id=employee_id,
            activity_type=ActivityType.PROFILE_VIEW,
            title="Profile viewed",
            actor_user_id=viewer.id,
            ip_address=viewer.ip_address,
            user_agent=viewer.user_agent,
        )
    
    def log_profile_update(
        self,
        employee_id: int,
        actor: CurrentUser,
        changed_fields: List[str],
    ) -> ActivityLog:
        """Log a profile update activity."""
        return self.log_activity(
            employee_id=employee_id,
            activity_type=ActivityType.PROFILE_UPDATE,
            title="Profile updated",
            description=f"Updated fields: {', '.join(changed_fields)}",
            details={"changed_fields": changed_fields},
            actor_user_id=actor.id,
            ip_address=actor.ip_address,
            user_agent=actor.user_agent,
        )
    
    def log_status_change(
        self,
        employee_id: int,
        actor: CurrentUser,
        old_status: str,
        new_status: str,
    ) -> ActivityLog:
        """Log an employment status change."""
        return self.log_activity(
            employee_id=employee_id,
            activity_type=ActivityType.STATUS_CHANGE,
            title=f"Status changed to {new_status}",
            description=f"Employment status changed from {old_status} to {new_status}",
            details={"old_status": old_status, "new_status": new_status},
            actor_user_id=actor.id,
            ip_address=actor.ip_address,
            user_agent=actor.user_agent,
        )
    
    def log_system_activity(
        self,
        employee_id: int,
        title: str,
        description: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> ActivityLog:
        """Log an automated system activity."""
        return self.log_activity(
            employee_id=employee_id,
            activity_type=ActivityType.SYSTEM_UPDATE,
            title=title,
            description=description,
            details=details,
            activity_source=ActivitySource.SYSTEM,
            is_automated=True,
        )
    
    # =========================================================================
    # Activity Retrieval
    # =========================================================================
    
    def get_employee_activities(
        self,
        employee_id: int,
        current_user: CurrentUser,
        filters: Optional[ActivityFilters] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> ActivityResponse:
        """
        Get activity feed for an employee.
        
        Applies access controls and optional filters.
        """
        # Check permissions
        self._check_activity_view_permission(employee_id, current_user)
        
        # Build query
        stmt = select(ActivityLog).where(ActivityLog.employee_id == employee_id)
        
        # Apply filters
        if filters:
            conditions = []
            
            if filters.activity_types:
                conditions.append(ActivityLog.activity_type.in_(filters.activity_types))
            
            if filters.date_from:
                conditions.append(ActivityLog.created_at >= filters.date_from)
            
            if filters.date_to:
                conditions.append(ActivityLog.created_at <= filters.date_to)
            
            if filters.actor_user_id:
                conditions.append(ActivityLog.actor_user_id == filters.actor_user_id)
            
            if not filters.include_automated:
                conditions.append(ActivityLog.is_automated == False)
            
            if conditions:
                stmt = stmt.where(and_(*conditions))
        
        # Only show visible activities
        stmt = stmt.where(ActivityLog.is_visible == True)
        
        # Get total count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.session.execute(count_stmt).scalar() or 0
        
        # Apply pagination and ordering
        offset = (page - 1) * page_size
        stmt = (
            stmt
            .order_by(ActivityLog.created_at.desc())
            .limit(page_size)
            .offset(offset)
        )
        
        # Execute query
        result = self.session.execute(stmt)
        activities = list(result.scalars())
        
        # Build response
        return ActivityResponse(
            employee_id=employee_id,
            total_activities=total,
            activities=[self._to_activity_entry(a) for a in activities],
            page=page,
            page_size=page_size,
            has_more=(offset + len(activities)) < total,
        )
    
    def get_recent_activities_for_manager(
        self,
        manager_id: int,
        current_user: CurrentUser,
        limit: int = 20,
    ) -> List[ActivityEntry]:
        """
        Get recent activities for employees managed by a manager.
        
        Useful for manager dashboards.
        """
        from src.models.employee import Employee
        
        # Get direct report IDs
        stmt = select(Employee.id).where(Employee.manager_id == manager_id)
        result = self.session.execute(stmt)
        report_ids = [r[0] for r in result]
        
        if not report_ids:
            return []
        
        # Get recent activities for these employees
        stmt = (
            select(ActivityLog)
            .where(ActivityLog.employee_id.in_(report_ids))
            .where(ActivityLog.is_visible == True)
            .order_by(ActivityLog.created_at.desc())
            .limit(limit)
        )
        
        result = self.session.execute(stmt)
        activities = list(result.scalars())
        
        return [self._to_activity_entry(a) for a in activities]
    
    # =========================================================================
    # Permission Checking
    # =========================================================================
    
    def _check_activity_view_permission(
        self,
        employee_id: int,
        current_user: CurrentUser,
    ) -> None:
        """Check if user can view activity for an employee."""
        from src.utils.errors import ForbiddenError
        
        # Admin and HR can view all
        if current_user.has_role(UserRole.ADMIN) or current_user.has_role(UserRole.HR_MANAGER):
            return
        
        # Users can view their own activity
        if current_user.employee_id == employee_id:
            return
        
        # Managers can view their direct reports' activity
        if current_user.has_role(UserRole.MANAGER):
            from src.models.employee import Employee
            
            stmt = select(Employee).where(Employee.id == employee_id)
            employee = self.session.execute(stmt).scalar_one_or_none()
            
            if employee and employee.manager_id == current_user.employee_id:
                return
        
        raise ForbiddenError(
            message="You don't have permission to view this activity log",
            details={"employee_id": employee_id},
        )
    
    # =========================================================================
    # Helpers
    # =========================================================================
    
    def _to_activity_entry(self, activity: ActivityLog) -> ActivityEntry:
        """Convert ActivityLog model to ActivityEntry schema."""
        return ActivityEntry(
            id=activity.id,
            employee_id=activity.employee_id,
            activity_type=activity.activity_type,
            activity_source=activity.activity_source,
            title=activity.title,
            description=activity.description,
            details=activity.details,
            related_entity_type=activity.related_entity_type,
            related_entity_id=activity.related_entity_id,
            actor_user_id=activity.actor_user_id,
            actor_name=activity.actor_name,
            is_automated=activity.is_automated,
            created_at=activity.created_at,
        )

