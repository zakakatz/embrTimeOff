"""API endpoints for email service."""

import base64
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Header, Request

from src.schemas.email import (
    SendEmailRequest,
    SendTemplateEmailRequest,
    SendBatchEmailRequest,
    WebhookEventRequest,
    RenderTemplateRequest,
    DeliveryResultResponse,
    BatchDeliveryResultResponse,
    DeliveryStatusResponse,
    DeliveryEventResponse,
    QueueStatusResponse,
    QueueStatsResponse,
    TemplateInfo,
    TemplateListResponse,
    RenderTemplateResponse,
    HealthCheckResponse,
    DeliveryStatusEnum,
    EmailProviderEnum,
    QueuePriorityEnum,
)
from src.services.email import EmailService
from src.services.email.queue_manager import QueuePriority

logger = logging.getLogger(__name__)

# Initialize email service
email_service = EmailService()

# Create router
email_router = APIRouter(prefix="/api/v1/email", tags=["Email"])

# Map API priority to service priority
PRIORITY_MAP = {
    QueuePriorityEnum.LOW: QueuePriority.LOW,
    QueuePriorityEnum.NORMAL: QueuePriority.NORMAL,
    QueuePriorityEnum.HIGH: QueuePriority.HIGH,
    QueuePriorityEnum.CRITICAL: QueuePriority.CRITICAL,
}


# =============================================================================
# Email Sending Endpoints
# =============================================================================

@email_router.post(
    "/send",
    response_model=DeliveryResultResponse,
    summary="Send an email",
    description="Send an email with HTML and/or plain text content."
)
async def send_email(request: SendEmailRequest) -> DeliveryResultResponse:
    """Send an email."""
    try:
        # Parse attachments
        attachments = None
        if request.attachments:
            attachments = [
                {
                    "filename": att.filename,
                    "content": base64.b64decode(att.content_base64),
                    "content_type": att.content_type,
                    "content_id": att.content_id,
                    "disposition": att.disposition,
                }
                for att in request.attachments
            ]
        
        result = await email_service.send(
            to=request.to,
            subject=request.subject,
            html_content=request.html_content,
            text_content=request.text_content,
            from_email=request.from_email,
            from_name=request.from_name,
            reply_to=request.reply_to,
            cc=request.cc,
            bcc=request.bcc,
            attachments=attachments,
            tags=request.tags,
            metadata=request.metadata,
            use_queue=request.use_queue,
            priority=PRIORITY_MAP.get(request.priority, QueuePriority.NORMAL),
            scheduled_at=request.scheduled_at,
        )
        
        return DeliveryResultResponse(
            success=result.success,
            message_id=result.message_id,
            status=DeliveryStatusEnum(result.status.value),
            error_code=result.error_code,
            error_message=result.error_message,
            timestamp=result.timestamp,
        )
        
    except Exception as e:
        logger.exception("Email send failed")
        raise HTTPException(status_code=500, detail=str(e))


@email_router.post(
    "/send/template",
    response_model=DeliveryResultResponse,
    summary="Send a templated email",
    description="Send an email using a pre-defined template with dynamic content."
)
async def send_template_email(request: SendTemplateEmailRequest) -> DeliveryResultResponse:
    """Send an email using a template."""
    try:
        # Parse attachments
        attachments = None
        if request.attachments:
            attachments = [
                {
                    "filename": att.filename,
                    "content": base64.b64decode(att.content_base64),
                    "content_type": att.content_type,
                }
                for att in request.attachments
            ]
        
        result = await email_service.send_template(
            template_id=request.template_id,
            to=request.to,
            context=request.context,
            from_email=request.from_email,
            from_name=request.from_name,
            reply_to=request.reply_to,
            cc=request.cc,
            bcc=request.bcc,
            attachments=attachments,
            tags=request.tags,
            use_queue=request.use_queue,
            priority=PRIORITY_MAP.get(request.priority, QueuePriority.NORMAL),
        )
        
        return DeliveryResultResponse(
            success=result.success,
            message_id=result.message_id,
            status=DeliveryStatusEnum(result.status.value),
            error_code=result.error_code,
            error_message=result.error_message,
            timestamp=result.timestamp,
        )
        
    except Exception as e:
        logger.exception("Template email send failed")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@email_router.post(
    "/send/batch",
    response_model=BatchDeliveryResultResponse,
    summary="Send batch emails",
    description="Send multiple emails in a single request."
)
async def send_batch_emails(request: SendBatchEmailRequest) -> BatchDeliveryResultResponse:
    """Send multiple emails."""
    try:
        messages = []
        for msg in request.messages:
            attachments = None
            if msg.attachments:
                attachments = [
                    {
                        "filename": att.filename,
                        "content": base64.b64decode(att.content_base64),
                        "content_type": att.content_type,
                    }
                    for att in msg.attachments
                ]
            
            messages.append({
                "to": msg.to,
                "subject": msg.subject,
                "html_content": msg.html_content,
                "text_content": msg.text_content,
                "from_email": msg.from_email,
                "from_name": msg.from_name,
                "reply_to": msg.reply_to,
                "cc": msg.cc,
                "bcc": msg.bcc,
                "attachments": attachments,
                "tags": msg.tags,
            })
        
        results = await email_service.send_batch(messages, use_queue=request.use_queue)
        
        response_results = [
            DeliveryResultResponse(
                success=r.success,
                message_id=r.message_id,
                status=DeliveryStatusEnum(r.status.value),
                error_code=r.error_code,
                error_message=r.error_message,
                timestamp=r.timestamp,
            )
            for r in results
        ]
        
        successful = sum(1 for r in results if r.success)
        
        return BatchDeliveryResultResponse(
            total=len(results),
            successful=successful,
            failed=len(results) - successful,
            results=response_results,
        )
        
    except Exception as e:
        logger.exception("Batch email send failed")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Delivery Status Endpoints
# =============================================================================

@email_router.get(
    "/status/{message_id}",
    response_model=DeliveryStatusResponse,
    summary="Get delivery status",
    description="Get the delivery status and events for a sent email."
)
async def get_delivery_status(message_id: str) -> DeliveryStatusResponse:
    """Get delivery status for a message."""
    status = email_service.get_delivery_status(message_id)
    events = email_service.get_delivery_events(message_id)
    
    if status is None and not events:
        # Check queue status
        queue_status = email_service.get_queue_status(message_id)
        if queue_status:
            return DeliveryStatusResponse(
                message_id=message_id,
                status=DeliveryStatusEnum.QUEUED,
                events=[],
            )
        raise HTTPException(status_code=404, detail="Message not found")
    
    return DeliveryStatusResponse(
        message_id=message_id,
        status=DeliveryStatusEnum(status.value) if status else DeliveryStatusEnum.PENDING,
        events=[
            DeliveryEventResponse(
                message_id=e.message_id,
                event_type=DeliveryStatusEnum(e.event_type.value),
                email=e.email,
                timestamp=e.timestamp,
                provider=EmailProviderEnum(e.provider.value),
                bounce_type=e.bounce_type.value if e.bounce_type else None,
                reason=e.reason,
            )
            for e in events
        ],
    )


@email_router.get(
    "/queue/{queue_id}",
    response_model=QueueStatusResponse,
    summary="Get queue status",
    description="Get the status of a queued email."
)
async def get_queue_status(queue_id: str) -> QueueStatusResponse:
    """Get status of a queued email."""
    queued_email = email_service.get_queue_status(queue_id)
    
    if not queued_email:
        raise HTTPException(status_code=404, detail="Queue entry not found")
    
    return QueueStatusResponse(
        queue_id=queued_email.id,
        status=queued_email.status.value,
        retry_count=queued_email.retry_count,
        created_at=queued_email.created_at,
        last_attempt_at=queued_email.last_attempt_at,
        next_retry_at=queued_email.next_retry_at,
        error_message=queued_email.error_message,
    )


@email_router.get(
    "/queue/stats",
    response_model=QueueStatsResponse,
    summary="Get queue statistics",
    description="Get email queue statistics."
)
async def get_queue_stats() -> QueueStatsResponse:
    """Get queue statistics."""
    stats = email_service.get_queue_stats()
    
    return QueueStatsResponse(
        pending=stats.get("pending", 0),
        processing=stats.get("processing", 0),
        sent=stats.get("sent", 0),
        failed=stats.get("failed", 0),
        retry_scheduled=stats.get("retry_scheduled", 0),
        total_completed=stats.get("total_completed", 0),
        is_running=stats.get("is_running", False),
    )


# =============================================================================
# Webhook Endpoints
# =============================================================================

@email_router.post(
    "/webhooks/{provider}",
    summary="Process provider webhook",
    description="Process delivery status webhooks from email providers."
)
async def process_webhook(
    provider: EmailProviderEnum,
    request: Request,
    x_signature: Optional[str] = Header(default=None, alias="X-Signature"),
    x_timestamp: Optional[str] = Header(default=None, alias="X-Timestamp"),
):
    """Process delivery webhook from provider."""
    try:
        payload = await request.json()
        
        from src.services.email.providers.base import EmailProviderType
        provider_type = EmailProviderType(provider.value)
        
        event = email_service.process_webhook(
            provider=provider_type,
            payload=payload,
            signature=x_signature,
            timestamp=x_timestamp,
        )
        
        if event:
            return {
                "processed": True,
                "event_type": event.event_type.value,
                "message_id": event.message_id,
            }
        
        return {"processed": False, "reason": "Invalid or unrecognized event"}
        
    except Exception as e:
        logger.exception("Webhook processing failed")
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# Template Endpoints
# =============================================================================

@email_router.get(
    "/templates",
    response_model=TemplateListResponse,
    summary="List templates",
    description="List available email templates."
)
async def list_templates(category: Optional[str] = None) -> TemplateListResponse:
    """List available email templates."""
    templates = email_service.template_service.list_templates(category)
    
    return TemplateListResponse(
        templates=[
            TemplateInfo(
                id=t.id,
                name=t.name,
                description=t.description,
                category=t.category,
                variables=t.variables,
                is_active=t.is_active,
            )
            for t in templates
        ],
        total=len(templates),
    )


@email_router.get(
    "/templates/{template_id}",
    response_model=TemplateInfo,
    summary="Get template",
    description="Get details of a specific email template."
)
async def get_template(template_id: str) -> TemplateInfo:
    """Get template details."""
    template = email_service.template_service.get_template(template_id)
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return TemplateInfo(
        id=template.id,
        name=template.name,
        description=template.description,
        category=template.category,
        variables=template.variables,
        is_active=template.is_active,
    )


@email_router.post(
    "/templates/render",
    response_model=RenderTemplateResponse,
    summary="Render template",
    description="Render a template with provided context data for preview."
)
async def render_template(request: RenderTemplateRequest) -> RenderTemplateResponse:
    """Render a template for preview."""
    try:
        subject, html, text = email_service.template_service.render(
            request.template_id,
            request.context,
        )
        
        return RenderTemplateResponse(
            subject=subject,
            html_content=html,
            text_content=text,
        )
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# Health & Management Endpoints
# =============================================================================

@email_router.get(
    "/health",
    response_model=HealthCheckResponse,
    summary="Health check",
    description="Check health of email service and providers."
)
async def health_check() -> HealthCheckResponse:
    """Check email service health."""
    provider_health = await email_service.health_check()
    queue_stats = email_service.get_queue_stats()
    
    return HealthCheckResponse(
        providers=provider_health,
        queue_enabled=queue_stats.get("queue_enabled", True),
        queue_running=queue_stats.get("is_running", False),
    )


@email_router.post(
    "/queue/start",
    summary="Start queue processor",
    description="Start the email queue processor."
)
async def start_queue():
    """Start the queue processor."""
    await email_service.start_queue()
    return {"message": "Queue processor started"}


@email_router.post(
    "/queue/stop",
    summary="Stop queue processor",
    description="Stop the email queue processor."
)
async def stop_queue():
    """Stop the queue processor."""
    await email_service.stop_queue()
    return {"message": "Queue processor stopped"}

