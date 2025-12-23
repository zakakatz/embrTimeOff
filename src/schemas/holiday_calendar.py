"""Pydantic models for holiday calendar and regulatory compliance API endpoints."""

from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, validator


# =============================================================================
# Enums
# =============================================================================

class HolidayType(str, Enum):
    """Type of holiday."""
    FEDERAL = "federal"
    STATE = "state"
    RELIGIOUS = "religious"
    COMPANY = "company"
    FLOATING = "floating"
    OBSERVED = "observed"


class ComplianceType(str, Enum):
    """Type of regulatory compliance."""
    LABOR_LAW = "labor_law"
    RELIGIOUS_ACCOMMODATION = "religious_accommodation"
    STATE_REGULATION = "state_regulation"
    FEDERAL_REGULATION = "federal_regulation"
    UNION_AGREEMENT = "union_agreement"
    INTERNATIONAL = "international"


class ComplianceStatus(str, Enum):
    """Compliance status."""
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PENDING_REVIEW = "pending_review"
    REMEDIATION_REQUIRED = "remediation_required"
    EXEMPT = "exempt"


class ImpactLevel(str, Enum):
    """Organizational impact level."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


# =============================================================================
# Holiday Models
# =============================================================================

class HolidayDate(BaseModel):
    """Individual holiday date information."""
    date: date = Field(..., description="Holiday date")
    name: str = Field(..., description="Holiday name")
    holiday_type: HolidayType = Field(..., description="Type of holiday")
    is_paid: bool = Field(default=True, description="Is a paid holiday")
    is_company_closed: bool = Field(default=True, description="Is company closed")
    
    # Religious observance
    is_religious: bool = Field(default=False, description="Is religious holiday")
    religious_tradition: Optional[str] = Field(default=None, description="Religious tradition")
    accommodation_required: bool = Field(default=False, description="Accommodation required")
    
    # Regulatory
    is_regulatory_required: bool = Field(default=False, description="Regulatory requirement")
    applicable_jurisdictions: List[str] = Field(
        default_factory=list,
        description="Applicable jurisdictions",
    )
    
    # Notes
    notes: Optional[str] = Field(default=None, description="Additional notes")


class HolidayCalendarCreateRequest(BaseModel):
    """Request model for creating a holiday calendar."""
    calendar_name: str = Field(..., min_length=1, max_length=100, description="Calendar name")
    calendar_year: int = Field(..., description="Calendar year")
    description: Optional[str] = Field(default=None, max_length=500, description="Description")
    
    # Holidays
    holidays: List[HolidayDate] = Field(..., min_items=1, description="Holiday dates")
    
    # Regulatory compliance
    regulatory_compliance_enabled: bool = Field(default=True, description="Enable compliance checks")
    applicable_labor_laws: List[str] = Field(
        default_factory=list,
        description="Applicable labor laws",
    )
    
    # Religious observance
    religious_observance_enabled: bool = Field(default=True, description="Enable religious observance")
    supported_religious_traditions: List[str] = Field(
        default_factory=list,
        description="Supported religious traditions",
    )
    
    # Organizational settings
    applies_to_locations: Optional[List[int]] = Field(
        default=None,
        description="Location IDs this calendar applies to",
    )
    applies_to_departments: Optional[List[int]] = Field(
        default=None,
        description="Department IDs this calendar applies to",
    )
    is_default: bool = Field(default=False, description="Is default calendar")

    @validator("holidays")
    def validate_holidays(cls, v):
        dates = [h.date for h in v]
        if len(dates) != len(set(dates)):
            raise ValueError("Duplicate holiday dates are not allowed")
        return v


class RegulatoryValidation(BaseModel):
    """Regulatory validation result for a holiday."""
    holiday_name: str = Field(..., description="Holiday name")
    holiday_date: date = Field(..., description="Holiday date")
    is_compliant: bool = Field(..., description="Is compliant")
    
    # Compliance details
    applicable_regulations: List[str] = Field(
        default_factory=list,
        description="Applicable regulations",
    )
    compliance_notes: List[str] = Field(
        default_factory=list,
        description="Compliance notes",
    )
    
    # Issues
    issues: List[str] = Field(default_factory=list, description="Compliance issues")
    recommendations: List[str] = Field(default_factory=list, description="Recommendations")


class BusinessImpactAnalysis(BaseModel):
    """Business impact analysis for the calendar."""
    total_holidays: int = Field(..., description="Total holidays")
    paid_holidays: int = Field(..., description="Paid holidays count")
    company_closure_days: int = Field(..., description="Company closure days")
    
    # Financial impact
    estimated_payroll_impact: Optional[float] = Field(
        default=None,
        description="Estimated payroll impact",
    )
    estimated_productivity_impact_days: float = Field(
        default=0,
        description="Estimated productivity impact in days",
    )
    
    # Operational impact
    operational_impact_level: ImpactLevel = Field(..., description="Operational impact level")
    affected_departments: int = Field(default=0, description="Number of affected departments")
    affected_employees_estimate: int = Field(default=0, description="Affected employees estimate")
    
    # Recommendations
    scheduling_recommendations: List[str] = Field(
        default_factory=list,
        description="Scheduling recommendations",
    )


class HolidayCalendarResponse(BaseModel):
    """Response model for created holiday calendar."""
    calendar_id: int = Field(..., description="Generated calendar ID")
    calendar_name: str = Field(..., description="Calendar name")
    calendar_year: int = Field(..., description="Calendar year")
    description: Optional[str] = Field(default=None, description="Description")
    
    # Holidays
    holidays: List[HolidayDate] = Field(..., description="Holiday dates")
    total_holidays: int = Field(..., description="Total holiday count")
    
    # Compliance
    regulatory_validation: List[RegulatoryValidation] = Field(
        default_factory=list,
        description="Regulatory validation results",
    )
    overall_compliance_status: ComplianceStatus = Field(
        ...,
        description="Overall compliance status",
    )
    
    # Impact
    business_impact: BusinessImpactAnalysis = Field(..., description="Business impact analysis")
    
    # Settings
    is_default: bool = Field(default=False, description="Is default calendar")
    applies_to_locations: Optional[List[int]] = Field(default=None, description="Location IDs")
    applies_to_departments: Optional[List[int]] = Field(default=None, description="Department IDs")
    
    # Audit
    created_by: int = Field(..., description="Created by employee ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    
    class Config:
        json_encoders = {
            date: lambda v: v.isoformat(),
            datetime: lambda v: v.isoformat(),
        }


# =============================================================================
# Regulatory Compliance Models
# =============================================================================

class ComplianceRequirement(BaseModel):
    """Individual compliance requirement."""
    requirement_id: str = Field(..., description="Requirement ID")
    requirement_name: str = Field(..., description="Requirement name")
    description: str = Field(..., description="Requirement description")
    
    # Classification
    compliance_type: ComplianceType = Field(..., description="Compliance type")
    jurisdiction: str = Field(..., description="Applicable jurisdiction")
    
    # Requirements
    mandatory: bool = Field(default=True, description="Is mandatory")
    effective_date: date = Field(..., description="Effective date")
    expiration_date: Optional[date] = Field(default=None, description="Expiration date")
    
    # Verification
    verification_method: str = Field(..., description="Verification method")
    verification_frequency: str = Field(..., description="Verification frequency")
    
    # Penalties
    non_compliance_penalty: Optional[str] = Field(
        default=None,
        description="Non-compliance penalty",
    )


class OrganizationalImpact(BaseModel):
    """Organizational impact assessment."""
    impact_level: ImpactLevel = Field(..., description="Impact level")
    affected_areas: List[str] = Field(default_factory=list, description="Affected areas")
    affected_employee_count: int = Field(default=0, description="Affected employee count")
    
    # Financial
    estimated_cost: Optional[float] = Field(default=None, description="Estimated cost")
    implementation_timeline: Optional[str] = Field(
        default=None,
        description="Implementation timeline",
    )
    
    # Risk
    risk_if_non_compliant: str = Field(..., description="Risk if non-compliant")
    mitigation_strategies: List[str] = Field(
        default_factory=list,
        description="Mitigation strategies",
    )


class ComplianceDeficiency(BaseModel):
    """Compliance deficiency detail."""
    deficiency_id: str = Field(..., description="Deficiency ID")
    requirement_id: str = Field(..., description="Related requirement ID")
    description: str = Field(..., description="Deficiency description")
    severity: str = Field(..., description="Severity: critical, high, medium, low")
    
    # Current state
    current_state: str = Field(..., description="Current compliance state")
    required_state: str = Field(..., description="Required state")
    gap_description: str = Field(..., description="Gap description")
    
    # Remediation
    remediation_required: bool = Field(default=True, description="Remediation required")
    remediation_steps: List[str] = Field(default_factory=list, description="Remediation steps")
    remediation_deadline: Optional[date] = Field(default=None, description="Deadline")
    estimated_remediation_effort: str = Field(
        default="medium",
        description="Estimated effort",
    )


class RegulatoryComplianceUpdateRequest(BaseModel):
    """Request model for regulatory compliance management."""
    compliance_type: ComplianceType = Field(..., description="Compliance type")
    
    # Requirements
    requirements: List[ComplianceRequirement] = Field(
        ...,
        min_items=1,
        description="Compliance requirements",
    )
    
    # Impact assessment
    organizational_impact: OrganizationalImpact = Field(
        ...,
        description="Organizational impact assessment",
    )
    
    # Tracking
    tracking_enabled: bool = Field(default=True, description="Enable compliance tracking")
    notification_contacts: List[str] = Field(
        default_factory=list,
        description="Notification email addresses",
    )
    
    # Notes
    notes: Optional[str] = Field(default=None, max_length=1000, description="Notes")


class RequirementAdherence(BaseModel):
    """Adherence status for a specific requirement."""
    requirement_id: str = Field(..., description="Requirement ID")
    requirement_name: str = Field(..., description="Requirement name")
    status: ComplianceStatus = Field(..., description="Adherence status")
    
    # Details
    last_verified: Optional[datetime] = Field(default=None, description="Last verification")
    next_verification: Optional[datetime] = Field(default=None, description="Next verification")
    verification_notes: Optional[str] = Field(default=None, description="Verification notes")
    
    # Evidence
    evidence_provided: bool = Field(default=False, description="Evidence provided")
    evidence_documents: List[str] = Field(default_factory=list, description="Evidence docs")


class RegulatoryComplianceResponse(BaseModel):
    """Response model for regulatory compliance management."""
    compliance_id: int = Field(..., description="Compliance record ID")
    compliance_type: ComplianceType = Field(..., description="Compliance type")
    
    # Status
    overall_status: ComplianceStatus = Field(..., description="Overall compliance status")
    compliance_score: float = Field(..., description="Compliance score (0-100)")
    
    # Requirements
    total_requirements: int = Field(..., description="Total requirements")
    compliant_requirements: int = Field(..., description="Compliant count")
    non_compliant_requirements: int = Field(..., description="Non-compliant count")
    pending_requirements: int = Field(..., description="Pending count")
    
    # Detailed adherence
    requirement_adherence: List[RequirementAdherence] = Field(
        ...,
        description="Requirement adherence details",
    )
    
    # Deficiencies
    deficiencies: List[ComplianceDeficiency] = Field(
        default_factory=list,
        description="Identified deficiencies",
    )
    
    # Impact
    organizational_impact: OrganizationalImpact = Field(
        ...,
        description="Organizational impact",
    )
    
    # Audit
    audit_trail_id: str = Field(..., description="Audit trail ID")
    last_updated_by: int = Field(..., description="Last updated by")
    last_updated_at: datetime = Field(..., description="Last update timestamp")
    
    # Recommendations
    recommendations: List[str] = Field(
        default_factory=list,
        description="Compliance recommendations",
    )
    
    class Config:
        json_encoders = {
            date: lambda v: v.isoformat(),
            datetime: lambda v: v.isoformat(),
        }


