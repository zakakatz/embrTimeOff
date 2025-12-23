"""Pydantic models for employee CSV import operations."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ImportStatus(str, Enum):
    """Status values for import job processing."""
    
    PENDING = "pending"
    VALIDATING = "validating"
    MAPPING = "mapping"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ROLLED_BACK = "rolled_back"


class ImportFieldError(BaseModel):
    """Validation error for a specific field in a CSV row."""
    
    field: str = Field(..., description="Name of the field with error")
    value: Optional[str] = Field(None, description="The invalid value")
    message: str = Field(..., description="Description of the validation error")
    code: str = Field(default="invalid", description="Error code for categorization")
    suggestion: Optional[str] = Field(None, description="Suggested correction")


class ImportRecordError(BaseModel):
    """Validation errors for a single CSV row."""
    
    row_number: int = Field(..., description="Row number in the CSV file (1-based)")
    employee_id: Optional[str] = Field(None, description="Employee ID from the row if available")
    field_errors: List[ImportFieldError] = Field(
        default_factory=list,
        description="List of field-level validation errors"
    )
    is_valid: bool = Field(default=False, description="Whether this row is valid")


class ImportRequest(BaseModel):
    """Request model for initiating a CSV import."""
    
    filename: str = Field(..., description="Name of the uploaded CSV file")
    allow_partial_import: bool = Field(
        default=True,
        description="Whether to import valid records even if some fail validation"
    )
    skip_first_row: bool = Field(
        default=True,
        description="Whether to skip the header row"
    )
    delimiter: str = Field(
        default=",",
        max_length=1,
        description="CSV delimiter character"
    )
    field_mappings: Optional[Dict[str, str]] = Field(
        default=None,
        description="Custom field mappings from CSV columns to employee fields"
    )


class ImportProgress(BaseModel):
    """Real-time progress information for an import job."""
    
    total_rows: int = Field(default=0, description="Total rows in the CSV file")
    processed_rows: int = Field(default=0, description="Rows processed so far")
    successful_rows: int = Field(default=0, description="Rows successfully imported")
    error_rows: int = Field(default=0, description="Rows with validation errors")
    completion_percentage: float = Field(default=0.0, description="Progress as percentage")
    estimated_completion_time: Optional[datetime] = Field(
        None,
        description="Estimated time of completion"
    )


class ImportResponse(BaseModel):
    """Response model for import initiation."""
    
    import_id: UUID = Field(..., description="Unique identifier for tracking the import")
    import_reference_id: str = Field(..., description="Human-readable reference ID")
    status: ImportStatus = Field(..., description="Current import status")
    filename: str = Field(..., description="Name of the uploaded file")
    file_size_bytes: int = Field(..., description="Size of the uploaded file in bytes")
    created_at: datetime = Field(..., description="When the import was initiated")
    message: str = Field(default="Import job created", description="Status message")


class ImportStatusResponse(BaseModel):
    """Detailed status response for an import job."""
    
    import_id: UUID = Field(..., description="Unique identifier for the import")
    import_reference_id: str = Field(..., description="Human-readable reference ID")
    status: ImportStatus = Field(..., description="Current import status")
    progress: ImportProgress = Field(..., description="Progress information")
    validation_errors: List[ImportRecordError] = Field(
        default_factory=list,
        description="List of validation errors found during import"
    )
    error_summary: Optional[Dict[str, int]] = Field(
        None,
        description="Summary of error counts by error type"
    )
    started_at: Optional[datetime] = Field(None, description="When processing started")
    completed_at: Optional[datetime] = Field(None, description="When processing completed")
    created_at: datetime = Field(..., description="When the import was initiated")
    created_by_user_id: UUID = Field(..., description="User who initiated the import")
    
    class Config:
        """Pydantic configuration."""
        
        from_attributes = True


class ImportValidationResult(BaseModel):
    """Result of validating a CSV file before import."""
    
    is_valid: bool = Field(..., description="Whether the file passed all validations")
    total_rows: int = Field(..., description="Total data rows in the file")
    valid_rows: int = Field(..., description="Number of valid rows")
    error_rows: int = Field(..., description="Number of rows with errors")
    errors: List[ImportRecordError] = Field(
        default_factory=list,
        description="Detailed errors for each invalid row"
    )
    detected_columns: List[str] = Field(
        default_factory=list,
        description="Column headers detected in the CSV"
    )
    suggested_mappings: Optional[Dict[str, str]] = Field(
        None,
        description="Suggested mappings from CSV columns to employee fields"
    )

