"""Create employee self-service tables.

Revision ID: 004
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create employee self-service tables."""
    
    # Create enums
    profile_visibility_level = postgresql.ENUM(
        "private", "team", "department", "organization", "public",
        name="profile_visibility_level",
    )
    profile_visibility_level.create(op.get_bind())
    
    notification_preference = postgresql.ENUM(
        "email", "in_app", "both", "none",
        name="notification_preference",
    )
    notification_preference.create(op.get_bind())
    
    request_type = postgresql.ENUM(
        "create", "update", "delete", "correction",
        name="request_type",
    )
    request_type.create(op.get_bind())
    
    field_category_type = postgresql.ENUM(
        "personal_info", "contact_info", "emergency_contact", "address",
        "banking", "tax", "benefits", "documents", "other",
        name="field_category_type",
    )
    field_category_type.create(op.get_bind())
    
    request_status = postgresql.ENUM(
        "draft", "pending", "under_review", "approved",
        "rejected", "cancelled", "completed", "expired",
        name="request_status",
    )
    request_status.create(op.get_bind())
    
    self_service_action_type = postgresql.ENUM(
        "login", "logout", "view_profile", "edit_profile",
        "submit_request", "cancel_request", "view_documents",
        "upload_document", "delete_document", "download_document",
        "view_compensation", "view_benefits", "update_preferences",
        "update_notifications", "view_audit_log", "export_data",
        "password_change", "mfa_setup", "session_expired", "failed_auth",
        name="self_service_action_type",
    )
    self_service_action_type.create(op.get_bind())
    
    audit_severity = postgresql.ENUM(
        "info", "warning", "error", "critical",
        name="audit_severity",
    )
    audit_severity.create(op.get_bind())
    
    # =========================================================================
    # Create employee_self_services table
    # =========================================================================
    op.create_table(
        "employee_self_services",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "employee_id",
            sa.Integer,
            sa.ForeignKey("employee.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        # Profile visibility
        sa.Column("profile_visibility_level", profile_visibility_level, nullable=False, server_default="team"),
        sa.Column("show_email", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("show_phone", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("show_location", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("show_department", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("show_manager", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("show_hire_date", sa.Boolean, nullable=False, server_default="false"),
        # Dashboard
        sa.Column("dashboard_preference_json", postgresql.JSONB, nullable=True),
        sa.Column("default_landing_page", sa.String(100), nullable=False, server_default="dashboard"),
        sa.Column("items_per_page", sa.Integer, nullable=False, server_default="25"),
        # Notifications
        sa.Column("notification_preference", notification_preference, nullable=False, server_default="both"),
        sa.Column("email_notifications_enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("push_notifications_enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("notify_on_request_status", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("notify_on_approval_needed", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("notification_digest_frequency", sa.String(20), nullable=False, server_default="immediate"),
        # Permissions
        sa.Column("can_edit_personal_info", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("can_edit_contact_info", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("can_edit_emergency_contacts", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("can_view_compensation", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("can_view_documents", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("can_upload_documents", sa.Boolean, nullable=False, server_default="true"),
        # Audit and security
        sa.Column("audit_trail_enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("audit_retention_days", sa.Integer, nullable=False, server_default="365"),
        sa.Column("require_mfa_for_sensitive", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("session_timeout_minutes", sa.Integer, nullable=False, server_default="30"),
        # Localization
        sa.Column("preferred_language", sa.String(10), nullable=False, server_default="en"),
        sa.Column("preferred_timezone", sa.String(50), nullable=False, server_default="UTC"),
        sa.Column("date_format", sa.String(20), nullable=False, server_default="YYYY-MM-DD"),
        sa.Column("time_format", sa.String(10), nullable=False, server_default="24h"),
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True), nullable=True),
    )
    
    op.create_index("ix_employee_self_services_employee_id", "employee_self_services", ["employee_id"])
    
    # =========================================================================
    # Create employee_update_requests table
    # =========================================================================
    op.create_table(
        "employee_update_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "employee_id",
            sa.Integer,
            sa.ForeignKey("employee.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("request_session_id", sa.String(64), nullable=False),
        sa.Column("request_reference", sa.String(50), nullable=False, unique=True),
        sa.Column("request_type", request_type, nullable=False, server_default="update"),
        sa.Column("field_category_type", field_category_type, nullable=False),
        sa.Column("update_fields_json", postgresql.JSONB, nullable=False),
        sa.Column("current_values_json", postgresql.JSONB, nullable=True),
        sa.Column("proposed_values_json", postgresql.JSONB, nullable=False),
        sa.Column("reason_for_change", sa.Text, nullable=True),
        sa.Column("supporting_document_ids", postgresql.JSONB, nullable=True),
        sa.Column("status", request_status, nullable=False, server_default="pending"),
        sa.Column("requires_approval", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("auto_approved", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("approval_reference_id", sa.String(64), nullable=True),
        sa.Column(
            "approver_id",
            sa.Integer,
            sa.ForeignKey("employee.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("approval_level", sa.Integer, nullable=False, server_default="1"),
        sa.Column("approval_notes", sa.Text, nullable=True),
        sa.Column("rejection_reason", sa.Text, nullable=True),
        sa.Column("priority", sa.String(20), nullable=False, server_default="normal"),
        sa.Column("is_escalated", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("escalation_reason", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    
    op.create_index("ix_employee_update_requests_employee_id", "employee_update_requests", ["employee_id"])
    op.create_index("ix_employee_update_requests_request_session_id", "employee_update_requests", ["request_session_id"])
    op.create_index("ix_employee_update_requests_request_reference", "employee_update_requests", ["request_reference"])
    op.create_index("ix_employee_update_requests_approval_reference_id", "employee_update_requests", ["approval_reference_id"])
    op.create_index("ix_employee_update_requests_status", "employee_update_requests", ["status"])
    op.create_index("ix_update_request_employee_status", "employee_update_requests", ["employee_id", "status"])
    op.create_index("ix_update_request_session", "employee_update_requests", ["request_session_id", "created_at"])
    op.create_index("ix_update_request_approval", "employee_update_requests", ["approval_reference_id", "status"])
    
    # =========================================================================
    # Create employee_self_audit_logs table
    # =========================================================================
    op.create_table(
        "employee_self_audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "employee_id",
            sa.Integer,
            sa.ForeignKey("employee.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("session_id", sa.String(64), nullable=True),
        sa.Column("action_type", self_service_action_type, nullable=False),
        sa.Column("severity", audit_severity, nullable=False, server_default="info"),
        sa.Column("resource_accessed", sa.Text, nullable=True),
        sa.Column("resource_type", sa.String(50), nullable=True),
        sa.Column("resource_id", sa.String(100), nullable=True),
        sa.Column("access_ip_address", postgresql.INET, nullable=True),
        sa.Column("access_user_agent", sa.Text, nullable=True),
        sa.Column("request_method", sa.String(10), nullable=True),
        sa.Column("request_path", sa.String(500), nullable=True),
        sa.Column("action_status", sa.String(20), nullable=False, server_default="success"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("error_code", sa.String(50), nullable=True),
        sa.Column("changes_made", postgresql.JSONB, nullable=True),
        sa.Column("previous_values", postgresql.JSONB, nullable=True),
        sa.Column("new_values", postgresql.JSONB, nullable=True),
        sa.Column("metadata_json", postgresql.JSONB, nullable=True),
        sa.Column("device_type", sa.String(50), nullable=True),
        sa.Column("browser", sa.String(100), nullable=True),
        sa.Column("os", sa.String(100), nullable=True),
        sa.Column("geo_country", sa.String(100), nullable=True),
        sa.Column("geo_city", sa.String(100), nullable=True),
        sa.Column("action_timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("action_duration_ms", sa.Integer, nullable=True),
    )
    
    op.create_index("ix_employee_self_audit_logs_employee_id", "employee_self_audit_logs", ["employee_id"])
    op.create_index("ix_employee_self_audit_logs_session_id", "employee_self_audit_logs", ["session_id"])
    op.create_index("ix_employee_self_audit_logs_action_type", "employee_self_audit_logs", ["action_type"])
    op.create_index("ix_employee_self_audit_logs_action_timestamp", "employee_self_audit_logs", ["action_timestamp"])
    op.create_index("ix_self_audit_employee_timestamp", "employee_self_audit_logs", ["employee_id", "action_timestamp"])
    op.create_index("ix_self_audit_action_timestamp", "employee_self_audit_logs", ["action_type", "action_timestamp"])
    op.create_index("ix_self_audit_session", "employee_self_audit_logs", ["session_id", "action_timestamp"])
    op.create_index("ix_self_audit_ip", "employee_self_audit_logs", ["access_ip_address"])


def downgrade() -> None:
    """Drop employee self-service tables."""
    
    # Drop employee_self_audit_logs
    op.drop_index("ix_self_audit_ip", table_name="employee_self_audit_logs")
    op.drop_index("ix_self_audit_session", table_name="employee_self_audit_logs")
    op.drop_index("ix_self_audit_action_timestamp", table_name="employee_self_audit_logs")
    op.drop_index("ix_self_audit_employee_timestamp", table_name="employee_self_audit_logs")
    op.drop_index("ix_employee_self_audit_logs_action_timestamp", table_name="employee_self_audit_logs")
    op.drop_index("ix_employee_self_audit_logs_action_type", table_name="employee_self_audit_logs")
    op.drop_index("ix_employee_self_audit_logs_session_id", table_name="employee_self_audit_logs")
    op.drop_index("ix_employee_self_audit_logs_employee_id", table_name="employee_self_audit_logs")
    op.drop_table("employee_self_audit_logs")
    
    # Drop employee_update_requests
    op.drop_index("ix_update_request_approval", table_name="employee_update_requests")
    op.drop_index("ix_update_request_session", table_name="employee_update_requests")
    op.drop_index("ix_update_request_employee_status", table_name="employee_update_requests")
    op.drop_index("ix_employee_update_requests_status", table_name="employee_update_requests")
    op.drop_index("ix_employee_update_requests_approval_reference_id", table_name="employee_update_requests")
    op.drop_index("ix_employee_update_requests_request_reference", table_name="employee_update_requests")
    op.drop_index("ix_employee_update_requests_request_session_id", table_name="employee_update_requests")
    op.drop_index("ix_employee_update_requests_employee_id", table_name="employee_update_requests")
    op.drop_table("employee_update_requests")
    
    # Drop employee_self_services
    op.drop_index("ix_employee_self_services_employee_id", table_name="employee_self_services")
    op.drop_table("employee_self_services")
    
    # Drop enums
    sa.Enum(name="audit_severity").drop(op.get_bind())
    sa.Enum(name="self_service_action_type").drop(op.get_bind())
    sa.Enum(name="request_status").drop(op.get_bind())
    sa.Enum(name="field_category_type").drop(op.get_bind())
    sa.Enum(name="request_type").drop(op.get_bind())
    sa.Enum(name="notification_preference").drop(op.get_bind())
    sa.Enum(name="profile_visibility_level").drop(op.get_bind())

