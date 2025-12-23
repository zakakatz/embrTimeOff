"""Service for setup wizard estimation calculations."""

import logging
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from src.schemas.setup_wizard_estimation import (
    BottleneckAnalysis,
    ComplexityAssessment,
    ComplexityLevelEnum,
    ConfigurationState,
    CriticalPathItem,
    EstimationRequest,
    EstimationResponse,
    MilestoneCheckpoint,
    OptimizationRecommendation,
    OrganizationalParameters,
    OrganizationSizeEnum,
    PhaseEstimate,
    ResourceRequirement,
    ResourceTypeEnum,
    SetupPhaseEnum,
    SetupScopeRequirements,
    TimelineAdjustment,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Phase Configuration
# =============================================================================

PHASE_DISPLAY_NAMES = {
    SetupPhaseEnum.ORGANIZATION_BASICS: "Organization Basics",
    SetupPhaseEnum.LOCATION_SETUP: "Location Setup",
    SetupPhaseEnum.DEPARTMENT_STRUCTURE: "Department Structure",
    SetupPhaseEnum.WORK_SCHEDULES: "Work Schedules",
    SetupPhaseEnum.TIME_OFF_POLICIES: "Time-Off Policies",
    SetupPhaseEnum.HOLIDAY_CALENDARS: "Holiday Calendars",
    SetupPhaseEnum.EMPLOYEE_IMPORT: "Employee Import",
    SetupPhaseEnum.APPROVAL_WORKFLOWS: "Approval Workflows",
    SetupPhaseEnum.INTEGRATION_SETUP: "Integration Setup",
    SetupPhaseEnum.TESTING_VALIDATION: "Testing & Validation",
}

# Base times in minutes for a small organization
BASE_PHASE_TIMES = {
    SetupPhaseEnum.ORGANIZATION_BASICS: 30,
    SetupPhaseEnum.LOCATION_SETUP: 45,
    SetupPhaseEnum.DEPARTMENT_STRUCTURE: 60,
    SetupPhaseEnum.WORK_SCHEDULES: 90,
    SetupPhaseEnum.TIME_OFF_POLICIES: 120,
    SetupPhaseEnum.HOLIDAY_CALENDARS: 45,
    SetupPhaseEnum.EMPLOYEE_IMPORT: 60,
    SetupPhaseEnum.APPROVAL_WORKFLOWS: 75,
    SetupPhaseEnum.INTEGRATION_SETUP: 120,
    SetupPhaseEnum.TESTING_VALIDATION: 90,
}

PHASE_DEPENDENCIES = {
    SetupPhaseEnum.ORGANIZATION_BASICS: [],
    SetupPhaseEnum.LOCATION_SETUP: [SetupPhaseEnum.ORGANIZATION_BASICS],
    SetupPhaseEnum.DEPARTMENT_STRUCTURE: [SetupPhaseEnum.ORGANIZATION_BASICS],
    SetupPhaseEnum.WORK_SCHEDULES: [SetupPhaseEnum.ORGANIZATION_BASICS],
    SetupPhaseEnum.TIME_OFF_POLICIES: [SetupPhaseEnum.WORK_SCHEDULES],
    SetupPhaseEnum.HOLIDAY_CALENDARS: [SetupPhaseEnum.LOCATION_SETUP],
    SetupPhaseEnum.EMPLOYEE_IMPORT: [
        SetupPhaseEnum.DEPARTMENT_STRUCTURE,
        SetupPhaseEnum.WORK_SCHEDULES,
    ],
    SetupPhaseEnum.APPROVAL_WORKFLOWS: [
        SetupPhaseEnum.DEPARTMENT_STRUCTURE,
        SetupPhaseEnum.TIME_OFF_POLICIES,
    ],
    SetupPhaseEnum.INTEGRATION_SETUP: [SetupPhaseEnum.ORGANIZATION_BASICS],
    SetupPhaseEnum.TESTING_VALIDATION: [
        SetupPhaseEnum.EMPLOYEE_IMPORT,
        SetupPhaseEnum.APPROVAL_WORKFLOWS,
    ],
}

PARALLEL_GROUPS = [
    [SetupPhaseEnum.LOCATION_SETUP, SetupPhaseEnum.DEPARTMENT_STRUCTURE, SetupPhaseEnum.WORK_SCHEDULES],
    [SetupPhaseEnum.TIME_OFF_POLICIES, SetupPhaseEnum.HOLIDAY_CALENDARS],
]

PHASE_TASKS = {
    SetupPhaseEnum.ORGANIZATION_BASICS: [
        "Enter organization details",
        "Configure company settings",
        "Set up fiscal year",
        "Configure time zones",
    ],
    SetupPhaseEnum.LOCATION_SETUP: [
        "Add office locations",
        "Configure location settings",
        "Set location time zones",
        "Assign location managers",
    ],
    SetupPhaseEnum.DEPARTMENT_STRUCTURE: [
        "Create department hierarchy",
        "Assign department heads",
        "Configure cost centers",
        "Set up reporting lines",
    ],
    SetupPhaseEnum.WORK_SCHEDULES: [
        "Define standard schedules",
        "Configure shift schedules",
        "Set up break times",
        "Assign schedules to locations",
    ],
    SetupPhaseEnum.TIME_OFF_POLICIES: [
        "Create policy types",
        "Configure accrual rules",
        "Set up carryover limits",
        "Define eligibility rules",
    ],
    SetupPhaseEnum.HOLIDAY_CALENDARS: [
        "Add public holidays",
        "Create custom holidays",
        "Assign calendars to locations",
        "Configure floating holidays",
    ],
    SetupPhaseEnum.EMPLOYEE_IMPORT: [
        "Prepare import file",
        "Map data fields",
        "Validate data",
        "Execute import",
        "Verify imported data",
    ],
    SetupPhaseEnum.APPROVAL_WORKFLOWS: [
        "Define approval chains",
        "Configure escalation rules",
        "Set up delegation",
        "Test workflow routing",
    ],
    SetupPhaseEnum.INTEGRATION_SETUP: [
        "Configure SSO",
        "Set up HRIS integration",
        "Configure payroll sync",
        "Test data flows",
    ],
    SetupPhaseEnum.TESTING_VALIDATION: [
        "Test time-off requests",
        "Validate accruals",
        "Test approvals",
        "Verify reports",
        "User acceptance testing",
    ],
}


class SetupWizardEstimationService:
    """Service for estimating setup wizard completion time."""

    def calculate_estimation(
        self,
        request: EstimationRequest,
    ) -> EstimationResponse:
        """
        Calculate complete setup wizard estimation.
        
        Considers organizational size, complexity, and scope requirements.
        """
        params = request.organizational_params
        current_state = request.current_state or ConfigurationState()
        scope = request.scope or SetupScopeRequirements()

        # Calculate phase estimates
        phase_estimates = self._calculate_phase_estimates(
            params, current_state, scope
        )

        # Calculate total time
        total_minutes = sum(
            p.estimated_minutes for p in phase_estimates if not p.is_complete
        )

        # Identify bottlenecks
        bottlenecks = self._identify_bottlenecks(params, phase_estimates)

        # Calculate critical path
        critical_path = self._calculate_critical_path(phase_estimates)
        critical_path_duration = sum(c.duration_minutes for c in critical_path)

        # Resource requirements
        resources = self._calculate_resource_requirements(params, phase_estimates)
        total_personnel_hours = sum(r.estimated_hours for r in resources)

        # Milestones
        milestones = self._generate_milestones(phase_estimates)

        # Complexity assessment
        complexity = self._assess_complexity(params)

        # Optimization recommendations
        optimizations = self._generate_optimization_recommendations(
            params, phase_estimates, bottlenecks
        )
        potential_savings = sum(o.time_savings_minutes for o in optimizations)

        # Timeline scenarios
        timelines = self._calculate_timeline_scenarios(
            total_minutes, scope, request.target_completion_date
        )

        # Parallel execution plan
        parallel_plan = self._create_parallel_execution_plan(phase_estimates)

        # Execution notes
        execution_notes = self._generate_execution_notes(params, complexity)

        # Calculate working/calendar days
        hours_per_day = scope.available_hours_per_day
        team_size = scope.team_size
        working_days = (total_minutes / 60) / (hours_per_day * team_size)
        calendar_days = working_days * 1.4  # Account for weekends

        return EstimationResponse(
            total_estimated_minutes=total_minutes,
            total_estimated_hours=round(total_minutes / 60, 1),
            estimated_working_days=round(working_days, 1),
            estimated_calendar_days=round(calendar_days, 1),
            phase_estimates=phase_estimates,
            bottlenecks=bottlenecks,
            critical_path=critical_path,
            critical_path_duration_minutes=critical_path_duration,
            resource_requirements=resources,
            total_personnel_hours=round(total_personnel_hours, 1),
            milestones=milestones,
            complexity_assessment=complexity,
            optimization_recommendations=optimizations,
            potential_time_savings_minutes=potential_savings,
            timeline_scenarios=timelines,
            recommended_scenario="standard" if not request.target_completion_date else "aggressive",
            recommended_start_phase=SetupPhaseEnum.ORGANIZATION_BASICS,
            parallel_execution_plan=parallel_plan,
            execution_notes=execution_notes,
            estimated_at=datetime.utcnow(),
            confidence_level="high" if complexity.overall_score < 50 else "medium",
        )

    def _calculate_phase_estimates(
        self,
        params: OrganizationalParameters,
        current_state: ConfigurationState,
        scope: SetupScopeRequirements,
    ) -> List[PhaseEstimate]:
        """Calculate time estimates for each phase."""
        estimates = []
        
        # Size multiplier
        size_multipliers = {
            OrganizationSizeEnum.SMALL: 1.0,
            OrganizationSizeEnum.MEDIUM: 1.5,
            OrganizationSizeEnum.LARGE: 2.5,
            OrganizationSizeEnum.ENTERPRISE: 4.0,
        }
        size_mult = size_multipliers.get(params.organization_size, 1.5)
        
        # Experience multiplier
        exp_multipliers = {"novice": 1.5, "intermediate": 1.0, "expert": 0.7}
        exp_mult = exp_multipliers.get(scope.experience_level, 1.0)

        for phase in scope.phases_to_complete:
            base_time = BASE_PHASE_TIMES.get(phase, 60)
            
            # Apply multipliers
            adjusted_time = base_time * size_mult * exp_mult
            
            # Phase-specific adjustments
            adjusted_time = self._apply_phase_adjustments(
                phase, adjusted_time, params
            )
            
            # Check completion status
            is_complete = self._check_phase_complete(phase, current_state)
            progress = self._get_phase_progress(phase, current_state)
            
            if not is_complete and progress > 0:
                adjusted_time *= (1 - progress / 100)
            
            # Complexity for this phase
            complexity = self._get_phase_complexity(phase, params)
            
            # Task breakdown
            tasks = PHASE_TASKS.get(phase, [])
            task_times = self._calculate_task_times(tasks, adjusted_time)
            
            # Dependencies
            deps = PHASE_DEPENDENCIES.get(phase, [])
            
            # Can run parallel
            can_parallel = any(phase in group for group in PARALLEL_GROUPS)
            
            # Tips
            tips = self._get_phase_tips(phase, params)
            
            estimates.append(PhaseEstimate(
                phase=phase,
                phase_display=PHASE_DISPLAY_NAMES.get(phase, phase.value),
                estimated_minutes=round(adjusted_time),
                estimated_hours=round(adjusted_time / 60, 1),
                complexity=complexity,
                dependencies=deps,
                can_run_parallel=can_parallel,
                tasks=tasks,
                task_time_breakdown=task_times,
                is_complete=is_complete,
                progress_percentage=progress,
                tips=tips,
            ))
        
        return estimates

    def _apply_phase_adjustments(
        self,
        phase: SetupPhaseEnum,
        base_time: float,
        params: OrganizationalParameters,
    ) -> float:
        """Apply phase-specific time adjustments."""
        time = base_time
        
        if phase == SetupPhaseEnum.LOCATION_SETUP:
            time += (params.location_count - 1) * 15  # 15 min per additional location
            if params.has_multiple_countries:
                time *= 1.5
        
        elif phase == SetupPhaseEnum.DEPARTMENT_STRUCTURE:
            time += (params.department_count - 1) * 10  # 10 min per additional dept
        
        elif phase == SetupPhaseEnum.WORK_SCHEDULES:
            time += (params.work_schedule_count - 1) * 20
            if params.has_shift_workers:
                time *= 1.5
        
        elif phase == SetupPhaseEnum.TIME_OFF_POLICIES:
            time += (params.policy_count - 1) * 25
            if params.has_union_requirements:
                time *= 1.4
        
        elif phase == SetupPhaseEnum.HOLIDAY_CALENDARS:
            if params.has_multiple_countries:
                time *= 2.0  # Different holidays per country
        
        elif phase == SetupPhaseEnum.EMPLOYEE_IMPORT:
            # Time scales with employee count
            emp_factor = math.log2(max(params.employee_count, 2)) / 5
            time *= (1 + emp_factor)
            if params.has_existing_data and params.data_cleanup_needed:
                time *= 1.5
        
        elif phase == SetupPhaseEnum.APPROVAL_WORKFLOWS:
            if params.has_complex_approval_chains:
                time *= 1.8
        
        elif phase == SetupPhaseEnum.INTEGRATION_SETUP:
            integration_count = int(params.requires_hris_integration) + int(params.requires_payroll_integration)
            time += integration_count * 60  # 60 min per integration
        
        return time

    def _check_phase_complete(
        self,
        phase: SetupPhaseEnum,
        state: ConfigurationState,
    ) -> bool:
        """Check if a phase is complete based on current state."""
        checks = {
            SetupPhaseEnum.LOCATION_SETUP: state.locations_configured > 0,
            SetupPhaseEnum.DEPARTMENT_STRUCTURE: state.departments_configured > 0,
            SetupPhaseEnum.WORK_SCHEDULES: state.schedules_configured > 0,
            SetupPhaseEnum.TIME_OFF_POLICIES: state.policies_configured > 0,
            SetupPhaseEnum.EMPLOYEE_IMPORT: state.employees_imported > 0,
            SetupPhaseEnum.APPROVAL_WORKFLOWS: state.workflows_configured > 0,
            SetupPhaseEnum.INTEGRATION_SETUP: state.integrations_connected > 0,
        }
        return checks.get(phase, False)

    def _get_phase_progress(
        self,
        phase: SetupPhaseEnum,
        state: ConfigurationState,
    ) -> float:
        """Get progress percentage for a phase."""
        if phase == SetupPhaseEnum.ORGANIZATION_BASICS:
            return min(state.completion_percentage * 10, 100)
        return state.completion_percentage if self._check_phase_complete(phase, state) else 0

    def _get_phase_complexity(
        self,
        phase: SetupPhaseEnum,
        params: OrganizationalParameters,
    ) -> ComplexityLevelEnum:
        """Determine complexity level for a phase."""
        complex_phases = {
            SetupPhaseEnum.TIME_OFF_POLICIES,
            SetupPhaseEnum.APPROVAL_WORKFLOWS,
            SetupPhaseEnum.INTEGRATION_SETUP,
        }
        
        if phase in complex_phases:
            if params.organization_size == OrganizationSizeEnum.ENTERPRISE:
                return ComplexityLevelEnum.HIGHLY_COMPLEX
            return ComplexityLevelEnum.COMPLEX
        
        if params.organization_size in [OrganizationSizeEnum.LARGE, OrganizationSizeEnum.ENTERPRISE]:
            return ComplexityLevelEnum.MODERATE
        
        return ComplexityLevelEnum.SIMPLE

    def _calculate_task_times(
        self,
        tasks: List[str],
        total_time: float,
    ) -> Dict[str, int]:
        """Distribute time across tasks."""
        if not tasks:
            return {}
        time_per_task = total_time / len(tasks)
        return {task: round(time_per_task) for task in tasks}

    def _get_phase_tips(
        self,
        phase: SetupPhaseEnum,
        params: OrganizationalParameters,
    ) -> List[str]:
        """Get tips for a phase."""
        tips = []
        
        if phase == SetupPhaseEnum.EMPLOYEE_IMPORT:
            tips.append("Prepare your data file before starting")
            if params.has_existing_data:
                tips.append("Review data for duplicates and inconsistencies")
        
        elif phase == SetupPhaseEnum.TIME_OFF_POLICIES:
            tips.append("Document all policy requirements before configuration")
            if params.has_union_requirements:
                tips.append("Verify union agreement terms are correctly reflected")
        
        elif phase == SetupPhaseEnum.INTEGRATION_SETUP:
            tips.append("Have API credentials ready")
            tips.append("Test in sandbox environment first")
        
        return tips

    def _identify_bottlenecks(
        self,
        params: OrganizationalParameters,
        estimates: List[PhaseEstimate],
    ) -> List[BottleneckAnalysis]:
        """Identify potential bottlenecks."""
        bottlenecks = []
        
        # Data import bottleneck
        if params.has_existing_data and params.employee_count > 100:
            bottlenecks.append(BottleneckAnalysis(
                bottleneck_id="BN001",
                phase=SetupPhaseEnum.EMPLOYEE_IMPORT,
                description="Large employee data import may take significant time",
                impact_minutes=max(30, params.employee_count // 10),
                severity="high" if params.employee_count > 500 else "medium",
                mitigation="Break import into smaller batches",
                can_parallelize=True,
            ))
        
        # Integration bottleneck
        if params.requires_hris_integration or params.requires_payroll_integration:
            bottlenecks.append(BottleneckAnalysis(
                bottleneck_id="BN002",
                phase=SetupPhaseEnum.INTEGRATION_SETUP,
                description="External system integration may require coordination",
                impact_minutes=120,
                severity="high",
                mitigation="Start integration planning early",
                can_parallelize=False,
            ))
        
        # Policy complexity bottleneck
        if params.has_union_requirements or params.policy_count > 10:
            bottlenecks.append(BottleneckAnalysis(
                bottleneck_id="BN003",
                phase=SetupPhaseEnum.TIME_OFF_POLICIES,
                description="Complex policy configuration requires careful review",
                impact_minutes=60,
                severity="medium",
                mitigation="Document policies before configuration",
                can_parallelize=False,
            ))
        
        return bottlenecks

    def _calculate_critical_path(
        self,
        estimates: List[PhaseEstimate],
    ) -> List[CriticalPathItem]:
        """Calculate the critical path through setup phases."""
        critical_path = []
        cumulative_time = 0
        
        # Simple critical path: follow dependency chain
        ordered_phases = [
            SetupPhaseEnum.ORGANIZATION_BASICS,
            SetupPhaseEnum.DEPARTMENT_STRUCTURE,
            SetupPhaseEnum.WORK_SCHEDULES,
            SetupPhaseEnum.TIME_OFF_POLICIES,
            SetupPhaseEnum.EMPLOYEE_IMPORT,
            SetupPhaseEnum.APPROVAL_WORKFLOWS,
            SetupPhaseEnum.TESTING_VALIDATION,
        ]
        
        phase_map = {e.phase: e for e in estimates}
        
        for phase in ordered_phases:
            if phase in phase_map and not phase_map[phase].is_complete:
                estimate = phase_map[phase]
                critical_path.append(CriticalPathItem(
                    phase=phase,
                    phase_display=PHASE_DISPLAY_NAMES.get(phase, phase.value),
                    duration_minutes=estimate.estimated_minutes,
                    start_offset_minutes=cumulative_time,
                    end_offset_minutes=cumulative_time + estimate.estimated_minutes,
                    is_blocking=True,
                ))
                cumulative_time += estimate.estimated_minutes
        
        return critical_path

    def _calculate_resource_requirements(
        self,
        params: OrganizationalParameters,
        estimates: List[PhaseEstimate],
    ) -> List[ResourceRequirement]:
        """Calculate resource requirements."""
        resources = []
        
        # HR Admin (always needed)
        hr_phases = [
            SetupPhaseEnum.TIME_OFF_POLICIES,
            SetupPhaseEnum.EMPLOYEE_IMPORT,
            SetupPhaseEnum.APPROVAL_WORKFLOWS,
        ]
        hr_hours = sum(
            e.estimated_hours for e in estimates if e.phase in hr_phases
        )
        resources.append(ResourceRequirement(
            resource_type=ResourceTypeEnum.HR_ADMIN,
            resource_description="HR administrator for policy and employee configuration",
            required_for_phases=hr_phases,
            estimated_hours=hr_hours,
            is_critical=True,
            availability_note="Should be available throughout setup",
        ))
        
        # IT Admin (if integrations needed)
        if params.requires_hris_integration or params.requires_payroll_integration:
            resources.append(ResourceRequirement(
                resource_type=ResourceTypeEnum.IT_ADMIN,
                resource_description="IT administrator for integration setup",
                required_for_phases=[SetupPhaseEnum.INTEGRATION_SETUP],
                estimated_hours=4.0,
                is_critical=True,
                availability_note="Needed during integration phase",
            ))
        
        # Department heads (for structure)
        if params.department_count > 5:
            resources.append(ResourceRequirement(
                resource_type=ResourceTypeEnum.DEPARTMENT_HEAD,
                resource_description="Department heads for structure validation",
                required_for_phases=[SetupPhaseEnum.DEPARTMENT_STRUCTURE],
                estimated_hours=2.0,
                is_critical=False,
                availability_note="Brief consultation needed",
            ))
        
        return resources

    def _generate_milestones(
        self,
        estimates: List[PhaseEstimate],
    ) -> List[MilestoneCheckpoint]:
        """Generate milestone checkpoints."""
        milestones = []
        cumulative = 0
        
        # Milestone 1: Foundation
        foundation_phases = [
            SetupPhaseEnum.ORGANIZATION_BASICS,
            SetupPhaseEnum.LOCATION_SETUP,
            SetupPhaseEnum.DEPARTMENT_STRUCTURE,
        ]
        foundation_time = sum(
            e.estimated_minutes for e in estimates if e.phase in foundation_phases
        )
        cumulative += foundation_time
        milestones.append(MilestoneCheckpoint(
            milestone_id="MS001",
            name="Foundation Complete",
            description="Organization structure is configured",
            phases_included=foundation_phases,
            estimated_completion_minutes=cumulative,
            completion_criteria=[
                "All locations configured",
                "Department hierarchy established",
                "Managers assigned",
            ],
            is_checkpoint=True,
        ))
        
        # Milestone 2: Policies Ready
        policy_phases = [
            SetupPhaseEnum.WORK_SCHEDULES,
            SetupPhaseEnum.TIME_OFF_POLICIES,
            SetupPhaseEnum.HOLIDAY_CALENDARS,
        ]
        policy_time = sum(
            e.estimated_minutes for e in estimates if e.phase in policy_phases
        )
        cumulative += policy_time
        milestones.append(MilestoneCheckpoint(
            milestone_id="MS002",
            name="Policies Configured",
            description="Time-off policies and schedules ready",
            phases_included=policy_phases,
            estimated_completion_minutes=cumulative,
            completion_criteria=[
                "All schedules defined",
                "Policies configured",
                "Holiday calendars set up",
            ],
            is_checkpoint=True,
        ))
        
        # Milestone 3: Go-Live Ready
        golive_phases = [
            SetupPhaseEnum.EMPLOYEE_IMPORT,
            SetupPhaseEnum.APPROVAL_WORKFLOWS,
            SetupPhaseEnum.TESTING_VALIDATION,
        ]
        golive_time = sum(
            e.estimated_minutes for e in estimates if e.phase in golive_phases
        )
        cumulative += golive_time
        milestones.append(MilestoneCheckpoint(
            milestone_id="MS003",
            name="Go-Live Ready",
            description="System ready for production use",
            phases_included=golive_phases,
            estimated_completion_minutes=cumulative,
            completion_criteria=[
                "All employees imported",
                "Approval workflows tested",
                "UAT complete",
            ],
            is_checkpoint=True,
        ))
        
        return milestones

    def _assess_complexity(
        self,
        params: OrganizationalParameters,
    ) -> ComplexityAssessment:
        """Assess overall setup complexity."""
        # Organizational complexity (0-100)
        org_score = 0
        org_score += min(params.employee_count / 10, 25)  # Max 25 for 250+ employees
        org_score += min(params.location_count * 5, 15)  # Max 15 for 3+ locations
        org_score += min(params.department_count * 2, 15)  # Max 15 for 7+ departments
        
        # Technical complexity
        tech_score = 0
        if params.has_shift_workers:
            tech_score += 15
        if params.has_complex_approval_chains:
            tech_score += 20
        if params.requires_hris_integration:
            tech_score += 15
        if params.requires_payroll_integration:
            tech_score += 15
        
        # Data complexity
        data_score = 0
        if params.has_existing_data:
            data_score += 15
        if params.data_cleanup_needed:
            data_score += 20
        
        # Integration complexity
        int_score = 0
        if params.has_multiple_countries:
            int_score += 20
        if params.has_union_requirements:
            int_score += 15
        
        overall = (org_score + tech_score + data_score + int_score) / 4
        
        # Determine level
        if overall >= 70:
            level = ComplexityLevelEnum.HIGHLY_COMPLEX
        elif overall >= 50:
            level = ComplexityLevelEnum.COMPLEX
        elif overall >= 30:
            level = ComplexityLevelEnum.MODERATE
        else:
            level = ComplexityLevelEnum.SIMPLE
        
        # Factors
        factors = []
        if params.employee_count > 200:
            factors.append(f"Large workforce ({params.employee_count} employees)")
        if params.has_multiple_countries:
            factors.append("Multi-country operation")
        if params.has_shift_workers:
            factors.append("Shift work scheduling")
        if params.has_union_requirements:
            factors.append("Union/CBA compliance")
        if params.requires_hris_integration:
            factors.append("HRIS integration required")
        
        # Simplification opportunities
        simplifications = []
        if params.policy_count > 5:
            simplifications.append("Consider consolidating similar policies")
        if not params.has_existing_data:
            simplifications.append("Fresh start allows clean configuration")
        
        # Benchmarks
        size_days = {
            OrganizationSizeEnum.SMALL: 2,
            OrganizationSizeEnum.MEDIUM: 5,
            OrganizationSizeEnum.LARGE: 12,
            OrganizationSizeEnum.ENTERPRISE: 25,
        }
        
        return ComplexityAssessment(
            overall_score=round(overall, 1),
            complexity_level=level,
            organizational_complexity=round(org_score, 1),
            technical_complexity=round(tech_score, 1),
            data_complexity=round(data_score, 1),
            integration_complexity=round(int_score, 1),
            percentile_rank=round(100 - overall, 1),
            benchmark_comparison=f"{'Above' if overall > 50 else 'Below'} average complexity",
            similar_org_avg_days=size_days.get(params.organization_size, 5),
            complexity_factors=factors,
            simplification_opportunities=simplifications,
        )

    def _generate_optimization_recommendations(
        self,
        params: OrganizationalParameters,
        estimates: List[PhaseEstimate],
        bottlenecks: List[BottleneckAnalysis],
    ) -> List[OptimizationRecommendation]:
        """Generate optimization recommendations."""
        recommendations = []
        
        # Parallel execution
        parallel_phases = [e for e in estimates if e.can_run_parallel]
        if len(parallel_phases) > 1:
            savings = sum(e.estimated_minutes for e in parallel_phases[1:]) // 2
            recommendations.append(OptimizationRecommendation(
                recommendation_id="OPT001",
                title="Enable Parallel Phase Execution",
                description="Execute independent phases simultaneously with multiple team members",
                time_savings_minutes=savings,
                implementation_effort="low",
                priority="high",
                affected_phases=[e.phase for e in parallel_phases],
                prerequisites=["Multiple team members available"],
            ))
        
        # Pre-import data preparation
        if params.has_existing_data:
            recommendations.append(OptimizationRecommendation(
                recommendation_id="OPT002",
                title="Pre-Prepare Import Data",
                description="Clean and format employee data before starting setup",
                time_savings_minutes=45,
                implementation_effort="medium",
                priority="high",
                affected_phases=[SetupPhaseEnum.EMPLOYEE_IMPORT],
                prerequisites=["Access to existing data"],
            ))
        
        # Template usage
        recommendations.append(OptimizationRecommendation(
            recommendation_id="OPT003",
            title="Use Pre-Built Templates",
            description="Leverage industry-standard policy and schedule templates",
            time_savings_minutes=30,
            implementation_effort="low",
            priority="medium",
            affected_phases=[
                SetupPhaseEnum.WORK_SCHEDULES,
                SetupPhaseEnum.TIME_OFF_POLICIES,
            ],
            prerequisites=[],
        ))
        
        return recommendations

    def _calculate_timeline_scenarios(
        self,
        total_minutes: int,
        scope: SetupScopeRequirements,
        target_date: Optional[datetime],
    ) -> List[TimelineAdjustment]:
        """Calculate different timeline scenarios."""
        scenarios = []
        now = datetime.utcnow()
        
        # Standard scenario
        standard_days = (total_minutes / 60) / scope.available_hours_per_day / scope.team_size
        scenarios.append(TimelineAdjustment(
            scenario="standard",
            total_days=round(standard_days * 1.4, 1),  # Calendar days
            working_days=round(standard_days, 1),
            hours_per_day=scope.available_hours_per_day,
            start_date=now,
            end_date=now + timedelta(days=int(standard_days * 1.4)),
            meets_target=None,
            adjustment_notes="Standard pace with normal work hours",
        ))
        
        # Aggressive scenario
        aggressive_days = standard_days * 0.7
        scenarios.append(TimelineAdjustment(
            scenario="aggressive",
            total_days=round(aggressive_days * 1.4, 1),
            working_days=round(aggressive_days, 1),
            hours_per_day=min(scope.available_hours_per_day * 1.5, 8),
            start_date=now,
            end_date=now + timedelta(days=int(aggressive_days * 1.4)),
            meets_target=None,
            adjustment_notes="Accelerated pace with extended hours",
        ))
        
        # Relaxed scenario
        relaxed_days = standard_days * 1.3
        scenarios.append(TimelineAdjustment(
            scenario="relaxed",
            total_days=round(relaxed_days * 1.4, 1),
            working_days=round(relaxed_days, 1),
            hours_per_day=max(scope.available_hours_per_day * 0.75, 2),
            start_date=now,
            end_date=now + timedelta(days=int(relaxed_days * 1.4)),
            meets_target=None,
            adjustment_notes="Comfortable pace with buffer time",
        ))
        
        # Check target date
        if target_date:
            for scenario in scenarios:
                if scenario.end_date:
                    scenario.meets_target = scenario.end_date <= target_date
        
        return scenarios

    def _create_parallel_execution_plan(
        self,
        estimates: List[PhaseEstimate],
    ) -> List[List[SetupPhaseEnum]]:
        """Create groups of phases that can run in parallel."""
        plan = []
        
        # First: Organization basics (must be first)
        plan.append([SetupPhaseEnum.ORGANIZATION_BASICS])
        
        # Second: Can run together
        group2 = [
            e.phase for e in estimates
            if e.phase in [
                SetupPhaseEnum.LOCATION_SETUP,
                SetupPhaseEnum.DEPARTMENT_STRUCTURE,
                SetupPhaseEnum.WORK_SCHEDULES,
                SetupPhaseEnum.INTEGRATION_SETUP,
            ]
            and not e.is_complete
        ]
        if group2:
            plan.append(group2)
        
        # Third: After structure
        group3 = [
            e.phase for e in estimates
            if e.phase in [
                SetupPhaseEnum.TIME_OFF_POLICIES,
                SetupPhaseEnum.HOLIDAY_CALENDARS,
            ]
            and not e.is_complete
        ]
        if group3:
            plan.append(group3)
        
        # Fourth: After policies
        group4 = [
            e.phase for e in estimates
            if e.phase in [
                SetupPhaseEnum.EMPLOYEE_IMPORT,
                SetupPhaseEnum.APPROVAL_WORKFLOWS,
            ]
            and not e.is_complete
        ]
        if group4:
            plan.append(group4)
        
        # Finally: Testing
        plan.append([SetupPhaseEnum.TESTING_VALIDATION])
        
        return plan

    def _generate_execution_notes(
        self,
        params: OrganizationalParameters,
        complexity: ComplexityAssessment,
    ) -> List[str]:
        """Generate execution recommendations."""
        notes = []
        
        notes.append(f"Complexity level: {complexity.complexity_level.value}")
        notes.append(
            f"Similar organizations typically complete setup in "
            f"{complexity.similar_org_avg_days} working days"
        )
        
        if params.has_existing_data:
            notes.append("Prepare and validate import data before starting setup")
        
        if params.requires_hris_integration:
            notes.append("Coordinate with HRIS team early for integration requirements")
        
        if complexity.overall_score > 60:
            notes.append("Consider engaging a consultant for complex configuration")
        
        notes.append("Schedule validation checkpoints at each milestone")
        
        return notes

