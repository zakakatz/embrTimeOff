"""
Celery Configuration with Redis Broker

Configures Celery for background task processing with Redis as the
message broker and result backend. Includes dead letter queue handling.
"""

import os
from datetime import timedelta
from typing import Any, Dict, List, Optional

try:
    from celery import Celery
    from celery.signals import task_failure, task_success, task_retry
    from kombu import Exchange, Queue
except ImportError:
    Celery = None
    task_failure = None
    task_success = None
    task_retry = None
    Exchange = None
    Queue = None

import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

class CeleryConfig:
    """Celery configuration settings."""
    
    # Broker settings
    broker_url: str = os.environ.get(
        "CELERY_BROKER_URL",
        os.environ.get("REDIS_URL", "redis://localhost:6379/1")
    )
    
    # Result backend
    result_backend: str = os.environ.get(
        "CELERY_RESULT_BACKEND",
        os.environ.get("REDIS_URL", "redis://localhost:6379/2")
    )
    
    # Serialization
    task_serializer: str = "json"
    result_serializer: str = "json"
    accept_content: List[str] = ["json"]
    
    # Timezone
    timezone: str = "UTC"
    enable_utc: bool = True
    
    # Task settings
    task_acks_late: bool = True
    task_reject_on_worker_lost: bool = True
    task_default_queue: str = "default"
    
    # Worker settings
    worker_prefetch_multiplier: int = 1
    worker_concurrency: int = int(os.environ.get("CELERY_CONCURRENCY", "4"))
    
    # Result settings
    result_expires: int = 3600  # 1 hour
    result_extended: bool = True
    
    # Task execution limits
    task_soft_time_limit: int = 300  # 5 minutes
    task_time_limit: int = 600  # 10 minutes
    
    # Retry settings
    task_default_retry_delay: int = 60  # 1 minute
    task_max_retries: int = 3
    
    # Rate limiting
    task_annotations: Dict[str, Any] = {
        "*": {
            "rate_limit": "100/m",  # 100 tasks per minute
        },
    }
    
    # Beat schedule
    beat_schedule: Dict[str, Any] = {}


# =============================================================================
# Queue Definitions
# =============================================================================

# Define exchanges
default_exchange = Exchange("default", type="direct") if Exchange else None
dlq_exchange = Exchange("dlq", type="direct") if Exchange else None

# Define queues with dead letter routing
CELERY_QUEUES = []

if Queue:
    CELERY_QUEUES = [
        # Default queue
        Queue(
            "default",
            default_exchange,
            routing_key="default",
            queue_arguments={
                "x-dead-letter-exchange": "dlq",
                "x-dead-letter-routing-key": "dlq.default",
            },
        ),
        
        # High priority queue
        Queue(
            "high_priority",
            default_exchange,
            routing_key="high_priority",
            queue_arguments={
                "x-dead-letter-exchange": "dlq",
                "x-dead-letter-routing-key": "dlq.high_priority",
            },
        ),
        
        # Balance calculation queue
        Queue(
            "balance_calc",
            default_exchange,
            routing_key="balance_calc",
            queue_arguments={
                "x-dead-letter-exchange": "dlq",
                "x-dead-letter-routing-key": "dlq.balance_calc",
            },
        ),
        
        # Email notifications queue
        Queue(
            "notifications",
            default_exchange,
            routing_key="notifications",
            queue_arguments={
                "x-dead-letter-exchange": "dlq",
                "x-dead-letter-routing-key": "dlq.notifications",
            },
        ),
        
        # Import processing queue
        Queue(
            "imports",
            default_exchange,
            routing_key="imports",
            queue_arguments={
                "x-dead-letter-exchange": "dlq",
                "x-dead-letter-routing-key": "dlq.imports",
            },
        ),
        
        # Dead letter queues
        Queue("dlq.default", dlq_exchange, routing_key="dlq.default"),
        Queue("dlq.high_priority", dlq_exchange, routing_key="dlq.high_priority"),
        Queue("dlq.balance_calc", dlq_exchange, routing_key="dlq.balance_calc"),
        Queue("dlq.notifications", dlq_exchange, routing_key="dlq.notifications"),
        Queue("dlq.imports", dlq_exchange, routing_key="dlq.imports"),
    ]

# Task routing
CELERY_TASK_ROUTES = {
    # Balance tasks
    "tasks.calculate_balance": {"queue": "balance_calc"},
    "tasks.refresh_balance_cache": {"queue": "balance_calc"},
    "tasks.calculate_projections": {"queue": "balance_calc"},
    
    # Notification tasks
    "tasks.send_email": {"queue": "notifications"},
    "tasks.send_notification": {"queue": "notifications"},
    
    # Import tasks
    "tasks.process_import": {"queue": "imports"},
    "tasks.validate_import": {"queue": "imports"},
    
    # High priority tasks
    "tasks.urgent_*": {"queue": "high_priority"},
}


# =============================================================================
# Celery Application Factory
# =============================================================================

def create_celery_app(
    name: str = "embi",
    config: Optional[CeleryConfig] = None,
) -> Optional[Any]:
    """
    Create and configure Celery application.
    
    Args:
        name: Application name
        config: Optional configuration override
    
    Returns:
        Configured Celery application or None if Celery not installed
    """
    if Celery is None:
        logger.warning("Celery not installed - background tasks disabled")
        return None
    
    config = config or CeleryConfig()
    
    app = Celery(name)
    
    # Apply configuration
    app.conf.update(
        broker_url=config.broker_url,
        result_backend=config.result_backend,
        task_serializer=config.task_serializer,
        result_serializer=config.result_serializer,
        accept_content=config.accept_content,
        timezone=config.timezone,
        enable_utc=config.enable_utc,
        task_acks_late=config.task_acks_late,
        task_reject_on_worker_lost=config.task_reject_on_worker_lost,
        task_default_queue=config.task_default_queue,
        worker_prefetch_multiplier=config.worker_prefetch_multiplier,
        worker_concurrency=config.worker_concurrency,
        result_expires=config.result_expires,
        result_extended=config.result_extended,
        task_soft_time_limit=config.task_soft_time_limit,
        task_time_limit=config.task_time_limit,
        task_default_retry_delay=config.task_default_retry_delay,
        task_annotations=config.task_annotations,
        beat_schedule=config.beat_schedule,
        task_queues=CELERY_QUEUES,
        task_routes=CELERY_TASK_ROUTES,
    )
    
    # Register signal handlers
    _register_signal_handlers(app)
    
    logger.info(f"Celery app '{name}' configured with broker: {config.broker_url}")
    
    return app


def _register_signal_handlers(app: Any) -> None:
    """Register Celery signal handlers for monitoring."""
    
    if task_failure:
        @task_failure.connect
        def handle_task_failure(sender=None, task_id=None, exception=None, **kwargs):
            """Handle task failure - log and optionally alert."""
            logger.error(
                f"Task {sender.name}[{task_id}] failed: {str(exception)}",
                extra={
                    "task_name": sender.name,
                    "task_id": task_id,
                    "exception": str(exception),
                },
            )
    
    if task_success:
        @task_success.connect
        def handle_task_success(sender=None, result=None, **kwargs):
            """Handle task success - log for monitoring."""
            logger.debug(f"Task {sender.name} completed successfully")
    
    if task_retry:
        @task_retry.connect
        def handle_task_retry(sender=None, reason=None, **kwargs):
            """Handle task retry - log for monitoring."""
            logger.warning(
                f"Task {sender.name} retrying: {reason}",
                extra={"task_name": sender.name, "retry_reason": reason},
            )


# =============================================================================
# Dead Letter Queue Handler
# =============================================================================

class DeadLetterQueueHandler:
    """
    Handles messages that failed processing and were routed to DLQ.
    
    Features:
    - Inspect failed messages
    - Replay messages after fixing issues
    - Archive or delete old failures
    """
    
    def __init__(self, app: Optional[Any] = None):
        self.app = app
    
    def get_dlq_messages(
        self,
        queue_name: str = "dlq.default",
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get messages from a dead letter queue."""
        if not self.app:
            return []
        
        messages = []
        
        try:
            with self.app.connection_for_read() as conn:
                simple_queue = conn.SimpleQueue(queue_name)
                
                for _ in range(min(limit, simple_queue.qsize())):
                    message = simple_queue.get(block=False)
                    if message:
                        messages.append({
                            "body": message.body,
                            "properties": message.properties,
                            "delivery_info": message.delivery_info,
                        })
                        message.requeue()  # Put it back for now
                
        except Exception as e:
            logger.error(f"Error reading DLQ: {str(e)}")
        
        return messages
    
    def replay_message(
        self,
        message_id: str,
        source_queue: str = "dlq.default",
        target_queue: str = "default",
    ) -> bool:
        """Replay a message from DLQ to original queue."""
        if not self.app:
            return False
        
        try:
            with self.app.connection_for_write() as conn:
                # This is a simplified implementation
                # In production, you'd want proper message handling
                producer = conn.Producer()
                producer.publish(
                    {"replayed": True, "original_message_id": message_id},
                    exchange="",
                    routing_key=target_queue,
                )
            return True
            
        except Exception as e:
            logger.error(f"Error replaying message: {str(e)}")
            return False
    
    def get_dlq_stats(self) -> Dict[str, int]:
        """Get statistics for all DLQs."""
        stats = {}
        dlq_names = [
            "dlq.default",
            "dlq.high_priority",
            "dlq.balance_calc",
            "dlq.notifications",
            "dlq.imports",
        ]
        
        if not self.app:
            return {name: 0 for name in dlq_names}
        
        try:
            with self.app.connection_for_read() as conn:
                for queue_name in dlq_names:
                    try:
                        simple_queue = conn.SimpleQueue(queue_name)
                        stats[queue_name] = simple_queue.qsize()
                    except Exception:
                        stats[queue_name] = 0
                        
        except Exception as e:
            logger.error(f"Error getting DLQ stats: {str(e)}")
        
        return stats


# =============================================================================
# Beat Schedule Configuration
# =============================================================================

def configure_beat_schedule(app: Any) -> None:
    """Configure Celery Beat periodic task schedule."""
    if not app:
        return
    
    app.conf.beat_schedule = {
        # Balance cache refresh
        "refresh-balance-cache-daily": {
            "task": "tasks.refresh_all_balance_caches",
            "schedule": timedelta(hours=24),
            "options": {"queue": "balance_calc"},
        },
        
        # DLQ cleanup
        "cleanup-dlq-weekly": {
            "task": "tasks.cleanup_dead_letter_queues",
            "schedule": timedelta(days=7),
            "options": {"queue": "default"},
        },
        
        # Cache metrics collection
        "collect-cache-metrics": {
            "task": "tasks.collect_cache_metrics",
            "schedule": timedelta(minutes=5),
            "options": {"queue": "default"},
        },
        
        # Session cleanup
        "cleanup-expired-sessions": {
            "task": "tasks.cleanup_expired_sessions",
            "schedule": timedelta(hours=6),
            "options": {"queue": "default"},
        },
    }


# =============================================================================
# Application Instance
# =============================================================================

# Create the Celery application
celery_app = create_celery_app()

# Configure beat schedule
if celery_app:
    configure_beat_schedule(celery_app)

# DLQ handler
dlq_handler = DeadLetterQueueHandler(celery_app)


def get_celery_app() -> Optional[Any]:
    """Get the Celery application instance."""
    return celery_app


def get_dlq_handler() -> DeadLetterQueueHandler:
    """Get the DLQ handler instance."""
    return dlq_handler

