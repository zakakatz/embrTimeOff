"""Pydantic schemas for setup wizard estimation API."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class OrganizationSizeEnum(str, Enum):
    """Organization size categories."""
    SMALL = "small"  # < 50 employees
    MEDIUM = "medium"  # 50-250 employees
    LARGE = "large"  # 250-1000 employees
    ENTERPRISE = "enterprise"  # 1000+ employees


class SetupPhaseEnum(str, Enum):
    """Phases of the setup wizard."""
    ORGANIZATION_BASICS = "organization_basics"
    LOCATION_SETUP = "location_setup"
    DEPARTMENT_STRUCTURE = "department_structure"
    WORK_SCHEDULES = "work_schedules"
    TIME_OFF_POLICIES = "time_off_policies"
    HOLIDAY_CALENDARS = "holiday_calendars"
    EMPLOYEE_IMPORT = "employee_import"
    APPROVAL_WORKFLOWS = "approval_workflows"
    INTEGRATION_SETUP = "integration_setup"
    TESTING_VALIDATION = "testing_validation"


class ComplexityLevelEnum(str, Enum):
    """Complexity level categories."""
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    HIGHLY_COMPLEX = "highly_complex"


class ResourceTypeEnum(str, Enum):
    """Types of resources needed."""
    HR_ADMIN = "hr_admin"
    IT_ADMIN = "it_admin"
    DEPARTMENT_HEAD = "department_head"
    EXECUTIVE_SPONSOR = "executive_sponsor"
    EXTERNAL_CONSULTANT = "external_consultant"


# =============================================================================
# Request Models
# =============================================================================

class ConfigurationState(BaseModel):
    """Current state of configuration."""
    locations_configured: int = Field(default=0, ge=0, description="Locations already set up")
    departments_configured: int = Field(default=0, ge=0, description="Departments configured")
    schedules_configured: int = Field(default=0, ge=0, description="Work schedules created")
    policies_configured: int = Field(default=0, ge=0, description="Policies configured")
    employees_imported: int = Field(default=0, ge=0, description="Employees already imported")
    workflows_configured: int = Field(default=0, ge=0, description="Approval workflows set up")
    integrations_connected: int = Field(default=0, ge=0, description="Integrations connected")
    completion_percentage: float = Field(
        default=0,
        ge=0,
        le=100,
        description="Overall completion percentage",
    )


class OrganizationalParameters(BaseModel):
    """Organizational parameters for estimation."""
    organization_name: Optional[str] = Field(default=None, description="Organization name")
    organization_size: OrganizationSizeEnum = Field(
        default=OrganizationSizeEnum.MEDIUM,
        description="Organization size category",
    )
    employee_count: int = Field(..., ge=1, description="Total employee count")
    location_count: int = Field(default=1, ge=1, description="Number of locations")
    department_count: int = Field(default=1, ge=1, description="Number of departments")
    work_schedule_count: int = Field(default=1, ge=1, description="Number of work schedules")
    policy_count: int = Field(default=1, ge=1, description="Number of time-off policies")
    
    # Configuration complexity factors
    has_shift_workers: bool = Field(default=False, description="Has shift work schedules")
    has_multiple_countries: bool = Field(default=False, description="Multi-country operation")
    has_union_requirements: bool = Field(default=False, description="Union/CBA requirements")
    has_complex_approval_chains: bool = Field(default=False, description="Complex approval workflows")
    requires_hris_integration: bool = Field(default=False, description="Needs HRIS integration")
    requires_payroll_integration: bool = Field(default=False, description="Needs payroll integration")
    
    # Data migration
    has_existing_data: bool = Field(default=False, description="Has data to migrate")
    existing_data_format: Optional[str] = Field(
        default=None,
        description="Format of existing data (csv, excel, api)",
    )
    data_cleanup_needed: bool = Field(default=False, description="Data cleanup required")


class SetupScopeRequirements(BaseModel):
    """Scope requirements for setup."""
    phases_to_complete: List[SetupPhaseEnum] = Field(
        default_factory=lambda: list(SetupPhaseEnum),
        description="Phases to include in setup",
    )
    priority_phases: List[SetupPhaseEnum] = Field(
        default_factory=list,
        description="High-priority phases to complete first",
    )
    parallel_execution_enabled: bool = Field(
        default=True,
        description="Allow parallel task execution",
    )
    available_hours_per_day: float = Field(
        default=4.0,
        ge=1,
        le=8,
        description="Hours available for setup per day",
    )
    team_size: int = Field(default=1, ge=1, le=10, description="Setup team size")
    experience_level: str = Field(
        default="intermediate",
        description="Team experience: novice, intermediate, expert",
    )


class EstimationRequest(BaseModel):
    """Request for setup wizard estimation."""
    organizational_params: OrganizationalParameters = Field(
        ...,
        description="Organizational parameters",
    )
    current_state: Optional[ConfigurationState] = Field(
        default=None,
        description="Current configuration state",
    )
    scope: Optional[SetupScopeRequirements] = Field(
        default=None,
        description="Setup scope requirements",
    )
    target_completion_date: Optional[datetime] = Field(
        default=None,
        description="Target completion date for timeline adjustments",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "organizational_params": {
                    "organization_size": "medium",
                    "employee_count": 150,
                    "location_count": 3,
                    "department_count": 8,
                    "work_schedule_count": 4,
                    "policy_count": 5,
                    "has_shift_workers": True,
                    "requires_hris_integration": True,
                },
                "scope": {
                    "parallel_execution_enabled": True,
                    "available_hours_per_day": 4,
                    "team_size": 2,
                },
            }
        }


# =============================================================================
# Response Models
# =============================================================================

class PhaseEstimate(BaseModel):
    """Estimation for a single setup phase."""
    phase: SetupPhaseEnum = Field(..., description="Setup phase")
    phase_display: str = Field(..., description="Human-readable phase name")
    estimated_minutes: int = Field(..., ge=0, description="Estimated time in minutes")
    estimated_hours: float = Field(..., ge=0, description="Estimated time in hours")
    complexity: ComplexityLevelEnum = Field(..., description="Phase complexity")
    
    # Dependencies
    dependencies: List[SetupPhaseEnum] = Field(
        default_factory=list,
        description="Phases that must complete first",
    )
    can_run_parallel: bool = Field(
        default=False,
        description="Can run in parallel with other phases",
    )
    
    # Breakdown
    tasks: List[str] = Field(default_factory=list, description="Tasks within this phase")
    task_time_breakdown: Dict[str, int] = Field(
        default_factory=dict,
        description="Time breakdown by task (minutes)",
    )
    
    # Status
    is_complete: bool = Field(default=False, description="Phase already complete")
    progress_percentage: float = Field(default=0, description="Current progress")
    
    # Recommendations
    tips: List[str] = Field(default_factory=list, description="Tips for this phase")


class BottleneckAnalysis(BaseModel):
    """Analysis of potential bottlenecks."""
    bottleneck_id: str = Field(..., description="Unique bottleneck ID")
    phase: SetupPhaseEnum = Field(..., description="Affected phase")
    description: str = Field(..., description="Bottleneck description")
    impact_minutes: int = Field(..., description="Potential time impact")
    severity: str = Field(..., description="Severity: low, medium, high, critical")
    mitigation: str = Field(..., description="Mitigation recommendation")
    can_parallelize: bool = Field(default=False, description="Can be mitigated by parallelization")


class CriticalPathItem(BaseModel):
    """Item on the critical path."""
    phase: SetupPhaseEnum = Field(..., description="Phase")
    phase_display: str = Field(..., description="Phase name")
    duration_minutes: int = Field(..., description="Duration")
    start_offset_minutes: int = Field(..., description="Start time offset")
    end_offset_minutes: int = Field(..., description="End time offset")
    is_blocking: bool = Field(default=True, description="Blocks subsequent phases")


class ResourceRequirement(BaseModel):
    """Resource requirement for setup."""
    resource_type: ResourceTypeEnum = Field(..., description="Type of resource")
    resource_description: str = Field(..., description="Resource description")
    required_for_phases: List[SetupPhaseEnum] = Field(
        default_factory=list,
        description="Phases requiring this resource",
    )
    estimated_hours: float = Field(..., description="Hours needed")
    is_critical: bool = Field(default=False, description="Critical resource")
    availability_note: str = Field(default="", description="Availability considerations")


class MilestoneCheckpoint(BaseModel):
    """Milestone checkpoint for progress tracking."""
    milestone_id: str = Field(..., description="Unique milestone ID")
    name: str = Field(..., description="Milestone name")
    description: str = Field(..., description="Milestone description")
    phases_included: List[SetupPhaseEnum] = Field(
        default_factory=list,
        description="Phases in this milestone",
    )
    estimated_completion_minutes: int = Field(..., description="Cumulative time to reach")
    completion_criteria: List[str] = Field(
        default_factory=list,
        description="Criteria to verify completion",
    )
    is_checkpoint: bool = Field(default=True, description="Should pause for verification")


class ComplexityAssessment(BaseModel):
    """Complexity assessment with scoring."""
    overall_score: float = Field(..., ge=0, le=100, description="Overall complexity score")
    complexity_level: ComplexityLevelEnum = Field(..., description="Complexity category")
    
    # Score breakdown
    organizational_complexity: float = Field(..., description="Org complexity score")
    technical_complexity: float = Field(..., description="Technical complexity score")
    data_complexity: float = Field(..., description="Data migration complexity")
    integration_complexity: float = Field(..., description="Integration complexity")
    
    # Benchmarks
    percentile_rank: float = Field(..., description="Percentile vs similar orgs")
    benchmark_comparison: str = Field(..., description="Comparison to benchmarks")
    similar_org_avg_days: float = Field(..., description="Avg days for similar orgs")
    
    # Factors
    complexity_factors: List[str] = Field(
        default_factory=list,
        description="Factors contributing to complexity",
    )
    simplification_opportunities: List[str] = Field(
        default_factory=list,
        description="Opportunities to reduce complexity",
    )


class OptimizationRecommendation(BaseModel):
    """Recommendation for optimizing setup time."""
    recommendation_id: str = Field(..., description="Recommendation ID")
    title: str = Field(..., description="Recommendation title")
    description: str = Field(..., description="Detailed description")
    time_savings_minutes: int = Field(..., description="Potential time savings")
    implementation_effort: str = Field(..., description="Effort: low, medium, high")
    priority: str = Field(..., description="Priority: low, medium, high")
    affected_phases: List[SetupPhaseEnum] = Field(
        default_factory=list,
        description="Affected phases",
    )
    prerequisites: List[str] = Field(
        default_factory=list,
        description="Prerequisites to implement",
    )


class TimelineAdjustment(BaseModel):
    """Adjusted timeline based on parameters."""
    scenario: str = Field(..., description="Scenario name")
    total_days: float = Field(..., description="Total calendar days")
    working_days: float = Field(..., description="Working days only")
    hours_per_day: float = Field(..., description="Hours per day assumed")
    start_date: Optional[datetime] = Field(default=None, description="Projected start")
    end_date: Optional[datetime] = Field(default=None, description="Projected end")
    meets_target: Optional[bool] = Field(default=None, description="Meets target date")
    adjustment_notes: str = Field(default="", description="Notes about adjustments")


class EstimationResponse(BaseModel):
    """Complete estimation response."""
    # Summary
    total_estimated_minutes: int = Field(..., description="Total estimated minutes")
    total_estimated_hours: float = Field(..., description="Total estimated hours")
    estimated_working_days: float = Field(..., description="Estimated working days")
    estimated_calendar_days: float = Field(..., description="Estimated calendar days")
    
    # Phase breakdown
    phase_estimates: List[PhaseEstimate] = Field(
        default_factory=list,
        description="Estimates by phase",
    )
    
    # Bottlenecks and critical path
    bottlenecks: List[BottleneckAnalysis] = Field(
        default_factory=list,
        description="Identified bottlenecks",
    )
    critical_path: List[CriticalPathItem] = Field(
        default_factory=list,
        description="Critical path items",
    )
    critical_path_duration_minutes: int = Field(..., description="Critical path duration")
    
    # Resources
    resource_requirements: List[ResourceRequirement] = Field(
        default_factory=list,
        description="Required resources",
    )
    total_personnel_hours: float = Field(..., description="Total personnel hours needed")
    
    # Milestones
    milestones: List[MilestoneCheckpoint] = Field(
        default_factory=list,
        description="Milestone checkpoints",
    )
    
    # Complexity
    complexity_assessment: ComplexityAssessment = Field(
        ...,
        description="Complexity assessment",
    )
    
    # Optimizations
    optimization_recommendations: List[OptimizationRecommendation] = Field(
        default_factory=list,
        description="Optimization recommendations",
    )
    potential_time_savings_minutes: int = Field(
        default=0,
        description="Potential time savings if optimizations applied",
    )
    
    # Timeline scenarios
    timeline_scenarios: List[TimelineAdjustment] = Field(
        default_factory=list,
        description="Timeline scenarios",
    )
    recommended_scenario: str = Field(..., description="Recommended scenario")
    
    # Execution recommendations
    recommended_start_phase: SetupPhaseEnum = Field(
        ...,
        description="Recommended starting phase",
    )
    parallel_execution_plan: List[List[SetupPhaseEnum]] = Field(
        default_factory=list,
        description="Phases that can run in parallel (grouped)",
    )
    execution_notes: List[str] = Field(
        default_factory=list,
        description="Execution recommendations",
    )
    
    # Metadata
    estimated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Estimation timestamp",
    )
    estimation_version: str = Field(
        default="1.0",
        description="Estimation algorithm version",
    )
    confidence_level: str = Field(
        default="high",
        description="Estimation confidence: low, medium, high",
    )

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}

