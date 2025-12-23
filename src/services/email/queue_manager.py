"""Email queue manager for high-volume sending with retry logic."""

import asyncio
import logging
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import threading

from src.services.email.providers.base import (
    EmailMessage,
    DeliveryResult,
    DeliveryStatus,
    EmailProvider,
)

logger = logging.getLogger(__name__)


class QueuePriority(int, Enum):
    """Email queue priority levels."""
    LOW = 1
    NORMAL = 5
    HIGH = 10
    CRITICAL = 100


class QueuedEmailStatus(str, Enum):
    """Status of a queued email."""
    PENDING = "pending"
    PROCESSING = "processing"
    SENT = "sent"
    FAILED = "failed"
    RETRY_SCHEDULED = "retry_scheduled"
    MAX_RETRIES_EXCEEDED = "max_retries_exceeded"


@dataclass
class QueuedEmail:
    """Represents an email in the queue."""
    id: str
    message: EmailMessage
    priority: QueuePriority = QueuePriority.NORMAL
    status: QueuedEmailStatus = QueuedEmailStatus.PENDING
    retry_count: int = 0
    max_retries: int = 3
    scheduled_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_attempt_at: Optional[datetime] = None
    next_retry_at: Optional[datetime] = None
    error_message: Optional[str] = None
    delivery_result: Optional[DeliveryResult] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __lt__(self, other: "QueuedEmail") -> bool:
        # Higher priority first, then earlier created
        if self.priority != other.priority:
            return self.priority > other.priority
        return self.created_at < other.created_at


@dataclass
class QueueConfig:
    """Email queue configuration."""
    max_concurrent: int = 10
    rate_limit_per_second: float = 10.0
    max_retries: int = 3
    retry_delay_base: int = 60  # Base delay in seconds
    retry_delay_multiplier: float = 2.0  # Exponential backoff
    max_retry_delay: int = 3600  # Max 1 hour
    batch_size: int = 100
    cleanup_interval: int = 3600  # Cleanup old entries every hour
    retention_days: int = 7  # Keep completed emails for 7 days


class RateLimiter:
    """Token bucket rate limiter."""
    
    def __init__(self, rate: float, capacity: float = None):
        self.rate = rate
        self.capacity = capacity or rate
        self.tokens = self.capacity
        self.last_update = time.monotonic()
        self._lock = threading.Lock()
    
    def acquire(self, tokens: int = 1) -> float:
        """
        Acquire tokens, returning wait time if needed.
        
        Returns:
            Time to wait before tokens available (0 if immediate)
        """
        with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_update = now
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return 0.0
            
            wait_time = (tokens - self.tokens) / self.rate
            return wait_time
    
    async def wait_for_token(self, tokens: int = 1) -> None:
        """Wait until tokens are available."""
        wait_time = self.acquire(tokens)
        if wait_time > 0:
            await asyncio.sleep(wait_time)
            self.acquire(tokens)


class EmailQueueManager:
    """
    Manages email queue with rate limiting, retry logic, and batch processing.
    
    Features:
    - Priority-based queuing
    - Rate limiting with token bucket
    - Exponential backoff for retries
    - Concurrent sending with configurable limits
    - Status tracking and callbacks
    """
    
    def __init__(
        self,
        provider: EmailProvider,
        config: Optional[QueueConfig] = None
    ):
        """
        Initialize the queue manager.
        
        Args:
            provider: Email provider to use for sending
            config: Queue configuration
        """
        self.provider = provider
        self.config = config or QueueConfig()
        
        self._queue: deque = deque()
        self._processing: Dict[str, QueuedEmail] = {}
        self._completed: Dict[str, QueuedEmail] = {}
        self._lock = threading.Lock()
        self._rate_limiter = RateLimiter(self.config.rate_limit_per_second)
        
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None
        self._callbacks: Dict[str, List[Callable]] = {
            "sent": [],
            "failed": [],
            "retry": [],
        }
    
    def enqueue(
        self,
        message: EmailMessage,
        priority: QueuePriority = QueuePriority.NORMAL,
        scheduled_at: Optional[datetime] = None,
        max_retries: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Add an email to the queue.
        
        Args:
            message: Email message to send
            priority: Queue priority
            scheduled_at: Schedule for later sending
            max_retries: Override default max retries
            metadata: Additional metadata to store
            
        Returns:
            Queue ID for tracking
        """
        queue_id = str(uuid.uuid4())
        
        queued_email = QueuedEmail(
            id=queue_id,
            message=message,
            priority=priority,
            scheduled_at=scheduled_at,
            max_retries=max_retries or self.config.max_retries,
            metadata=metadata or {},
        )
        
        with self._lock:
            self._queue.append(queued_email)
            # Sort by priority
            self._queue = deque(sorted(self._queue))
        
        logger.info(f"Email queued: {queue_id} (priority: {priority.name})")
        return queue_id
    
    def enqueue_batch(
        self,
        messages: List[EmailMessage],
        priority: QueuePriority = QueuePriority.NORMAL
    ) -> List[str]:
        """
        Add multiple emails to the queue.
        
        Args:
            messages: List of email messages
            priority: Queue priority for all messages
            
        Returns:
            List of queue IDs
        """
        queue_ids = []
        for message in messages:
            queue_id = self.enqueue(message, priority)
            queue_ids.append(queue_id)
        return queue_ids
    
    def get_status(self, queue_id: str) -> Optional[QueuedEmail]:
        """
        Get the status of a queued email.
        
        Args:
            queue_id: Queue ID
            
        Returns:
            QueuedEmail or None if not found
        """
        with self._lock:
            # Check processing
            if queue_id in self._processing:
                return self._processing[queue_id]
            
            # Check completed
            if queue_id in self._completed:
                return self._completed[queue_id]
            
            # Check queue
            for email in self._queue:
                if email.id == queue_id:
                    return email
        
        return None
    
    def cancel(self, queue_id: str) -> bool:
        """
        Cancel a queued email.
        
        Args:
            queue_id: Queue ID to cancel
            
        Returns:
            True if cancelled, False if not found or already processing
        """
        with self._lock:
            for i, email in enumerate(self._queue):
                if email.id == queue_id:
                    del self._queue[i]
                    logger.info(f"Email cancelled: {queue_id}")
                    return True
        return False
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        with self._lock:
            pending = len(self._queue)
            processing = len(self._processing)
            
            # Count by status in completed
            sent = sum(1 for e in self._completed.values() if e.status == QueuedEmailStatus.SENT)
            failed = sum(1 for e in self._completed.values() if e.status in (
                QueuedEmailStatus.FAILED, QueuedEmailStatus.MAX_RETRIES_EXCEEDED
            ))
            
            # Count retries scheduled
            retry_scheduled = sum(1 for e in self._queue if e.status == QueuedEmailStatus.RETRY_SCHEDULED)
        
        return {
            "pending": pending,
            "processing": processing,
            "sent": sent,
            "failed": failed,
            "retry_scheduled": retry_scheduled,
            "total_completed": len(self._completed),
            "is_running": self._running,
        }
    
    def on_sent(self, callback: Callable[[QueuedEmail], None]) -> None:
        """Register callback for successful sends."""
        self._callbacks["sent"].append(callback)
    
    def on_failed(self, callback: Callable[[QueuedEmail], None]) -> None:
        """Register callback for failed sends."""
        self._callbacks["failed"].append(callback)
    
    def on_retry(self, callback: Callable[[QueuedEmail], None]) -> None:
        """Register callback for retry attempts."""
        self._callbacks["retry"].append(callback)
    
    async def start(self) -> None:
        """Start the queue processor."""
        if self._running:
            return
        
        self._running = True
        self._worker_task = asyncio.create_task(self._process_loop())
        logger.info("Email queue processor started")
    
    async def stop(self, wait: bool = True) -> None:
        """
        Stop the queue processor.
        
        Args:
            wait: Wait for current processing to complete
        """
        self._running = False
        
        if self._worker_task and wait:
            try:
                await asyncio.wait_for(self._worker_task, timeout=30)
            except asyncio.TimeoutError:
                self._worker_task.cancel()
        
        logger.info("Email queue processor stopped")
    
    async def _process_loop(self) -> None:
        """Main processing loop."""
        while self._running:
            try:
                # Get next batch
                batch = self._get_next_batch()
                
                if not batch:
                    await asyncio.sleep(0.1)
                    continue
                
                # Process batch concurrently
                tasks = []
                for email in batch:
                    task = asyncio.create_task(self._process_email(email))
                    tasks.append(task)
                
                await asyncio.gather(*tasks, return_exceptions=True)
                
            except Exception as e:
                logger.exception(f"Queue processing error: {e}")
                await asyncio.sleep(1)
    
    def _get_next_batch(self) -> List[QueuedEmail]:
        """Get next batch of emails to process."""
        batch = []
        now = datetime.utcnow()
        
        with self._lock:
            # Don't exceed concurrent limit
            available_slots = self.config.max_concurrent - len(self._processing)
            if available_slots <= 0:
                return []
            
            items_to_remove = []
            
            for i, email in enumerate(self._queue):
                if len(batch) >= min(available_slots, self.config.batch_size):
                    break
                
                # Skip if scheduled for later
                if email.scheduled_at and email.scheduled_at > now:
                    continue
                
                # Skip if retry not yet due
                if email.next_retry_at and email.next_retry_at > now:
                    continue
                
                # Move to processing
                email.status = QueuedEmailStatus.PROCESSING
                self._processing[email.id] = email
                batch.append(email)
                items_to_remove.append(i)
            
            # Remove from queue (reverse order to maintain indices)
            for i in reversed(items_to_remove):
                del self._queue[i]
        
        return batch
    
    async def _process_email(self, email: QueuedEmail) -> None:
        """Process a single email."""
        try:
            # Apply rate limiting
            await self._rate_limiter.wait_for_token()
            
            email.last_attempt_at = datetime.utcnow()
            
            # Send via provider
            result = await self.provider.send(email.message)
            email.delivery_result = result
            
            if result.success:
                email.status = QueuedEmailStatus.SENT
                self._trigger_callbacks("sent", email)
                logger.info(f"Email sent: {email.id} (message_id: {result.message_id})")
            else:
                await self._handle_failure(email, result.error_message)
                
        except Exception as e:
            logger.exception(f"Email processing error: {email.id}")
            await self._handle_failure(email, str(e))
        
        finally:
            # Move to completed
            with self._lock:
                self._processing.pop(email.id, None)
                self._completed[email.id] = email
    
    async def _handle_failure(self, email: QueuedEmail, error_message: str) -> None:
        """Handle email send failure."""
        email.error_message = error_message
        email.retry_count += 1
        
        if email.retry_count < email.max_retries:
            # Schedule retry with exponential backoff
            delay = min(
                self.config.retry_delay_base * (self.config.retry_delay_multiplier ** email.retry_count),
                self.config.max_retry_delay
            )
            email.next_retry_at = datetime.utcnow() + timedelta(seconds=delay)
            email.status = QueuedEmailStatus.RETRY_SCHEDULED
            
            # Re-queue
            with self._lock:
                self._processing.pop(email.id, None)
                self._queue.append(email)
            
            self._trigger_callbacks("retry", email)
            logger.warning(
                f"Email retry scheduled: {email.id} "
                f"(attempt {email.retry_count}, delay {delay}s)"
            )
        else:
            email.status = QueuedEmailStatus.MAX_RETRIES_EXCEEDED
            self._trigger_callbacks("failed", email)
            logger.error(f"Email failed after max retries: {email.id}")
    
    def _trigger_callbacks(self, event: str, email: QueuedEmail) -> None:
        """Trigger registered callbacks."""
        for callback in self._callbacks.get(event, []):
            try:
                callback(email)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    def cleanup_old_entries(self) -> int:
        """
        Clean up old completed entries.
        
        Returns:
            Number of entries cleaned up
        """
        cutoff = datetime.utcnow() - timedelta(days=self.config.retention_days)
        count = 0
        
        with self._lock:
            to_remove = [
                id for id, email in self._completed.items()
                if email.created_at < cutoff
            ]
            for id in to_remove:
                del self._completed[id]
                count += 1
        
        if count:
            logger.info(f"Cleaned up {count} old queue entries")
        
        return count

