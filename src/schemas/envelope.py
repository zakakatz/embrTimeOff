"""Pydantic schemas for e-signature envelope management API."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, validator


# =============================================================================
# Enums
# =============================================================================

class EnvelopeStatusEnum(str, Enum):
    """Status of an e-signature envelope."""
    DRAFT = "draft"
    SENT = "sent"
    DELIVERED = "delivered"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DECLINED = "declined"
    VOIDED = "voided"
    EXPIRED = "expired"


class RecipientStatusEnum(str, Enum):
    """Status of an individual recipient."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    VIEWED = "viewed"
    SIGNED = "signed"
    DECLINED = "declined"
    EXPIRED = "expired"


class RecipientTypeEnum(str, Enum):
    """Type of recipient in the signing workflow."""
    SIGNER = "signer"
    CARBON_COPY = "carbon_copy"
    CERTIFIED_DELIVERY = "certified_delivery"
    IN_PERSON_SIGNER = "in_person_signer"
    APPROVER = "approver"
    EDITOR = "editor"


class FieldTypeEnum(str, Enum):
    """Types of fields that can be placed on documents."""
    SIGNATURE = "signature"
    INITIAL = "initial"
    DATE_SIGNED = "date_signed"
    TEXT = "text"
    CHECKBOX = "checkbox"
    DROPDOWN = "dropdown"
    RADIO = "radio"
    ATTACHMENT = "attachment"
    COMPANY = "company"
    TITLE = "title"
    FULL_NAME = "full_name"
    EMAIL = "email"


# =============================================================================
# Field Schemas
# =============================================================================

class FieldPosition(BaseModel):
    """Position of a field on a document."""
    document_index: int = Field(default=0, ge=0, description="Index of the document (0-based)")
    page_number: int = Field(default=1, ge=1, description="Page number (1-based)")
    x_position: float = Field(..., ge=0, description="X position in points from left")
    y_position: float = Field(..., ge=0, description="Y position in points from top")
    width: float = Field(default=200, gt=0, description="Field width in points")
    height: float = Field(default=50, gt=0, description="Field height in points")


class FieldDefinition(BaseModel):
    """Definition of a field to place on a document."""
    field_type: FieldTypeEnum = Field(..., description="Type of field")
    field_name: str = Field(..., min_length=1, max_length=100, description="Unique field name")
    recipient_index: int = Field(
        ...,
        ge=0,
        description="Index of the recipient this field belongs to (0-based)"
    )
    position: FieldPosition = Field(..., description="Field position on document")
    required: bool = Field(default=True, description="Whether field is required")
    default_value: Optional[str] = Field(default=None, description="Default value")
    validation_pattern: Optional[str] = Field(
        default=None,
        description="Regex pattern for text validation"
    )
    validation_message: Optional[str] = Field(
        default=None,
        description="Error message for validation failure"
    )
    options: Optional[List[str]] = Field(
        default=None,
        description="Options for dropdown/radio fields"
    )


class FieldResponse(BaseModel):
    """Field in an envelope response."""
    id: int = Field(..., description="Field ID")
    field_type: FieldTypeEnum = Field(..., description="Type of field")
    field_name: str = Field(..., description="Field name")
    recipient_id: int = Field(..., description="Recipient ID this field belongs to")
    position: FieldPosition = Field(..., description="Field position")
    required: bool = Field(..., description="Whether field is required")
    value: Optional[str] = Field(default=None, description="Current value")
    completed: bool = Field(default=False, description="Whether field is completed")
    completed_at: Optional[datetime] = Field(default=None, description="When field was completed")


# =============================================================================
# Recipient Schemas
# =============================================================================

class RecipientDefinition(BaseModel):
    """Definition of a recipient in an envelope."""
    email: str = Field(..., description="Recipient email address")
    name: str = Field(..., min_length=1, max_length=255, description="Recipient name")
    recipient_type: RecipientTypeEnum = Field(
        default=RecipientTypeEnum.SIGNER,
        description="Type of recipient"
    )
    role_name: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Logical role name (e.g., 'Employee', 'Manager')"
    )
    routing_order: int = Field(
        default=1,
        ge=1,
        description="Order in signing sequence"
    )
    employee_id: Optional[int] = Field(
        default=None,
        description="Employee ID if recipient is an internal employee"
    )

    @validator("email")
    def validate_email(cls, v: str) -> str:
        """Validate email format."""
        if "@" not in v or "." not in v:
            raise ValueError("Invalid email format")
        return v.lower()


class RecipientResponse(BaseModel):
    """Recipient in an envelope response."""
    id: int = Field(..., description="Recipient ID")
    email: str = Field(..., description="Recipient email")
    name: str = Field(..., description="Recipient name")
    recipient_type: RecipientTypeEnum = Field(..., description="Type of recipient")
    role_name: Optional[str] = Field(default=None, description="Role name")
    routing_order: int = Field(..., description="Order in signing sequence")
    status: RecipientStatusEnum = Field(..., description="Current status")
    employee_id: Optional[int] = Field(default=None, description="Employee ID if internal")
    
    # Timestamps
    sent_at: Optional[datetime] = Field(default=None, description="When notification was sent")
    delivered_at: Optional[datetime] = Field(default=None, description="When email was delivered")
    viewed_at: Optional[datetime] = Field(default=None, description="When envelope was first viewed")
    signed_at: Optional[datetime] = Field(default=None, description="When signing was completed")
    declined_at: Optional[datetime] = Field(default=None, description="When envelope was declined")
    
    # Decline info
    decline_reason: Optional[str] = Field(default=None, description="Reason for declining")


class RecipientProgress(BaseModel):
    """Progress information for a recipient."""
    recipient_id: int = Field(..., description="Recipient ID")
    name: str = Field(..., description="Recipient name")
    email: str = Field(..., description="Recipient email")
    status: RecipientStatusEnum = Field(..., description="Current status")
    status_description: str = Field(..., description="Human-readable status")
    routing_order: int = Field(..., description="Order in sequence")
    is_current: bool = Field(
        default=False,
        description="Whether this recipient is currently active in workflow"
    )
    fields_total: int = Field(default=0, description="Total fields assigned")
    fields_completed: int = Field(default=0, description="Completed fields")
    completion_percentage: float = Field(default=0, description="Field completion percentage")


# =============================================================================
# Envelope Request Schemas
# =============================================================================

class CreateEnvelopeRequest(BaseModel):
    """Request to create a new envelope."""
    subject: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Email subject line"
    )
    message: Optional[str] = Field(
        default=None,
        max_length=5000,
        description="Email message body"
    )
    recipients: List[RecipientDefinition] = Field(
        ...,
        min_items=1,
        max_items=50,
        description="List of recipients"
    )
    fields: Optional[List[FieldDefinition]] = Field(
        default=None,
        description="Field definitions for the documents"
    )
    document_ids: Optional[List[str]] = Field(
        default=None,
        description="Storage IDs of documents to include"
    )
    
    # Related Entity
    related_entity_type: Optional[str] = Field(
        default=None,
        description="Type of related HR entity"
    )
    related_entity_id: Optional[int] = Field(
        default=None,
        description="ID of related entity"
    )
    
    # Workflow Configuration
    routing_order_enabled: bool = Field(
        default=True,
        description="Whether recipients sign in order"
    )
    
    # Reminders and Expiration
    reminder_enabled: bool = Field(default=True, description="Enable reminders")
    reminder_delay_days: int = Field(
        default=3,
        ge=1,
        le=30,
        description="Days before first reminder"
    )
    reminder_frequency_days: int = Field(
        default=3,
        ge=1,
        le=30,
        description="Days between reminders"
    )
    expires_in_days: Optional[int] = Field(
        default=30,
        ge=1,
        le=365,
        description="Days until envelope expires"
    )
    
    # Auto-send
    send_immediately: bool = Field(
        default=False,
        description="Send immediately after creation"
    )

    @validator("recipients")
    def validate_recipients(cls, v: List[RecipientDefinition]) -> List[RecipientDefinition]:
        """Validate recipient list."""
        # Check for at least one signer
        signers = [r for r in v if r.recipient_type == RecipientTypeEnum.SIGNER]
        if not signers:
            raise ValueError("At least one signer is required")
        
        # Check for unique emails
        emails = [r.email for r in v]
        if len(emails) != len(set(emails)):
            raise ValueError("Duplicate recipient emails are not allowed")
        
        return v

    @validator("fields")
    def validate_fields(cls, v, values) -> Optional[List[FieldDefinition]]:
        """Validate field definitions."""
        if not v:
            return v
        
        recipients = values.get("recipients", [])
        max_recipient_index = len(recipients) - 1
        
        # Check field names are unique
        names = [f.field_name for f in v]
        if len(names) != len(set(names)):
            raise ValueError("Field names must be unique")
        
        # Check recipient indices are valid
        for field in v:
            if field.recipient_index > max_recipient_index:
                raise ValueError(
                    f"Field '{field.field_name}' references invalid recipient index {field.recipient_index}"
                )
        
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "subject": "Time-Off Request Approval",
                "message": "Please review and sign the attached time-off request.",
                "recipients": [
                    {
                        "email": "manager@company.com",
                        "name": "John Manager",
                        "recipient_type": "signer",
                        "role_name": "Manager",
                        "routing_order": 1,
                    },
                    {
                        "email": "hr@company.com",
                        "name": "HR Department",
                        "recipient_type": "carbon_copy",
                        "routing_order": 2,
                    },
                ],
                "routing_order_enabled": True,
                "send_immediately": True,
            }
        }


class UpdateEnvelopeStatusRequest(BaseModel):
    """Request to update envelope status."""
    status: EnvelopeStatusEnum = Field(..., description="New status")
    reason: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Reason for status change (required for void)"
    )

    @validator("reason")
    def validate_reason(cls, v, values) -> Optional[str]:
        """Require reason for void status."""
        status = values.get("status")
        if status == EnvelopeStatusEnum.VOIDED and not v:
            raise ValueError("Reason is required when voiding an envelope")
        return v


# =============================================================================
# Envelope Response Schemas
# =============================================================================

class WorkflowStatus(BaseModel):
    """Current workflow status of an envelope."""
    current_routing_order: int = Field(
        ...,
        description="Current position in routing sequence"
    )
    total_routing_orders: int = Field(
        ...,
        description="Total positions in routing sequence"
    )
    waiting_for: List[str] = Field(
        default_factory=list,
        description="Names of recipients currently being waited on"
    )
    next_recipients: List[str] = Field(
        default_factory=list,
        description="Names of recipients next in sequence"
    )
    is_sequential: bool = Field(..., description="Whether routing is sequential")
    can_progress: bool = Field(
        default=True,
        description="Whether workflow can progress"
    )
    blocking_reason: Optional[str] = Field(
        default=None,
        description="Reason if workflow is blocked"
    )


class AuditTrailEntry(BaseModel):
    """Audit trail entry for an envelope."""
    id: int = Field(..., description="Entry ID")
    action: str = Field(..., description="Action performed")
    action_description: str = Field(..., description="Human-readable description")
    actor_name: str = Field(..., description="Name of actor")
    actor_email: str = Field(..., description="Email of actor")
    actor_role: Optional[str] = Field(default=None, description="Role of actor")
    ip_address: Optional[str] = Field(default=None, description="IP address")
    created_at: datetime = Field(..., description="Timestamp")


class EnvelopeResponse(BaseModel):
    """Complete envelope response."""
    id: int = Field(..., description="Envelope ID")
    external_id: str = Field(..., description="External reference ID")
    subject: str = Field(..., description="Subject line")
    message: Optional[str] = Field(default=None, description="Message body")
    status: EnvelopeStatusEnum = Field(..., description="Current status")
    status_description: str = Field(..., description="Human-readable status")
    
    # Sender
    sender_email: str = Field(..., description="Sender email")
    sender_name: str = Field(..., description="Sender name")
    sender_employee_id: Optional[int] = Field(default=None, description="Sender employee ID")
    
    # Related Entity
    related_entity_type: Optional[str] = Field(default=None, description="Related entity type")
    related_entity_id: Optional[int] = Field(default=None, description="Related entity ID")
    
    # Recipients
    recipients: List[RecipientResponse] = Field(
        default_factory=list,
        description="List of recipients"
    )
    
    # Fields
    fields: Optional[List[FieldResponse]] = Field(
        default=None,
        description="Field definitions"
    )
    
    # Documents
    document_ids: Optional[List[str]] = Field(default=None, description="Document storage IDs")
    
    # Workflow
    routing_order_enabled: bool = Field(..., description="Sequential routing enabled")
    workflow_status: WorkflowStatus = Field(..., description="Current workflow status")
    
    # Completion
    completed_count: int = Field(..., description="Recipients who completed")
    total_recipients: int = Field(..., description="Total recipients")
    completion_percentage: float = Field(..., description="Overall completion percentage")
    
    # Timestamps
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(default=None, description="Last update")
    sent_at: Optional[datetime] = Field(default=None, description="When sent")
    completed_at: Optional[datetime] = Field(default=None, description="When completed")
    expiration_date: Optional[datetime] = Field(default=None, description="Expiration date")
    voided_at: Optional[datetime] = Field(default=None, description="When voided")
    
    # Void info
    void_reason: Optional[str] = Field(default=None, description="Reason for voiding")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class EnvelopeCreateResponse(BaseModel):
    """Response for envelope creation."""
    envelope_id: int = Field(..., description="Created envelope ID")
    external_id: str = Field(..., description="External reference ID")
    status: EnvelopeStatusEnum = Field(..., description="Initial status")
    recipients_count: int = Field(..., description="Number of recipients")
    message: str = Field(..., description="Success message")
    
    # If sent immediately
    sent: bool = Field(default=False, description="Whether envelope was sent")
    sent_at: Optional[datetime] = Field(default=None, description="When sent")


class EnvelopeStatusUpdateResponse(BaseModel):
    """Response for status update."""
    envelope_id: int = Field(..., description="Envelope ID")
    previous_status: EnvelopeStatusEnum = Field(..., description="Previous status")
    new_status: EnvelopeStatusEnum = Field(..., description="New status")
    status_description: str = Field(..., description="Human-readable status")
    notifications_sent: int = Field(
        default=0,
        description="Number of notifications triggered"
    )
    audit_entry_id: int = Field(..., description="Audit trail entry ID")
    message: str = Field(..., description="Success message")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class EnvelopeListResponse(BaseModel):
    """Response for envelope list."""
    envelopes: List[EnvelopeResponse] = Field(..., description="List of envelopes")
    total: int = Field(..., description="Total count")
    page: int = Field(default=1, description="Current page")
    page_size: int = Field(default=20, description="Page size")


# =============================================================================
# Validation Error Schemas
# =============================================================================

class EnvelopeValidationError(BaseModel):
    """Validation error for envelope operations."""
    field: str = Field(..., description="Field with error")
    message: str = Field(..., description="Error message")
    code: str = Field(..., description="Error code")


class EnvelopeValidationErrorResponse(BaseModel):
    """Response for validation errors."""
    message: str = Field(default="Validation failed", description="Error summary")
    errors: List[EnvelopeValidationError] = Field(
        default_factory=list,
        description="List of validation errors"
    )

