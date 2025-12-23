"""API endpoints for setup wizard estimation."""

import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, status

from src.schemas.setup_wizard_estimation import (
    EstimationRequest,
    EstimationResponse,
)
from src.services.setup_wizard_estimation_service import SetupWizardEstimationService

logger = logging.getLogger(__name__)


# =============================================================================
# Router Setup
# =============================================================================

setup_wizard_estimation_router = APIRouter(
    prefix="/api/setup-wizard",
    tags=["Setup Wizard Estimation"],
)


# =============================================================================
# Dependencies
# =============================================================================

def get_estimation_service() -> SetupWizardEstimationService:
    """Get estimation service instance."""
    return SetupWizardEstimationService()


# =============================================================================
# Endpoints
# =============================================================================

@setup_wizard_estimation_router.post(
    "/configuration-estimation",
    response_model=EstimationResponse,
    summary="Estimate setup wizard completion time",
    description="""
    Calculate estimated completion time for the setup wizard based on organizational
    parameters, current configuration state, and scope requirements.
    
    **Estimation Includes:**
    - Phase-by-phase time breakdown with tasks
    - Bottleneck identification and mitigation strategies
    - Critical path analysis with dependencies
    - Resource requirements (personnel, time)
    - Milestone checkpoints for progress tracking
    - Complexity assessment with benchmarks
    - Optimization recommendations for faster completion
    - Multiple timeline scenarios (standard, aggressive, relaxed)
    - Parallel execution plan for concurrent tasks
    
    **Factors Considered:**
    - Organization size and employee count
    - Number of locations, departments, and policies
    - Configuration complexity (shifts, unions, approvals)
    - Integration requirements (HRIS, payroll)
    - Current configuration state (partial completion)
    - Team size and experience level
    - Available hours per day
    
    **Response Provides:**
    - Total estimated time in minutes, hours, and days
    - Detailed breakdown by setup phase
    - Identified bottlenecks with severity levels
    - Critical path through the setup process
    - Required resources by type and phase
    - Milestone checkpoints with completion criteria
    - Complexity score with similar organization benchmarks
    - Actionable optimization recommendations
    - Timeline scenarios with projected end dates
    - Execution notes and best practices
    """,
    responses={
        200: {
            "description": "Estimation calculated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "total_estimated_minutes": 480,
                        "total_estimated_hours": 8.0,
                        "estimated_working_days": 2.0,
                        "estimated_calendar_days": 2.8,
                        "phase_estimates": [],
                        "complexity_assessment": {
                            "overall_score": 35.0,
                            "complexity_level": "moderate",
                        },
                        "recommended_scenario": "standard",
                    }
                }
            },
        },
        400: {
            "description": "Invalid request parameters",
            "content": {
                "application/json": {
                    "examples": {
                        "invalid_employee_count": {
                            "summary": "Invalid employee count",
                            "value": {
                                "detail": "employee_count must be at least 1",
                            }
                        },
                        "invalid_hours": {
                            "summary": "Invalid hours per day",
                            "value": {
                                "detail": "available_hours_per_day must be between 1 and 8",
                            }
                        },
                    }
                }
            },
        },
        422: {
            "description": "Validation error",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["body", "organizational_params", "employee_count"],
                                "msg": "field required",
                                "type": "value_error.missing",
                            }
                        ]
                    }
                }
            },
        },
    },
)
async def estimate_configuration(
    request: EstimationRequest,
) -> EstimationResponse:
    """
    Calculate setup wizard completion time estimation.
    
    Analyzes organizational parameters, current configuration state, and scope
    requirements to provide detailed time estimates, bottleneck analysis,
    resource requirements, and optimization recommendations.
    
    **Organizational Parameters (Required):**
    - `employee_count`: Total number of employees
    - `organization_size`: Size category (small/medium/large/enterprise)
    - `location_count`: Number of office locations
    - `department_count`: Number of departments
    - Various complexity flags (shift workers, unions, integrations)
    
    **Current State (Optional):**
    - Already configured locations, departments, schedules, etc.
    - Overall completion percentage
    
    **Scope Requirements (Optional):**
    - Phases to include
    - Available hours per day
    - Team size
    - Experience level
    - Target completion date
    
    **Returns:**
    Comprehensive estimation including phase breakdowns, critical path,
    bottlenecks, resources, milestones, complexity assessment, optimizations,
    and timeline scenarios.
    """
    service = get_estimation_service()
    
    try:
        # Validate additional business rules
        params = request.organizational_params
        
        # Employee count vs organization size consistency check
        size_ranges = {
            "small": (1, 50),
            "medium": (50, 250),
            "large": (250, 1000),
            "enterprise": (1000, float("inf")),
        }
        
        size_range = size_ranges.get(params.organization_size.value, (1, float("inf")))
        if not (size_range[0] <= params.employee_count < size_range[1]):
            logger.warning(
                f"Organization size {params.organization_size.value} "
                f"doesn't match employee count {params.employee_count}"
            )
            # Continue anyway, but this affects estimation accuracy
        
        # Calculate estimation
        estimation = service.calculate_estimation(request)
        
        logger.info(
            f"Generated estimation for {params.employee_count} employees, "
            f"{params.organization_size.value} organization: "
            f"{estimation.total_estimated_hours:.1f} hours, "
            f"{estimation.estimated_working_days:.1f} working days"
        )
        
        return estimation
        
    except ValueError as e:
        logger.warning(f"Invalid estimation request: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.exception(f"Error calculating estimation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while calculating the estimation",
        )


@setup_wizard_estimation_router.get(
    "/phases",
    summary="List setup wizard phases",
    description="Get information about all available setup wizard phases.",
    responses={
        200: {"description": "Phase information retrieved"},
    },
)
async def list_setup_phases() -> dict:
    """
    List all setup wizard phases with descriptions and dependencies.
    """
    from src.services.setup_wizard_estimation_service import (
        PHASE_DISPLAY_NAMES,
        PHASE_DEPENDENCIES,
        BASE_PHASE_TIMES,
        PHASE_TASKS,
    )
    from src.schemas.setup_wizard_estimation import SetupPhaseEnum
    
    phases = []
    for phase in SetupPhaseEnum:
        phases.append({
            "phase": phase.value,
            "display_name": PHASE_DISPLAY_NAMES.get(phase, phase.value),
            "base_time_minutes": BASE_PHASE_TIMES.get(phase, 60),
            "dependencies": [d.value for d in PHASE_DEPENDENCIES.get(phase, [])],
            "tasks": PHASE_TASKS.get(phase, []),
        })
    
    return {
        "phases": phases,
        "total_phases": len(phases),
    }


@setup_wizard_estimation_router.get(
    "/complexity-factors",
    summary="List complexity factors",
    description="Get information about factors that affect setup complexity.",
    responses={
        200: {"description": "Complexity factors retrieved"},
    },
)
async def list_complexity_factors() -> dict:
    """
    List factors that affect setup wizard complexity.
    """
    return {
        "factors": [
            {
                "factor": "employee_count",
                "description": "Number of employees in the organization",
                "impact": "Affects import time and policy complexity",
                "thresholds": {
                    "low": "< 50 employees",
                    "medium": "50-250 employees",
                    "high": "250-1000 employees",
                    "very_high": "> 1000 employees",
                },
            },
            {
                "factor": "location_count",
                "description": "Number of office locations",
                "impact": "Each location requires separate configuration",
                "thresholds": {
                    "low": "1 location",
                    "medium": "2-5 locations",
                    "high": "> 5 locations",
                },
            },
            {
                "factor": "has_shift_workers",
                "description": "Organization has shift-based work schedules",
                "impact": "Increases schedule configuration complexity",
                "multiplier": 1.5,
            },
            {
                "factor": "has_multiple_countries",
                "description": "Operations span multiple countries",
                "impact": "Different holidays, labor laws, policies",
                "multiplier": 1.5,
            },
            {
                "factor": "has_union_requirements",
                "description": "Union or collective bargaining agreements",
                "impact": "Policy configuration must match CBA terms",
                "multiplier": 1.4,
            },
            {
                "factor": "requires_hris_integration",
                "description": "Integration with HRIS system required",
                "impact": "Additional setup and testing time",
                "additional_minutes": 60,
            },
            {
                "factor": "requires_payroll_integration",
                "description": "Integration with payroll system required",
                "impact": "Additional setup and testing time",
                "additional_minutes": 60,
            },
            {
                "factor": "has_complex_approval_chains",
                "description": "Multi-level approval workflows required",
                "impact": "Increases workflow configuration time",
                "multiplier": 1.8,
            },
            {
                "factor": "data_cleanup_needed",
                "description": "Existing data requires cleanup before import",
                "impact": "Increases data preparation time",
                "multiplier": 1.5,
            },
        ],
        "experience_multipliers": {
            "novice": 1.5,
            "intermediate": 1.0,
            "expert": 0.7,
        },
        "size_multipliers": {
            "small": 1.0,
            "medium": 1.5,
            "large": 2.5,
            "enterprise": 4.0,
        },
    }

