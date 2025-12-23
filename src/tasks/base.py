"""
Base Task Classes

Provides base task classes with:
- Exponential backoff retry logic
- Error handling and logging
- Status tracking
- Metrics collection
"""

import logging
import time
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar

try:
    from celery import Task, shared_task
    from celery.exceptions import MaxRetriesExceededError, Retry, SoftTimeLimitExceeded
    CELERY_AVAILABLE = True
except ImportError:
    Task = object
    shared_task = None
    MaxRetriesExceededError = Exception
    Retry = Exception
    SoftTimeLimitExceeded = Exception
    CELERY_AVAILABLE = False

logger = logging.getLogger(__name__)


# =============================================================================
# Task Status Enum
# =============================================================================

class TaskStatus(str, Enum):
    """Task execution status."""
    
    PENDING = "pending"
    STARTED = "started"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    RETRY = "retry"
    REVOKED = "revoked"


# =============================================================================
# Task Result Data Classes
# =============================================================================

@dataclass
class TaskResult:
    """Standardized task result."""
    
    task_id: str
    task_name: str
    status: TaskStatus
    result: Optional[Any] = None
    error: Optional[str] = None
    error_traceback: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    execution_time_ms: Optional[int] = None
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "task_name": self.task_name,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "error_traceback": self.error_traceback,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "execution_time_ms": self.execution_time_ms,
            "retry_count": self.retry_count,
            "metadata": self.metadata,
        }


@dataclass
class RetryConfig:
    """Retry configuration for tasks."""
    
    max_retries: int = 3
    default_retry_delay: int = 60  # seconds
    exponential_backoff: bool = True
    max_backoff_delay: int = 3600  # 1 hour max
    backoff_factor: float = 2.0
    retry_on_exceptions: List[Type[Exception]] = field(default_factory=lambda: [Exception])
    dont_retry_on: List[Type[Exception]] = field(default_factory=list)
    
    def get_retry_delay(self, retry_count: int) -> int:
        """Calculate retry delay with optional exponential backoff."""
        if not self.exponential_backoff:
            return self.default_retry_delay
        
        delay = self.default_retry_delay * (self.backoff_factor ** retry_count)
        return min(int(delay), self.max_backoff_delay)


# =============================================================================
# Base Task Class
# =============================================================================

class BaseTask(Task if CELERY_AVAILABLE else object):
    """
    Base task class with retry logic and monitoring.
    
    Features:
    - Exponential backoff retries
    - Automatic error logging
    - Status tracking
    - Execution time metrics
    """
    
    # Default retry configuration
    autoretry_for = (Exception,)
    max_retries = 3
    default_retry_delay = 60
    retry_backoff = True
    retry_backoff_max = 3600
    retry_jitter = True
    
    # Task options
    acks_late = True
    reject_on_worker_lost = True
    track_started = True
    
    # Custom configuration
    retry_config: RetryConfig = RetryConfig()
    
    def __init__(self):
        super().__init__() if CELERY_AVAILABLE else None
        self._start_time: Optional[float] = None
    
    def before_start(self, task_id: str, args: tuple, kwargs: dict) -> None:
        """Called before task starts execution."""
        self._start_time = time.time()
        logger.info(
            f"Task {self.name}[{task_id}] starting",
            extra={
                "task_id": task_id,
                "task_name": self.name,
                "args": str(args)[:200],
                "kwargs": str(kwargs)[:200],
            }
        )
    
    def on_success(self, retval: Any, task_id: str, args: tuple, kwargs: dict) -> None:
        """Called when task succeeds."""
        execution_time = self._get_execution_time()
        logger.info(
            f"Task {self.name}[{task_id}] succeeded in {execution_time}ms",
            extra={
                "task_id": task_id,
                "task_name": self.name,
                "execution_time_ms": execution_time,
                "status": TaskStatus.SUCCESS.value,
            }
        )
    
    def on_failure(
        self,
        exc: Exception,
        task_id: str,
        args: tuple,
        kwargs: dict,
        einfo: Any,
    ) -> None:
        """Called when task fails."""
        execution_time = self._get_execution_time()
        logger.error(
            f"Task {self.name}[{task_id}] failed: {str(exc)}",
            extra={
                "task_id": task_id,
                "task_name": self.name,
                "execution_time_ms": execution_time,
                "status": TaskStatus.FAILURE.value,
                "error": str(exc),
                "traceback": traceback.format_exc(),
            },
            exc_info=True,
        )
    
    def on_retry(
        self,
        exc: Exception,
        task_id: str,
        args: tuple,
        kwargs: dict,
        einfo: Any,
    ) -> None:
        """Called when task is retried."""
        retry_count = self.request.retries if hasattr(self, 'request') else 0
        delay = self.retry_config.get_retry_delay(retry_count)
        
        logger.warning(
            f"Task {self.name}[{task_id}] retrying (attempt {retry_count + 1}/{self.max_retries}), "
            f"delay: {delay}s, reason: {str(exc)}",
            extra={
                "task_id": task_id,
                "task_name": self.name,
                "retry_count": retry_count,
                "retry_delay": delay,
                "status": TaskStatus.RETRY.value,
                "error": str(exc),
            }
        )
    
    def _get_execution_time(self) -> Optional[int]:
        """Get execution time in milliseconds."""
        if self._start_time is None:
            return None
        return int((time.time() - self._start_time) * 1000)
    
    def should_retry(self, exc: Exception) -> bool:
        """Determine if task should be retried for given exception."""
        # Don't retry if explicitly excluded
        for exc_type in self.retry_config.dont_retry_on:
            if isinstance(exc, exc_type):
                return False
        
        # Retry if in allowed exceptions
        for exc_type in self.retry_config.retry_on_exceptions:
            if isinstance(exc, exc_type):
                return True
        
        return False
    
    def execute_with_retry(self, *args, **kwargs) -> Any:
        """Execute task with retry logic."""
        retry_count = self.request.retries if hasattr(self, 'request') else 0
        
        try:
            return self.run(*args, **kwargs)
            
        except SoftTimeLimitExceeded:
            # Don't retry on timeout - log and fail
            logger.error(f"Task {self.name} exceeded time limit")
            raise
            
        except Exception as exc:
            if self.should_retry(exc) and retry_count < self.max_retries:
                delay = self.retry_config.get_retry_delay(retry_count)
                raise self.retry(exc=exc, countdown=delay)
            raise


# =============================================================================
# Task Decorator
# =============================================================================

T = TypeVar('T', bound=Callable)


def background_task(
    name: Optional[str] = None,
    queue: str = "default",
    retry_config: Optional[RetryConfig] = None,
    soft_time_limit: int = 300,
    time_limit: int = 600,
) -> Callable[[T], T]:
    """
    Decorator to create a background task.
    
    Args:
        name: Task name (defaults to function name)
        queue: Queue to route task to
        retry_config: Custom retry configuration
        soft_time_limit: Soft time limit in seconds
        time_limit: Hard time limit in seconds
    
    Example:
        @background_task(queue="notifications", retry_config=RetryConfig(max_retries=5))
        def send_welcome_email(user_id: int):
            ...
    """
    def decorator(func: T) -> T:
        if not CELERY_AVAILABLE or shared_task is None:
            # Return function as-is if Celery not available
            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            return wrapper  # type: ignore
        
        # Create Celery task
        task_name = name or f"tasks.{func.__name__}"
        config = retry_config or RetryConfig()
        
        @shared_task(
            name=task_name,
            bind=True,
            base=BaseTask,
            queue=queue,
            autoretry_for=tuple(config.retry_on_exceptions),
            max_retries=config.max_retries,
            default_retry_delay=config.default_retry_delay,
            retry_backoff=config.exponential_backoff,
            retry_backoff_max=config.max_backoff_delay,
            soft_time_limit=soft_time_limit,
            time_limit=time_limit,
        )
        @wraps(func)
        def celery_task(self, *args, **kwargs):
            return func(*args, **kwargs)
        
        return celery_task  # type: ignore
    
    return decorator


# =============================================================================
# Task Registry
# =============================================================================

class TaskRegistry:
    """
    Registry for tracking all background tasks.
    
    Provides:
    - Task discovery
    - Status queries
    - Metrics collection
    """
    
    _instance = None
    _tasks: Dict[str, Dict[str, Any]] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def register(
        self,
        task_name: str,
        queue: str = "default",
        description: str = "",
        tags: Optional[List[str]] = None,
    ) -> None:
        """Register a task in the registry."""
        self._tasks[task_name] = {
            "name": task_name,
            "queue": queue,
            "description": description,
            "tags": tags or [],
            "registered_at": datetime.now(timezone.utc).isoformat(),
        }
    
    def get_task(self, task_name: str) -> Optional[Dict[str, Any]]:
        """Get task information."""
        return self._tasks.get(task_name)
    
    def list_tasks(
        self,
        queue: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List all registered tasks, optionally filtered."""
        tasks = list(self._tasks.values())
        
        if queue:
            tasks = [t for t in tasks if t["queue"] == queue]
        
        if tag:
            tasks = [t for t in tasks if tag in t["tags"]]
        
        return tasks
    
    def get_all_queues(self) -> List[str]:
        """Get all unique queue names."""
        return list(set(t["queue"] for t in self._tasks.values()))


# Global registry instance
task_registry = TaskRegistry()


def register_task(
    queue: str = "default",
    description: str = "",
    tags: Optional[List[str]] = None,
) -> Callable[[T], T]:
    """
    Decorator to register a task in the registry.
    
    Example:
        @register_task(queue="notifications", description="Send email", tags=["email"])
        @background_task(queue="notifications")
        def send_email(to: str, subject: str, body: str):
            ...
    """
    def decorator(func: T) -> T:
        task_name = getattr(func, 'name', f"tasks.{func.__name__}")
        task_registry.register(
            task_name=task_name,
            queue=queue,
            description=description,
            tags=tags,
        )
        return func
    
    return decorator

