"""
Task Monitoring Service

Provides status tracking, metrics collection, and health checks
for background task processing.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from src.tasks.base import TaskStatus, TaskRegistry, task_registry

logger = logging.getLogger(__name__)

# Try to import Celery components
try:
    from celery import Celery
    from celery.result import AsyncResult
    from src.tasks.celery_app import celery_app
    CELERY_AVAILABLE = celery_app is not None
except ImportError:
    Celery = None
    AsyncResult = None
    celery_app = None
    CELERY_AVAILABLE = False


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class TaskStatusInfo:
    """Information about a task's current status."""
    
    task_id: str
    task_name: str
    status: str
    result: Optional[Any] = None
    error: Optional[str] = None
    traceback: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    execution_time_ms: Optional[int] = None
    retries: int = 0
    queue: Optional[str] = None
    worker: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "task_name": self.task_name,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "traceback": self.traceback,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "execution_time_ms": self.execution_time_ms,
            "retries": self.retries,
            "queue": self.queue,
            "worker": self.worker,
        }


@dataclass
class WorkerInfo:
    """Information about a Celery worker."""
    
    hostname: str
    status: str
    active_tasks: int
    processed_tasks: int
    pool_size: int
    uptime_seconds: int
    last_heartbeat: Optional[datetime] = None
    queues: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "hostname": self.hostname,
            "status": self.status,
            "active_tasks": self.active_tasks,
            "processed_tasks": self.processed_tasks,
            "pool_size": self.pool_size,
            "uptime_seconds": self.uptime_seconds,
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "queues": self.queues,
        }


@dataclass
class QueueStats:
    """Statistics for a task queue."""
    
    name: str
    pending: int
    active: int
    failed: int
    succeeded: int
    avg_wait_time_ms: float
    avg_execution_time_ms: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "pending": self.pending,
            "active": self.active,
            "failed": self.failed,
            "succeeded": self.succeeded,
            "avg_wait_time_ms": self.avg_wait_time_ms,
            "avg_execution_time_ms": self.avg_execution_time_ms,
        }


@dataclass
class TaskMetrics:
    """Overall task processing metrics."""
    
    total_tasks: int
    pending_tasks: int
    running_tasks: int
    succeeded_tasks: int
    failed_tasks: int
    retried_tasks: int
    avg_execution_time_ms: float
    avg_wait_time_ms: float
    tasks_per_minute: float
    error_rate: float
    period_start: datetime
    period_end: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_tasks": self.total_tasks,
            "pending_tasks": self.pending_tasks,
            "running_tasks": self.running_tasks,
            "succeeded_tasks": self.succeeded_tasks,
            "failed_tasks": self.failed_tasks,
            "retried_tasks": self.retried_tasks,
            "avg_execution_time_ms": self.avg_execution_time_ms,
            "avg_wait_time_ms": self.avg_wait_time_ms,
            "tasks_per_minute": self.tasks_per_minute,
            "error_rate": self.error_rate,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
        }


# =============================================================================
# Task Monitoring Service
# =============================================================================

class TaskMonitoringService:
    """
    Service for monitoring background task processing.
    
    Provides:
    - Task status tracking
    - Worker health monitoring
    - Queue statistics
    - Performance metrics
    """
    
    def __init__(self, app: Optional[Any] = None):
        """
        Initialize monitoring service.
        
        Args:
            app: Celery application instance
        """
        self.app = app or celery_app
        self._enabled = self.app is not None
    
    @property
    def is_enabled(self) -> bool:
        """Check if task monitoring is available."""
        return self._enabled
    
    # =========================================================================
    # Task Status
    # =========================================================================
    
    def get_task_status(self, task_id: str) -> TaskStatusInfo:
        """
        Get status of a specific task.
        
        Args:
            task_id: Celery task ID
            
        Returns:
            TaskStatusInfo with current status
        """
        if not self._enabled or AsyncResult is None:
            return TaskStatusInfo(
                task_id=task_id,
                task_name="unknown",
                status="unavailable",
                error="Task monitoring not available",
            )
        
        try:
            result = AsyncResult(task_id, app=self.app)
            
            status_info = TaskStatusInfo(
                task_id=task_id,
                task_name=result.name or "unknown",
                status=result.status,
                result=result.result if result.successful() else None,
                error=str(result.result) if result.failed() else None,
                traceback=result.traceback if result.failed() else None,
                retries=result.retries or 0,
            )
            
            # Get extended info if available
            if hasattr(result, 'info') and isinstance(result.info, dict):
                info = result.info
                if 'started_at' in info:
                    status_info.started_at = datetime.fromisoformat(info['started_at'])
                if 'completed_at' in info:
                    status_info.completed_at = datetime.fromisoformat(info['completed_at'])
                if 'execution_time_ms' in info:
                    status_info.execution_time_ms = info['execution_time_ms']
            
            return status_info
            
        except Exception as e:
            logger.error(f"Error getting task status for {task_id}: {e}")
            return TaskStatusInfo(
                task_id=task_id,
                task_name="unknown",
                status="error",
                error=str(e),
            )
    
    def get_task_result(
        self,
        task_id: str,
        wait: bool = False,
        timeout: Optional[int] = None,
    ) -> Optional[Any]:
        """
        Get result of a completed task.
        
        Args:
            task_id: Celery task ID
            wait: Whether to wait for completion
            timeout: Timeout in seconds if waiting
            
        Returns:
            Task result or None
        """
        if not self._enabled or AsyncResult is None:
            return None
        
        try:
            result = AsyncResult(task_id, app=self.app)
            
            if wait:
                return result.get(timeout=timeout)
            elif result.ready():
                return result.result
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting task result for {task_id}: {e}")
            return None
    
    def revoke_task(
        self,
        task_id: str,
        terminate: bool = False,
        signal: str = "SIGTERM",
    ) -> bool:
        """
        Revoke (cancel) a task.
        
        Args:
            task_id: Celery task ID
            terminate: Force terminate if running
            signal: Signal to send if terminating
            
        Returns:
            True if revocation was sent
        """
        if not self._enabled:
            return False
        
        try:
            self.app.control.revoke(
                task_id,
                terminate=terminate,
                signal=signal,
            )
            logger.info(f"Revoked task {task_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error revoking task {task_id}: {e}")
            return False
    
    # =========================================================================
    # Worker Health
    # =========================================================================
    
    def get_workers(self) -> List[WorkerInfo]:
        """
        Get information about all active workers.
        
        Returns:
            List of WorkerInfo objects
        """
        if not self._enabled:
            return []
        
        workers = []
        
        try:
            # Get worker stats
            inspect = self.app.control.inspect()
            
            # Active tasks
            active = inspect.active() or {}
            
            # Worker stats
            stats = inspect.stats() or {}
            
            # Process each worker
            for hostname, worker_stats in stats.items():
                active_tasks = len(active.get(hostname, []))
                
                workers.append(WorkerInfo(
                    hostname=hostname,
                    status="online",
                    active_tasks=active_tasks,
                    processed_tasks=worker_stats.get('total', {}).get('tasks.task', 0),
                    pool_size=worker_stats.get('pool', {}).get('max-concurrency', 0),
                    uptime_seconds=int(worker_stats.get('clock', 0)),
                    queues=[q['name'] for q in worker_stats.get('queues', [])],
                ))
            
        except Exception as e:
            logger.error(f"Error getting worker info: {e}")
        
        return workers
    
    def ping_workers(self) -> Dict[str, bool]:
        """
        Ping all workers to check connectivity.
        
        Returns:
            Dictionary mapping worker hostname to ping success
        """
        if not self._enabled:
            return {}
        
        try:
            inspect = self.app.control.inspect()
            pings = inspect.ping() or {}
            
            return {hostname: True for hostname in pings.keys()}
            
        except Exception as e:
            logger.error(f"Error pinging workers: {e}")
            return {}
    
    def get_worker_health(self) -> Dict[str, Any]:
        """
        Get overall worker health summary.
        
        Returns:
            Dictionary with health information
        """
        workers = self.get_workers()
        pings = self.ping_workers()
        
        online_workers = len([w for w in workers if w.status == "online"])
        total_active_tasks = sum(w.active_tasks for w in workers)
        
        return {
            "status": "healthy" if online_workers > 0 else "unhealthy",
            "online_workers": online_workers,
            "total_workers": len(workers),
            "total_active_tasks": total_active_tasks,
            "workers": [w.to_dict() for w in workers],
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
    
    # =========================================================================
    # Queue Statistics
    # =========================================================================
    
    def get_queue_stats(self, queue_name: Optional[str] = None) -> List[QueueStats]:
        """
        Get statistics for task queues.
        
        Args:
            queue_name: Specific queue name or None for all
            
        Returns:
            List of QueueStats objects
        """
        if not self._enabled:
            # Return placeholder stats
            queues = ["default", "balance_calc", "notifications", "imports"]
            if queue_name:
                queues = [queue_name] if queue_name in queues else []
            
            return [
                QueueStats(
                    name=q,
                    pending=0,
                    active=0,
                    failed=0,
                    succeeded=0,
                    avg_wait_time_ms=0,
                    avg_execution_time_ms=0,
                )
                for q in queues
            ]
        
        stats = []
        
        try:
            inspect = self.app.control.inspect()
            
            # Get queue lengths
            reserved = inspect.reserved() or {}
            active = inspect.active() or {}
            
            # Aggregate by queue
            queue_data: Dict[str, Dict[str, int]] = {}
            
            for tasks in reserved.values():
                for task in tasks:
                    q = task.get('delivery_info', {}).get('routing_key', 'default')
                    if q not in queue_data:
                        queue_data[q] = {"pending": 0, "active": 0}
                    queue_data[q]["pending"] += 1
            
            for tasks in active.values():
                for task in tasks:
                    q = task.get('delivery_info', {}).get('routing_key', 'default')
                    if q not in queue_data:
                        queue_data[q] = {"pending": 0, "active": 0}
                    queue_data[q]["active"] += 1
            
            # Build stats
            for q_name, counts in queue_data.items():
                if queue_name and q_name != queue_name:
                    continue
                
                stats.append(QueueStats(
                    name=q_name,
                    pending=counts["pending"],
                    active=counts["active"],
                    failed=0,  # Would need to track separately
                    succeeded=0,  # Would need to track separately
                    avg_wait_time_ms=0,  # Would need to track separately
                    avg_execution_time_ms=0,  # Would need to track separately
                ))
            
        except Exception as e:
            logger.error(f"Error getting queue stats: {e}")
        
        return stats
    
    # =========================================================================
    # Metrics
    # =========================================================================
    
    def get_metrics(
        self,
        period_minutes: int = 60,
    ) -> TaskMetrics:
        """
        Get task processing metrics.
        
        Args:
            period_minutes: Time period for metrics
            
        Returns:
            TaskMetrics object
        """
        now = datetime.now(timezone.utc)
        period_start = now - timedelta(minutes=period_minutes)
        
        # Placeholder metrics - would aggregate from monitoring backend
        return TaskMetrics(
            total_tasks=1000,
            pending_tasks=50,
            running_tasks=10,
            succeeded_tasks=920,
            failed_tasks=20,
            retried_tasks=30,
            avg_execution_time_ms=250.0,
            avg_wait_time_ms=100.0,
            tasks_per_minute=16.7,
            error_rate=0.02,
            period_start=period_start,
            period_end=now,
        )
    
    def get_task_type_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Get statistics by task type.
        
        Returns:
            Dictionary mapping task name to stats
        """
        # Use task registry to get registered tasks
        tasks = task_registry.list_tasks()
        
        # Placeholder stats per task type
        stats = {}
        for task in tasks:
            stats[task["name"]] = {
                "queue": task["queue"],
                "description": task["description"],
                "tags": task["tags"],
                "executions_24h": 100,  # Placeholder
                "avg_execution_time_ms": 200,  # Placeholder
                "error_rate": 0.01,  # Placeholder
            }
        
        return stats
    
    # =========================================================================
    # Health Check
    # =========================================================================
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform comprehensive health check.
        
        Returns:
            Dictionary with health status
        """
        if not self._enabled:
            return {
                "status": "disabled",
                "reason": "Celery not configured",
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }
        
        health = {
            "status": "healthy",
            "broker": {"status": "unknown"},
            "backend": {"status": "unknown"},
            "workers": {"status": "unknown", "count": 0},
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
        
        try:
            # Check broker connection
            conn = self.app.connection()
            conn.ensure_connection(max_retries=1)
            health["broker"] = {"status": "connected"}
            conn.close()
        except Exception as e:
            health["broker"] = {"status": "error", "error": str(e)}
            health["status"] = "unhealthy"
        
        try:
            # Check workers
            workers = self.get_workers()
            online = len([w for w in workers if w.status == "online"])
            health["workers"] = {
                "status": "healthy" if online > 0 else "no_workers",
                "count": online,
            }
            if online == 0:
                health["status"] = "degraded"
        except Exception as e:
            health["workers"] = {"status": "error", "error": str(e)}
            health["status"] = "unhealthy"
        
        return health


# =============================================================================
# Service Instance
# =============================================================================

# Global service instance
_monitoring_service: Optional[TaskMonitoringService] = None


def get_monitoring_service() -> TaskMonitoringService:
    """Get task monitoring service instance."""
    global _monitoring_service
    
    if _monitoring_service is None:
        _monitoring_service = TaskMonitoringService()
    
    return _monitoring_service

