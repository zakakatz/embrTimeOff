"""API endpoints for employee CSV import/export operations."""

import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, Form, Header, Query, Request, UploadFile, status
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.schemas.employee_export import (
    AvailableExportFieldsResponse,
    ExportFieldSelection,
    ExportFilters,
    ExportRequest,
    ExportResponse,
)
from src.schemas.employee_import import (
    ImportResponse,
    ImportStatus,
    ImportStatusResponse,
    ImportValidationResult,
)
from src.services.employee_import_service import EmployeeImportService
from src.services.employee_export_service import EmployeeExportService
from src.utils.auth import CurrentUser, UserRole, get_mock_current_user
from src.utils.errors import APIError, ValidationError


# =============================================================================
# Request/Response Models
# =============================================================================

class ImportInitiateRequest(BaseModel):
    """Request parameters for initiating an import."""
    
    allow_partial_import: bool = Field(
        default=True,
        description="Whether to import valid records even if some fail validation"
    )
    delimiter: str = Field(
        default=",",
        max_length=1,
        description="CSV delimiter character"
    )


class ImportInitiateResponse(BaseModel):
    """Response for import initiation."""
    
    data: ImportResponse
    message: str = "Import job created successfully"


class ImportStatusResponseWrapper(BaseModel):
    """Response wrapper for import status."""
    
    data: ImportStatusResponse


class ValidationResultResponse(BaseModel):
    """Response wrapper for validation results."""
    
    data: ImportValidationResult


class ExportRequestBody(BaseModel):
    """Request body for export operation."""
    
    field_selection: Optional[ExportFieldSelection] = None
    filters: Optional[ExportFilters] = None
    include_headers: bool = True
    delimiter: str = ","
    filename_prefix: str = "employees_export"


# =============================================================================
# Dependency Injection
# =============================================================================

def get_import_service(
    session: Annotated[Session, Depends(get_db)],
) -> EmployeeImportService:
    """Get employee import service instance."""
    return EmployeeImportService(session)


def get_export_service(
    session: Annotated[Session, Depends(get_db)],
) -> EmployeeExportService:
    """Get employee export service instance."""
    return EmployeeExportService(session)


def get_current_user(
    request: Request,
    x_user_id: Annotated[Optional[str], Header(alias="X-User-ID")] = None,
    x_employee_id: Annotated[Optional[int], Header(alias="X-Employee-ID")] = None,
    x_user_role: Annotated[Optional[str], Header(alias="X-User-Role")] = None,
) -> CurrentUser:
    """
    Get current user from request headers.
    
    In production, this would verify JWT tokens or session cookies.
    For development, it uses headers to simulate different users/roles.
    """
    # Parse user ID
    user_id = None
    if x_user_id:
        try:
            user_id = uuid.UUID(x_user_id)
        except ValueError:
            pass
    
    # Parse role
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


# =============================================================================
# Router Setup
# =============================================================================

employee_import_export_router = APIRouter(
    prefix="/api/employees",
    tags=["Employee Import/Export"],
)


# =============================================================================
# Import Endpoints
# =============================================================================

@employee_import_export_router.post(
    "/import",
    response_model=ImportInitiateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Import Employees from CSV",
    description="Upload a CSV file to import employee data. Creates an import job for tracking.",
)
async def import_employees(
    file: Annotated[UploadFile, File(description="CSV file containing employee data")],
    service: Annotated[EmployeeImportService, Depends(get_import_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    allow_partial_import: Annotated[bool, Form(description="Allow partial imports")] = True,
    delimiter: Annotated[str, Form(description="CSV delimiter")] = ",",
    x_organization_id: Annotated[Optional[str], Header(alias="X-Organization-ID")] = None,
) -> ImportInitiateResponse:
    """
    Import employees from a CSV file.
    
    - Accepts CSV file uploads
    - Validates file format and content
    - Creates an import job for tracking progress
    - Supports partial imports (valid records imported, invalid skipped)
    - Returns import job ID for status tracking
    """
    # Validate file type
    if not file.filename or not file.filename.endswith(".csv"):
        raise ValidationError(message="Only CSV files are supported")
    
    # Read file content
    content = await file.read()
    
    # Parse organization ID
    organization_id = uuid.uuid4()  # Default for development
    if x_organization_id:
        try:
            organization_id = uuid.UUID(x_organization_id)
        except ValueError:
            pass
    
    # Create import job
    result = service.create_import_job(
        content=content,
        filename=file.filename,
        current_user=current_user,
        organization_id=organization_id,
        allow_partial_import=allow_partial_import,
        delimiter=delimiter,
    )
    
    return ImportInitiateResponse(data=result)


@employee_import_export_router.post(
    "/import/{import_id}/validate",
    response_model=ValidationResultResponse,
    summary="Validate Import Data",
    description="Validate CSV data for an import job before processing.",
)
async def validate_import(
    import_id: uuid.UUID,
    file: Annotated[UploadFile, File(description="CSV file to validate")],
    service: Annotated[EmployeeImportService, Depends(get_import_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> ValidationResultResponse:
    """
    Validate CSV data for an import job.
    
    - Performs format validation
    - Checks data types
    - Validates business rules
    - Returns detailed error reports for invalid records
    """
    content = await file.read()
    
    result = service.validate_import(
        import_job_id=import_id,
        content=content,
        current_user=current_user,
    )
    
    return ValidationResultResponse(data=result)


@employee_import_export_router.post(
    "/import/{import_id}/process",
    response_model=ImportStatusResponseWrapper,
    summary="Process Import",
    description="Process the validated import and create employee records.",
)
async def process_import(
    import_id: uuid.UUID,
    file: Annotated[UploadFile, File(description="CSV file to process")],
    service: Annotated[EmployeeImportService, Depends(get_import_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> ImportStatusResponseWrapper:
    """
    Process the import and create employee records.
    
    - Creates employee records for valid rows
    - Supports partial imports
    - Records validation errors for failed rows
    - Updates import job status
    """
    content = await file.read()
    
    result = service.process_import(
        import_job_id=import_id,
        content=content,
        current_user=current_user,
    )
    
    return ImportStatusResponseWrapper(data=result)


@employee_import_export_router.get(
    "/import/{import_id}/status",
    response_model=ImportStatusResponseWrapper,
    summary="Get Import Status",
    description="Get real-time status and progress of an import job.",
)
async def get_import_status(
    import_id: uuid.UUID,
    service: Annotated[EmployeeImportService, Depends(get_import_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> ImportStatusResponseWrapper:
    """
    Get import job status.
    
    - Returns current status (pending, validating, processing, completed, failed)
    - Provides progress tracking (completion percentage, rows processed)
    - Includes error summaries and detailed validation errors
    - Shows estimated completion time for in-progress imports
    """
    result = service.get_import_status(
        import_job_id=import_id,
        current_user=current_user,
    )
    
    return ImportStatusResponseWrapper(data=result)


# =============================================================================
# Export Endpoints
# =============================================================================

@employee_import_export_router.get(
    "/export",
    summary="Export Employees to CSV",
    description="Generate a CSV export of employee data.",
)
async def export_employees(
    service: Annotated[EmployeeExportService, Depends(get_export_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    # Field selection
    fields: Annotated[Optional[str], Query(description="Comma-separated list of fields to export")] = None,
    exclude_fields: Annotated[Optional[str], Query(description="Comma-separated list of fields to exclude")] = None,
    include_all: Annotated[bool, Query(description="Include all permitted fields")] = False,
    # Filters
    department_ids: Annotated[Optional[str], Query(description="Comma-separated department IDs")] = None,
    location_ids: Annotated[Optional[str], Query(description="Comma-separated location IDs")] = None,
    employment_status: Annotated[Optional[str], Query(description="Comma-separated employment statuses")] = None,
    employment_type: Annotated[Optional[str], Query(description="Comma-separated employment types")] = None,
    is_active: Annotated[Optional[bool], Query(description="Filter by active status")] = None,
    search: Annotated[Optional[str], Query(description="Search query")] = None,
    # Options
    include_headers: Annotated[bool, Query(description="Include column headers")] = True,
    delimiter: Annotated[str, Query(description="CSV delimiter character")] = ",",
    filename_prefix: Annotated[str, Query(description="Prefix for exported filename")] = "employees_export",
) -> StreamingResponse:
    """
    Export employees to CSV.
    
    - Supports customizable field selection based on user permissions
    - Applies role-based access controls to field visibility
    - Supports filtering by department, location, status, etc.
    - Returns CSV as streaming download
    """
    # Build field selection
    field_selection = ExportFieldSelection(
        include_all=include_all,
        fields=[f.strip() for f in fields.split(",")] if fields else None,
        exclude_fields=[f.strip() for f in exclude_fields.split(",")] if exclude_fields else None,
    )
    
    # Build filters
    filters = ExportFilters(
        department_ids=[int(d.strip()) for d in department_ids.split(",")] if department_ids else None,
        location_ids=[int(l.strip()) for l in location_ids.split(",")] if location_ids else None,
        employment_status=[s.strip() for s in employment_status.split(",")] if employment_status else None,
        employment_type=[t.strip() for t in employment_type.split(",")] if employment_type else None,
        is_active=is_active,
        search_query=search,
    )
    
    # Build request
    request = ExportRequest(
        field_selection=field_selection,
        filters=filters,
        include_headers=include_headers,
        delimiter=delimiter,
        filename_prefix=filename_prefix,
    )
    
    # Generate export
    csv_content, response = service.export_employees(
        current_user=current_user,
        request=request,
    )
    
    # Return as streaming response
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={response.filename}",
            "X-Total-Records": str(response.total_records),
            "X-Exported-Fields": ",".join(response.exported_fields),
        },
    )


@employee_import_export_router.post(
    "/export",
    summary="Export Employees to CSV (POST)",
    description="Generate a CSV export with complex filters via POST body.",
)
async def export_employees_post(
    request: ExportRequestBody,
    service: Annotated[EmployeeExportService, Depends(get_export_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> StreamingResponse:
    """
    Export employees to CSV using POST request.
    
    Allows more complex filter configurations via request body.
    """
    # Build request
    export_request = ExportRequest(
        field_selection=request.field_selection,
        filters=request.filters,
        include_headers=request.include_headers,
        delimiter=request.delimiter,
        filename_prefix=request.filename_prefix,
    )
    
    # Generate export
    csv_content, response = service.export_employees(
        current_user=current_user,
        request=export_request,
    )
    
    # Return as streaming response
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={response.filename}",
            "X-Total-Records": str(response.total_records),
            "X-Exported-Fields": ",".join(response.exported_fields),
        },
    )


@employee_import_export_router.get(
    "/export/fields",
    response_model=AvailableExportFieldsResponse,
    summary="Get Available Export Fields",
    description="Get list of fields available for export based on user permissions.",
)
async def get_export_fields(
    service: Annotated[EmployeeExportService, Depends(get_export_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> AvailableExportFieldsResponse:
    """
    Get available export fields.
    
    - Returns fields the user is permitted to export based on their role
    - Includes field metadata (display name, type, sensitivity)
    """
    return service.get_available_fields(current_user=current_user)


# =============================================================================
# Exception Handler (for registration with main app)
# =============================================================================

async def import_export_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """Handle API errors for import/export endpoints."""
    response = exc.to_response()
    return JSONResponse(
        status_code=response.status_code,
        content=response.to_dict(),
    )

