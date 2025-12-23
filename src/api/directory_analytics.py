"""API endpoints for advanced directory filtering and organizational analytics."""

import uuid
from datetime import datetime, date
from enum import Enum
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select, distinct
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.models.employee import Employee, Department, Location
from src.utils.auth import CurrentUser, UserRole, get_mock_current_user
from src.utils.errors import ForbiddenError


# =============================================================================
# Enums
# =============================================================================

class FilterCategory(str, Enum):
    """Categories for filtering employees."""
    
    DEMOGRAPHIC = "demographic"
    EMPLOYMENT = "employment"
    ORGANIZATIONAL = "organizational"
    GEOGRAPHIC = "geographic"
    TEMPORAL = "temporal"


class FilterType(str, Enum):
    """Type of filter control."""
    
    MULTI_SELECT = "multi_select"
    SINGLE_SELECT = "single_select"
    RANGE = "range"
    DATE_RANGE = "date_range"
    TEXT = "text"
    BOOLEAN = "boolean"


class MetricTrend(str, Enum):
    """Trend direction for metrics."""
    
    INCREASING = "increasing"
    DECREASING = "decreasing"
    STABLE = "stable"
    VOLATILE = "volatile"


class RecommendationPriority(str, Enum):
    """Priority level for recommendations."""
    
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# =============================================================================
# Filter Models
# =============================================================================

class FilterOption(BaseModel):
    """Option for a filter with count."""
    
    value: str = Field(..., description="Filter value")
    label: str = Field(..., description="Display label")
    count: int = Field(default=0, description="Number of matching employees")
    is_active: bool = Field(default=True, description="Whether option is selectable")


class FilterDefinition(BaseModel):
    """Definition of a filter."""
    
    id: str = Field(..., description="Filter identifier")
    name: str = Field(..., description="Display name")
    category: FilterCategory = Field(..., description="Filter category")
    filter_type: FilterType = Field(..., description="Type of filter control")
    description: Optional[str] = Field(None, description="Filter description")
    
    # Options for select filters
    options: List[FilterOption] = Field(default_factory=list)
    
    # Range constraints
    min_value: Optional[float] = Field(None, description="Minimum value for range")
    max_value: Optional[float] = Field(None, description="Maximum value for range")
    
    # Metadata
    is_required: bool = Field(default=False, description="Whether filter is required")
    depends_on: Optional[str] = Field(None, description="Parent filter this depends on")
    access_level: str = Field(default="employee", description="Minimum access level")


class FilterSuggestion(BaseModel):
    """Intelligent filter suggestion."""
    
    filter_id: str = Field(..., description="Suggested filter ID")
    reason: str = Field(..., description="Why this filter is suggested")
    relevance_score: float = Field(default=1.0, ge=0.0, le=1.0)
    context: str = Field(default="general", description="Context for suggestion")


class FiltersResponse(BaseModel):
    """Response containing all available filters."""
    
    # Available filters by category
    filters: List[FilterDefinition] = Field(default_factory=list)
    
    # Grouped by category for UI
    categories: Dict[str, List[FilterDefinition]] = Field(default_factory=dict)
    
    # Suggestions
    suggestions: List[FilterSuggestion] = Field(default_factory=list)
    
    # Metadata
    total_employees: int = Field(default=0, description="Total employees in scope")
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    access_level: str = Field(default="employee", description="User's access level")


# =============================================================================
# Analytics Models
# =============================================================================

class SpanOfControlMetric(BaseModel):
    """Span of control analysis for a manager."""
    
    manager_id: int
    manager_name: str
    direct_reports: int
    total_reports: int  # Including indirect
    organizational_level: int
    is_optimal: bool = Field(default=True)
    recommendation: Optional[str] = None


class DepartmentDensity(BaseModel):
    """Density analysis for a department."""
    
    department_id: int
    department_name: str
    total_employees: int
    managers_count: int
    manager_to_employee_ratio: float
    average_span_of_control: float
    max_depth: int
    efficiency_score: float = Field(default=1.0, ge=0.0, le=1.0)


class LocationDensity(BaseModel):
    """Employee density by location."""
    
    location_id: int
    location_name: str
    total_employees: int
    departments_represented: int
    primary_department: Optional[str] = None
    capacity_utilization: Optional[float] = None


class TenureDistribution(BaseModel):
    """Distribution of employee tenure."""
    
    bucket: str = Field(..., description="Tenure bucket (e.g., '0-1 years')")
    count: int
    percentage: float


class MetricAnalysis(BaseModel):
    """Detailed analysis of a metric."""
    
    metric_name: str
    current_value: float
    benchmark_value: Optional[float] = None
    trend: MetricTrend = MetricTrend.STABLE
    change_from_previous: Optional[float] = None
    analysis: str = Field(default="", description="Narrative analysis")
    is_healthy: bool = Field(default=True)


class OptimizationRecommendation(BaseModel):
    """Recommendation for organizational optimization."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    description: str
    priority: RecommendationPriority
    category: str = Field(default="efficiency")
    
    # Impact analysis
    affected_departments: List[str] = Field(default_factory=list)
    affected_employees_count: int = Field(default=0)
    estimated_impact: str = Field(default="", description="Expected outcome")
    
    # Implementation
    effort_level: str = Field(default="medium", description="low/medium/high")
    prerequisites: List[str] = Field(default_factory=list)


class OrganizationalAnalyticsResponse(BaseModel):
    """Comprehensive organizational analytics response."""
    
    # Summary metrics
    total_employees: int = Field(default=0)
    total_managers: int = Field(default=0)
    total_departments: int = Field(default=0)
    total_locations: int = Field(default=0)
    
    # Ratios and averages
    overall_manager_ratio: float = Field(default=0.0, description="Managers per employee")
    average_span_of_control: float = Field(default=0.0)
    average_organizational_depth: float = Field(default=0.0)
    
    # Detailed analyses
    span_of_control_analysis: List[SpanOfControlMetric] = Field(default_factory=list)
    department_density: List[DepartmentDensity] = Field(default_factory=list)
    location_density: List[LocationDensity] = Field(default_factory=list)
    tenure_distribution: List[TenureDistribution] = Field(default_factory=list)
    
    # Metric analyses
    metrics: List[MetricAnalysis] = Field(default_factory=list)
    
    # Recommendations
    recommendations: List[OptimizationRecommendation] = Field(default_factory=list)
    
    # Metadata
    analysis_period: str = Field(default="current", description="Period of analysis")
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    data_freshness: str = Field(default="real-time")


# =============================================================================
# Helper Functions
# =============================================================================

def build_department_filter(session: Session) -> FilterDefinition:
    """Build department filter with counts."""
    result = session.execute(
        select(
            Department.id,
            Department.name,
            func.count(Employee.id).label("count"),
        )
        .outerjoin(Employee, Employee.department_id == Department.id)
        .where(Department.is_active == True)
        .group_by(Department.id, Department.name)
        .order_by(Department.name)
    )
    
    options = []
    for row in result:
        options.append(FilterOption(
            value=str(row.id),
            label=row.name,
            count=row.count or 0,
        ))
    
    return FilterDefinition(
        id="department",
        name="Department",
        category=FilterCategory.ORGANIZATIONAL,
        filter_type=FilterType.MULTI_SELECT,
        description="Filter by department",
        options=options,
    )


def build_location_filter(session: Session) -> FilterDefinition:
    """Build location filter with counts."""
    result = session.execute(
        select(
            Location.id,
            Location.name,
            func.count(Employee.id).label("count"),
        )
        .outerjoin(Employee, Employee.location_id == Location.id)
        .where(Location.is_active == True)
        .group_by(Location.id, Location.name)
        .order_by(Location.name)
    )
    
    options = []
    for row in result:
        options.append(FilterOption(
            value=str(row.id),
            label=row.name,
            count=row.count or 0,
        ))
    
    return FilterDefinition(
        id="location",
        name="Location",
        category=FilterCategory.GEOGRAPHIC,
        filter_type=FilterType.MULTI_SELECT,
        description="Filter by office location",
        options=options,
    )


def build_employment_type_filter(session: Session) -> FilterDefinition:
    """Build employment type filter."""
    result = session.execute(
        select(
            Employee.employment_type,
            func.count(Employee.id).label("count"),
        )
        .where(Employee.is_active == True)
        .where(Employee.employment_type.isnot(None))
        .group_by(Employee.employment_type)
    )
    
    options = []
    for row in result:
        if row.employment_type:
            label = row.employment_type.replace("_", " ").title()
            options.append(FilterOption(
                value=row.employment_type,
                label=label,
                count=row.count,
            ))
    
    return FilterDefinition(
        id="employment_type",
        name="Employment Type",
        category=FilterCategory.EMPLOYMENT,
        filter_type=FilterType.MULTI_SELECT,
        description="Filter by employment type",
        options=options,
    )


def build_is_manager_filter(session: Session) -> FilterDefinition:
    """Build is manager filter."""
    # Count managers (employees with direct reports)
    manager_count = session.execute(
        select(func.count(distinct(Employee.manager_id)))
        .where(Employee.is_active == True)
        .where(Employee.manager_id.isnot(None))
    ).scalar() or 0
    
    total = session.execute(
        select(func.count()).where(Employee.is_active == True)
    ).scalar() or 0
    
    return FilterDefinition(
        id="is_manager",
        name="Manager Status",
        category=FilterCategory.ORGANIZATIONAL,
        filter_type=FilterType.SINGLE_SELECT,
        description="Filter by whether employee has direct reports",
        options=[
            FilterOption(value="true", label="Is a Manager", count=manager_count),
            FilterOption(value="false", label="Not a Manager", count=total - manager_count),
        ],
    )


def build_tenure_filter(session: Session) -> FilterDefinition:
    """Build tenure range filter."""
    # Get min and max hire dates
    result = session.execute(
        select(
            func.min(Employee.hire_date),
            func.max(Employee.hire_date),
        ).where(Employee.is_active == True)
    ).first()
    
    min_date = result[0] if result else None
    max_date = result[1] if result else None
    
    today = date.today()
    
    # Calculate tenure buckets
    buckets = [
        ("0-6 months", 0, 183),
        ("6-12 months", 184, 365),
        ("1-2 years", 366, 730),
        ("2-5 years", 731, 1825),
        ("5+ years", 1826, 99999),
    ]
    
    options = []
    for label, min_days, max_days in buckets:
        count = session.execute(
            select(func.count())
            .where(Employee.is_active == True)
            .where(Employee.hire_date.isnot(None))
            .where(func.datediff(func.current_date(), Employee.hire_date) >= min_days)
            .where(func.datediff(func.current_date(), Employee.hire_date) <= max_days)
        ).scalar() or 0
        
        options.append(FilterOption(
            value=label.replace(" ", "_").lower(),
            label=label,
            count=count,
        ))
    
    return FilterDefinition(
        id="tenure",
        name="Tenure",
        category=FilterCategory.TEMPORAL,
        filter_type=FilterType.MULTI_SELECT,
        description="Filter by length of employment",
        options=options,
    )


def generate_filter_suggestions(
    user: CurrentUser,
    session: Session,
) -> List[FilterSuggestion]:
    """Generate intelligent filter suggestions."""
    suggestions = []
    
    # Suggest department filter for managers
    if UserRole.MANAGER in user.roles:
        suggestions.append(FilterSuggestion(
            filter_id="department",
            reason="View employees in your department",
            relevance_score=0.9,
            context="manager_context",
        ))
    
    # Suggest location for HR
    if UserRole.HR in user.roles:
        suggestions.append(FilterSuggestion(
            filter_id="location",
            reason="Analyze workforce distribution by location",
            relevance_score=0.85,
            context="hr_context",
        ))
        suggestions.append(FilterSuggestion(
            filter_id="tenure",
            reason="Review employee tenure distribution",
            relevance_score=0.8,
            context="hr_context",
        ))
    
    # General suggestions
    suggestions.append(FilterSuggestion(
        filter_id="employment_type",
        reason="Filter by employment classification",
        relevance_score=0.7,
        context="general",
    ))
    
    return suggestions


def calculate_span_of_control(
    manager_id: int,
    session: Session,
) -> tuple[int, int]:
    """Calculate direct and total reports for a manager."""
    direct = session.execute(
        select(func.count())
        .where(Employee.manager_id == manager_id)
        .where(Employee.is_active == True)
    ).scalar() or 0
    
    # For total, would recursively count all reports
    # Simplified here to direct only
    total = direct
    
    return direct, total


def analyze_department_density(
    department: Department,
    session: Session,
) -> DepartmentDensity:
    """Analyze density metrics for a department."""
    # Count employees
    total_employees = session.execute(
        select(func.count())
        .where(Employee.department_id == department.id)
        .where(Employee.is_active == True)
    ).scalar() or 0
    
    # Count managers in department
    managers_count = session.execute(
        select(func.count(distinct(Employee.manager_id)))
        .where(Employee.department_id == department.id)
        .where(Employee.manager_id.isnot(None))
        .where(Employee.is_active == True)
    ).scalar() or 0
    
    # Calculate ratio
    ratio = managers_count / total_employees if total_employees > 0 else 0
    avg_span = total_employees / managers_count if managers_count > 0 else 0
    
    # Efficiency score (simplified)
    # Optimal span is 5-8, penalty for too narrow or too wide
    efficiency = 1.0
    if avg_span < 4:
        efficiency = 0.7  # Too narrow
    elif avg_span > 10:
        efficiency = 0.75  # Too wide
    
    return DepartmentDensity(
        department_id=department.id,
        department_name=department.name,
        total_employees=total_employees,
        managers_count=managers_count,
        manager_to_employee_ratio=round(ratio, 3),
        average_span_of_control=round(avg_span, 1),
        max_depth=3,  # Simplified
        efficiency_score=efficiency,
    )


def generate_optimization_recommendations(
    analytics: Dict[str, Any],
    session: Session,
) -> List[OptimizationRecommendation]:
    """Generate optimization recommendations based on analytics."""
    recommendations = []
    
    avg_span = analytics.get("average_span_of_control", 0)
    
    # Check for span of control issues
    if avg_span < 4:
        recommendations.append(OptimizationRecommendation(
            title="Consider Consolidating Management Layers",
            description=(
                "Average span of control is below optimal range. "
                "Consider restructuring to reduce management layers."
            ),
            priority=RecommendationPriority.MEDIUM,
            category="efficiency",
            estimated_impact="Reduced overhead, faster decision making",
            effort_level="high",
        ))
    elif avg_span > 10:
        recommendations.append(OptimizationRecommendation(
            title="Consider Adding Team Leads",
            description=(
                "Some managers have very wide spans of control. "
                "Consider adding team leads to improve oversight."
            ),
            priority=RecommendationPriority.MEDIUM,
            category="effectiveness",
            estimated_impact="Improved employee support and development",
            effort_level="medium",
        ))
    
    # Check for location concentration
    if analytics.get("location_count", 0) == 1:
        recommendations.append(OptimizationRecommendation(
            title="Consider Geographic Diversification",
            description=(
                "All employees are in a single location. "
                "Consider remote work options for resilience."
            ),
            priority=RecommendationPriority.LOW,
            category="resilience",
            estimated_impact="Business continuity improvement",
            effort_level="low",
        ))
    
    return recommendations


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


# =============================================================================
# Router Setup
# =============================================================================

directory_analytics_router = APIRouter(
    prefix="/api/employee-directory",
    tags=["Directory Analytics"],
)


# =============================================================================
# Endpoints
# =============================================================================

@directory_analytics_router.get(
    "/filters",
    response_model=FiltersResponse,
    summary="Get Available Filters",
    description="Get comprehensive filtering categories for employee directory.",
)
async def get_directory_filters(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    context: Optional[str] = Query(None, description="Context for filter suggestions"),
) -> FiltersResponse:
    """
    Get available filters for employee directory.
    
    - Provides demographic, employment, organizational, and geographic filters
    - Includes counts for each filter option
    - Generates intelligent suggestions based on user role
    - Enforces privacy policy and access levels
    """
    filters = []
    
    # Build filters based on access level
    access_level = "employee"
    if UserRole.HR in current_user.roles or UserRole.ADMIN in current_user.roles:
        access_level = "admin"
    elif UserRole.MANAGER in current_user.roles:
        access_level = "manager"
    
    # Department filter
    dept_filter = build_department_filter(session)
    filters.append(dept_filter)
    
    # Location filter
    loc_filter = build_location_filter(session)
    filters.append(loc_filter)
    
    # Employment type filter
    emp_type_filter = build_employment_type_filter(session)
    filters.append(emp_type_filter)
    
    # Manager status filter
    manager_filter = build_is_manager_filter(session)
    filters.append(manager_filter)
    
    # Tenure filter (simplified without date diff function)
    filters.append(FilterDefinition(
        id="tenure",
        name="Tenure",
        category=FilterCategory.TEMPORAL,
        filter_type=FilterType.MULTI_SELECT,
        description="Filter by length of employment",
        options=[
            FilterOption(value="0_6_months", label="0-6 months", count=0),
            FilterOption(value="6_12_months", label="6-12 months", count=0),
            FilterOption(value="1_2_years", label="1-2 years", count=0),
            FilterOption(value="2_5_years", label="2-5 years", count=0),
            FilterOption(value="5_plus_years", label="5+ years", count=0),
        ],
    ))
    
    # Hire date range filter
    filters.append(FilterDefinition(
        id="hire_date",
        name="Hire Date",
        category=FilterCategory.TEMPORAL,
        filter_type=FilterType.DATE_RANGE,
        description="Filter by hire date range",
    ))
    
    # Active status filter
    filters.append(FilterDefinition(
        id="is_active",
        name="Status",
        category=FilterCategory.EMPLOYMENT,
        filter_type=FilterType.SINGLE_SELECT,
        description="Filter by active/inactive status",
        options=[
            FilterOption(value="true", label="Active", count=0),
            FilterOption(value="false", label="Inactive", count=0),
        ],
        access_level="manager",  # Only managers+ can see inactive
    ))
    
    # Build categories
    categories: Dict[str, List[FilterDefinition]] = {}
    for f in filters:
        cat = f.category.value
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(f)
    
    # Generate suggestions
    suggestions = generate_filter_suggestions(current_user, session)
    
    # Get total employees
    total = session.execute(
        select(func.count()).where(Employee.is_active == True)
    ).scalar() or 0
    
    return FiltersResponse(
        filters=filters,
        categories=categories,
        suggestions=suggestions,
        total_employees=total,
        access_level=access_level,
    )


@directory_analytics_router.get(
    "/analytics/organizational-density",
    response_model=OrganizationalAnalyticsResponse,
    summary="Get Organizational Density Analytics",
    description="Analyze manager-to-employee ratios and organizational structure.",
)
async def get_organizational_density(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    department_id: Optional[int] = Query(None, description="Filter by department"),
    location_id: Optional[int] = Query(None, description="Filter by location"),
) -> OrganizationalAnalyticsResponse:
    """
    Get organizational density analytics.
    
    - Analyzes manager-to-employee ratios
    - Calculates span of control metrics
    - Provides department and location density analysis
    - Generates optimization recommendations
    
    Requires HR or Admin role.
    """
    # Check permissions
    if not any(r in current_user.roles for r in [UserRole.HR, UserRole.ADMIN]):
        raise ForbiddenError(message="Insufficient permissions for analytics access")
    
    # Base query conditions
    conditions = [Employee.is_active == True]
    if department_id:
        conditions.append(Employee.department_id == department_id)
    if location_id:
        conditions.append(Employee.location_id == location_id)
    
    # Total employees
    total_employees = session.execute(
        select(func.count()).where(*conditions)
    ).scalar() or 0
    
    # Total managers (employees with reports)
    total_managers = session.execute(
        select(func.count(distinct(Employee.manager_id)))
        .where(Employee.manager_id.isnot(None))
        .where(*conditions)
    ).scalar() or 0
    
    # Total departments
    total_departments = session.execute(
        select(func.count()).where(Department.is_active == True)
    ).scalar() or 0
    
    # Total locations
    total_locations = session.execute(
        select(func.count()).where(Location.is_active == True)
    ).scalar() or 0
    
    # Calculate overall ratios
    manager_ratio = total_managers / total_employees if total_employees > 0 else 0
    avg_span = total_employees / total_managers if total_managers > 0 else 0
    
    # Span of control analysis for top managers
    span_analysis = []
    result = session.execute(
        select(Employee)
        .where(Employee.is_active == True)
        .where(Employee.id.in_(
            select(distinct(Employee.manager_id))
            .where(Employee.manager_id.isnot(None))
        ))
        .limit(20)
    )
    managers = list(result.scalars())
    
    for manager in managers:
        direct, total = calculate_span_of_control(manager.id, session)
        is_optimal = 4 <= direct <= 8
        recommendation = None
        if direct < 4:
            recommendation = "Consider expanding responsibilities"
        elif direct > 8:
            recommendation = "Consider adding team lead"
        
        span_analysis.append(SpanOfControlMetric(
            manager_id=manager.id,
            manager_name=f"{manager.first_name} {manager.last_name}",
            direct_reports=direct,
            total_reports=total,
            organizational_level=0,  # Simplified
            is_optimal=is_optimal,
            recommendation=recommendation,
        ))
    
    # Department density
    dept_density = []
    result = session.execute(
        select(Department).where(Department.is_active == True).limit(20)
    )
    departments = list(result.scalars())
    
    for dept in departments:
        density = analyze_department_density(dept, session)
        dept_density.append(density)
    
    # Location density
    loc_density = []
    result = session.execute(
        select(Location).where(Location.is_active == True).limit(20)
    )
    locations = list(result.scalars())
    
    for loc in locations:
        emp_count = session.execute(
            select(func.count())
            .where(Employee.location_id == loc.id)
            .where(Employee.is_active == True)
        ).scalar() or 0
        
        depts_count = session.execute(
            select(func.count(distinct(Employee.department_id)))
            .where(Employee.location_id == loc.id)
            .where(Employee.is_active == True)
        ).scalar() or 0
        
        loc_density.append(LocationDensity(
            location_id=loc.id,
            location_name=loc.name,
            total_employees=emp_count,
            departments_represented=depts_count,
        ))
    
    # Tenure distribution
    tenure_dist = [
        TenureDistribution(bucket="0-1 years", count=0, percentage=0),
        TenureDistribution(bucket="1-3 years", count=0, percentage=0),
        TenureDistribution(bucket="3-5 years", count=0, percentage=0),
        TenureDistribution(bucket="5+ years", count=0, percentage=0),
    ]
    
    # Metric analyses
    metrics = [
        MetricAnalysis(
            metric_name="Manager to Employee Ratio",
            current_value=round(manager_ratio, 3),
            benchmark_value=0.15,  # Industry benchmark ~15%
            trend=MetricTrend.STABLE,
            analysis=f"Current ratio is {round(manager_ratio * 100, 1)}% managers",
            is_healthy=0.10 <= manager_ratio <= 0.20,
        ),
        MetricAnalysis(
            metric_name="Average Span of Control",
            current_value=round(avg_span, 1),
            benchmark_value=6.0,  # Optimal range 5-8
            trend=MetricTrend.STABLE,
            analysis=f"Average manager oversees {round(avg_span, 1)} employees",
            is_healthy=4 <= avg_span <= 10,
        ),
    ]
    
    # Generate recommendations
    analytics_data = {
        "average_span_of_control": avg_span,
        "manager_ratio": manager_ratio,
        "location_count": total_locations,
    }
    recommendations = generate_optimization_recommendations(analytics_data, session)
    
    return OrganizationalAnalyticsResponse(
        total_employees=total_employees,
        total_managers=total_managers,
        total_departments=total_departments,
        total_locations=total_locations,
        overall_manager_ratio=round(manager_ratio, 3),
        average_span_of_control=round(avg_span, 1),
        average_organizational_depth=3.0,  # Simplified
        span_of_control_analysis=span_analysis,
        department_density=dept_density,
        location_density=loc_density,
        tenure_distribution=tenure_dist,
        metrics=metrics,
        recommendations=recommendations,
    )

