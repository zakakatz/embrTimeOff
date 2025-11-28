"""Create import_audit_logs and import_rollback_entities tables.

Revision ID: 003
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create import_audit_logs and import_rollback_entities tables."""
    
    # Create action_type enum
    action_type = postgresql.ENUM(
        "created",
        "uploaded",
        "validated",
        "processing_started",
        "processing_completed",
        "failed",
        "cancelled",
        "rollback_requested",
        "rollback_completed",
        name="action_type",
    )
    action_type.create(op.get_bind())
    
    # Create actor_role enum
    actor_role = postgresql.ENUM(
        "admin",
        "hr_admin",
        "user",
        "system",
        name="actor_role",
    )
    actor_role.create(op.get_bind())
    
    # Create action_performed enum
    action_performed = postgresql.ENUM(
        "created",
        "updated",
        "deleted",
        name="action_performed",
    )
    action_performed.create(op.get_bind())
    
    # Create rollback_status enum
    rollback_status = postgresql.ENUM(
        "not_processed",
        "processed",
        "failed",
        "partial",
        name="rollback_status",
    )
    rollback_status.create(op.get_bind())
    
    # =========================================================================
    # Create import_audit_logs table
    # =========================================================================
    op.create_table(
        "import_audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "import_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("import_jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_role", actor_role, nullable=False),
        sa.Column("action_type", action_type, nullable=False),
        sa.Column("action_details", postgresql.JSONB, nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column(
            "action_timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    
    # Indexes for import_audit_logs
    op.create_index(
        "ix_import_audit_logs_import_job_id",
        "import_audit_logs",
        ["import_job_id"],
    )
    op.create_index(
        "ix_import_audit_logs_actor_user_id",
        "import_audit_logs",
        ["actor_user_id"],
    )
    op.create_index(
        "ix_import_audit_logs_action_type",
        "import_audit_logs",
        ["action_type"],
    )
    op.create_index(
        "ix_import_audit_logs_action_timestamp",
        "import_audit_logs",
        ["action_timestamp"],
    )
    op.create_index(
        "ix_audit_log_job_timestamp",
        "import_audit_logs",
        ["import_job_id", "action_timestamp"],
    )
    op.create_index(
        "ix_audit_log_actor_timestamp",
        "import_audit_logs",
        ["actor_user_id", "action_timestamp"],
    )
    op.create_index(
        "ix_audit_log_action_timestamp",
        "import_audit_logs",
        ["action_type", "action_timestamp"],
    )
    
    # =========================================================================
    # Create import_rollback_entities table
    # =========================================================================
    op.create_table(
        "import_rollback_entities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "import_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("import_jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("rollback_token", sa.String(64), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action_performed", action_performed, nullable=False),
        sa.Column("original_state", postgresql.JSONB, nullable=True),
        sa.Column("imported_state", postgresql.JSONB, nullable=True),
        sa.Column("is_processed", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "rollback_status",
            rollback_status,
            nullable=False,
            server_default="not_processed",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    
    # Indexes for import_rollback_entities
    op.create_index(
        "ix_import_rollback_entities_import_job_id",
        "import_rollback_entities",
        ["import_job_id"],
    )
    op.create_index(
        "ix_import_rollback_entities_rollback_token",
        "import_rollback_entities",
        ["rollback_token"],
    )
    op.create_index(
        "ix_import_rollback_entities_entity_type",
        "import_rollback_entities",
        ["entity_type"],
    )
    op.create_index(
        "ix_import_rollback_entities_entity_id",
        "import_rollback_entities",
        ["entity_id"],
    )
    op.create_index(
        "ix_rollback_token_entity",
        "import_rollback_entities",
        ["rollback_token", "entity_type"],
    )
    op.create_index(
        "ix_rollback_job_status",
        "import_rollback_entities",
        ["import_job_id", "rollback_status"],
    )
    op.create_index(
        "ix_rollback_entity_lookup",
        "import_rollback_entities",
        ["entity_type", "entity_id"],
    )


def downgrade() -> None:
    """Drop import_audit_logs and import_rollback_entities tables."""
    
    # Drop import_rollback_entities indexes and table
    op.drop_index("ix_rollback_entity_lookup", table_name="import_rollback_entities")
    op.drop_index("ix_rollback_job_status", table_name="import_rollback_entities")
    op.drop_index("ix_rollback_token_entity", table_name="import_rollback_entities")
    op.drop_index("ix_import_rollback_entities_entity_id", table_name="import_rollback_entities")
    op.drop_index("ix_import_rollback_entities_entity_type", table_name="import_rollback_entities")
    op.drop_index("ix_import_rollback_entities_rollback_token", table_name="import_rollback_entities")
    op.drop_index("ix_import_rollback_entities_import_job_id", table_name="import_rollback_entities")
    op.drop_table("import_rollback_entities")
    
    # Drop import_audit_logs indexes and table
    op.drop_index("ix_audit_log_action_timestamp", table_name="import_audit_logs")
    op.drop_index("ix_audit_log_actor_timestamp", table_name="import_audit_logs")
    op.drop_index("ix_audit_log_job_timestamp", table_name="import_audit_logs")
    op.drop_index("ix_import_audit_logs_action_timestamp", table_name="import_audit_logs")
    op.drop_index("ix_import_audit_logs_action_type", table_name="import_audit_logs")
    op.drop_index("ix_import_audit_logs_actor_user_id", table_name="import_audit_logs")
    op.drop_index("ix_import_audit_logs_import_job_id", table_name="import_audit_logs")
    op.drop_table("import_audit_logs")
    
    # Drop enums
    sa.Enum(name="rollback_status").drop(op.get_bind())
    sa.Enum(name="action_performed").drop(op.get_bind())
    sa.Enum(name="actor_role").drop(op.get_bind())
    sa.Enum(name="action_type").drop(op.get_bind())

