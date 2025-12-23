"""Pydantic models for employee CSV export operations."""

from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ExportFormat(str, Enum):
    """Supported export file formats."""
    
    CSV = "csv"


class ExportFieldSelection(BaseModel):
    """Configuration for which fields to include in export."""
    
    include_all: bool = Field(
        default=False,
        description="Include all fields the user has permission to view"
    )
    fields: Optional[List[str]] = Field(
        default=None,
        description="Specific fields to include in export"
    )
    exclude_fields: Optional[List[str]] = Field(
        default=None,
        description="Fields to exclude from export"
    )
    
    @field_validator("fields", "exclude_fields", mode="before")
    @classmethod
    def validate_fields_list(cls, v):
        """Ensure field lists are properly formatted."""
        if v is None:
            return v
        if isinstance(v, str):
            return [f.strip() for f in v.split(",")]
        return v


class ExportFilters(BaseModel):
    """Filter criteria for employee export."""
    
    department_ids: Optional[List[int]] = Field(
        default=None,
        description="Filter by department IDs"
    )
    location_ids: Optional[List[int]] = Field(
        default=None,
        description="Filter by location IDs"
    )
    employment_status: Optional[List[str]] = Field(
        default=None,
        description="Filter by employment status (active, terminated, etc.)"
    )
    employment_type: Optional[List[str]] = Field(
        default=None,
        description="Filter by employment type (full_time, part_time, etc.)"
    )
    hire_date_from: Optional[date] = Field(
        default=None,
        description="Filter employees hired on or after this date"
    )
    hire_date_to: Optional[date] = Field(
        default=None,
        description="Filter employees hired on or before this date"
    )
    manager_ids: Optional[List[int]] = Field(
        default=None,
        description="Filter by manager IDs (employees reporting to these managers)"
    )
    is_active: Optional[bool] = Field(
        default=None,
        description="Filter by active status"
    )
    search_query: Optional[str] = Field(
        default=None,
        description="Search query to filter employees"
    )


class ExportRequest(BaseModel):
    """Request model for initiating a CSV export."""
    
    format: ExportFormat = Field(
        default=ExportFormat.CSV,
        description="Export file format"
    )
    field_selection: Optional[ExportFieldSelection] = Field(
        default=None,
        description="Configuration for which fields to export"
    )
    filters: Optional[ExportFilters] = Field(
        default=None,
        description="Filters to apply to the export"
    )
    include_headers: bool = Field(
        default=True,
        description="Include column headers in the export"
    )
    delimiter: str = Field(
        default=",",
        max_length=1,
        description="CSV delimiter character"
    )
    filename_prefix: Optional[str] = Field(
        default="employees_export",
        max_length=100,
        description="Prefix for the exported filename"
    )


class ExportResponse(BaseModel):
    """Response model for export operations."""
    
    filename: str = Field(..., description="Name of the exported file")
    content_type: str = Field(
        default="text/csv",
        description="MIME type of the exported file"
    )
    total_records: int = Field(..., description="Number of records exported")
    exported_fields: List[str] = Field(
        default_factory=list,
        description="Fields included in the export"
    )
    filters_applied: Optional[Dict[str, Any]] = Field(
        None,
        description="Summary of filters applied to the export"
    )
    generated_at: datetime = Field(..., description="When the export was generated")
    generated_by_user_id: UUID = Field(..., description="User who generated the export")


class ExportableField(BaseModel):
    """Information about a field that can be exported."""
    
    name: str = Field(..., description="Field name")
    display_name: str = Field(..., description="Human-readable field name")
    description: Optional[str] = Field(None, description="Field description")
    data_type: str = Field(..., description="Data type of the field")
    is_sensitive: bool = Field(
        default=False,
        description="Whether this field contains sensitive data"
    )


class AvailableExportFieldsResponse(BaseModel):
    """Response listing fields available for export based on user permissions."""
    
    fields: List[ExportableField] = Field(
        default_factory=list,
        description="List of exportable fields"
    )
    total_fields: int = Field(..., description="Total number of available fields")
    user_role: str = Field(..., description="Role of the requesting user")

