"""SQLAlchemy model for time-off requests."""

from datetime import date, datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base


class TimeOffType(str, Enum):
    """Types of time off."""
    
    VACATION = "vacation"
    SICK = "sick"
    PERSONAL = "personal"
    BEREAVEMENT = "bereavement"
    JURY_DUTY = "jury_duty"
    PARENTAL = "parental"
    UNPAID = "unpaid"
    FLOATING_HOLIDAY = "floating_holiday"
    COMPENSATORY = "compensatory"


class TimeOffRequestStatus(str, Enum):
    """Status of time-off request."""
    
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class TimeOffRequest(Base):
    """Model for employee time-off requests."""
    
    __tablename__ = "time_off_request"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Employee reference
    employee_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("employee.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Request details
    request_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=TimeOffType.VACATION.value,
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    
    # Duration
    total_days: Mapped[float] = mapped_column(Integer, nullable=False, default=1)
    is_half_day: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    half_day_period: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )  # morning or afternoon
    
    # Reason and notes
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    employee_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Status
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=TimeOffRequestStatus.DRAFT.value,
        index=True,
    )
    
    # Approver information
    current_approver_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("employee.id", ondelete="SET NULL"),
        nullable=True,
    )
    approval_level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    
    # Balance impact
    balance_before: Mapped[Optional[float]] = mapped_column(Integer, nullable=True)
    balance_after: Mapped[Optional[float]] = mapped_column(Integer, nullable=True)
    
    # Conflict information (stored as JSON string)
    conflicts_detected: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Approval notes
    approver_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Timestamps
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
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    rejected_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Audit
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    updated_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Relationships
    employee: Mapped["Employee"] = relationship(
        "Employee",
        foreign_keys=[employee_id],
        back_populates="time_off_requests",
    )
    current_approver: Mapped[Optional["Employee"]] = relationship(
        "Employee",
        foreign_keys=[current_approver_id],
    )
    
    def __repr__(self) -> str:
        return (
            f"TimeOffRequest(id={self.id}, employee_id={self.employee_id}, "
            f"type={self.request_type}, status={self.status})"
        )


class TimeOffRequestAudit(Base):
    """Audit trail for time-off request changes."""
    
    __tablename__ = "time_off_request_audit"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    request_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("time_off_request.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Action details
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    previous_status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    new_status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    
    # Actor
    performed_by: Mapped[int] = mapped_column(Integer, nullable=False)
    performed_by_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Details
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    changes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    
    # Timestamp
    performed_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    
    # IP and user agent for security
    ip_address: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)


class TimeOffBalance(Base):
    """Employee time-off balance tracking."""
    
    __tablename__ = "time_off_balance"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    employee_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("employee.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Balance type
    balance_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=TimeOffType.VACATION.value,
    )
    
    # Year
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Balance values
    total_allocated: Mapped[float] = mapped_column(Integer, nullable=False, default=0)
    used: Mapped[float] = mapped_column(Integer, nullable=False, default=0)
    pending: Mapped[float] = mapped_column(Integer, nullable=False, default=0)
    available: Mapped[float] = mapped_column(Integer, nullable=False, default=0)
    
    # Carryover
    carried_over: Mapped[float] = mapped_column(Integer, nullable=False, default=0)
    
    # Timestamps
    last_updated: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

