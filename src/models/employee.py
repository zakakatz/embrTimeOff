"""SQLAlchemy Employee model for database operations."""

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.employee_audit_trail import EmployeeAuditTrail
    from src.models.holiday_calendar import HolidayCalendar


class Location(Base):
    """
    Office location with complete address information and operational fields.
    
    Extended with administrative fields for facility management, capacity tracking,
    and regulatory compliance.
    """
    
    __tablename__ = "location"
    
    # Primary Key
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # Basic Information
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # Address Fields
    address_line1: Mapped[str] = mapped_column(String(255), nullable=False)
    address_line2: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state_province: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), nullable=False, default="UTC")
    
    # =========================================================================
    # Extended Administrative Fields (WO-52)
    # =========================================================================
    
    # Location Classification
    location_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="office",
        comment="Type: office, warehouse, remote, satellite, headquarters"
    )
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    
    # Capacity Management
    capacity: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Maximum employee capacity for this location"
    )
    
    # Facility Management
    facility_manager_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("employee.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
        comment="Employee responsible for facility management"
    )
    
    # Operating Hours (JSON format: {"monday": {"open": "09:00", "close": "17:00"}, ...})
    operating_hours: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
        comment="Operating hours by day of week in JSON format"
    )
    
    # Holiday Calendar Reference
    holiday_calendar_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("holiday_calendar.id", ondelete="SET NULL"),
        nullable=True,
        comment="Reference to holiday calendar for this location"
    )
    
    # Regulatory and Tax Information
    regulatory_jurisdiction: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Regulatory jurisdiction code for compliance"
    )
    tax_jurisdiction: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Tax jurisdiction for payroll and tax purposes"
    )
    
    # Emergency Information (JSON format: {"name": "...", "phone": "...", "email": "..."})
    emergency_contact_info: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
        comment="Emergency contact information in JSON format"
    )
    
    # Facility Amenities (list of amenities: ["parking", "cafeteria", "gym", ...])
    facility_amenities: Mapped[Optional[List[str]]] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
        comment="List of available facility amenities"
    )
    
    # =========================================================================
    # Timestamps
    # =========================================================================
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    
    # =========================================================================
    # Relationships
    # =========================================================================
    
    employees: Mapped[list["Employee"]] = relationship(
        "Employee", back_populates="location", foreign_keys="Employee.location_id"
    )
    facility_manager: Mapped[Optional["Employee"]] = relationship(
        "Employee", foreign_keys=[facility_manager_id], post_update=True
    )
    holiday_calendar: Mapped[Optional["HolidayCalendar"]] = relationship(
        "HolidayCalendar", back_populates="locations", foreign_keys=[holiday_calendar_id]
    )


class WorkSchedule(Base):
    """
    Work schedule configuration with hours, days, and template management.
    
    Extended with template management fields for schedule type classification,
    overtime eligibility, and applicability restrictions.
    """
    
    __tablename__ = "work_schedule"
    
    # Primary Key
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # Basic Information
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Time Configuration
    hours_per_week: Mapped[Decimal] = mapped_column(
        Numeric(4, 2), nullable=False, default=Decimal("40.00")
    )
    days_per_week: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    start_time: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    end_time: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    is_flexible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    
    # =========================================================================
    # Extended Template Management Fields (WO-52)
    # =========================================================================
    
    # Schedule Classification
    schedule_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="standard",
        comment="Type: standard, shift, compressed, flexible, part_time, custom"
    )
    
    # Template Management
    is_template: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether this schedule can be used as a template"
    )
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    
    # Break Configuration
    break_duration_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=60,
        comment="Total break time in minutes per day"
    )
    
    # Overtime Configuration
    overtime_eligible: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether employees on this schedule are eligible for overtime"
    )
    
    # Weekend Work
    weekend_work_allowed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether weekend work is permitted under this schedule"
    )
    
    # Schedule Pattern (JSON format for complex patterns)
    # Example: {"pattern_type": "rotating", "rotation_days": 14, "shifts": [...]}
    schedule_pattern: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
        comment="Complex schedule pattern configuration in JSON format"
    )
    
    # Applicability Restrictions - Location IDs
    applicable_locations: Mapped[Optional[List[int]]] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
        comment="List of location IDs where this schedule can be applied"
    )
    
    # Applicability Restrictions - Department IDs
    applicable_departments: Mapped[Optional[List[int]]] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
        comment="List of department IDs where this schedule can be applied"
    )
    
    # =========================================================================
    # Timestamps
    # =========================================================================
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    
    # =========================================================================
    # Relationships
    # =========================================================================
    
    employees: Mapped[list["Employee"]] = relationship(
        "Employee", back_populates="work_schedule"
    )


class Department(Base):
    """
    Organizational department with hierarchical support and administrative fields.
    
    Extended with administrative fields for cost center tracking, budget management,
    approval workflows, and capacity constraints.
    """
    
    __tablename__ = "department"
    
    # Primary Key
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # Basic Information
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Hierarchy
    parent_department_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("department.id", ondelete="SET NULL"), nullable=True
    )
    head_of_department_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("employee.id", ondelete="SET NULL", use_alter=True), nullable=True
    )
    location_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("location.id", ondelete="SET NULL"), nullable=True
    )
    
    # =========================================================================
    # Extended Administrative Fields (WO-52)
    # =========================================================================
    
    # Financial Tracking
    cost_center: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Cost center code for financial tracking"
    )
    budget_code: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Budget code for expense allocation"
    )
    
    # Status and Dates
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    effective_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="Date when this department became effective"
    )
    end_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="Date when this department was discontinued (if applicable)"
    )
    
    # Organizational Structure
    organizational_level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="Level in organizational hierarchy (1 = top level)"
    )
    department_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="operational",
        comment="Type: operational, administrative, support, executive, project"
    )
    
    # Governance
    approval_required_for_changes: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether changes to this department require approval"
    )
    
    # Capacity Constraints
    max_employees: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Maximum number of employees allowed in this department"
    )
    
    # Location Restrictions (list of allowed location IDs)
    location_restrictions: Mapped[Optional[List[int]]] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
        comment="List of location IDs where employees in this department can be based"
    )
    
    # =========================================================================
    # Timestamps
    # =========================================================================
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    
    # =========================================================================
    # Relationships
    # =========================================================================
    
    parent_department: Mapped[Optional["Department"]] = relationship(
        "Department", remote_side=[id], foreign_keys=[parent_department_id]
    )
    head_of_department: Mapped[Optional["Employee"]] = relationship(
        "Employee", foreign_keys=[head_of_department_id], post_update=True
    )
    location: Mapped[Optional["Location"]] = relationship("Location")
    employees: Mapped[list["Employee"]] = relationship(
        "Employee", back_populates="department", foreign_keys="Employee.department_id"
    )


class Employee(Base):
    """
    Core employee model with personal info, contact details, and employment data.
    
    Supports organizational hierarchy via manager relationship and
    comprehensive employment tracking.
    """
    
    __tablename__ = "employee"
    
    # Primary Key
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # Unique Identifiers
    employee_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    
    # Personal Information
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    middle_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    preferred_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    
    # Contact Information
    personal_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone_number: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    mobile_number: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    address_line1: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    address_line2: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    state_province: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Employment Information - Foreign Keys
    department_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("department.id", ondelete="SET NULL"), nullable=True, index=True
    )
    manager_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("employee.id", ondelete="SET NULL"), nullable=True, index=True
    )
    location_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("location.id", ondelete="SET NULL"), nullable=True, index=True
    )
    work_schedule_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("work_schedule.id", ondelete="SET NULL"), nullable=True
    )
    
    # Employment Information - Details
    job_title: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    employment_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    employment_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="active", index=True
    )
    hire_date: Mapped[date] = mapped_column(Date, nullable=False)
    termination_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    
    # Compensation
    salary: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    hourly_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2), nullable=True)
    
    # System Fields
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    
    # Relationships
    department: Mapped[Optional["Department"]] = relationship(
        "Department", back_populates="employees", foreign_keys=[department_id]
    )
    manager: Mapped[Optional["Employee"]] = relationship(
        "Employee", remote_side=[id], foreign_keys=[manager_id], backref="direct_reports"
    )
    location: Mapped[Optional["Location"]] = relationship(
        "Location", back_populates="employees", foreign_keys=[location_id]
    )
    work_schedule: Mapped[Optional["WorkSchedule"]] = relationship(
        "WorkSchedule", back_populates="employees"
    )
    audit_trails: Mapped[list["EmployeeAuditTrail"]] = relationship(
        "EmployeeAuditTrail", backref="employee", cascade="all, delete-orphan"
    )
    
    # Composite indexes for common query patterns
    __table_args__ = (
        Index("idx_employee_name", "last_name", "first_name"),
    )
    
    def __repr__(self) -> str:
        return (
            f"<Employee("
            f"id={self.id}, "
            f"employee_id={self.employee_id}, "
            f"name={self.first_name} {self.last_name}"
            f")>"
        )
    
    def to_dict(self) -> dict:
        """Convert employee to dictionary for audit logging."""
        return {
            "id": self.id,
            "employee_id": self.employee_id,
            "email": self.email,
            "first_name": self.first_name,
            "middle_name": self.middle_name,
            "last_name": self.last_name,
            "preferred_name": self.preferred_name,
            "date_of_birth": self.date_of_birth,
            "gender": self.gender,
            "personal_email": self.personal_email,
            "phone_number": self.phone_number,
            "mobile_number": self.mobile_number,
            "address_line1": self.address_line1,
            "address_line2": self.address_line2,
            "city": self.city,
            "state_province": self.state_province,
            "postal_code": self.postal_code,
            "country": self.country,
            "department_id": self.department_id,
            "manager_id": self.manager_id,
            "location_id": self.location_id,
            "work_schedule_id": self.work_schedule_id,
            "job_title": self.job_title,
            "employment_type": self.employment_type,
            "employment_status": self.employment_status,
            "hire_date": self.hire_date,
            "termination_date": self.termination_date,
            "salary": self.salary,
            "hourly_rate": self.hourly_rate,
            "is_active": self.is_active,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

