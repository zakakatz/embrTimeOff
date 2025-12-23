"""Tests for employee import service."""

import uuid
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from src.schemas.employee_import import ImportFieldError, ImportStatus
from src.utils.csv_parser import (
    REQUIRED_FIELDS,
    ParseResult,
    ParsedRow,
    parse_csv_content,
    suggest_field_mapping,
    validate_and_convert_field,
    validate_email,
    validate_phone,
    parse_date,
    parse_decimal,
    parse_integer,
)


# =============================================================================
# CSV Parser Tests
# =============================================================================

class TestCSVParser:
    """Test cases for CSV parsing utilities."""
    
    def test_parse_valid_csv(self):
        """Test parsing a valid CSV file."""
        content = b"""employee_id,email,first_name,last_name,hire_date
EMP001,john@example.com,John,Doe,2024-01-15
EMP002,jane@example.com,Jane,Smith,2024-02-01"""
        
        result = parse_csv_content(content)
        
        assert result.total_rows == 2
        assert result.valid_rows == 2
        assert result.error_rows == 0
        assert len(result.rows) == 2
    
    def test_parse_csv_with_errors(self):
        """Test parsing CSV with validation errors."""
        content = b"""employee_id,email,first_name,last_name,hire_date
EMP001,invalid-email,John,Doe,2024-01-15
EMP002,jane@example.com,,Smith,2024-02-01"""
        
        result = parse_csv_content(content)
        
        assert result.total_rows == 2
        assert result.error_rows > 0
    
    def test_auto_detect_field_mappings(self):
        """Test automatic field mapping detection."""
        columns = ["emp_id", "work_email", "first_name", "last name", "hire_date"]
        
        mappings = suggest_field_mapping(columns)
        
        assert "emp_id" in mappings
        assert mappings["emp_id"] == "employee_id"
        assert "work_email" in mappings
        assert mappings["work_email"] == "email"
    
    def test_custom_delimiter(self):
        """Test parsing CSV with custom delimiter."""
        content = b"""employee_id;email;first_name;last_name;hire_date
EMP001;john@example.com;John;Doe;2024-01-15"""
        
        result = parse_csv_content(content, delimiter=";")
        
        assert result.total_rows == 1
        assert result.valid_rows == 1


# =============================================================================
# Email Validation Tests
# =============================================================================

class TestEmailValidation:
    """Test cases for email validation."""
    
    def test_valid_email(self):
        """Test valid email addresses."""
        valid_emails = [
            "user@example.com",
            "user.name@example.com",
            "user+tag@example.com",
            "user@subdomain.example.com",
        ]
        
        for email in valid_emails:
            is_valid, error = validate_email(email)
            assert is_valid, f"Email {email} should be valid"
    
    def test_invalid_email(self):
        """Test invalid email addresses."""
        invalid_emails = [
            "invalid",
            "@example.com",
            "user@",
            "user@.com",
            "user space@example.com",
        ]
        
        for email in invalid_emails:
            is_valid, error = validate_email(email)
            assert not is_valid, f"Email {email} should be invalid"
    
    def test_empty_email(self):
        """Test empty email is valid (optional field)."""
        is_valid, error = validate_email("")
        assert is_valid


# =============================================================================
# Phone Validation Tests
# =============================================================================

class TestPhoneValidation:
    """Test cases for phone validation."""
    
    def test_valid_phone_numbers(self):
        """Test valid phone numbers."""
        valid_phones = [
            "+1234567890",
            "123-456-7890",
            "(123) 456-7890",
            "1234567890",
        ]
        
        for phone in valid_phones:
            is_valid, error = validate_phone(phone)
            assert is_valid, f"Phone {phone} should be valid"
    
    def test_invalid_phone_numbers(self):
        """Test invalid phone numbers."""
        invalid_phones = [
            "abc",
            "12345",  # Too short
            "abc-def-ghij",
        ]
        
        for phone in invalid_phones:
            is_valid, error = validate_phone(phone)
            assert not is_valid, f"Phone {phone} should be invalid"
    
    def test_empty_phone(self):
        """Test empty phone is valid (optional field)."""
        is_valid, error = validate_phone("")
        assert is_valid


# =============================================================================
# Date Parsing Tests
# =============================================================================

class TestDateParsing:
    """Test cases for date parsing."""
    
    def test_parse_iso_date(self):
        """Test parsing ISO format dates."""
        parsed, error = parse_date("2024-01-15")
        assert parsed == date(2024, 1, 15)
        assert error is None
    
    def test_parse_us_date(self):
        """Test parsing US format dates."""
        parsed, error = parse_date("01/15/2024")
        assert parsed == date(2024, 1, 15)
        assert error is None
    
    def test_parse_invalid_date(self):
        """Test parsing invalid date returns error."""
        parsed, error = parse_date("not-a-date")
        assert parsed is None
        assert error is not None
    
    def test_parse_empty_date(self):
        """Test parsing empty date returns None."""
        parsed, error = parse_date("")
        assert parsed is None
        assert error is None


# =============================================================================
# Number Parsing Tests
# =============================================================================

class TestNumberParsing:
    """Test cases for number parsing."""
    
    def test_parse_decimal(self):
        """Test parsing decimal values."""
        parsed, error = parse_decimal("50000.00")
        assert parsed is not None
        assert float(parsed) == 50000.00
    
    def test_parse_decimal_with_currency(self):
        """Test parsing decimal with currency symbol."""
        parsed, error = parse_decimal("$50,000.00")
        assert parsed is not None
        assert float(parsed) == 50000.00
    
    def test_parse_invalid_decimal(self):
        """Test parsing invalid decimal returns error."""
        parsed, error = parse_decimal("not-a-number")
        assert parsed is None
        assert error is not None
    
    def test_parse_integer(self):
        """Test parsing integer values."""
        parsed, error = parse_integer("123")
        assert parsed == 123
    
    def test_parse_invalid_integer(self):
        """Test parsing invalid integer returns error."""
        parsed, error = parse_integer("12.5")
        assert parsed is None
        assert error is not None


# =============================================================================
# Field Conversion Tests
# =============================================================================

class TestFieldConversion:
    """Test cases for field validation and conversion."""
    
    def test_string_field(self):
        """Test string field conversion."""
        value, error = validate_and_convert_field("first_name", "John", "string")
        assert value == "John"
        assert error is None
    
    def test_email_field_valid(self):
        """Test valid email field conversion."""
        value, error = validate_and_convert_field("email", "john@example.com", "email")
        assert value == "john@example.com"
        assert error is None
    
    def test_email_field_invalid(self):
        """Test invalid email field returns error."""
        value, error = validate_and_convert_field("email", "invalid", "email")
        assert error is not None
        assert error.code == "invalid_email"
    
    def test_date_field_valid(self):
        """Test valid date field conversion."""
        value, error = validate_and_convert_field("hire_date", "2024-01-15", "date")
        assert value == date(2024, 1, 15)
        assert error is None
    
    def test_date_field_invalid(self):
        """Test invalid date field returns error."""
        value, error = validate_and_convert_field("hire_date", "not-a-date", "date")
        assert error is not None
        assert error.code == "invalid_date"


# =============================================================================
# Required Fields Tests
# =============================================================================

class TestRequiredFields:
    """Test cases for required field validation."""
    
    def test_required_fields_defined(self):
        """Test that required fields are properly defined."""
        assert "employee_id" in REQUIRED_FIELDS
        assert "email" in REQUIRED_FIELDS
        assert "first_name" in REQUIRED_FIELDS
        assert "last_name" in REQUIRED_FIELDS
        assert "hire_date" in REQUIRED_FIELDS
    
    def test_missing_required_field_creates_error(self):
        """Test that missing required fields create validation errors."""
        content = b"""employee_id,email,first_name,last_name
EMP001,john@example.com,John,Doe"""  # Missing hire_date
        
        result = parse_csv_content(content)
        
        # Should have error for missing hire_date
        assert result.error_rows > 0
        
        # Find the error
        for row in result.rows:
            if not row.is_valid:
                field_names = [e.field for e in row.errors]
                assert "hire_date" in field_names


# =============================================================================
# Checksum Tests
# =============================================================================

class TestChecksum:
    """Test cases for file checksum calculation."""
    
    def test_checksum_consistency(self):
        """Test that same content produces same checksum."""
        from src.utils.csv_parser import compute_file_checksum
        
        content = b"test content"
        checksum1 = compute_file_checksum(content)
        checksum2 = compute_file_checksum(content)
        
        assert checksum1 == checksum2
    
    def test_checksum_different_content(self):
        """Test that different content produces different checksum."""
        from src.utils.csv_parser import compute_file_checksum
        
        content1 = b"content 1"
        content2 = b"content 2"
        
        checksum1 = compute_file_checksum(content1)
        checksum2 = compute_file_checksum(content2)
        
        assert checksum1 != checksum2

