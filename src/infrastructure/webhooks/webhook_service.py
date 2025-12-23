"""
Webhook Infrastructure Service

Provides reliable outbound webhook delivery with HMAC signature verification,
exponential backoff retry logic, and comprehensive delivery tracking.
"""

import asyncio
import hashlib
import hmac
import json
import logging
import secrets
import time
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
from uuid import uuid4

import httpx
from pydantic import BaseModel, Field, HttpUrl

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

class WebhookConfig(BaseModel):
    """Webhook service configuration."""
    
    # Delivery settings
    timeout_seconds: float = Field(default=30.0, description="Request timeout")
    max_payload_size: int = Field(default=1024 * 1024, description="Max payload size (1MB)")
    max_redirects: int = Field(default=0, description="Max redirects to follow")
    
    # Retry settings
    max_retries: int = Field(default=5, description="Max retry attempts")
    initial_retry_delay: float = Field(default=1.0, description="Initial delay in seconds")
    max_retry_delay: float = Field(default=300.0, description="Max delay (5 minutes)")
    retry_multiplier: float = Field(default=2.0, description="Exponential backoff multiplier")
    
    # Security
    signature_header: str = Field(default="X-Webhook-Signature", description="Signature header name")
    signature_algorithm: str = Field(default="sha256", description="HMAC algorithm")
    timestamp_header: str = Field(default="X-Webhook-Timestamp", description="Timestamp header")
    
    # Rate limiting
    max_concurrent_deliveries: int = Field(default=10, description="Max concurrent webhook deliveries")


# =============================================================================
# Enums
# =============================================================================

class WebhookEventType(str, Enum):
    """Available webhook event types."""
    
    # Employee events
    EMPLOYEE_CREATED = "employee.created"
    EMPLOYEE_UPDATED = "employee.updated"
    EMPLOYEE_DELETED = "employee.deleted"
    
    # Time-off events
    TIMEOFF_REQUESTED = "timeoff.requested"
    TIMEOFF_APPROVED = "timeoff.approved"
    TIMEOFF_DENIED = "timeoff.denied"
    TIMEOFF_CANCELLED = "timeoff.cancelled"
    
    # Organization events
    DEPARTMENT_CREATED = "department.created"
    DEPARTMENT_UPDATED = "department.updated"
    MANAGER_ASSIGNED = "manager.assigned"
    
    # System events
    IMPORT_COMPLETED = "import.completed"
    EXPORT_COMPLETED = "export.completed"


class DeliveryStatus(str, Enum):
    """Webhook delivery status."""
    
    PENDING = "pending"
    DELIVERING = "delivering"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"


# =============================================================================
# Models
# =============================================================================

class WebhookEndpoint(BaseModel):
    """Registered webhook endpoint."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    url: str
    secret: str
    name: str
    description: Optional[str] = None
    
    # Event filtering
    events: List[str] = Field(default_factory=list)  # Empty = all events
    
    # Status
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = None
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Stats
    total_deliveries: int = 0
    successful_deliveries: int = 0
    failed_deliveries: int = 0
    last_delivery_at: Optional[datetime] = None


class WebhookPayload(BaseModel):
    """Webhook event payload."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    data: Dict[str, Any]
    
    # Metadata
    version: str = "1.0"
    source: str = "embi"


class DeliveryAttempt(BaseModel):
    """Record of a webhook delivery attempt."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    webhook_id: str
    endpoint_id: str
    payload_id: str
    
    # Timing
    attempt_number: int
    attempted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    
    # Result
    status: DeliveryStatus
    response_code: Optional[int] = None
    response_body: Optional[str] = None
    error_message: Optional[str] = None
    
    # Next retry
    next_retry_at: Optional[datetime] = None


class WebhookDelivery(BaseModel):
    """Complete webhook delivery record."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    endpoint_id: str
    endpoint_url: str
    
    # Payload
    event_type: str
    payload: WebhookPayload
    
    # Status
    status: DeliveryStatus = DeliveryStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    
    # Attempts
    attempt_count: int = 0
    max_attempts: int = 5
    attempts: List[DeliveryAttempt] = Field(default_factory=list)
    
    # Next action
    next_retry_at: Optional[datetime] = None


# =============================================================================
# Signature Generator
# =============================================================================

class WebhookSignature:
    """HMAC signature generation and verification for webhooks."""
    
    def __init__(self, algorithm: str = "sha256"):
        self.algorithm = algorithm
    
    def generate(
        self,
        payload: str,
        secret: str,
        timestamp: Optional[int] = None,
    ) -> str:
        """
        Generate HMAC signature for payload.
        
        Signature format: t={timestamp},v1={signature}
        """
        if timestamp is None:
            timestamp = int(time.time())
        
        # Create signed payload
        signed_payload = f"{timestamp}.{payload}"
        
        # Compute HMAC
        signature = hmac.new(
            secret.encode(),
            signed_payload.encode(),
            hashlib.sha256 if self.algorithm == "sha256" else hashlib.sha512,
        ).hexdigest()
        
        return f"t={timestamp},v1={signature}"
    
    def verify(
        self,
        payload: str,
        signature_header: str,
        secret: str,
        tolerance_seconds: int = 300,
    ) -> bool:
        """
        Verify webhook signature.
        
        Returns True if signature is valid and within time tolerance.
        """
        try:
            # Parse signature header
            parts = dict(p.split("=") for p in signature_header.split(","))
            timestamp = int(parts.get("t", 0))
            received_signature = parts.get("v1", "")
            
            # Check timestamp tolerance
            current_time = int(time.time())
            if abs(current_time - timestamp) > tolerance_seconds:
                return False
            
            # Compute expected signature
            expected = self.generate(payload, secret, timestamp)
            expected_signature = expected.split(",")[1].split("=")[1]
            
            # Constant-time comparison
            return hmac.compare_digest(expected_signature, received_signature)
            
        except Exception:
            return False


# =============================================================================
# Delivery Engine
# =============================================================================

class WebhookDeliveryEngine:
    """
    Async webhook delivery engine with retry logic.
    
    Features:
    - Exponential backoff for failed deliveries
    - Concurrent delivery with rate limiting
    - Timeout and redirect protection
    - Comprehensive logging
    """
    
    def __init__(self, config: Optional[WebhookConfig] = None):
        self.config = config or WebhookConfig()
        self.signature = WebhookSignature(self.config.signature_algorithm)
        self._semaphore = asyncio.Semaphore(self.config.max_concurrent_deliveries)
        self._http_client: Optional[httpx.AsyncClient] = None
    
    async def get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=self.config.timeout_seconds,
                follow_redirects=self.config.max_redirects > 0,
                max_redirects=self.config.max_redirects,
            )
        return self._http_client
    
    async def close(self) -> None:
        """Close HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
    
    async def deliver(
        self,
        endpoint: WebhookEndpoint,
        payload: WebhookPayload,
    ) -> WebhookDelivery:
        """
        Deliver a webhook with retry logic.
        
        Returns complete delivery record with all attempts.
        """
        delivery = WebhookDelivery(
            endpoint_id=endpoint.id,
            endpoint_url=endpoint.url,
            event_type=payload.event_type,
            payload=payload,
            max_attempts=self.config.max_retries + 1,
        )
        
        # Serialize payload
        payload_json = payload.model_dump_json()
        
        # Check payload size
        if len(payload_json) > self.config.max_payload_size:
            delivery.status = DeliveryStatus.FAILED
            delivery.attempts.append(DeliveryAttempt(
                webhook_id=delivery.id,
                endpoint_id=endpoint.id,
                payload_id=payload.id,
                attempt_number=1,
                status=DeliveryStatus.FAILED,
                error_message=f"Payload size ({len(payload_json)}) exceeds limit ({self.config.max_payload_size})",
            ))
            return delivery
        
        # Attempt delivery with retries
        for attempt in range(delivery.max_attempts):
            delivery.attempt_count = attempt + 1
            
            attempt_result = await self._attempt_delivery(
                endpoint=endpoint,
                payload_json=payload_json,
                attempt_number=attempt + 1,
                delivery_id=delivery.id,
                payload_id=payload.id,
            )
            
            delivery.attempts.append(attempt_result)
            
            if attempt_result.status == DeliveryStatus.DELIVERED:
                delivery.status = DeliveryStatus.DELIVERED
                delivery.completed_at = datetime.now(timezone.utc)
                break
            
            # Calculate next retry delay
            if attempt < delivery.max_attempts - 1:
                delay = self._calculate_retry_delay(attempt)
                delivery.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
                delivery.status = DeliveryStatus.RETRYING
                
                logger.info(
                    f"Webhook delivery failed, retrying in {delay}s "
                    f"(attempt {attempt + 1}/{delivery.max_attempts})"
                )
                
                await asyncio.sleep(delay)
            else:
                delivery.status = DeliveryStatus.FAILED
                delivery.completed_at = datetime.now(timezone.utc)
        
        return delivery
    
    async def _attempt_delivery(
        self,
        endpoint: WebhookEndpoint,
        payload_json: str,
        attempt_number: int,
        delivery_id: str,
        payload_id: str,
    ) -> DeliveryAttempt:
        """Make a single delivery attempt."""
        attempt = DeliveryAttempt(
            webhook_id=delivery_id,
            endpoint_id=endpoint.id,
            payload_id=payload_id,
            attempt_number=attempt_number,
            status=DeliveryStatus.DELIVERING,
        )
        
        start_time = time.time()
        
        try:
            async with self._semaphore:
                client = await self.get_client()
                
                # Generate signature
                timestamp = int(time.time())
                signature = self.signature.generate(payload_json, endpoint.secret, timestamp)
                
                # Prepare headers
                headers = {
                    "Content-Type": "application/json",
                    self.config.signature_header: signature,
                    self.config.timestamp_header: str(timestamp),
                    "User-Agent": "EMBI-Webhook/1.0",
                    "X-Webhook-ID": delivery_id,
                    "X-Delivery-Attempt": str(attempt_number),
                }
                
                # Send request
                response = await client.post(
                    endpoint.url,
                    content=payload_json,
                    headers=headers,
                )
                
                attempt.response_code = response.status_code
                attempt.response_body = response.text[:500] if response.text else None
                
                # Check for success (2xx status codes)
                if 200 <= response.status_code < 300:
                    attempt.status = DeliveryStatus.DELIVERED
                else:
                    attempt.status = DeliveryStatus.FAILED
                    attempt.error_message = f"HTTP {response.status_code}: {response.reason_phrase}"
                
        except httpx.TimeoutException as e:
            attempt.status = DeliveryStatus.FAILED
            attempt.error_message = f"Timeout: {str(e)}"
            
        except httpx.TooManyRedirects:
            attempt.status = DeliveryStatus.FAILED
            attempt.error_message = "Too many redirects"
            
        except httpx.RequestError as e:
            attempt.status = DeliveryStatus.FAILED
            attempt.error_message = f"Request error: {str(e)}"
            
        except Exception as e:
            attempt.status = DeliveryStatus.FAILED
            attempt.error_message = f"Unexpected error: {str(e)}"
            logger.exception(f"Webhook delivery error: {str(e)}")
        
        finally:
            attempt.completed_at = datetime.now(timezone.utc)
            attempt.duration_ms = int((time.time() - start_time) * 1000)
        
        return attempt
    
    def _calculate_retry_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay."""
        delay = self.config.initial_retry_delay * (self.config.retry_multiplier ** attempt)
        return min(delay, self.config.max_retry_delay)


# =============================================================================
# Webhook Service
# =============================================================================

class WebhookService:
    """
    Complete webhook management service.
    
    Features:
    - Endpoint registration and management
    - Event filtering per endpoint
    - Delivery tracking and history
    - Secret management
    """
    
    def __init__(
        self,
        config: Optional[WebhookConfig] = None,
        delivery_engine: Optional[WebhookDeliveryEngine] = None,
    ):
        self.config = config or WebhookConfig()
        self.delivery_engine = delivery_engine or WebhookDeliveryEngine(self.config)
        
        # In-memory storage (replace with database in production)
        self._endpoints: Dict[str, WebhookEndpoint] = {}
        self._deliveries: Dict[str, WebhookDelivery] = {}
    
    # =========================================================================
    # Endpoint Management
    # =========================================================================
    
    def register_endpoint(
        self,
        url: str,
        name: str,
        events: Optional[List[str]] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> WebhookEndpoint:
        """
        Register a new webhook endpoint.
        
        Returns endpoint with generated secret.
        """
        # Validate URL
        if not url.startswith("https://"):
            logger.warning(f"Webhook endpoint using non-HTTPS URL: {url}")
        
        # Generate secret
        secret = secrets.token_urlsafe(32)
        
        endpoint = WebhookEndpoint(
            url=url,
            secret=secret,
            name=name,
            description=description,
            events=events or [],
            metadata=metadata or {},
        )
        
        self._endpoints[endpoint.id] = endpoint
        
        logger.info(f"Registered webhook endpoint: {endpoint.id} -> {url}")
        
        return endpoint
    
    def get_endpoint(self, endpoint_id: str) -> Optional[WebhookEndpoint]:
        """Get endpoint by ID."""
        return self._endpoints.get(endpoint_id)
    
    def list_endpoints(self, active_only: bool = True) -> List[WebhookEndpoint]:
        """List all endpoints."""
        endpoints = list(self._endpoints.values())
        if active_only:
            endpoints = [e for e in endpoints if e.is_active]
        return endpoints
    
    def update_endpoint(
        self,
        endpoint_id: str,
        url: Optional[str] = None,
        name: Optional[str] = None,
        events: Optional[List[str]] = None,
        is_active: Optional[bool] = None,
    ) -> Optional[WebhookEndpoint]:
        """Update endpoint configuration."""
        endpoint = self._endpoints.get(endpoint_id)
        if not endpoint:
            return None
        
        if url is not None:
            endpoint.url = url
        if name is not None:
            endpoint.name = name
        if events is not None:
            endpoint.events = events
        if is_active is not None:
            endpoint.is_active = is_active
        
        endpoint.updated_at = datetime.now(timezone.utc)
        
        return endpoint
    
    def regenerate_secret(self, endpoint_id: str) -> Optional[str]:
        """Regenerate endpoint secret."""
        endpoint = self._endpoints.get(endpoint_id)
        if not endpoint:
            return None
        
        new_secret = secrets.token_urlsafe(32)
        endpoint.secret = new_secret
        endpoint.updated_at = datetime.now(timezone.utc)
        
        return new_secret
    
    def delete_endpoint(self, endpoint_id: str) -> bool:
        """Delete an endpoint."""
        if endpoint_id in self._endpoints:
            del self._endpoints[endpoint_id]
            return True
        return False
    
    # =========================================================================
    # Event Dispatch
    # =========================================================================
    
    async def dispatch(
        self,
        event_type: str,
        data: Dict[str, Any],
    ) -> List[WebhookDelivery]:
        """
        Dispatch an event to all subscribed endpoints.
        
        Returns list of delivery records.
        """
        payload = WebhookPayload(
            event_type=event_type,
            data=data,
        )
        
        # Find subscribed endpoints
        endpoints = self._get_subscribed_endpoints(event_type)
        
        if not endpoints:
            logger.debug(f"No endpoints subscribed to event: {event_type}")
            return []
        
        # Deliver to all endpoints concurrently
        deliveries = await asyncio.gather(*[
            self._deliver_to_endpoint(endpoint, payload)
            for endpoint in endpoints
        ])
        
        # Update endpoint stats
        for delivery in deliveries:
            self._update_endpoint_stats(delivery)
        
        return list(deliveries)
    
    async def _deliver_to_endpoint(
        self,
        endpoint: WebhookEndpoint,
        payload: WebhookPayload,
    ) -> WebhookDelivery:
        """Deliver payload to a single endpoint."""
        delivery = await self.delivery_engine.deliver(endpoint, payload)
        self._deliveries[delivery.id] = delivery
        return delivery
    
    def _get_subscribed_endpoints(self, event_type: str) -> List[WebhookEndpoint]:
        """Get endpoints subscribed to an event type."""
        endpoints = []
        
        for endpoint in self._endpoints.values():
            if not endpoint.is_active:
                continue
            
            # Empty events list means subscribed to all events
            if not endpoint.events or event_type in endpoint.events:
                endpoints.append(endpoint)
        
        return endpoints
    
    def _update_endpoint_stats(self, delivery: WebhookDelivery) -> None:
        """Update endpoint delivery statistics."""
        endpoint = self._endpoints.get(delivery.endpoint_id)
        if not endpoint:
            return
        
        endpoint.total_deliveries += 1
        endpoint.last_delivery_at = datetime.now(timezone.utc)
        
        if delivery.status == DeliveryStatus.DELIVERED:
            endpoint.successful_deliveries += 1
        else:
            endpoint.failed_deliveries += 1
    
    # =========================================================================
    # Delivery Tracking
    # =========================================================================
    
    def get_delivery(self, delivery_id: str) -> Optional[WebhookDelivery]:
        """Get delivery by ID."""
        return self._deliveries.get(delivery_id)
    
    def list_deliveries(
        self,
        endpoint_id: Optional[str] = None,
        status: Optional[DeliveryStatus] = None,
        limit: int = 100,
    ) -> List[WebhookDelivery]:
        """List deliveries with optional filtering."""
        deliveries = list(self._deliveries.values())
        
        if endpoint_id:
            deliveries = [d for d in deliveries if d.endpoint_id == endpoint_id]
        
        if status:
            deliveries = [d for d in deliveries if d.status == status]
        
        # Sort by creation time, newest first
        deliveries.sort(key=lambda d: d.created_at, reverse=True)
        
        return deliveries[:limit]
    
    def get_delivery_stats(self, endpoint_id: Optional[str] = None) -> Dict[str, Any]:
        """Get delivery statistics."""
        deliveries = list(self._deliveries.values())
        
        if endpoint_id:
            deliveries = [d for d in deliveries if d.endpoint_id == endpoint_id]
        
        total = len(deliveries)
        delivered = sum(1 for d in deliveries if d.status == DeliveryStatus.DELIVERED)
        failed = sum(1 for d in deliveries if d.status == DeliveryStatus.FAILED)
        pending = sum(1 for d in deliveries if d.status in [DeliveryStatus.PENDING, DeliveryStatus.RETRYING])
        
        return {
            "total": total,
            "delivered": delivered,
            "failed": failed,
            "pending": pending,
            "success_rate": round(delivered / total * 100, 2) if total > 0 else 0,
        }
    
    async def close(self) -> None:
        """Close the service and cleanup resources."""
        await self.delivery_engine.close()


# =============================================================================
# Singleton
# =============================================================================

_webhook_service: Optional[WebhookService] = None


def get_webhook_service() -> WebhookService:
    """Get the webhook service singleton."""
    global _webhook_service
    if _webhook_service is None:
        _webhook_service = WebhookService()
    return _webhook_service

