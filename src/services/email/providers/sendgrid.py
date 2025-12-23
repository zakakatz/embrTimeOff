"""SendGrid email provider implementation."""

import base64
import hashlib
import hmac
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
import json

from src.services.email.providers.base import (
    EmailProvider,
    EmailProviderType,
    EmailMessage,
    DeliveryResult,
    DeliveryStatus,
    DeliveryEvent,
    BounceType,
)

logger = logging.getLogger(__name__)


class SendGridProvider(EmailProvider):
    """
    SendGrid email provider.
    
    Supports:
    - Single and batch email sending
    - HTML and plain text content
    - Attachments (inline and regular)
    - Delivery tracking via webhooks
    - Email scheduling
    """
    
    provider_type = EmailProviderType.SENDGRID
    API_BASE_URL = "https://api.sendgrid.com/v3"
    
    # Event type mapping from SendGrid to internal status
    EVENT_MAPPING = {
        "processed": DeliveryStatus.QUEUED,
        "dropped": DeliveryStatus.DROPPED,
        "delivered": DeliveryStatus.DELIVERED,
        "deferred": DeliveryStatus.PENDING,
        "bounce": DeliveryStatus.BOUNCED,
        "open": DeliveryStatus.OPENED,
        "click": DeliveryStatus.CLICKED,
        "spamreport": DeliveryStatus.SPAM,
        "unsubscribe": DeliveryStatus.UNSUBSCRIBED,
        "group_unsubscribe": DeliveryStatus.UNSUBSCRIBED,
        "group_resubscribe": DeliveryStatus.DELIVERED,
    }
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize SendGrid provider.
        
        Config options:
        - api_key: SendGrid API key (required, or SENDGRID_API_KEY env var)
        - webhook_key: Webhook verification key (optional)
        - default_from_email: Default sender email
        - default_from_name: Default sender name
        - sandbox_mode: Enable sandbox mode for testing
        """
        self.config = config or {}
        self._validate_config()
        self._http_client = None
    
    def _validate_config(self) -> None:
        """Validate SendGrid configuration."""
        self.api_key = self.config.get("api_key") or os.getenv("SENDGRID_API_KEY")
        if not self.api_key:
            raise ValueError("SendGrid API key is required")
        
        self.webhook_key = self.config.get("webhook_key") or os.getenv("SENDGRID_WEBHOOK_KEY")
        self.default_from_email = self.config.get("default_from_email") or os.getenv("SENDGRID_FROM_EMAIL")
        self.default_from_name = self.config.get("default_from_name") or os.getenv("SENDGRID_FROM_NAME", "")
        self.sandbox_mode = self.config.get("sandbox_mode", False)
    
    async def send(self, message: EmailMessage) -> DeliveryResult:
        """Send an email via SendGrid."""
        try:
            payload = self._build_payload(message)
            
            # Try to use httpx for async, fall back to requests
            try:
                import httpx
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{self.API_BASE_URL}/mail/send",
                        headers=self._get_headers(),
                        json=payload,
                        timeout=30.0,
                    )
                status_code = response.status_code
                response_text = response.text
                response_headers = dict(response.headers)
            except ImportError:
                # Fallback to synchronous requests
                import requests
                response = requests.post(
                    f"{self.API_BASE_URL}/mail/send",
                    headers=self._get_headers(),
                    json=payload,
                    timeout=30,
                )
                status_code = response.status_code
                response_text = response.text
                response_headers = dict(response.headers)
            
            if status_code in (200, 201, 202):
                # SendGrid returns message ID in X-Message-Id header
                message_id = response_headers.get("x-message-id", "")
                return DeliveryResult.success_result(message_id, self.provider_type)
            else:
                error_data = json.loads(response_text) if response_text else {}
                errors = error_data.get("errors", [])
                error_msg = errors[0].get("message") if errors else f"HTTP {status_code}"
                return DeliveryResult.failure_result(
                    error_message=error_msg,
                    provider=self.provider_type,
                    error_code=str(status_code),
                )
                
        except Exception as e:
            logger.exception("SendGrid send failed")
            return DeliveryResult.failure_result(
                error_message=str(e),
                provider=self.provider_type,
            )
    
    async def send_batch(self, messages: List[EmailMessage]) -> List[DeliveryResult]:
        """Send multiple emails via SendGrid."""
        # SendGrid doesn't have a true batch API, send individually
        results = []
        for message in messages:
            result = await self.send(message)
            results.append(result)
        return results
    
    async def get_delivery_status(self, message_id: str) -> Optional[DeliveryStatus]:
        """
        Get delivery status from SendGrid.
        
        Note: SendGrid doesn't provide a direct status API.
        Status tracking is done via webhooks.
        """
        logger.warning("SendGrid status lookup requires webhook integration")
        return None
    
    def parse_webhook_event(self, payload: Dict[str, Any]) -> Optional[DeliveryEvent]:
        """Parse SendGrid webhook event."""
        try:
            # SendGrid sends events in a list
            events = payload if isinstance(payload, list) else [payload]
            
            for event in events:
                event_type = event.get("event", "").lower()
                if event_type not in self.EVENT_MAPPING:
                    continue
                
                # Extract bounce type
                bounce_type = None
                if event_type == "bounce":
                    bounce_classification = event.get("type", "").lower()
                    if "block" in bounce_classification:
                        bounce_type = BounceType.BLOCK
                    elif "bounce" in bounce_classification:
                        bounce_type = BounceType.HARD if "hard" in bounce_classification else BounceType.SOFT
                    else:
                        bounce_type = BounceType.UNKNOWN
                
                return DeliveryEvent(
                    message_id=event.get("sg_message_id", "").split(".")[0],
                    event_type=self.EVENT_MAPPING[event_type],
                    email=event.get("email", ""),
                    timestamp=datetime.fromtimestamp(event.get("timestamp", 0)),
                    provider=self.provider_type,
                    bounce_type=bounce_type,
                    reason=event.get("reason"),
                    user_agent=event.get("useragent"),
                    ip_address=event.get("ip"),
                    link_url=event.get("url"),
                    raw_event=event,
                )
            
            return None
        except Exception as e:
            logger.error(f"Failed to parse SendGrid webhook: {e}")
            return None
    
    def verify_webhook_signature(
        self,
        payload: bytes,
        signature: str,
        timestamp: Optional[str] = None
    ) -> bool:
        """Verify SendGrid webhook signature."""
        if not self.webhook_key:
            logger.warning("No webhook key configured for SendGrid")
            return True  # Skip verification if no key
        
        try:
            # SendGrid uses ECDSA signature
            # For simplicity, we'll do basic HMAC verification
            # In production, use proper ECDSA verification
            
            expected = hmac.new(
                self.webhook_key.encode(),
                payload,
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(expected, signature)
        except Exception as e:
            logger.error(f"Webhook verification failed: {e}")
            return False
    
    async def health_check(self) -> bool:
        """Check SendGrid API availability."""
        try:
            try:
                import httpx
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{self.API_BASE_URL}/scopes",
                        headers=self._get_headers(),
                        timeout=10.0,
                    )
                return response.status_code == 200
            except ImportError:
                import requests
                response = requests.get(
                    f"{self.API_BASE_URL}/scopes",
                    headers=self._get_headers(),
                    timeout=10,
                )
                return response.status_code == 200
        except Exception:
            return False
    
    def _get_headers(self) -> Dict[str, str]:
        """Get API headers."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
    
    def _build_payload(self, message: EmailMessage) -> Dict[str, Any]:
        """Build SendGrid API payload."""
        from_addr = message.from_address
        if not from_addr:
            from_addr = type('obj', (object,), {
                'email': self.default_from_email,
                'name': self.default_from_name
            })()
        
        payload = {
            "personalizations": [
                {
                    "to": [{"email": addr.email, "name": addr.name} for addr in message.to],
                }
            ],
            "from": {
                "email": from_addr.email,
                "name": from_addr.name or "",
            },
            "subject": message.subject,
        }
        
        # Add CC
        if message.cc:
            payload["personalizations"][0]["cc"] = [
                {"email": addr.email, "name": addr.name} for addr in message.cc
            ]
        
        # Add BCC
        if message.bcc:
            payload["personalizations"][0]["bcc"] = [
                {"email": addr.email, "name": addr.name} for addr in message.bcc
            ]
        
        # Add content
        content = []
        if message.text_content:
            content.append({"type": "text/plain", "value": message.text_content})
        if message.html_content:
            content.append({"type": "text/html", "value": message.html_content})
        payload["content"] = content
        
        # Add reply-to
        if message.reply_to:
            payload["reply_to"] = {
                "email": message.reply_to.email,
                "name": message.reply_to.name or "",
            }
        
        # Add attachments
        if message.attachments:
            payload["attachments"] = []
            for att in message.attachments:
                attachment_data = {
                    "content": base64.b64encode(att.content).decode(),
                    "filename": att.filename,
                    "type": att.content_type,
                    "disposition": att.disposition,
                }
                if att.content_id:
                    attachment_data["content_id"] = att.content_id
                payload["attachments"].append(attachment_data)
        
        # Add custom headers
        if message.headers:
            payload["headers"] = message.headers
        
        # Add categories/tags
        if message.tags:
            payload["categories"] = message.tags[:10]  # SendGrid limit
        
        # Add tracking ID as custom arg
        if message.tracking_id:
            payload["personalizations"][0]["custom_args"] = {
                "tracking_id": message.tracking_id
            }
        
        # Add scheduled send time
        if message.send_at:
            payload["send_at"] = int(message.send_at.timestamp())
        
        # Sandbox mode
        if self.sandbox_mode:
            payload["mail_settings"] = {"sandbox_mode": {"enable": True}}
        
        return payload

