"""SQLAlchemy models for time-off request system.

Provides comprehensive database schema for managing employee time-off requests,
approvals, audit trails, and delegation of approval authority.
"""

from datetime import date, datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Index,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base


# =============================================================================
# Enums
# =============================================================================

class RequestType(str, Enum):
    """Type of time-off request."""
    
    VACATION = "vacation"
    SICK = "sick"
    PERSONAL = "personal"
    FLOATING_HOLIDAY = "floating_holiday"
    BEREAVEMENT = "bereavement"
    JURY_DUTY = "jury_duty"
    PARENTAL = "parental"
    UNPAID = "unpaid"
    COMPENSATORY = "compensatory"


class RequestStatus(str, Enum):
    """Status of a time-off request."""
    
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    CANCELLED = "cancelled"
    WITHDRAWN = "withdrawn"


class ApprovalStatus(str, Enum):
    """Status of an approval action."""
    
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"


class AuditAction(str, Enum):
    """Actions tracked in audit log."""
    
    SUBMITTED = "submitted"
    APPROVED = "approved"
    DENIED = "denied"
    CANCELLED = "cancelled"
    WITHDRAWN = "withdrawn"
    MODIFIED = "modified"
    ESCALATED = "escalated"
    DELEGATED = "delegated"


# =============================================================================
# TimeOffRequest Model
# =============================================================================

class TimeOffRequest(Base):
    """
    Core model for time-off requests.
    
    Tracks employee requests for time off including dates, type,
    status, and associated comments.
    """
    
    __tablename__ = "time_off_request"
    
    # Primary key
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    
    # Employee making the request
    employee_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("employee.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Policy reference (optional - for policy-based time off)
    policy_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("time_off_policy.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # Request type
    request_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=RequestType.VACATION.value,
    )
    
    # Date range
    start_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    end_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    
    # Hours requested (for partial day requests)
    hours_requested: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=8.0,
    )
    
    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=RequestStatus.PENDING.value,
        index=True,
    )
    
    # Comments
    employee_comments: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    manager_comments: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    
    # Key timestamps
    submitted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )
    denied_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )
    
    # Audit timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    
    # Relationships
    employee: Mapped["Employee"] = relationship(
        "Employee",
        foreign_keys=[employee_id],
        backref="time_off_requests",
    )
    
    approvals: Mapped[List["RequestApproval"]] = relationship(
        "RequestApproval",
        back_populates="request",
        cascade="all, delete-orphan",
    )
    
    audit_logs: Mapped[List["RequestAuditLog"]] = relationship(
        "RequestAuditLog",
        back_populates="request",
        cascade="all, delete-orphan",
    )
    
    # Indexes
    __table_args__ = (
        Index("ix_time_off_request_employee_dates", "employee_id", "start_date", "end_date"),
        Index("ix_time_off_request_status_dates", "status", "start_date"),
    )
    
    def __repr__(self) -> str:
        return (
            f"TimeOffRequest(id={self.id}, employee_id={self.employee_id}, "
            f"type={self.request_type}, status={self.status})"
        )
    
    @property
    def request_type_enum(self) -> RequestType:
        """Get request type as enum."""
        return RequestType(self.request_type)
    
    @property
    def status_enum(self) -> RequestStatus:
        """Get status as enum."""
        return RequestStatus(self.status)


# =============================================================================
# RequestApproval Model
# =============================================================================

class RequestApproval(Base):
    """
    Model for tracking approval actions on time-off requests.
    
    Supports multi-level approval workflows where multiple approvers
    may need to sign off on a request.
    """
    
    __tablename__ = "request_approval"
    
    # Primary key
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    
    # Reference to the request
    request_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("time_off_request.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Approver
    approver_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("employee.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Approval level (1 = first level, 2 = second level, etc.)
    approval_level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
    
    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ApprovalStatus.PENDING.value,
    )
    
    # Comments from approver
    comments: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    
    # Action timestamps
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )
    denied_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )
    
    # Audit timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    
    # Relationships
    request: Mapped["TimeOffRequest"] = relationship(
        "TimeOffRequest",
        back_populates="approvals",
    )
    
    approver: Mapped["Employee"] = relationship(
        "Employee",
        foreign_keys=[approver_id],
    )
    
    # Constraints
    __table_args__ = (
        UniqueConstraint(
            "request_id",
            "approver_id",
            "approval_level",
            name="uq_request_approver_level",
        ),
    )
    
    def __repr__(self) -> str:
        return (
            f"RequestApproval(id={self.id}, request_id={self.request_id}, "
            f"approver_id={self.approver_id}, status={self.status})"
        )
    
    @property
    def status_enum(self) -> ApprovalStatus:
        """Get status as enum."""
        return ApprovalStatus(self.status)


# =============================================================================
# RequestAuditLog Model
# =============================================================================

class RequestAuditLog(Base):
    """
    Audit log for time-off request changes.
    
    Tracks all actions taken on requests for compliance
    and historical tracking.
    """
    
    __tablename__ = "request_audit_log"
    
    # Primary key
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    
    # Reference to the request
    request_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("time_off_request.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Who performed the action
    actor_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("employee.id", ondelete="SET NULL"),
        nullable=False,
    )
    
    # Action taken
    action: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )
    
    # Status transition
    previous_status: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )
    new_status: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )
    
    # Comments
    comments: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    
    # Additional details (JSON)
    details: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    
    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    
    # IP address and user agent for security
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    user_agent: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    
    # Relationships
    request: Mapped["TimeOffRequest"] = relationship(
        "TimeOffRequest",
        back_populates="audit_logs",
    )
    
    actor: Mapped["Employee"] = relationship(
        "Employee",
        foreign_keys=[actor_id],
    )
    
    def __repr__(self) -> str:
        return (
            f"RequestAuditLog(id={self.id}, request_id={self.request_id}, "
            f"action={self.action})"
        )
    
    @property
    def action_enum(self) -> AuditAction:
        """Get action as enum."""
        return AuditAction(self.action)


# =============================================================================
# ApprovalDelegate Model
# =============================================================================

class ApprovalDelegate(Base):
    """
    Model for delegating approval authority.
    
    Allows managers to delegate their approval authority to another
    employee for a specified time period.
    """
    
    __tablename__ = "approval_delegate"
    
    # Primary key
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    
    # Manager delegating authority
    manager_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("employee.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Delegate receiving authority
    delegate_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("employee.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Effective period
    start_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    end_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    
    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    
    # Reason for delegation
    reason: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    
    # Scope of delegation (all requests or specific types)
    scope: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        default="all",
    )
    
    # Audit timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    
    # Relationships
    manager: Mapped["Employee"] = relationship(
        "Employee",
        foreign_keys=[manager_id],
        backref="delegations_given",
    )
    
    delegate: Mapped["Employee"] = relationship(
        "Employee",
        foreign_keys=[delegate_id],
        backref="delegations_received",
    )
    
    # Constraints
    __table_args__ = (
        Index("ix_approval_delegate_active", "is_active", "start_date", "end_date"),
    )
    
    def __repr__(self) -> str:
        return (
            f"ApprovalDelegate(id={self.id}, manager_id={self.manager_id}, "
            f"delegate_id={self.delegate_id}, is_active={self.is_active})"
        )
    
    @property
    def is_current(self) -> bool:
        """Check if delegation is currently active."""
        today = date.today()
        return (
            self.is_active
            and self.start_date <= today
            and self.end_date >= today
        )


# =============================================================================
# TimeOffPolicy Model (Referenced by TimeOffRequest)
# =============================================================================

class TimeOffPolicy(Base):
    """
    Model for time-off policies.
    
    Defines the rules and balances for different types of time off.
    """
    
    __tablename__ = "time_off_policy"
    
    # Primary key
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    
    # Policy name
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    
    # Policy code
    code: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        unique=True,
    )
    
    # Description
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    
    # Request type this policy applies to
    request_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )
    
    # Accrual settings
    accrual_rate: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    accrual_period: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="monthly",
    )
    max_balance: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    max_carryover: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    
    # Request limits
    min_request_days: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.5,
    )
    max_request_days: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    advance_notice_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    
    # Approval settings
    requires_approval: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    approval_levels: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
    
    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    
    def __repr__(self) -> str:
        return f"TimeOffPolicy(id={self.id}, code={self.code}, name={self.name})"

