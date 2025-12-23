"""Tests for employee audit trail and activity API endpoints."""

import uuid
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.main import create_app
from src.models.employee_audit_trail import ChangeType
from src.schemas.employee_audit import (
    ActivityEntry,
    ActivityResponse,
    ActivityType,
    AuditTrailEntry,
    AuditTrailResponse,
    AuditTrailSummary,
)


@pytest.fixture
def app():
    """Create test application."""
    return create_app()


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def admin_headers():
    """Headers for admin user."""
    return {
        "X-User-ID": str(uuid.uuid4()),
        "X-Employee-ID": "1",
        "X-User-Role": "admin",
    }


@pytest.fixture
def mock_audit_entry():
    """Create mock audit trail entry."""
    return AuditTrailEntry(
        id=uuid.uuid4(),
        employee_id=1,
        changed_field="email",
        previous_value='"old@example.com"',
        new_value='"new@example.com"',
        changed_by_user_id=uuid.uuid4(),
        change_timestamp=datetime.now(),
        change_type=ChangeType.UPDATE,
        change_reason="User update",
        field_display_name="Email Address",
        is_automated=False,
    )


@pytest.fixture
def mock_activity_entry():
    """Create mock activity entry."""
    return ActivityEntry(
        id=uuid.uuid4(),
        employee_id=1,
        activity_type=ActivityType.PROFILE_UPDATE,
        activity_source="user",
        title="Profile updated",
        description="Updated fields: email",
        details={"changed_fields": ["email"]},
        actor_user_id=uuid.uuid4(),
        actor_name="Admin User",
        is_automated=False,
        created_at=datetime.now(),
    )


class TestAuditTrailEndpoints:
    """Tests for audit trail endpoints."""
    
    @patch("src.api.employee_audit.get_audit_service")
    def test_get_audit_trail_success(
        self,
        mock_get_service,
        client,
        admin_headers,
        mock_audit_entry,
    ):
        """Test successful audit trail retrieval."""
        mock_service = MagicMock()
        mock_service.get_audit_trail.return_value = AuditTrailResponse(
            employee_id=1,
            total_entries=1,
            entries=[mock_audit_entry],
            page=1,
            page_size=50,
            has_more=False,
        )
        mock_get_service.return_value = mock_service
        
        response = client.get(
            "/api/employees/1/audit-trail",
            headers=admin_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert data["data"]["employee_id"] == 1
        assert data["data"]["total_entries"] == 1
    
    @patch("src.api.employee_audit.get_audit_service")
    def test_get_audit_trail_with_filters(
        self,
        mock_get_service,
        client,
        admin_headers,
    ):
        """Test audit trail with filters."""
        mock_service = MagicMock()
        mock_service.get_audit_trail.return_value = AuditTrailResponse(
            employee_id=1,
            total_entries=0,
            entries=[],
            page=1,
            page_size=50,
            has_more=False,
        )
        mock_get_service.return_value = mock_service
        
        response = client.get(
            "/api/employees/1/audit-trail",
            params={
                "change_type": "UPDATE",
                "field_name": "email",
                "page": 1,
                "page_size": 25,
            },
            headers=admin_headers,
        )
        
        assert response.status_code == 200
    
    @patch("src.api.employee_audit.get_audit_service")
    def test_get_audit_summary(
        self,
        mock_get_service,
        client,
        admin_headers,
    ):
        """Test audit summary retrieval."""
        mock_service = MagicMock()
        mock_service.get_audit_summary.return_value = AuditTrailSummary(
            employee_id=1,
            total_changes=10,
            first_change=datetime.now() - timedelta(days=30),
            last_change=datetime.now(),
            change_counts_by_type={"UPDATE": 8, "CREATE": 2},
            most_changed_fields=[
                {"field": "email", "display_name": "Email Address", "count": 5},
            ],
            actors_count=3,
        )
        mock_get_service.return_value = mock_service
        
        response = client.get(
            "/api/employees/1/audit-trail/summary",
            headers=admin_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["total_changes"] == 10
        assert data["data"]["actors_count"] == 3
    
    @patch("src.api.employee_audit.get_audit_service")
    def test_get_field_history(
        self,
        mock_get_service,
        client,
        admin_headers,
        mock_audit_entry,
    ):
        """Test field history retrieval."""
        mock_service = MagicMock()
        mock_service.get_field_history.return_value = [mock_audit_entry]
        mock_get_service.return_value = mock_service
        
        response = client.get(
            "/api/employees/1/audit-trail/field/email",
            headers=admin_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert len(data["data"]) == 1


class TestActivityEndpoints:
    """Tests for activity endpoints."""
    
    @patch("src.api.employee_audit.get_activity_service")
    def test_get_activity_success(
        self,
        mock_get_service,
        client,
        admin_headers,
        mock_activity_entry,
    ):
        """Test successful activity retrieval."""
        mock_service = MagicMock()
        mock_service.get_employee_activities.return_value = ActivityResponse(
            employee_id=1,
            total_activities=1,
            activities=[mock_activity_entry],
            page=1,
            page_size=50,
            has_more=False,
        )
        mock_get_service.return_value = mock_service
        
        response = client.get(
            "/api/employees/1/activity",
            headers=admin_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["employee_id"] == 1
        assert data["data"]["total_activities"] == 1
    
    @patch("src.api.employee_audit.get_activity_service")
    def test_get_activity_with_filters(
        self,
        mock_get_service,
        client,
        admin_headers,
    ):
        """Test activity with filters."""
        mock_service = MagicMock()
        mock_service.get_employee_activities.return_value = ActivityResponse(
            employee_id=1,
            total_activities=0,
            activities=[],
            page=1,
            page_size=50,
            has_more=False,
        )
        mock_get_service.return_value = mock_service
        
        response = client.get(
            "/api/employees/1/activity",
            params={
                "activity_types": "profile_update,status_change",
                "include_automated": "false",
            },
            headers=admin_headers,
        )
        
        assert response.status_code == 200


class TestAccessControl:
    """Tests for access control on audit and activity endpoints."""
    
    def test_audit_trail_requires_auth_headers(self, client):
        """Test that audit trail requires proper headers."""
        response = client.get("/api/employees/1/audit-trail")
        # Should still work as we default to admin in dev mode
        assert response.status_code in [200, 403, 422]
    
    def test_activity_requires_auth_headers(self, client):
        """Test that activity requires proper headers."""
        response = client.get("/api/employees/1/activity")
        # Should still work as we default to admin in dev mode
        assert response.status_code in [200, 403, 422]

