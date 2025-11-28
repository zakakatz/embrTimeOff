"""Pydantic models for employee API operations with validation rules."""

import re
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


# =============================================================================
# Enums
# =============================================================================

class EmploymentType(str, Enum):
    """Employment type classification."""
    
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACTOR = "contractor"
    INTERN = "intern"


class EmployeeStatus(str, Enum):
    """Employee status values."""
    
    ACTIVE = "active"
    INACTIVE = "inactive"
    TERMINATED = "terminated"


# =============================================================================
# Response Models - Nested Objects
# =============================================================================

class DepartmentResponse(BaseModel):
    """Department data for API responses."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    code: str
    name: str
    description: Optional[str] = None
    parent_department_id: Optional[int] = None
    is_active: bool = True


class LocationResponse(BaseModel):
    """Location data for API responses."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    code: str
    name: str
    address_line1: str
    address_line2: Optional[str] = None
    city: str
    state_province: Optional[str] = None
    postal_code: Optional[str] = None
    country: str
    timezone: str = "UTC"
    is_active: bool = True


class WorkScheduleResponse(BaseModel):
    """Work schedule data for API responses."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    name: str
    description: Optional[str] = None
    hours_per_week: Decimal = Field(default=Decimal("40.00"))
    days_per_week: int = 5
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    is_flexible: bool = False
    is_active: bool = True


class EmployeeBasicResponse(BaseModel):
    """
    Basic employee data for manager references.
    
    Used to avoid circular dependencies in nested response objects.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    employee_id: str
    email: str
    first_name: str
    last_name: str
    preferred_name: Optional[str] = None
    job_title: Optional[str] = None


# =============================================================================
# Response Models - Full Employee
# =============================================================================

class EmployeeResponse(BaseModel):
    """
    Complete employee data for API responses.
    
    Includes nested objects for department, location, manager, and work schedule.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    # Identification
    id: int
    employee_id: str
    email: str
    
    # Personal Information
    first_name: str
    middle_name: Optional[str] = None
    last_name: str
    preferred_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    
    # Contact Information
    personal_email: Optional[str] = None
    phone_number: Optional[str] = None
    mobile_number: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state_province: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    
    # Employment Information
    job_title: Optional[str] = None
    employment_type: Optional[EmploymentType] = None
    employment_status: EmployeeStatus = EmployeeStatus.ACTIVE
    hire_date: date
    termination_date: Optional[date] = None
    salary: Optional[Decimal] = Field(default=None, max_digits=12, decimal_places=2)
    hourly_rate: Optional[Decimal] = Field(default=None, max_digits=8, decimal_places=2)
    
    # Nested relationships
    department: Optional[DepartmentResponse] = None
    location: Optional[LocationResponse] = None
    manager: Optional[EmployeeBasicResponse] = None
    work_schedule: Optional[WorkScheduleResponse] = None
    
    # System fields
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


# =============================================================================
# Request Models
# =============================================================================

# Phone number regex pattern (flexible international format)
PHONE_PATTERN = re.compile(r"^\+?[1-9]\d{1,14}$|^\+?[0-9\s\-\(\)]{7,20}$")


class EmployeeCreateRequest(BaseModel):
    """
    Request model for creating a new employee.
    
    Includes comprehensive validation rules for all fields.
    """
    
    model_config = ConfigDict(str_strip_whitespace=True)
    
    # Required identification
    employee_id: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Unique employee identifier",
    )
    email: EmailStr = Field(
        ...,
        max_length=255,
        description="Work email address",
    )
    
    # Required personal information
    first_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Employee's first name",
    )
    last_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Employee's last name",
    )
    
    # Optional personal information
    middle_name: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Employee's middle name",
    )
    preferred_name: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Preferred name or nickname",
    )
    date_of_birth: Optional[date] = Field(
        default=None,
        description="Date of birth",
    )
    gender: Optional[str] = Field(
        default=None,
        max_length=20,
        description="Gender",
    )
    
    # Contact information
    personal_email: Optional[EmailStr] = Field(
        default=None,
        max_length=255,
        description="Personal email address",
    )
    phone_number: Optional[str] = Field(
        default=None,
        max_length=30,
        description="Work phone number",
    )
    mobile_number: Optional[str] = Field(
        default=None,
        max_length=30,
        description="Mobile phone number",
    )
    address_line1: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Street address line 1",
    )
    address_line2: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Street address line 2",
    )
    city: Optional[str] = Field(
        default=None,
        max_length=100,
        description="City",
    )
    state_province: Optional[str] = Field(
        default=None,
        max_length=100,
        description="State or province",
    )
    postal_code: Optional[str] = Field(
        default=None,
        max_length=20,
        description="Postal/ZIP code",
    )
    country: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Country",
    )
    
    # Employment information
    department_id: Optional[int] = Field(
        default=None,
        description="Department ID",
    )
    manager_id: Optional[int] = Field(
        default=None,
        description="Manager's employee ID",
    )
    location_id: Optional[int] = Field(
        default=None,
        description="Work location ID",
    )
    work_schedule_id: Optional[int] = Field(
        default=None,
        description="Work schedule ID",
    )
    job_title: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Job title",
    )
    employment_type: Optional[EmploymentType] = Field(
        default=None,
        description="Employment type",
    )
    employment_status: EmployeeStatus = Field(
        default=EmployeeStatus.ACTIVE,
        description="Employment status",
    )
    hire_date: date = Field(
        ...,
        description="Date of hire",
    )
    termination_date: Optional[date] = Field(
        default=None,
        description="Date of termination (if applicable)",
    )
    
    # Compensation
    salary: Optional[Decimal] = Field(
        default=None,
        max_digits=12,
        decimal_places=2,
        ge=Decimal("0"),
        description="Annual salary (12 digits, 2 decimal places)",
    )
    hourly_rate: Optional[Decimal] = Field(
        default=None,
        max_digits=8,
        decimal_places=2,
        ge=Decimal("0"),
        description="Hourly rate (8 digits, 2 decimal places)",
    )
    
    @field_validator("phone_number", "mobile_number")
    @classmethod
    def validate_phone_format(cls, v: Optional[str]) -> Optional[str]:
        """Validate phone number format."""
        if v is None:
            return v
        # Remove common formatting characters for validation
        cleaned = re.sub(r"[\s\-\(\)]", "", v)
        if not re.match(r"^\+?[0-9]{7,15}$", cleaned):
            raise ValueError(
                "Invalid phone number format. Use international format (e.g., +1234567890) "
                "or standard format with 7-15 digits."
            )
        return v
    
    @field_validator("hire_date")
    @classmethod
    def validate_hire_date_not_future(cls, v: date) -> date:
        """Ensure hire date is not in the future."""
        if v > date.today():
            raise ValueError("Hire date cannot be in the future")
        return v
    
    @field_validator("salary")
    @classmethod
    def validate_salary_precision(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Validate salary has correct precision (12 digits, 2 decimal places)."""
        if v is None:
            return v
        # Check total digits (max 12 including decimals, with 2 decimal places)
        if v >= Decimal("10000000000"):  # 10^10 = max with 2 decimal places for 12 digits
            raise ValueError("Salary must have at most 12 digits total")
        return v
    
    @field_validator("hourly_rate")
    @classmethod
    def validate_hourly_rate_precision(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Validate hourly rate has correct precision (8 digits, 2 decimal places)."""
        if v is None:
            return v
        # Check total digits (max 8 including decimals, with 2 decimal places)
        if v >= Decimal("1000000"):  # 10^6 = max with 2 decimal places for 8 digits
            raise ValueError("Hourly rate must have at most 8 digits total")
        return v
    
    @model_validator(mode="after")
    def validate_termination_after_hire(self) -> "EmployeeCreateRequest":
        """Ensure termination date is after hire date when provided."""
        if self.termination_date is not None and self.hire_date is not None:
            if self.termination_date <= self.hire_date:
                raise ValueError("Termination date must be after hire date")
        return self


class EmployeeUpdateRequest(BaseModel):
    """
    Request model for updating an employee.
    
    All fields are optional to support partial updates.
    """
    
    model_config = ConfigDict(str_strip_whitespace=True)
    
    # Identification (optional for updates)
    employee_id: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=20,
        description="Unique employee identifier",
    )
    email: Optional[EmailStr] = Field(
        default=None,
        max_length=255,
        description="Work email address",
    )
    
    # Personal information
    first_name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Employee's first name",
    )
    last_name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Employee's last name",
    )
    middle_name: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Employee's middle name",
    )
    preferred_name: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Preferred name or nickname",
    )
    date_of_birth: Optional[date] = Field(
        default=None,
        description="Date of birth",
    )
    gender: Optional[str] = Field(
        default=None,
        max_length=20,
        description="Gender",
    )
    
    # Contact information
    personal_email: Optional[EmailStr] = Field(
        default=None,
        max_length=255,
        description="Personal email address",
    )
    phone_number: Optional[str] = Field(
        default=None,
        max_length=30,
        description="Work phone number",
    )
    mobile_number: Optional[str] = Field(
        default=None,
        max_length=30,
        description="Mobile phone number",
    )
    address_line1: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Street address line 1",
    )
    address_line2: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Street address line 2",
    )
    city: Optional[str] = Field(
        default=None,
        max_length=100,
        description="City",
    )
    state_province: Optional[str] = Field(
        default=None,
        max_length=100,
        description="State or province",
    )
    postal_code: Optional[str] = Field(
        default=None,
        max_length=20,
        description="Postal/ZIP code",
    )
    country: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Country",
    )
    
    # Employment information
    department_id: Optional[int] = Field(
        default=None,
        description="Department ID",
    )
    manager_id: Optional[int] = Field(
        default=None,
        description="Manager's employee ID",
    )
    location_id: Optional[int] = Field(
        default=None,
        description="Work location ID",
    )
    work_schedule_id: Optional[int] = Field(
        default=None,
        description="Work schedule ID",
    )
    job_title: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Job title",
    )
    employment_type: Optional[EmploymentType] = Field(
        default=None,
        description="Employment type",
    )
    employment_status: Optional[EmployeeStatus] = Field(
        default=None,
        description="Employment status",
    )
    hire_date: Optional[date] = Field(
        default=None,
        description="Date of hire",
    )
    termination_date: Optional[date] = Field(
        default=None,
        description="Date of termination (if applicable)",
    )
    
    # Compensation
    salary: Optional[Decimal] = Field(
        default=None,
        max_digits=12,
        decimal_places=2,
        ge=Decimal("0"),
        description="Annual salary (12 digits, 2 decimal places)",
    )
    hourly_rate: Optional[Decimal] = Field(
        default=None,
        max_digits=8,
        decimal_places=2,
        ge=Decimal("0"),
        description="Hourly rate (8 digits, 2 decimal places)",
    )
    
    @field_validator("phone_number", "mobile_number")
    @classmethod
    def validate_phone_format(cls, v: Optional[str]) -> Optional[str]:
        """Validate phone number format."""
        if v is None:
            return v
        cleaned = re.sub(r"[\s\-\(\)]", "", v)
        if not re.match(r"^\+?[0-9]{7,15}$", cleaned):
            raise ValueError(
                "Invalid phone number format. Use international format (e.g., +1234567890) "
                "or standard format with 7-15 digits."
            )
        return v
    
    @field_validator("hire_date")
    @classmethod
    def validate_hire_date_not_future(cls, v: Optional[date]) -> Optional[date]:
        """Ensure hire date is not in the future."""
        if v is not None and v > date.today():
            raise ValueError("Hire date cannot be in the future")
        return v
    
    @field_validator("salary")
    @classmethod
    def validate_salary_precision(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Validate salary has correct precision."""
        if v is None:
            return v
        if v >= Decimal("10000000000"):
            raise ValueError("Salary must have at most 12 digits total")
        return v
    
    @field_validator("hourly_rate")
    @classmethod
    def validate_hourly_rate_precision(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Validate hourly rate has correct precision."""
        if v is None:
            return v
        if v >= Decimal("1000000"):
            raise ValueError("Hourly rate must have at most 8 digits total")
        return v
    
    @model_validator(mode="after")
    def validate_termination_after_hire(self) -> "EmployeeUpdateRequest":
        """Ensure termination date is after hire date when both provided."""
        if self.termination_date is not None and self.hire_date is not None:
            if self.termination_date <= self.hire_date:
                raise ValueError("Termination date must be after hire date")
        return self

