"""Time series data models with partitioning for audit logs and analytics.

Implements PostgreSQL time-based partitioning with automatic partition management.
"""

from datetime import datetime, date
from enum import Enum
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    func,
    event,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


# =============================================================================
# Enums
# =============================================================================

class AuditActionType(str, Enum):
    """Type of audit action."""
    
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    LOGIN = "login"
    LOGOUT = "logout"
    EXPORT = "export"
    IMPORT = "import"
    APPROVE = "approve"
    REJECT = "reject"
    ACCESS = "access"


class AuditCategory(str, Enum):
    """Category of audited resource."""
    
    EMPLOYEE = "employee"
    TIME_OFF = "time_off"
    COMPENSATION = "compensation"
    DOCUMENT = "document"
    SYSTEM = "system"
    SECURITY = "security"
    REPORT = "report"


class PartitionStatus(str, Enum):
    """Status of a partition."""
    
    ACTIVE = "active"
    ARCHIVED = "archived"
    PENDING_DELETION = "pending_deletion"
    DELETED = "deleted"


# =============================================================================
# Partition Configuration
# =============================================================================

class PartitionConfig:
    """Configuration for time-based partitioning."""
    
    # Audit logs: monthly partitions
    AUDIT_PARTITION_INTERVAL = "month"
    AUDIT_RETENTION_MONTHS = 24  # 2 years
    
    # Analytics: daily partitions
    ANALYTICS_PARTITION_INTERVAL = "day"
    ANALYTICS_RETENTION_DAYS = 730  # 2 years
    
    # Partition naming patterns
    AUDIT_PARTITION_PREFIX = "audit_log_"
    ANALYTICS_PARTITION_PREFIX = "analytics_event_"


# =============================================================================
# Audit Log Model (Partitioned)
# =============================================================================

class AuditLog(Base):
    """
    Audit log with time-based partitioning.
    
    Uses monthly partitions for efficient querying and retention management.
    The actual partitioning is configured at the PostgreSQL level.
    """
    
    __tablename__ = "audit_log"
    
    # Primary key - composite with timestamp for partitioning
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    
    # Timestamp - partition key (must be part of primary key for partitioning)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        primary_key=True,  # For partition key
    )
    
    # User identification
    user_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        nullable=True,
        index=True,
    )
    
    employee_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )
    
    # Action details
    action_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    
    # Resource information
    resource_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    
    resource_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    
    # Data fields (sensitive data should be encrypted)
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    
    # Encrypted sensitive data
    encrypted_data: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    
    # Change tracking
    old_values: Mapped[Optional[str]] = mapped_column(
        JSONB,
        nullable=True,
    )
    
    new_values: Mapped[Optional[str]] = mapped_column(
        JSONB,
        nullable=True,
    )
    
    # Request context
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    
    user_agent: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    
    request_id: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    
    session_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    
    # Success/failure
    is_successful: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    
    # Additional metadata
    metadata: Mapped[Optional[str]] = mapped_column(
        JSONB,
        nullable=True,
    )
    
    # Indexes for common queries
    __table_args__ = (
        Index("ix_audit_log_user_time", "user_id", "timestamp"),
        Index("ix_audit_log_action_time", "action_type", "timestamp"),
        Index("ix_audit_log_resource", "resource_type", "resource_id"),
        Index("ix_audit_log_category_time", "category", "timestamp"),
        # Partition definition (PostgreSQL specific)
        {"postgresql_partition_by": "RANGE (timestamp)"},
    )
    
    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, action={self.action_type}, time={self.timestamp})>"


# =============================================================================
# Analytics Event Model (Partitioned)
# =============================================================================

class AnalyticsEvent(Base):
    """
    Analytics events with daily partitioning.
    
    Stores time series data for analytics and reporting.
    """
    
    __tablename__ = "analytics_event"
    
    # Primary key
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    
    # Timestamp - partition key
    event_time: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        primary_key=True,
    )
    
    # Event identification
    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    
    event_category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    
    # Context
    employee_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )
    
    department_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )
    
    location_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    
    # Metrics
    metric_value: Mapped[Optional[float]] = mapped_column(
        Integer,  # Using Integer for Decimal/Float storage
        nullable=True,
    )
    
    metric_unit: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    
    # Event data
    event_data: Mapped[Optional[str]] = mapped_column(
        JSONB,
        nullable=True,
    )
    
    # Dimensions for analysis
    dimensions: Mapped[Optional[str]] = mapped_column(
        JSONB,
        nullable=True,
    )
    
    # Source
    source: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    
    # Indexes
    __table_args__ = (
        Index("ix_analytics_type_time", "event_type", "event_time"),
        Index("ix_analytics_category_time", "event_category", "event_time"),
        Index("ix_analytics_employee_time", "employee_id", "event_time"),
        {"postgresql_partition_by": "RANGE (event_time)"},
    )
    
    def __repr__(self) -> str:
        return f"<AnalyticsEvent(id={self.id}, type={self.event_type}, time={self.event_time})>"


# =============================================================================
# Partition Management Model
# =============================================================================

class PartitionMetadata(Base):
    """
    Tracks partition metadata for management and cleanup.
    """
    
    __tablename__ = "partition_metadata"
    
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    
    # Partition identification
    table_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    
    partition_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
    )
    
    # Partition range
    start_date: Mapped[date] = mapped_column(
        DateTime,
        nullable=False,
    )
    
    end_date: Mapped[date] = mapped_column(
        DateTime,
        nullable=False,
    )
    
    # Status
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=PartitionStatus.ACTIVE.value,
    )
    
    # Statistics
    row_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    
    size_bytes: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    
    archived_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )
    
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )
    
    # Retention
    retention_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )
    
    def __repr__(self) -> str:
        return f"<PartitionMetadata(partition={self.partition_name}, status={self.status})>"


# =============================================================================
# Partition Management SQL Templates
# =============================================================================

class PartitionSQL:
    """SQL templates for partition management."""
    
    # Create monthly partition for audit logs
    CREATE_AUDIT_PARTITION = """
        CREATE TABLE IF NOT EXISTS audit_log_{year}_{month:02d}
        PARTITION OF audit_log
        FOR VALUES FROM ('{start_date}') TO ('{end_date}');
    """
    
    # Create daily partition for analytics
    CREATE_ANALYTICS_PARTITION = """
        CREATE TABLE IF NOT EXISTS analytics_event_{year}_{month:02d}_{day:02d}
        PARTITION OF analytics_event
        FOR VALUES FROM ('{start_date}') TO ('{end_date}');
    """
    
    # Drop old partition
    DROP_PARTITION = """
        DROP TABLE IF EXISTS {partition_name};
    """
    
    # Archive partition (detach then rename)
    DETACH_PARTITION = """
        ALTER TABLE {parent_table} DETACH PARTITION {partition_name};
    """
    
    # Get partition statistics
    PARTITION_STATS = """
        SELECT 
            pg_total_relation_size('{partition_name}') as size_bytes,
            (SELECT count(*) FROM {partition_name}) as row_count;
    """
    
    # List all partitions for a table
    LIST_PARTITIONS = """
        SELECT 
            child.relname as partition_name,
            pg_get_expr(child.relpartbound, child.oid) as partition_expression
        FROM pg_inherits
        JOIN pg_class parent ON pg_inherits.inhparent = parent.oid
        JOIN pg_class child ON pg_inherits.inhrelid = child.oid
        WHERE parent.relname = '{table_name}';
    """


# =============================================================================
# Partition Management Functions
# =============================================================================

def generate_partition_name(
    table_prefix: str,
    partition_date: date,
    interval: str = "month",
) -> str:
    """Generate partition name based on date and interval."""
    if interval == "month":
        return f"{table_prefix}{partition_date.year}_{partition_date.month:02d}"
    elif interval == "day":
        return f"{table_prefix}{partition_date.year}_{partition_date.month:02d}_{partition_date.day:02d}"
    else:
        raise ValueError(f"Unknown interval: {interval}")


def calculate_retention_date(
    retention_period: int,
    interval: str = "month",
) -> date:
    """Calculate the cutoff date for retention."""
    from datetime import timedelta
    
    today = date.today()
    
    if interval == "month":
        # Go back N months
        month = today.month - retention_period
        year = today.year
        while month <= 0:
            month += 12
            year -= 1
        return date(year, month, 1)
    elif interval == "day":
        return today - timedelta(days=retention_period)
    else:
        raise ValueError(f"Unknown interval: {interval}")

