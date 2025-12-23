"""SQLAlchemy model for reporting relationships.

Manages complex organizational reporting structures including:
- Direct reports
- Matrix reporting
- Dotted line relationships
- Temporary reporting arrangements
"""

from datetime import date, datetime
from enum import Enum
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Index,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base


class RelationshipType(str, Enum):
    """Type of reporting relationship."""
    
    DIRECT = "direct"           # Standard direct report
    DOTTED_LINE = "dotted_line" # Secondary reporting line
    MATRIX = "matrix"           # Matrix organization reporting
    TEMPORARY = "temporary"     # Temporary assignment


class AuthorityLevel(str, Enum):
    """Level of authority in the relationship."""
    
    FULL = "full"           # Full management authority
    LIMITED = "limited"     # Limited authority (specific functions)
    ADVISORY = "advisory"   # Advisory role only


class ReportingRelationship(Base):
    """
    Model for managing reporting relationships between employees.
    
    Supports complex organizational structures including matrix organizations,
    dotted line reporting, and temporary assignments.
    
    Attributes:
        id: Unique identifier for the relationship (UUID)
        employee_id: The employee who reports (UUID FK to Employee)
        manager_id: The manager being reported to (UUID FK to Employee)
        relationship_type: Type of reporting relationship
        effective_date: When the relationship starts
        end_date: When the relationship ends (null if ongoing)
        is_primary: Whether this is the primary reporting relationship
        authority_level: Level of authority the manager has
        created_by_id: Who created this relationship (UUID FK to Employee)
        approved_by_id: Who approved this relationship (UUID FK to Employee)
        created_at: Timestamp of creation
        updated_at: Timestamp of last update
    """
    
    __tablename__ = "reporting_relationship"
    
    # Primary key - using Integer for compatibility, can be UUID in production
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    
    # UUID field for external reference
    uuid: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        nullable=False,
        default=lambda: str(uuid4()),
        index=True,
    )
    
    # Foreign keys to Employee table
    employee_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("employee.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    manager_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("employee.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Relationship type
    relationship_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=RelationshipType.DIRECT.value,
    )
    
    # Effective dates
    effective_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    
    end_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )
    
    # Relationship flags
    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    
    # Authority level
    authority_level: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=AuthorityLevel.FULL.value,
    )
    
    # Audit fields - who created/approved
    created_by_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("employee.id", ondelete="SET NULL"),
        nullable=False,
    )
    
    approved_by_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("employee.id", ondelete="SET NULL"),
        nullable=True,
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
    
    # Additional metadata
    notes: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    
    # Status for soft delete / deactivation
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    
    # Relationships
    employee: Mapped["Employee"] = relationship(
        "Employee",
        foreign_keys=[employee_id],
        backref="reporting_relationships_as_employee",
    )
    
    manager: Mapped["Employee"] = relationship(
        "Employee",
        foreign_keys=[manager_id],
        backref="reporting_relationships_as_manager",
    )
    
    created_by: Mapped["Employee"] = relationship(
        "Employee",
        foreign_keys=[created_by_id],
    )
    
    approved_by: Mapped[Optional["Employee"]] = relationship(
        "Employee",
        foreign_keys=[approved_by_id],
    )
    
    # Table constraints and indexes
    __table_args__ = (
        # Ensure unique active primary relationship per employee
        UniqueConstraint(
            "employee_id",
            "is_primary",
            name="uq_employee_primary_relationship",
            # Note: This constraint should be conditional (only when is_primary=True)
            # In practice, use a partial unique index in PostgreSQL
        ),
        
        # Index for finding all reports of a manager
        Index(
            "ix_reporting_relationship_manager_active",
            "manager_id",
            "is_active",
        ),
        
        # Index for finding relationship by type
        Index(
            "ix_reporting_relationship_type",
            "relationship_type",
        ),
        
        # Index for date range queries
        Index(
            "ix_reporting_relationship_dates",
            "effective_date",
            "end_date",
        ),
        
        # Composite index for common queries
        Index(
            "ix_reporting_relationship_employee_manager_active",
            "employee_id",
            "manager_id",
            "is_active",
        ),
    )
    
    def __repr__(self) -> str:
        return (
            f"ReportingRelationship("
            f"id={self.id}, "
            f"employee_id={self.employee_id}, "
            f"manager_id={self.manager_id}, "
            f"type={self.relationship_type}, "
            f"is_primary={self.is_primary})"
        )
    
    @property
    def is_current(self) -> bool:
        """Check if this relationship is currently active."""
        today = date.today()
        return (
            self.is_active
            and self.effective_date <= today
            and (self.end_date is None or self.end_date >= today)
        )
    
    @property
    def relationship_type_enum(self) -> RelationshipType:
        """Get the relationship type as an enum."""
        return RelationshipType(self.relationship_type)
    
    @property
    def authority_level_enum(self) -> AuthorityLevel:
        """Get the authority level as an enum."""
        return AuthorityLevel(self.authority_level)


class ReportingRelationshipHistory(Base):
    """
    Audit trail for reporting relationship changes.
    
    Tracks all changes to reporting relationships for compliance
    and historical analysis.
    """
    
    __tablename__ = "reporting_relationship_history"
    
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    
    # Reference to the relationship
    relationship_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("reporting_relationship.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Change details
    action: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )  # created, updated, ended, deactivated
    
    # Previous values (as JSON string)
    previous_values: Mapped[Optional[str]] = mapped_column(
        String,  # Store as JSON
        nullable=True,
    )
    
    # New values (as JSON string)
    new_values: Mapped[Optional[str]] = mapped_column(
        String,  # Store as JSON
        nullable=True,
    )
    
    # Who made the change
    changed_by_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("employee.id", ondelete="SET NULL"),
        nullable=False,
    )
    
    # When the change was made
    changed_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    
    # Reason for change
    change_reason: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    
    # Relationships
    relationship: Mapped["ReportingRelationship"] = relationship(
        "ReportingRelationship",
        backref="history",
    )
    
    changed_by: Mapped["Employee"] = relationship(
        "Employee",
        foreign_keys=[changed_by_id],
    )
    
    def __repr__(self) -> str:
        return (
            f"ReportingRelationshipHistory("
            f"id={self.id}, "
            f"relationship_id={self.relationship_id}, "
            f"action={self.action})"
        )

