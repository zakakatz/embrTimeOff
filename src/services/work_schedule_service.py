"""Service for work schedule management."""

import json
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.models.employee import Employee, Department, Location, WorkSchedule
from src.schemas.work_schedule import (
    BreakSchedule,
    CreateWorkScheduleRequest,
    EmployeeAssignmentSummary,
    ImpactAssessment,
    LaborLawCompliance,
    ScheduleTypeEnum,
    UpdateWorkScheduleRequest,
    WorkScheduleResponse,
    WorkingPattern,
)
from src.utils.auth import CurrentUser

logger = logging.getLogger(__name__)


# Schedule type display names
SCHEDULE_TYPE_DISPLAY = {
    "standard": "Standard",
    "shift": "Shift Work",
    "compressed": "Compressed Workweek",
    "flexible": "Flexible Hours",
    "part_time": "Part-Time",
    "custom": "Custom Schedule",
}


class WorkScheduleService:
    """Service for managing work schedules."""

    def __init__(self, session: Session):
        """Initialize with database session."""
        self.session = session

    # =========================================================================
    # Labor Law Compliance
    # =========================================================================

    def validate_labor_compliance(
        self,
        hours_per_week: float,
        hours_per_day: float,
        break_minutes: int,
        jurisdiction: str = "default",
    ) -> LaborLawCompliance:
        """
        Validate schedule against labor law requirements.
        
        Checks daily hours, weekly hours, and break requirements.
        """
        violations = []
        warnings = []
        
        # Default labor law limits (would be configurable by jurisdiction)
        max_daily = 10.0
        max_weekly = 48.0
        min_break_after_hours = 6.0
        min_break_minutes = 30
        
        # Check daily hours
        if hours_per_day > max_daily:
            violations.append(
                f"Daily hours ({hours_per_day:.1f}) exceed maximum allowed ({max_daily})"
            )
        elif hours_per_day > 8:
            warnings.append(
                f"Daily hours ({hours_per_day:.1f}) exceed standard 8-hour workday"
            )
        
        # Check weekly hours
        if hours_per_week > max_weekly:
            violations.append(
                f"Weekly hours ({hours_per_week:.1f}) exceed maximum allowed ({max_weekly})"
            )
        elif hours_per_week > 40:
            warnings.append(
                f"Weekly hours ({hours_per_week:.1f}) exceed standard 40-hour workweek"
            )
        
        # Check break requirements
        if hours_per_day >= min_break_after_hours and break_minutes < min_break_minutes:
            violations.append(
                f"Break duration ({break_minutes} min) is less than required "
                f"({min_break_minutes} min) for shifts over {min_break_after_hours} hours"
            )
        
        return LaborLawCompliance(
            is_compliant=len(violations) == 0,
            violations=violations,
            warnings=warnings,
            jurisdiction=jurisdiction,
            max_daily_hours=max_daily,
            max_weekly_hours=max_weekly,
            min_break_requirements=f"{min_break_minutes} min after {min_break_after_hours} hours",
        )

    # =========================================================================
    # Schedule CRUD Operations
    # =========================================================================

    def create_schedule(
        self,
        request: CreateWorkScheduleRequest,
        current_user: CurrentUser,
    ) -> Tuple[WorkSchedule, LaborLawCompliance]:
        """
        Create a new work schedule.
        
        Validates labor law compliance before creation.
        """
        # Calculate derived values
        hours_per_day = request.hours_per_week / max(request.days_per_week, 1)
        
        # Validate labor compliance
        compliance = self.validate_labor_compliance(
            hours_per_week=request.hours_per_week,
            hours_per_day=hours_per_day,
            break_minutes=request.break_duration_minutes,
        )
        
        if not compliance.is_compliant:
            raise ValueError(
                f"Schedule violates labor law requirements: {', '.join(compliance.violations)}"
            )
        
        # Build schedule pattern if working pattern provided
        schedule_pattern = None
        if request.working_pattern:
            schedule_pattern = request.working_pattern.dict()
        
        # Create schedule
        schedule = WorkSchedule(
            name=request.name,
            description=request.description,
            schedule_type=request.schedule_type.value,
            hours_per_week=Decimal(str(request.hours_per_week)),
            days_per_week=request.days_per_week,
            start_time=request.start_time,
            end_time=request.end_time,
            is_flexible=request.is_flexible,
            break_duration_minutes=request.break_duration_minutes,
            overtime_eligible=request.overtime_eligible,
            weekend_work_allowed=request.weekend_work_allowed,
            is_template=request.is_template,
            is_active=True,
            schedule_pattern=schedule_pattern,
            applicable_locations=request.applicable_locations,
            applicable_departments=request.applicable_departments,
        )
        
        self.session.add(schedule)
        self.session.commit()
        
        logger.info(f"Created work schedule {schedule.id}: {schedule.name}")
        
        return schedule, compliance

    def get_schedule(self, schedule_id: int) -> Optional[WorkSchedule]:
        """Get a schedule by ID."""
        return self.session.get(WorkSchedule, schedule_id)

    def update_schedule(
        self,
        schedule_id: int,
        request: UpdateWorkScheduleRequest,
        current_user: CurrentUser,
    ) -> Tuple[WorkSchedule, ImpactAssessment]:
        """
        Update a work schedule.
        
        Validates changes and assesses impact on assigned employees.
        """
        schedule = self.session.get(WorkSchedule, schedule_id)
        if not schedule:
            raise ValueError(f"Schedule {schedule_id} not found")
        
        # Calculate hours for validation
        hours_per_week = request.hours_per_week or float(schedule.hours_per_week)
        days_per_week = request.days_per_week or schedule.days_per_week
        hours_per_day = hours_per_week / max(days_per_week, 1)
        break_minutes = request.break_duration_minutes or schedule.break_duration_minutes
        
        # Validate compliance
        compliance = self.validate_labor_compliance(
            hours_per_week=hours_per_week,
            hours_per_day=hours_per_day,
            break_minutes=break_minutes,
        )
        
        if not compliance.is_compliant:
            raise ValueError(
                f"Changes violate labor law requirements: {', '.join(compliance.violations)}"
            )
        
        # Assess impact
        impact = self._assess_update_impact(schedule, request)
        
        # Apply updates
        if request.name is not None:
            schedule.name = request.name
        if request.description is not None:
            schedule.description = request.description
        if request.schedule_type is not None:
            schedule.schedule_type = request.schedule_type.value
        if request.hours_per_week is not None:
            schedule.hours_per_week = Decimal(str(request.hours_per_week))
        if request.days_per_week is not None:
            schedule.days_per_week = request.days_per_week
        if request.start_time is not None:
            schedule.start_time = request.start_time
        if request.end_time is not None:
            schedule.end_time = request.end_time
        if request.is_flexible is not None:
            schedule.is_flexible = request.is_flexible
        if request.break_duration_minutes is not None:
            schedule.break_duration_minutes = request.break_duration_minutes
        if request.overtime_eligible is not None:
            schedule.overtime_eligible = request.overtime_eligible
        if request.weekend_work_allowed is not None:
            schedule.weekend_work_allowed = request.weekend_work_allowed
        if request.is_template is not None:
            schedule.is_template = request.is_template
        if request.is_active is not None:
            schedule.is_active = request.is_active
        if request.working_pattern is not None:
            schedule.schedule_pattern = request.working_pattern.dict()
        if request.applicable_locations is not None:
            schedule.applicable_locations = request.applicable_locations
        if request.applicable_departments is not None:
            schedule.applicable_departments = request.applicable_departments
        
        self.session.commit()
        
        logger.info(f"Updated work schedule {schedule_id}")
        
        return schedule, impact

    def deactivate_schedule(
        self,
        schedule_id: int,
        current_user: CurrentUser,
    ) -> Tuple[WorkSchedule, int, List[int]]:
        """
        Deactivate a work schedule.
        
        Validates employee reassignment requirements.
        Returns (schedule, employees_affected, alternative_schedule_ids).
        """
        schedule = self.session.get(WorkSchedule, schedule_id)
        if not schedule:
            raise ValueError(f"Schedule {schedule_id} not found")
        
        if not schedule.is_active:
            raise ValueError("Schedule is already inactive")
        
        # Count affected employees
        affected_count = self.session.execute(
            select(func.count(Employee.id))
            .where(Employee.work_schedule_id == schedule_id)
            .where(Employee.is_active == True)
        ).scalar() or 0
        
        # Find alternative schedules
        alternatives = []
        if affected_count > 0:
            alt_stmt = select(WorkSchedule.id).where(
                WorkSchedule.is_active == True,
                WorkSchedule.id != schedule_id,
                WorkSchedule.schedule_type == schedule.schedule_type,
            ).limit(5)
            alternatives = [id for id, in self.session.execute(alt_stmt).all()]
        
        # Deactivate
        schedule.is_active = False
        self.session.commit()
        
        logger.info(
            f"Deactivated work schedule {schedule_id}, "
            f"{affected_count} employees affected"
        )
        
        return schedule, affected_count, alternatives

    def _assess_update_impact(
        self,
        schedule: WorkSchedule,
        request: UpdateWorkScheduleRequest,
    ) -> ImpactAssessment:
        """Assess the impact of schedule changes."""
        # Count affected employees
        affected_count = self.session.execute(
            select(func.count(Employee.id))
            .where(Employee.work_schedule_id == schedule.id)
            .where(Employee.is_active == True)
        ).scalar() or 0
        
        # Get affected departments
        dept_stmt = (
            select(Department.name)
            .join(Employee, Employee.department_id == Department.id)
            .where(Employee.work_schedule_id == schedule.id)
            .where(Employee.is_active == True)
            .distinct()
        )
        departments = [name for name, in self.session.execute(dept_stmt).all()]
        
        # Determine if significant changes
        significant_changes = False
        warnings = []
        
        if request.hours_per_week and abs(request.hours_per_week - float(schedule.hours_per_week)) > 4:
            significant_changes = True
            warnings.append("Significant change in weekly hours")
        
        if request.start_time and request.start_time != schedule.start_time:
            significant_changes = True
            warnings.append("Work start time will change")
        
        if request.schedule_type and request.schedule_type.value != schedule.schedule_type:
            significant_changes = True
            warnings.append("Schedule type is changing")
        
        # Determine risk level
        risk = "low"
        if affected_count > 50:
            risk = "high"
        elif affected_count > 10 or significant_changes:
            risk = "medium"
        
        return ImpactAssessment(
            employees_affected=affected_count,
            departments_affected=departments,
            requires_transition=significant_changes and affected_count > 0,
            recommended_transition_days=14 if significant_changes else 7,
            risk_level=risk,
            warnings=warnings,
        )

    # =========================================================================
    # Schedule Queries
    # =========================================================================

    def list_schedules(
        self,
        schedule_type: Optional[str] = None,
        min_hours: Optional[float] = None,
        max_hours: Optional[float] = None,
        is_active: Optional[bool] = None,
        has_assignments: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[WorkSchedule], int]:
        """
        List work schedules with filtering.
        """
        stmt = select(WorkSchedule)
        
        # Apply filters
        if schedule_type:
            stmt = stmt.where(WorkSchedule.schedule_type == schedule_type)
        
        if min_hours is not None:
            stmt = stmt.where(WorkSchedule.hours_per_week >= Decimal(str(min_hours)))
        
        if max_hours is not None:
            stmt = stmt.where(WorkSchedule.hours_per_week <= Decimal(str(max_hours)))
        
        if is_active is not None:
            stmt = stmt.where(WorkSchedule.is_active == is_active)
        
        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.session.execute(count_stmt).scalar() or 0
        
        # Apply pagination
        stmt = (
            stmt
            .order_by(WorkSchedule.name)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        
        schedules = self.session.execute(stmt).scalars().all()
        
        # Filter by assignment if requested
        if has_assignments is not None:
            filtered = []
            for schedule in schedules:
                count = self.session.execute(
                    select(func.count(Employee.id))
                    .where(Employee.work_schedule_id == schedule.id)
                ).scalar() or 0
                
                if has_assignments and count > 0:
                    filtered.append(schedule)
                elif not has_assignments and count == 0:
                    filtered.append(schedule)
            
            schedules = filtered
        
        return list(schedules), total

    def get_assignment_summary(self, schedule_id: int) -> EmployeeAssignmentSummary:
        """Get employee assignment summary for a schedule."""
        # Total assigned
        total = self.session.execute(
            select(func.count(Employee.id))
            .where(Employee.work_schedule_id == schedule_id)
        ).scalar() or 0
        
        # Active assigned
        active = self.session.execute(
            select(func.count(Employee.id))
            .where(Employee.work_schedule_id == schedule_id)
            .where(Employee.is_active == True)
        ).scalar() or 0
        
        # By department
        dept_counts = {}
        dept_stmt = (
            select(Department.name, func.count(Employee.id))
            .join(Employee, Employee.department_id == Department.id)
            .where(Employee.work_schedule_id == schedule_id)
            .where(Employee.is_active == True)
            .group_by(Department.name)
        )
        for name, count in self.session.execute(dept_stmt).all():
            dept_counts[name] = count
        
        # By location
        loc_counts = {}
        loc_stmt = (
            select(Location.name, func.count(Employee.id))
            .join(Employee, Employee.location_id == Location.id)
            .where(Employee.work_schedule_id == schedule_id)
            .where(Employee.is_active == True)
            .group_by(Location.name)
        )
        for name, count in self.session.execute(loc_stmt).all():
            loc_counts[name] = count
        
        return EmployeeAssignmentSummary(
            total_assigned=total,
            active_assigned=active,
            by_department=dept_counts,
            by_location=loc_counts,
        )

    # =========================================================================
    # Response Building
    # =========================================================================

    def build_schedule_response(
        self,
        schedule: WorkSchedule,
    ) -> WorkScheduleResponse:
        """Build a complete schedule response."""
        hours_per_day = float(schedule.hours_per_week) / max(schedule.days_per_week, 1)
        net_hours = float(schedule.hours_per_week) - (
            schedule.break_duration_minutes / 60 * schedule.days_per_week
        )
        
        # Get assignments
        assignments = self.get_assignment_summary(schedule.id)
        
        # Validate compliance
        compliance = self.validate_labor_compliance(
            hours_per_week=float(schedule.hours_per_week),
            hours_per_day=hours_per_day,
            break_minutes=schedule.break_duration_minutes,
        )
        
        # Parse breaks from pattern if available
        breaks = []
        if schedule.schedule_pattern and isinstance(schedule.schedule_pattern, dict):
            pattern_breaks = schedule.schedule_pattern.get("breaks", [])
            for b in pattern_breaks:
                breaks.append(BreakSchedule(**b))
        
        # Parse working pattern
        working_pattern = None
        if schedule.schedule_pattern:
            try:
                working_pattern = WorkingPattern(**schedule.schedule_pattern)
            except Exception:
                pass
        
        return WorkScheduleResponse(
            id=schedule.id,
            name=schedule.name,
            description=schedule.description,
            schedule_type=ScheduleTypeEnum(schedule.schedule_type),
            schedule_type_display=SCHEDULE_TYPE_DISPLAY.get(
                schedule.schedule_type,
                schedule.schedule_type.title()
            ),
            hours_per_week=float(schedule.hours_per_week),
            days_per_week=schedule.days_per_week,
            start_time=schedule.start_time,
            end_time=schedule.end_time,
            is_flexible=schedule.is_flexible,
            hours_per_day=round(hours_per_day, 2),
            break_duration_minutes=schedule.break_duration_minutes,
            breaks=breaks,
            net_working_hours=round(net_hours, 2),
            working_pattern=working_pattern,
            overtime_eligible=schedule.overtime_eligible,
            weekend_work_allowed=schedule.weekend_work_allowed,
            is_template=schedule.is_template,
            is_active=schedule.is_active,
            applicable_locations=schedule.applicable_locations,
            applicable_departments=schedule.applicable_departments,
            assignments=assignments,
            labor_compliance=compliance,
            created_at=schedule.created_at,
            updated_at=schedule.updated_at,
        )

