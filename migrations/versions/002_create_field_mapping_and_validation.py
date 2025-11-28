"""Create field_mapping_rules and import_validation_errors tables.

Revision ID: 002
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create field_mapping_rules and import_validation_errors tables."""
    
    # Create data_type enum
    data_type = postgresql.ENUM(
        "string",
        "integer",
        "decimal",
        "date",
        "datetime",
        "boolean",
        "enum",
        name="data_type",
    )
    data_type.create(op.get_bind())
    
    # Create error_type enum
    error_type = postgresql.ENUM(
        "structural",
        "data_type",
        "constraint_violation",
        "business_rule",
        "duplicate_record",
        "reference_error",
        name="error_type",
    )
    error_type.create(op.get_bind())
    
    # Create severity enum
    severity = postgresql.ENUM(
        "critical",
        "error",
        "warning",
        "info",
        name="severity",
    )
    severity.create(op.get_bind())
    
    # Create resolution_status enum
    resolution_status = postgresql.ENUM(
        "unresolved",
        "resolved",
        "ignored",
        "auto_corrected",
        name="resolution_status",
    )
    resolution_status.create(op.get_bind())
    
    # =========================================================================
    # Create field_mapping_rules table
    # =========================================================================
    op.create_table(
        "field_mapping_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rule_name", sa.String(100), nullable=False),
        sa.Column("source_column", sa.String(100), nullable=False),
        sa.Column("target_attribute", sa.String(100), nullable=False),
        sa.Column(
            "data_type",
            data_type,
            nullable=False,
            server_default="string",
        ),
        sa.Column("is_required", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("validation_rules", postgresql.JSONB, nullable=True),
        sa.Column("transformation_rules", postgresql.JSONB, nullable=True),
        sa.Column("auto_detection_patterns", postgresql.JSONB, nullable=True),
        sa.Column("default_value", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
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
    )
    
    # Indexes for field_mapping_rules
    op.create_index(
        "ix_field_mapping_rules_organization_id",
        "field_mapping_rules",
        ["organization_id"],
    )
    op.create_index(
        "ix_field_mapping_rules_is_active",
        "field_mapping_rules",
        ["is_active"],
    )
    op.create_index(
        "ix_field_mapping_org_target",
        "field_mapping_rules",
        ["organization_id", "target_attribute"],
    )
    op.create_index(
        "ix_field_mapping_source",
        "field_mapping_rules",
        ["organization_id", "source_column"],
    )
    
    # Unique constraint to prevent duplicate active mappings for same target
    # Uses partial index to only apply when is_active = true
    op.execute("""
        CREATE UNIQUE INDEX uq_active_target_attribute_per_org
        ON field_mapping_rules (organization_id, target_attribute)
        WHERE is_active = true
    """)
    
    # =========================================================================
    # Create import_validation_errors table
    # =========================================================================
    op.create_table(
        "import_validation_errors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "import_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("import_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "row_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("import_rows.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("error_type", error_type, nullable=False),
        sa.Column("severity", severity, nullable=False),
        sa.Column("error_code", sa.String(50), nullable=False),
        sa.Column("error_message", sa.Text, nullable=False),
        sa.Column("field_name", sa.String(100), nullable=True),
        sa.Column("field_value", sa.Text, nullable=True),
        sa.Column("expected_format", sa.Text, nullable=True),
        sa.Column("suggested_correction", sa.Text, nullable=True),
        sa.Column(
            "resolution_status",
            resolution_status,
            nullable=False,
            server_default="unresolved",
        ),
        sa.Column("requires_manual_review", sa.Boolean, nullable=False, server_default="false"),
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
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    
    # Indexes for import_validation_errors
    op.create_index(
        "ix_import_validation_errors_import_job_id",
        "import_validation_errors",
        ["import_job_id"],
    )
    op.create_index(
        "ix_import_validation_errors_row_id",
        "import_validation_errors",
        ["row_id"],
    )
    op.create_index(
        "ix_import_validation_errors_error_type",
        "import_validation_errors",
        ["error_type"],
    )
    op.create_index(
        "ix_import_validation_errors_severity",
        "import_validation_errors",
        ["severity"],
    )
    op.create_index(
        "ix_import_validation_errors_field_name",
        "import_validation_errors",
        ["field_name"],
    )
    op.create_index(
        "ix_validation_error_job_severity",
        "import_validation_errors",
        ["import_job_id", "severity"],
    )
    op.create_index(
        "ix_validation_error_job_type",
        "import_validation_errors",
        ["import_job_id", "error_type"],
    )
    op.create_index(
        "ix_validation_error_resolution",
        "import_validation_errors",
        ["resolution_status", "requires_manual_review"],
    )


def downgrade() -> None:
    """Drop field_mapping_rules and import_validation_errors tables."""
    
    # Drop import_validation_errors indexes and table
    op.drop_index("ix_validation_error_resolution", table_name="import_validation_errors")
    op.drop_index("ix_validation_error_job_type", table_name="import_validation_errors")
    op.drop_index("ix_validation_error_job_severity", table_name="import_validation_errors")
    op.drop_index("ix_import_validation_errors_field_name", table_name="import_validation_errors")
    op.drop_index("ix_import_validation_errors_severity", table_name="import_validation_errors")
    op.drop_index("ix_import_validation_errors_error_type", table_name="import_validation_errors")
    op.drop_index("ix_import_validation_errors_row_id", table_name="import_validation_errors")
    op.drop_index("ix_import_validation_errors_import_job_id", table_name="import_validation_errors")
    op.drop_table("import_validation_errors")
    
    # Drop field_mapping_rules indexes and table
    op.execute("DROP INDEX IF EXISTS uq_active_target_attribute_per_org")
    op.drop_index("ix_field_mapping_source", table_name="field_mapping_rules")
    op.drop_index("ix_field_mapping_org_target", table_name="field_mapping_rules")
    op.drop_index("ix_field_mapping_rules_is_active", table_name="field_mapping_rules")
    op.drop_index("ix_field_mapping_rules_organization_id", table_name="field_mapping_rules")
    op.drop_table("field_mapping_rules")
    
    # Drop enums
    sa.Enum(name="resolution_status").drop(op.get_bind())
    sa.Enum(name="severity").drop(op.get_bind())
    sa.Enum(name="error_type").drop(op.get_bind())
    sa.Enum(name="data_type").drop(op.get_bind())

