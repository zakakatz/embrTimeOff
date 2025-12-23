"""Pydantic models for time-off request API operations.

Provides structured request and response models with comprehensive
validation for client-server communication in time-off workflows.
"""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


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


# =============================================================================
# Nested Response Models (for serialization)
# =============================================================================

class EmployeeBasicResponse(BaseModel):
    """
    Basic employee information for nested responses.
    
    Contains minimal employee data needed for display
    in time-off related contexts.
    """
    
    id: UUID = Field(
        ...,
        description="Unique identifier of the employee",
    )
    employee_id: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Employee ID code",
    )
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
    email: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Employee's email address",
    )
    job_title: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Employee's job title",
    )
    department_name: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Name of employee's department",
    )
    
    @property
    def full_name(self) -> str:
        """Return full name of employee."""
        return f"{self.first_name} {self.last_name}"
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "employee_id": "EMP001",
                "first_name": "John",
                "last_name": "Doe",
                "email": "john.doe@company.com",
                "job_title": "Software Engineer",
                "department_name": "Engineering",
            }
        }


class TimeOffPolicyResponse(BaseModel):
    """
    Time-off policy information for nested responses.
    
    Contains policy details relevant to time-off requests
    including accrual and request limits.
    """
    
    id: UUID = Field(
        ...,
        description="Unique identifier of the policy",
    )
    code: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Policy code identifier",
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Display name of the policy",
    )
    description: Optional[str] = Field(
        default=None,
        description="Policy description",
    )
    request_type: RequestType = Field(
        ...,
        description="Type of request this policy applies to",
    )
    accrual_rate: Decimal = Field(
        default=Decimal("0"),
        description="Accrual rate per period",
    )
    accrual_period: str = Field(
        default="monthly",
        description="Accrual period (e.g., monthly, yearly)",
    )
    max_balance: Optional[Decimal] = Field(
        default=None,
        description="Maximum balance that can be accrued",
    )
    min_request_days: Decimal = Field(
        default=Decimal("0.5"),
        description="Minimum days that can be requested",
    )
    max_request_days: Optional[Decimal] = Field(
        default=None,
        description="Maximum days that can be requested at once",
    )
    advance_notice_days: int = Field(
        default=0,
        ge=0,
        description="Required advance notice in days",
    )
    requires_approval: bool = Field(
        default=True,
        description="Whether requests require approval",
    )
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "660e8400-e29b-41d4-a716-446655440001",
                "code": "VAC-2024",
                "name": "Annual Vacation",
                "description": "Standard annual vacation policy",
                "request_type": "vacation",
                "accrual_rate": 1.67,
                "accrual_period": "monthly",
                "max_balance": 40.0,
                "min_request_days": 0.5,
                "max_request_days": 10.0,
                "advance_notice_days": 14,
                "requires_approval": True,
            }
        }


class RequestApprovalResponse(BaseModel):
    """
    Response model for approval actions on time-off requests.
    
    Contains the approver information, approval status,
    and relevant timestamps for tracking approval workflow.
    """
    
    id: UUID = Field(
        ...,
        description="Unique identifier of the approval record",
    )
    approver: EmployeeBasicResponse = Field(
        ...,
        description="Employee who is/was the approver",
    )
    approval_level: int = Field(
        ...,
        ge=1,
        description="Level of approval (1 = first level, etc.)",
    )
    status: ApprovalStatus = Field(
        ...,
        description="Current status of this approval",
    )
    comments: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Comments from the approver",
    )
    approved_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp when approved",
    )
    denied_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp when denied",
    )
    created_at: datetime = Field(
        ...,
        description="Timestamp when approval record was created",
    )
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "770e8400-e29b-41d4-a716-446655440002",
                "approver": {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "employee_id": "MGR001",
                    "first_name": "Jane",
                    "last_name": "Manager",
                    "email": "jane.manager@company.com",
                    "job_title": "Engineering Manager",
                    "department_name": "Engineering",
                },
                "approval_level": 1,
                "status": "approved",
                "comments": "Approved. Enjoy your time off!",
                "approved_at": "2024-03-10T14:30:00Z",
                "denied_at": None,
                "created_at": "2024-03-05T09:00:00Z",
            }
        }


# =============================================================================
# Request Models
# =============================================================================

class TimeOffRequestCreate(BaseModel):
    """
    Request model for creating a new time-off request.
    
    Contains all required and optional fields with
    comprehensive validation for data integrity.
    """
    
    policy_id: Optional[UUID] = Field(
        default=None,
        description="ID of the time-off policy (optional if request_type provided)",
    )
    request_type: RequestType = Field(
        ...,
        description="Type of time-off request",
    )
    start_date: date = Field(
        ...,
        description="Start date of the time-off period",
    )
    end_date: date = Field(
        ...,
        description="End date of the time-off period",
    )
    hours_requested: Decimal = Field(
        default=Decimal("8.00"),
        ge=Decimal("0.5"),
        le=Decimal("9999.99"),
        max_digits=6,
        decimal_places=2,
        description="Total hours requested (for partial day or multi-day requests)",
    )
    employee_comments: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Comments from the requesting employee",
    )
    
    @field_validator("request_type", mode="before")
    @classmethod
    def validate_request_type(cls, v: Any) -> RequestType:
        """Ensure request_type is a valid enum value."""
        if isinstance(v, str):
            try:
                return RequestType(v.lower())
            except ValueError:
                raise ValueError(
                    f"Invalid request_type: {v}. Must be one of: "
                    f"{[e.value for e in RequestType]}"
                )
        return v
    
    @field_validator("hours_requested", mode="before")
    @classmethod
    def validate_hours_requested(cls, v: Any) -> Decimal:
        """Convert and validate hours_requested."""
        if isinstance(v, (int, float)):
            v = Decimal(str(v))
        if isinstance(v, str):
            try:
                v = Decimal(v)
            except Exception:
                raise ValueError("hours_requested must be a valid decimal number")
        return v
    
    @model_validator(mode="after")
    def validate_dates(self) -> "TimeOffRequestCreate":
        """Ensure end_date is not before start_date."""
        if self.end_date < self.start_date:
            raise ValueError("end_date cannot be before start_date")
        return self
    
    class Config:
        json_schema_extra = {
            "example": {
                "policy_id": "660e8400-e29b-41d4-a716-446655440001",
                "request_type": "vacation",
                "start_date": "2024-03-15",
                "end_date": "2024-03-22",
                "hours_requested": 56.00,
                "employee_comments": "Annual family vacation",
            }
        }


class TimeOffRequestUpdate(BaseModel):
    """
    Request model for updating an existing time-off request.
    
    Supports partial updates to modifiable fields only.
    """
    
    start_date: Optional[date] = Field(
        default=None,
        description="Updated start date",
    )
    end_date: Optional[date] = Field(
        default=None,
        description="Updated end date",
    )
    hours_requested: Optional[Decimal] = Field(
        default=None,
        ge=Decimal("0.5"),
        le=Decimal("9999.99"),
        max_digits=6,
        decimal_places=2,
        description="Updated hours requested",
    )
    employee_comments: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Updated comments from employee",
    )
    
    @field_validator("hours_requested", mode="before")
    @classmethod
    def validate_hours_requested(cls, v: Any) -> Optional[Decimal]:
        """Convert and validate hours_requested if provided."""
        if v is None:
            return None
        if isinstance(v, (int, float)):
            v = Decimal(str(v))
        if isinstance(v, str):
            try:
                v = Decimal(v)
            except Exception:
                raise ValueError("hours_requested must be a valid decimal number")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "start_date": "2024-03-18",
                "end_date": "2024-03-22",
                "hours_requested": 40.00,
                "employee_comments": "Shortened to avoid conflict with project deadline",
            }
        }


# =============================================================================
# Response Models
# =============================================================================

class TimeOffRequestResponse(BaseModel):
    """
    Complete response model for a time-off request.
    
    Contains all request details including nested objects
    for employee, policy, and approval information.
    """
    
    id: UUID = Field(
        ...,
        description="Unique identifier of the request",
    )
    employee: EmployeeBasicResponse = Field(
        ...,
        description="Employee who submitted the request",
    )
    policy: Optional[TimeOffPolicyResponse] = Field(
        default=None,
        description="Associated time-off policy (if any)",
    )
    request_type: RequestType = Field(
        ...,
        description="Type of time-off request",
    )
    start_date: date = Field(
        ...,
        description="Start date of the time-off period",
    )
    end_date: date = Field(
        ...,
        description="End date of the time-off period",
    )
    hours_requested: Decimal = Field(
        ...,
        description="Total hours requested",
    )
    status: RequestStatus = Field(
        ...,
        description="Current status of the request",
    )
    employee_comments: Optional[str] = Field(
        default=None,
        description="Comments from the requesting employee",
    )
    manager_comments: Optional[str] = Field(
        default=None,
        description="Comments from the manager/approver",
    )
    approvals: List[RequestApprovalResponse] = Field(
        default_factory=list,
        description="List of approval records for this request",
    )
    submitted_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp when request was submitted",
    )
    approved_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp when request was fully approved",
    )
    denied_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp when request was denied",
    )
    created_at: datetime = Field(
        ...,
        description="Timestamp when request was created",
    )
    updated_at: datetime = Field(
        ...,
        description="Timestamp when request was last updated",
    )
    
    @property
    def duration_days(self) -> int:
        """Calculate the number of days in the request."""
        return (self.end_date - self.start_date).days + 1
    
    @property
    def is_pending(self) -> bool:
        """Check if request is still pending."""
        return self.status == RequestStatus.PENDING
    
    @property
    def is_finalized(self) -> bool:
        """Check if request has reached a final state."""
        return self.status in (
            RequestStatus.APPROVED,
            RequestStatus.DENIED,
            RequestStatus.CANCELLED,
            RequestStatus.WITHDRAWN,
        )
    
    @property
    def pending_approval_count(self) -> int:
        """Count of pending approvals."""
        return sum(
            1 for a in self.approvals
            if a.status == ApprovalStatus.PENDING
        )
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "880e8400-e29b-41d4-a716-446655440003",
                "employee": {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "employee_id": "EMP001",
                    "first_name": "John",
                    "last_name": "Doe",
                    "email": "john.doe@company.com",
                    "job_title": "Software Engineer",
                    "department_name": "Engineering",
                },
                "policy": {
                    "id": "660e8400-e29b-41d4-a716-446655440001",
                    "code": "VAC-2024",
                    "name": "Annual Vacation",
                    "description": "Standard annual vacation policy",
                    "request_type": "vacation",
                    "accrual_rate": 1.67,
                    "accrual_period": "monthly",
                    "max_balance": 40.0,
                    "min_request_days": 0.5,
                    "max_request_days": 10.0,
                    "advance_notice_days": 14,
                    "requires_approval": True,
                },
                "request_type": "vacation",
                "start_date": "2024-03-15",
                "end_date": "2024-03-22",
                "hours_requested": 56.00,
                "status": "approved",
                "employee_comments": "Annual family vacation",
                "manager_comments": "Approved. Enjoy!",
                "approvals": [
                    {
                        "id": "770e8400-e29b-41d4-a716-446655440002",
                        "approver": {
                            "id": "550e8400-e29b-41d4-a716-446655440000",
                            "employee_id": "MGR001",
                            "first_name": "Jane",
                            "last_name": "Manager",
                            "email": "jane.manager@company.com",
                            "job_title": "Engineering Manager",
                            "department_name": "Engineering",
                        },
                        "approval_level": 1,
                        "status": "approved",
                        "comments": "Approved",
                        "approved_at": "2024-03-10T14:30:00Z",
                        "denied_at": None,
                        "created_at": "2024-03-05T09:00:00Z",
                    }
                ],
                "submitted_at": "2024-03-05T09:00:00Z",
                "approved_at": "2024-03-10T14:30:00Z",
                "denied_at": None,
                "created_at": "2024-03-05T09:00:00Z",
                "updated_at": "2024-03-10T14:30:00Z",
            }
        }


class TimeOffRequestListResponse(BaseModel):
    """
    Response model for listing time-off requests.
    
    Contains a paginated list of requests with metadata.
    """
    
    items: List[TimeOffRequestResponse] = Field(
        default_factory=list,
        description="List of time-off requests",
    )
    total: int = Field(
        ...,
        ge=0,
        description="Total number of requests matching the query",
    )
    page: int = Field(
        default=1,
        ge=1,
        description="Current page number",
    )
    page_size: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Number of items per page",
    )
    total_pages: int = Field(
        ...,
        ge=0,
        description="Total number of pages",
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "items": [],
                "total": 100,
                "page": 1,
                "page_size": 20,
                "total_pages": 5,
            }
        }


class TimeOffBalanceResponse(BaseModel):
    """
    Response model for employee time-off balance.
    
    Shows current balance, used amount, and available amount
    for a specific policy type.
    """
    
    policy_id: UUID = Field(
        ...,
        description="ID of the time-off policy",
    )
    policy_name: str = Field(
        ...,
        description="Name of the time-off policy",
    )
    request_type: RequestType = Field(
        ...,
        description="Type of time-off",
    )
    total_allocated: Decimal = Field(
        ...,
        ge=Decimal("0"),
        description="Total hours allocated for the period",
    )
    total_used: Decimal = Field(
        default=Decimal("0"),
        ge=Decimal("0"),
        description="Total hours already used",
    )
    total_pending: Decimal = Field(
        default=Decimal("0"),
        ge=Decimal("0"),
        description="Total hours in pending requests",
    )
    available_balance: Decimal = Field(
        ...,
        description="Available balance (allocated - used - pending)",
    )
    as_of_date: date = Field(
        ...,
        description="Date this balance was calculated",
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "policy_id": "660e8400-e29b-41d4-a716-446655440001",
                "policy_name": "Annual Vacation",
                "request_type": "vacation",
                "total_allocated": 160.00,
                "total_used": 48.00,
                "total_pending": 16.00,
                "available_balance": 96.00,
                "as_of_date": "2024-03-15",
            }
        }

