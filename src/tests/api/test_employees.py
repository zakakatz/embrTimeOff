"""Tests for employee import/export API endpoints."""

import io
import uuid
from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.schemas.employee_import import ImportStatus


client = TestClient(app)


# =============================================================================
# Test Data
# =============================================================================

VALID_CSV_CONTENT = """employee_id,email,first_name,last_name,hire_date
EMP001,john.doe@example.com,John,Doe,2024-01-15
EMP002,jane.smith@example.com,Jane,Smith,2024-02-01
EMP003,bob.wilson@example.com,Bob,Wilson,2024-03-10
"""

INVALID_CSV_CONTENT = """employee_id,email,first_name,last_name,hire_date
EMP001,invalid-email,John,Doe,2024-01-15
EMP002,jane.smith@example.com,,Smith,2024-02-01
EMP003,bob.wilson@example.com,Bob,Wilson,invalid-date
"""

MIXED_CSV_CONTENT = """employee_id,email,first_name,last_name,hire_date
EMP001,john.doe@example.com,John,Doe,2024-01-15
EMP002,invalid-email,Jane,Smith,2024-02-01
EMP003,bob.wilson@example.com,Bob,Wilson,2024-03-10
"""


# =============================================================================
# Import Endpoint Tests
# =============================================================================

class TestImportEndpoints:
    """Test cases for import endpoints."""
    
    def test_import_csv_creates_job(self):
        """Test that uploading a CSV creates an import job."""
        files = {"file": ("employees.csv", VALID_CSV_CONTENT, "text/csv")}
        data = {"allow_partial_import": "true", "delimiter": ","}
        
        response = client.post(
            "/api/employees/import",
            files=files,
            data=data,
            headers={"X-User-Role": "admin"},
        )
        
        assert response.status_code == 201
        result = response.json()
        assert "data" in result
        assert "import_id" in result["data"]
        assert result["data"]["status"] == "pending"
        assert result["data"]["filename"] == "employees.csv"
    
    def test_import_rejects_non_csv_files(self):
        """Test that non-CSV files are rejected."""
        files = {"file": ("employees.txt", "some content", "text/plain")}
        
        response = client.post(
            "/api/employees/import",
            files=files,
            headers={"X-User-Role": "admin"},
        )
        
        assert response.status_code == 400
        result = response.json()
        assert "error" in result
    
    def test_import_rejects_empty_file(self):
        """Test that empty files are rejected."""
        files = {"file": ("employees.csv", "", "text/csv")}
        
        response = client.post(
            "/api/employees/import",
            files=files,
            headers={"X-User-Role": "admin"},
        )
        
        assert response.status_code == 400
    
    def test_get_import_status(self):
        """Test retrieving import job status."""
        # First create an import job
        files = {"file": ("employees.csv", VALID_CSV_CONTENT, "text/csv")}
        create_response = client.post(
            "/api/employees/import",
            files=files,
            headers={"X-User-Role": "admin"},
        )
        
        assert create_response.status_code == 201
        import_id = create_response.json()["data"]["import_id"]
        
        # Get status
        status_response = client.get(
            f"/api/employees/import/{import_id}/status",
            headers={"X-User-Role": "admin"},
        )
        
        assert status_response.status_code == 200
        result = status_response.json()
        assert "data" in result
        assert result["data"]["import_id"] == import_id
    
    def test_get_import_status_not_found(self):
        """Test that getting status for non-existent job returns 404."""
        fake_id = str(uuid.uuid4())
        
        response = client.get(
            f"/api/employees/import/{fake_id}/status",
            headers={"X-User-Role": "admin"},
        )
        
        assert response.status_code == 404


# =============================================================================
# Export Endpoint Tests
# =============================================================================

class TestExportEndpoints:
    """Test cases for export endpoints."""
    
    def test_export_returns_csv(self):
        """Test that export returns CSV content."""
        response = client.get(
            "/api/employees/export",
            headers={"X-User-Role": "admin"},
        )
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        assert "Content-Disposition" in response.headers
        assert "attachment" in response.headers["Content-Disposition"]
    
    def test_export_with_field_selection(self):
        """Test export with specific field selection."""
        response = client.get(
            "/api/employees/export",
            params={"fields": "employee_id,email,first_name,last_name"},
            headers={"X-User-Role": "admin"},
        )
        
        assert response.status_code == 200
        # Check that exported fields header includes requested fields
        exported_fields = response.headers.get("X-Exported-Fields", "")
        assert "employee_id" in exported_fields
        assert "email" in exported_fields
    
    def test_export_with_filters(self):
        """Test export with filters applied."""
        response = client.get(
            "/api/employees/export",
            params={
                "is_active": "true",
                "employment_status": "active",
            },
            headers={"X-User-Role": "admin"},
        )
        
        assert response.status_code == 200
    
    def test_export_post_method(self):
        """Test export using POST method with body."""
        request_body = {
            "field_selection": {
                "include_all": False,
                "fields": ["employee_id", "email", "first_name", "last_name"],
            },
            "filters": {
                "is_active": True,
            },
            "include_headers": True,
            "delimiter": ",",
            "filename_prefix": "test_export",
        }
        
        response = client.post(
            "/api/employees/export",
            json=request_body,
            headers={"X-User-Role": "admin"},
        )
        
        assert response.status_code == 200
        assert "test_export" in response.headers.get("Content-Disposition", "")
    
    def test_get_available_export_fields(self):
        """Test getting available export fields."""
        response = client.get(
            "/api/employees/export/fields",
            headers={"X-User-Role": "admin"},
        )
        
        assert response.status_code == 200
        result = response.json()
        assert "fields" in result
        assert "total_fields" in result
        assert "user_role" in result
        assert len(result["fields"]) > 0
    
    def test_export_fields_vary_by_role(self):
        """Test that available fields vary by user role."""
        # Admin should see all fields
        admin_response = client.get(
            "/api/employees/export/fields",
            headers={"X-User-Role": "admin"},
        )
        
        # Employee should see fewer fields
        employee_response = client.get(
            "/api/employees/export/fields",
            headers={"X-User-Role": "employee"},
        )
        
        admin_fields = admin_response.json()["total_fields"]
        employee_fields = employee_response.json()["total_fields"]
        
        assert admin_fields >= employee_fields


# =============================================================================
# Validation Tests
# =============================================================================

class TestImportValidation:
    """Test cases for import validation."""
    
    def test_validate_valid_csv(self):
        """Test validation of valid CSV returns no errors."""
        # Create import job
        files = {"file": ("employees.csv", VALID_CSV_CONTENT, "text/csv")}
        create_response = client.post(
            "/api/employees/import",
            files=files,
            headers={"X-User-Role": "admin"},
        )
        
        import_id = create_response.json()["data"]["import_id"]
        
        # Validate
        validate_files = {"file": ("employees.csv", VALID_CSV_CONTENT, "text/csv")}
        validate_response = client.post(
            f"/api/employees/import/{import_id}/validate",
            files=validate_files,
            headers={"X-User-Role": "admin"},
        )
        
        assert validate_response.status_code == 200
        result = validate_response.json()
        assert result["data"]["is_valid"] == True
        assert result["data"]["error_rows"] == 0
    
    def test_validate_invalid_csv_returns_errors(self):
        """Test validation of invalid CSV returns detailed errors."""
        # Create import job
        files = {"file": ("employees.csv", INVALID_CSV_CONTENT, "text/csv")}
        create_response = client.post(
            "/api/employees/import",
            files=files,
            headers={"X-User-Role": "admin"},
        )
        
        import_id = create_response.json()["data"]["import_id"]
        
        # Validate
        validate_files = {"file": ("employees.csv", INVALID_CSV_CONTENT, "text/csv")}
        validate_response = client.post(
            f"/api/employees/import/{import_id}/validate",
            files=validate_files,
            headers={"X-User-Role": "admin"},
        )
        
        assert validate_response.status_code == 200
        result = validate_response.json()
        assert result["data"]["is_valid"] == False
        assert result["data"]["error_rows"] > 0
        assert len(result["data"]["errors"]) > 0


# =============================================================================
# Authorization Tests
# =============================================================================

class TestAuthorization:
    """Test cases for authorization."""
    
    def test_admin_can_import(self):
        """Test that admin users can perform imports."""
        files = {"file": ("employees.csv", VALID_CSV_CONTENT, "text/csv")}
        
        response = client.post(
            "/api/employees/import",
            files=files,
            headers={"X-User-Role": "admin"},
        )
        
        assert response.status_code == 201
    
    def test_admin_can_export(self):
        """Test that admin users can perform exports."""
        response = client.get(
            "/api/employees/export",
            headers={"X-User-Role": "admin"},
        )
        
        assert response.status_code == 200

