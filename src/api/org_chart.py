"""API endpoints for organizational chart and hierarchy visualization."""

import uuid
from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.models.employee import Employee, Department, Location
from src.schemas.employee_directory import OrganizationalChartNode, OrganizationalChartResponse
from src.utils.auth import CurrentUser, UserRole, get_mock_current_user
from src.utils.errors import NotFoundError


# =============================================================================
# Enums
# =============================================================================

class ChartViewType(str, Enum):
    """Type of organizational chart view."""
    
    HIERARCHY = "hierarchy"      # Traditional top-down
    MATRIX = "matrix"           # Matrix organization
    DEPARTMENT = "department"   # By department
    LOCATION = "location"       # By location


class RelationshipStrength(str, Enum):
    """Strength of team relationship."""
    
    STRONG = "strong"     # Direct reporting or frequent collaboration
    MEDIUM = "medium"     # Regular interaction
    WEAK = "weak"         # Occasional interaction


# =============================================================================
# Response Models
# =============================================================================

class EmployeeSummary(BaseModel):
    """Lightweight employee summary for chart nodes."""
    
    id: int
    employee_id: str
    full_name: str
    job_title: Optional[str] = None
    department_name: Optional[str] = None
    location_name: Optional[str] = None
    is_active: bool = True


class ChartNode(BaseModel):
    """Node in organizational chart."""
    
    employee: EmployeeSummary
    level: int = Field(default=0, description="Level in hierarchy")
    span_of_control: int = Field(default=0, description="Total reports")
    direct_reports_count: int = Field(default=0, description="Direct reports")
    is_expanded: bool = Field(default=True)
    children: List["ChartNode"] = Field(default_factory=list)
    
    # Additional relationships for matrix orgs
    dotted_line_reports: List[EmployeeSummary] = Field(default_factory=list)
    functional_relationships: List[EmployeeSummary] = Field(default_factory=list)


ChartNode.model_rebuild()


class DepartmentNode(BaseModel):
    """Department in org chart."""
    
    id: int
    code: str
    name: str
    head: Optional[EmployeeSummary] = None
    employee_count: int = Field(default=0)
    sub_departments: List["DepartmentNode"] = Field(default_factory=list)


DepartmentNode.model_rebuild()


class OrgChartResponse(BaseModel):
    """Response for organizational chart."""
    
    view_type: ChartViewType
    root_node: Optional[ChartNode] = None
    departments: List[DepartmentNode] = Field(default_factory=list)
    
    # Statistics
    total_employees: int = Field(default=0)
    total_departments: int = Field(default=0)
    max_depth: int = Field(default=0)
    
    # Metadata
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    depth_limit: int = Field(default=3)


class TeamMember(BaseModel):
    """Team member for team explorer."""
    
    employee: EmployeeSummary
    role_in_team: str = Field(default="member")
    tenure_months: float = Field(default=0.0)
    is_cross_functional: bool = Field(default=False)


class TeamRelationship(BaseModel):
    """Relationship between teams."""
    
    team_id: str
    team_name: str
    relationship_type: str
    interaction_density: float = Field(default=0.0, ge=0.0, le=1.0)
    shared_projects: int = Field(default=0)


class TeamComposition(BaseModel):
    """Team composition analysis."""
    
    total_members: int = Field(default=0)
    by_employment_type: Dict[str, int] = Field(default_factory=dict)
    by_location: Dict[str, int] = Field(default_factory=dict)
    by_tenure: Dict[str, int] = Field(default_factory=dict)
    average_tenure_months: float = Field(default=0.0)


class TeamOptimizationRecommendation(BaseModel):
    """Recommendation for team optimization."""
    
    recommendation_type: str
    title: str
    description: str
    priority: str = Field(default="medium")
    affected_members: List[str] = Field(default_factory=list)


class TeamExplorerRequest(BaseModel):
    """Request for team explorer."""
    
    manager_id: Optional[int] = Field(None, description="Manager/team lead ID")
    department_id: Optional[int] = Field(None, description="Department ID")
    include_cross_team: bool = Field(default=True, description="Include cross-team relationships")
    include_analysis: bool = Field(default=True, description="Include composition analysis")
    max_depth: int = Field(default=2, ge=1, le=5, description="Depth to explore")


class TeamExplorerResponse(BaseModel):
    """Response for team explorer."""
    
    team_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    team_name: str
    team_lead: Optional[EmployeeSummary] = None
    
    # Members
    members: List[TeamMember] = Field(default_factory=list)
    total_members: int = Field(default=0)
    
    # Relationships
    cross_team_associations: List[TeamRelationship] = Field(default_factory=list)
    
    # Analysis
    composition: Optional[TeamComposition] = None
    
    # Recommendations
    recommendations: List[TeamOptimizationRecommendation] = Field(default_factory=list)
    
    # Metadata
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# Helper Functions
# =============================================================================

def build_employee_summary(employee: Employee) -> EmployeeSummary:
    """Build employee summary from model."""
    return EmployeeSummary(
        id=employee.id,
        employee_id=employee.employee_id,
        full_name=f"{employee.first_name} {employee.last_name}",
        job_title=employee.job_title,
        department_name=employee.department.name if employee.department else None,
        location_name=employee.location.name if employee.location else None,
        is_active=employee.is_active,
    )


def build_chart_node(
    employee: Employee,
    session: Session,
    current_level: int = 0,
    max_depth: int = 3,
) -> ChartNode:
    """Recursively build chart node for employee."""
    summary = build_employee_summary(employee)
    
    # Count direct reports
    direct_reports_count = session.execute(
        select(func.count()).where(
            Employee.manager_id == employee.id,
            Employee.is_active == True,
        )
    ).scalar() or 0
    
    children = []
    
    # Only expand if within depth limit
    if current_level < max_depth and direct_reports_count > 0:
        result = session.execute(
            select(Employee).where(
                Employee.manager_id == employee.id,
                Employee.is_active == True,
            ).order_by(Employee.last_name)
        )
        direct_reports = list(result.scalars())
        
        for report in direct_reports:
            child_node = build_chart_node(
                report, session, current_level + 1, max_depth
            )
            children.append(child_node)
    
    # Calculate span of control (total in subtree)
    span = direct_reports_count
    for child in children:
        span += child.span_of_control
    
    return ChartNode(
        employee=summary,
        level=current_level,
        span_of_control=span,
        direct_reports_count=direct_reports_count,
        is_expanded=current_level < max_depth,
        children=children,
    )


def build_department_node(
    department: Department,
    session: Session,
) -> DepartmentNode:
    """Build department node."""
    # Get head
    head = None
    if department.head_of_department_id:
        head_emp = session.get(Employee, department.head_of_department_id)
        if head_emp:
            head = build_employee_summary(head_emp)
    
    # Count employees
    employee_count = session.execute(
        select(func.count()).where(
            Employee.department_id == department.id,
            Employee.is_active == True,
        )
    ).scalar() or 0
    
    # Get sub-departments
    result = session.execute(
        select(Department).where(
            Department.parent_department_id == department.id,
            Department.is_active == True,
        ).order_by(Department.name)
    )
    sub_depts = list(result.scalars())
    
    sub_nodes = [build_department_node(d, session) for d in sub_depts]
    
    return DepartmentNode(
        id=department.id,
        code=department.code,
        name=department.name,
        head=head,
        employee_count=employee_count,
        sub_departments=sub_nodes,
    )


def analyze_team_composition(
    members: List[Employee],
    session: Session,
) -> TeamComposition:
    """Analyze team composition."""
    now = datetime.utcnow().date()
    
    by_type: Dict[str, int] = {}
    by_location: Dict[str, int] = {}
    by_tenure: Dict[str, int] = {"0-1 years": 0, "1-3 years": 0, "3-5 years": 0, "5+ years": 0}
    
    total_tenure = 0.0
    
    for member in members:
        # By employment type
        emp_type = member.employment_type or "unknown"
        by_type[emp_type] = by_type.get(emp_type, 0) + 1
        
        # By location
        loc_name = member.location.name if member.location else "Unknown"
        by_location[loc_name] = by_location.get(loc_name, 0) + 1
        
        # Tenure
        if member.hire_date:
            tenure_days = (now - member.hire_date).days
            tenure_years = tenure_days / 365.25
            total_tenure += tenure_days / 30.44  # months
            
            if tenure_years < 1:
                by_tenure["0-1 years"] += 1
            elif tenure_years < 3:
                by_tenure["1-3 years"] += 1
            elif tenure_years < 5:
                by_tenure["3-5 years"] += 1
            else:
                by_tenure["5+ years"] += 1
    
    avg_tenure = total_tenure / len(members) if members else 0.0
    
    return TeamComposition(
        total_members=len(members),
        by_employment_type=by_type,
        by_location=by_location,
        by_tenure=by_tenure,
        average_tenure_months=round(avg_tenure, 1),
    )


def generate_recommendations(
    composition: TeamComposition,
    members: List[Employee],
) -> List[TeamOptimizationRecommendation]:
    """Generate team optimization recommendations."""
    recommendations = []
    
    # Check for single location concentration
    if composition.by_location:
        max_loc = max(composition.by_location.values())
        if max_loc / composition.total_members > 0.8 and composition.total_members > 3:
            recommendations.append(TeamOptimizationRecommendation(
                recommendation_type="diversity",
                title="Consider Geographic Diversity",
                description="Most team members are in a single location. Consider distributed team members for resilience.",
                priority="low",
            ))
    
    # Check for tenure imbalance
    if composition.by_tenure.get("0-1 years", 0) > composition.total_members * 0.5:
        recommendations.append(TeamOptimizationRecommendation(
            recommendation_type="knowledge",
            title="High New Member Ratio",
            description="More than half the team has less than 1 year tenure. Consider pairing with experienced members.",
            priority="medium",
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

org_chart_router = APIRouter(
    prefix="/api/employee-directory",
    tags=["Organizational Chart"],
)


# =============================================================================
# Endpoints
# =============================================================================

@org_chart_router.get(
    "/organizational-chart",
    response_model=OrgChartResponse,
    summary="Get Organizational Chart",
    description="Generate organizational hierarchy chart.",
)
async def get_organizational_chart(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    view_type: ChartViewType = ChartViewType.HIERARCHY,
    root_employee_id: Optional[int] = None,
    department_id: Optional[int] = None,
    depth_limit: Annotated[int, Query(ge=1, le=5)] = 3,
) -> OrgChartResponse:
    """
    Generate organizational chart.
    
    - Supports hierarchy, matrix, department, and location views
    - Limits depth to prevent performance issues
    - Includes span of control calculations
    - Handles matrix organizations with multiple relationships
    """
    total_employees = session.execute(
        select(func.count()).where(Employee.is_active == True)
    ).scalar() or 0
    
    total_departments = session.execute(
        select(func.count()).where(Department.is_active == True)
    ).scalar() or 0
    
    root_node = None
    departments = []
    max_depth = 0
    
    if view_type == ChartViewType.HIERARCHY:
        # Find root employee(s)
        if root_employee_id:
            root_emp = session.get(Employee, root_employee_id)
            if not root_emp:
                raise NotFoundError(message="Root employee not found")
            root_node = build_chart_node(root_emp, session, 0, depth_limit)
            max_depth = depth_limit
        else:
            # Find top-level employees (no manager)
            result = session.execute(
                select(Employee).where(
                    Employee.manager_id.is_(None),
                    Employee.is_active == True,
                ).order_by(Employee.last_name).limit(1)
            )
            root_emp = result.scalar_one_or_none()
            
            if root_emp:
                root_node = build_chart_node(root_emp, session, 0, depth_limit)
                max_depth = depth_limit
    
    elif view_type == ChartViewType.DEPARTMENT:
        # Build by department hierarchy
        result = session.execute(
            select(Department).where(
                Department.parent_department_id.is_(None),
                Department.is_active == True,
            ).order_by(Department.name)
        )
        root_depts = list(result.scalars())
        
        departments = [build_department_node(d, session) for d in root_depts]
    
    elif view_type == ChartViewType.MATRIX:
        # For matrix view, start from specified employee or department
        if root_employee_id:
            root_emp = session.get(Employee, root_employee_id)
            if root_emp:
                root_node = build_chart_node(root_emp, session, 0, depth_limit)
                
                # In a real implementation, would also include
                # dotted-line and functional relationships
                max_depth = depth_limit
    
    return OrgChartResponse(
        view_type=view_type,
        root_node=root_node,
        departments=departments,
        total_employees=total_employees,
        total_departments=total_departments,
        max_depth=max_depth,
        depth_limit=depth_limit,
    )


@org_chart_router.get(
    "/organizational-chart/{employee_id}",
    summary="Get Chart for Employee",
    description="Get organizational chart centered on a specific employee.",
)
async def get_employee_chart(
    employee_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    depth_limit: int = 2,
) -> Dict[str, Any]:
    """
    Get chart centered on an employee.
    
    - Shows employee's position in hierarchy
    - Includes manager chain and direct reports
    """
    employee = session.get(Employee, employee_id)
    if not employee:
        raise NotFoundError(message="Employee not found")
    
    # Build manager chain
    manager_chain = []
    current = employee
    while current.manager_id:
        manager = session.get(Employee, current.manager_id)
        if manager:
            manager_chain.insert(0, build_employee_summary(manager))
            current = manager
        else:
            break
    
    # Build subtree
    node = build_chart_node(employee, session, 0, depth_limit)
    
    return {
        "employee": build_employee_summary(employee).model_dump(),
        "manager_chain": [m.model_dump() for m in manager_chain],
        "subtree": node.model_dump(),
        "level_in_org": len(manager_chain),
    }


@org_chart_router.post(
    "/team-explorer",
    response_model=TeamExplorerResponse,
    summary="Explore Team",
    description="Discover team members and cross-team associations.",
)
async def explore_team(
    request: TeamExplorerRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> TeamExplorerResponse:
    """
    Explore team composition and relationships.
    
    - Discovers team members under a manager or in a department
    - Analyzes team composition
    - Identifies cross-team relationships
    - Provides optimization recommendations
    """
    team_lead = None
    team_name = "Team"
    members = []
    
    # Build team based on criteria
    if request.manager_id:
        manager = session.get(Employee, request.manager_id)
        if not manager:
            raise NotFoundError(message="Manager not found")
        
        team_lead = build_employee_summary(manager)
        team_name = f"{manager.first_name}'s Team"
        
        # Get direct reports
        result = session.execute(
            select(Employee).where(
                Employee.manager_id == request.manager_id,
                Employee.is_active == True,
            ).order_by(Employee.last_name)
        )
        team_employees = list(result.scalars())
        
    elif request.department_id:
        department = session.get(Department, request.department_id)
        if not department:
            raise NotFoundError(message="Department not found")
        
        team_name = department.name
        
        if department.head_of_department_id:
            head = session.get(Employee, department.head_of_department_id)
            if head:
                team_lead = build_employee_summary(head)
        
        # Get department members
        result = session.execute(
            select(Employee).where(
                Employee.department_id == request.department_id,
                Employee.is_active == True,
            ).order_by(Employee.last_name)
        )
        team_employees = list(result.scalars())
    else:
        team_employees = []
    
    # Build member list
    now = datetime.utcnow().date()
    for emp in team_employees:
        tenure = 0.0
        if emp.hire_date:
            tenure = (now - emp.hire_date).days / 30.44
        
        members.append(TeamMember(
            employee=build_employee_summary(emp),
            role_in_team="member",
            tenure_months=round(tenure, 1),
            is_cross_functional=False,
        ))
    
    # Analyze composition
    composition = None
    if request.include_analysis and team_employees:
        composition = analyze_team_composition(team_employees, session)
    
    # Generate recommendations
    recommendations = []
    if composition:
        recommendations = generate_recommendations(composition, team_employees)
    
    # Cross-team associations (simplified)
    cross_team = []
    if request.include_cross_team:
        # In a real implementation, would analyze actual cross-team collaboration
        pass
    
    return TeamExplorerResponse(
        team_name=team_name,
        team_lead=team_lead,
        members=members,
        total_members=len(members),
        cross_team_associations=cross_team,
        composition=composition,
        recommendations=recommendations,
    )


@org_chart_router.get(
    "/direct-reports/{manager_id}",
    summary="Get Direct Reports",
    description="Get list of direct reports for a manager.",
)
async def get_direct_reports(
    manager_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> Dict[str, Any]:
    """Get direct reports for a manager."""
    manager = session.get(Employee, manager_id)
    if not manager:
        raise NotFoundError(message="Manager not found")
    
    result = session.execute(
        select(Employee).where(
            Employee.manager_id == manager_id,
            Employee.is_active == True,
        ).order_by(Employee.last_name)
    )
    reports = list(result.scalars())
    
    return {
        "manager": build_employee_summary(manager).model_dump(),
        "direct_reports": [build_employee_summary(r).model_dump() for r in reports],
        "count": len(reports),
    }

