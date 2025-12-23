"""Pydantic models for Employee Directory API responses.

This module provides structured response models for:
- Directory employee listings
- Organizational chart hierarchy
- Team structure visualization
"""

from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional, ForwardRef
from uuid import UUID

from pydantic import BaseModel, Field, computed_field


# =============================================================================
# Enums
# =============================================================================

class EmploymentType(str, Enum):
    """Employment type enumeration."""
    
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACTOR = "contractor"
    INTERN = "intern"
    TEMPORARY = "temporary"


class EmploymentStatus(str, Enum):
    """Employment status enumeration."""
    
    ACTIVE = "active"
    ON_LEAVE = "on_leave"
    TERMINATED = "terminated"
    SUSPENDED = "suspended"


# =============================================================================
# Nested Models
# =============================================================================

class DepartmentInfo(BaseModel):
    """Department information for directory display."""
    
    id: int = Field(..., description="Department ID")
    code: str = Field(..., description="Department code")
    name: str = Field(..., description="Department name")
    
    class Config:
        from_attributes = True


class LocationInfo(BaseModel):
    """Location information for directory display."""
    
    id: int = Field(..., description="Location ID")
    code: str = Field(..., description="Location code")
    name: str = Field(..., description="Location name")
    city: Optional[str] = Field(None, description="City")
    country: Optional[str] = Field(None, description="Country")
    timezone: Optional[str] = Field(None, description="Timezone")
    
    class Config:
        from_attributes = True


class ManagerInfo(BaseModel):
    """Manager information for directory display."""
    
    id: int = Field(..., description="Manager employee ID (primary key)")
    employee_id: str = Field(..., description="Manager employee identifier")
    full_name: str = Field(..., description="Manager full name")
    job_title: Optional[str] = Field(None, description="Manager job title")
    email: Optional[str] = Field(None, description="Manager email")
    
    class Config:
        from_attributes = True


class ContactInfo(BaseModel):
    """Contact information for directory display."""
    
    email: str = Field(..., description="Work email address")
    phone_number: Optional[str] = Field(None, description="Work phone number")
    mobile_number: Optional[str] = Field(None, description="Mobile phone number")
    
    class Config:
        from_attributes = True


class ReportingRelationship(BaseModel):
    """Represents a reporting relationship in the organizational structure."""
    
    relationship_type: str = Field(
        ..., 
        description="Type of relationship (direct, dotted_line, functional)"
    )
    employee_id: int = Field(..., description="Related employee ID")
    employee_name: str = Field(..., description="Related employee name")
    job_title: Optional[str] = Field(None, description="Related employee job title")
    
    class Config:
        from_attributes = True


# =============================================================================
# Directory Employee Response
# =============================================================================

class DirectoryEmployeeResponse(BaseModel):
    """
    Response model for a single employee in the directory.
    
    Contains all fields needed for directory display including
    personal info, job details, organizational placement, and contact info.
    """
    
    # Identifiers
    id: int = Field(..., description="Employee primary key ID")
    employee_id: str = Field(..., description="Employee identifier (e.g., EMP001)")
    
    # Name information
    full_name: str = Field(..., description="Full display name")
    first_name: str = Field(..., description="First name")
    last_name: str = Field(..., description="Last name")
    preferred_name: Optional[str] = Field(None, description="Preferred name if set")
    display_first_name: Optional[str] = Field(
        None, 
        description="Preferred name or first name for display"
    )
    
    # Job information
    job_title: Optional[str] = Field(None, description="Current job title")
    employment_type: Optional[str] = Field(None, description="Employment type")
    employment_status: Optional[str] = Field(None, description="Employment status")
    
    # Organizational placement
    department: Optional[DepartmentInfo] = Field(None, description="Department details")
    location: Optional[LocationInfo] = Field(None, description="Location details")
    manager: Optional[ManagerInfo] = Field(None, description="Manager details")
    
    # Contact information
    contact_info: ContactInfo = Field(..., description="Contact information")
    
    # Organizational metrics
    organizational_level: int = Field(
        default=0,
        description="Level in organizational hierarchy (0 = CEO/top level)"
    )
    direct_reports_count: int = Field(
        default=0,
        description="Number of direct reports"
    )
    
    # Employment dates
    hire_date: date = Field(..., description="Date of hire")
    
    # Flags
    is_active: bool = Field(default=True, description="Whether employee is active")
    is_manager: bool = Field(default=False, description="Whether employee has direct reports")
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "employee_id": "EMP001",
                "full_name": "John Smith",
                "first_name": "John",
                "last_name": "Smith",
                "preferred_name": None,
                "job_title": "Senior Software Engineer",
                "employment_type": "full_time",
                "department": {
                    "id": 1,
                    "code": "ENG",
                    "name": "Engineering"
                },
                "location": {
                    "id": 1,
                    "code": "HQ",
                    "name": "Headquarters",
                    "city": "San Francisco",
                    "country": "USA"
                },
                "manager": {
                    "id": 2,
                    "employee_id": "EMP002",
                    "full_name": "Jane Doe",
                    "job_title": "Engineering Manager"
                },
                "contact_info": {
                    "email": "john.smith@company.com",
                    "phone_number": "+1-555-0100"
                },
                "organizational_level": 3,
                "direct_reports_count": 2,
                "hire_date": "2020-03-15",
                "is_active": True,
                "is_manager": True
            }
        }


# =============================================================================
# Organizational Chart Node
# =============================================================================

class OrganizationalChartNode(BaseModel):
    """
    Hierarchical node for organizational chart display.
    
    Supports recursive structure with direct_reports containing
    nested OrganizationalChartNode instances.
    """
    
    # Employee identifiers
    id: int = Field(..., description="Employee primary key ID")
    employee_id: str = Field(..., description="Employee identifier")
    
    # Display information
    full_name: str = Field(..., description="Full display name")
    job_title: Optional[str] = Field(None, description="Job title")
    email: Optional[str] = Field(None, description="Work email")
    
    # Department and location
    department: Optional[DepartmentInfo] = Field(None, description="Department")
    location: Optional[LocationInfo] = Field(None, description="Location")
    
    # Hierarchy information
    level: int = Field(
        default=0,
        description="Level in the organizational hierarchy (0 = root/CEO)"
    )
    span_of_control: int = Field(
        default=0,
        description="Total number of employees reporting up through this node"
    )
    
    # Flags
    is_department_head: bool = Field(
        default=False,
        description="Whether this employee is head of their department"
    )
    is_expanded: bool = Field(
        default=True,
        description="Whether this node should be expanded in the UI"
    )
    
    # Reporting relationships (for complex structures)
    reporting_relationships: List[ReportingRelationship] = Field(
        default_factory=list,
        description="Additional reporting relationships (dotted line, functional)"
    )
    
    # Direct reports (recursive)
    direct_reports: List["OrganizationalChartNode"] = Field(
        default_factory=list,
        description="List of direct reports as nested nodes"
    )
    
    # Metadata
    direct_reports_count: int = Field(
        default=0,
        description="Number of direct reports"
    )
    has_more_reports: bool = Field(
        default=False,
        description="Whether there are more reports not included (pagination)"
    )
    
    class Config:
        from_attributes = True


# Enable forward reference resolution for recursive model
OrganizationalChartNode.model_rebuild()


# =============================================================================
# Team Structure Response
# =============================================================================

class TeamMember(BaseModel):
    """Simplified team member for team structure display."""
    
    id: int = Field(..., description="Employee primary key ID")
    employee_id: str = Field(..., description="Employee identifier")
    full_name: str = Field(..., description="Full display name")
    job_title: Optional[str] = Field(None, description="Job title")
    email: Optional[str] = Field(None, description="Work email")
    hire_date: date = Field(..., description="Hire date")
    is_active: bool = Field(default=True, description="Active status")
    
    class Config:
        from_attributes = True


class TeamStructureResponse(BaseModel):
    """
    Response model for team structure visualization.
    
    Represents a team with its lead, members, and organizational context.
    """
    
    # Team lead
    team_lead: DirectoryEmployeeResponse = Field(
        ...,
        description="Team lead/manager information"
    )
    
    # Team members
    team_members: List[TeamMember] = Field(
        default_factory=list,
        description="List of team members"
    )
    
    # Organizational context
    department: Optional[DepartmentInfo] = Field(
        None,
        description="Department this team belongs to"
    )
    location: Optional[LocationInfo] = Field(
        None,
        description="Primary location of the team"
    )
    
    # Team metrics
    team_size: int = Field(
        default=0,
        description="Total number of team members (excluding lead)"
    )
    organizational_depth: int = Field(
        default=1,
        description="Depth of organizational hierarchy within the team"
    )
    
    # Additional metadata
    active_members_count: int = Field(
        default=0,
        description="Number of active team members"
    )
    average_tenure_months: Optional[float] = Field(
        None,
        description="Average tenure of team members in months"
    )
    
    class Config:
        from_attributes = True


# =============================================================================
# Directory List Response (Paginated)
# =============================================================================

class DirectoryListResponse(BaseModel):
    """Paginated response for directory employee listings."""
    
    employees: List[DirectoryEmployeeResponse] = Field(
        default_factory=list,
        description="List of employees"
    )
    total: int = Field(default=0, description="Total number of employees matching filters")
    page: int = Field(default=1, description="Current page number")
    page_size: int = Field(default=20, description="Number of employees per page")
    total_pages: int = Field(default=0, description="Total number of pages")
    has_next: bool = Field(default=False, description="Whether there is a next page")
    has_previous: bool = Field(default=False, description="Whether there is a previous page")
    
    # Filters applied
    filters_applied: Dict[str, Any] = Field(
        default_factory=dict,
        description="Filters that were applied to this listing"
    )
    
    class Config:
        from_attributes = True


# =============================================================================
# Organizational Chart Response
# =============================================================================

class OrganizationalChartResponse(BaseModel):
    """Response for organizational chart data."""
    
    root_node: OrganizationalChartNode = Field(
        ...,
        description="Root node of the organizational chart"
    )
    total_employees: int = Field(
        default=0,
        description="Total number of employees in the chart"
    )
    max_depth: int = Field(
        default=0,
        description="Maximum depth of the hierarchy"
    )
    generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When this chart data was generated"
    )
    
    class Config:
        from_attributes = True


# =============================================================================
# Search Response
# =============================================================================

class DirectorySearchResult(BaseModel):
    """Search result with relevance scoring."""
    
    employee: DirectoryEmployeeResponse = Field(..., description="Employee data")
    relevance_score: float = Field(
        default=1.0,
        description="Relevance score for search ranking (0-1)"
    )
    matched_fields: List[str] = Field(
        default_factory=list,
        description="Fields that matched the search query"
    )
    
    class Config:
        from_attributes = True


class DirectorySearchResponse(BaseModel):
    """Paginated search results for directory."""
    
    results: List[DirectorySearchResult] = Field(
        default_factory=list,
        description="Search results"
    )
    query: str = Field(..., description="Search query that was executed")
    total: int = Field(default=0, description="Total matching results")
    page: int = Field(default=1, description="Current page")
    page_size: int = Field(default=20, description="Results per page")
    search_time_ms: Optional[float] = Field(
        None,
        description="Time taken for search in milliseconds"
    )
    
    class Config:
        from_attributes = True

