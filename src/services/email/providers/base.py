"""Base email provider interface."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class EmailProviderType(str, Enum):
    """Supported email provider types."""
    SENDGRID = "sendgrid"
    SES = "ses"
    SMTP = "smtp"
    MOCK = "mock"


class DeliveryStatus(str, Enum):
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
    UNSUBSCRIBED = "unsubscribed"


class BounceType(str, Enum):
    """Bounce classification."""
    HARD = "hard"  # Permanent failure
    SOFT = "soft"  # Temporary failure
    BLOCK = "block"  # Blocked by receiver
    UNKNOWN = "unknown"


@dataclass
class EmailAddress:
    """Email address with optional name."""
    email: str
    name: Optional[str] = None
    
    def __str__(self) -> str:
        if self.name:
            return f"{self.name} <{self.email}>"
        return self.email


@dataclass
class EmailAttachment:
    """Email attachment."""
    filename: str
    content: bytes
    content_type: str
    content_id: Optional[str] = None  # For inline attachments
    disposition: str = "attachment"  # 'attachment' or 'inline'


@dataclass
class EmailMessage:
    """Email message to be sent."""
    to: List[EmailAddress]
    subject: str
    html_content: Optional[str] = None
    text_content: Optional[str] = None
    from_address: Optional[EmailAddress] = None
    reply_to: Optional[EmailAddress] = None
    cc: List[EmailAddress] = field(default_factory=list)
    bcc: List[EmailAddress] = field(default_factory=list)
    attachments: List[EmailAttachment] = field(default_factory=list)
    headers: Dict[str, str] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tracking_id: Optional[str] = None
    send_at: Optional[datetime] = None  # Scheduled send time
    
    def __post_init__(self):
        # Ensure at least one content type
        if not self.html_content and not self.text_content:
            raise ValueError("Email must have either HTML or text content")


@dataclass
class DeliveryResult:
    """Result of email delivery attempt."""
    success: bool
    message_id: Optional[str] = None
    provider: Optional[EmailProviderType] = None
    status: DeliveryStatus = DeliveryStatus.PENDING
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    provider_response: Optional[Dict[str, Any]] = None
    
    @classmethod
    def success_result(
        cls,
        message_id: str,
        provider: EmailProviderType
    ) -> "DeliveryResult":
        return cls(
            success=True,
            message_id=message_id,
            provider=provider,
            status=DeliveryStatus.SENT,
        )
    
    @classmethod
    def failure_result(
        cls,
        error_message: str,
        provider: Optional[EmailProviderType] = None,
        error_code: Optional[str] = None
    ) -> "DeliveryResult":
        return cls(
            success=False,
            provider=provider,
            status=DeliveryStatus.FAILED,
            error_code=error_code,
            error_message=error_message,
        )


@dataclass
class DeliveryEvent:
    """Webhook event for email delivery status."""
    message_id: str
    event_type: DeliveryStatus
    email: str
    timestamp: datetime
    provider: EmailProviderType
    bounce_type: Optional[BounceType] = None
    reason: Optional[str] = None
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None
    link_url: Optional[str] = None  # For click events
    raw_event: Optional[Dict[str, Any]] = None


class EmailProvider(ABC):
    """
    Abstract base class for email providers.
    
    All email provider implementations must inherit from this class
    and implement the required methods.
    """
    
    provider_type: EmailProviderType
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the email provider.
        
        Args:
            config: Provider-specific configuration
        """
        self.config = config
        self._validate_config()
    
    @abstractmethod
    def _validate_config(self) -> None:
        """Validate provider configuration."""
        pass
    
    @abstractmethod
    async def send(self, message: EmailMessage) -> DeliveryResult:
        """
        Send an email message.
        
        Args:
            message: Email message to send
            
        Returns:
            DeliveryResult with success/failure information
        """
        pass
    
    @abstractmethod
    async def send_batch(self, messages: List[EmailMessage]) -> List[DeliveryResult]:
        """
        Send multiple email messages.
        
        Args:
            messages: List of email messages to send
            
        Returns:
            List of DeliveryResult for each message
        """
        pass
    
    @abstractmethod
    async def get_delivery_status(self, message_id: str) -> Optional[DeliveryStatus]:
        """
        Get the delivery status of a sent email.
        
        Args:
            message_id: Message ID from send result
            
        Returns:
            Current delivery status or None if not found
        """
        pass
    
    @abstractmethod
    def parse_webhook_event(self, payload: Dict[str, Any]) -> Optional[DeliveryEvent]:
        """
        Parse a webhook payload into a DeliveryEvent.
        
        Args:
            payload: Raw webhook payload from provider
            
        Returns:
            Parsed DeliveryEvent or None if invalid
        """
        pass
    
    @abstractmethod
    def verify_webhook_signature(
        self,
        payload: bytes,
        signature: str,
        timestamp: Optional[str] = None
    ) -> bool:
        """
        Verify webhook signature for security.
        
        Args:
            payload: Raw webhook payload
            signature: Signature from webhook header
            timestamp: Timestamp from webhook header (if applicable)
            
        Returns:
            True if signature is valid
        """
        pass
    
    async def health_check(self) -> bool:
        """
        Check if the provider is healthy and accessible.
        
        Returns:
            True if provider is healthy
        """
        return True
    
    def get_rate_limits(self) -> Dict[str, int]:
        """
        Get current rate limits for the provider.
        
        Returns:
            Dictionary with rate limit information
        """
        return {
            "requests_per_second": 10,
            "emails_per_day": 100000,
        }


class MockEmailProvider(EmailProvider):
    """Mock email provider for testing."""
    
    provider_type = EmailProviderType.MOCK
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.sent_messages: List[EmailMessage] = []
        self.delivery_statuses: Dict[str, DeliveryStatus] = {}
    
    def _validate_config(self) -> None:
        pass
    
    async def send(self, message: EmailMessage) -> DeliveryResult:
        import uuid
        message_id = str(uuid.uuid4())
        self.sent_messages.append(message)
        self.delivery_statuses[message_id] = DeliveryStatus.SENT
        
        logger.info(f"Mock email sent: {message.subject} to {[str(a) for a in message.to]}")
        
        return DeliveryResult.success_result(message_id, self.provider_type)
    
    async def send_batch(self, messages: List[EmailMessage]) -> List[DeliveryResult]:
        results = []
        for msg in messages:
            results.append(await self.send(msg))
        return results
    
    async def get_delivery_status(self, message_id: str) -> Optional[DeliveryStatus]:
        return self.delivery_statuses.get(message_id)
    
    def parse_webhook_event(self, payload: Dict[str, Any]) -> Optional[DeliveryEvent]:
        return None
    
    def verify_webhook_signature(
        self,
        payload: bytes,
        signature: str,
        timestamp: Optional[str] = None
    ) -> bool:
        return True

