"""Email service package for transactional and notification emails."""

from src.services.email.email_service import EmailService
from src.services.email.template_service import EmailTemplateService
from src.services.email.queue_manager import EmailQueueManager
from src.services.email.providers.base import EmailProvider, EmailProviderType

__all__ = [
    "EmailService",
    "EmailTemplateService",
    "EmailQueueManager",
    "EmailProvider",
    "EmailProviderType",
]

