"""SQLAlchemy models for holiday calendar management.

Provides database schema for managing location-specific holiday schedules,
supporting multi-regional operations with different holiday observances.
"""

from datetime import date, datetime
from enum import Enum
from typing import TYPE_CHECKING, List, Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.employee import Employee


# =============================================================================
# Enums
# =============================================================================

class HolidayType(str, Enum):
    """Type classification for holidays."""
    
    NATIONAL = "national"
    RELIGIOUS = "religious"
    COMPANY = "company"
    REGIONAL = "regional"


# =============================================================================
# HolidayCalendar Model
# =============================================================================

class HolidayCalendar(Base):
    """
    Calendar for managing location-specific holiday schedules.
    
    Supports multi-regional operations by allowing different calendars
    for different countries and regions. Each calendar can contain
    multiple holidays and be assigned to one or more locations.
    """
    
    __tablename__ = "holiday_calendar"
    
    # Primary Key (UUID)
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
        comment="Unique identifier for the calendar",
    )
    
    # Basic Information
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Display name of the holiday calendar",
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Detailed description of the calendar",
    )
    
    # Geographic Scope
    country: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Country this calendar applies to",
    )
    region: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Region or state within the country (if applicable)",
    )
    
    # Year and Status
    calendar_year: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
        comment="Year this calendar is for",
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether this is the default calendar for the country/region",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether this calendar is active and available for use",
    )
    
    # Audit Fields - Created By
    created_by_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("employee.id", ondelete="SET NULL"),
        nullable=False,
        comment="Employee who created this calendar",
    )
    
    # Audit Fields - Approved By (optional approval workflow)
    approved_by_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("employee.id", ondelete="SET NULL"),
        nullable=True,
        comment="Employee who approved this calendar (if approval required)",
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Timestamp when the calendar was created",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Timestamp when the calendar was last updated",
    )
    
    # =========================================================================
    # Relationships
    # =========================================================================
    
    holidays: Mapped[List["Holiday"]] = relationship(
        "Holiday",
        back_populates="calendar",
        cascade="all, delete-orphan",
        order_by="Holiday.date",
    )
    
    created_by: Mapped["Employee"] = relationship(
        "Employee",
        foreign_keys=[created_by_id],
        lazy="select",
    )
    
    approved_by: Mapped[Optional["Employee"]] = relationship(
        "Employee",
        foreign_keys=[approved_by_id],
        lazy="select",
    )
    
    locations: Mapped[List["Location"]] = relationship(
        "Location",
        back_populates="holiday_calendar",
        lazy="select",
    )
    
    # =========================================================================
    # Table Arguments
    # =========================================================================
    
    __table_args__ = (
        # Unique constraint for default calendar per country/region/year
        UniqueConstraint(
            "country",
            "region",
            "calendar_year",
            "is_default",
            name="uq_default_calendar_per_country_region_year",
        ),
        # Composite index for common lookups
        Index(
            "ix_holiday_calendar_country_year",
            "country",
            "calendar_year",
        ),
        Index(
            "ix_holiday_calendar_active_year",
            "is_active",
            "calendar_year",
        ),
    )
    
    def __repr__(self) -> str:
        return (
            f"HolidayCalendar(id={self.id}, name={self.name}, "
            f"country={self.country}, year={self.calendar_year})"
        )
    
    @property
    def holiday_count(self) -> int:
        """Return the number of holidays in this calendar."""
        return len(self.holidays) if self.holidays else 0
    
    @property
    def paid_holiday_count(self) -> int:
        """Return the number of paid holidays in this calendar."""
        if not self.holidays:
            return 0
        return sum(1 for h in self.holidays if h.is_paid)


# =============================================================================
# Holiday Model
# =============================================================================

class Holiday(Base):
    """
    Individual holiday within a calendar.
    
    Represents a specific holiday with its date, type, and
    configuration for payroll and scheduling purposes.
    """
    
    __tablename__ = "holiday"
    
    # Primary Key (UUID)
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
        comment="Unique identifier for the holiday",
    )
    
    # Calendar Reference
    calendar_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("holiday_calendar.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to the parent calendar",
    )
    
    # Holiday Details
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Name of the holiday",
    )
    date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
        comment="Date of the holiday",
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Additional description or notes about the holiday",
    )
    
    # Recurrence Configuration
    is_recurring: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether this holiday recurs annually",
    )
    
    # Holiday Classification
    holiday_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=HolidayType.NATIONAL.value,
        comment="Type: national, religious, company, regional",
    )
    
    # Payroll Configuration
    is_paid: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether employees are paid for this holiday",
    )
    
    # Mandatory Observance
    is_mandatory: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether observance of this holiday is mandatory (office closed)",
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Timestamp when the holiday was created",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Timestamp when the holiday was last updated",
    )
    
    # =========================================================================
    # Relationships
    # =========================================================================
    
    calendar: Mapped["HolidayCalendar"] = relationship(
        "HolidayCalendar",
        back_populates="holidays",
    )
    
    # =========================================================================
    # Table Arguments
    # =========================================================================
    
    __table_args__ = (
        # Prevent duplicate holidays on the same date in a calendar
        UniqueConstraint(
            "calendar_id",
            "date",
            name="uq_holiday_calendar_date",
        ),
        # Index for date range queries
        Index(
            "ix_holiday_calendar_date_range",
            "calendar_id",
            "date",
        ),
    )
    
    def __repr__(self) -> str:
        return (
            f"Holiday(id={self.id}, name={self.name}, "
            f"date={self.date}, type={self.holiday_type})"
        )
    
    @property
    def holiday_type_enum(self) -> HolidayType:
        """Get holiday type as enum."""
        return HolidayType(self.holiday_type)
    
    @property
    def is_national(self) -> bool:
        """Check if this is a national holiday."""
        return self.holiday_type == HolidayType.NATIONAL.value
    
    @property
    def is_company_holiday(self) -> bool:
        """Check if this is a company-specific holiday."""
        return self.holiday_type == HolidayType.COMPANY.value


# Import Location here to avoid circular import at module level
from src.models.employee import Location  # noqa: E402

