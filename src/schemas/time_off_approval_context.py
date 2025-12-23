"""Pydantic models for time-off request approval context.

Provides data models for contextual information and decision support
during time-off request approval workflows. These models aggregate
team conflicts, coverage warnings, policy considerations, and other
relevant context to help approvers make informed decisions.
"""

from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# =============================================================================
# Enums
# =============================================================================

class ConflictType(str, Enum):
    """Type of scheduling conflict."""
    
    APPROVED_REQUEST = "approved_request"
    PENDING_REQUEST = "pending_request"
    SCHEDULED_ABSENCE = "scheduled_absence"


class ImpactLevel(str, Enum):
    """Impact level for conflicts and warnings."""
    
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class WarningLevel(str, Enum):
    """Warning severity level for coverage warnings."""
    
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class ApprovalDecision(str, Enum):
    """Decision type for approval actions."""
    
    APPROVE = "approve"
    DENY = "deny"


class ConditionType(str, Enum):
    """Type of condition applied to an approval."""
    
    PARTIAL_APPROVAL = "partial_approval"
    DATE_MODIFICATION = "date_modification"
    HOURS_REDUCTION = "hours_reduction"


# =============================================================================
# Supporting Models
# =============================================================================

class TeamConflict(BaseModel):
    """
    Identifies a scheduling conflict with another team member.
    
    Used to alert approvers when the requested time off overlaps
    with other team members' approved or pending requests.
    """
    
    conflicting_employee_id: UUID = Field(
        ...,
        description="UUID of the employee with a conflicting request",
    )
    conflicting_employee_name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Full name of the conflicting employee",
    )
    conflict_dates: List[date] = Field(
        default_factory=list,
        description="List of dates that overlap with the request",
    )
    conflict_type: ConflictType = Field(
        ...,
        description="Type of conflict (approved, pending, or scheduled absence)",
    )
    impact_level: ImpactLevel = Field(
        default=ImpactLevel.MEDIUM,
        description="Severity of the conflict impact on team operations",
    )
    
    @field_validator("conflict_type", mode="before")
    @classmethod
    def validate_conflict_type(cls, v: Any) -> ConflictType:
        """Ensure conflict_type is a valid enum value."""
        if isinstance(v, str):
            try:
                return ConflictType(v.lower())
            except ValueError:
                raise ValueError(
                    f"Invalid conflict_type: {v}. Must be one of: "
                    f"{[e.value for e in ConflictType]}"
                )
        return v
    
    @field_validator("impact_level", mode="before")
    @classmethod
    def validate_impact_level(cls, v: Any) -> ImpactLevel:
        """Ensure impact_level is a valid enum value."""
        if isinstance(v, str):
            try:
                return ImpactLevel(v.lower())
            except ValueError:
                raise ValueError(
                    f"Invalid impact_level: {v}. Must be one of: "
                    f"{[e.value for e in ImpactLevel]}"
                )
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "conflicting_employee_id": "550e8400-e29b-41d4-a716-446655440000",
                "conflicting_employee_name": "Jane Smith",
                "conflict_dates": ["2024-03-15", "2024-03-18"],
                "conflict_type": "approved_request",
                "impact_level": "medium",
            }
        }


class HolidayOverlap(BaseModel):
    """
    Information about holidays that overlap with the request.
    
    Helps approvers understand if the time-off request includes
    company holidays that may affect the actual days taken.
    """
    
    holiday_date: date = Field(
        ...,
        description="Date of the holiday",
    )
    holiday_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Name of the holiday",
    )
    is_company_holiday: bool = Field(
        default=True,
        description="Whether this is an official company holiday",
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "holiday_date": "2024-03-17",
                "holiday_name": "St. Patrick's Day",
                "is_company_holiday": False,
            }
        }


class CoverageWarning(BaseModel):
    """
    Staffing coverage warning for the requested time off.
    
    Assesses the impact on department staffing levels and
    identifies critical functions that may be affected.
    """
    
    department: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Department affected by the coverage issue",
    )
    affected_dates: List[date] = Field(
        default_factory=list,
        description="List of dates with coverage concerns",
    )
    coverage_percentage: Decimal = Field(
        ...,
        ge=Decimal("0"),
        le=Decimal("100"),
        description="Percentage of department coverage remaining (0-100)",
    )
    critical_functions: List[str] = Field(
        default_factory=list,
        description="Critical functions that may be impacted",
    )
    warning_level: WarningLevel = Field(
        default=WarningLevel.INFO,
        description="Severity of the coverage warning",
    )
    
    @field_validator("warning_level", mode="before")
    @classmethod
    def validate_warning_level(cls, v: Any) -> WarningLevel:
        """Ensure warning_level is a valid enum value."""
        if isinstance(v, str):
            try:
                return WarningLevel(v.lower())
            except ValueError:
                raise ValueError(
                    f"Invalid warning_level: {v}. Must be one of: "
                    f"{[e.value for e in WarningLevel]}"
                )
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "department": "Engineering",
                "affected_dates": ["2024-03-15", "2024-03-16"],
                "coverage_percentage": 45.5,
                "critical_functions": ["On-call support", "Release management"],
                "warning_level": "warning",
            }
        }


class PolicyConsideration(BaseModel):
    """
    Policy-related considerations for the approval decision.
    
    Highlights policy requirements, restrictions, or special
    conditions that apply to the request.
    """
    
    policy_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Name of the applicable policy",
    )
    consideration_type: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Type of consideration (e.g., 'advance_notice', 'blackout_period')",
    )
    description: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Detailed description of the policy consideration",
    )
    is_blocking: bool = Field(
        default=False,
        description="Whether this consideration blocks approval",
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "policy_name": "Vacation Policy",
                "consideration_type": "advance_notice",
                "description": "Request submitted with less than 2 weeks notice",
                "is_blocking": False,
            }
        }


class BalanceImpactSummary(BaseModel):
    """
    Summary of how the request impacts time-off balances.
    
    Provides current balance, the amount requested, and the
    resulting balance after approval.
    """
    
    current_balance: Decimal = Field(
        ...,
        description="Current time-off balance in hours",
    )
    requested_hours: Decimal = Field(
        ...,
        ge=Decimal("0"),
        description="Number of hours requested",
    )
    balance_after_approval: Decimal = Field(
        ...,
        description="Remaining balance after approval",
    )
    accrual_by_end_date: Decimal = Field(
        default=Decimal("0"),
        description="Estimated accrual by the end of the request period",
    )
    will_have_negative_balance: bool = Field(
        default=False,
        description="Whether approval would result in a negative balance",
    )
    policy_type: str = Field(
        default="",
        description="Type of time-off policy (e.g., 'vacation', 'sick')",
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "current_balance": 80.0,
                "requested_hours": 24.0,
                "balance_after_approval": 56.0,
                "accrual_by_end_date": 8.0,
                "will_have_negative_balance": False,
                "policy_type": "vacation",
            }
        }


# =============================================================================
# Approval Condition Model
# =============================================================================

class ApprovalCondition(BaseModel):
    """
    Condition attached to an approval decision.
    
    Supports conditional approvals where the request may be
    partially approved or modified before final approval.
    """
    
    condition_type: ConditionType = Field(
        ...,
        description="Type of condition (partial, date modification, hours reduction)",
    )
    condition_details: Dict[str, Any] = Field(
        default_factory=dict,
        description="JSON details of the condition (e.g., new dates, modified hours)",
    )
    condition_notes: str = Field(
        default="",
        max_length=500,
        description="Additional notes about the condition",
    )
    
    @field_validator("condition_type", mode="before")
    @classmethod
    def validate_condition_type(cls, v: Any) -> ConditionType:
        """Ensure condition_type is a valid enum value."""
        if isinstance(v, str):
            try:
                return ConditionType(v.lower())
            except ValueError:
                raise ValueError(
                    f"Invalid condition_type: {v}. Must be one of: "
                    f"{[e.value for e in ConditionType]}"
                )
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "condition_type": "date_modification",
                "condition_details": {
                    "original_start": "2024-03-15",
                    "original_end": "2024-03-22",
                    "modified_start": "2024-03-18",
                    "modified_end": "2024-03-22",
                },
                "condition_notes": "Start date moved to avoid project deadline",
            }
        }


# =============================================================================
# Main Context and Decision Models
# =============================================================================

class ApprovalContext(BaseModel):
    """
    Aggregated context for time-off request approval decisions.
    
    Combines all relevant information including team conflicts,
    holiday overlaps, coverage warnings, policy considerations,
    and balance impact to support informed approval decisions.
    """
    
    request_id: UUID = Field(
        ...,
        description="UUID of the time-off request",
    )
    team_conflicts: List[TeamConflict] = Field(
        default_factory=list,
        description="List of team member conflicts for the requested dates",
    )
    holiday_overlaps: List[HolidayOverlap] = Field(
        default_factory=list,
        description="List of holidays that overlap with the request",
    )
    coverage_warnings: List[CoverageWarning] = Field(
        default_factory=list,
        description="List of coverage warnings for affected departments",
    )
    policy_considerations: List[PolicyConsideration] = Field(
        default_factory=list,
        description="List of policy-related considerations",
    )
    balance_impact: Optional[BalanceImpactSummary] = Field(
        default=None,
        description="Summary of balance impact from approving this request",
    )
    
    @property
    def has_conflicts(self) -> bool:
        """Check if there are any team conflicts."""
        return len(self.team_conflicts) > 0
    
    @property
    def has_critical_warnings(self) -> bool:
        """Check if there are any critical coverage warnings."""
        return any(
            w.warning_level == WarningLevel.CRITICAL
            for w in self.coverage_warnings
        )
    
    @property
    def has_blocking_considerations(self) -> bool:
        """Check if there are any blocking policy considerations."""
        return any(p.is_blocking for p in self.policy_considerations)
    
    @property
    def high_impact_conflicts_count(self) -> int:
        """Count of high-impact conflicts."""
        return sum(
            1 for c in self.team_conflicts
            if c.impact_level == ImpactLevel.HIGH
        )
    
    class Config:
        json_schema_extra = {
            "example": {
                "request_id": "550e8400-e29b-41d4-a716-446655440000",
                "team_conflicts": [
                    {
                        "conflicting_employee_id": "660e8400-e29b-41d4-a716-446655440001",
                        "conflicting_employee_name": "Jane Smith",
                        "conflict_dates": ["2024-03-15"],
                        "conflict_type": "approved_request",
                        "impact_level": "medium",
                    }
                ],
                "holiday_overlaps": [
                    {
                        "holiday_date": "2024-03-17",
                        "holiday_name": "St. Patrick's Day",
                        "is_company_holiday": False,
                    }
                ],
                "coverage_warnings": [],
                "policy_considerations": [],
                "balance_impact": {
                    "current_balance": 80.0,
                    "requested_hours": 24.0,
                    "balance_after_approval": 56.0,
                    "accrual_by_end_date": 8.0,
                    "will_have_negative_balance": False,
                    "policy_type": "vacation",
                },
            }
        }


class ApprovalDecisionRequest(BaseModel):
    """
    Request model for submitting an approval decision.
    
    Captures the approver's decision along with any comments
    or conditions attached to the approval.
    """
    
    request_id: UUID = Field(
        ...,
        description="UUID of the time-off request being decided",
    )
    decision: ApprovalDecision = Field(
        ...,
        description="The approval decision (approve or deny)",
    )
    comments: str = Field(
        default="",
        max_length=1000,
        description="Comments from the approver explaining the decision",
    )
    conditions: List[ApprovalCondition] = Field(
        default_factory=list,
        description="List of conditions attached to the approval (if any)",
    )
    
    @field_validator("decision", mode="before")
    @classmethod
    def validate_decision(cls, v: Any) -> ApprovalDecision:
        """Ensure decision is a valid enum value."""
        if isinstance(v, str):
            try:
                return ApprovalDecision(v.lower())
            except ValueError:
                raise ValueError(
                    f"Invalid decision: {v}. Must be one of: "
                    f"{[e.value for e in ApprovalDecision]}"
                )
        return v
    
    @property
    def is_conditional_approval(self) -> bool:
        """Check if this is a conditional approval."""
        return (
            self.decision == ApprovalDecision.APPROVE
            and len(self.conditions) > 0
        )
    
    class Config:
        json_schema_extra = {
            "example": {
                "request_id": "550e8400-e29b-41d4-a716-446655440000",
                "decision": "approve",
                "comments": "Approved with date adjustment",
                "conditions": [
                    {
                        "condition_type": "date_modification",
                        "condition_details": {
                            "modified_start": "2024-03-18",
                        },
                        "condition_notes": "Moved start date to avoid critical meeting",
                    }
                ],
            }
        }


class ApprovalDecisionResponse(BaseModel):
    """
    Response model after processing an approval decision.
    
    Confirms the decision was recorded and provides the
    updated status of the request.
    """
    
    request_id: UUID = Field(
        ...,
        description="UUID of the time-off request",
    )
    decision: ApprovalDecision = Field(
        ...,
        description="The recorded decision",
    )
    new_status: str = Field(
        ...,
        description="The new status of the request after the decision",
    )
    processed_at: str = Field(
        ...,
        description="ISO timestamp when the decision was processed",
    )
    conditions_applied: List[ApprovalCondition] = Field(
        default_factory=list,
        description="List of conditions that were applied",
    )
    next_approver_required: bool = Field(
        default=False,
        description="Whether additional approval levels are required",
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "request_id": "550e8400-e29b-41d4-a716-446655440000",
                "decision": "approve",
                "new_status": "approved",
                "processed_at": "2024-03-10T14:30:00Z",
                "conditions_applied": [],
                "next_approver_required": False,
            }
        }

