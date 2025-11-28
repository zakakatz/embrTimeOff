"""Create import_jobs and import_rows tables.

Revision ID: 001
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create import_jobs and import_rows tables with all constraints and indexes."""
    
    # Create import_job_status enum
    import_job_status = postgresql.ENUM(
        "pending",
        "validating",
        "mapping",
        "processing",
        "completed",
        "failed",
        "cancelled",
        "rolled_back",
        name="import_job_status",
    )
    import_job_status.create(op.get_bind())
    
    # Create validation_status enum
    validation_status = postgresql.ENUM(
        "pending",
        "valid",
        "invalid",
        "warning",
        name="validation_status",
    )
    validation_status.create(op.get_bind())
    
    # Create import_jobs table
    op.create_table(
        "import_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("import_reference_id", sa.String(50), nullable=False, unique=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger, nullable=False),
        sa.Column("file_checksum", sa.String(64), nullable=False),
        sa.Column(
            "status",
            import_job_status,
            nullable=False,
            server_default="pending",
        ),
        sa.Column("total_rows", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("processed_rows", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("successful_rows", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("error_rows", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("validation_errors", postgresql.JSONB, nullable=True),
        sa.Column("mapping_config", postgresql.JSONB, nullable=True),
        sa.Column("field_mappings", postgresql.JSONB, nullable=True),
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
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rollback_token", sa.String(64), nullable=True),
        sa.Column("rollback_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rolled_back_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rolled_back_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "file_size_bytes >= 1 AND file_size_bytes <= 104857600",
            name="ck_import_job_file_size_range",
        ),
    )
    
    # Create indexes for import_jobs
    op.create_index("ix_import_jobs_import_reference_id", "import_jobs", ["import_reference_id"])
    op.create_index("ix_import_jobs_organization_id", "import_jobs", ["organization_id"])
    op.create_index("ix_import_jobs_created_by_user_id", "import_jobs", ["created_by_user_id"])
    op.create_index("ix_import_jobs_status", "import_jobs", ["status"])
    op.create_index("ix_import_jobs_rollback_token", "import_jobs", ["rollback_token"])
    op.create_index("ix_import_jobs_checksum_status", "import_jobs", ["file_checksum", "status"])
    
    # Create import_rows table
    op.create_table(
        "import_rows",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "import_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("import_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("row_number", sa.BigInteger, nullable=False),
        sa.Column("source_data", postgresql.JSONB, nullable=True),
        sa.Column("mapped_data", postgresql.JSONB, nullable=True),
        sa.Column(
            "validation_status",
            validation_status,
            nullable=False,
            server_default="pending",
        ),
        sa.Column("error_details", postgresql.JSONB, nullable=True),
        sa.Column("is_processed", sa.Boolean, nullable=False, server_default="false"),
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
        sa.CheckConstraint("row_number >= 1", name="ck_import_row_row_number_min"),
        sa.UniqueConstraint("import_job_id", "row_number", name="uq_import_row_job_row_number"),
    )
    
    # Create indexes for import_rows
    op.create_index("ix_import_rows_import_job_id", "import_rows", ["import_job_id"])
    op.create_index("ix_import_rows_validation_status", "import_rows", ["validation_status"])
    op.create_index("ix_import_rows_is_processed", "import_rows", ["is_processed"])


def downgrade() -> None:
    """Drop import_jobs and import_rows tables."""
    
    # Drop import_rows table and indexes
    op.drop_index("ix_import_rows_is_processed", table_name="import_rows")
    op.drop_index("ix_import_rows_validation_status", table_name="import_rows")
    op.drop_index("ix_import_rows_import_job_id", table_name="import_rows")
    op.drop_table("import_rows")
    
    # Drop import_jobs table and indexes
    op.drop_index("ix_import_jobs_checksum_status", table_name="import_jobs")
    op.drop_index("ix_import_jobs_rollback_token", table_name="import_jobs")
    op.drop_index("ix_import_jobs_status", table_name="import_jobs")
    op.drop_index("ix_import_jobs_created_by_user_id", table_name="import_jobs")
    op.drop_index("ix_import_jobs_organization_id", table_name="import_jobs")
    op.drop_index("ix_import_jobs_import_reference_id", table_name="import_jobs")
    op.drop_table("import_jobs")
    
    # Drop enums
    sa.Enum(name="validation_status").drop(op.get_bind())
    sa.Enum(name="import_job_status").drop(op.get_bind())

