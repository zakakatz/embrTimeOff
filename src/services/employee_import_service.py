"""Service for employee CSV import operations."""

import secrets
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.config.settings import get_settings
from src.models.employee import Employee
from src.models.import_job import ImportJob, ImportJobStatus
from src.models.import_row import ImportRow, ValidationStatus
from src.models.validation_error import ErrorType, ImportValidationError, Severity
from src.schemas.employee_import import (
    ImportFieldError,
    ImportProgress,
    ImportRecordError,
    ImportResponse,
    ImportStatus,
    ImportStatusResponse,
    ImportValidationResult,
)
from src.utils.audit_logger import ImportExportAuditContext, ImportExportAuditLogger
from src.utils.auth import CurrentUser, UserRole
from src.utils.csv_parser import (
    REQUIRED_FIELDS,
    ParseResult,
    compute_file_checksum,
    parse_csv_content,
    suggest_field_mapping,
)
from src.utils.errors import (
    NotFoundError,
    ValidationError,
    create_not_found_error,
)


class EmployeeImportService:
    """
    Service for handling employee CSV import operations.
    
    Provides functionality for:
    - Creating and managing import jobs
    - Validating CSV files and data
    - Processing imports (with partial import support)
    - Tracking import progress and status
    - Error reporting with field-level details
    """
    
    def __init__(self, session: Session):
        """Initialize with database session."""
        self.session = session
        self.settings = get_settings()
        self.audit_logger = ImportExportAuditLogger(session)
    
    def _generate_reference_id(self) -> str:
        """Generate a unique human-readable reference ID."""
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        random_suffix = secrets.token_hex(4).upper()
        return f"IMP-{timestamp}-{random_suffix}"
    
    def _generate_rollback_token(self) -> str:
        """Generate a secure rollback token."""
        return secrets.token_urlsafe(32)
    
    def create_import_job(
        self,
        content: bytes,
        filename: str,
        current_user: CurrentUser,
        organization_id: uuid.UUID,
        allow_partial_import: bool = True,
        delimiter: str = ",",
        custom_mappings: Optional[Dict[str, str]] = None,
    ) -> ImportResponse:
        """
        Create a new import job from uploaded CSV content.
        
        This validates the file format and creates an import job record,
        but does not process the actual data yet.
        """
        # Validate file size
        file_size = len(content)
        max_size = 100 * 1024 * 1024  # 100MB
        if file_size > max_size:
            raise ValidationError(
                message=f"File size ({file_size} bytes) exceeds maximum allowed ({max_size} bytes)"
            )
        
        if file_size < 1:
            raise ValidationError(message="File is empty")
        
        # Compute checksum
        file_checksum = compute_file_checksum(content)
        
        # Parse CSV to validate format and get row count
        try:
            parse_result = parse_csv_content(
                content=content,
                delimiter=delimiter,
                custom_mappings=custom_mappings,
            )
        except Exception as e:
            raise ValidationError(message=f"Failed to parse CSV file: {str(e)}")
        
        # Create import job
        import_job = ImportJob(
            import_reference_id=self._generate_reference_id(),
            organization_id=organization_id,
            created_by_user_id=current_user.id,
            filename=filename,
            file_size_bytes=file_size,
            file_checksum=file_checksum,
            status=ImportJobStatus.PENDING,
            total_rows=parse_result.total_rows,
            field_mappings=custom_mappings or parse_result.suggested_mappings,
            mapping_config={
                "allow_partial_import": allow_partial_import,
                "delimiter": delimiter,
            },
            rollback_token=self._generate_rollback_token(),
            rollback_expires_at=datetime.utcnow() + timedelta(days=7),
        )
        
        self.session.add(import_job)
        
        # Create audit log
        audit_context = ImportExportAuditContext(
            user_id=current_user.id,
            operation_type="import",
            ip_address=current_user.ip_address,
            user_agent=current_user.user_agent,
        )
        self.audit_logger.log_import_created(
            import_job_id=import_job.id,
            context=audit_context,
            filename=filename,
            file_size=file_size,
        )
        
        self.session.flush()
        
        return ImportResponse(
            import_id=import_job.id,
            import_reference_id=import_job.import_reference_id,
            status=ImportStatus(import_job.status.value),
            filename=filename,
            file_size_bytes=file_size,
            created_at=import_job.created_at,
            message="Import job created successfully. Call the validate endpoint to begin processing.",
        )
    
    def validate_import(
        self,
        import_job_id: uuid.UUID,
        content: bytes,
        current_user: CurrentUser,
    ) -> ImportValidationResult:
        """
        Validate CSV content for an import job.
        
        Performs comprehensive validation including:
        - Format validation (proper CSV structure)
        - Data type checking (dates, numbers, etc.)
        - Business rule validation (required fields, unique constraints)
        """
        # Get import job
        import_job = self._get_import_job(import_job_id)
        
        # Update status
        import_job.status = ImportJobStatus.VALIDATING
        self.session.flush()
        
        # Get configuration
        config = import_job.mapping_config or {}
        delimiter = config.get("delimiter", ",")
        field_mappings = import_job.field_mappings
        
        # Parse and validate
        parse_result = parse_csv_content(
            content=content,
            delimiter=delimiter,
            custom_mappings=field_mappings,
        )
        
        # Build validation result with detailed errors
        errors: List[ImportRecordError] = []
        
        for row in parse_result.rows:
            if not row.is_valid:
                record_error = ImportRecordError(
                    row_number=row.row_number,
                    employee_id=row.data.get("employee_id"),
                    field_errors=row.errors,
                    is_valid=False,
                )
                errors.append(record_error)
                
                # Store validation error in database
                for field_error in row.errors:
                    validation_error = ImportValidationError(
                        import_job_id=import_job.id,
                        error_type=ErrorType.DATA_TYPE,
                        severity=Severity.ERROR,
                        error_code=field_error.code,
                        error_message=field_error.message,
                        field_name=field_error.field,
                        field_value=field_error.value,
                        suggested_correction=field_error.suggestion,
                    )
                    self.session.add(validation_error)
        
        # Check for duplicate employee_ids within the file
        seen_employee_ids: Dict[str, int] = {}
        for row in parse_result.rows:
            emp_id = row.data.get("employee_id")
            if emp_id:
                if emp_id in seen_employee_ids:
                    # Add duplicate error
                    dup_error = ImportRecordError(
                        row_number=row.row_number,
                        employee_id=emp_id,
                        field_errors=[ImportFieldError(
                            field="employee_id",
                            value=emp_id,
                            message=f"Duplicate employee_id found in row {seen_employee_ids[emp_id]}",
                            code="duplicate",
                            suggestion="Each employee_id must be unique",
                        )],
                        is_valid=False,
                    )
                    errors.append(dup_error)
                else:
                    seen_employee_ids[emp_id] = row.row_number
        
        # Check for existing employee_ids in database
        existing_ids = self._check_existing_employee_ids(list(seen_employee_ids.keys()))
        for emp_id, row_num in seen_employee_ids.items():
            if emp_id in existing_ids:
                db_error = ImportRecordError(
                    row_number=row_num,
                    employee_id=emp_id,
                    field_errors=[ImportFieldError(
                        field="employee_id",
                        value=emp_id,
                        message=f"Employee with ID '{emp_id}' already exists in the database",
                        code="duplicate",
                        suggestion="Use a different employee_id or update the existing record",
                    )],
                    is_valid=False,
                )
                errors.append(db_error)
        
        # Update import job with validation results
        import_job.validation_errors = [
            {"row": e.row_number, "errors": [fe.model_dump() for fe in e.field_errors]}
            for e in errors
        ]
        import_job.status = ImportJobStatus.MAPPING  # Ready for processing
        
        # Log validation completion
        audit_context = ImportExportAuditContext(
            user_id=current_user.id,
            operation_type="import",
            ip_address=current_user.ip_address,
            user_agent=current_user.user_agent,
        )
        self.audit_logger.log_import_validated(
            import_job_id=import_job.id,
            context=audit_context,
            total_rows=parse_result.total_rows,
            valid_rows=parse_result.valid_rows,
            error_rows=parse_result.error_rows + len(errors),
        )
        
        self.session.flush()
        
        return ImportValidationResult(
            is_valid=len(errors) == 0,
            total_rows=parse_result.total_rows,
            valid_rows=parse_result.valid_rows,
            error_rows=parse_result.error_rows + len(errors),
            errors=errors,
            detected_columns=parse_result.headers,
            suggested_mappings=parse_result.suggested_mappings,
        )
    
    def process_import(
        self,
        import_job_id: uuid.UUID,
        content: bytes,
        current_user: CurrentUser,
    ) -> ImportStatusResponse:
        """
        Process the import by creating employee records.
        
        Supports partial imports - valid records are imported even if some fail.
        """
        import_job = self._get_import_job(import_job_id)
        
        # Check status
        if import_job.status not in [ImportJobStatus.MAPPING, ImportJobStatus.PENDING]:
            raise ValidationError(
                message=f"Import job cannot be processed in current status: {import_job.status.value}"
            )
        
        # Update status
        import_job.status = ImportJobStatus.PROCESSING
        import_job.started_at = datetime.utcnow()
        self.session.flush()
        
        # Get configuration
        config = import_job.mapping_config or {}
        delimiter = config.get("delimiter", ",")
        allow_partial = config.get("allow_partial_import", True)
        field_mappings = import_job.field_mappings
        
        # Parse CSV
        parse_result = parse_csv_content(
            content=content,
            delimiter=delimiter,
            custom_mappings=field_mappings,
        )
        
        # Log processing start
        audit_context = ImportExportAuditContext(
            user_id=current_user.id,
            operation_type="import",
            ip_address=current_user.ip_address,
            user_agent=current_user.user_agent,
        )
        self.audit_logger.log_import_processing_started(
            import_job_id=import_job.id,
            context=audit_context,
            total_rows=parse_result.total_rows,
        )
        
        # Process rows
        successful_rows = 0
        error_rows = 0
        validation_errors: List[ImportRecordError] = []
        
        for row in parse_result.rows:
            import_job.processed_rows += 1
            
            if not row.is_valid:
                error_rows += 1
                import_job.error_rows += 1
                validation_errors.append(ImportRecordError(
                    row_number=row.row_number,
                    employee_id=row.data.get("employee_id"),
                    field_errors=row.errors,
                    is_valid=False,
                ))
                continue
            
            # Try to create employee
            try:
                employee = self._create_employee_from_row(row.data, import_job.id)
                successful_rows += 1
                import_job.successful_rows += 1
                
                # Create import row record for rollback support
                import_row = ImportRow(
                    import_job_id=import_job.id,
                    row_number=row.row_number,
                    source_data=row.data,
                    mapped_data=row.data,
                    validation_status=ValidationStatus.VALID,
                    is_processed=True,
                )
                self.session.add(import_row)
                
            except IntegrityError as e:
                error_rows += 1
                import_job.error_rows += 1
                self.session.rollback()
                
                validation_errors.append(ImportRecordError(
                    row_number=row.row_number,
                    employee_id=row.data.get("employee_id"),
                    field_errors=[ImportFieldError(
                        field="employee_id",
                        value=row.data.get("employee_id"),
                        message=f"Database constraint violation: {str(e.orig)}",
                        code="database_error",
                    )],
                    is_valid=False,
                ))
                
                if not allow_partial:
                    import_job.status = ImportJobStatus.FAILED
                    self.session.flush()
                    raise ValidationError(
                        message="Import failed due to database error. Partial import not allowed."
                    )
            
            except Exception as e:
                error_rows += 1
                import_job.error_rows += 1
                
                validation_errors.append(ImportRecordError(
                    row_number=row.row_number,
                    employee_id=row.data.get("employee_id"),
                    field_errors=[ImportFieldError(
                        field="unknown",
                        value=None,
                        message=f"Unexpected error: {str(e)}",
                        code="unknown_error",
                    )],
                    is_valid=False,
                ))
        
        # Update final status
        import_job.completed_at = datetime.utcnow()
        if error_rows == 0:
            import_job.status = ImportJobStatus.COMPLETED
        elif successful_rows > 0:
            import_job.status = ImportJobStatus.COMPLETED  # Partial success
        else:
            import_job.status = ImportJobStatus.FAILED
        
        # Calculate duration
        duration = (import_job.completed_at - import_job.started_at).total_seconds()
        
        # Log completion
        self.audit_logger.log_import_completed(
            import_job_id=import_job.id,
            context=audit_context,
            successful_rows=successful_rows,
            error_rows=error_rows,
            duration_seconds=duration,
        )
        
        self.session.flush()
        
        # Build error summary
        error_summary: Dict[str, int] = {}
        for record in validation_errors:
            for field_error in record.field_errors:
                error_code = field_error.code
                error_summary[error_code] = error_summary.get(error_code, 0) + 1
        
        return ImportStatusResponse(
            import_id=import_job.id,
            import_reference_id=import_job.import_reference_id,
            status=ImportStatus(import_job.status.value),
            progress=ImportProgress(
                total_rows=import_job.total_rows,
                processed_rows=import_job.processed_rows,
                successful_rows=import_job.successful_rows,
                error_rows=import_job.error_rows,
                completion_percentage=100.0,
            ),
            validation_errors=validation_errors,
            error_summary=error_summary if error_summary else None,
            started_at=import_job.started_at,
            completed_at=import_job.completed_at,
            created_at=import_job.created_at,
            created_by_user_id=import_job.created_by_user_id,
        )
    
    def get_import_status(
        self,
        import_job_id: uuid.UUID,
        current_user: CurrentUser,
    ) -> ImportStatusResponse:
        """Get the current status of an import job."""
        import_job = self._get_import_job(import_job_id)
        
        # Calculate completion percentage
        completion_pct = 0.0
        if import_job.total_rows > 0:
            completion_pct = (import_job.processed_rows / import_job.total_rows) * 100
        
        # Build validation errors from stored data
        validation_errors: List[ImportRecordError] = []
        if import_job.validation_errors:
            for error_data in import_job.validation_errors:
                field_errors = [
                    ImportFieldError(**fe) for fe in error_data.get("errors", [])
                ]
                validation_errors.append(ImportRecordError(
                    row_number=error_data.get("row", 0),
                    field_errors=field_errors,
                    is_valid=False,
                ))
        
        # Build error summary
        error_summary: Dict[str, int] = {}
        for record in validation_errors:
            for field_error in record.field_errors:
                error_code = field_error.code
                error_summary[error_code] = error_summary.get(error_code, 0) + 1
        
        # Estimate completion time
        estimated_completion: Optional[datetime] = None
        if import_job.status == ImportJobStatus.PROCESSING and import_job.started_at:
            if import_job.processed_rows > 0:
                elapsed = (datetime.utcnow() - import_job.started_at).total_seconds()
                rate = import_job.processed_rows / elapsed
                remaining = import_job.total_rows - import_job.processed_rows
                if rate > 0:
                    estimated_seconds = remaining / rate
                    estimated_completion = datetime.utcnow() + timedelta(seconds=estimated_seconds)
        
        return ImportStatusResponse(
            import_id=import_job.id,
            import_reference_id=import_job.import_reference_id,
            status=ImportStatus(import_job.status.value),
            progress=ImportProgress(
                total_rows=import_job.total_rows,
                processed_rows=import_job.processed_rows,
                successful_rows=import_job.successful_rows,
                error_rows=import_job.error_rows,
                completion_percentage=round(completion_pct, 2),
                estimated_completion_time=estimated_completion,
            ),
            validation_errors=validation_errors,
            error_summary=error_summary if error_summary else None,
            started_at=import_job.started_at,
            completed_at=import_job.completed_at,
            created_at=import_job.created_at,
            created_by_user_id=import_job.created_by_user_id,
        )
    
    def _get_import_job(self, import_job_id: uuid.UUID) -> ImportJob:
        """Get import job by ID or raise NotFoundError."""
        import_job = self.session.get(ImportJob, import_job_id)
        if import_job is None or import_job.is_deleted:
            raise create_not_found_error("Import Job", str(import_job_id))
        return import_job
    
    def _check_existing_employee_ids(self, employee_ids: List[str]) -> set:
        """Check which employee_ids already exist in the database."""
        if not employee_ids:
            return set()
        
        stmt = select(Employee.employee_id).where(
            Employee.employee_id.in_(employee_ids)
        )
        result = self.session.execute(stmt)
        return {row[0] for row in result}
    
    def _create_employee_from_row(
        self,
        row_data: Dict[str, Any],
        import_job_id: uuid.UUID,
    ) -> Employee:
        """Create an Employee record from parsed row data."""
        employee = Employee(
            employee_id=row_data.get("employee_id"),
            email=row_data.get("email"),
            first_name=row_data.get("first_name"),
            middle_name=row_data.get("middle_name"),
            last_name=row_data.get("last_name"),
            preferred_name=row_data.get("preferred_name"),
            date_of_birth=row_data.get("date_of_birth"),
            gender=row_data.get("gender"),
            personal_email=row_data.get("personal_email"),
            phone_number=row_data.get("phone_number"),
            mobile_number=row_data.get("mobile_number"),
            address_line1=row_data.get("address_line1"),
            address_line2=row_data.get("address_line2"),
            city=row_data.get("city"),
            state_province=row_data.get("state_province"),
            postal_code=row_data.get("postal_code"),
            country=row_data.get("country"),
            department_id=row_data.get("department_id"),
            manager_id=row_data.get("manager_id"),
            location_id=row_data.get("location_id"),
            work_schedule_id=row_data.get("work_schedule_id"),
            job_title=row_data.get("job_title"),
            employment_type=row_data.get("employment_type"),
            employment_status=row_data.get("employment_status", "active"),
            hire_date=row_data.get("hire_date"),
            termination_date=row_data.get("termination_date"),
            salary=row_data.get("salary"),
            hourly_rate=row_data.get("hourly_rate"),
        )
        
        self.session.add(employee)
        self.session.flush()
        
        return employee

