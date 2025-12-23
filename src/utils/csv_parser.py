"""CSV parsing utilities for employee import/export operations."""

import csv
import hashlib
import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Generator, List, Optional, Tuple

from src.schemas.employee_import import ImportFieldError


# Standard employee fields and their expected types
EMPLOYEE_FIELDS: Dict[str, str] = {
    "employee_id": "string",
    "email": "email",
    "first_name": "string",
    "middle_name": "string",
    "last_name": "string",
    "preferred_name": "string",
    "date_of_birth": "date",
    "gender": "string",
    "personal_email": "email",
    "phone_number": "phone",
    "mobile_number": "phone",
    "address_line1": "string",
    "address_line2": "string",
    "city": "string",
    "state_province": "string",
    "postal_code": "string",
    "country": "string",
    "department_id": "integer",
    "manager_id": "integer",
    "location_id": "integer",
    "work_schedule_id": "integer",
    "job_title": "string",
    "employment_type": "string",
    "employment_status": "string",
    "hire_date": "date",
    "termination_date": "date",
    "salary": "decimal",
    "hourly_rate": "decimal",
}

# Required fields for employee creation
REQUIRED_FIELDS = {"employee_id", "email", "first_name", "last_name", "hire_date"}

# Common column name variations for auto-mapping
COLUMN_NAME_MAPPINGS: Dict[str, List[str]] = {
    "employee_id": ["employee_id", "emp_id", "id", "employee_number", "emp_number", "employee number"],
    "email": ["email", "work_email", "company_email", "email_address", "work email"],
    "first_name": ["first_name", "firstname", "first", "given_name", "first name"],
    "middle_name": ["middle_name", "middlename", "middle", "middle name"],
    "last_name": ["last_name", "lastname", "last", "surname", "family_name", "last name"],
    "preferred_name": ["preferred_name", "nickname", "preferred", "preferred name"],
    "date_of_birth": ["date_of_birth", "dob", "birth_date", "birthdate", "birthday", "date of birth"],
    "gender": ["gender", "sex"],
    "personal_email": ["personal_email", "home_email", "private_email", "personal email"],
    "phone_number": ["phone_number", "phone", "work_phone", "office_phone", "telephone", "phone number"],
    "mobile_number": ["mobile_number", "mobile", "cell_phone", "cell", "mobile_phone", "mobile number"],
    "address_line1": ["address_line1", "address1", "street", "street_address", "address", "address line 1"],
    "address_line2": ["address_line2", "address2", "apt", "suite", "unit", "address line 2"],
    "city": ["city", "town", "municipality"],
    "state_province": ["state_province", "state", "province", "region", "state province"],
    "postal_code": ["postal_code", "zip", "zip_code", "postcode", "postal code"],
    "country": ["country", "nation", "country_code"],
    "department_id": ["department_id", "dept_id", "department", "dept", "department id"],
    "manager_id": ["manager_id", "manager", "supervisor_id", "reports_to", "manager id"],
    "location_id": ["location_id", "location", "office_id", "site_id", "location id"],
    "work_schedule_id": ["work_schedule_id", "schedule_id", "schedule", "work schedule id"],
    "job_title": ["job_title", "title", "position", "role", "job title"],
    "employment_type": ["employment_type", "emp_type", "type", "employment type"],
    "employment_status": ["employment_status", "status", "emp_status", "employment status"],
    "hire_date": ["hire_date", "start_date", "join_date", "date_hired", "hire date"],
    "termination_date": ["termination_date", "end_date", "termination", "termination date"],
    "salary": ["salary", "annual_salary", "base_salary", "compensation"],
    "hourly_rate": ["hourly_rate", "rate", "hourly", "hour_rate", "hourly rate"],
}


@dataclass
class ParsedRow:
    """Result of parsing a single CSV row."""
    
    row_number: int
    data: Dict[str, Any]
    errors: List[ImportFieldError] = field(default_factory=list)
    is_valid: bool = True


@dataclass
class ParseResult:
    """Result of parsing an entire CSV file."""
    
    rows: List[ParsedRow] = field(default_factory=list)
    headers: List[str] = field(default_factory=list)
    total_rows: int = 0
    valid_rows: int = 0
    error_rows: int = 0
    file_checksum: str = ""
    suggested_mappings: Dict[str, str] = field(default_factory=dict)


def compute_file_checksum(content: bytes) -> str:
    """Compute SHA-256 checksum of file content."""
    return hashlib.sha256(content).hexdigest()


def detect_delimiter(sample: str) -> str:
    """
    Detect the delimiter used in a CSV file.
    
    Checks for comma, semicolon, tab, and pipe delimiters.
    """
    delimiters = [",", ";", "\t", "|"]
    counts = {d: sample.count(d) for d in delimiters}
    
    # Return delimiter with highest count, default to comma
    max_delimiter = max(counts, key=counts.get)
    if counts[max_delimiter] > 0:
        return max_delimiter
    return ","


def normalize_column_name(name: str) -> str:
    """Normalize a column name for matching."""
    return name.lower().strip().replace("-", "_").replace(" ", "_")


def suggest_field_mapping(csv_columns: List[str]) -> Dict[str, str]:
    """
    Suggest mappings from CSV columns to employee fields.
    
    Returns a dict mapping CSV column names to employee field names.
    """
    mappings: Dict[str, str] = {}
    normalized_columns = {normalize_column_name(col): col for col in csv_columns}
    
    for field_name, variations in COLUMN_NAME_MAPPINGS.items():
        for variation in variations:
            normalized_var = normalize_column_name(variation)
            if normalized_var in normalized_columns:
                original_col = normalized_columns[normalized_var]
                mappings[original_col] = field_name
                break
    
    return mappings


def validate_email(value: str) -> Tuple[bool, Optional[str]]:
    """Validate email format."""
    if not value:
        return True, None
    
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if re.match(email_pattern, value):
        return True, None
    return False, "Invalid email format"


def validate_phone(value: str) -> Tuple[bool, Optional[str]]:
    """Validate phone number format."""
    if not value:
        return True, None
    
    # Remove common formatting characters
    cleaned = re.sub(r'[\s\-\(\)\.]', '', value)
    
    # Check if remaining is mostly digits
    if re.match(r'^\+?\d{7,15}$', cleaned):
        return True, None
    return False, "Invalid phone number format"


def parse_date(value: str) -> Tuple[Optional[date], Optional[str]]:
    """
    Parse a date string into a date object.
    
    Supports multiple formats: YYYY-MM-DD, MM/DD/YYYY, DD/MM/YYYY, etc.
    """
    if not value or value.strip() == "":
        return None, None
    
    formats = [
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%Y/%m/%d",
        "%m-%d-%Y",
        "%d-%m-%Y",
        "%Y%m%d",
        "%B %d, %Y",
        "%b %d, %Y",
    ]
    
    for fmt in formats:
        try:
            parsed = datetime.strptime(value.strip(), fmt)
            return parsed.date(), None
        except ValueError:
            continue
    
    return None, f"Could not parse date: {value}. Expected format: YYYY-MM-DD"


def parse_decimal(value: str) -> Tuple[Optional[Decimal], Optional[str]]:
    """Parse a decimal value from string."""
    if not value or value.strip() == "":
        return None, None
    
    try:
        # Remove currency symbols and commas
        cleaned = re.sub(r'[$€£¥,]', '', value.strip())
        return Decimal(cleaned), None
    except InvalidOperation:
        return None, f"Invalid decimal value: {value}"


def parse_integer(value: str) -> Tuple[Optional[int], Optional[str]]:
    """Parse an integer value from string."""
    if not value or value.strip() == "":
        return None, None
    
    try:
        return int(value.strip()), None
    except ValueError:
        return None, f"Invalid integer value: {value}"


def validate_and_convert_field(
    field_name: str,
    value: str,
    field_type: str,
) -> Tuple[Any, Optional[ImportFieldError]]:
    """
    Validate and convert a field value based on its expected type.
    
    Returns the converted value and any validation error.
    """
    # Clean the value
    value = value.strip() if value else ""
    
    if field_type == "string":
        return value if value else None, None
    
    elif field_type == "email":
        is_valid, error_msg = validate_email(value)
        if not is_valid:
            return value, ImportFieldError(
                field=field_name,
                value=value,
                message=error_msg,
                code="invalid_email",
                suggestion="Provide a valid email address (e.g., user@example.com)"
            )
        return value if value else None, None
    
    elif field_type == "phone":
        is_valid, error_msg = validate_phone(value)
        if not is_valid:
            return value, ImportFieldError(
                field=field_name,
                value=value,
                message=error_msg,
                code="invalid_phone",
                suggestion="Provide a valid phone number"
            )
        return value if value else None, None
    
    elif field_type == "date":
        parsed, error_msg = parse_date(value)
        if error_msg:
            return value, ImportFieldError(
                field=field_name,
                value=value,
                message=error_msg,
                code="invalid_date",
                suggestion="Use format YYYY-MM-DD (e.g., 2024-01-15)"
            )
        return parsed, None
    
    elif field_type == "decimal":
        parsed, error_msg = parse_decimal(value)
        if error_msg:
            return value, ImportFieldError(
                field=field_name,
                value=value,
                message=error_msg,
                code="invalid_decimal",
                suggestion="Provide a valid number (e.g., 50000.00)"
            )
        return parsed, None
    
    elif field_type == "integer":
        parsed, error_msg = parse_integer(value)
        if error_msg:
            return value, ImportFieldError(
                field=field_name,
                value=value,
                message=error_msg,
                code="invalid_integer",
                suggestion="Provide a valid whole number"
            )
        return parsed, None
    
    return value if value else None, None


def parse_csv_row(
    row: Dict[str, str],
    row_number: int,
    field_mappings: Dict[str, str],
) -> ParsedRow:
    """
    Parse and validate a single CSV row.
    
    Args:
        row: Dictionary of column name to value from CSV reader
        row_number: The row number in the file (1-based)
        field_mappings: Mapping from CSV column names to employee field names
    
    Returns:
        ParsedRow with converted data and any validation errors
    """
    data: Dict[str, Any] = {}
    errors: List[ImportFieldError] = []
    
    for csv_column, value in row.items():
        # Get the employee field name from mapping
        field_name = field_mappings.get(csv_column)
        if not field_name:
            continue
        
        # Get the expected field type
        field_type = EMPLOYEE_FIELDS.get(field_name, "string")
        
        # Validate and convert the value
        converted, error = validate_and_convert_field(field_name, value, field_type)
        data[field_name] = converted
        
        if error:
            errors.append(error)
    
    # Check for required fields
    for required_field in REQUIRED_FIELDS:
        if required_field not in data or data.get(required_field) is None:
            # Check if it was in the CSV but empty
            errors.append(ImportFieldError(
                field=required_field,
                value=None,
                message=f"Required field '{required_field}' is missing or empty",
                code="required",
                suggestion=f"Provide a value for {required_field}"
            ))
    
    is_valid = len(errors) == 0
    
    return ParsedRow(
        row_number=row_number,
        data=data,
        errors=errors,
        is_valid=is_valid,
    )


def parse_csv_content(
    content: bytes,
    delimiter: str = ",",
    skip_first_row: bool = True,
    custom_mappings: Optional[Dict[str, str]] = None,
) -> ParseResult:
    """
    Parse CSV content and validate all rows.
    
    Args:
        content: Raw CSV file content as bytes
        delimiter: CSV delimiter character
        skip_first_row: Whether the first row is headers
        custom_mappings: Custom column to field mappings (overrides auto-detection)
    
    Returns:
        ParseResult with all parsed rows and metadata
    """
    # Compute checksum
    file_checksum = compute_file_checksum(content)
    
    # Decode content
    try:
        text_content = content.decode("utf-8")
    except UnicodeDecodeError:
        # Try latin-1 as fallback
        text_content = content.decode("latin-1")
    
    # Auto-detect delimiter if needed
    if not delimiter or delimiter not in [",", ";", "\t", "|"]:
        delimiter = detect_delimiter(text_content[:1000])
    
    # Parse CSV
    reader = csv.DictReader(io.StringIO(text_content), delimiter=delimiter)
    headers = reader.fieldnames or []
    
    # Generate field mappings
    auto_mappings = suggest_field_mapping(headers)
    field_mappings = custom_mappings if custom_mappings else auto_mappings
    
    # Parse all rows
    rows: List[ParsedRow] = []
    valid_count = 0
    error_count = 0
    
    for idx, row in enumerate(reader, start=2 if skip_first_row else 1):
        parsed_row = parse_csv_row(row, idx, field_mappings)
        rows.append(parsed_row)
        
        if parsed_row.is_valid:
            valid_count += 1
        else:
            error_count += 1
    
    return ParseResult(
        rows=rows,
        headers=headers,
        total_rows=len(rows),
        valid_rows=valid_count,
        error_rows=error_count,
        file_checksum=file_checksum,
        suggested_mappings=auto_mappings,
    )


def stream_csv_rows(
    content: bytes,
    delimiter: str = ",",
    skip_first_row: bool = True,
    custom_mappings: Optional[Dict[str, str]] = None,
) -> Generator[ParsedRow, None, None]:
    """
    Stream CSV rows one at a time for memory-efficient processing.
    
    Useful for very large files where loading all rows at once is not feasible.
    """
    # Decode content
    try:
        text_content = content.decode("utf-8")
    except UnicodeDecodeError:
        text_content = content.decode("latin-1")
    
    # Auto-detect delimiter
    if not delimiter:
        delimiter = detect_delimiter(text_content[:1000])
    
    # Parse CSV
    reader = csv.DictReader(io.StringIO(text_content), delimiter=delimiter)
    headers = reader.fieldnames or []
    
    # Generate field mappings
    auto_mappings = suggest_field_mapping(headers)
    field_mappings = custom_mappings if custom_mappings else auto_mappings
    
    # Yield rows one at a time
    for idx, row in enumerate(reader, start=2 if skip_first_row else 1):
        yield parse_csv_row(row, idx, field_mappings)


def generate_csv_content(
    data: List[Dict[str, Any]],
    fields: List[str],
    include_headers: bool = True,
    delimiter: str = ",",
) -> bytes:
    """
    Generate CSV content from a list of dictionaries.
    
    Args:
        data: List of employee data dictionaries
        fields: List of field names to include (in order)
        include_headers: Whether to include a header row
        delimiter: CSV delimiter character
    
    Returns:
        CSV content as bytes
    """
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=fields,
        delimiter=delimiter,
        extrasaction="ignore",
    )
    
    if include_headers:
        writer.writeheader()
    
    for row in data:
        # Convert values to strings, handling special types
        string_row = {}
        for field in fields:
            value = row.get(field)
            if value is None:
                string_row[field] = ""
            elif isinstance(value, (date, datetime)):
                string_row[field] = value.isoformat()
            elif isinstance(value, Decimal):
                string_row[field] = str(value)
            else:
                string_row[field] = str(value)
        writer.writerow(string_row)
    
    return output.getvalue().encode("utf-8")

