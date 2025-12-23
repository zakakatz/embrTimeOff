"""API endpoints for document generation and file processing."""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Query, BackgroundTasks
from fastapi.responses import StreamingResponse, Response

from src.schemas.document_generation import (
    DocumentGenerationRequest,
    DocumentGenerationResponse,
    DocumentStatusResponse,
    TemplateRenderRequest,
    TemplateRenderResponse,
    FileValidationResponse,
    FileUploadResponse,
    StoredFileInfo,
    StorageStatsResponse,
    AvailableTemplatesResponse,
    SupportedFormatsResponse,
    ValidationIssue,
    ValidationSeverityEnum,
    DocumentStatusEnum,
    DocumentFormatEnum,
)
from src.services.document_generation import (
    DocumentGenerator,
    PDFService,
    FileValidator,
    FileStorageManager,
    TemplateEngine,
)
from src.services.document_generation.document_generator import (
    DocumentGenerationRequest as ServiceRequest,
    DocumentFormat,
    DocumentColumn,
)
from src.services.document_generation.pdf_service import (
    PDFConfig,
    PageSize,
    PageOrientation,
    PageMargins,
    PDFMetadata,
)
from src.services.document_generation.file_validator import (
    FileValidationConfig,
    ValidationResult,
)
from src.services.document_generation.file_storage_manager import StorageConfig

logger = logging.getLogger(__name__)

# Initialize services
template_engine = TemplateEngine()
pdf_service = PDFService(template_engine)
document_generator = DocumentGenerator(template_engine, pdf_service)
file_validator = FileValidator()
file_storage = FileStorageManager()

# Create router
documents_router = APIRouter(prefix="/api/v1/documents", tags=["Documents"])


# =============================================================================
# Document Generation Endpoints
# =============================================================================

@documents_router.post(
    "/generate",
    response_model=DocumentGenerationResponse,
    summary="Generate a document",
    description="Generate a document in the specified format from data or template."
)
async def generate_document(
    request: DocumentGenerationRequest,
    background_tasks: BackgroundTasks
) -> DocumentGenerationResponse:
    """
    Generate a document synchronously.
    
    Supports PDF, CSV, Excel, JSON, and HTML formats.
    """
    try:
        # Convert API request to service request
        columns = [
            DocumentColumn(
                key=col.key,
                header=col.header,
                width=col.width,
                format_type=col.format_type,
                alignment=col.alignment,
                visible=col.visible,
            )
            for col in request.columns
        ]
        
        pdf_config = None
        if request.pdf_config:
            pdf_config = PDFConfig(
                page_size=PageSize(request.pdf_config.page_size.value),
                orientation=PageOrientation(request.pdf_config.orientation.value),
                margins=PageMargins(
                    top=request.pdf_config.margins.top if request.pdf_config.margins else 25.0,
                    right=request.pdf_config.margins.right if request.pdf_config.margins else 25.0,
                    bottom=request.pdf_config.margins.bottom if request.pdf_config.margins else 25.0,
                    left=request.pdf_config.margins.left if request.pdf_config.margins else 25.0,
                ) if request.pdf_config.margins else None,
                metadata=PDFMetadata(
                    title=request.pdf_config.metadata.title if request.pdf_config.metadata else request.title,
                    author=request.pdf_config.metadata.author if request.pdf_config.metadata else "",
                ) if request.pdf_config.metadata else None,
                header_template=request.pdf_config.header_template,
                footer_template=request.pdf_config.footer_template,
                include_page_numbers=request.pdf_config.include_page_numbers,
                base_font_size=request.pdf_config.base_font_size,
            )
        
        service_request = ServiceRequest(
            format=DocumentFormat(request.format.value),
            template_name=request.template_name,
            data=request.data,
            columns=columns,
            title=request.title,
            filename=request.filename,
            pdf_config=pdf_config,
            include_headers=request.include_headers,
            sheet_name=request.sheet_name,
        )
        
        result = document_generator.generate(service_request)
        
        # Store the generated document
        if result.content:
            stored = file_storage.store(
                content=result.content,
                filename=result.filename,
                content_type=result.content_type,
                ttl_hours=24,  # Documents expire after 24 hours
            )
            download_url = f"/api/v1/documents/download/{stored.id}"
        else:
            download_url = None
        
        return DocumentGenerationResponse(
            id=result.id,
            status=DocumentStatusEnum(result.status.value),
            format=DocumentFormatEnum(result.format.value),
            filename=result.filename,
            content_type=result.content_type,
            size_bytes=result.size_bytes,
            download_url=download_url,
            error_message=result.error_message,
            created_at=result.created_at,
            completed_at=result.completed_at,
            progress=result.progress,
        )
        
    except Exception as e:
        logger.exception("Document generation failed")
        raise HTTPException(status_code=500, detail=str(e))


@documents_router.get(
    "/status/{task_id}",
    response_model=DocumentStatusResponse,
    summary="Get generation status",
    description="Check the status of a document generation task."
)
async def get_generation_status(task_id: str) -> DocumentStatusResponse:
    """Get the status of a document generation task."""
    result = document_generator.get_task_status(task_id)
    
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return DocumentStatusResponse(
        id=result.id,
        status=DocumentStatusEnum(result.status.value),
        progress=result.progress,
        error_message=result.error_message,
        download_ready=result.status.value == "completed" and result.content is not None,
    )


@documents_router.get(
    "/download/{file_id}",
    summary="Download generated document",
    description="Download a generated document by its file ID."
)
async def download_document(file_id: str):
    """Download a generated or uploaded document."""
    stored_file = file_storage.get_file_info(file_id)
    
    if not stored_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    if stored_file.is_expired:
        file_storage.delete(file_id)
        raise HTTPException(status_code=410, detail="File has expired")
    
    content = file_storage.retrieve(file_id)
    if not content:
        raise HTTPException(status_code=404, detail="File content not found")
    
    return Response(
        content=content,
        media_type=stored_file.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{stored_file.filename}"',
            "Content-Length": str(stored_file.size_bytes),
        }
    )


@documents_router.delete(
    "/cancel/{task_id}",
    summary="Cancel generation task",
    description="Cancel a pending or in-progress document generation task."
)
async def cancel_generation(task_id: str) -> dict:
    """Cancel a document generation task."""
    if document_generator.cancel_task(task_id):
        return {"message": "Task cancelled", "task_id": task_id}
    raise HTTPException(
        status_code=400,
        detail="Task not found or already completed"
    )


# =============================================================================
# Template Endpoints
# =============================================================================

@documents_router.post(
    "/templates/render",
    response_model=TemplateRenderResponse,
    summary="Render a template",
    description="Render a template string with provided context data."
)
async def render_template(request: TemplateRenderRequest) -> TemplateRenderResponse:
    """Render a template with context data."""
    try:
        # Validate template first
        errors = template_engine.validate_template(request.template)
        if errors:
            return TemplateRenderResponse(
                rendered="",
                success=False,
                errors=errors,
            )
        
        rendered = template_engine.render(request.template, request.context)
        return TemplateRenderResponse(
            rendered=rendered,
            success=True,
            errors=[],
        )
    except Exception as e:
        return TemplateRenderResponse(
            rendered="",
            success=False,
            errors=[str(e)],
        )


@documents_router.get(
    "/templates",
    response_model=AvailableTemplatesResponse,
    summary="List available templates",
    description="Get a list of built-in document templates."
)
async def list_templates() -> AvailableTemplatesResponse:
    """List available document templates."""
    templates = [
        {
            "name": "employee_report",
            "description": "Employee profile report with personal and organizational information",
            "formats": ["pdf", "html"],
        },
        {
            "name": "time_off_summary",
            "description": "Time-off balance and request summary report",
            "formats": ["pdf", "csv", "xlsx"],
        },
        {
            "name": "org_chart",
            "description": "Organizational chart and team structure",
            "formats": ["pdf", "html"],
        },
        {
            "name": "audit_report",
            "description": "Audit trail report with change history",
            "formats": ["pdf", "csv", "xlsx"],
        },
    ]
    return AvailableTemplatesResponse(templates=templates)


@documents_router.get(
    "/formats",
    response_model=SupportedFormatsResponse,
    summary="List supported formats",
    description="Get a list of supported document output formats."
)
async def list_formats() -> SupportedFormatsResponse:
    """List supported document formats."""
    formats = [
        {
            "format": "pdf",
            "extension": ".pdf",
            "mime_type": "application/pdf",
            "description": "PDF document with template support",
        },
        {
            "format": "csv",
            "extension": ".csv",
            "mime_type": "text/csv",
            "description": "Comma-separated values",
        },
        {
            "format": "xlsx",
            "extension": ".xlsx",
            "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "description": "Excel spreadsheet with formatting",
        },
        {
            "format": "json",
            "extension": ".json",
            "mime_type": "application/json",
            "description": "JSON data export",
        },
        {
            "format": "html",
            "extension": ".html",
            "mime_type": "text/html",
            "description": "HTML document",
        },
    ]
    return SupportedFormatsResponse(formats=formats)


# =============================================================================
# File Validation Endpoints
# =============================================================================

@documents_router.post(
    "/validate",
    response_model=FileValidationResponse,
    summary="Validate a file",
    description="Validate an uploaded file for type, size, and content integrity."
)
async def validate_file(
    file: UploadFile = File(...),
    max_size_mb: Optional[float] = Query(default=None, description="Max size in MB")
) -> FileValidationResponse:
    """Validate an uploaded file."""
    content = await file.read()
    
    # Configure validation
    config = FileValidationConfig()
    if max_size_mb:
        config.max_file_size = int(max_size_mb * 1024 * 1024)
    
    validator = FileValidator(config)
    result = validator.validate(
        file_content=content,
        filename=file.filename or "unknown",
        declared_content_type=file.content_type,
    )
    
    return FileValidationResponse(
        is_valid=result.is_valid,
        filename=result.filename,
        file_size=result.file_size,
        content_type=result.content_type,
        issues=[
            ValidationIssue(
                code=issue.code,
                message=issue.message,
                severity=ValidationSeverityEnum(issue.severity.value),
                field=issue.field,
                details=issue.details,
            )
            for issue in result.issues
        ],
        file_hash=result.file_hash,
        validated_at=result.validated_at,
    )


# =============================================================================
# File Storage Endpoints
# =============================================================================

@documents_router.post(
    "/upload",
    response_model=FileUploadResponse,
    summary="Upload a file",
    description="Upload and store a file with validation."
)
async def upload_file(
    file: UploadFile = File(...),
    ttl_hours: Optional[int] = Query(default=24, ge=1, le=168, description="Time to live in hours")
) -> FileUploadResponse:
    """Upload and store a file."""
    content = await file.read()
    filename = file.filename or "uploaded_file"
    content_type = file.content_type or "application/octet-stream"
    
    # Validate first
    validation_result = file_validator.validate(
        file_content=content,
        filename=filename,
        declared_content_type=content_type,
    )
    
    if not validation_result.is_valid:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "File validation failed",
                "issues": [
                    {"code": i.code, "message": i.message}
                    for i in validation_result.issues
                    if i.severity.value == "error"
                ],
            }
        )
    
    # Store the file
    stored = file_storage.store(
        content=content,
        filename=filename,
        content_type=validation_result.content_type,
        ttl_hours=ttl_hours,
    )
    
    return FileUploadResponse(
        file_id=stored.id,
        filename=stored.filename,
        content_type=stored.content_type,
        size_bytes=stored.size_bytes,
        hash_value=stored.hash_value,
        expires_at=stored.expires_at,
        validation=FileValidationResponse(
            is_valid=validation_result.is_valid,
            filename=validation_result.filename,
            file_size=validation_result.file_size,
            content_type=validation_result.content_type,
            issues=[
                ValidationIssue(
                    code=i.code,
                    message=i.message,
                    severity=ValidationSeverityEnum(i.severity.value),
                    field=i.field,
                    details=i.details,
                )
                for i in validation_result.issues
            ],
            file_hash=validation_result.file_hash,
            validated_at=validation_result.validated_at,
        ),
    )


@documents_router.get(
    "/files/{file_id}",
    response_model=StoredFileInfo,
    summary="Get file info",
    description="Get information about a stored file."
)
async def get_file_info(file_id: str) -> StoredFileInfo:
    """Get information about a stored file."""
    stored = file_storage.get_file_info(file_id)
    
    if not stored:
        raise HTTPException(status_code=404, detail="File not found")
    
    return StoredFileInfo(
        id=stored.id,
        filename=stored.filename,
        content_type=stored.content_type,
        size_bytes=stored.size_bytes,
        hash_value=stored.hash_value,
        created_at=stored.created_at,
        expires_at=stored.expires_at,
        is_expired=stored.is_expired,
        metadata=stored.metadata,
    )


@documents_router.delete(
    "/files/{file_id}",
    summary="Delete a file",
    description="Delete a stored file."
)
async def delete_file(file_id: str) -> dict:
    """Delete a stored file."""
    if file_storage.delete(file_id):
        return {"message": "File deleted", "file_id": file_id}
    raise HTTPException(status_code=404, detail="File not found")


@documents_router.get(
    "/storage/stats",
    response_model=StorageStatsResponse,
    summary="Get storage statistics",
    description="Get file storage statistics."
)
async def get_storage_stats() -> StorageStatsResponse:
    """Get storage statistics."""
    stats = file_storage.get_storage_stats()
    return StorageStatsResponse(
        total_files=stats["total_files"],
        total_size_bytes=stats["total_size_bytes"],
        expired_files=stats["expired_files"],
        backend=stats["backend"],
    )


@documents_router.post(
    "/storage/cleanup",
    summary="Cleanup expired files",
    description="Remove expired files from storage."
)
async def cleanup_storage() -> dict:
    """Clean up expired files."""
    count = file_storage.cleanup_expired()
    return {"message": f"Cleaned up {count} expired files", "cleaned_count": count}

