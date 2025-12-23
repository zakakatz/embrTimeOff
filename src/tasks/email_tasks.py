"""
Email Delivery Tasks

Background tasks for sending emails and notifications
with retry logic and delivery tracking.
"""

import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from src.tasks.base import (
    RetryConfig,
    background_task,
    register_task,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Configuration
# =============================================================================

class EmailPriority(str, Enum):
    """Email priority levels."""
    
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class NotificationType(str, Enum):
    """Types of notifications."""
    
    TIME_OFF_REQUEST = "time_off_request"
    TIME_OFF_APPROVED = "time_off_approved"
    TIME_OFF_DENIED = "time_off_denied"
    BALANCE_LOW = "balance_low"
    PROFILE_UPDATED = "profile_updated"
    WELCOME = "welcome"
    PASSWORD_RESET = "password_reset"
    REPORT_READY = "report_ready"


# Retry configuration for email tasks
EMAIL_RETRY_CONFIG = RetryConfig(
    max_retries=5,
    default_retry_delay=60,  # 1 minute
    exponential_backoff=True,
    max_backoff_delay=3600,  # 1 hour max
)

# Higher retry for urgent emails
URGENT_EMAIL_RETRY_CONFIG = RetryConfig(
    max_retries=10,
    default_retry_delay=30,  # 30 seconds
    exponential_backoff=True,
    max_backoff_delay=1800,  # 30 minutes max
)


# =============================================================================
# Email Sending Tasks
# =============================================================================

@register_task(
    queue="notifications",
    description="Send a single email",
    tags=["email", "notification"],
)
@background_task(
    name="tasks.send_email",
    queue="notifications",
    retry_config=EMAIL_RETRY_CONFIG,
    soft_time_limit=60,
    time_limit=120,
)
def send_email(
    to: str,
    subject: str,
    body: str,
    from_email: Optional[str] = None,
    cc: Optional[List[str]] = None,
    bcc: Optional[List[str]] = None,
    reply_to: Optional[str] = None,
    priority: str = EmailPriority.NORMAL.value,
    attachments: Optional[List[Dict[str, Any]]] = None,
    track_opens: bool = True,
    track_clicks: bool = True,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Send a single email.
    
    Args:
        to: Recipient email address
        subject: Email subject
        body: Email body (HTML supported)
        from_email: Sender email (defaults to system default)
        cc: CC recipients
        bcc: BCC recipients
        reply_to: Reply-to address
        priority: Email priority level
        attachments: List of attachment dictionaries
        track_opens: Enable open tracking
        track_clicks: Enable click tracking
        metadata: Additional metadata for tracking
    
    Returns:
        Dictionary with send results
    """
    logger.info(f"Sending email to {to}: {subject}")
    
    # Build email result
    result = {
        "to": to,
        "subject": subject,
        "priority": priority,
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "status": "sent",
        "message_id": None,
        "metadata": metadata or {},
    }
    
    try:
        # This would integrate with actual email service
        # (e.g., SendGrid, AWS SES, SMTP)
        
        # Placeholder implementation
        import uuid
        result["message_id"] = f"msg_{uuid.uuid4().hex[:12]}"
        
        logger.info(
            f"Email sent successfully: {result['message_id']} to {to}"
        )
        
    except Exception as e:
        result["status"] = "failed"
        result["error"] = str(e)
        logger.error(f"Failed to send email to {to}: {e}")
        raise
    
    return result


@register_task(
    queue="notifications",
    description="Send email to multiple recipients",
    tags=["email", "notification", "batch"],
)
@background_task(
    name="tasks.send_bulk_email",
    queue="notifications",
    retry_config=EMAIL_RETRY_CONFIG,
    soft_time_limit=300,
    time_limit=600,
)
def send_bulk_email(
    recipients: List[str],
    subject: str,
    body: str,
    batch_id: Optional[str] = None,
    personalize: bool = False,
    personalization_data: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Send email to multiple recipients.
    
    Args:
        recipients: List of recipient email addresses
        subject: Email subject
        body: Email body template
        batch_id: Optional batch identifier
        personalize: Enable personalization
        personalization_data: Dict mapping email to personalization data
    
    Returns:
        Dictionary with batch send results
    """
    logger.info(f"Sending bulk email to {len(recipients)} recipients")
    
    results = {
        "batch_id": batch_id or f"bulk_{datetime.now(timezone.utc).timestamp()}",
        "total_recipients": len(recipients),
        "sent": 0,
        "failed": 0,
        "errors": [],
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    
    for email in recipients:
        try:
            # Personalize if enabled
            personalized_body = body
            personalized_subject = subject
            
            if personalize and personalization_data:
                data = personalization_data.get(email, {})
                for key, value in data.items():
                    personalized_body = personalized_body.replace(f"{{{{{key}}}}}", str(value))
                    personalized_subject = personalized_subject.replace(f"{{{{{key}}}}}", str(value))
            
            # Send individual email
            send_email(
                to=email,
                subject=personalized_subject,
                body=personalized_body,
                metadata={"batch_id": results["batch_id"]},
            )
            results["sent"] += 1
            
        except Exception as e:
            results["failed"] += 1
            results["errors"].append({"email": email, "error": str(e)})
    
    results["completed_at"] = datetime.now(timezone.utc).isoformat()
    
    logger.info(
        f"Bulk email completed: {results['sent']} sent, {results['failed']} failed"
    )
    
    return results


# =============================================================================
# Notification Tasks
# =============================================================================

@register_task(
    queue="notifications",
    description="Send notification based on type",
    tags=["notification"],
)
@background_task(
    name="tasks.send_notification",
    queue="notifications",
    retry_config=EMAIL_RETRY_CONFIG,
    soft_time_limit=60,
    time_limit=120,
)
def send_notification(
    notification_type: str,
    recipient_id: int,
    data: Dict[str, Any],
    channels: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Send a notification through configured channels.
    
    Args:
        notification_type: Type of notification
        recipient_id: Employee ID of recipient
        data: Notification data
        channels: Override channels (defaults to user preferences)
    
    Returns:
        Dictionary with notification results
    """
    logger.info(
        f"Sending {notification_type} notification to employee {recipient_id}"
    )
    
    # Default channels if not specified
    channels = channels or ["email", "in_app"]
    
    results = {
        "notification_type": notification_type,
        "recipient_id": recipient_id,
        "channels": channels,
        "channel_results": {},
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }
    
    # Get notification template based on type
    template = _get_notification_template(notification_type)
    
    for channel in channels:
        try:
            if channel == "email":
                # Get recipient email (would query from database)
                recipient_email = data.get("email", f"employee_{recipient_id}@example.com")
                
                send_email(
                    to=recipient_email,
                    subject=template["subject"].format(**data),
                    body=template["body"].format(**data),
                    priority=template.get("priority", EmailPriority.NORMAL.value),
                )
                results["channel_results"]["email"] = "sent"
                
            elif channel == "in_app":
                # Would create in-app notification record
                results["channel_results"]["in_app"] = "created"
                
            elif channel == "push":
                # Would send push notification
                results["channel_results"]["push"] = "sent"
                
        except Exception as e:
            results["channel_results"][channel] = f"failed: {str(e)}"
            logger.error(f"Failed to send {channel} notification: {e}")
    
    return results


def _get_notification_template(notification_type: str) -> Dict[str, str]:
    """Get notification template for given type."""
    templates = {
        NotificationType.TIME_OFF_REQUEST.value: {
            "subject": "Time-off Request Submitted",
            "body": "Your time-off request for {start_date} to {end_date} has been submitted and is pending approval.",
            "priority": EmailPriority.NORMAL.value,
        },
        NotificationType.TIME_OFF_APPROVED.value: {
            "subject": "Time-off Request Approved",
            "body": "Your time-off request for {start_date} to {end_date} has been approved.",
            "priority": EmailPriority.HIGH.value,
        },
        NotificationType.TIME_OFF_DENIED.value: {
            "subject": "Time-off Request Denied",
            "body": "Your time-off request for {start_date} to {end_date} was not approved. Reason: {reason}",
            "priority": EmailPriority.HIGH.value,
        },
        NotificationType.BALANCE_LOW.value: {
            "subject": "Low Balance Alert",
            "body": "Your {policy_name} balance is low ({balance} hours remaining).",
            "priority": EmailPriority.NORMAL.value,
        },
        NotificationType.PROFILE_UPDATED.value: {
            "subject": "Profile Updated",
            "body": "Your profile has been updated. Fields changed: {fields_changed}.",
            "priority": EmailPriority.LOW.value,
        },
        NotificationType.WELCOME.value: {
            "subject": "Welcome to {company_name}!",
            "body": "Welcome to the team, {first_name}! We're excited to have you.",
            "priority": EmailPriority.HIGH.value,
        },
        NotificationType.PASSWORD_RESET.value: {
            "subject": "Password Reset Request",
            "body": "Click the link to reset your password: {reset_link}",
            "priority": EmailPriority.URGENT.value,
        },
        NotificationType.REPORT_READY.value: {
            "subject": "Your Report is Ready",
            "body": "Your requested report ({report_name}) is ready. Click here to download: {download_link}",
            "priority": EmailPriority.NORMAL.value,
        },
    }
    
    return templates.get(notification_type, {
        "subject": "Notification",
        "body": "You have a new notification.",
        "priority": EmailPriority.NORMAL.value,
    })


# =============================================================================
# Manager Notification Tasks
# =============================================================================

@register_task(
    queue="notifications",
    description="Notify manager of time-off request",
    tags=["notification", "time-off", "manager"],
)
@background_task(
    name="tasks.notify_manager_time_off_request",
    queue="notifications",
    retry_config=URGENT_EMAIL_RETRY_CONFIG,
    soft_time_limit=60,
    time_limit=120,
)
def notify_manager_time_off_request(
    request_id: int,
    employee_id: int,
    manager_id: int,
    start_date: str,
    end_date: str,
    hours_requested: float,
) -> Dict[str, Any]:
    """
    Notify manager of a new time-off request.
    
    Args:
        request_id: Time-off request ID
        employee_id: Employee who submitted request
        manager_id: Manager to notify
        start_date: Request start date
        end_date: Request end date
        hours_requested: Total hours requested
    
    Returns:
        Dictionary with notification results
    """
    logger.info(
        f"Notifying manager {manager_id} of time-off request {request_id}"
    )
    
    return send_notification(
        notification_type="manager_time_off_request",
        recipient_id=manager_id,
        data={
            "request_id": request_id,
            "employee_id": employee_id,
            "start_date": start_date,
            "end_date": end_date,
            "hours_requested": hours_requested,
        },
        channels=["email", "in_app"],
    )


@register_task(
    queue="notifications",
    description="Send daily digest of pending approvals",
    tags=["notification", "digest", "manager"],
)
@background_task(
    name="tasks.send_pending_approvals_digest",
    queue="notifications",
    retry_config=EMAIL_RETRY_CONFIG,
    soft_time_limit=300,
    time_limit=600,
)
def send_pending_approvals_digest(
    manager_id: int,
    pending_requests: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Send daily digest of pending approvals to manager.
    
    Args:
        manager_id: Manager to send digest to
        pending_requests: List of pending request details
    
    Returns:
        Dictionary with send results
    """
    logger.info(
        f"Sending pending approvals digest to manager {manager_id} "
        f"({len(pending_requests)} requests)"
    )
    
    # Format request list
    request_list = "\n".join([
        f"- {r['employee_name']}: {r['start_date']} to {r['end_date']} ({r['hours']} hours)"
        for r in pending_requests
    ])
    
    return send_email(
        to=f"manager_{manager_id}@example.com",  # Would get actual email
        subject=f"Pending Approvals ({len(pending_requests)} requests)",
        body=f"""
        You have {len(pending_requests)} pending time-off requests to review:
        
        {request_list}
        
        Please log in to review and approve or deny these requests.
        """,
        priority=EmailPriority.NORMAL.value,
        metadata={
            "type": "pending_approvals_digest",
            "manager_id": manager_id,
            "request_count": len(pending_requests),
        },
    )

