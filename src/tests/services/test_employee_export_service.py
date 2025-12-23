"""Tests for employee export service."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from src.schemas.employee_export import (
    ExportFieldSelection,
    ExportFilters,
    ExportRequest,
)
from src.utils.csv_parser import generate_csv_content


# =============================================================================
# CSV Generation Tests
# =============================================================================

class TestCSVGeneration:
    """Test cases for CSV generation."""
    
    def test_generate_csv_with_headers(self):
        """Test generating CSV with headers."""
        data = [
            {"employee_id": "EMP001", "first_name": "John", "last_name": "Doe"},
            {"employee_id": "EMP002", "first_name": "Jane", "last_name": "Smith"},
        ]
        fields = ["employee_id", "first_name", "last_name"]
        
        content = generate_csv_content(data, fields, include_headers=True)
        csv_text = content.decode("utf-8")
        
        lines = csv_text.strip().split("\n")
        assert len(lines) == 3  # Header + 2 data rows
        assert "employee_id" in lines[0]
        assert "EMP001" in lines[1]
        assert "EMP002" in lines[2]
    
    def test_generate_csv_without_headers(self):
        """Test generating CSV without headers."""
        data = [
            {"employee_id": "EMP001", "first_name": "John"},
        ]
        fields = ["employee_id", "first_name"]
        
        content = generate_csv_content(data, fields, include_headers=False)
        csv_text = content.decode("utf-8")
        
        lines = csv_text.strip().split("\n")
        assert len(lines) == 1  # Only data row
        assert "employee_id" not in lines[0]
        assert "EMP001" in lines[0]
    
    def test_generate_csv_with_custom_delimiter(self):
        """Test generating CSV with custom delimiter."""
        data = [
            {"employee_id": "EMP001", "first_name": "John"},
        ]
        fields = ["employee_id", "first_name"]
        
        content = generate_csv_content(data, fields, delimiter=";")
        csv_text = content.decode("utf-8")
        
        assert ";" in csv_text
    
    def test_generate_csv_handles_dates(self):
        """Test that date values are properly formatted."""
        data = [
            {"employee_id": "EMP001", "hire_date": date(2024, 1, 15)},
        ]
        fields = ["employee_id", "hire_date"]
        
        content = generate_csv_content(data, fields)
        csv_text = content.decode("utf-8")
        
        assert "2024-01-15" in csv_text
    
    def test_generate_csv_handles_decimals(self):
        """Test that decimal values are properly formatted."""
        data = [
            {"employee_id": "EMP001", "salary": Decimal("50000.00")},
        ]
        fields = ["employee_id", "salary"]
        
        content = generate_csv_content(data, fields)
        csv_text = content.decode("utf-8")
        
        assert "50000.00" in csv_text
    
    def test_generate_csv_handles_none_values(self):
        """Test that None values are handled."""
        data = [
            {"employee_id": "EMP001", "middle_name": None},
        ]
        fields = ["employee_id", "middle_name"]
        
        content = generate_csv_content(data, fields)
        csv_text = content.decode("utf-8")
        
        # Should have empty field for None
        assert "EMP001," in csv_text


# =============================================================================
# Field Selection Tests
# =============================================================================

class TestFieldSelection:
    """Test cases for export field selection."""
    
    def test_field_selection_with_include_all(self):
        """Test field selection with include_all flag."""
        selection = ExportFieldSelection(include_all=True)
        
        assert selection.include_all == True
        assert selection.fields is None
    
    def test_field_selection_with_specific_fields(self):
        """Test field selection with specific fields."""
        selection = ExportFieldSelection(
            include_all=False,
            fields=["employee_id", "email", "first_name"],
        )
        
        assert selection.include_all == False
        assert len(selection.fields) == 3
        assert "employee_id" in selection.fields
    
    def test_field_selection_with_exclusions(self):
        """Test field selection with exclusions."""
        selection = ExportFieldSelection(
            include_all=True,
            exclude_fields=["salary", "hourly_rate"],
        )
        
        assert "salary" in selection.exclude_fields
        assert "hourly_rate" in selection.exclude_fields
    
    def test_field_selection_from_string(self):
        """Test field selection parsing from comma-separated string."""
        selection = ExportFieldSelection(
            fields="employee_id, email, first_name",
        )
        
        assert len(selection.fields) == 3


# =============================================================================
# Export Filter Tests
# =============================================================================

class TestExportFilters:
    """Test cases for export filters."""
    
    def test_filters_with_department(self):
        """Test filters with department filter."""
        filters = ExportFilters(
            department_ids=[1, 2, 3],
        )
        
        assert len(filters.department_ids) == 3
    
    def test_filters_with_date_range(self):
        """Test filters with date range."""
        filters = ExportFilters(
            hire_date_from=date(2024, 1, 1),
            hire_date_to=date(2024, 12, 31),
        )
        
        assert filters.hire_date_from == date(2024, 1, 1)
        assert filters.hire_date_to == date(2024, 12, 31)
    
    def test_filters_with_multiple_criteria(self):
        """Test filters with multiple criteria."""
        filters = ExportFilters(
            department_ids=[1],
            location_ids=[1, 2],
            employment_status=["active"],
            is_active=True,
        )
        
        assert filters.department_ids == [1]
        assert filters.location_ids == [1, 2]
        assert filters.employment_status == ["active"]
        assert filters.is_active == True


# =============================================================================
# Export Request Tests
# =============================================================================

class TestExportRequest:
    """Test cases for export request model."""
    
    def test_default_export_request(self):
        """Test default export request values."""
        request = ExportRequest()
        
        assert request.include_headers == True
        assert request.delimiter == ","
        assert request.filename_prefix == "employees_export"
    
    def test_export_request_with_all_options(self):
        """Test export request with all options specified."""
        request = ExportRequest(
            field_selection=ExportFieldSelection(
                fields=["employee_id", "email"],
            ),
            filters=ExportFilters(
                is_active=True,
            ),
            include_headers=True,
            delimiter=";",
            filename_prefix="custom_export",
        )
        
        assert request.delimiter == ";"
        assert request.filename_prefix == "custom_export"
        assert request.filters.is_active == True


# =============================================================================
# Role-Based Field Filtering Tests
# =============================================================================

class TestRoleBasedFieldFiltering:
    """Test cases for role-based field filtering."""
    
    def test_admin_sees_all_fields(self):
        """Test that admin role can see all fields."""
        from src.utils.auth import UserRole, ROLE_VIEWABLE_FIELDS
        
        admin_fields = ROLE_VIEWABLE_FIELDS[UserRole.ADMIN]
        
        assert "salary" in admin_fields
        assert "hourly_rate" in admin_fields
        assert "date_of_birth" in admin_fields
    
    def test_employee_has_limited_fields(self):
        """Test that employee role has limited field access."""
        from src.utils.auth import UserRole, ROLE_VIEWABLE_FIELDS
        
        employee_fields = ROLE_VIEWABLE_FIELDS[UserRole.EMPLOYEE]
        admin_fields = ROLE_VIEWABLE_FIELDS[UserRole.ADMIN]
        
        # Employee should have fewer fields than admin
        assert len(employee_fields) < len(admin_fields)
        
        # Employee should not see sensitive fields
        assert "salary" not in employee_fields
        assert "hourly_rate" not in employee_fields
    
    def test_manager_has_intermediate_access(self):
        """Test that manager role has intermediate field access."""
        from src.utils.auth import UserRole, ROLE_VIEWABLE_FIELDS
        
        manager_fields = ROLE_VIEWABLE_FIELDS[UserRole.MANAGER]
        employee_fields = ROLE_VIEWABLE_FIELDS[UserRole.EMPLOYEE]
        admin_fields = ROLE_VIEWABLE_FIELDS[UserRole.ADMIN]
        
        # Manager should have more than employee but less than admin
        assert len(manager_fields) >= len(employee_fields)
        assert len(manager_fields) <= len(admin_fields)

