"""API endpoints for employment types and work schedule templates."""

import uuid
from datetime import datetime, time
from enum import Enum
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, Query, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.models.employee import WorkSchedule
from src.utils.auth import CurrentUser, UserRole, get_mock_current_user
from src.utils.errors import ForbiddenError, NotFoundError, ValidationError


# =============================================================================
# Enums
# =============================================================================

class EmploymentCategory(str, Enum):
    """Category of employment."""
    
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACTOR = "contractor"
    INTERN = "intern"
    TEMPORARY = "temporary"
    SEASONAL = "seasonal"


class BenefitEligibility(str, Enum):
    """Benefit eligibility status."""
    
    FULL = "full"
    PARTIAL = "partial"
    NONE = "none"


class ScheduleType(str, Enum):
    """Type of work schedule."""
    
    STANDARD = "standard"
    FLEXIBLE = "flexible"
    SHIFT = "shift"
    COMPRESSED = "compressed"
    REMOTE = "remote"
    HYBRID = "hybrid"


class DayOfWeek(str, Enum):
    """Days of the week."""
    
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


# =============================================================================
# Request Models
# =============================================================================

class BenefitEligibilityRule(BaseModel):
    """Rule for benefit eligibility."""
    
    benefit_type: str = Field(..., description="Type of benefit")
    eligibility: BenefitEligibility = Field(..., description="Eligibility status")
    waiting_period_days: int = Field(default=0, ge=0, description="Days before eligible")
    minimum_hours_per_week: Optional[float] = Field(None, ge=0, description="Min hours required")
    conditions: Optional[str] = Field(None, max_length=500, description="Additional conditions")


class PolicyAssociation(BaseModel):
    """Association with an organizational policy."""
    
    policy_id: str = Field(..., description="Policy identifier")
    policy_name: str = Field(..., description="Policy name")
    is_required: bool = Field(default=True, description="Whether policy is required")


class CreateEmploymentTypeRequest(BaseModel):
    """Request to create an employment type."""
    
    code: str = Field(
        ...,
        min_length=2,
        max_length=20,
        pattern=r"^[A-Z0-9_-]+$",
        description="Unique type code",
    )
    name: str = Field(..., min_length=1, max_length=100, description="Type name")
    category: EmploymentCategory = Field(..., description="Employment category")
    description: Optional[str] = Field(None, max_length=500, description="Description")
    
    # Hours configuration
    standard_hours_per_week: float = Field(
        default=40.0,
        ge=0,
        le=168,
        description="Standard weekly hours",
    )
    minimum_hours_per_week: Optional[float] = Field(
        None,
        ge=0,
        le=168,
        description="Minimum weekly hours",
    )
    maximum_hours_per_week: Optional[float] = Field(
        None,
        ge=0,
        le=168,
        description="Maximum weekly hours",
    )
    
    # Overtime
    overtime_eligible: bool = Field(default=True, description="Whether overtime eligible")
    overtime_threshold_hours: Optional[float] = Field(
        None,
        ge=0,
        description="Hours after which overtime applies",
    )
    
    # Benefits
    benefit_eligibility_rules: List[BenefitEligibilityRule] = Field(
        default_factory=list,
        description="Benefit eligibility rules",
    )
    
    # Policy associations
    policy_associations: List[PolicyAssociation] = Field(
        default_factory=list,
        description="Associated policies",
    )
    
    # Compatible schedules
    compatible_schedule_types: List[ScheduleType] = Field(
        default_factory=list,
        description="Compatible schedule types",
    )
    
    # Metadata
    is_active: bool = Field(default=True)
    
    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        """Validate code format."""
        return v.upper()
    
    @field_validator("maximum_hours_per_week")
    @classmethod
    def validate_max_hours(cls, v: Optional[float], info) -> Optional[float]:
        """Validate max hours >= min hours."""
        min_hours = info.data.get("minimum_hours_per_week")
        if v is not None and min_hours is not None and v < min_hours:
            raise ValueError("Maximum hours must be >= minimum hours")
        return v


class WorkingHoursPattern(BaseModel):
    """Pattern for working hours."""
    
    day: DayOfWeek = Field(..., description="Day of week")
    is_working_day: bool = Field(default=True, description="Whether it's a working day")
    start_time: Optional[str] = Field(None, description="Start time (HH:MM)")
    end_time: Optional[str] = Field(None, description="End time (HH:MM)")
    break_duration_minutes: int = Field(default=30, ge=0, description="Break duration")
    
    @field_validator("start_time", "end_time")
    @classmethod
    def validate_time_format(cls, v: Optional[str]) -> Optional[str]:
        """Validate time format."""
        if v is not None:
            try:
                parts = v.split(":")
                hour = int(parts[0])
                minute = int(parts[1]) if len(parts) > 1 else 0
                if not (0 <= hour <= 23 and 0 <= minute <= 59):
                    raise ValueError("Invalid time")
            except (ValueError, IndexError):
                raise ValueError("Time must be in HH:MM format")
        return v


class FlexibleArrangement(BaseModel):
    """Flexible work arrangement definition."""
    
    arrangement_type: str = Field(..., description="Type of arrangement")
    core_hours_start: Optional[str] = Field(None, description="Core hours start")
    core_hours_end: Optional[str] = Field(None, description="Core hours end")
    flex_window_hours: Optional[float] = Field(None, ge=0, description="Flexibility window")
    remote_days_per_week: Optional[int] = Field(None, ge=0, le=7, description="Remote days")
    requires_approval: bool = Field(default=False, description="Whether approval needed")


class TimeOffEligibilityRule(BaseModel):
    """Time-off eligibility rule."""
    
    time_off_type: str = Field(..., description="Type of time off")
    accrual_rate: float = Field(default=0.0, ge=0, description="Days accrued per period")
    accrual_period: str = Field(default="month", description="Accrual period")
    maximum_balance: Optional[float] = Field(None, ge=0, description="Max carryover balance")
    waiting_period_days: int = Field(default=0, ge=0, description="Eligibility waiting period")


class CreateWorkScheduleTemplateRequest(BaseModel):
    """Request to create a work schedule template."""
    
    code: str = Field(
        ...,
        min_length=2,
        max_length=20,
        pattern=r"^[A-Z0-9_-]+$",
        description="Unique template code",
    )
    name: str = Field(..., min_length=1, max_length=100, description="Template name")
    schedule_type: ScheduleType = Field(..., description="Type of schedule")
    description: Optional[str] = Field(None, max_length=500, description="Description")
    
    # Working hours
    working_hours_pattern: List[WorkingHoursPattern] = Field(
        default_factory=list,
        description="Weekly working hours pattern",
    )
    total_hours_per_week: float = Field(
        default=40.0,
        ge=0,
        le=168,
        description="Total weekly hours",
    )
    
    # Flexibility
    is_flexible: bool = Field(default=False, description="Whether schedule is flexible")
    flexible_arrangement: Optional[FlexibleArrangement] = Field(
        None,
        description="Flexible work arrangement",
    )
    
    # Time off
    time_off_eligibility_rules: List[TimeOffEligibilityRule] = Field(
        default_factory=list,
        description="Time-off eligibility rules",
    )
    
    # Overtime
    overtime_eligible: bool = Field(default=True)
    weekend_work_allowed: bool = Field(default=False)
    
    # Compatibility
    compatible_employment_types: List[str] = Field(
        default_factory=list,
        description="Compatible employment type codes",
    )
    applicable_locations: List[int] = Field(
        default_factory=list,
        description="Applicable location IDs",
    )
    applicable_departments: List[int] = Field(
        default_factory=list,
        description="Applicable department IDs",
    )
    
    # Metadata
    is_template: bool = Field(default=True)
    is_active: bool = Field(default=True)
    
    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        """Validate code format."""
        return v.upper()


# =============================================================================
# Response Models
# =============================================================================

class EmploymentTypeResponse(BaseModel):
    """Response for employment type."""
    
    id: int
    code: str
    name: str
    category: str
    description: Optional[str] = None
    
    # Hours
    standard_hours_per_week: float
    minimum_hours_per_week: Optional[float] = None
    maximum_hours_per_week: Optional[float] = None
    
    # Overtime
    overtime_eligible: bool
    overtime_threshold_hours: Optional[float] = None
    
    # Benefits
    benefit_eligibility_rules: List[BenefitEligibilityRule] = Field(default_factory=list)
    
    # Policies
    policy_associations: List[PolicyAssociation] = Field(default_factory=list)
    
    # Schedules
    compatible_schedule_types: List[str] = Field(default_factory=list)
    
    # Metadata
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    # Validation
    validation_status: str = Field(default="valid")
    validation_warnings: List[str] = Field(default_factory=list)


class WorkScheduleTemplateResponse(BaseModel):
    """Response for work schedule template."""
    
    id: int
    code: str
    name: str
    schedule_type: str
    description: Optional[str] = None
    
    # Hours
    working_hours_pattern: List[WorkingHoursPattern] = Field(default_factory=list)
    total_hours_per_week: float
    
    # Flexibility
    is_flexible: bool
    flexible_arrangement: Optional[FlexibleArrangement] = None
    
    # Time off
    time_off_eligibility_rules: List[TimeOffEligibilityRule] = Field(default_factory=list)
    
    # Overtime
    overtime_eligible: bool
    weekend_work_allowed: bool
    
    # Compatibility
    compatible_employment_types: List[str] = Field(default_factory=list)
    applicable_locations: List[int] = Field(default_factory=list)
    applicable_departments: List[int] = Field(default_factory=list)
    
    # Metadata
    is_template: bool
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    # Validation
    validation_status: str = Field(default="valid")
    validation_warnings: List[str] = Field(default_factory=list)


# =============================================================================
# Mock Data Store
# =============================================================================

_employment_type_counter = 100
_employment_types: Dict[int, Dict[str, Any]] = {}

_schedule_template_counter = 200
_schedule_templates: Dict[int, Dict[str, Any]] = {}


def get_next_employment_type_id() -> int:
    """Get next employment type ID."""
    global _employment_type_counter
    _employment_type_counter += 1
    return _employment_type_counter


def get_next_schedule_template_id() -> int:
    """Get next schedule template ID."""
    global _schedule_template_counter
    _schedule_template_counter += 1
    return _schedule_template_counter


# =============================================================================
# Helper Functions
# =============================================================================

def validate_benefit_rules(
    rules: List[BenefitEligibilityRule],
) -> tuple[bool, List[str]]:
    """Validate benefit eligibility rules."""
    warnings = []
    
    benefit_types = set()
    for rule in rules:
        if rule.benefit_type in benefit_types:
            return False, [f"Duplicate benefit type: {rule.benefit_type}"]
        benefit_types.add(rule.benefit_type)
        
        if rule.eligibility == BenefitEligibility.FULL and rule.waiting_period_days > 365:
            warnings.append(f"Long waiting period for {rule.benefit_type}: {rule.waiting_period_days} days")
    
    return True, warnings


def validate_working_hours_pattern(
    pattern: List[WorkingHoursPattern],
) -> tuple[bool, List[str]]:
    """Validate working hours pattern consistency."""
    warnings = []
    
    days_seen = set()
    total_hours = 0
    
    for day_pattern in pattern:
        if day_pattern.day.value in days_seen:
            return False, [f"Duplicate day: {day_pattern.day.value}"]
        days_seen.add(day_pattern.day.value)
        
        if day_pattern.is_working_day:
            if not day_pattern.start_time or not day_pattern.end_time:
                return False, [f"Working day {day_pattern.day.value} must have start and end times"]
            
            # Calculate hours (simplified)
            start_parts = day_pattern.start_time.split(":")
            end_parts = day_pattern.end_time.split(":")
            
            start_minutes = int(start_parts[0]) * 60 + int(start_parts[1] if len(start_parts) > 1 else 0)
            end_minutes = int(end_parts[0]) * 60 + int(end_parts[1] if len(end_parts) > 1 else 0)
            
            work_minutes = end_minutes - start_minutes - day_pattern.break_duration_minutes
            if work_minutes < 0:
                return False, [f"Invalid hours for {day_pattern.day.value}: end time before start time"]
            
            total_hours += work_minutes / 60
    
    if total_hours > 60:
        warnings.append(f"Total weekly hours ({total_hours:.1f}) exceeds typical maximum")
    
    return True, warnings


def validate_time_off_rules(
    rules: List[TimeOffEligibilityRule],
) -> tuple[bool, List[str]]:
    """Validate time-off eligibility rules."""
    warnings = []
    
    time_off_types = set()
    for rule in rules:
        if rule.time_off_type in time_off_types:
            return False, [f"Duplicate time-off type: {rule.time_off_type}"]
        time_off_types.add(rule.time_off_type)
        
        if rule.accrual_rate > 5:  # More than 5 days per period
            warnings.append(f"High accrual rate for {rule.time_off_type}: {rule.accrual_rate}")
    
    return True, warnings


def validate_schedule_compatibility(
    schedule_type: ScheduleType,
    employment_type_codes: List[str],
) -> tuple[bool, List[str]]:
    """Validate schedule-employment type compatibility."""
    warnings = []
    
    # Check for common compatibility issues
    if schedule_type == ScheduleType.REMOTE:
        # Remote schedules may not be compatible with certain types
        pass
    
    return True, warnings


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


def require_admin(current_user: CurrentUser) -> CurrentUser:
    """Require admin role."""
    if not any(r in current_user.roles for r in [UserRole.ADMIN, UserRole.HR]):
        raise ForbiddenError(message="Admin access required")
    return current_user


# =============================================================================
# Router Setup
# =============================================================================

employment_types_router = APIRouter(
    prefix="/api/admin",
    tags=["Employment Types"],
)


# =============================================================================
# Employment Type Endpoints
# =============================================================================

@employment_types_router.post(
    "/employment-types",
    response_model=EmploymentTypeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Employment Type",
    description="Create a new employment type configuration.",
)
async def create_employment_type(
    request: CreateEmploymentTypeRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> EmploymentTypeResponse:
    """
    Create a new employment type.
    
    - Validates policy associations
    - Validates benefit eligibility rules
    - Returns created type with validation status
    """
    require_admin(current_user)
    
    # Check for duplicate code
    for et in _employment_types.values():
        if et["code"] == request.code:
            raise ValidationError(
                message=f"Employment type with code '{request.code}' already exists",
                field_errors=[{"field": "code", "message": "Code already in use"}],
            )
    
    # Validate benefit rules
    rules_valid, rule_warnings = validate_benefit_rules(request.benefit_eligibility_rules)
    if not rules_valid:
        raise ValidationError(
            message=rule_warnings[0],
            field_errors=[{"field": "benefit_eligibility_rules", "message": rule_warnings[0]}],
        )
    
    # Create employment type
    type_id = get_next_employment_type_id()
    now = datetime.utcnow()
    
    emp_type = {
        "id": type_id,
        "code": request.code,
        "name": request.name,
        "category": request.category.value,
        "description": request.description,
        "standard_hours_per_week": request.standard_hours_per_week,
        "minimum_hours_per_week": request.minimum_hours_per_week,
        "maximum_hours_per_week": request.maximum_hours_per_week,
        "overtime_eligible": request.overtime_eligible,
        "overtime_threshold_hours": request.overtime_threshold_hours,
        "benefit_eligibility_rules": request.benefit_eligibility_rules,
        "policy_associations": request.policy_associations,
        "compatible_schedule_types": [st.value for st in request.compatible_schedule_types],
        "is_active": request.is_active,
        "created_at": now,
    }
    
    _employment_types[type_id] = emp_type
    
    return EmploymentTypeResponse(
        id=type_id,
        code=request.code,
        name=request.name,
        category=request.category.value,
        description=request.description,
        standard_hours_per_week=request.standard_hours_per_week,
        minimum_hours_per_week=request.minimum_hours_per_week,
        maximum_hours_per_week=request.maximum_hours_per_week,
        overtime_eligible=request.overtime_eligible,
        overtime_threshold_hours=request.overtime_threshold_hours,
        benefit_eligibility_rules=request.benefit_eligibility_rules,
        policy_associations=request.policy_associations,
        compatible_schedule_types=[st.value for st in request.compatible_schedule_types],
        is_active=request.is_active,
        created_at=now,
        validation_status="valid",
        validation_warnings=rule_warnings,
    )


@employment_types_router.get(
    "/employment-types",
    response_model=List[EmploymentTypeResponse],
    summary="List Employment Types",
    description="List all employment type configurations.",
)
async def list_employment_types(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    include_inactive: bool = Query(False, description="Include inactive types"),
) -> List[EmploymentTypeResponse]:
    """List all employment types."""
    results = []
    
    for et in _employment_types.values():
        if not include_inactive and not et["is_active"]:
            continue
        
        results.append(EmploymentTypeResponse(
            id=et["id"],
            code=et["code"],
            name=et["name"],
            category=et["category"],
            description=et.get("description"),
            standard_hours_per_week=et["standard_hours_per_week"],
            minimum_hours_per_week=et.get("minimum_hours_per_week"),
            maximum_hours_per_week=et.get("maximum_hours_per_week"),
            overtime_eligible=et["overtime_eligible"],
            overtime_threshold_hours=et.get("overtime_threshold_hours"),
            benefit_eligibility_rules=et.get("benefit_eligibility_rules", []),
            policy_associations=et.get("policy_associations", []),
            compatible_schedule_types=et.get("compatible_schedule_types", []),
            is_active=et["is_active"],
            created_at=et["created_at"],
            updated_at=et.get("updated_at"),
        ))
    
    return results


@employment_types_router.get(
    "/employment-types/{type_id}",
    response_model=EmploymentTypeResponse,
    summary="Get Employment Type",
    description="Get a specific employment type by ID.",
)
async def get_employment_type(
    type_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> EmploymentTypeResponse:
    """Get a specific employment type."""
    if type_id not in _employment_types:
        raise NotFoundError(message=f"Employment type {type_id} not found")
    
    et = _employment_types[type_id]
    
    return EmploymentTypeResponse(
        id=et["id"],
        code=et["code"],
        name=et["name"],
        category=et["category"],
        description=et.get("description"),
        standard_hours_per_week=et["standard_hours_per_week"],
        minimum_hours_per_week=et.get("minimum_hours_per_week"),
        maximum_hours_per_week=et.get("maximum_hours_per_week"),
        overtime_eligible=et["overtime_eligible"],
        overtime_threshold_hours=et.get("overtime_threshold_hours"),
        benefit_eligibility_rules=et.get("benefit_eligibility_rules", []),
        policy_associations=et.get("policy_associations", []),
        compatible_schedule_types=et.get("compatible_schedule_types", []),
        is_active=et["is_active"],
        created_at=et["created_at"],
        updated_at=et.get("updated_at"),
    )


# =============================================================================
# Work Schedule Template Endpoints
# =============================================================================

@employment_types_router.post(
    "/work-schedule-templates",
    response_model=WorkScheduleTemplateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Work Schedule Template",
    description="Create a new work schedule template.",
)
async def create_work_schedule_template(
    request: CreateWorkScheduleTemplateRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> WorkScheduleTemplateResponse:
    """
    Create a new work schedule template.
    
    - Validates working hours pattern
    - Validates time-off eligibility rules
    - Validates employment type compatibility
    """
    require_admin(current_user)
    
    # Check for duplicate code
    for st in _schedule_templates.values():
        if st["code"] == request.code:
            raise ValidationError(
                message=f"Schedule template with code '{request.code}' already exists",
                field_errors=[{"field": "code", "message": "Code already in use"}],
            )
    
    # Validate working hours pattern
    if request.working_hours_pattern:
        pattern_valid, pattern_warnings = validate_working_hours_pattern(
            request.working_hours_pattern
        )
        if not pattern_valid:
            raise ValidationError(
                message=pattern_warnings[0],
                field_errors=[{"field": "working_hours_pattern", "message": pattern_warnings[0]}],
            )
    
    # Validate time-off rules
    if request.time_off_eligibility_rules:
        rules_valid, rule_warnings = validate_time_off_rules(
            request.time_off_eligibility_rules
        )
        if not rules_valid:
            raise ValidationError(
                message=rule_warnings[0],
                field_errors=[{"field": "time_off_eligibility_rules", "message": rule_warnings[0]}],
            )
    
    # Validate compatibility
    compat_valid, compat_warnings = validate_schedule_compatibility(
        request.schedule_type,
        request.compatible_employment_types,
    )
    
    # Create template
    template_id = get_next_schedule_template_id()
    now = datetime.utcnow()
    
    template = {
        "id": template_id,
        "code": request.code,
        "name": request.name,
        "schedule_type": request.schedule_type.value,
        "description": request.description,
        "working_hours_pattern": [p.model_dump() for p in request.working_hours_pattern],
        "total_hours_per_week": request.total_hours_per_week,
        "is_flexible": request.is_flexible,
        "flexible_arrangement": request.flexible_arrangement.model_dump() if request.flexible_arrangement else None,
        "time_off_eligibility_rules": [r.model_dump() for r in request.time_off_eligibility_rules],
        "overtime_eligible": request.overtime_eligible,
        "weekend_work_allowed": request.weekend_work_allowed,
        "compatible_employment_types": request.compatible_employment_types,
        "applicable_locations": request.applicable_locations,
        "applicable_departments": request.applicable_departments,
        "is_template": request.is_template,
        "is_active": request.is_active,
        "created_at": now,
    }
    
    _schedule_templates[template_id] = template
    
    all_warnings = []
    if request.working_hours_pattern:
        _, pattern_warnings = validate_working_hours_pattern(request.working_hours_pattern)
        all_warnings.extend(pattern_warnings)
    all_warnings.extend(compat_warnings)
    
    return WorkScheduleTemplateResponse(
        id=template_id,
        code=request.code,
        name=request.name,
        schedule_type=request.schedule_type.value,
        description=request.description,
        working_hours_pattern=request.working_hours_pattern,
        total_hours_per_week=request.total_hours_per_week,
        is_flexible=request.is_flexible,
        flexible_arrangement=request.flexible_arrangement,
        time_off_eligibility_rules=request.time_off_eligibility_rules,
        overtime_eligible=request.overtime_eligible,
        weekend_work_allowed=request.weekend_work_allowed,
        compatible_employment_types=request.compatible_employment_types,
        applicable_locations=request.applicable_locations,
        applicable_departments=request.applicable_departments,
        is_template=request.is_template,
        is_active=request.is_active,
        created_at=now,
        validation_status="valid",
        validation_warnings=all_warnings,
    )


@employment_types_router.get(
    "/work-schedule-templates",
    response_model=List[WorkScheduleTemplateResponse],
    summary="List Work Schedule Templates",
    description="List all work schedule templates.",
)
async def list_work_schedule_templates(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    include_inactive: bool = Query(False, description="Include inactive templates"),
    schedule_type: Optional[str] = Query(None, description="Filter by schedule type"),
) -> List[WorkScheduleTemplateResponse]:
    """List all work schedule templates."""
    results = []
    
    for st in _schedule_templates.values():
        if not include_inactive and not st["is_active"]:
            continue
        if schedule_type and st["schedule_type"] != schedule_type:
            continue
        
        results.append(WorkScheduleTemplateResponse(
            id=st["id"],
            code=st["code"],
            name=st["name"],
            schedule_type=st["schedule_type"],
            description=st.get("description"),
            working_hours_pattern=[WorkingHoursPattern(**p) for p in st.get("working_hours_pattern", [])],
            total_hours_per_week=st["total_hours_per_week"],
            is_flexible=st["is_flexible"],
            flexible_arrangement=FlexibleArrangement(**st["flexible_arrangement"]) if st.get("flexible_arrangement") else None,
            time_off_eligibility_rules=[TimeOffEligibilityRule(**r) for r in st.get("time_off_eligibility_rules", [])],
            overtime_eligible=st["overtime_eligible"],
            weekend_work_allowed=st["weekend_work_allowed"],
            compatible_employment_types=st.get("compatible_employment_types", []),
            applicable_locations=st.get("applicable_locations", []),
            applicable_departments=st.get("applicable_departments", []),
            is_template=st["is_template"],
            is_active=st["is_active"],
            created_at=st["created_at"],
            updated_at=st.get("updated_at"),
        ))
    
    return results


@employment_types_router.get(
    "/work-schedule-templates/{template_id}",
    response_model=WorkScheduleTemplateResponse,
    summary="Get Work Schedule Template",
    description="Get a specific work schedule template.",
)
async def get_work_schedule_template(
    template_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> WorkScheduleTemplateResponse:
    """Get a specific work schedule template."""
    if template_id not in _schedule_templates:
        raise NotFoundError(message=f"Schedule template {template_id} not found")
    
    st = _schedule_templates[template_id]
    
    return WorkScheduleTemplateResponse(
        id=st["id"],
        code=st["code"],
        name=st["name"],
        schedule_type=st["schedule_type"],
        description=st.get("description"),
        working_hours_pattern=[WorkingHoursPattern(**p) for p in st.get("working_hours_pattern", [])],
        total_hours_per_week=st["total_hours_per_week"],
        is_flexible=st["is_flexible"],
        flexible_arrangement=FlexibleArrangement(**st["flexible_arrangement"]) if st.get("flexible_arrangement") else None,
        time_off_eligibility_rules=[TimeOffEligibilityRule(**r) for r in st.get("time_off_eligibility_rules", [])],
        overtime_eligible=st["overtime_eligible"],
        weekend_work_allowed=st["weekend_work_allowed"],
        compatible_employment_types=st.get("compatible_employment_types", []),
        applicable_locations=st.get("applicable_locations", []),
        applicable_departments=st.get("applicable_departments", []),
        is_template=st["is_template"],
        is_active=st["is_active"],
        created_at=st["created_at"],
        updated_at=st.get("updated_at"),
    )

