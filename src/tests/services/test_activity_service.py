"""Tests for activity service."""

import uuid
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from src.models.activity_log import ActivityLog, ActivitySource, ActivityType
from src.services.activity_service import ActivityService
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


class TestActivityService:
    """Tests for ActivityService."""
    
    def test_service_initialization(self, mock_session):
        """Test service initializes correctly."""
        service = ActivityService(mock_session)
        assert service.session == mock_session
    
    def test_log_activity_creates_record(self, mock_session):
        """Test logging activity creates ActivityLog record."""
        service = ActivityService(mock_session)
        
        activity = service.log_activity(
            employee_id=1,
            activity_type=ActivityType.PROFILE_UPDATE,
            title="Test activity",
            description="Test description",
        )
        
        assert activity.employee_id == 1
        assert activity.activity_type == ActivityType.PROFILE_UPDATE
        assert activity.title == "Test activity"
        mock_session.add.assert_called_once_with(activity)
    
    def test_log_profile_view(self, mock_session, admin_user):
        """Test logging profile view activity."""
        service = ActivityService(mock_session)
        
        activity = service.log_profile_view(
            employee_id=1,
            viewer=admin_user,
        )
        
        assert activity.activity_type == ActivityType.PROFILE_VIEW
        assert activity.title == "Profile viewed"
        assert activity.actor_user_id == admin_user.id
    
    def test_log_profile_update(self, mock_session, admin_user):
        """Test logging profile update activity."""
        service = ActivityService(mock_session)
        
        activity = service.log_profile_update(
            employee_id=1,
            actor=admin_user,
            changed_fields=["email", "phone_number"],
        )
        
        assert activity.activity_type == ActivityType.PROFILE_UPDATE
        assert "email" in activity.description
        assert activity.details["changed_fields"] == ["email", "phone_number"]
    
    def test_log_status_change(self, mock_session, admin_user):
        """Test logging status change activity."""
        service = ActivityService(mock_session)
        
        activity = service.log_status_change(
            employee_id=1,
            actor=admin_user,
            old_status="active",
            new_status="on_leave",
        )
        
        assert activity.activity_type == ActivityType.STATUS_CHANGE
        assert "on_leave" in activity.title
        assert activity.details["old_status"] == "active"
        assert activity.details["new_status"] == "on_leave"
    
    def test_log_system_activity(self, mock_session):
        """Test logging system activity."""
        service = ActivityService(mock_session)
        
        activity = service.log_system_activity(
            employee_id=1,
            title="System update",
            description="Automated sync completed",
        )
        
        assert activity.activity_type == ActivityType.SYSTEM_UPDATE
        assert activity.activity_source == ActivitySource.SYSTEM
        assert activity.is_automated is True


class TestActivityPermissions:
    """Tests for activity view permissions."""
    
    def test_admin_can_view_any_activity(
        self,
        mock_session,
        admin_user,
    ):
        """Test admin can view any activity."""
        service = ActivityService(mock_session)
        
        # Should not raise
        service._check_activity_view_permission(
            employee_id=99,
            current_user=admin_user,
        )
    
    def test_employee_can_view_own_activity(
        self,
        mock_session,
        employee_user,
    ):
        """Test employee can view own activity."""
        service = ActivityService(mock_session)
        
        # Should not raise
        service._check_activity_view_permission(
            employee_id=2,  # Same as employee_user.employee_id
            current_user=employee_user,
        )
    
    def test_employee_cannot_view_other_activity(
        self,
        mock_session,
        employee_user,
    ):
        """Test employee cannot view others' activity."""
        from src.utils.errors import ForbiddenError
        
        service = ActivityService(mock_session)
        
        with pytest.raises(ForbiddenError):
            service._check_activity_view_permission(
                employee_id=99,
                current_user=employee_user,
            )


class TestActivityFiltering:
    """Tests for activity filtering."""
    
    @patch.object(ActivityService, "_check_activity_view_permission")
    def test_get_employee_activities_with_filters(
        self,
        mock_check,
        mock_session,
        admin_user,
    ):
        """Test getting activities with filters."""
        from src.schemas.employee_audit import ActivityFilters
        
        mock_session.execute.return_value.scalar.return_value = 0
        
        service = ActivityService(mock_session)
        
        filters = ActivityFilters(
            activity_types=[ActivityType.PROFILE_UPDATE],
            include_automated=False,
        )
        
        result = service.get_employee_activities(
            employee_id=1,
            current_user=admin_user,
            filters=filters,
        )
        
        assert result.employee_id == 1
        mock_check.assert_called_once()
    
    @patch.object(ActivityService, "_check_activity_view_permission")
    def test_pagination(
        self,
        mock_check,
        mock_session,
        admin_user,
    ):
        """Test activity pagination."""
        mock_session.execute.return_value.scalar.return_value = 100
        mock_session.execute.return_value.scalars.return_value = []
        
        service = ActivityService(mock_session)
        
        result = service.get_employee_activities(
            employee_id=1,
            current_user=admin_user,
            page=3,
            page_size=20,
        )
        
        assert result.page == 3
        assert result.page_size == 20

