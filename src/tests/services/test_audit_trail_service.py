"""Tests for audit trail service."""

import uuid
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from src.models.employee_audit_trail import ChangeType, EmployeeAuditTrail
from src.services.audit_trail_service import AuditTrailService
from src.utils.auth import CurrentUser, UserRole


@pytest.fixture
def mock_session():
    """Create mock database session."""
    return MagicMock()


@pytest.fixture
def admin_user():
    """Create admin user."""
    return CurrentUser(
        id=uuid.uuid4(),
        employee_id=1,
        roles=[UserRole.ADMIN],
    )


@pytest.fixture
def employee_user():
    """Create regular employee user."""
    return CurrentUser(
        id=uuid.uuid4(),
        employee_id=2,
        roles=[UserRole.EMPLOYEE],
    )


@pytest.fixture
def mock_audit_record():
    """Create mock audit record."""
    return EmployeeAuditTrail(
        id=uuid.uuid4(),
        employee_id=1,
        changed_field="email",
        previous_value='"old@example.com"',
        new_value='"new@example.com"',
        changed_by_user_id=uuid.uuid4(),
        change_timestamp=datetime.now(),
        change_type=ChangeType.UPDATE,
        change_reason="User update",
    )


class TestAuditTrailService:
    """Tests for AuditTrailService."""
    
    def test_service_initialization(self, mock_session):
        """Test service initializes correctly."""
        service = AuditTrailService(mock_session)
        assert service.session == mock_session
    
    @patch.object(AuditTrailService, "_check_audit_view_permission")
    def test_get_audit_trail_calls_permission_check(
        self,
        mock_check,
        mock_session,
        admin_user,
    ):
        """Test that audit trail checks permissions."""
        mock_session.execute.return_value.scalar.return_value = 0
        
        service = AuditTrailService(mock_session)
        service.get_audit_trail(
            employee_id=1,
            current_user=admin_user,
        )
        
        mock_check.assert_called_once_with(1, admin_user)
    
    def test_admin_can_view_any_audit_trail(
        self,
        mock_session,
        admin_user,
    ):
        """Test admin permission check passes."""
        service = AuditTrailService(mock_session)
        
        # Should not raise
        service._check_audit_view_permission(
            employee_id=99,
            current_user=admin_user,
        )
    
    def test_employee_can_view_own_audit_trail(
        self,
        mock_session,
        employee_user,
    ):
        """Test employee can view their own audit trail."""
        service = AuditTrailService(mock_session)
        
        # Should not raise when viewing own audit trail
        service._check_audit_view_permission(
            employee_id=2,  # Same as employee_user.employee_id
            current_user=employee_user,
        )
    
    def test_employee_cannot_view_other_audit_trail(
        self,
        mock_session,
        employee_user,
    ):
        """Test employee cannot view others' audit trails."""
        from src.utils.errors import ForbiddenError
        
        service = AuditTrailService(mock_session)
        
        with pytest.raises(ForbiddenError):
            service._check_audit_view_permission(
                employee_id=99,  # Different from employee_user.employee_id
                current_user=employee_user,
            )
    
    def test_to_audit_entry_conversion(
        self,
        mock_session,
        mock_audit_record,
    ):
        """Test audit record to entry conversion."""
        service = AuditTrailService(mock_session)
        
        entry = service._to_audit_entry(mock_audit_record)
        
        assert entry.id == mock_audit_record.id
        assert entry.employee_id == mock_audit_record.employee_id
        assert entry.changed_field == "email"
        assert entry.field_display_name == "Email Address"
    
    def test_field_display_name_mapping(self, mock_session):
        """Test field display names are mapped correctly."""
        from src.services.audit_trail_service import FIELD_DISPLAY_NAMES
        
        assert "email" in FIELD_DISPLAY_NAMES
        assert FIELD_DISPLAY_NAMES["email"] == "Email Address"
        assert "first_name" in FIELD_DISPLAY_NAMES
        assert FIELD_DISPLAY_NAMES["first_name"] == "First Name"


class TestAuditTrailFiltering:
    """Tests for audit trail filtering."""
    
    @patch.object(AuditTrailService, "_check_audit_view_permission")
    def test_filter_by_change_type(
        self,
        mock_check,
        mock_session,
        admin_user,
    ):
        """Test filtering by change type."""
        mock_session.execute.return_value.scalar.return_value = 0
        
        service = AuditTrailService(mock_session)
        result = service.get_audit_trail(
            employee_id=1,
            current_user=admin_user,
            change_type=ChangeType.UPDATE,
        )
        
        # Verify the query was built (actual filtering is done by SQLAlchemy)
        assert result.employee_id == 1
    
    @patch.object(AuditTrailService, "_check_audit_view_permission")
    def test_pagination(
        self,
        mock_check,
        mock_session,
        admin_user,
    ):
        """Test pagination parameters."""
        mock_session.execute.return_value.scalar.return_value = 100
        mock_session.execute.return_value.scalars.return_value = []
        
        service = AuditTrailService(mock_session)
        result = service.get_audit_trail(
            employee_id=1,
            current_user=admin_user,
            page=2,
            page_size=25,
        )
        
        assert result.page == 2
        assert result.page_size == 25

