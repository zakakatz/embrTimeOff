"""
Webhook API Endpoints

Provides webhook endpoint management and delivery tracking.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.infrastructure.webhooks.webhook_service import (
    WebhookService,
    WebhookEndpoint,
    WebhookDelivery,
    WebhookEventType,
    DeliveryStatus,
    get_webhook_service,
)

router = APIRouter(prefix="/api/v1/webhooks", tags=["Webhooks"])


# =============================================================================
# Request/Response Models
# =============================================================================

class EndpointRegistrationRequest(BaseModel):
    """Request to register a webhook endpoint."""
    
    url: str = Field(..., description="Webhook URL (HTTPS recommended)")
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    events: List[str] = Field(
        default_factory=list,
        description="Event types to subscribe to (empty = all events)",
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EndpointResponse(BaseModel):
    """Webhook endpoint response."""
    
    id: str
    url: str
    name: str
    description: Optional[str] = None
    events: List[str]
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    # Stats
    total_deliveries: int
    successful_deliveries: int
    failed_deliveries: int
    last_delivery_at: Optional[datetime] = None
    
    # Secret only shown on creation
    secret: Optional[str] = None


class EndpointUpdateRequest(BaseModel):
    """Request to update a webhook endpoint."""
    
    url: Optional[str] = None
    name: Optional[str] = None
    events: Optional[List[str]] = None
    is_active: Optional[bool] = None


class DeliveryAttemptResponse(BaseModel):
    """Delivery attempt details."""
    
    id: str
    attempt_number: int
    attempted_at: datetime
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    status: str
    response_code: Optional[int] = None
    error_message: Optional[str] = None


class DeliveryResponse(BaseModel):
    """Webhook delivery response."""
    
    id: str
    endpoint_id: str
    endpoint_url: str
    event_type: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    attempt_count: int
    attempts: List[DeliveryAttemptResponse]


class DeliveryStatsResponse(BaseModel):
    """Delivery statistics response."""
    
    total: int
    delivered: int
    failed: int
    pending: int
    success_rate: float


class EventTypesResponse(BaseModel):
    """Available event types response."""
    
    event_types: List[str]


class TestWebhookRequest(BaseModel):
    """Request to test a webhook endpoint."""
    
    event_type: str = Field(default="test.ping")
    data: Dict[str, Any] = Field(
        default_factory=lambda: {"message": "Test webhook delivery"},
    )


# =============================================================================
# Endpoints
# =============================================================================

@router.post(
    "/endpoints",
    response_model=EndpointResponse,
    status_code=201,
    summary="Register Webhook Endpoint",
    description="Register a new webhook endpoint to receive events",
)
async def register_endpoint(
    request: EndpointRegistrationRequest,
    service: WebhookService = Depends(get_webhook_service),
) -> EndpointResponse:
    """
    Register a new webhook endpoint.
    
    Returns the endpoint details including the secret (shown only once).
    """
    # Validate event types
    valid_events = {e.value for e in WebhookEventType}
    for event in request.events:
        if event not in valid_events:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid event type: {event}",
            )
    
    endpoint = service.register_endpoint(
        url=request.url,
        name=request.name,
        events=request.events,
        description=request.description,
        metadata=request.metadata,
    )
    
    return EndpointResponse(
        id=endpoint.id,
        url=endpoint.url,
        name=endpoint.name,
        description=endpoint.description,
        events=endpoint.events,
        is_active=endpoint.is_active,
        created_at=endpoint.created_at,
        total_deliveries=0,
        successful_deliveries=0,
        failed_deliveries=0,
        secret=endpoint.secret,  # Only shown on creation
    )


@router.get(
    "/endpoints",
    response_model=List[EndpointResponse],
    summary="List Webhook Endpoints",
    description="List all registered webhook endpoints",
)
async def list_endpoints(
    active_only: bool = Query(True, description="Only return active endpoints"),
    service: WebhookService = Depends(get_webhook_service),
) -> List[EndpointResponse]:
    """List all webhook endpoints."""
    endpoints = service.list_endpoints(active_only=active_only)
    
    return [
        EndpointResponse(
            id=e.id,
            url=e.url,
            name=e.name,
            description=e.description,
            events=e.events,
            is_active=e.is_active,
            created_at=e.created_at,
            updated_at=e.updated_at,
            total_deliveries=e.total_deliveries,
            successful_deliveries=e.successful_deliveries,
            failed_deliveries=e.failed_deliveries,
            last_delivery_at=e.last_delivery_at,
        )
        for e in endpoints
    ]


@router.get(
    "/endpoints/{endpoint_id}",
    response_model=EndpointResponse,
    summary="Get Webhook Endpoint",
    description="Get details of a specific webhook endpoint",
)
async def get_endpoint(
    endpoint_id: str,
    service: WebhookService = Depends(get_webhook_service),
) -> EndpointResponse:
    """Get webhook endpoint details."""
    endpoint = service.get_endpoint(endpoint_id)
    
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")
    
    return EndpointResponse(
        id=endpoint.id,
        url=endpoint.url,
        name=endpoint.name,
        description=endpoint.description,
        events=endpoint.events,
        is_active=endpoint.is_active,
        created_at=endpoint.created_at,
        updated_at=endpoint.updated_at,
        total_deliveries=endpoint.total_deliveries,
        successful_deliveries=endpoint.successful_deliveries,
        failed_deliveries=endpoint.failed_deliveries,
        last_delivery_at=endpoint.last_delivery_at,
    )


@router.patch(
    "/endpoints/{endpoint_id}",
    response_model=EndpointResponse,
    summary="Update Webhook Endpoint",
    description="Update webhook endpoint configuration",
)
async def update_endpoint(
    endpoint_id: str,
    request: EndpointUpdateRequest,
    service: WebhookService = Depends(get_webhook_service),
) -> EndpointResponse:
    """Update webhook endpoint."""
    # Validate event types if provided
    if request.events:
        valid_events = {e.value for e in WebhookEventType}
        for event in request.events:
            if event not in valid_events:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid event type: {event}",
                )
    
    endpoint = service.update_endpoint(
        endpoint_id=endpoint_id,
        url=request.url,
        name=request.name,
        events=request.events,
        is_active=request.is_active,
    )
    
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")
    
    return EndpointResponse(
        id=endpoint.id,
        url=endpoint.url,
        name=endpoint.name,
        description=endpoint.description,
        events=endpoint.events,
        is_active=endpoint.is_active,
        created_at=endpoint.created_at,
        updated_at=endpoint.updated_at,
        total_deliveries=endpoint.total_deliveries,
        successful_deliveries=endpoint.successful_deliveries,
        failed_deliveries=endpoint.failed_deliveries,
        last_delivery_at=endpoint.last_delivery_at,
    )


@router.post(
    "/endpoints/{endpoint_id}/regenerate-secret",
    summary="Regenerate Endpoint Secret",
    description="Regenerate the signing secret for a webhook endpoint",
)
async def regenerate_secret(
    endpoint_id: str,
    service: WebhookService = Depends(get_webhook_service),
) -> Dict[str, Any]:
    """Regenerate endpoint secret."""
    new_secret = service.regenerate_secret(endpoint_id)
    
    if not new_secret:
        raise HTTPException(status_code=404, detail="Endpoint not found")
    
    return {
        "endpoint_id": endpoint_id,
        "secret": new_secret,
        "message": "Store this secret securely. It will not be shown again.",
        "regenerated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.delete(
    "/endpoints/{endpoint_id}",
    status_code=204,
    summary="Delete Webhook Endpoint",
    description="Delete a webhook endpoint",
)
async def delete_endpoint(
    endpoint_id: str,
    service: WebhookService = Depends(get_webhook_service),
) -> None:
    """Delete webhook endpoint."""
    success = service.delete_endpoint(endpoint_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Endpoint not found")


@router.post(
    "/endpoints/{endpoint_id}/test",
    response_model=DeliveryResponse,
    summary="Test Webhook Endpoint",
    description="Send a test event to a webhook endpoint",
)
async def test_endpoint(
    endpoint_id: str,
    request: TestWebhookRequest,
    service: WebhookService = Depends(get_webhook_service),
) -> DeliveryResponse:
    """Send test webhook to endpoint."""
    endpoint = service.get_endpoint(endpoint_id)
    
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")
    
    # Temporarily subscribe to test event if not subscribed
    original_events = endpoint.events.copy()
    if endpoint.events and request.event_type not in endpoint.events:
        endpoint.events.append(request.event_type)
    
    # Dispatch test event
    deliveries = await service.dispatch(
        event_type=request.event_type,
        data=request.data,
    )
    
    # Restore original events
    endpoint.events = original_events
    
    # Find delivery for this endpoint
    delivery = next((d for d in deliveries if d.endpoint_id == endpoint_id), None)
    
    if not delivery:
        raise HTTPException(status_code=500, detail="Test delivery failed")
    
    return _delivery_to_response(delivery)


# =============================================================================
# Delivery Tracking Endpoints
# =============================================================================

@router.get(
    "/deliveries",
    response_model=List[DeliveryResponse],
    summary="List Deliveries",
    description="List webhook deliveries with optional filtering",
)
async def list_deliveries(
    endpoint_id: Optional[str] = Query(None, description="Filter by endpoint"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(100, ge=1, le=1000),
    service: WebhookService = Depends(get_webhook_service),
) -> List[DeliveryResponse]:
    """List webhook deliveries."""
    status_enum = None
    if status:
        try:
            status_enum = DeliveryStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    
    deliveries = service.list_deliveries(
        endpoint_id=endpoint_id,
        status=status_enum,
        limit=limit,
    )
    
    return [_delivery_to_response(d) for d in deliveries]


@router.get(
    "/deliveries/{delivery_id}",
    response_model=DeliveryResponse,
    summary="Get Delivery Details",
    description="Get details of a specific webhook delivery",
)
async def get_delivery(
    delivery_id: str,
    service: WebhookService = Depends(get_webhook_service),
) -> DeliveryResponse:
    """Get delivery details."""
    delivery = service.get_delivery(delivery_id)
    
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")
    
    return _delivery_to_response(delivery)


@router.get(
    "/stats",
    response_model=DeliveryStatsResponse,
    summary="Get Delivery Statistics",
    description="Get webhook delivery statistics",
)
async def get_stats(
    endpoint_id: Optional[str] = Query(None, description="Filter by endpoint"),
    service: WebhookService = Depends(get_webhook_service),
) -> DeliveryStatsResponse:
    """Get delivery statistics."""
    stats = service.get_delivery_stats(endpoint_id=endpoint_id)
    
    return DeliveryStatsResponse(**stats)


@router.get(
    "/event-types",
    response_model=EventTypesResponse,
    summary="List Event Types",
    description="List all available webhook event types",
)
async def list_event_types() -> EventTypesResponse:
    """List available event types."""
    return EventTypesResponse(
        event_types=[e.value for e in WebhookEventType]
    )


# =============================================================================
# Helpers
# =============================================================================

def _delivery_to_response(delivery: WebhookDelivery) -> DeliveryResponse:
    """Convert delivery model to response."""
    return DeliveryResponse(
        id=delivery.id,
        endpoint_id=delivery.endpoint_id,
        endpoint_url=delivery.endpoint_url,
        event_type=delivery.event_type,
        status=delivery.status.value,
        created_at=delivery.created_at,
        completed_at=delivery.completed_at,
        attempt_count=delivery.attempt_count,
        attempts=[
            DeliveryAttemptResponse(
                id=a.id,
                attempt_number=a.attempt_number,
                attempted_at=a.attempted_at,
                completed_at=a.completed_at,
                duration_ms=a.duration_ms,
                status=a.status.value,
                response_code=a.response_code,
                error_message=a.error_message,
            )
            for a in delivery.attempts
        ],
    )

