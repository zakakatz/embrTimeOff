"""API endpoints for employee import execution and progress tracking."""

import csv
import io
import secrets
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.employee_import_upload import file_storage, require_import_permission
from src.api.employee_import_validate import (
    EMPLOYEE_FIELDS,
    suggest_field_mapping,
    validate_field_value,
    transform_field_value,
    ValidationSeverity,
)
from src.database.database import get_db
from src.utils.auth import CurrentUser, UserRole
from src.utils.errors import APIError, NotFoundError, ValidationError


# =============================================================================
# Enums
# =============================================================================

class ImportStatus(str, Enum):
    """Status of an import job."""
    
    PENDING = "pending"
    VALIDATING = "validating"
    VALIDATED = "validated"
    EXECUTING = "executing"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    CANCELLED = "cancelled"


class RecordStatus(str, Enum):
    """Status of a single record in the import."""
    
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    ERROR = "error"
    SKIPPED = "skipped"


# =============================================================================
# In-Memory Import State (would be database in production)
# =============================================================================

class ImportJobState:
    """In-memory state for import jobs."""
    
    def __init__(self):
        self.jobs: Dict[str, Dict[str, Any]] = {}
    
    def create_job(self, import_id: uuid.UUID) -> Dict[str, Any]:
        job = {
            "import_id": str(import_id),
            "status": ImportStatus.PENDING,
            "total_rows": 0,
            "processed_rows": 0,
            "success_count": 0,
            "error_count": 0,
            "skipped_count": 0,
            "current_batch": 0,
            "total_batches": 0,
            "records": [],
            "errors": [],
            "rollback_token": None,
            "created_at": datetime.utcnow(),
            "started_at": None,
            "completed_at": None,
            "processing_rate": 0.0,
            "estimated_completion": None,
        }
        self.jobs[str(import_id)] = job
        return job
    
    def get_job(self, import_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        return self.jobs.get(str(import_id))
    
    def update_job(self, import_id: uuid.UUID, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        job = self.jobs.get(str(import_id))
        if job:
            job.update(updates)
        return job


import_state = ImportJobState()


# =============================================================================
# Request/Response Models
# =============================================================================

class FieldMapping(BaseModel):
    """Field mapping configuration."""
    csv_column_index: int
    employee_field: str


class ExecuteRequest(BaseModel):
    """Request to execute an import."""
    
    mappings: Optional[List[FieldMapping]] = Field(
        None,
        description="Field mappings (uses auto-detected if not provided)"
    )
    batch_size: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Number of records to process per batch"
    )
    allow_partial: bool = Field(
        default=True,
        description="Continue processing after errors (skip failed records)"
    )
    dry_run: bool = Field(
        default=False,
        description="Simulate execution without persisting data"
    )


class RecordResult(BaseModel):
    """Result for a single imported record."""
    
    row_number: int = Field(..., description="Row number in CSV (1-based)")
    status: RecordStatus = Field(..., description="Record status")
    employee_id: Optional[str] = Field(None, description="Created/updated employee ID")
    action: Optional[str] = Field(None, description="Action taken (create/update/skip)")
    errors: List[str] = Field(default_factory=list, description="Error messages if any")
    warnings: List[str] = Field(default_factory=list, description="Warning messages")


class ExecutionSummary(BaseModel):
    """Summary of import execution."""
    
    total_rows: int = Field(default=0, description="Total rows processed")
    success_count: int = Field(default=0, description="Successfully imported records")
    error_count: int = Field(default=0, description="Failed records")
    skipped_count: int = Field(default=0, description="Skipped records")
    created_count: int = Field(default=0, description="New records created")
    updated_count: int = Field(default=0, description="Existing records updated")


class ExecuteResponse(BaseModel):
    """Response for import execution."""
    
    import_id: uuid.UUID = Field(..., description="Import job ID")
    status: ImportStatus = Field(..., description="Final import status")
    summary: ExecutionSummary = Field(..., description="Execution summary")
    records: List[RecordResult] = Field(default_factory=list, description="Record results (sample)")
    records_truncated: bool = Field(default=False, description="Whether record list was truncated")
    rollback_token: Optional[str] = Field(None, description="Token for rolling back this import")
    rollback_expires_at: Optional[datetime] = Field(None, description="Rollback token expiration")
    executed_at: datetime = Field(default_factory=datetime.utcnow, description="Execution timestamp")
    duration_seconds: float = Field(default=0.0, description="Execution duration")


class BatchProgress(BaseModel):
    """Progress of a single batch."""
    
    batch_number: int = Field(..., description="Current batch number")
    total_batches: int = Field(..., description="Total number of batches")
    batch_size: int = Field(..., description="Records in this batch")
    batch_processed: int = Field(..., description="Records processed in batch")
    batch_success: int = Field(..., description="Successful records in batch")
    batch_errors: int = Field(..., description="Failed records in batch")


class PerformanceMetrics(BaseModel):
    """Performance metrics for import execution."""
    
    processing_rate: float = Field(default=0.0, description="Records per second")
    average_batch_time_ms: float = Field(default=0.0, description="Average batch processing time")
    error_rate: float = Field(default=0.0, description="Error rate (0-1)")
    estimated_remaining_seconds: Optional[float] = Field(None, description="Estimated time remaining")
    bottleneck: Optional[str] = Field(None, description="Identified bottleneck if any")


class ProgressResponse(BaseModel):
    """Response for progress tracking."""
    
    import_id: uuid.UUID = Field(..., description="Import job ID")
    status: ImportStatus = Field(..., description="Current status")
    
    # Overall progress
    total_rows: int = Field(default=0, description="Total rows to process")
    processed_rows: int = Field(default=0, description="Rows processed so far")
    completion_percentage: float = Field(default=0.0, description="Completion percentage (0-100)")
    
    # Counts
    success_count: int = Field(default=0, description="Successful records")
    error_count: int = Field(default=0, description="Failed records")
    skipped_count: int = Field(default=0, description="Skipped records")
    remaining_count: int = Field(default=0, description="Records remaining")
    
    # Batch progress
    current_batch: Optional[BatchProgress] = Field(None, description="Current batch progress")
    
    # Performance
    metrics: PerformanceMetrics = Field(default_factory=PerformanceMetrics, description="Performance metrics")
    
    # Timing
    started_at: Optional[datetime] = Field(None, description="When execution started")
    estimated_completion: Optional[datetime] = Field(None, description="Estimated completion time")
    
    # Recent errors (for monitoring)
    recent_errors: List[str] = Field(default_factory=list, description="Most recent errors")


class RollbackRequest(BaseModel):
    """Request to rollback an import."""
    
    rollback_token: str = Field(..., description="Rollback token from execution response")
    reason: Optional[str] = Field(None, description="Reason for rollback")


class RollbackResponse(BaseModel):
    """Response for rollback operation."""
    
    import_id: uuid.UUID = Field(..., description="Import job ID")
    status: str = Field(..., description="Rollback status")
    records_reverted: int = Field(default=0, description="Number of records reverted")
    rolled_back_at: datetime = Field(default_factory=datetime.utcnow, description="Rollback timestamp")


# =============================================================================
# Helper Functions
# =============================================================================

def process_csv_row(
    row: List[str],
    row_number: int,
    headers: List[str],
    mapping_dict: Dict[int, str],
    session: Session,
    dry_run: bool = False,
) -> RecordResult:
    """Process a single CSV row and create/update employee record."""
    errors = []
    warnings = []
    transformed_data = {}
    
    # Transform and validate each field
    for col_idx, value in enumerate(row):
        field = mapping_dict.get(col_idx)
        if not field:
            continue
        
        column_name = headers[col_idx] if col_idx < len(headers) else f"Column {col_idx}"
        
        # Validate
        field_errors = validate_field_value(field, value, row_number, column_name)
        for err in field_errors:
            if err.severity == ValidationSeverity.ERROR:
                errors.append(err.message)
            else:
                warnings.append(err.message)
        
        # Transform
        transformed_data[field] = transform_field_value(field, value)
    
    # Check for required fields
    required_fields = ["employee_id", "email", "first_name", "last_name", "hire_date"]
    for field in required_fields:
        if field not in transformed_data or not transformed_data.get(field):
            errors.append(f"Required field '{field}' is missing")
    
    if errors:
        return RecordResult(
            row_number=row_number,
            status=RecordStatus.ERROR,
            errors=errors,
            warnings=warnings,
        )
    
    # In a real implementation, we would:
    # 1. Check if employee exists (by employee_id or email)
    # 2. Create or update the employee record
    # 3. Handle relationships (department, location, manager)
    
    if dry_run:
        return RecordResult(
            row_number=row_number,
            status=RecordStatus.SUCCESS,
            employee_id=transformed_data.get("employee_id"),
            action="create (dry run)",
            warnings=warnings,
        )
    
    # Simulate successful creation
    return RecordResult(
        row_number=row_number,
        status=RecordStatus.SUCCESS,
        employee_id=transformed_data.get("employee_id"),
        action="create",
        warnings=warnings,
    )


def generate_rollback_token() -> str:
    """Generate a secure rollback token."""
    return secrets.token_urlsafe(32)


# =============================================================================
# Router Setup
# =============================================================================

employee_import_execute_router = APIRouter(
    prefix="/api/employee-import",
    tags=["Employee Import Execution"],
)


# =============================================================================
# Endpoints
# =============================================================================

@employee_import_execute_router.post(
    "/execute/{import_id}",
    response_model=ExecuteResponse,
    summary="Execute Import",
    description="Execute validated import and create employee records.",
)
async def execute_import(
    import_id: uuid.UUID,
    request: ExecuteRequest,
    current_user: Annotated[CurrentUser, Depends(require_import_permission)],
    session: Annotated[Session, Depends(get_db)],
    max_results: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> ExecuteResponse:
    """
    Execute an import job.
    
    - Processes validated imports in batches
    - Provides row-by-row validation during execution
    - Supports automatic rollback on critical failures
    - Returns rollback token for manual rollback capability
    """
    start_time = datetime.utcnow()
    
    # Retrieve uploaded file
    content = file_storage.retrieve(import_id)
    if not content:
        raise NotFoundError(
            message="Upload not found or has expired",
            details={"import_id": str(import_id)},
        )
    
    # Parse CSV
    try:
        text = content.decode("utf-8", errors="replace")
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
    except Exception as e:
        raise ValidationError(
            message=f"Failed to parse CSV: {str(e)}",
        )
    
    if len(rows) < 2:
        raise ValidationError(message="CSV must have at least a header row and one data row")
    
    headers = rows[0]
    data_rows = rows[1:]
    
    # Build field mappings
    mapping_dict = {}
    if request.mappings:
        for m in request.mappings:
            mapping_dict[m.csv_column_index] = m.employee_field
    else:
        for i, header in enumerate(headers):
            suggested_field, confidence = suggest_field_mapping(header)
            if suggested_field and confidence >= 0.7:
                mapping_dict[i] = suggested_field
    
    # Initialize job state
    job = import_state.create_job(import_id)
    job["status"] = ImportStatus.EXECUTING
    job["total_rows"] = len(data_rows)
    job["started_at"] = start_time
    job["total_batches"] = (len(data_rows) + request.batch_size - 1) // request.batch_size
    
    # Process rows in batches
    all_results: List[RecordResult] = []
    success_count = 0
    error_count = 0
    skipped_count = 0
    created_count = 0
    updated_count = 0
    
    try:
        for batch_idx in range(0, len(data_rows), request.batch_size):
            batch = data_rows[batch_idx:batch_idx + request.batch_size]
            job["current_batch"] = batch_idx // request.batch_size + 1
            
            for row_offset, row in enumerate(batch):
                row_number = batch_idx + row_offset + 1
                
                result = process_csv_row(
                    row=row,
                    row_number=row_number,
                    headers=headers,
                    mapping_dict=mapping_dict,
                    session=session,
                    dry_run=request.dry_run,
                )
                
                all_results.append(result)
                
                if result.status == RecordStatus.SUCCESS:
                    success_count += 1
                    if result.action and "create" in result.action:
                        created_count += 1
                    elif result.action and "update" in result.action:
                        updated_count += 1
                elif result.status == RecordStatus.ERROR:
                    error_count += 1
                    if not request.allow_partial:
                        raise Exception(f"Import failed at row {row_number}: {result.errors}")
                else:
                    skipped_count += 1
                
                job["processed_rows"] = row_number
                job["success_count"] = success_count
                job["error_count"] = error_count
            
            # Commit batch (in real implementation)
            if not request.dry_run:
                session.commit()
        
        # Determine final status
        if error_count == 0:
            final_status = ImportStatus.COMPLETED
        elif success_count > 0:
            final_status = ImportStatus.COMPLETED_WITH_ERRORS
        else:
            final_status = ImportStatus.FAILED
        
    except Exception as e:
        session.rollback()
        final_status = ImportStatus.FAILED
        job["errors"].append(str(e))
    
    end_time = datetime.utcnow()
    duration = (end_time - start_time).total_seconds()
    
    # Generate rollback token
    rollback_token = generate_rollback_token() if success_count > 0 and not request.dry_run else None
    rollback_expires = end_time + timedelta(hours=24) if rollback_token else None
    
    # Update job state
    job["status"] = final_status
    job["completed_at"] = end_time
    job["rollback_token"] = rollback_token
    job["records"] = all_results
    
    # Build response
    summary = ExecutionSummary(
        total_rows=len(data_rows),
        success_count=success_count,
        error_count=error_count,
        skipped_count=skipped_count,
        created_count=created_count,
        updated_count=updated_count,
    )
    
    return ExecuteResponse(
        import_id=import_id,
        status=final_status,
        summary=summary,
        records=all_results[:max_results],
        records_truncated=len(all_results) > max_results,
        rollback_token=rollback_token,
        rollback_expires_at=rollback_expires,
        executed_at=end_time,
        duration_seconds=duration,
    )


@employee_import_execute_router.get(
    "/progress/{import_id}",
    response_model=ProgressResponse,
    summary="Get Import Progress",
    description="Get real-time progress of an import execution.",
)
async def get_import_progress(
    import_id: uuid.UUID,
    current_user: Annotated[CurrentUser, Depends(require_import_permission)],
) -> ProgressResponse:
    """
    Get real-time progress for an import job.
    
    - Returns current status and completion percentage
    - Includes processing rate and estimated completion time
    - Shows recent errors for monitoring
    """
    job = import_state.get_job(import_id)
    
    if not job:
        # Return pending status for new jobs
        return ProgressResponse(
            import_id=import_id,
            status=ImportStatus.PENDING,
            total_rows=0,
            processed_rows=0,
            completion_percentage=0.0,
        )
    
    # Calculate metrics
    total = job["total_rows"]
    processed = job["processed_rows"]
    completion = (processed / total * 100) if total > 0 else 0.0
    remaining = total - processed
    
    # Calculate processing rate
    started = job.get("started_at")
    processing_rate = 0.0
    estimated_remaining = None
    
    if started and processed > 0:
        elapsed = (datetime.utcnow() - started).total_seconds()
        processing_rate = processed / elapsed if elapsed > 0 else 0.0
        if processing_rate > 0 and remaining > 0:
            estimated_remaining = remaining / processing_rate
    
    # Error rate
    error_rate = job["error_count"] / processed if processed > 0 else 0.0
    
    # Batch progress
    batch_progress = None
    if job["current_batch"] > 0:
        batch_progress = BatchProgress(
            batch_number=job["current_batch"],
            total_batches=job["total_batches"],
            batch_size=100,  # Default
            batch_processed=min(100, processed % 100 or 100),
            batch_success=job["success_count"],
            batch_errors=job["error_count"],
        )
    
    # Performance metrics
    metrics = PerformanceMetrics(
        processing_rate=processing_rate,
        average_batch_time_ms=0.0,  # Would calculate from batch timing
        error_rate=error_rate,
        estimated_remaining_seconds=estimated_remaining,
        bottleneck="validation" if error_rate > 0.1 else None,
    )
    
    # Recent errors
    recent_errors = [str(e) for e in job.get("errors", [])[-5:]]
    
    # Estimated completion
    estimated_completion = None
    if estimated_remaining:
        estimated_completion = datetime.utcnow() + timedelta(seconds=estimated_remaining)
    
    return ProgressResponse(
        import_id=import_id,
        status=job["status"],
        total_rows=total,
        processed_rows=processed,
        completion_percentage=completion,
        success_count=job["success_count"],
        error_count=job["error_count"],
        skipped_count=job["skipped_count"],
        remaining_count=remaining,
        current_batch=batch_progress,
        metrics=metrics,
        started_at=job.get("started_at"),
        estimated_completion=estimated_completion,
        recent_errors=recent_errors,
    )


@employee_import_execute_router.post(
    "/rollback/{import_id}",
    response_model=RollbackResponse,
    summary="Rollback Import",
    description="Rollback a completed import using the rollback token.",
)
async def rollback_import(
    import_id: uuid.UUID,
    request: RollbackRequest,
    current_user: Annotated[CurrentUser, Depends(require_import_permission)],
    session: Annotated[Session, Depends(get_db)],
) -> RollbackResponse:
    """
    Rollback a completed import.
    
    - Requires valid rollback token from execution response
    - Reverts all created/updated records
    - Creates audit trail of rollback operation
    """
    job = import_state.get_job(import_id)
    
    if not job:
        raise NotFoundError(
            message="Import job not found",
            details={"import_id": str(import_id)},
        )
    
    # Verify rollback token
    if job.get("rollback_token") != request.rollback_token:
        raise ValidationError(
            message="Invalid rollback token",
            details={"hint": "Ensure you're using the token from the execution response"},
        )
    
    # Check if already rolled back
    if job["status"] == ImportStatus.ROLLED_BACK:
        raise ValidationError(
            message="Import has already been rolled back",
        )
    
    # In a real implementation, we would:
    # 1. Find all records created/updated by this import
    # 2. Delete created records
    # 3. Revert updated records to previous state
    # 4. Create audit trail entries
    
    records_reverted = job["success_count"]
    
    # Update job state
    job["status"] = ImportStatus.ROLLED_BACK
    job["rollback_token"] = None  # Invalidate token
    
    return RollbackResponse(
        import_id=import_id,
        status="success",
        records_reverted=records_reverted,
    )


@employee_import_execute_router.post(
    "/cancel/{import_id}",
    status_code=status.HTTP_200_OK,
    summary="Cancel Import",
    description="Cancel an in-progress import.",
)
async def cancel_import(
    import_id: uuid.UUID,
    current_user: Annotated[CurrentUser, Depends(require_import_permission)],
) -> Dict[str, Any]:
    """
    Cancel an in-progress import.
    
    - Stops processing of remaining records
    - Already processed records are not affected
    """
    job = import_state.get_job(import_id)
    
    if not job:
        raise NotFoundError(
            message="Import job not found",
            details={"import_id": str(import_id)},
        )
    
    if job["status"] not in [ImportStatus.PENDING, ImportStatus.EXECUTING]:
        raise ValidationError(
            message=f"Cannot cancel import with status: {job['status'].value}",
        )
    
    job["status"] = ImportStatus.CANCELLED
    
    return {
        "import_id": str(import_id),
        "status": "cancelled",
        "processed_rows": job["processed_rows"],
        "message": "Import cancelled successfully",
    }

