"""Pydantic models for email API."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, EmailStr


class EmailProviderEnum(str, Enum):
    """Supported email providers."""
    SENDGRID = "sendgrid"
    SES = "ses"
    MOCK = "mock"


class DeliveryStatusEnum(str, Enum):
    """Email delivery status."""
    PENDING = "pending"
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    OPENED = "opened"
    CLICKED = "clicked"
    BOUNCED = "bounced"
    FAILED = "failed"
    DROPPED = "dropped"
    SPAM = "spam"


class QueuePriorityEnum(str, Enum):
    """Queue priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


# Request Models

class EmailAddressRequest(BaseModel):
    """Email address with optional name."""
    email: EmailStr = Field(..., description="Email address")
    name: Optional[str] = Field(default=None, description="Display name")


class AttachmentRequest(BaseModel):
    """Email attachment."""
    filename: str = Field(..., description="Attachment filename")
    content_base64: str = Field(..., description="Base64-encoded content")
    content_type: str = Field(default="application/octet-stream", description="MIME type")
    content_id: Optional[str] = Field(default=None, description="Content ID for inline attachments")
    disposition: str = Field(default="attachment", description="'attachment' or 'inline'")


class SendEmailRequest(BaseModel):
    """Request to send an email."""
    to: List[EmailStr] = Field(..., min_length=1, description="Recipient email addresses")
    subject: str = Field(..., min_length=1, max_length=998, description="Email subject")
    html_content: Optional[str] = Field(default=None, description="HTML body content")
    text_content: Optional[str] = Field(default=None, description="Plain text body content")
    from_email: Optional[EmailStr] = Field(default=None, description="Sender email")
    from_name: Optional[str] = Field(default=None, description="Sender name")
    reply_to: Optional[EmailStr] = Field(default=None, description="Reply-to email")
    cc: Optional[List[EmailStr]] = Field(default=None, description="CC recipients")
    bcc: Optional[List[EmailStr]] = Field(default=None, description="BCC recipients")
    attachments: Optional[List[AttachmentRequest]] = Field(default=None, description="Attachments")
    tags: Optional[List[str]] = Field(default=None, max_length=10, description="Tags for categorization")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")
    use_queue: bool = Field(default=True, description="Whether to use the queue")
    priority: QueuePriorityEnum = Field(default=QueuePriorityEnum.NORMAL, description="Queue priority")
    scheduled_at: Optional[datetime] = Field(default=None, description="Schedule for later sending")

    class Config:
        json_schema_extra = {
            "example": {
                "to": ["recipient@example.com"],
                "subject": "Hello from the API",
                "html_content": "<h1>Hello!</h1><p>This is a test email.</p>",
                "text_content": "Hello! This is a test email.",
                "tags": ["test", "api"],
            }
        }


class SendTemplateEmailRequest(BaseModel):
    """Request to send a templated email."""
    template_id: str = Field(..., description="Template identifier")
    to: List[EmailStr] = Field(..., min_length=1, description="Recipient email addresses")
    context: Dict[str, Any] = Field(default_factory=dict, description="Template context variables")
    from_email: Optional[EmailStr] = Field(default=None, description="Sender email")
    from_name: Optional[str] = Field(default=None, description="Sender name")
    reply_to: Optional[EmailStr] = Field(default=None, description="Reply-to email")
    cc: Optional[List[EmailStr]] = Field(default=None, description="CC recipients")
    bcc: Optional[List[EmailStr]] = Field(default=None, description="BCC recipients")
    attachments: Optional[List[AttachmentRequest]] = Field(default=None, description="Attachments")
    tags: Optional[List[str]] = Field(default=None, description="Tags")
    use_queue: bool = Field(default=True, description="Whether to use the queue")
    priority: QueuePriorityEnum = Field(default=QueuePriorityEnum.NORMAL, description="Queue priority")

    class Config:
        json_schema_extra = {
            "example": {
                "template_id": "welcome",
                "to": ["newuser@example.com"],
                "context": {
                    "user": {"first_name": "John"},
                    "company_name": "Acme Corp",
                    "login_url": "https://example.com/login",
                },
            }
        }


class SendBatchEmailRequest(BaseModel):
    """Request to send batch emails."""
    messages: List[SendEmailRequest] = Field(..., min_length=1, max_length=100, description="List of emails to send")
    use_queue: bool = Field(default=True, description="Whether to use the queue")


class WebhookEventRequest(BaseModel):
    """Webhook event payload."""
    provider: EmailProviderEnum = Field(..., description="Provider that sent the webhook")
    payload: Dict[str, Any] = Field(..., description="Raw webhook payload")
    signature: Optional[str] = Field(default=None, description="Webhook signature")
    timestamp: Optional[str] = Field(default=None, description="Webhook timestamp")


class RenderTemplateRequest(BaseModel):
    """Request to render a template."""
    template_id: str = Field(..., description="Template identifier")
    context: Dict[str, Any] = Field(default_factory=dict, description="Template context variables")


# Response Models

class DeliveryResultResponse(BaseModel):
    """Email delivery result."""
    success: bool = Field(..., description="Whether the operation was successful")
    message_id: Optional[str] = Field(default=None, description="Message ID for tracking")
    status: DeliveryStatusEnum = Field(..., description="Delivery status")
    error_code: Optional[str] = Field(default=None, description="Error code if failed")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Timestamp")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class BatchDeliveryResultResponse(BaseModel):
    """Batch email delivery results."""
    total: int = Field(..., description="Total emails in batch")
    successful: int = Field(..., description="Number of successful sends")
    failed: int = Field(..., description="Number of failed sends")
    results: List[DeliveryResultResponse] = Field(..., description="Individual results")


class DeliveryEventResponse(BaseModel):
    """Delivery event from webhook."""
    message_id: str = Field(..., description="Message ID")
    event_type: DeliveryStatusEnum = Field(..., description="Event type")
    email: str = Field(..., description="Recipient email")
    timestamp: datetime = Field(..., description="Event timestamp")
    provider: EmailProviderEnum = Field(..., description="Provider")
    bounce_type: Optional[str] = Field(default=None, description="Bounce type if bounced")
    reason: Optional[str] = Field(default=None, description="Additional reason/details")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class DeliveryStatusResponse(BaseModel):
    """Delivery status for a message."""
    message_id: str = Field(..., description="Message ID")
    status: DeliveryStatusEnum = Field(..., description="Current status")
    events: List[DeliveryEventResponse] = Field(default_factory=list, description="Delivery events")


class QueueStatusResponse(BaseModel):
    """Queue status for an email."""
    queue_id: str = Field(..., description="Queue ID")
    status: str = Field(..., description="Queue status")
    retry_count: int = Field(default=0, description="Number of retry attempts")
    created_at: datetime = Field(..., description="Created timestamp")
    last_attempt_at: Optional[datetime] = Field(default=None, description="Last attempt timestamp")
    next_retry_at: Optional[datetime] = Field(default=None, description="Next retry timestamp")
    error_message: Optional[str] = Field(default=None, description="Last error message")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class QueueStatsResponse(BaseModel):
    """Queue statistics."""
    pending: int = Field(..., description="Pending emails")
    processing: int = Field(..., description="Currently processing")
    sent: int = Field(..., description="Successfully sent")
    failed: int = Field(..., description="Failed sends")
    retry_scheduled: int = Field(..., description="Scheduled for retry")
    total_completed: int = Field(..., description="Total completed")
    is_running: bool = Field(..., description="Whether queue processor is running")


class TemplateInfo(BaseModel):
    """Email template information."""
    id: str = Field(..., description="Template ID")
    name: str = Field(..., description="Template name")
    description: Optional[str] = Field(default=None, description="Template description")
    category: Optional[str] = Field(default=None, description="Template category")
    variables: List[str] = Field(default_factory=list, description="Required variables")
    is_active: bool = Field(default=True, description="Whether template is active")


class TemplateListResponse(BaseModel):
    """List of templates."""
    templates: List[TemplateInfo] = Field(..., description="Available templates")
    total: int = Field(..., description="Total count")


class RenderTemplateResponse(BaseModel):
    """Rendered template result."""
    subject: str = Field(..., description="Rendered subject")
    html_content: str = Field(..., description="Rendered HTML content")
    text_content: Optional[str] = Field(default=None, description="Rendered text content")


class HealthCheckResponse(BaseModel):
    """Provider health check results."""
    providers: Dict[str, bool] = Field(..., description="Provider health status")
    queue_enabled: bool = Field(..., description="Whether queue is enabled")
    queue_running: bool = Field(default=False, description="Whether queue processor is running")

