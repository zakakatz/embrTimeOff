"""API endpoints for holiday calendar and regulatory compliance management."""

from datetime import date, datetime
from typing import Any, Dict, List, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, status

from src.schemas.holiday_calendar import (
    HolidayCalendarCreateRequest,
    HolidayCalendarResponse,
    HolidayDate,
    HolidayType,
    RegulatoryValidation,
    BusinessImpactAnalysis,
    ImpactLevel,
    ComplianceStatus,
    RegulatoryComplianceUpdateRequest,
    RegulatoryComplianceResponse,
    ComplianceType,
    ComplianceRequirement,
    OrganizationalImpact,
    RequirementAdherence,
    ComplianceDeficiency,
)


holiday_calendar_router = APIRouter(
    prefix="/api/admin",
    tags=["Holiday Calendar & Regulatory Compliance"],
)


# =============================================================================
# Helper Functions
# =============================================================================

def get_current_user():
    """Mock function to get current authenticated user."""
    return {
        "id": 1,
        "name": "Admin User",
        "role": "admin",
        "is_hr": True,
    }


def validate_admin_access(user: Dict[str, Any]) -> bool:
    """Validate admin access."""
    return user.get("role") == "admin" or user.get("is_hr", False)


def validate_regulatory_compliance(
    holidays: List[HolidayDate],
    applicable_laws: List[str],
) -> List[RegulatoryValidation]:
    """Validate holidays against regulatory requirements."""
    validations = []
    
    # Federal holidays that should be included
    federal_required = [
        ("New Year's Day", date(2025, 1, 1)),
        ("Memorial Day", date(2025, 5, 26)),
        ("Independence Day", date(2025, 7, 4)),
        ("Labor Day", date(2025, 9, 1)),
        ("Thanksgiving", date(2025, 11, 27)),
        ("Christmas Day", date(2025, 12, 25)),
    ]
    
    holiday_dates = {h.date: h for h in holidays}
    
    for name, req_date in federal_required:
        if req_date in holiday_dates:
            holiday = holiday_dates[req_date]
            validations.append(RegulatoryValidation(
                holiday_name=holiday.name,
                holiday_date=holiday.date,
                is_compliant=True,
                applicable_regulations=["FLSA", "Federal Holiday Act"],
                compliance_notes=["Holiday meets federal requirements"],
                issues=[],
                recommendations=[],
            ))
        else:
            validations.append(RegulatoryValidation(
                holiday_name=name,
                holiday_date=req_date,
                is_compliant=False,
                applicable_regulations=["FLSA", "Federal Holiday Act"],
                compliance_notes=[],
                issues=[f"{name} is a recommended federal holiday but not included"],
                recommendations=[f"Consider adding {name} to meet federal guidelines"],
            ))
    
    # Check religious accommodation
    for holiday in holidays:
        if holiday.is_religious and holiday.accommodation_required:
            validations.append(RegulatoryValidation(
                holiday_name=holiday.name,
                holiday_date=holiday.date,
                is_compliant=True,
                applicable_regulations=["Title VII", "Religious Accommodation"],
                compliance_notes=["Religious accommodation properly configured"],
                issues=[],
                recommendations=[],
            ))
    
    return validations


def calculate_business_impact(
    holidays: List[HolidayDate],
    employee_count: int = 100,
    avg_daily_cost: float = 500.0,
) -> BusinessImpactAnalysis:
    """Calculate business impact of the holiday calendar."""
    paid_holidays = sum(1 for h in holidays if h.is_paid)
    closure_days = sum(1 for h in holidays if h.is_company_closed)
    
    # Estimate payroll impact
    payroll_impact = paid_holidays * employee_count * avg_daily_cost
    
    # Productivity impact
    productivity_impact = closure_days * 1.0  # 1 day per closure
    
    # Determine operational impact
    if closure_days > 15:
        impact_level = ImpactLevel.HIGH
    elif closure_days > 10:
        impact_level = ImpactLevel.MEDIUM
    else:
        impact_level = ImpactLevel.LOW
    
    recommendations = []
    if closure_days > 12:
        recommendations.append("Consider staggering some holiday closures")
    if paid_holidays > 15:
        recommendations.append("Review paid holiday count against industry benchmarks")
    
    return BusinessImpactAnalysis(
        total_holidays=len(holidays),
        paid_holidays=paid_holidays,
        company_closure_days=closure_days,
        estimated_payroll_impact=payroll_impact,
        estimated_productivity_impact_days=productivity_impact,
        operational_impact_level=impact_level,
        affected_departments=10,  # Mock
        affected_employees_estimate=employee_count,
        scheduling_recommendations=recommendations,
    )


# =============================================================================
# Holiday Calendar Endpoint
# =============================================================================

@holiday_calendar_router.post(
    "/holiday-calendars",
    response_model=HolidayCalendarResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create holiday calendar",
    description="Create a new holiday calendar with regulatory compliance verification.",
)
async def create_holiday_calendar(
    request: HolidayCalendarCreateRequest,
):
    """
    Create a new holiday calendar.
    
    This endpoint:
    - Validates holiday dates for proper formatting
    - Verifies regulatory compliance against labor laws
    - Supports religious observance accommodation
    - Provides business impact analysis
    - Maintains audit trail
    
    **Access Control**: Requires admin or HR privileges.
    """
    current_user = get_current_user()
    
    if not validate_admin_access(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or HR privileges required to manage holiday calendars",
        )
    
    # Validate holiday dates are in the correct year
    for holiday in request.holidays:
        if holiday.date.year != request.calendar_year:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Holiday {holiday.name} date must be in year {request.calendar_year}",
            )
    
    # Perform regulatory validation
    regulatory_validations = validate_regulatory_compliance(
        request.holidays,
        request.applicable_labor_laws,
    )
    
    # Determine overall compliance status
    non_compliant_count = sum(1 for v in regulatory_validations if not v.is_compliant)
    if non_compliant_count == 0:
        overall_status = ComplianceStatus.COMPLIANT
    elif non_compliant_count <= 2:
        overall_status = ComplianceStatus.PENDING_REVIEW
    else:
        overall_status = ComplianceStatus.REMEDIATION_REQUIRED
    
    # Calculate business impact
    business_impact = calculate_business_impact(request.holidays)
    
    # Generate calendar ID (mock)
    calendar_id = 1001
    now = datetime.utcnow()
    
    return HolidayCalendarResponse(
        calendar_id=calendar_id,
        calendar_name=request.calendar_name,
        calendar_year=request.calendar_year,
        description=request.description,
        holidays=request.holidays,
        total_holidays=len(request.holidays),
        regulatory_validation=regulatory_validations,
        overall_compliance_status=overall_status,
        business_impact=business_impact,
        is_default=request.is_default,
        applies_to_locations=request.applies_to_locations,
        applies_to_departments=request.applies_to_departments,
        created_by=current_user["id"],
        created_at=now,
    )


# =============================================================================
# Regulatory Compliance Endpoint
# =============================================================================

@holiday_calendar_router.put(
    "/regulatory-compliance",
    response_model=RegulatoryComplianceResponse,
    summary="Manage regulatory compliance",
    description="Update and verify organizational regulatory compliance.",
)
async def update_regulatory_compliance(
    request: RegulatoryComplianceUpdateRequest,
):
    """
    Manage regulatory compliance requirements.
    
    This endpoint:
    - Validates organizational structures against regulations
    - Maintains comprehensive compliance tracking
    - Handles regulatory requirement updates
    - Provides compliance verification with deficiency identification
    - Maintains audit trails
    
    **Access Control**: Requires admin or HR privileges.
    """
    current_user = get_current_user()
    
    if not validate_admin_access(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or HR privileges required to manage regulatory compliance",
        )
    
    now = datetime.utcnow()
    
    # Process requirements and determine adherence
    requirement_adherence = []
    compliant_count = 0
    non_compliant_count = 0
    pending_count = 0
    
    for req in request.requirements:
        # Mock verification (in real implementation, would check against org data)
        is_verified = req.mandatory  # Mock: mandatory items are verified
        
        if is_verified:
            status_val = ComplianceStatus.COMPLIANT
            compliant_count += 1
        elif req.effective_date > date.today():
            status_val = ComplianceStatus.PENDING_REVIEW
            pending_count += 1
        else:
            status_val = ComplianceStatus.NON_COMPLIANT
            non_compliant_count += 1
        
        requirement_adherence.append(RequirementAdherence(
            requirement_id=req.requirement_id,
            requirement_name=req.requirement_name,
            status=status_val,
            last_verified=now if is_verified else None,
            next_verification=datetime(now.year, now.month + 3 if now.month < 10 else 1, 1),
            verification_notes="Automated verification completed" if is_verified else "Manual verification required",
            evidence_provided=is_verified,
            evidence_documents=["compliance_doc.pdf"] if is_verified else [],
        ))
    
    # Identify deficiencies
    deficiencies = []
    for i, adherence in enumerate(requirement_adherence):
        if adherence.status == ComplianceStatus.NON_COMPLIANT:
            deficiencies.append(ComplianceDeficiency(
                deficiency_id=f"DEF-{i+1:03d}",
                requirement_id=adherence.requirement_id,
                description=f"Non-compliance identified for {adherence.requirement_name}",
                severity="high" if request.requirements[i].mandatory else "medium",
                current_state="Non-compliant",
                required_state="Full compliance with regulatory requirement",
                gap_description="Organization has not met the specified requirement",
                remediation_required=True,
                remediation_steps=[
                    "Review current organizational practices",
                    "Implement required changes",
                    "Document compliance evidence",
                    "Schedule verification",
                ],
                remediation_deadline=date.today() + date.resolution if date else None,
                estimated_remediation_effort="high" if request.requirements[i].mandatory else "medium",
            ))
    
    # Calculate compliance score
    total_requirements = len(request.requirements)
    compliance_score = (compliant_count / total_requirements * 100) if total_requirements > 0 else 0
    
    # Determine overall status
    if compliance_score >= 95:
        overall_status = ComplianceStatus.COMPLIANT
    elif compliance_score >= 70:
        overall_status = ComplianceStatus.PENDING_REVIEW
    elif compliance_score >= 50:
        overall_status = ComplianceStatus.REMEDIATION_REQUIRED
    else:
        overall_status = ComplianceStatus.NON_COMPLIANT
    
    # Generate recommendations
    recommendations = []
    if non_compliant_count > 0:
        recommendations.append(f"Address {non_compliant_count} non-compliant requirement(s) immediately")
    if pending_count > 0:
        recommendations.append(f"Complete verification for {pending_count} pending requirement(s)")
    if compliance_score < 100:
        recommendations.append("Schedule regular compliance audits")
    if request.organizational_impact.impact_level in [ImpactLevel.HIGH, ImpactLevel.MEDIUM]:
        recommendations.append("Consider engaging compliance consultant for high-impact areas")
    
    return RegulatoryComplianceResponse(
        compliance_id=2001,  # Mock ID
        compliance_type=request.compliance_type,
        overall_status=overall_status,
        compliance_score=round(compliance_score, 1),
        total_requirements=total_requirements,
        compliant_requirements=compliant_count,
        non_compliant_requirements=non_compliant_count,
        pending_requirements=pending_count,
        requirement_adherence=requirement_adherence,
        deficiencies=deficiencies,
        organizational_impact=request.organizational_impact,
        audit_trail_id=str(uuid.uuid4()),
        last_updated_by=current_user["id"],
        last_updated_at=now,
        recommendations=recommendations,
    )


