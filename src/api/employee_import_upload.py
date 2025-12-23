"""API endpoints for employee CSV file upload and validation."""

import hashlib
import io
import os
import tempfile
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Header, Query, Request, UploadFile, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.database.database import get_db
from src.utils.auth import CurrentUser, UserRole, get_mock_current_user
from src.utils.errors import APIError, ForbiddenError, ValidationError


# =============================================================================
# Constants and Configuration
# =============================================================================

MAX_FILE_SIZE_MB = getattr(settings, 'MAX_IMPORT_FILE_SIZE_MB', 10)
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
ALLOWED_CONTENT_TYPES = ['text/csv', 'application/csv', 'text/plain']
ALLOWED_EXTENSIONS = ['.csv']

# Dangerous patterns that could indicate malware or injection
DANGEROUS_PATTERNS = [
    b'<%',      # ASP/JSP tags
    b'<?php',   # PHP tags
    b'<script', # Script tags
    b'<iframe', # iframe injection
    b'javascript:', # JavaScript protocol
    b'vbscript:', # VBScript protocol
    b'data:text/html', # Data URI
]


# =============================================================================
# Request/Response Models
# =============================================================================

class ColumnInfo(BaseModel):
    """Information about a detected CSV column."""
    
    index: int = Field(..., description="Zero-based column index")
    name: str = Field(..., description="Column header name")
    detected_type: str = Field(..., description="Detected data type (string, number, date, email, etc.)")
    sample_values: List[str] = Field(default_factory=list, description="Sample values from this column")
    empty_count: int = Field(default=0, description="Number of empty values")
    unique_count: int = Field(default=0, description="Approximate number of unique values")


class FileValidationResult(BaseModel):
    """Results of file format validation."""
    
    is_valid: bool = Field(..., description="Whether file passed validation")
    errors: List[str] = Field(default_factory=list, description="List of validation errors")
    warnings: List[str] = Field(default_factory=list, description="List of validation warnings")
    

class UploadResult(BaseModel):
    """Result of file upload operation."""
    
    import_id: uuid.UUID = Field(..., description="Unique identifier for this import")
    filename: str = Field(..., description="Original filename")
    file_size: int = Field(..., description="File size in bytes")
    file_hash: str = Field(..., description="SHA-256 hash of file content")
    upload_timestamp: datetime = Field(..., description="When the file was uploaded")
    expires_at: datetime = Field(..., description="When the temporary file will expire")
    row_count: int = Field(..., description="Number of data rows detected")
    column_count: int = Field(..., description="Number of columns detected")
    columns: List[ColumnInfo] = Field(default_factory=list, description="Detected column information")
    encoding: str = Field(default="utf-8", description="Detected file encoding")
    delimiter: str = Field(default=",", description="Detected delimiter")
    has_headers: bool = Field(default=True, description="Whether file has header row")
    validation: FileValidationResult = Field(..., description="File validation results")
    queue_position: Optional[int] = Field(None, description="Position in processing queue")
    estimated_process_time: Optional[int] = Field(None, description="Estimated processing time in seconds")


class UploadResponse(BaseModel):
    """Response for upload endpoint."""
    
    success: bool = Field(default=True)
    message: str = Field(default="File uploaded successfully")
    data: UploadResult


class UploadErrorDetail(BaseModel):
    """Detailed error information."""
    
    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")


class UploadErrorResponse(BaseModel):
    """Response for upload errors."""
    
    success: bool = Field(default=False)
    error: UploadErrorDetail


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
    
    roles = [UserRole.ADMIN]  # Default for development
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


def require_import_permission(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """Require user to have import permission."""
    allowed_roles = [UserRole.ADMIN, UserRole.HR_MANAGER]
    
    if not any(current_user.has_role(role) for role in allowed_roles):
        raise ForbiddenError(
            message="You don't have permission to import employee data",
            details={"required_roles": [r.value for r in allowed_roles]},
        )
    
    return current_user


# =============================================================================
# File Validation Functions
# =============================================================================

def validate_file_size(content: bytes) -> Optional[str]:
    """Validate file size is within limits."""
    if len(content) > MAX_FILE_SIZE_BYTES:
        return f"File size ({len(content) / 1024 / 1024:.2f} MB) exceeds maximum allowed size ({MAX_FILE_SIZE_MB} MB)"
    return None


def validate_file_extension(filename: str) -> Optional[str]:
    """Validate file has allowed extension."""
    if not filename:
        return "Filename is required"
    
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return f"File extension '{ext}' not allowed. Allowed extensions: {', '.join(ALLOWED_EXTENSIONS)}"
    return None


def validate_content_type(content_type: Optional[str]) -> Optional[str]:
    """Validate content type is allowed."""
    if not content_type:
        return None  # Skip if not provided
    
    # Normalize content type (remove charset etc)
    base_type = content_type.split(';')[0].strip().lower()
    if base_type not in ALLOWED_CONTENT_TYPES:
        return f"Content type '{content_type}' not allowed"
    return None


def scan_for_security_threats(content: bytes) -> List[str]:
    """Scan file content for potential security threats."""
    threats = []
    
    # Check for dangerous patterns
    content_lower = content.lower()
    for pattern in DANGEROUS_PATTERNS:
        if pattern.lower() in content_lower:
            threats.append(f"Potentially dangerous content detected: {pattern.decode('utf-8', errors='ignore')}")
    
    # Check for null bytes (potential binary/executable)
    if b'\x00' in content:
        threats.append("Binary content detected (null bytes found)")
    
    return threats


def detect_encoding(content: bytes) -> str:
    """Detect file encoding."""
    # Check for BOM markers
    if content.startswith(b'\xef\xbb\xbf'):
        return 'utf-8-sig'
    if content.startswith(b'\xff\xfe'):
        return 'utf-16-le'
    if content.startswith(b'\xfe\xff'):
        return 'utf-16-be'
    
    # Try UTF-8
    try:
        content.decode('utf-8')
        return 'utf-8'
    except UnicodeDecodeError:
        pass
    
    # Fall back to latin-1 (accepts any byte)
    return 'latin-1'


def detect_delimiter(lines: List[str]) -> str:
    """Detect CSV delimiter from content."""
    if not lines:
        return ','
    
    # Count occurrences of common delimiters in first line
    delimiters = {',': 0, ';': 0, '\t': 0, '|': 0}
    first_line = lines[0]
    
    for delim in delimiters:
        delimiters[delim] = first_line.count(delim)
    
    # Return delimiter with most occurrences
    best_delim = max(delimiters, key=delimiters.get)
    if delimiters[best_delim] > 0:
        return best_delim
    return ','


def detect_column_type(values: List[str]) -> str:
    """Detect data type from sample values."""
    if not values:
        return 'string'
    
    # Filter out empty values
    non_empty = [v.strip() for v in values if v.strip()]
    if not non_empty:
        return 'string'
    
    # Check for email pattern
    if all('@' in v and '.' in v for v in non_empty):
        return 'email'
    
    # Check for date patterns
    date_patterns = ['-', '/']
    if all(any(p in v for p in date_patterns) for v in non_empty):
        return 'date'
    
    # Check for numeric
    try:
        for v in non_empty:
            float(v.replace(',', ''))
        return 'number'
    except ValueError:
        pass
    
    # Check for boolean
    bool_values = {'true', 'false', 'yes', 'no', '1', '0', 'y', 'n'}
    if all(v.lower() in bool_values for v in non_empty):
        return 'boolean'
    
    return 'string'


def analyze_csv_content(content: bytes, encoding: str, delimiter: str) -> Dict[str, Any]:
    """Analyze CSV content and extract metadata."""
    import csv
    
    text = content.decode(encoding, errors='replace')
    lines = text.strip().split('\n')
    
    if not lines:
        return {
            'row_count': 0,
            'column_count': 0,
            'columns': [],
            'has_headers': False,
        }
    
    # Parse CSV
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = list(reader)
    
    if not rows:
        return {
            'row_count': 0,
            'column_count': 0,
            'columns': [],
            'has_headers': False,
        }
    
    headers = rows[0]
    data_rows = rows[1:] if len(rows) > 1 else []
    
    # Analyze columns
    columns = []
    for i, header in enumerate(headers):
        # Get values for this column
        col_values = [row[i] if i < len(row) else '' for row in data_rows]
        sample_values = [v for v in col_values[:5] if v]  # First 5 non-empty values
        
        columns.append(ColumnInfo(
            index=i,
            name=header.strip(),
            detected_type=detect_column_type(col_values[:100]),  # Sample first 100 rows
            sample_values=sample_values,
            empty_count=sum(1 for v in col_values if not v.strip()),
            unique_count=len(set(v.strip().lower() for v in col_values if v.strip())),
        ))
    
    return {
        'row_count': len(data_rows),
        'column_count': len(headers),
        'columns': columns,
        'has_headers': True,  # We assume first row is headers
    }


def calculate_file_hash(content: bytes) -> str:
    """Calculate SHA-256 hash of file content."""
    return hashlib.sha256(content).hexdigest()


# =============================================================================
# Temporary File Storage
# =============================================================================

class TemporaryFileStorage:
    """Manages temporary file storage for uploads."""
    
    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = Path(base_dir) if base_dir else Path(tempfile.gettempdir()) / 'employee_imports'
        self.base_dir.mkdir(parents=True, exist_ok=True)
    
    def store(self, import_id: uuid.UUID, content: bytes) -> Path:
        """Store file content and return path."""
        file_path = self.base_dir / f"{import_id}.csv"
        file_path.write_bytes(content)
        return file_path
    
    def retrieve(self, import_id: uuid.UUID) -> Optional[bytes]:
        """Retrieve file content by import ID."""
        file_path = self.base_dir / f"{import_id}.csv"
        if file_path.exists():
            return file_path.read_bytes()
        return None
    
    def delete(self, import_id: uuid.UUID) -> bool:
        """Delete stored file."""
        file_path = self.base_dir / f"{import_id}.csv"
        if file_path.exists():
            file_path.unlink()
            return True
        return False
    
    def cleanup_expired(self, max_age_hours: int = 24) -> int:
        """Remove files older than max_age_hours. Returns count of deleted files."""
        cutoff = datetime.now().timestamp() - (max_age_hours * 3600)
        deleted = 0
        
        for file_path in self.base_dir.glob("*.csv"):
            if file_path.stat().st_mtime < cutoff:
                file_path.unlink()
                deleted += 1
        
        return deleted


# Global storage instance
file_storage = TemporaryFileStorage()


# =============================================================================
# Router Setup
# =============================================================================

employee_import_upload_router = APIRouter(
    prefix="/api/employee-import",
    tags=["Employee Import Upload"],
)


# =============================================================================
# Endpoints
# =============================================================================

@employee_import_upload_router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload CSV File for Import",
    description="Upload a CSV file for employee data import with validation and security scanning.",
    responses={
        400: {"model": UploadErrorResponse, "description": "Validation error"},
        403: {"model": UploadErrorResponse, "description": "Permission denied"},
        413: {"model": UploadErrorResponse, "description": "File too large"},
    },
)
async def upload_import_file(
    file: Annotated[UploadFile, File(description="CSV file containing employee data")],
    current_user: Annotated[CurrentUser, Depends(require_import_permission)],
    x_organization_id: Annotated[Optional[str], Header(alias="X-Organization-ID")] = None,
) -> UploadResponse:
    """
    Upload a CSV file for employee data import.
    
    This endpoint:
    - Validates file format, size, and extension
    - Scans for potential security threats
    - Detects encoding and delimiter
    - Analyzes column structure
    - Stores file temporarily for processing
    - Returns import ID for tracking
    
    Role-based access: Requires ADMIN or HR_MANAGER role.
    """
    errors = []
    warnings = []
    
    # Validate filename and extension
    ext_error = validate_file_extension(file.filename or '')
    if ext_error:
        raise ValidationError(
            message=ext_error,
            details={"filename": file.filename, "code": "INVALID_EXTENSION"},
        )
    
    # Validate content type
    ct_error = validate_content_type(file.content_type)
    if ct_error:
        warnings.append(ct_error)  # Warning, not error
    
    # Read file content
    content = await file.read()
    
    # Validate file size
    size_error = validate_file_size(content)
    if size_error:
        raise ValidationError(
            message=size_error,
            details={
                "file_size": len(content),
                "max_size": MAX_FILE_SIZE_BYTES,
                "code": "FILE_TOO_LARGE",
            },
        )
    
    # Check for empty file
    if len(content) == 0:
        raise ValidationError(
            message="File is empty",
            details={"code": "EMPTY_FILE"},
        )
    
    # Security scanning
    threats = scan_for_security_threats(content)
    if threats:
        raise ValidationError(
            message="File failed security scan",
            details={
                "threats": threats,
                "code": "SECURITY_VIOLATION",
            },
        )
    
    # Detect encoding
    encoding = detect_encoding(content)
    
    # Decode and detect delimiter
    try:
        text = content.decode(encoding, errors='replace')
        lines = text.strip().split('\n')
        delimiter = detect_delimiter(lines)
    except Exception as e:
        raise ValidationError(
            message=f"Failed to parse file content: {str(e)}",
            details={"code": "PARSE_ERROR"},
        )
    
    # Validate CSV structure
    if not lines or len(lines) < 2:
        errors.append("File must contain at least a header row and one data row")
    
    # Analyze CSV content
    try:
        analysis = analyze_csv_content(content, encoding, delimiter)
    except Exception as e:
        raise ValidationError(
            message=f"Failed to analyze CSV structure: {str(e)}",
            details={"code": "ANALYSIS_ERROR"},
        )
    
    # Check for minimum columns
    if analysis['column_count'] < 2:
        errors.append(f"File must contain at least 2 columns, found {analysis['column_count']}")
    
    # Generate import ID and store file
    import_id = uuid.uuid4()
    file_hash = calculate_file_hash(content)
    
    # Store file temporarily
    file_storage.store(import_id, content)
    
    # Calculate timestamps
    upload_timestamp = datetime.utcnow()
    expires_at = upload_timestamp + timedelta(hours=24)
    
    # Estimate queue position and processing time (mock for now)
    queue_position = 1  # Would come from actual queue
    estimated_time = max(5, analysis['row_count'] // 100)  # Rough estimate
    
    # Build validation result
    validation = FileValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )
    
    # Build response
    result = UploadResult(
        import_id=import_id,
        filename=file.filename or 'unknown.csv',
        file_size=len(content),
        file_hash=file_hash,
        upload_timestamp=upload_timestamp,
        expires_at=expires_at,
        row_count=analysis['row_count'],
        column_count=analysis['column_count'],
        columns=analysis['columns'],
        encoding=encoding,
        delimiter=delimiter,
        has_headers=analysis['has_headers'],
        validation=validation,
        queue_position=queue_position if validation.is_valid else None,
        estimated_process_time=estimated_time if validation.is_valid else None,
    )
    
    return UploadResponse(
        success=True,
        message="File uploaded successfully" if validation.is_valid else "File uploaded with validation errors",
        data=result,
    )


@employee_import_upload_router.get(
    "/upload/{import_id}",
    response_model=UploadResponse,
    summary="Get Upload Status",
    description="Get status and details of a previously uploaded file.",
)
async def get_upload_status(
    import_id: uuid.UUID,
    current_user: Annotated[CurrentUser, Depends(require_import_permission)],
) -> UploadResponse:
    """
    Get status of a previously uploaded file.
    
    Returns the same information as the upload endpoint, useful for
    checking if an upload is still valid for processing.
    """
    # Try to retrieve the file
    content = file_storage.retrieve(import_id)
    
    if not content:
        raise ValidationError(
            message="Upload not found or has expired",
            details={"import_id": str(import_id), "code": "UPLOAD_NOT_FOUND"},
        )
    
    # Re-analyze the file
    encoding = detect_encoding(content)
    text = content.decode(encoding, errors='replace')
    lines = text.strip().split('\n')
    delimiter = detect_delimiter(lines)
    analysis = analyze_csv_content(content, encoding, delimiter)
    
    # Get file stats (for timestamp)
    file_path = file_storage.base_dir / f"{import_id}.csv"
    upload_timestamp = datetime.fromtimestamp(file_path.stat().st_mtime)
    expires_at = upload_timestamp + timedelta(hours=24)
    
    result = UploadResult(
        import_id=import_id,
        filename=f"{import_id}.csv",  # Original filename not stored
        file_size=len(content),
        file_hash=calculate_file_hash(content),
        upload_timestamp=upload_timestamp,
        expires_at=expires_at,
        row_count=analysis['row_count'],
        column_count=analysis['column_count'],
        columns=analysis['columns'],
        encoding=encoding,
        delimiter=delimiter,
        has_headers=analysis['has_headers'],
        validation=FileValidationResult(is_valid=True, errors=[], warnings=[]),
        queue_position=1,
        estimated_process_time=max(5, analysis['row_count'] // 100),
    )
    
    return UploadResponse(
        success=True,
        message="Upload found",
        data=result,
    )


@employee_import_upload_router.delete(
    "/upload/{import_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel Upload",
    description="Cancel an upload and delete the temporary file.",
)
async def cancel_upload(
    import_id: uuid.UUID,
    current_user: Annotated[CurrentUser, Depends(require_import_permission)],
) -> None:
    """
    Cancel an upload and delete the temporary file.
    
    Use this to clean up files that won't be processed.
    """
    deleted = file_storage.delete(import_id)
    
    if not deleted:
        raise ValidationError(
            message="Upload not found or already deleted",
            details={"import_id": str(import_id), "code": "UPLOAD_NOT_FOUND"},
        )


# =============================================================================
# Exception Handler
# =============================================================================

async def upload_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """Handle API errors for upload endpoints."""
    response = exc.to_response()
    return JSONResponse(
        status_code=response.status_code,
        content={
            "success": False,
            "error": {
                "code": exc.error_code,
                "message": exc.message,
                "details": exc.details,
            },
        },
    )

