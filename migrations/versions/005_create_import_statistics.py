"""Create import_statistics table.

Revision ID: 005
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create import_statistics table with constraints."""
    
    op.create_table(
        "import_statistics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "import_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("import_jobs.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        # File processing metrics
        sa.Column("file_size_processed_mb", sa.Numeric(10, 2), nullable=False, server_default="0.00"),
        # Time metrics
        sa.Column("processing_time_seconds", sa.Integer, nullable=False, server_default="0"),
        sa.Column("validation_time_seconds", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_resolution_time_seconds", sa.Integer, nullable=False, server_default="0"),
        # Throughput metrics
        sa.Column("records_per_second", sa.Numeric(10, 2), nullable=False, server_default="0.00"),
        # Quality metrics (percentages)
        sa.Column("mapping_confidence_score", sa.Numeric(5, 2), nullable=False, server_default="0.00"),
        sa.Column("auto_mapping_success_rate", sa.Numeric(5, 2), nullable=False, server_default="0.00"),
        # Resource utilization
        sa.Column("memory_usage_mb", sa.Numeric(10, 2), nullable=False, server_default="0.00"),
        sa.Column("cpu_usage_percentage", sa.Numeric(5, 2), nullable=False, server_default="0.00"),
        # Additional metrics
        sa.Column("peak_memory_usage_mb", sa.Numeric(10, 2), nullable=True),
        sa.Column("avg_row_processing_ms", sa.Numeric(10, 2), nullable=True),
        sa.Column("total_api_calls", sa.Integer, nullable=True),
        sa.Column("cache_hit_rate", sa.Numeric(5, 2), nullable=True),
        # Timestamp
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        # Constraints
        sa.CheckConstraint("processing_time_seconds >= 0", name="ck_import_stats_processing_time_min"),
        sa.CheckConstraint("validation_time_seconds >= 0", name="ck_import_stats_validation_time_min"),
        sa.CheckConstraint("error_resolution_time_seconds >= 0", name="ck_import_stats_error_resolution_time_min"),
        sa.CheckConstraint("file_size_processed_mb >= 0", name="ck_import_stats_file_size_min"),
        sa.CheckConstraint("memory_usage_mb >= 0", name="ck_import_stats_memory_usage_min"),
        sa.CheckConstraint("records_per_second >= 0", name="ck_import_stats_records_per_second_min"),
        sa.CheckConstraint(
            "mapping_confidence_score >= 0 AND mapping_confidence_score <= 100",
            name="ck_import_stats_mapping_confidence_range",
        ),
        sa.CheckConstraint(
            "auto_mapping_success_rate >= 0 AND auto_mapping_success_rate <= 100",
            name="ck_import_stats_auto_mapping_range",
        ),
        sa.CheckConstraint(
            "cpu_usage_percentage >= 0 AND cpu_usage_percentage <= 100",
            name="ck_import_stats_cpu_usage_range",
        ),
        sa.CheckConstraint(
            "cache_hit_rate IS NULL OR (cache_hit_rate >= 0 AND cache_hit_rate <= 100)",
            name="ck_import_stats_cache_hit_range",
        ),
    )
    
    # Create index for efficient lookups
    op.create_index("ix_import_statistics_import_job_id", "import_statistics", ["import_job_id"])


def downgrade() -> None:
    """Drop import_statistics table."""
    
    op.drop_index("ix_import_statistics_import_job_id", table_name="import_statistics")
    op.drop_table("import_statistics")

