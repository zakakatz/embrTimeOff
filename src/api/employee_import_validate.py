"""API endpoints for employee import data validation and preview."""

import csv
import io
import re
import uuid
from datetime import date, datetime
from enum import Enum
from typing import Annotated, Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, Header, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.employee_import_upload import file_storage, require_import_permission
from src.database.database import get_db
from src.utils.auth import CurrentUser, UserRole, get_mock_current_user
from src.utils.errors import APIError, ForbiddenError, NotFoundError, ValidationError


# =============================================================================
# Enums
# =============================================================================

class ValidationSeverity(str, Enum):
    """Severity levels for validation errors."""
    
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ValidationErrorType(str, Enum):
    """Types of validation errors."""
    
    MISSING_REQUIRED = "missing_required"
    INVALID_TYPE = "invalid_type"
    INVALID_FORMAT = "invalid_format"
    CONSTRAINT_VIOLATION = "constraint_violation"
    DUPLICATE_VALUE = "duplicate_value"
    REFERENCE_NOT_FOUND = "reference_not_found"
    BUSINESS_RULE_VIOLATION = "business_rule_violation"


# =============================================================================
# Request/Response Models
# =============================================================================

class FieldMapping(BaseModel):
    """Mapping between CSV column and employee field."""
    
    csv_column: str = Field(..., description="CSV column name")
    csv_column_index: int = Field(..., description="CSV column index (0-based)")
    employee_field: Optional[str] = Field(None, description="Mapped employee field name")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Mapping confidence score")
    is_required: bool = Field(default=False, description="Whether the field is required")
    suggested_mappings: List[str] = Field(default_factory=list, description="Alternative mapping suggestions")


class FieldMappingRequest(BaseModel):
    """Request to set field mappings."""
    
    mappings: List[FieldMapping] = Field(..., description="Field mappings to apply")


class ValidationError(BaseModel):
    """A single validation error."""
    
    row_number: int = Field(..., description="Row number (1-based, excluding header)")
    column: str = Field(..., description="Column name")
    field: Optional[str] = Field(None, description="Employee field name")
    value: Optional[str] = Field(None, description="The invalid value")
    error_type: ValidationErrorType = Field(..., description="Type of error")
    severity: ValidationSeverity = Field(default=ValidationSeverity.ERROR, description="Severity level")
    message: str = Field(..., description="Error message")
    suggested_fix: Optional[str] = Field(None, description="Suggested correction")


class ValidationSummary(BaseModel):
    """Summary of validation results."""
    
    total_rows: int = Field(default=0, description="Total data rows in file")
    valid_rows: int = Field(default=0, description="Number of valid rows")
    error_rows: int = Field(default=0, description="Number of rows with errors")
    warning_rows: int = Field(default=0, description="Number of rows with warnings only")
    error_count: int = Field(default=0, description="Total number of errors")
    warning_count: int = Field(default=0, description="Total number of warnings")
    errors_by_type: Dict[str, int] = Field(default_factory=dict, description="Error counts by type")
    errors_by_field: Dict[str, int] = Field(default_factory=dict, description="Error counts by field")


class ValidateResponse(BaseModel):
    """Response for validation endpoint."""
    
    import_id: uuid.UUID = Field(..., description="Import job ID")
    is_valid: bool = Field(default=False, description="Whether all rows are valid")
    can_proceed: bool = Field(default=False, description="Whether import can proceed (valid or partial allowed)")
    summary: ValidationSummary = Field(..., description="Validation summary")
    field_mappings: List[FieldMapping] = Field(default_factory=list, description="Field mappings (with suggestions)")
    errors: List[ValidationError] = Field(default_factory=list, description="Validation errors (limited)")
    errors_truncated: bool = Field(default=False, description="Whether error list was truncated")
    validated_at: datetime = Field(default_factory=datetime.utcnow, description="Validation timestamp")


class PreviewRow(BaseModel):
    """A single row in the preview."""
    
    row_number: int = Field(..., description="Row number (1-based)")
    original_data: Dict[str, str] = Field(..., description="Original CSV data")
    transformed_data: Dict[str, Any] = Field(..., description="Transformed employee data")
    is_valid: bool = Field(default=True, description="Whether row is valid")
    errors: List[ValidationError] = Field(default_factory=list, description="Row-specific errors")
    warnings: List[ValidationError] = Field(default_factory=list, description="Row-specific warnings")


class ImpactAssessment(BaseModel):
    """Assessment of import impact on database."""
    
    new_employees: int = Field(default=0, description="Number of new employees to create")
    updated_employees: int = Field(default=0, description="Number of existing employees to update")
    unchanged_employees: int = Field(default=0, description="Number of employees with no changes")
    new_departments_referenced: List[str] = Field(default_factory=list, description="New department names referenced")
    new_locations_referenced: List[str] = Field(default_factory=list, description="New location names referenced")


class PreviewResponse(BaseModel):
    """Response for preview endpoint."""
    
    import_id: uuid.UUID = Field(..., description="Import job ID")
    summary: ValidationSummary = Field(..., description="Validation summary")
    preview_rows: List[PreviewRow] = Field(default_factory=list, description="Sample preview rows")
    total_preview_rows: int = Field(default=0, description="Total rows in preview")
    field_mappings: List[FieldMapping] = Field(default_factory=list, description="Applied field mappings")
    impact_assessment: ImpactAssessment = Field(..., description="Impact assessment")
    generated_at: datetime = Field(default_factory=datetime.utcnow, description="Preview generation timestamp")


# =============================================================================
# Field Configuration
# =============================================================================

EMPLOYEE_FIELDS = {
    "employee_id": {"required": True, "type": "string", "max_length": 20},
    "email": {"required": True, "type": "email", "max_length": 255},
    "first_name": {"required": True, "type": "string", "max_length": 100},
    "middle_name": {"required": False, "type": "string", "max_length": 100},
    "last_name": {"required": True, "type": "string", "max_length": 100},
    "preferred_name": {"required": False, "type": "string", "max_length": 100},
    "date_of_birth": {"required": False, "type": "date"},
    "gender": {"required": False, "type": "string", "max_length": 20},
    "personal_email": {"required": False, "type": "email", "max_length": 255},
    "phone_number": {"required": False, "type": "phone", "max_length": 30},
    "mobile_number": {"required": False, "type": "phone", "max_length": 30},
    "address_line1": {"required": False, "type": "string", "max_length": 255},
    "address_line2": {"required": False, "type": "string", "max_length": 255},
    "city": {"required": False, "type": "string", "max_length": 100},
    "state_province": {"required": False, "type": "string", "max_length": 100},
    "postal_code": {"required": False, "type": "string", "max_length": 20},
    "country": {"required": False, "type": "string", "max_length": 100},
    "department": {"required": False, "type": "string", "max_length": 100},
    "department_code": {"required": False, "type": "string", "max_length": 20},
    "location": {"required": False, "type": "string", "max_length": 100},
    "location_code": {"required": False, "type": "string", "max_length": 20},
    "manager_email": {"required": False, "type": "email", "max_length": 255},
    "manager_id": {"required": False, "type": "string", "max_length": 20},
    "job_title": {"required": False, "type": "string", "max_length": 100},
    "employment_type": {"required": False, "type": "enum", "values": ["full_time", "part_time", "contractor", "intern"]},
    "employment_status": {"required": False, "type": "enum", "values": ["active", "on_leave", "terminated"]},
    "hire_date": {"required": True, "type": "date"},
    "termination_date": {"required": False, "type": "date"},
    "salary": {"required": False, "type": "number"},
    "hourly_rate": {"required": False, "type": "number"},
}

# Common column name variations for auto-mapping
COLUMN_ALIASES = {
    "employee_id": ["emp_id", "employeeid", "id", "employee_number", "emp_number"],
    "email": ["work_email", "workemail", "email_address", "e_mail"],
    "first_name": ["firstname", "first", "given_name", "givenname"],
    "middle_name": ["middlename", "middle"],
    "last_name": ["lastname", "last", "surname", "family_name", "familyname"],
    "preferred_name": ["preferredname", "nickname", "preferred"],
    "date_of_birth": ["dob", "birth_date", "birthdate", "birthday"],
    "phone_number": ["phone", "work_phone", "workphone", "telephone"],
    "mobile_number": ["mobile", "cell", "cell_phone", "cellphone"],
    "hire_date": ["hiredate", "start_date", "startdate", "date_hired"],
    "job_title": ["title", "jobtitle", "position", "role"],
    "department": ["dept", "department_name", "deptname"],
    "department_code": ["dept_code", "deptcode"],
    "location": ["office", "location_name", "site"],
    "location_code": ["office_code", "site_code"],
    "employment_type": ["emp_type", "employmenttype", "type"],
    "employment_status": ["status", "emp_status", "employmentstatus"],
    "manager_email": ["manageremail", "manager_email_address", "reports_to_email"],
    "manager_id": ["manager_employee_id", "reports_to", "supervisor_id"],
    "salary": ["annual_salary", "base_salary"],
    "hourly_rate": ["hourly_wage", "rate"],
}


# =============================================================================
# Validation Functions
# =============================================================================

def suggest_field_mapping(csv_column: str) -> Tuple[Optional[str], float]:
    """Suggest employee field mapping for a CSV column."""
    normalized = csv_column.lower().strip().replace(" ", "_").replace("-", "_")
    
    # Direct match
    if normalized in EMPLOYEE_FIELDS:
        return normalized, 1.0
    
    # Check aliases
    for field, aliases in COLUMN_ALIASES.items():
        if normalized in aliases:
            return field, 0.9
    
    # Fuzzy matching
    for field in EMPLOYEE_FIELDS:
        if field in normalized or normalized in field:
            return field, 0.7
    
    return None, 0.0


def validate_field_value(
    field: str,
    value: str,
    row_number: int,
    column: str,
) -> List[ValidationError]:
    """Validate a single field value."""
    errors = []
    field_config = EMPLOYEE_FIELDS.get(field, {})
    
    # Check required
    if field_config.get("required") and not value.strip():
        errors.append(ValidationError(
            row_number=row_number,
            column=column,
            field=field,
            value=value,
            error_type=ValidationErrorType.MISSING_REQUIRED,
            severity=ValidationSeverity.ERROR,
            message=f"Required field '{field}' is empty",
        ))
        return errors
    
    # Skip validation for empty optional fields
    if not value.strip():
        return errors
    
    # Type validation
    field_type = field_config.get("type", "string")
    
    if field_type == "email":
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, value.strip()):
            errors.append(ValidationError(
                row_number=row_number,
                column=column,
                field=field,
                value=value,
                error_type=ValidationErrorType.INVALID_FORMAT,
                severity=ValidationSeverity.ERROR,
                message=f"Invalid email format: '{value}'",
                suggested_fix="Ensure email follows format: name@domain.com",
            ))
    
    elif field_type == "date":
        date_formats = ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"]
        parsed = None
        for fmt in date_formats:
            try:
                parsed = datetime.strptime(value.strip(), fmt).date()
                break
            except ValueError:
                continue
        if not parsed:
            errors.append(ValidationError(
                row_number=row_number,
                column=column,
                field=field,
                value=value,
                error_type=ValidationErrorType.INVALID_FORMAT,
                severity=ValidationSeverity.ERROR,
                message=f"Invalid date format: '{value}'",
                suggested_fix="Use YYYY-MM-DD format (e.g., 2024-01-15)",
            ))
    
    elif field_type == "number":
        try:
            float(value.strip().replace(",", ""))
        except ValueError:
            errors.append(ValidationError(
                row_number=row_number,
                column=column,
                field=field,
                value=value,
                error_type=ValidationErrorType.INVALID_TYPE,
                severity=ValidationSeverity.ERROR,
                message=f"Invalid number: '{value}'",
            ))
    
    elif field_type == "phone":
        phone_pattern = r'^[\d\s\-\(\)\+\.]+$'
        if not re.match(phone_pattern, value.strip()):
            errors.append(ValidationError(
                row_number=row_number,
                column=column,
                field=field,
                value=value,
                error_type=ValidationErrorType.INVALID_FORMAT,
                severity=ValidationSeverity.WARNING,
                message=f"Phone number may have invalid characters: '{value}'",
            ))
    
    elif field_type == "enum":
        allowed_values = field_config.get("values", [])
        if value.strip().lower() not in [v.lower() for v in allowed_values]:
            errors.append(ValidationError(
                row_number=row_number,
                column=column,
                field=field,
                value=value,
                error_type=ValidationErrorType.CONSTRAINT_VIOLATION,
                severity=ValidationSeverity.ERROR,
                message=f"Value '{value}' not in allowed values: {allowed_values}",
                suggested_fix=f"Use one of: {', '.join(allowed_values)}",
            ))
    
    # Length validation
    max_length = field_config.get("max_length")
    if max_length and len(value) > max_length:
        errors.append(ValidationError(
            row_number=row_number,
            column=column,
            field=field,
            value=value[:50] + "..." if len(value) > 50 else value,
            error_type=ValidationErrorType.CONSTRAINT_VIOLATION,
            severity=ValidationSeverity.WARNING,
            message=f"Value exceeds maximum length of {max_length} characters",
        ))
    
    return errors


def transform_field_value(field: str, value: str) -> Any:
    """Transform a field value to the appropriate type."""
    if not value.strip():
        return None
    
    field_config = EMPLOYEE_FIELDS.get(field, {})
    field_type = field_config.get("type", "string")
    
    if field_type == "date":
        date_formats = ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"]
        for fmt in date_formats:
            try:
                return datetime.strptime(value.strip(), fmt).date().isoformat()
            except ValueError:
                continue
        return value.strip()
    
    elif field_type == "number":
        try:
            num = float(value.strip().replace(",", ""))
            return int(num) if num == int(num) else num
        except ValueError:
            return value.strip()
    
    elif field_type == "enum":
        return value.strip().lower()
    
    return value.strip()


# =============================================================================
# Router Setup
# =============================================================================

employee_import_validate_router = APIRouter(
    prefix="/api/employee-import",
    tags=["Employee Import Validation"],
)


# =============================================================================
# Endpoints
# =============================================================================

@employee_import_validate_router.post(
    "/validate/{import_id}",
    response_model=ValidateResponse,
    summary="Validate Import Data",
    description="Perform comprehensive validation on uploaded CSV data without persisting.",
)
async def validate_import(
    import_id: uuid.UUID,
    current_user: Annotated[CurrentUser, Depends(require_import_permission)],
    mappings: Optional[FieldMappingRequest] = None,
    max_errors: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> ValidateResponse:
    """
    Validate uploaded CSV data.
    
    - Performs type checking and constraint validation
    - Validates business rules
    - Suggests field mappings if not provided
    - Returns detailed error report
    """
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
            details={"import_id": str(import_id)},
        )
    
    if len(rows) < 2:
        raise ValidationError(
            message="CSV must have at least a header row and one data row",
        )
    
    headers = rows[0]
    data_rows = rows[1:]
    
    # Build field mappings
    field_mappings = []
    mapping_dict = {}
    
    if mappings and mappings.mappings:
        # Use provided mappings
        for m in mappings.mappings:
            field_mappings.append(m)
            if m.employee_field:
                mapping_dict[m.csv_column_index] = m.employee_field
    else:
        # Auto-suggest mappings
        for i, header in enumerate(headers):
            suggested_field, confidence = suggest_field_mapping(header)
            field_config = EMPLOYEE_FIELDS.get(suggested_field or "", {})
            field_mappings.append(FieldMapping(
                csv_column=header,
                csv_column_index=i,
                employee_field=suggested_field,
                confidence=confidence,
                is_required=field_config.get("required", False),
                suggested_mappings=[f for f in EMPLOYEE_FIELDS.keys() if f != suggested_field][:5],
            ))
            if suggested_field:
                mapping_dict[i] = suggested_field
    
    # Validate rows
    all_errors = []
    valid_rows = 0
    error_rows = set()
    warning_rows = set()
    errors_by_type: Dict[str, int] = {}
    errors_by_field: Dict[str, int] = {}
    
    for row_idx, row in enumerate(data_rows, start=1):
        row_has_error = False
        row_has_warning = False
        
        for col_idx, value in enumerate(row):
            field = mapping_dict.get(col_idx)
            if not field:
                continue
            
            column_name = headers[col_idx] if col_idx < len(headers) else f"Column {col_idx}"
            errors = validate_field_value(field, value, row_idx, column_name)
            
            for err in errors:
                if err.severity == ValidationSeverity.ERROR:
                    row_has_error = True
                else:
                    row_has_warning = True
                
                errors_by_type[err.error_type.value] = errors_by_type.get(err.error_type.value, 0) + 1
                errors_by_field[field] = errors_by_field.get(field, 0) + 1
                
                if len(all_errors) < max_errors:
                    all_errors.append(err)
        
        if row_has_error:
            error_rows.add(row_idx)
        elif row_has_warning:
            warning_rows.add(row_idx)
        else:
            valid_rows += 1
    
    # Build summary
    summary = ValidationSummary(
        total_rows=len(data_rows),
        valid_rows=valid_rows,
        error_rows=len(error_rows),
        warning_rows=len(warning_rows),
        error_count=sum(1 for e in all_errors if e.severity == ValidationSeverity.ERROR),
        warning_count=sum(1 for e in all_errors if e.severity == ValidationSeverity.WARNING),
        errors_by_type=errors_by_type,
        errors_by_field=errors_by_field,
    )
    
    return ValidateResponse(
        import_id=import_id,
        is_valid=len(error_rows) == 0,
        can_proceed=len(error_rows) == 0 or valid_rows > 0,
        summary=summary,
        field_mappings=field_mappings,
        errors=all_errors,
        errors_truncated=len(all_errors) >= max_errors,
    )


@employee_import_validate_router.post(
    "/preview/{import_id}",
    response_model=PreviewResponse,
    summary="Preview Import Data",
    description="Generate a preview of mapped and transformed data without executing import.",
)
async def preview_import(
    import_id: uuid.UUID,
    current_user: Annotated[CurrentUser, Depends(require_import_permission)],
    mappings: Optional[FieldMappingRequest] = None,
    preview_rows: Annotated[int, Query(ge=1, le=100)] = 10,
) -> PreviewResponse:
    """
    Generate import preview.
    
    - Shows mapped records with transformations applied
    - Provides impact assessment
    - Does not persist any data
    """
    # Retrieve uploaded file
    content = file_storage.retrieve(import_id)
    if not content:
        raise NotFoundError(
            message="Upload not found or has expired",
            details={"import_id": str(import_id)},
        )
    
    # Parse CSV
    text = content.decode("utf-8", errors="replace")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    
    if len(rows) < 2:
        raise ValidationError(message="CSV must have at least a header row and one data row")
    
    headers = rows[0]
    data_rows = rows[1:]
    
    # Build field mappings
    mapping_dict = {}
    field_mappings = []
    
    if mappings and mappings.mappings:
        for m in mappings.mappings:
            field_mappings.append(m)
            if m.employee_field:
                mapping_dict[m.csv_column_index] = m.employee_field
    else:
        for i, header in enumerate(headers):
            suggested_field, confidence = suggest_field_mapping(header)
            field_config = EMPLOYEE_FIELDS.get(suggested_field or "", {})
            field_mappings.append(FieldMapping(
                csv_column=header,
                csv_column_index=i,
                employee_field=suggested_field,
                confidence=confidence,
                is_required=field_config.get("required", False),
            ))
            if suggested_field:
                mapping_dict[i] = suggested_field
    
    # Generate preview rows
    preview_list = []
    valid_count = 0
    error_count = 0
    
    for row_idx, row in enumerate(data_rows[:preview_rows], start=1):
        original_data = {headers[i]: v for i, v in enumerate(row) if i < len(headers)}
        transformed_data = {}
        row_errors = []
        row_warnings = []
        
        for col_idx, value in enumerate(row):
            field = mapping_dict.get(col_idx)
            if not field:
                continue
            
            column_name = headers[col_idx] if col_idx < len(headers) else f"Column {col_idx}"
            
            # Validate
            errors = validate_field_value(field, value, row_idx, column_name)
            for err in errors:
                if err.severity == ValidationSeverity.ERROR:
                    row_errors.append(err)
                else:
                    row_warnings.append(err)
            
            # Transform
            transformed_data[field] = transform_field_value(field, value)
        
        is_valid = len(row_errors) == 0
        if is_valid:
            valid_count += 1
        else:
            error_count += 1
        
        preview_list.append(PreviewRow(
            row_number=row_idx,
            original_data=original_data,
            transformed_data=transformed_data,
            is_valid=is_valid,
            errors=row_errors,
            warnings=row_warnings,
        ))
    
    # Build summary
    summary = ValidationSummary(
        total_rows=len(data_rows),
        valid_rows=valid_count,
        error_rows=error_count,
        warning_rows=0,
        error_count=sum(len(p.errors) for p in preview_list),
        warning_count=sum(len(p.warnings) for p in preview_list),
    )
    
    # Impact assessment (mock - would query database in real implementation)
    impact = ImpactAssessment(
        new_employees=valid_count,
        updated_employees=0,
        unchanged_employees=0,
    )
    
    return PreviewResponse(
        import_id=import_id,
        summary=summary,
        preview_rows=preview_list,
        total_preview_rows=min(preview_rows, len(data_rows)),
        field_mappings=field_mappings,
        impact_assessment=impact,
    )


@employee_import_validate_router.get(
    "/mappings/suggestions",
    summary="Get Field Mapping Suggestions",
    description="Get suggested field mappings for a list of column names.",
)
async def get_mapping_suggestions(
    columns: Annotated[str, Query(description="Comma-separated column names")],
    current_user: Annotated[CurrentUser, Depends(require_import_permission)],
) -> Dict[str, Any]:
    """
    Get field mapping suggestions for column names.
    """
    column_list = [c.strip() for c in columns.split(",")]
    suggestions = []
    
    for i, col in enumerate(column_list):
        suggested_field, confidence = suggest_field_mapping(col)
        field_config = EMPLOYEE_FIELDS.get(suggested_field or "", {})
        suggestions.append({
            "csv_column": col,
            "csv_column_index": i,
            "suggested_field": suggested_field,
            "confidence": confidence,
            "is_required": field_config.get("required", False),
            "alternatives": [f for f in EMPLOYEE_FIELDS.keys() if f != suggested_field][:5],
        })
    
    return {
        "suggestions": suggestions,
        "available_fields": list(EMPLOYEE_FIELDS.keys()),
    }

