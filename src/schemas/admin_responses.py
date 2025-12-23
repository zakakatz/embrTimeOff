"""Pydantic models for administrative API responses.

Provides structured response models for organizational structure management
including departments, locations, and organizational changes.
"""

from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, computed_field


# =============================================================================
# Enums
# =============================================================================

class DepartmentType(str, Enum):
    """Type of department."""
    
    FUNCTIONAL = "functional"       # Standard functional department
    DIVISIONAL = "divisional"       # Business division
    MATRIX = "matrix"               # Matrix organization unit
    PROJECT = "project"             # Project-based team
    SUPPORT = "support"             # Support/shared services
    EXECUTIVE = "executive"         # Executive office


class LocationType(str, Enum):
    """Type of location."""
    
    OFFICE = "office"               # Standard office
    HEADQUARTERS = "headquarters"    # Main headquarters
    BRANCH = "branch"               # Branch office
    WAREHOUSE = "warehouse"         # Warehouse/distribution
    RETAIL = "retail"               # Retail location
    REMOTE = "remote"               # Remote/virtual
    DATA_CENTER = "data_center"     # Data center
    FACTORY = "factory"             # Manufacturing facility


class ChangeType(str, Enum):
    """Type of organizational change."""
    
    RESTRUCTURE = "restructure"             # Department restructuring
    MERGER = "merger"                       # Department merger
    SPLIT = "split"                         # Department split
    CREATION = "creation"                   # New department/location
    CLOSURE = "closure"                     # Department/location closure
    RELOCATION = "relocation"               # Location change
    LEADERSHIP_CHANGE = "leadership_change" # Head of department change
    POLICY_CHANGE = "policy_change"         # Policy modification
    BUDGET_CHANGE = "budget_change"         # Budget modification


class ChangeStatus(str, Enum):
    """Status of organizational change."""
    
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ROLLED_BACK = "rolled_back"


# =============================================================================
# Supporting Models
# =============================================================================

class EmployeeBasicResponse(BaseModel):
    """Basic employee information for nested responses."""
    
    id: int = Field(..., description="Employee primary key ID")
    employee_id: str = Field(..., description="Employee identifier (e.g., EMP001)")
    full_name: str = Field(..., description="Full display name")
    first_name: str = Field(..., description="First name")
    last_name: str = Field(..., description="Last name")
    job_title: Optional[str] = Field(None, description="Current job title")
    email: Optional[str] = Field(None, description="Work email")
    department_name: Optional[str] = Field(None, description="Department name")
    is_active: bool = Field(default=True, description="Active status")
    
    class Config:
        from_attributes = True


class DepartmentBasicResponse(BaseModel):
    """Basic department information for nested responses."""
    
    id: int = Field(..., description="Department ID")
    code: str = Field(..., description="Department code")
    name: str = Field(..., description="Department name")
    department_type: Optional[str] = Field(None, description="Type of department")
    is_active: bool = Field(default=True, description="Active status")
    
    class Config:
        from_attributes = True


class LocationBasicResponse(BaseModel):
    """Basic location information for nested responses."""
    
    id: int = Field(..., description="Location ID")
    code: str = Field(..., description="Location code")
    name: str = Field(..., description="Location name")
    city: Optional[str] = Field(None, description="City")
    country: Optional[str] = Field(None, description="Country")
    
    class Config:
        from_attributes = True


class AddressInfo(BaseModel):
    """Address information for locations."""
    
    street_address: Optional[str] = Field(None, description="Street address line 1")
    street_address_2: Optional[str] = Field(None, description="Street address line 2")
    city: Optional[str] = Field(None, description="City")
    state_province: Optional[str] = Field(None, description="State or province")
    postal_code: Optional[str] = Field(None, description="Postal/ZIP code")
    country: Optional[str] = Field(None, description="Country")
    
    # Geographic coordinates
    latitude: Optional[float] = Field(None, description="Latitude coordinate")
    longitude: Optional[float] = Field(None, description="Longitude coordinate")
    
    class Config:
        from_attributes = True
    
    @computed_field
    @property
    def formatted_address(self) -> str:
        """Get formatted address string."""
        parts = []
        if self.street_address:
            parts.append(self.street_address)
        if self.street_address_2:
            parts.append(self.street_address_2)
        
        city_state = []
        if self.city:
            city_state.append(self.city)
        if self.state_province:
            city_state.append(self.state_province)
        if self.postal_code:
            city_state.append(self.postal_code)
        
        if city_state:
            parts.append(", ".join(city_state))
        
        if self.country:
            parts.append(self.country)
        
        return ", ".join(parts) if parts else ""


class HolidayCalendarSummary(BaseModel):
    """Summary of holiday calendar."""
    
    id: int = Field(..., description="Calendar ID")
    name: str = Field(..., description="Calendar name")
    year: int = Field(..., description="Calendar year")
    total_holidays: int = Field(default=0, description="Total number of holidays")
    country: Optional[str] = Field(None, description="Country/region")
    
    class Config:
        from_attributes = True


class OperatingHoursInfo(BaseModel):
    """Operating hours information."""
    
    monday: Optional[str] = Field(None, description="Monday hours")
    tuesday: Optional[str] = Field(None, description="Tuesday hours")
    wednesday: Optional[str] = Field(None, description="Wednesday hours")
    thursday: Optional[str] = Field(None, description="Thursday hours")
    friday: Optional[str] = Field(None, description="Friday hours")
    saturday: Optional[str] = Field(None, description="Saturday hours")
    sunday: Optional[str] = Field(None, description="Sunday hours")
    timezone: Optional[str] = Field(None, description="Timezone for hours")
    notes: Optional[str] = Field(None, description="Additional notes")


# =============================================================================
# Main Administrative Response Models
# =============================================================================

class DepartmentAdminResponse(BaseModel):
    """
    Comprehensive department response for administrative operations.
    
    Includes full department details, hierarchy information, and aggregated metrics.
    """
    
    # Identifiers
    id: int = Field(..., description="Department primary key ID")
    uuid: Optional[str] = Field(None, description="Department UUID for external reference")
    
    # Basic info
    name: str = Field(..., description="Department name")
    code: str = Field(..., description="Department code")
    description: Optional[str] = Field(None, description="Department description")
    
    # Hierarchy
    parent_department: Optional[DepartmentBasicResponse] = Field(
        None,
        description="Parent department in hierarchy",
    )
    
    # Leadership
    head_of_department: Optional[EmployeeBasicResponse] = Field(
        None,
        description="Head of department",
    )
    
    # Financial
    cost_center: Optional[str] = Field(None, description="Cost center code")
    budget_code: Optional[str] = Field(None, description="Budget code")
    
    # Organizational
    organizational_level: int = Field(
        default=1,
        description="Level in organizational hierarchy (1 = top level)",
    )
    department_type: DepartmentType = Field(
        default=DepartmentType.FUNCTIONAL,
        description="Type of department",
    )
    
    # Aggregated counts
    employee_count: int = Field(
        default=0,
        description="Number of employees in department",
    )
    subdepartment_count: int = Field(
        default=0,
        description="Number of sub-departments",
    )
    
    # Child departments (for tree view)
    subdepartments: List[DepartmentBasicResponse] = Field(
        default_factory=list,
        description="Direct sub-departments",
    )
    
    # Status
    is_active: bool = Field(default=True, description="Whether department is active")
    
    # Effective dates
    effective_date: Optional[date] = Field(None, description="When department became effective")
    end_date: Optional[date] = Field(None, description="When department was discontinued")
    
    # Timestamps
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    
    # Audit
    created_by: Optional[EmployeeBasicResponse] = Field(None, description="Who created this department")
    last_modified_by: Optional[EmployeeBasicResponse] = Field(None, description="Who last modified")
    
    class Config:
        from_attributes = True


class LocationAdminResponse(BaseModel):
    """
    Comprehensive location response for administrative operations.
    
    Includes full location details, facility information, and operational data.
    """
    
    # Identifiers
    id: int = Field(..., description="Location primary key ID")
    uuid: Optional[str] = Field(None, description="Location UUID for external reference")
    
    # Basic info
    name: str = Field(..., description="Location name")
    code: str = Field(..., description="Location code")
    description: Optional[str] = Field(None, description="Location description")
    
    # Address
    address: AddressInfo = Field(..., description="Full address information")
    
    # Type and timezone
    location_type: LocationType = Field(
        default=LocationType.OFFICE,
        description="Type of location",
    )
    timezone: Optional[str] = Field(None, description="Location timezone (IANA format)")
    
    # Capacity
    capacity: Optional[int] = Field(None, description="Maximum capacity")
    current_occupancy: Optional[int] = Field(None, description="Current occupancy")
    
    # Management
    facility_manager: Optional[EmployeeBasicResponse] = Field(
        None,
        description="Facility manager",
    )
    
    # Holiday calendar
    holiday_calendar: Optional[HolidayCalendarSummary] = Field(
        None,
        description="Associated holiday calendar",
    )
    
    # Employee count
    employee_count: int = Field(
        default=0,
        description="Number of employees at this location",
    )
    department_count: int = Field(
        default=0,
        description="Number of departments at this location",
    )
    
    # Operating hours
    operating_hours: Optional[OperatingHoursInfo] = Field(
        None,
        description="Operating hours",
    )
    
    # Regulatory
    regulatory_jurisdiction: Optional[str] = Field(None, description="Regulatory jurisdiction")
    tax_jurisdiction: Optional[str] = Field(None, description="Tax jurisdiction")
    
    # Contact
    phone_number: Optional[str] = Field(None, description="Main phone number")
    emergency_contact: Optional[str] = Field(None, description="Emergency contact info")
    
    # Amenities
    amenities: List[str] = Field(default_factory=list, description="Available amenities")
    
    # Status
    is_active: bool = Field(default=True, description="Whether location is active")
    
    # Timestamps
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    
    class Config:
        from_attributes = True


class OrganizationalChangeResponse(BaseModel):
    """
    Response model for organizational changes.
    
    Tracks changes to organizational structure including restructuring,
    leadership changes, and policy modifications.
    """
    
    # Identifiers
    id: int = Field(..., description="Change record ID")
    uuid: Optional[str] = Field(None, description="Change UUID for external reference")
    
    # Change details
    change_type: ChangeType = Field(..., description="Type of organizational change")
    entity_type: str = Field(
        ...,
        description="Type of entity being changed (department, location, etc.)",
    )
    entity_id: int = Field(..., description="ID of the entity being changed")
    entity_name: Optional[str] = Field(None, description="Name of the entity being changed")
    
    # Summary
    change_summary: str = Field(..., description="Brief summary of the change")
    change_description: Optional[str] = Field(None, description="Detailed description")
    
    # Requestor and approver
    requested_by: EmployeeBasicResponse = Field(
        ...,
        description="Who requested the change",
    )
    approved_by: Optional[EmployeeBasicResponse] = Field(
        None,
        description="Who approved the change",
    )
    
    # Status
    change_status: ChangeStatus = Field(..., description="Current status of the change")
    
    # Dates
    requested_date: datetime = Field(..., description="When change was requested")
    effective_date: Optional[date] = Field(None, description="When change takes effect")
    implementation_date: Optional[date] = Field(None, description="When change was implemented")
    completion_date: Optional[datetime] = Field(None, description="When change was completed")
    
    # Impact
    affected_employees_count: int = Field(
        default=0,
        description="Number of employees affected",
    )
    affected_departments: List[DepartmentBasicResponse] = Field(
        default_factory=list,
        description="Departments affected by the change",
    )
    affected_locations: List[LocationBasicResponse] = Field(
        default_factory=list,
        description="Locations affected by the change",
    )
    
    # Impact assessment
    impact_assessment: Dict[str, Any] = Field(
        default_factory=dict,
        description="Detailed impact assessment",
    )
    
    # Previous and new state
    previous_state: Optional[Dict[str, Any]] = Field(
        None,
        description="State before the change",
    )
    new_state: Optional[Dict[str, Any]] = Field(
        None,
        description="State after the change",
    )
    
    # Reason and notes
    reason: Optional[str] = Field(None, description="Reason for the change")
    rejection_reason: Optional[str] = Field(None, description="Reason for rejection if rejected")
    notes: Optional[str] = Field(None, description="Additional notes")
    
    # Rollback info
    is_rollbackable: bool = Field(default=True, description="Whether change can be rolled back")
    rollback_deadline: Optional[datetime] = Field(None, description="Deadline for rollback")
    
    # Timestamps
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    
    class Config:
        from_attributes = True


# =============================================================================
# List Response Models
# =============================================================================

class DepartmentListResponse(BaseModel):
    """Paginated list of departments."""
    
    departments: List[DepartmentAdminResponse] = Field(default_factory=list)
    total: int = Field(default=0, description="Total number of departments")
    page: int = Field(default=1)
    page_size: int = Field(default=20)
    total_pages: int = Field(default=0)


class LocationListResponse(BaseModel):
    """Paginated list of locations."""
    
    locations: List[LocationAdminResponse] = Field(default_factory=list)
    total: int = Field(default=0, description="Total number of locations")
    page: int = Field(default=1)
    page_size: int = Field(default=20)
    total_pages: int = Field(default=0)


class OrganizationalChangeListResponse(BaseModel):
    """Paginated list of organizational changes."""
    
    changes: List[OrganizationalChangeResponse] = Field(default_factory=list)
    total: int = Field(default=0, description="Total number of changes")
    page: int = Field(default=1)
    page_size: int = Field(default=20)
    total_pages: int = Field(default=0)
    
    # Summary counts
    pending_count: int = Field(default=0, description="Changes pending approval")
    in_progress_count: int = Field(default=0, description="Changes in progress")
    completed_count: int = Field(default=0, description="Completed changes")

