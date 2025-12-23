"""SQLAlchemy model for time-off policies."""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, Float, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base


class AccrualMethod(str, Enum):
    """Methods for accruing time-off."""
    ANNUAL_LUMP_SUM = "annual_lump_sum"
    MONTHLY_ACCRUAL = "monthly_accrual"
    PAY_PERIOD_ACCRUAL = "pay_period_accrual"
    HOURS_WORKED = "hours_worked"
    NONE = "none"


class PolicyStatus(str, Enum):
    """Status of a policy."""
    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


class TimeOffPolicy(Base):
    """Model for time-off policies."""
    
    __tablename__ = "time_off_policy"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Basic info
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    policy_type: Mapped[str] = mapped_column(String(50), nullable=False, default="vacation")
    
    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=PolicyStatus.DRAFT.value,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    
    # Accrual configuration
    accrual_method: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=AccrualMethod.ANNUAL_LUMP_SUM.value,
    )
    base_accrual_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    accrual_frequency: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    accrual_cap: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Balance limits
    max_balance: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    min_balance_allowed: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    max_carryover: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    carryover_expiry_months: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Request rules
    min_request_days: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    max_request_days: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    advance_notice_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_consecutive_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Approval configuration
    requires_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    approval_levels: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    auto_approve_threshold: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Eligibility
    waiting_period_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    eligibility_criteria: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    
    # Tenure tiers (JSON array)
    tenure_tiers: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Additional settings
    allow_negative_balance: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    prorate_first_year: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    include_weekends: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    include_holidays: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    
    # Dates
    effective_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    expiry_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Audit
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        onupdate=func.now(),
    )
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    updated_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    def __repr__(self) -> str:
        return f"TimeOffPolicy(id={self.id}, name={self.name}, status={self.status})"


class PolicyVersion(Base):
    """Version history for policy changes."""
    
    __tablename__ = "time_off_policy_version"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    policy_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("time_off_policy.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Snapshot of policy at this version
    policy_snapshot: Mapped[str] = mapped_column(Text, nullable=False)  # JSON
    
    # Change info
    change_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    change_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Audit
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    created_by: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)


class PolicyAuditLog(Base):
    """Audit log for policy operations."""
    
    __tablename__ = "time_off_policy_audit_log"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    policy_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    
    # Action
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # Changes
    previous_values: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    new_values: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    
    # Actor
    performed_by: Mapped[int] = mapped_column(Integer, nullable=False)
    performed_by_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Context
    ip_address: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Timestamp
    performed_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

