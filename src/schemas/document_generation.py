"""Pydantic models for document generation API."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class DocumentFormatEnum(str, Enum):
    """Supported document output formats."""
    PDF = "pdf"
    CSV = "csv"
    EXCEL = "xlsx"
    JSON = "json"
    HTML = "html"


class DocumentStatusEnum(str, Enum):
    """Document generation status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PageSizeEnum(str, Enum):
    """Standard page sizes for PDF."""
    A4 = "A4"
    LETTER = "Letter"
    LEGAL = "Legal"
    A3 = "A3"
    A5 = "A5"


class PageOrientationEnum(str, Enum):
    """Page orientation options."""
    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"


class ValidationSeverityEnum(str, Enum):
    """Validation issue severity levels."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


# Request Models

class PageMarginsRequest(BaseModel):
    """Page margins configuration."""
    top: float = Field(default=25.0, ge=0, description="Top margin in mm")
    right: float = Field(default=25.0, ge=0, description="Right margin in mm")
    bottom: float = Field(default=25.0, ge=0, description="Bottom margin in mm")
    left: float = Field(default=25.0, ge=0, description="Left margin in mm")


class PDFMetadataRequest(BaseModel):
    """PDF document metadata."""
    title: str = Field(default="", description="Document title")
    author: str = Field(default="", description="Document author")
    subject: str = Field(default="", description="Document subject")
    keywords: List[str] = Field(default_factory=list, description="Document keywords")


class PDFConfigRequest(BaseModel):
    """PDF generation configuration."""
    page_size: PageSizeEnum = Field(default=PageSizeEnum.A4, description="Page size")
    orientation: PageOrientationEnum = Field(
        default=PageOrientationEnum.PORTRAIT, description="Page orientation"
    )
    margins: Optional[PageMarginsRequest] = Field(default=None, description="Page margins")
    metadata: Optional[PDFMetadataRequest] = Field(default=None, description="Document metadata")
    header_template: Optional[str] = Field(default=None, description="Header HTML template")
    footer_template: Optional[str] = Field(default=None, description="Footer HTML template")
    include_page_numbers: bool = Field(default=True, description="Include page numbers")
    base_font_size: int = Field(default=12, ge=8, le=24, description="Base font size in points")


class ColumnDefinition(BaseModel):
    """Column definition for tabular documents."""
    key: str = Field(..., description="Data key (supports dot notation)")
    header: str = Field(..., description="Column header text")
    width: Optional[int] = Field(default=None, ge=1, description="Column width")
    format_type: Optional[str] = Field(
        default=None,
        description="Format type: currency, date, number, percentage"
    )
    alignment: str = Field(default="left", description="Text alignment: left, center, right")
    visible: bool = Field(default=True, description="Whether column is visible")


class DocumentGenerationRequest(BaseModel):
    """Request to generate a document."""
    format: DocumentFormatEnum = Field(..., description="Output format")
    template_name: Optional[str] = Field(
        default=None,
        description="Built-in template name (employee_report, time_off_summary, etc.)"
    )
    title: str = Field(default="Document", description="Document title")
    filename: Optional[str] = Field(default=None, description="Output filename (auto-generated if not provided)")
    data: Dict[str, Any] = Field(default_factory=dict, description="Data for template rendering")
    columns: List[ColumnDefinition] = Field(
        default_factory=list,
        description="Column definitions for tabular formats"
    )
    pdf_config: Optional[PDFConfigRequest] = Field(
        default=None,
        description="PDF-specific configuration"
    )
    include_headers: bool = Field(default=True, description="Include headers in tabular output")
    sheet_name: str = Field(default="Sheet1", description="Excel sheet name")


class TemplateRenderRequest(BaseModel):
    """Request to render a template."""
    template: str = Field(..., description="Template string to render")
    context: Dict[str, Any] = Field(default_factory=dict, description="Template context data")


class FileValidationRequest(BaseModel):
    """Request to validate a file."""
    filename: str = Field(..., description="Original filename")
    content_type: Optional[str] = Field(default=None, description="Declared content type")
    max_size_bytes: Optional[int] = Field(default=None, description="Max file size override")
    allowed_extensions: Optional[List[str]] = Field(
        default=None,
        description="Allowed file extensions override"
    )


# Response Models

class ValidationIssue(BaseModel):
    """Validation issue details."""
    code: str = Field(..., description="Issue code")
    message: str = Field(..., description="Human-readable message")
    severity: ValidationSeverityEnum = Field(..., description="Issue severity")
    field: Optional[str] = Field(default=None, description="Related field")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Additional details")


class FileValidationResponse(BaseModel):
    """File validation result."""
    is_valid: bool = Field(..., description="Whether file is valid")
    filename: str = Field(..., description="Validated filename")
    file_size: int = Field(..., description="File size in bytes")
    content_type: str = Field(..., description="Detected/declared content type")
    issues: List[ValidationIssue] = Field(default_factory=list, description="Validation issues")
    file_hash: Optional[str] = Field(default=None, description="SHA-256 hash of file content")
    validated_at: datetime = Field(default_factory=datetime.utcnow, description="Validation timestamp")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class DocumentGenerationResponse(BaseModel):
    """Document generation result."""
    id: str = Field(..., description="Generation task ID")
    status: DocumentStatusEnum = Field(..., description="Current status")
    format: DocumentFormatEnum = Field(..., description="Document format")
    filename: str = Field(..., description="Output filename")
    content_type: str = Field(..., description="MIME type")
    size_bytes: int = Field(default=0, description="File size in bytes")
    download_url: Optional[str] = Field(default=None, description="URL to download the document")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    completed_at: Optional[datetime] = Field(default=None, description="Completion timestamp")
    progress: int = Field(default=0, ge=0, le=100, description="Progress percentage")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class DocumentStatusResponse(BaseModel):
    """Document generation status."""
    id: str = Field(..., description="Task ID")
    status: DocumentStatusEnum = Field(..., description="Current status")
    progress: int = Field(default=0, ge=0, le=100, description="Progress percentage")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    download_ready: bool = Field(default=False, description="Whether download is ready")


class TemplateRenderResponse(BaseModel):
    """Template render result."""
    rendered: str = Field(..., description="Rendered template output")
    success: bool = Field(default=True, description="Whether rendering succeeded")
    errors: List[str] = Field(default_factory=list, description="Validation/render errors")


class StoredFileInfo(BaseModel):
    """Information about a stored file."""
    id: str = Field(..., description="File ID")
    filename: str = Field(..., description="Original filename")
    content_type: str = Field(..., description="MIME type")
    size_bytes: int = Field(..., description="File size")
    hash_value: str = Field(..., description="SHA-256 hash")
    created_at: datetime = Field(..., description="Upload timestamp")
    expires_at: Optional[datetime] = Field(default=None, description="Expiration timestamp")
    is_expired: bool = Field(default=False, description="Whether file has expired")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="File metadata")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class StorageStatsResponse(BaseModel):
    """Storage statistics."""
    total_files: int = Field(..., description="Total number of files")
    total_size_bytes: int = Field(..., description="Total storage size")
    expired_files: int = Field(..., description="Number of expired files")
    backend: str = Field(..., description="Storage backend type")


class FileUploadResponse(BaseModel):
    """File upload result."""
    file_id: str = Field(..., description="Unique file identifier")
    filename: str = Field(..., description="Stored filename")
    content_type: str = Field(..., description="Detected content type")
    size_bytes: int = Field(..., description="File size")
    hash_value: str = Field(..., description="SHA-256 hash")
    expires_at: Optional[datetime] = Field(default=None, description="Expiration timestamp")
    validation: FileValidationResponse = Field(..., description="Validation results")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class AvailableTemplatesResponse(BaseModel):
    """List of available document templates."""
    templates: List[Dict[str, str]] = Field(..., description="Available templates with names and descriptions")


class SupportedFormatsResponse(BaseModel):
    """List of supported document formats."""
    formats: List[Dict[str, str]] = Field(..., description="Supported formats with extensions and MIME types")

