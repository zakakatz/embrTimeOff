"""Pydantic schemas for work schedule management API."""

from datetime import datetime, time
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, validator


class ScheduleTypeEnum(str, Enum):
    """Types of work schedules."""
    STANDARD = "standard"
    SHIFT = "shift"
    COMPRESSED = "compressed"
    FLEXIBLE = "flexible"
    PART_TIME = "part_time"
    CUSTOM = "custom"


class DayOfWeekEnum(str, Enum):
    """Days of the week."""
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


# =============================================================================
# Working Pattern Models
# =============================================================================

class DailySchedule(BaseModel):
    """Schedule for a single day."""
    day: DayOfWeekEnum = Field(..., description="Day of week")
    is_working_day: bool = Field(default=True, description="Whether this is a working day")
    start_time: Optional[str] = Field(default=None, description="Start time (HH:MM)")
    end_time: Optional[str] = Field(default=None, description="End time (HH:MM)")
    hours: Optional[float] = Field(default=None, ge=0, le=24, description="Working hours")


class BreakSchedule(BaseModel):
    """Break schedule configuration."""
    break_type: str = Field(..., description="Type: lunch, rest, meal")
    duration_minutes: int = Field(..., ge=0, le=120, description="Duration in minutes")
    start_time: Optional[str] = Field(default=None, description="Fixed start time if applicable")
    is_paid: bool = Field(default=False, description="Whether break is paid")
    is_mandatory: bool = Field(default=True, description="Whether break is mandatory")


class WorkingPattern(BaseModel):
    """Complete working pattern definition."""
    daily_schedules: List[DailySchedule] = Field(
        default_factory=list,
        description="Schedule for each day of the week",
    )
    breaks: List[BreakSchedule] = Field(
        default_factory=list,
        description="Break schedule configuration",
    )
    core_hours_start: Optional[str] = Field(
        default=None,
        description="Core hours start time for flexible schedules",
    )
    core_hours_end: Optional[str] = Field(
        default=None,
        description="Core hours end time for flexible schedules",
    )
    rotation_pattern: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Rotation pattern for shift schedules",
    )


# =============================================================================
# Labor Compliance Models
# =============================================================================

class LaborLawCompliance(BaseModel):
    """Labor law compliance validation result."""
    is_compliant: bool = Field(..., description="Whether schedule is compliant")
    violations: List[str] = Field(
        default_factory=list,
        description="List of violations",
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Warnings (not violations but recommendations)",
    )
    jurisdiction: str = Field(default="default", description="Applicable jurisdiction")
    max_daily_hours: float = Field(default=10, description="Maximum daily hours allowed")
    max_weekly_hours: float = Field(default=40, description="Maximum weekly hours allowed")
    min_break_requirements: str = Field(
        default="30 min after 6 hours",
        description="Break requirements",
    )


# =============================================================================
# Request Models
# =============================================================================

class CreateWorkScheduleRequest(BaseModel):
    """Request to create a new work schedule."""
    name: str = Field(..., min_length=1, max_length=100, description="Schedule name")
    description: Optional[str] = Field(default=None, max_length=500, description="Description")
    schedule_type: ScheduleTypeEnum = Field(
        default=ScheduleTypeEnum.STANDARD,
        description="Schedule type",
    )
    
    # Time configuration
    hours_per_week: float = Field(
        default=40.0,
        ge=0,
        le=168,
        description="Total hours per week",
    )
    days_per_week: int = Field(
        default=5,
        ge=1,
        le=7,
        description="Working days per week",
    )
    start_time: Optional[str] = Field(
        default="09:00",
        description="Default start time (HH:MM)",
    )
    end_time: Optional[str] = Field(
        default="17:00",
        description="Default end time (HH:MM)",
    )
    is_flexible: bool = Field(
        default=False,
        description="Whether schedule has flexible hours",
    )
    
    # Break configuration
    break_duration_minutes: int = Field(
        default=60,
        ge=0,
        le=180,
        description="Total break time per day in minutes",
    )
    breaks: Optional[List[BreakSchedule]] = Field(
        default=None,
        description="Detailed break schedule",
    )
    
    # Working pattern
    working_pattern: Optional[WorkingPattern] = Field(
        default=None,
        description="Detailed working pattern",
    )
    
    # Overtime and weekend
    overtime_eligible: bool = Field(
        default=True,
        description="Whether overtime is allowed",
    )
    weekend_work_allowed: bool = Field(
        default=False,
        description="Whether weekend work is permitted",
    )
    
    # Template settings
    is_template: bool = Field(
        default=True,
        description="Can be used as a template",
    )
    
    # Applicability
    applicable_locations: Optional[List[int]] = Field(
        default=None,
        description="Location IDs where applicable",
    )
    applicable_departments: Optional[List[int]] = Field(
        default=None,
        description="Department IDs where applicable",
    )

    @validator("start_time", "end_time")
    def validate_time_format(cls, v: Optional[str]) -> Optional[str]:
        """Validate time format."""
        if v is None:
            return v
        try:
            parts = v.split(":")
            if len(parts) != 2:
                raise ValueError("Invalid time format")
            hour, minute = int(parts[0]), int(parts[1])
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError("Invalid time values")
            return f"{hour:02d}:{minute:02d}"
        except (ValueError, IndexError):
            raise ValueError("Time must be in HH:MM format")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Standard 9-5",
                "description": "Standard 40-hour work week",
                "schedule_type": "standard",
                "hours_per_week": 40.0,
                "days_per_week": 5,
                "start_time": "09:00",
                "end_time": "17:00",
                "break_duration_minutes": 60,
                "overtime_eligible": True,
            }
        }


class UpdateWorkScheduleRequest(BaseModel):
    """Request to update a work schedule."""
    name: Optional[str] = Field(default=None, max_length=100, description="Schedule name")
    description: Optional[str] = Field(default=None, max_length=500, description="Description")
    schedule_type: Optional[ScheduleTypeEnum] = Field(default=None, description="Schedule type")
    
    # Time configuration
    hours_per_week: Optional[float] = Field(
        default=None,
        ge=0,
        le=168,
        description="Total hours per week",
    )
    days_per_week: Optional[int] = Field(
        default=None,
        ge=1,
        le=7,
        description="Working days per week",
    )
    start_time: Optional[str] = Field(default=None, description="Default start time")
    end_time: Optional[str] = Field(default=None, description="Default end time")
    is_flexible: Optional[bool] = Field(default=None, description="Flexible hours")
    
    # Break configuration
    break_duration_minutes: Optional[int] = Field(
        default=None,
        ge=0,
        le=180,
        description="Break time per day in minutes",
    )
    breaks: Optional[List[BreakSchedule]] = Field(default=None, description="Break schedule")
    
    # Working pattern
    working_pattern: Optional[WorkingPattern] = Field(default=None, description="Working pattern")
    
    # Overtime and weekend
    overtime_eligible: Optional[bool] = Field(default=None, description="Overtime allowed")
    weekend_work_allowed: Optional[bool] = Field(default=None, description="Weekend work allowed")
    
    # Template settings
    is_template: Optional[bool] = Field(default=None, description="Template flag")
    is_active: Optional[bool] = Field(default=None, description="Active status")
    
    # Applicability
    applicable_locations: Optional[List[int]] = Field(default=None, description="Location IDs")
    applicable_departments: Optional[List[int]] = Field(default=None, description="Department IDs")
    
    # Change management
    transition_date: Optional[datetime] = Field(
        default=None,
        description="When changes take effect",
    )
    notify_employees: bool = Field(
        default=True,
        description="Notify affected employees",
    )
    change_reason: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Reason for change",
    )


# =============================================================================
# Response Models
# =============================================================================

class EmployeeAssignmentSummary(BaseModel):
    """Summary of employee assignments to a schedule."""
    total_assigned: int = Field(default=0, description="Total employees assigned")
    active_assigned: int = Field(default=0, description="Active employees assigned")
    by_department: Dict[str, int] = Field(
        default_factory=dict,
        description="Count by department",
    )
    by_location: Dict[str, int] = Field(
        default_factory=dict,
        description="Count by location",
    )


class ImpactAssessment(BaseModel):
    """Impact assessment for schedule changes."""
    employees_affected: int = Field(..., description="Number of employees affected")
    departments_affected: List[str] = Field(
        default_factory=list,
        description="Affected departments",
    )
    requires_transition: bool = Field(
        default=False,
        description="Whether transition period is needed",
    )
    recommended_transition_days: int = Field(
        default=14,
        description="Recommended transition period in days",
    )
    risk_level: str = Field(
        default="low",
        description="Risk level: low, medium, high",
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Warnings about the change",
    )


class WorkScheduleResponse(BaseModel):
    """Complete work schedule response."""
    id: int = Field(..., description="Schedule ID")
    name: str = Field(..., description="Schedule name")
    description: Optional[str] = Field(default=None, description="Description")
    schedule_type: ScheduleTypeEnum = Field(..., description="Schedule type")
    schedule_type_display: str = Field(..., description="Human-readable type")
    
    # Time configuration
    hours_per_week: float = Field(..., description="Hours per week")
    days_per_week: int = Field(..., description="Days per week")
    start_time: Optional[str] = Field(default=None, description="Start time")
    end_time: Optional[str] = Field(default=None, description="End time")
    is_flexible: bool = Field(..., description="Flexible hours flag")
    hours_per_day: float = Field(..., description="Average hours per day")
    
    # Break configuration
    break_duration_minutes: int = Field(..., description="Break duration")
    breaks: List[BreakSchedule] = Field(
        default_factory=list,
        description="Break schedule",
    )
    net_working_hours: float = Field(
        ...,
        description="Net working hours after breaks",
    )
    
    # Working pattern
    working_pattern: Optional[WorkingPattern] = Field(
        default=None,
        description="Working pattern",
    )
    
    # Overtime and weekend
    overtime_eligible: bool = Field(..., description="Overtime allowed")
    weekend_work_allowed: bool = Field(..., description="Weekend work allowed")
    
    # Template and status
    is_template: bool = Field(..., description="Is template")
    is_active: bool = Field(..., description="Is active")
    
    # Applicability
    applicable_locations: Optional[List[int]] = Field(
        default=None,
        description="Location IDs",
    )
    applicable_departments: Optional[List[int]] = Field(
        default=None,
        description="Department IDs",
    )
    
    # Assignments
    assignments: EmployeeAssignmentSummary = Field(
        ...,
        description="Employee assignments",
    )
    
    # Compliance
    labor_compliance: LaborLawCompliance = Field(
        ...,
        description="Labor law compliance",
    )
    
    # Timestamps
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(default=None, description="Last update")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class WorkScheduleCreateResponse(BaseModel):
    """Response for schedule creation."""
    schedule: WorkScheduleResponse = Field(..., description="Created schedule")
    compliance_validated: bool = Field(..., description="Compliance validation passed")
    message: str = Field(..., description="Success message")


class WorkScheduleUpdateResponse(BaseModel):
    """Response for schedule update."""
    schedule: WorkScheduleResponse = Field(..., description="Updated schedule")
    impact_assessment: ImpactAssessment = Field(..., description="Impact assessment")
    notifications_sent: int = Field(default=0, description="Notifications sent")
    message: str = Field(..., description="Success message")


class WorkScheduleDeleteResponse(BaseModel):
    """Response for schedule deletion/deactivation."""
    schedule_id: int = Field(..., description="Schedule ID")
    deactivated: bool = Field(..., description="Whether deactivated")
    employees_affected: int = Field(..., description="Employees affected")
    reassignment_required: bool = Field(..., description="Reassignment needed")
    suggested_alternatives: List[int] = Field(
        default_factory=list,
        description="Suggested alternative schedule IDs",
    )
    transition_guidance: str = Field(..., description="Transition guidance")
    message: str = Field(..., description="Status message")


class WorkScheduleListResponse(BaseModel):
    """Response for schedule listing."""
    schedules: List[WorkScheduleResponse] = Field(..., description="List of schedules")
    total: int = Field(..., description="Total count")
    page: int = Field(default=1, description="Current page")
    page_size: int = Field(default=20, description="Page size")
    
    # Summary statistics
    total_employees_scheduled: int = Field(
        default=0,
        description="Total employees across all schedules",
    )
    schedule_type_counts: Dict[str, int] = Field(
        default_factory=dict,
        description="Count by schedule type",
    )

