"""SQLAlchemy model for approval delegates."""

from datetime import datetime, date
from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base


class DelegateStatus(str, Enum):
    """Status of a delegate assignment."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"
    REVOKED = "revoked"


class DelegateScope(str, Enum):
    """Scope of delegation."""
    ALL = "all"  # All approval types
    TIME_OFF = "time_off"  # Time-off approvals only
    EXPENSE = "expense"  # Expense approvals only
    PROFILE_CHANGES = "profile_changes"  # Profile change approvals only


class ApprovalDelegate(Base):
    """Model for approval delegate assignments."""
    
    __tablename__ = "approval_delegate"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Delegator (manager assigning their approval authority)
    delegator_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("employee.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Delegate (person receiving approval authority)
    delegate_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("employee.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Delegation scope
    scope: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=DelegateScope.ALL.value,
    )
    
    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=DelegateStatus.ACTIVE.value,
        index=True,
    )
    
    # Effective dates
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    
    # Limitations
    max_approval_amount: Mapped[Optional[float]] = mapped_column(Integer, nullable=True)
    max_approval_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    team_scope_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    
    # Reason for delegation
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Contact info during delegation
    delegator_contact: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
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
    created_by: Mapped[int] = mapped_column(Integer, nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    revoked_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    revoke_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Relationships
    delegator: Mapped["Employee"] = relationship(
        "Employee",
        foreign_keys=[delegator_id],
        backref="delegations_given",
    )
    delegate: Mapped["Employee"] = relationship(
        "Employee",
        foreign_keys=[delegate_id],
        backref="delegations_received",
    )
    
    def __repr__(self) -> str:
        return (
            f"ApprovalDelegate(id={self.id}, delegator={self.delegator_id}, "
            f"delegate={self.delegate_id}, status={self.status})"
        )
    
    @property
    def is_active(self) -> bool:
        """Check if delegation is currently active."""
        today = date.today()
        return (
            self.status == DelegateStatus.ACTIVE.value and
            self.start_date <= today <= self.end_date
        )


class DelegateAuditLog(Base):
    """Audit log for delegate operations."""
    
    __tablename__ = "delegate_audit_log"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    delegate_assignment_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    
    # Action
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # Details
    previous_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    new_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    
    # Actor
    performed_by: Mapped[int] = mapped_column(Integer, nullable=False)
    performed_by_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Timestamp
    performed_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )


