"""AWS SES email provider implementation."""

import base64
import hashlib
import hmac
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

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


class SESProvider(EmailProvider):
    """
    AWS Simple Email Service (SES) provider.
    
    Supports:
    - Single and batch email sending
    - HTML and plain text content
    - Attachments
    - Delivery tracking via SNS webhooks
    - Configuration sets for tracking
    """
    
    provider_type = EmailProviderType.SES
    
    # Event type mapping from SES/SNS to internal status
    EVENT_MAPPING = {
        "send": DeliveryStatus.SENT,
        "reject": DeliveryStatus.FAILED,
        "bounce": DeliveryStatus.BOUNCED,
        "complaint": DeliveryStatus.SPAM,
        "delivery": DeliveryStatus.DELIVERED,
        "open": DeliveryStatus.OPENED,
        "click": DeliveryStatus.CLICKED,
        "renderingfailure": DeliveryStatus.FAILED,
    }
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize SES provider.
        
        Config options:
        - aws_access_key_id: AWS access key (or use AWS_ACCESS_KEY_ID env var)
        - aws_secret_access_key: AWS secret key (or use AWS_SECRET_ACCESS_KEY env var)
        - aws_region: AWS region (default: us-east-1)
        - configuration_set: SES configuration set for tracking
        - default_from_email: Default sender email
        - default_from_name: Default sender name
        """
        self.config = config or {}
        self._validate_config()
        self._ses_client = None
    
    def _validate_config(self) -> None:
        """Validate SES configuration."""
        self.aws_access_key = self.config.get("aws_access_key_id") or os.getenv("AWS_ACCESS_KEY_ID")
        self.aws_secret_key = self.config.get("aws_secret_access_key") or os.getenv("AWS_SECRET_ACCESS_KEY")
        self.aws_region = self.config.get("aws_region") or os.getenv("AWS_REGION", "us-east-1")
        self.configuration_set = self.config.get("configuration_set") or os.getenv("SES_CONFIGURATION_SET")
        self.default_from_email = self.config.get("default_from_email") or os.getenv("SES_FROM_EMAIL")
        self.default_from_name = self.config.get("default_from_name") or os.getenv("SES_FROM_NAME", "")
    
    def _get_client(self):
        """Get or create boto3 SES client."""
        if self._ses_client is None:
            try:
                import boto3
                
                client_kwargs = {"region_name": self.aws_region}
                if self.aws_access_key and self.aws_secret_key:
                    client_kwargs["aws_access_key_id"] = self.aws_access_key
                    client_kwargs["aws_secret_access_key"] = self.aws_secret_key
                
                self._ses_client = boto3.client("ses", **client_kwargs)
            except ImportError:
                raise ImportError("boto3 is required for SES provider")
        
        return self._ses_client
    
    async def send(self, message: EmailMessage) -> DeliveryResult:
        """Send an email via SES."""
        try:
            client = self._get_client()
            
            # Build email
            if message.attachments:
                # Use raw email for attachments
                raw_email = self._build_raw_email(message)
                
                send_kwargs = {
                    "Source": self._format_address(message.from_address),
                    "Destinations": [addr.email for addr in message.to + message.cc + message.bcc],
                    "RawMessage": {"Data": raw_email},
                }
                
                if self.configuration_set:
                    send_kwargs["ConfigurationSetName"] = self.configuration_set
                
                response = client.send_raw_email(**send_kwargs)
            else:
                # Use simple email API
                send_kwargs = self._build_send_email_params(message)
                response = client.send_email(**send_kwargs)
            
            message_id = response.get("MessageId", "")
            return DeliveryResult.success_result(message_id, self.provider_type)
            
        except Exception as e:
            logger.exception("SES send failed")
            error_code = getattr(e, "response", {}).get("Error", {}).get("Code", "Unknown")
            return DeliveryResult.failure_result(
                error_message=str(e),
                provider=self.provider_type,
                error_code=error_code,
            )
    
    async def send_batch(self, messages: List[EmailMessage]) -> List[DeliveryResult]:
        """Send multiple emails via SES."""
        # SES has SendBulkTemplatedEmail but requires templates
        # For flexibility, send individually
        results = []
        for message in messages:
            result = await self.send(message)
            results.append(result)
        return results
    
    async def get_delivery_status(self, message_id: str) -> Optional[DeliveryStatus]:
        """
        Get delivery status from SES.
        
        Note: SES doesn't provide direct status lookup.
        Status tracking is done via SNS notifications.
        """
        logger.warning("SES status lookup requires SNS notification integration")
        return None
    
    def parse_webhook_event(self, payload: Dict[str, Any]) -> Optional[DeliveryEvent]:
        """Parse SES SNS webhook event."""
        try:
            # Handle SNS notification wrapper
            if payload.get("Type") == "Notification":
                message = json.loads(payload.get("Message", "{}"))
            else:
                message = payload
            
            event_type = message.get("eventType", message.get("notificationType", "")).lower()
            if event_type not in self.EVENT_MAPPING:
                return None
            
            mail_info = message.get("mail", {})
            
            # Determine bounce type
            bounce_type = None
            if event_type == "bounce":
                bounce_info = message.get("bounce", {})
                bounce_classification = bounce_info.get("bounceType", "").lower()
                if bounce_classification == "permanent":
                    bounce_type = BounceType.HARD
                elif bounce_classification == "transient":
                    bounce_type = BounceType.SOFT
                else:
                    bounce_type = BounceType.UNKNOWN
            
            # Get recipient email
            if event_type == "bounce":
                recipients = message.get("bounce", {}).get("bouncedRecipients", [])
                email = recipients[0].get("emailAddress", "") if recipients else ""
                reason = recipients[0].get("diagnosticCode", "") if recipients else ""
            elif event_type == "complaint":
                recipients = message.get("complaint", {}).get("complainedRecipients", [])
                email = recipients[0].get("emailAddress", "") if recipients else ""
                reason = message.get("complaint", {}).get("complaintFeedbackType", "")
            else:
                email = mail_info.get("destination", [""])[0]
                reason = None
            
            return DeliveryEvent(
                message_id=mail_info.get("messageId", ""),
                event_type=self.EVENT_MAPPING[event_type],
                email=email,
                timestamp=datetime.fromisoformat(
                    mail_info.get("timestamp", datetime.utcnow().isoformat()).replace("Z", "+00:00")
                ),
                provider=self.provider_type,
                bounce_type=bounce_type,
                reason=reason,
                raw_event=message,
            )
            
        except Exception as e:
            logger.error(f"Failed to parse SES webhook: {e}")
            return None
    
    def verify_webhook_signature(
        self,
        payload: bytes,
        signature: str,
        timestamp: Optional[str] = None
    ) -> bool:
        """
        Verify SNS message signature.
        
        Note: Full SNS signature verification requires downloading
        the signing certificate. This is a simplified check.
        """
        try:
            # Parse the payload to get signature info
            data = json.loads(payload)
            
            # For SNS, verify the subscription confirmation
            if data.get("Type") == "SubscriptionConfirmation":
                logger.info("SNS subscription confirmation received")
                return True
            
            # Basic validation - check required fields
            required_fields = ["Message", "MessageId", "Timestamp", "TopicArn"]
            if all(field in data for field in required_fields):
                return True
            
            return False
        except Exception as e:
            logger.error(f"Webhook verification failed: {e}")
            return False
    
    async def health_check(self) -> bool:
        """Check SES API availability."""
        try:
            client = self._get_client()
            client.get_send_quota()
            return True
        except Exception:
            return False
    
    def get_rate_limits(self) -> Dict[str, int]:
        """Get SES sending quota."""
        try:
            client = self._get_client()
            quota = client.get_send_quota()
            return {
                "max_24_hour_send": int(quota.get("Max24HourSend", 0)),
                "max_send_rate": int(quota.get("MaxSendRate", 0)),
                "sent_last_24_hours": int(quota.get("SentLast24Hours", 0)),
            }
        except Exception:
            return super().get_rate_limits()
    
    def _format_address(self, address) -> str:
        """Format email address for SES."""
        if address is None:
            return f"{self.default_from_name} <{self.default_from_email}>" if self.default_from_name else self.default_from_email
        if address.name:
            return f"{address.name} <{address.email}>"
        return address.email
    
    def _build_send_email_params(self, message: EmailMessage) -> Dict[str, Any]:
        """Build parameters for send_email API."""
        params = {
            "Source": self._format_address(message.from_address),
            "Destination": {
                "ToAddresses": [addr.email for addr in message.to],
            },
            "Message": {
                "Subject": {"Data": message.subject, "Charset": "UTF-8"},
                "Body": {},
            },
        }
        
        # Add CC/BCC
        if message.cc:
            params["Destination"]["CcAddresses"] = [addr.email for addr in message.cc]
        if message.bcc:
            params["Destination"]["BccAddresses"] = [addr.email for addr in message.bcc]
        
        # Add body content
        if message.text_content:
            params["Message"]["Body"]["Text"] = {"Data": message.text_content, "Charset": "UTF-8"}
        if message.html_content:
            params["Message"]["Body"]["Html"] = {"Data": message.html_content, "Charset": "UTF-8"}
        
        # Add reply-to
        if message.reply_to:
            params["ReplyToAddresses"] = [message.reply_to.email]
        
        # Add configuration set
        if self.configuration_set:
            params["ConfigurationSetName"] = self.configuration_set
        
        # Add tags
        if message.tags:
            params["Tags"] = [{"Name": f"tag_{i}", "Value": tag} for i, tag in enumerate(message.tags[:10])]
        
        return params
    
    def _build_raw_email(self, message: EmailMessage) -> bytes:
        """Build raw MIME email with attachments."""
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        from email.mime.base import MIMEBase
        from email import encoders
        from email.utils import formataddr
        
        # Create message container
        msg = MIMEMultipart("mixed")
        
        # Set headers
        from_addr = message.from_address
        if from_addr:
            msg["From"] = formataddr((from_addr.name or "", from_addr.email))
        else:
            msg["From"] = formataddr((self.default_from_name, self.default_from_email))
        
        msg["To"] = ", ".join(formataddr((a.name or "", a.email)) for a in message.to)
        msg["Subject"] = message.subject
        
        if message.cc:
            msg["Cc"] = ", ".join(formataddr((a.name or "", a.email)) for a in message.cc)
        if message.reply_to:
            msg["Reply-To"] = formataddr((message.reply_to.name or "", message.reply_to.email))
        
        # Add custom headers
        for key, value in message.headers.items():
            msg[key] = value
        
        # Create body part
        body_part = MIMEMultipart("alternative")
        
        if message.text_content:
            body_part.attach(MIMEText(message.text_content, "plain", "utf-8"))
        if message.html_content:
            body_part.attach(MIMEText(message.html_content, "html", "utf-8"))
        
        msg.attach(body_part)
        
        # Add attachments
        for attachment in message.attachments:
            part = MIMEBase(*attachment.content_type.split("/", 1))
            part.set_payload(attachment.content)
            encoders.encode_base64(part)
            
            if attachment.disposition == "inline" and attachment.content_id:
                part.add_header("Content-ID", f"<{attachment.content_id}>")
                part.add_header("Content-Disposition", "inline", filename=attachment.filename)
            else:
                part.add_header("Content-Disposition", "attachment", filename=attachment.filename)
            
            msg.attach(part)
        
        return msg.as_bytes()

