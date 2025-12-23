"""Background tasks for employee import processing.

These tasks are designed to be executed asynchronously using a task queue
system like Celery or RQ. For now, they provide the core logic that can
be wrapped in the appropriate task decorator when a queue is configured.
"""

import logging
import time
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from src.database.database import get_db_context
from src.models.import_audit import ActorRole
from src.models.import_job import ImportJob, ImportJobStatus
from src.models.import_row import ImportRow, ValidationStatus
from src.models.validation_error import ErrorType, ImportValidationError, Severity
from src.utils.audit_logger import ImportExportAuditContext, ImportExportAuditLogger
from src.utils.csv_parser import parse_csv_content


logger = logging.getLogger(__name__)


def validate_import_job(
    import_job_id: uuid.UUID,
    file_content: bytes,
    user_id: uuid.UUID,
) -> Dict[str, Any]:
    """
    Background task to validate an import job.
    
    This task performs comprehensive validation of the CSV file including:
    - Format validation
    - Data type checking
    - Business rule validation
    - Duplicate detection
    
    Args:
        import_job_id: UUID of the import job
        file_content: Raw CSV file content
        user_id: UUID of the user who initiated the import
    
    Returns:
        Dictionary with validation results
    """
    logger.info(f"Starting validation for import job {import_job_id}")
    start_time = time.time()
    
    with get_db_context() as session:
        # Get import job
        import_job = session.get(ImportJob, import_job_id)
        if import_job is None:
            logger.error(f"Import job {import_job_id} not found")
            return {"error": "Import job not found"}
        
        # Update status
        import_job.status = ImportJobStatus.VALIDATING
        session.flush()
        
        # Create audit context
        audit_context = ImportExportAuditContext(
            user_id=user_id,
            operation_type="import",
            actor_role=ActorRole.SYSTEM,
        )
        audit_logger = ImportExportAuditLogger(session)
        
        try:
            # Parse CSV
            config = import_job.mapping_config or {}
            delimiter = config.get("delimiter", ",")
            field_mappings = import_job.field_mappings
            
            parse_result = parse_csv_content(
                content=file_content,
                delimiter=delimiter,
                custom_mappings=field_mappings,
            )
            
            # Store validation results
            valid_count = 0
            error_count = 0
            
            for row in parse_result.rows:
                # Create ImportRow record
                import_row = ImportRow(
                    import_job_id=import_job.id,
                    row_number=row.row_number,
                    source_data=row.data,
                    mapped_data=row.data if row.is_valid else None,
                    validation_status=(
                        ValidationStatus.VALID if row.is_valid
                        else ValidationStatus.INVALID
                    ),
                    error_details=[e.model_dump() for e in row.errors] if row.errors else None,
                )
                session.add(import_row)
                session.flush()
                
                # Create validation error records
                for field_error in row.errors:
                    validation_error = ImportValidationError(
                        import_job_id=import_job.id,
                        row_id=import_row.id,
                        error_type=ErrorType.DATA_TYPE,
                        severity=Severity.ERROR,
                        error_code=field_error.code,
                        error_message=field_error.message,
                        field_name=field_error.field,
                        field_value=field_error.value,
                        suggested_correction=field_error.suggestion,
                    )
                    session.add(validation_error)
                
                if row.is_valid:
                    valid_count += 1
                else:
                    error_count += 1
            
            # Update import job
            import_job.total_rows = parse_result.total_rows
            import_job.status = ImportJobStatus.MAPPING
            import_job.validation_errors = [
                {
                    "row": row.row_number,
                    "errors": [e.model_dump() for e in row.errors],
                }
                for row in parse_result.rows if not row.is_valid
            ]
            
            # Log validation completion
            duration = time.time() - start_time
            audit_logger.log_import_validated(
                import_job_id=import_job.id,
                context=audit_context,
                total_rows=parse_result.total_rows,
                valid_rows=valid_count,
                error_rows=error_count,
            )
            
            logger.info(
                f"Validation completed for job {import_job_id}: "
                f"{valid_count} valid, {error_count} errors in {duration:.2f}s"
            )
            
            return {
                "import_job_id": str(import_job_id),
                "status": "validated",
                "total_rows": parse_result.total_rows,
                "valid_rows": valid_count,
                "error_rows": error_count,
                "duration_seconds": duration,
            }
            
        except Exception as e:
            logger.exception(f"Validation failed for job {import_job_id}: {e}")
            import_job.status = ImportJobStatus.FAILED
            
            audit_logger.log_import_failed(
                import_job_id=import_job.id,
                context=audit_context,
                error_message=str(e),
            )
            
            return {
                "import_job_id": str(import_job_id),
                "status": "failed",
                "error": str(e),
            }


def process_import_job(
    import_job_id: uuid.UUID,
    file_content: bytes,
    user_id: uuid.UUID,
) -> Dict[str, Any]:
    """
    Background task to process an import job and create employee records.
    
    This task:
    - Reads validated rows from the import job
    - Creates Employee records for valid rows
    - Updates import job progress in real-time
    - Handles partial imports (continues on individual row failures)
    
    Args:
        import_job_id: UUID of the import job
        file_content: Raw CSV file content
        user_id: UUID of the user who initiated the import
    
    Returns:
        Dictionary with processing results
    """
    logger.info(f"Starting processing for import job {import_job_id}")
    start_time = time.time()
    
    with get_db_context() as session:
        from src.models.employee import Employee
        
        # Get import job
        import_job = session.get(ImportJob, import_job_id)
        if import_job is None:
            logger.error(f"Import job {import_job_id} not found")
            return {"error": "Import job not found"}
        
        # Check status
        if import_job.status not in [ImportJobStatus.MAPPING, ImportJobStatus.PENDING]:
            logger.warning(f"Import job {import_job_id} in unexpected status: {import_job.status}")
            return {"error": f"Cannot process job in status: {import_job.status.value}"}
        
        # Update status
        import_job.status = ImportJobStatus.PROCESSING
        import_job.started_at = datetime.utcnow()
        session.flush()
        
        # Create audit context
        audit_context = ImportExportAuditContext(
            user_id=user_id,
            operation_type="import",
            actor_role=ActorRole.SYSTEM,
        )
        audit_logger = ImportExportAuditLogger(session)
        
        # Log processing start
        audit_logger.log_import_processing_started(
            import_job_id=import_job.id,
            context=audit_context,
            total_rows=import_job.total_rows,
        )
        
        try:
            # Parse CSV
            config = import_job.mapping_config or {}
            delimiter = config.get("delimiter", ",")
            allow_partial = config.get("allow_partial_import", True)
            field_mappings = import_job.field_mappings
            
            parse_result = parse_csv_content(
                content=file_content,
                delimiter=delimiter,
                custom_mappings=field_mappings,
            )
            
            # Process rows
            successful = 0
            errors = 0
            
            for row in parse_result.rows:
                import_job.processed_rows += 1
                
                if not row.is_valid:
                    errors += 1
                    import_job.error_rows += 1
                    continue
                
                try:
                    # Create employee
                    employee = Employee(
                        employee_id=row.data.get("employee_id"),
                        email=row.data.get("email"),
                        first_name=row.data.get("first_name"),
                        middle_name=row.data.get("middle_name"),
                        last_name=row.data.get("last_name"),
                        preferred_name=row.data.get("preferred_name"),
                        date_of_birth=row.data.get("date_of_birth"),
                        gender=row.data.get("gender"),
                        personal_email=row.data.get("personal_email"),
                        phone_number=row.data.get("phone_number"),
                        mobile_number=row.data.get("mobile_number"),
                        address_line1=row.data.get("address_line1"),
                        address_line2=row.data.get("address_line2"),
                        city=row.data.get("city"),
                        state_province=row.data.get("state_province"),
                        postal_code=row.data.get("postal_code"),
                        country=row.data.get("country"),
                        department_id=row.data.get("department_id"),
                        manager_id=row.data.get("manager_id"),
                        location_id=row.data.get("location_id"),
                        work_schedule_id=row.data.get("work_schedule_id"),
                        job_title=row.data.get("job_title"),
                        employment_type=row.data.get("employment_type"),
                        employment_status=row.data.get("employment_status", "active"),
                        hire_date=row.data.get("hire_date"),
                        termination_date=row.data.get("termination_date"),
                        salary=row.data.get("salary"),
                        hourly_rate=row.data.get("hourly_rate"),
                    )
                    session.add(employee)
                    session.flush()
                    
                    successful += 1
                    import_job.successful_rows += 1
                    
                except Exception as e:
                    logger.warning(f"Failed to create employee for row {row.row_number}: {e}")
                    errors += 1
                    import_job.error_rows += 1
                    
                    if not allow_partial:
                        raise
                
                # Periodic flush for progress tracking
                if import_job.processed_rows % 100 == 0:
                    session.flush()
            
            # Complete the job
            import_job.completed_at = datetime.utcnow()
            import_job.status = (
                ImportJobStatus.COMPLETED if errors == 0
                else ImportJobStatus.COMPLETED if successful > 0
                else ImportJobStatus.FAILED
            )
            
            duration = (import_job.completed_at - import_job.started_at).total_seconds()
            
            # Log completion
            audit_logger.log_import_completed(
                import_job_id=import_job.id,
                context=audit_context,
                successful_rows=successful,
                error_rows=errors,
                duration_seconds=duration,
            )
            
            logger.info(
                f"Processing completed for job {import_job_id}: "
                f"{successful} successful, {errors} errors in {duration:.2f}s"
            )
            
            return {
                "import_job_id": str(import_job_id),
                "status": import_job.status.value,
                "successful_rows": successful,
                "error_rows": errors,
                "duration_seconds": duration,
            }
            
        except Exception as e:
            logger.exception(f"Processing failed for job {import_job_id}: {e}")
            import_job.status = ImportJobStatus.FAILED
            import_job.completed_at = datetime.utcnow()
            
            audit_logger.log_import_failed(
                import_job_id=import_job.id,
                context=audit_context,
                error_message=str(e),
                processed_rows=import_job.processed_rows,
            )
            
            return {
                "import_job_id": str(import_job_id),
                "status": "failed",
                "error": str(e),
            }

