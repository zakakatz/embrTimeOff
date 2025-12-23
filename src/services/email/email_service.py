"""Main email service with provider management and delivery tracking."""

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Type

from src.services.email.providers.base import (
    EmailProvider,
    EmailProviderType,
    EmailMessage,
    EmailAddress,
    EmailAttachment,
    DeliveryResult,
    DeliveryStatus,
    DeliveryEvent,
    MockEmailProvider,
)
from src.services.email.providers.sendgrid import SendGridProvider
from src.services.email.providers.ses import SESProvider
from src.services.email.template_service import EmailTemplateService
from src.services.email.queue_manager import (
    EmailQueueManager,
    QueueConfig,
    QueuePriority,
    QueuedEmail,
)

logger = logging.getLogger(__name__)


@dataclass
class EmailServiceConfig:
    """Configuration for the email service."""
    primary_provider: EmailProviderType = EmailProviderType.MOCK
    fallback_provider: Optional[EmailProviderType] = None
    default_from_email: str = ""
    default_from_name: str = ""
    enable_tracking: bool = True
    enable_queue: bool = True
    queue_config: Optional[QueueConfig] = None
    provider_configs: Dict[EmailProviderType, Dict[str, Any]] = None
    
    @classmethod
    def from_env(cls) -> "EmailServiceConfig":
        """Create configuration from environment variables."""
        primary = os.getenv("EMAIL_PROVIDER", "mock").lower()
        fallback = os.getenv("EMAIL_FALLBACK_PROVIDER", "").lower()
        
        provider_map = {
            "sendgrid": EmailProviderType.SENDGRID,
            "ses": EmailProviderType.SES,
            "mock": EmailProviderType.MOCK,
        }
        
        return cls(
            primary_provider=provider_map.get(primary, EmailProviderType.MOCK),
            fallback_provider=provider_map.get(fallback) if fallback else None,
            default_from_email=os.getenv("EMAIL_FROM_ADDRESS", ""),
            default_from_name=os.getenv("EMAIL_FROM_NAME", ""),
            enable_tracking=os.getenv("EMAIL_TRACKING_ENABLED", "true").lower() == "true",
            enable_queue=os.getenv("EMAIL_QUEUE_ENABLED", "true").lower() == "true",
        )


class EmailService:
    """
    Main email service for sending transactional and notification emails.
    
    Features:
    - Multiple provider support with failover
    - Template-based email composition
    - Queue management for high-volume sending
    - Delivery status tracking
    - Webhook handling for delivery events
    """
    
    # Provider class registry
    PROVIDER_CLASSES: Dict[EmailProviderType, Type[EmailProvider]] = {
        EmailProviderType.SENDGRID: SendGridProvider,
        EmailProviderType.SES: SESProvider,
        EmailProviderType.MOCK: MockEmailProvider,
    }
    
    def __init__(self, config: Optional[EmailServiceConfig] = None):
        """
        Initialize the email service.
        
        Args:
            config: Service configuration
        """
        self.config = config or EmailServiceConfig.from_env()
        
        # Initialize providers
        self._providers: Dict[EmailProviderType, EmailProvider] = {}
        self._init_providers()
        
        # Initialize template service
        self.template_service = EmailTemplateService()
        
        # Initialize queue manager
        self._queue_manager: Optional[EmailQueueManager] = None
        if self.config.enable_queue:
            self._init_queue()
        
        # Delivery status storage (in production, use database)
        self._delivery_statuses: Dict[str, DeliveryStatus] = {}
        self._delivery_events: Dict[str, List[DeliveryEvent]] = {}
    
    def _init_providers(self) -> None:
        """Initialize email providers."""
        # Initialize primary provider
        primary_class = self.PROVIDER_CLASSES.get(self.config.primary_provider)
        if primary_class:
            provider_config = (self.config.provider_configs or {}).get(
                self.config.primary_provider, {}
            )
            try:
                self._providers[self.config.primary_provider] = primary_class(provider_config)
                logger.info(f"Initialized primary email provider: {self.config.primary_provider}")
            except Exception as e:
                logger.error(f"Failed to initialize primary provider: {e}")
        
        # Initialize fallback provider
        if self.config.fallback_provider:
            fallback_class = self.PROVIDER_CLASSES.get(self.config.fallback_provider)
            if fallback_class:
                provider_config = (self.config.provider_configs or {}).get(
                    self.config.fallback_provider, {}
                )
                try:
                    self._providers[self.config.fallback_provider] = fallback_class(provider_config)
                    logger.info(f"Initialized fallback email provider: {self.config.fallback_provider}")
                except Exception as e:
                    logger.error(f"Failed to initialize fallback provider: {e}")
        
        # Always have mock provider available
        if EmailProviderType.MOCK not in self._providers:
            self._providers[EmailProviderType.MOCK] = MockEmailProvider()
    
    def _init_queue(self) -> None:
        """Initialize the email queue manager."""
        primary_provider = self._providers.get(self.config.primary_provider)
        if not primary_provider:
            primary_provider = self._providers.get(EmailProviderType.MOCK)
        
        self._queue_manager = EmailQueueManager(
            provider=primary_provider,
            config=self.config.queue_config,
        )
        
        # Register callbacks
        self._queue_manager.on_sent(self._on_email_sent)
        self._queue_manager.on_failed(self._on_email_failed)
    
    def _on_email_sent(self, queued_email: QueuedEmail) -> None:
        """Callback for successful email sends."""
        if queued_email.delivery_result and queued_email.delivery_result.message_id:
            self._delivery_statuses[queued_email.delivery_result.message_id] = DeliveryStatus.SENT
    
    def _on_email_failed(self, queued_email: QueuedEmail) -> None:
        """Callback for failed email sends."""
        logger.error(f"Email failed: {queued_email.id} - {queued_email.error_message}")
    
    async def send(
        self,
        to: List[str],
        subject: str,
        html_content: Optional[str] = None,
        text_content: Optional[str] = None,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
        reply_to: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        use_queue: bool = True,
        priority: QueuePriority = QueuePriority.NORMAL,
        scheduled_at: Optional[datetime] = None,
    ) -> DeliveryResult:
        """
        Send an email.
        
        Args:
            to: List of recipient email addresses
            subject: Email subject
            html_content: HTML body content
            text_content: Plain text body content
            from_email: Sender email (uses default if not provided)
            from_name: Sender name
            reply_to: Reply-to email address
            cc: CC recipients
            bcc: BCC recipients
            attachments: List of attachment dicts with filename, content, content_type
            tags: Tags for categorization
            metadata: Additional metadata
            use_queue: Whether to use the queue (default True)
            priority: Queue priority
            scheduled_at: Schedule for later sending
            
        Returns:
            DeliveryResult with status
        """
        # Build message
        message = self._build_message(
            to=to,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
            from_email=from_email,
            from_name=from_name,
            reply_to=reply_to,
            cc=cc,
            bcc=bcc,
            attachments=attachments,
            tags=tags,
            metadata=metadata,
        )
        
        # Use queue or send directly
        if use_queue and self._queue_manager and self.config.enable_queue:
            queue_id = self._queue_manager.enqueue(
                message=message,
                priority=priority,
                scheduled_at=scheduled_at,
                metadata=metadata,
            )
            return DeliveryResult(
                success=True,
                message_id=queue_id,
                status=DeliveryStatus.QUEUED,
            )
        
        return await self._send_direct(message)
    
    async def send_template(
        self,
        template_id: str,
        to: List[str],
        context: Dict[str, Any],
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
        reply_to: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        tags: Optional[List[str]] = None,
        use_queue: bool = True,
        priority: QueuePriority = QueuePriority.NORMAL,
    ) -> DeliveryResult:
        """
        Send an email using a template.
        
        Args:
            template_id: Template identifier
            to: List of recipient email addresses
            context: Template context variables
            from_email: Sender email (uses default if not provided)
            from_name: Sender name
            reply_to: Reply-to email address
            cc: CC recipients
            bcc: BCC recipients
            attachments: List of attachments
            tags: Tags for categorization
            use_queue: Whether to use the queue
            priority: Queue priority
            
        Returns:
            DeliveryResult with status
        """
        # Render template
        subject, html_content, text_content = self.template_service.render(
            template_id, context
        )
        
        return await self.send(
            to=to,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
            from_email=from_email,
            from_name=from_name,
            reply_to=reply_to,
            cc=cc,
            bcc=bcc,
            attachments=attachments,
            tags=tags,
            use_queue=use_queue,
            priority=priority,
        )
    
    async def send_batch(
        self,
        messages: List[Dict[str, Any]],
        use_queue: bool = True
    ) -> List[DeliveryResult]:
        """
        Send multiple emails.
        
        Args:
            messages: List of message dicts (same format as send() kwargs)
            use_queue: Whether to use the queue
            
        Returns:
            List of DeliveryResult for each message
        """
        results = []
        
        for msg_data in messages:
            result = await self.send(
                to=msg_data.get("to", []),
                subject=msg_data.get("subject", ""),
                html_content=msg_data.get("html_content"),
                text_content=msg_data.get("text_content"),
                from_email=msg_data.get("from_email"),
                from_name=msg_data.get("from_name"),
                reply_to=msg_data.get("reply_to"),
                cc=msg_data.get("cc"),
                bcc=msg_data.get("bcc"),
                attachments=msg_data.get("attachments"),
                tags=msg_data.get("tags"),
                use_queue=use_queue,
            )
            results.append(result)
        
        return results
    
    async def _send_direct(self, message: EmailMessage) -> DeliveryResult:
        """Send email directly through provider."""
        # Try primary provider
        primary_provider = self._providers.get(self.config.primary_provider)
        if primary_provider:
            result = await primary_provider.send(message)
            if result.success:
                if result.message_id:
                    self._delivery_statuses[result.message_id] = DeliveryStatus.SENT
                return result
        
        # Try fallback provider
        if self.config.fallback_provider:
            fallback_provider = self._providers.get(self.config.fallback_provider)
            if fallback_provider:
                logger.warning("Primary provider failed, using fallback")
                result = await fallback_provider.send(message)
                if result.success and result.message_id:
                    self._delivery_statuses[result.message_id] = DeliveryStatus.SENT
                return result
        
        return DeliveryResult.failure_result("No available email provider")
    
    def _build_message(
        self,
        to: List[str],
        subject: str,
        html_content: Optional[str] = None,
        text_content: Optional[str] = None,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
        reply_to: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> EmailMessage:
        """Build an EmailMessage object."""
        # Parse addresses
        to_addresses = [EmailAddress(email=addr) for addr in to]
        
        from_address = None
        if from_email or self.config.default_from_email:
            from_address = EmailAddress(
                email=from_email or self.config.default_from_email,
                name=from_name or self.config.default_from_name,
            )
        
        reply_to_address = None
        if reply_to:
            reply_to_address = EmailAddress(email=reply_to)
        
        cc_addresses = [EmailAddress(email=addr) for addr in (cc or [])]
        bcc_addresses = [EmailAddress(email=addr) for addr in (bcc or [])]
        
        # Parse attachments
        email_attachments = []
        for att in (attachments or []):
            email_attachments.append(EmailAttachment(
                filename=att["filename"],
                content=att["content"] if isinstance(att["content"], bytes) else att["content"].encode(),
                content_type=att.get("content_type", "application/octet-stream"),
                content_id=att.get("content_id"),
                disposition=att.get("disposition", "attachment"),
            ))
        
        return EmailMessage(
            to=to_addresses,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
            from_address=from_address,
            reply_to=reply_to_address,
            cc=cc_addresses,
            bcc=bcc_addresses,
            attachments=email_attachments,
            tags=tags or [],
            metadata=metadata or {},
        )
    
    def get_delivery_status(self, message_id: str) -> Optional[DeliveryStatus]:
        """
        Get the delivery status of a sent email.
        
        Args:
            message_id: Message ID from send result
            
        Returns:
            DeliveryStatus or None if not found
        """
        return self._delivery_statuses.get(message_id)
    
    def get_delivery_events(self, message_id: str) -> List[DeliveryEvent]:
        """
        Get all delivery events for a message.
        
        Args:
            message_id: Message ID
            
        Returns:
            List of DeliveryEvent objects
        """
        return self._delivery_events.get(message_id, [])
    
    def process_webhook(
        self,
        provider: EmailProviderType,
        payload: Dict[str, Any],
        signature: Optional[str] = None,
        timestamp: Optional[str] = None
    ) -> Optional[DeliveryEvent]:
        """
        Process a delivery webhook from a provider.
        
        Args:
            provider: Provider type
            payload: Raw webhook payload
            signature: Webhook signature for verification
            timestamp: Webhook timestamp
            
        Returns:
            Parsed DeliveryEvent or None
        """
        email_provider = self._providers.get(provider)
        if not email_provider:
            logger.error(f"Unknown provider for webhook: {provider}")
            return None
        
        # Verify signature if provided
        if signature:
            payload_bytes = str(payload).encode() if not isinstance(payload, bytes) else payload
            if not email_provider.verify_webhook_signature(payload_bytes, signature, timestamp):
                logger.warning("Webhook signature verification failed")
                return None
        
        # Parse event
        event = email_provider.parse_webhook_event(payload)
        if event:
            # Update status
            self._delivery_statuses[event.message_id] = event.event_type
            
            # Store event
            if event.message_id not in self._delivery_events:
                self._delivery_events[event.message_id] = []
            self._delivery_events[event.message_id].append(event)
            
            logger.info(f"Processed webhook event: {event.event_type} for {event.message_id}")
        
        return event
    
    async def start_queue(self) -> None:
        """Start the email queue processor."""
        if self._queue_manager:
            await self._queue_manager.start()
    
    async def stop_queue(self) -> None:
        """Stop the email queue processor."""
        if self._queue_manager:
            await self._queue_manager.stop()
    
    def get_queue_status(self, queue_id: str) -> Optional[QueuedEmail]:
        """Get status of a queued email."""
        if self._queue_manager:
            return self._queue_manager.get_status(queue_id)
        return None
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        if self._queue_manager:
            return self._queue_manager.get_queue_stats()
        return {"queue_enabled": False}
    
    async def health_check(self) -> Dict[str, bool]:
        """Check health of all providers."""
        results = {}
        for provider_type, provider in self._providers.items():
            try:
                results[provider_type.value] = await provider.health_check()
            except Exception:
                results[provider_type.value] = False
        return results

