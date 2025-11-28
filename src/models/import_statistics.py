"""ImportStatistics model for tracking import performance metrics."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.models.base import Base


class ImportStatistics(Base):
    """
    Performance metrics model for import operations.
    
    Tracks detailed statistics including processing times, throughput,
    resource utilization, and quality metrics for optimization and
    SLA monitoring.
    """
    
    __tablename__ = "import_statistics"
    
    # Primary Key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    
    # One-to-one relationship with import job
    import_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("import_jobs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    
    # File processing metrics
    file_size_processed_mb: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    
    # Time metrics (in seconds)
    processing_time_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    validation_time_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    error_resolution_time_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    
    # Throughput metrics
    records_per_second: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    
    # Quality metrics (percentages 0.00 - 100.00)
    mapping_confidence_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    auto_mapping_success_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    
    # Resource utilization metrics
    memory_usage_mb: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    cpu_usage_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    
    # Additional metrics
    peak_memory_usage_mb: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    avg_row_processing_ms: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Average time to process a single row in milliseconds",
    )
    total_api_calls: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    cache_hit_rate: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )
    
    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    
    # Relationship
    import_job: Mapped["ImportJob"] = relationship(
        "ImportJob",
        back_populates="statistics",
    )
    
    # Table constraints
    __table_args__ = (
        # Minimum value constraints for time fields
        CheckConstraint(
            "processing_time_seconds >= 0",
            name="ck_import_stats_processing_time_min",
        ),
        CheckConstraint(
            "validation_time_seconds >= 0",
            name="ck_import_stats_validation_time_min",
        ),
        CheckConstraint(
            "error_resolution_time_seconds >= 0",
            name="ck_import_stats_error_resolution_time_min",
        ),
        # Minimum value constraints for size fields
        CheckConstraint(
            "file_size_processed_mb >= 0",
            name="ck_import_stats_file_size_min",
        ),
        CheckConstraint(
            "memory_usage_mb >= 0",
            name="ck_import_stats_memory_usage_min",
        ),
        CheckConstraint(
            "records_per_second >= 0",
            name="ck_import_stats_records_per_second_min",
        ),
        # Range constraints for percentage fields (0.00 - 100.00)
        CheckConstraint(
            "mapping_confidence_score >= 0 AND mapping_confidence_score <= 100",
            name="ck_import_stats_mapping_confidence_range",
        ),
        CheckConstraint(
            "auto_mapping_success_rate >= 0 AND auto_mapping_success_rate <= 100",
            name="ck_import_stats_auto_mapping_range",
        ),
        CheckConstraint(
            "cpu_usage_percentage >= 0 AND cpu_usage_percentage <= 100",
            name="ck_import_stats_cpu_usage_range",
        ),
        CheckConstraint(
            "cache_hit_rate IS NULL OR (cache_hit_rate >= 0 AND cache_hit_rate <= 100)",
            name="ck_import_stats_cache_hit_range",
        ),
    )
    
    def __repr__(self) -> str:
        return (
            f"<ImportStatistics("
            f"id={self.id}, "
            f"job_id={self.import_job_id}, "
            f"records/s={self.records_per_second}"
            f")>"
        )


# Avoid circular imports
from src.models.import_job import ImportJob

