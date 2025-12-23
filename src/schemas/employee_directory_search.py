"""Pydantic models for Employee Directory Search and Filtering.

This module provides comprehensive search request and response models
for advanced employee directory filtering, faceted search, and pagination.
"""

from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


# =============================================================================
# Enums
# =============================================================================

class SortField(str, Enum):
    """Available fields for sorting search results."""
    
    RELEVANCE = "relevance"
    LAST_NAME = "last_name"
    FIRST_NAME = "first_name"
    HIRE_DATE = "hire_date"
    DEPARTMENT = "department"
    LOCATION = "location"
    JOB_TITLE = "job_title"


class SortOrder(str, Enum):
    """Sort order direction."""
    
    ASC = "asc"
    DESC = "desc"


# =============================================================================
# Supporting Models
# =============================================================================

class DateRange(BaseModel):
    """Date range for filtering queries."""
    
    start_date: Optional[date] = Field(
        None,
        description="Start date of the range (inclusive)"
    )
    end_date: Optional[date] = Field(
        None,
        description="End date of the range (inclusive)"
    )
    
    @model_validator(mode='after')
    def validate_date_range(self) -> 'DateRange':
        if self.start_date and self.end_date:
            if self.start_date > self.end_date:
                raise ValueError("start_date must be before or equal to end_date")
        return self


class PaginationInfo(BaseModel):
    """Pagination information for search responses."""
    
    page: int = Field(default=1, ge=1, description="Current page number")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")
    total_pages: int = Field(default=0, ge=0, description="Total number of pages")
    total_items: int = Field(default=0, ge=0, description="Total number of items")
    has_next: bool = Field(default=False, description="Whether there is a next page")
    has_previous: bool = Field(default=False, description="Whether there is a previous page")
    
    @classmethod
    def from_query(
        cls,
        page: int,
        page_size: int,
        total_items: int,
    ) -> 'PaginationInfo':
        """Create pagination info from query parameters and total count."""
        total_pages = (total_items + page_size - 1) // page_size if total_items > 0 else 0
        return cls(
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            total_items=total_items,
            has_next=page < total_pages,
            has_previous=page > 1,
        )


class FacetValue(BaseModel):
    """A single value within a facet."""
    
    value: str = Field(..., description="Facet value")
    label: str = Field(..., description="Display label for the value")
    count: int = Field(default=0, ge=0, description="Number of results with this value")
    selected: bool = Field(default=False, description="Whether this value is currently selected")


class SearchFacet(BaseModel):
    """A facet for filtering search results."""
    
    field: str = Field(..., description="Field name this facet applies to")
    label: str = Field(..., description="Display label for the facet")
    values: List[FacetValue] = Field(
        default_factory=list,
        description="Available values for this facet"
    )
    is_multi_select: bool = Field(
        default=True,
        description="Whether multiple values can be selected"
    )


class SearchFacets(BaseModel):
    """Collection of facets for filtering."""
    
    departments: SearchFacet = Field(
        default_factory=lambda: SearchFacet(
            field="department_id",
            label="Department",
            values=[],
        ),
        description="Department facet"
    )
    locations: SearchFacet = Field(
        default_factory=lambda: SearchFacet(
            field="location_id",
            label="Location",
            values=[],
        ),
        description="Location facet"
    )
    employment_types: SearchFacet = Field(
        default_factory=lambda: SearchFacet(
            field="employment_type",
            label="Employment Type",
            values=[],
        ),
        description="Employment type facet"
    )
    employment_statuses: SearchFacet = Field(
        default_factory=lambda: SearchFacet(
            field="employment_status",
            label="Status",
            values=[],
        ),
        description="Employment status facet"
    )
    organizational_levels: SearchFacet = Field(
        default_factory=lambda: SearchFacet(
            field="organizational_level",
            label="Organizational Level",
            values=[],
            is_multi_select=False,
        ),
        description="Organizational level facet"
    )


class SearchSuggestion(BaseModel):
    """A search suggestion for autocomplete."""
    
    text: str = Field(..., description="Suggested search text")
    type: str = Field(..., description="Type of suggestion (name, job_title, department, etc.)")
    employee_id: Optional[int] = Field(
        None,
        description="Employee ID if suggestion is for a specific employee"
    )
    relevance_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Relevance score for ranking suggestions"
    )


# =============================================================================
# Search Request Model
# =============================================================================

class DirectorySearchRequest(BaseModel):
    """
    Request model for directory search operations.
    
    Supports complex filtering combinations including text search,
    department/location filters, date ranges, and organizational criteria.
    """
    
    # Text Search
    query: Optional[str] = Field(
        None,
        max_length=100,
        description="Search query text (searches name, email, job title)"
    )
    
    # Organizational Filters
    department_ids: Optional[List[int]] = Field(
        None,
        max_length=50,
        description="Filter by department IDs"
    )
    location_ids: Optional[List[int]] = Field(
        None,
        max_length=50,
        description="Filter by location IDs"
    )
    
    # Employment Filters
    employment_types: Optional[List[str]] = Field(
        None,
        max_length=10,
        description="Filter by employment types (full_time, part_time, contractor, etc.)"
    )
    employment_statuses: Optional[List[str]] = Field(
        None,
        max_length=10,
        description="Filter by employment statuses (active, on_leave, terminated, etc.)"
    )
    
    # Job-Related Filters
    job_title_keywords: Optional[List[str]] = Field(
        None,
        max_length=20,
        description="Keywords to match against job titles"
    )
    
    # Hierarchy Filters
    manager_id: Optional[int] = Field(
        None,
        description="Filter by manager (returns direct reports)"
    )
    organizational_level: Optional[int] = Field(
        None,
        ge=0,
        le=20,
        description="Filter by organizational level (0 = CEO level)"
    )
    include_sub_departments: bool = Field(
        default=False,
        description="Include employees from sub-departments when filtering by department"
    )
    
    # Date Filters
    hire_date_range: Optional[DateRange] = Field(
        None,
        description="Filter by hire date range"
    )
    
    # Status Filters
    include_inactive: bool = Field(
        default=False,
        description="Include inactive employees in results"
    )
    
    # Pagination
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Number of results per page"
    )
    
    # Sorting
    sort_by: SortField = Field(
        default=SortField.RELEVANCE,
        description="Field to sort results by"
    )
    sort_order: SortOrder = Field(
        default=SortOrder.ASC,
        description="Sort order direction"
    )
    
    # Response Options
    include_facets: bool = Field(
        default=True,
        description="Include facets in response"
    )
    include_suggestions: bool = Field(
        default=False,
        description="Include search suggestions in response"
    )
    
    @field_validator('query')
    @classmethod
    def clean_query(cls, v: Optional[str]) -> Optional[str]:
        """Clean and normalize search query."""
        if v is not None:
            v = v.strip()
            if len(v) == 0:
                return None
        return v
    
    @field_validator('job_title_keywords')
    @classmethod
    def validate_keywords(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate and clean job title keywords."""
        if v is not None:
            # Remove empty strings and limit keyword length
            v = [kw.strip()[:50] for kw in v if kw.strip()]
            if len(v) == 0:
                return None
        return v
    
    def has_filters(self) -> bool:
        """Check if any filters are applied."""
        return any([
            self.query,
            self.department_ids,
            self.location_ids,
            self.employment_types,
            self.employment_statuses,
            self.job_title_keywords,
            self.manager_id is not None,
            self.organizational_level is not None,
            self.hire_date_range,
        ])
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "software engineer",
                "department_ids": [1, 2, 3],
                "location_ids": [1],
                "employment_types": ["full_time"],
                "include_inactive": False,
                "page": 1,
                "page_size": 20,
                "sort_by": "relevance",
                "include_facets": True
            }
        }


# =============================================================================
# Search Response Model
# =============================================================================

class DirectorySearchResultItem(BaseModel):
    """A single search result item."""
    
    id: int = Field(..., description="Employee primary key ID")
    employee_id: str = Field(..., description="Employee identifier")
    full_name: str = Field(..., description="Full display name")
    first_name: str = Field(..., description="First name")
    last_name: str = Field(..., description="Last name")
    preferred_name: Optional[str] = Field(None, description="Preferred name")
    email: str = Field(..., description="Work email")
    job_title: Optional[str] = Field(None, description="Job title")
    department_id: Optional[int] = Field(None, description="Department ID")
    department_name: Optional[str] = Field(None, description="Department name")
    location_id: Optional[int] = Field(None, description="Location ID")
    location_name: Optional[str] = Field(None, description="Location name")
    manager_id: Optional[int] = Field(None, description="Manager ID")
    manager_name: Optional[str] = Field(None, description="Manager name")
    employment_type: Optional[str] = Field(None, description="Employment type")
    employment_status: Optional[str] = Field(None, description="Employment status")
    hire_date: date = Field(..., description="Hire date")
    is_active: bool = Field(default=True, description="Active status")
    
    # Search metadata
    relevance_score: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Relevance score for search ranking"
    )
    matched_fields: Optional[List[str]] = Field(
        None,
        description="Fields that matched the search query"
    )
    
    class Config:
        from_attributes = True


class DirectorySearchResponse(BaseModel):
    """
    Response model for directory search operations.
    
    Contains search results, pagination info, facets for filtering,
    and search suggestions for autocomplete.
    """
    
    # Results
    results: List[DirectorySearchResultItem] = Field(
        default_factory=list,
        description="Search results"
    )
    
    # Counts
    total_count: int = Field(
        default=0,
        ge=0,
        description="Total number of employees (unfiltered)"
    )
    filtered_count: int = Field(
        default=0,
        ge=0,
        description="Number of employees matching filters"
    )
    
    # Pagination
    pagination: PaginationInfo = Field(
        default_factory=PaginationInfo,
        description="Pagination information"
    )
    
    # Facets
    facets: Optional[SearchFacets] = Field(
        None,
        description="Facets for filtering (if requested)"
    )
    
    # Suggestions
    search_suggestions: Optional[List[SearchSuggestion]] = Field(
        None,
        description="Search suggestions for autocomplete (if requested)"
    )
    
    # Query Info
    query_echo: Optional[str] = Field(
        None,
        description="Echo of the search query that was executed"
    )
    search_time_ms: Optional[float] = Field(
        None,
        ge=0,
        description="Time taken for search in milliseconds"
    )
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "results": [
                    {
                        "id": 1,
                        "employee_id": "EMP001",
                        "full_name": "John Smith",
                        "first_name": "John",
                        "last_name": "Smith",
                        "email": "john.smith@company.com",
                        "job_title": "Senior Software Engineer",
                        "department_name": "Engineering",
                        "location_name": "Headquarters",
                        "hire_date": "2020-03-15",
                        "relevance_score": 0.95
                    }
                ],
                "total_count": 500,
                "filtered_count": 25,
                "pagination": {
                    "page": 1,
                    "page_size": 20,
                    "total_pages": 2,
                    "total_items": 25,
                    "has_next": True,
                    "has_previous": False
                }
            }
        }


# =============================================================================
# Autocomplete Request/Response
# =============================================================================

class AutocompleteRequest(BaseModel):
    """Request model for search autocomplete."""
    
    query: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Partial search text for autocomplete"
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of suggestions to return"
    )
    include_departments: bool = Field(
        default=True,
        description="Include department name suggestions"
    )
    include_locations: bool = Field(
        default=True,
        description="Include location name suggestions"
    )
    include_job_titles: bool = Field(
        default=True,
        description="Include job title suggestions"
    )


class AutocompleteResponse(BaseModel):
    """Response model for search autocomplete."""
    
    suggestions: List[SearchSuggestion] = Field(
        default_factory=list,
        description="Autocomplete suggestions"
    )
    query: str = Field(..., description="Original query")

