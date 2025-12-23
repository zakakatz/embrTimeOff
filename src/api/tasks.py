"""
Task Monitoring API Endpoints

Provides endpoints for:
- Task status tracking
- Worker health monitoring
- Queue statistics
- Task management (revoke, retry)
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.services.task_monitoring_service import (
    TaskMonitoringService,
    TaskStatusInfo,
    WorkerInfo,
    QueueStats,
    TaskMetrics,
    get_monitoring_service,
)
from src.tasks.base import task_registry

router = APIRouter(prefix="/api/v1/tasks", tags=["Tasks"])


# =============================================================================
# Request/Response Models
# =============================================================================

class TaskStatusResponse(BaseModel):
    """Task status response."""
    
    task_id: str
    task_name: str
    status: str
    result: Optional[Any] = None
    error: Optional[str] = None
    traceback: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    execution_time_ms: Optional[int] = None
    retries: int = 0
    queue: Optional[str] = None
    worker: Optional[str] = None


class WorkerResponse(BaseModel):
    """Worker information response."""
    
    hostname: str
    status: str
    active_tasks: int
    processed_tasks: int
    pool_size: int
    uptime_seconds: int
    last_heartbeat: Optional[str] = None
    queues: List[str] = Field(default_factory=list)


class WorkerHealthResponse(BaseModel):
    """Worker health summary response."""
    
    status: str
    online_workers: int
    total_workers: int
    total_active_tasks: int
    workers: List[WorkerResponse]
    checked_at: str


class QueueStatsResponse(BaseModel):
    """Queue statistics response."""
    
    name: str
    pending: int
    active: int
    failed: int
    succeeded: int
    avg_wait_time_ms: float
    avg_execution_time_ms: float


class TaskMetricsResponse(BaseModel):
    """Task metrics response."""
    
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
    period_start: str
    period_end: str


class HealthCheckResponse(BaseModel):
    """Health check response."""
    
    status: str
    broker: Dict[str, Any]
    backend: Dict[str, Any]
    workers: Dict[str, Any]
    checked_at: str


class RegisteredTaskResponse(BaseModel):
    """Registered task information."""
    
    name: str
    queue: str
    description: str
    tags: List[str]
    registered_at: str


class RevokeTaskRequest(BaseModel):
    """Request to revoke a task."""
    
    terminate: bool = Field(default=False, description="Force terminate if running")
    signal: str = Field(default="SIGTERM", description="Signal to send")


# =============================================================================
# Task Status Endpoints
# =============================================================================

@router.get(
    "/status/{task_id}",
    response_model=TaskStatusResponse,
    summary="Get task status",
    description="Get the current status of a background task",
)
async def get_task_status(
    task_id: str,
    service: TaskMonitoringService = Depends(get_monitoring_service),
) -> TaskStatusResponse:
    """Get status of a specific task."""
    status = service.get_task_status(task_id)
    
    return TaskStatusResponse(
        task_id=status.task_id,
        task_name=status.task_name,
        status=status.status,
        result=status.result,
        error=status.error,
        traceback=status.traceback,
        started_at=status.started_at.isoformat() if status.started_at else None,
        completed_at=status.completed_at.isoformat() if status.completed_at else None,
        execution_time_ms=status.execution_time_ms,
        retries=status.retries,
        queue=status.queue,
        worker=status.worker,
    )


@router.get(
    "/result/{task_id}",
    summary="Get task result",
    description="Get the result of a completed task",
)
async def get_task_result(
    task_id: str,
    wait: bool = Query(False, description="Wait for task completion"),
    timeout: int = Query(30, ge=1, le=300, description="Timeout in seconds"),
    service: TaskMonitoringService = Depends(get_monitoring_service),
) -> Dict[str, Any]:
    """Get result of a completed task."""
    result = service.get_task_result(task_id, wait=wait, timeout=timeout)
    
    if result is None and not wait:
        raise HTTPException(
            status_code=404,
            detail="Task not found or not completed"
        )
    
    return {"task_id": task_id, "result": result}


@router.post(
    "/revoke/{task_id}",
    summary="Revoke task",
    description="Cancel a pending or running task",
)
async def revoke_task(
    task_id: str,
    request: RevokeTaskRequest,
    service: TaskMonitoringService = Depends(get_monitoring_service),
) -> Dict[str, Any]:
    """Revoke (cancel) a task."""
    success = service.revoke_task(
        task_id,
        terminate=request.terminate,
        signal=request.signal,
    )
    
    if not success:
        raise HTTPException(
            status_code=500,
            detail="Failed to revoke task"
        )
    
    return {
        "task_id": task_id,
        "status": "revoked",
        "terminate": request.terminate,
    }


# =============================================================================
# Worker Endpoints
# =============================================================================

@router.get(
    "/workers",
    response_model=WorkerHealthResponse,
    summary="Get worker health",
    description="Get health status of all Celery workers",
)
async def get_workers(
    service: TaskMonitoringService = Depends(get_monitoring_service),
) -> WorkerHealthResponse:
    """Get worker health information."""
    health = service.get_worker_health()
    
    return WorkerHealthResponse(
        status=health["status"],
        online_workers=health["online_workers"],
        total_workers=health["total_workers"],
        total_active_tasks=health["total_active_tasks"],
        workers=[
            WorkerResponse(**w) for w in health["workers"]
        ],
        checked_at=health["checked_at"],
    )


@router.get(
    "/workers/ping",
    summary="Ping workers",
    description="Ping all workers to check connectivity",
)
async def ping_workers(
    service: TaskMonitoringService = Depends(get_monitoring_service),
) -> Dict[str, Any]:
    """Ping all workers."""
    pings = service.ping_workers()
    
    return {
        "pings": pings,
        "total": len(pings),
        "responsive": sum(1 for v in pings.values() if v),
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


# =============================================================================
# Queue Endpoints
# =============================================================================

@router.get(
    "/queues",
    response_model=List[QueueStatsResponse],
    summary="Get queue statistics",
    description="Get statistics for all task queues",
)
async def get_queue_stats(
    queue: Optional[str] = Query(None, description="Filter by queue name"),
    service: TaskMonitoringService = Depends(get_monitoring_service),
) -> List[QueueStatsResponse]:
    """Get queue statistics."""
    stats = service.get_queue_stats(queue_name=queue)
    
    return [
        QueueStatsResponse(
            name=s.name,
            pending=s.pending,
            active=s.active,
            failed=s.failed,
            succeeded=s.succeeded,
            avg_wait_time_ms=s.avg_wait_time_ms,
            avg_execution_time_ms=s.avg_execution_time_ms,
        )
        for s in stats
    ]


# =============================================================================
# Metrics Endpoints
# =============================================================================

@router.get(
    "/metrics",
    response_model=TaskMetricsResponse,
    summary="Get task metrics",
    description="Get overall task processing metrics",
)
async def get_metrics(
    period: int = Query(60, ge=1, le=1440, description="Period in minutes"),
    service: TaskMonitoringService = Depends(get_monitoring_service),
) -> TaskMetricsResponse:
    """Get task processing metrics."""
    metrics = service.get_metrics(period_minutes=period)
    
    return TaskMetricsResponse(
        total_tasks=metrics.total_tasks,
        pending_tasks=metrics.pending_tasks,
        running_tasks=metrics.running_tasks,
        succeeded_tasks=metrics.succeeded_tasks,
        failed_tasks=metrics.failed_tasks,
        retried_tasks=metrics.retried_tasks,
        avg_execution_time_ms=metrics.avg_execution_time_ms,
        avg_wait_time_ms=metrics.avg_wait_time_ms,
        tasks_per_minute=metrics.tasks_per_minute,
        error_rate=metrics.error_rate,
        period_start=metrics.period_start.isoformat(),
        period_end=metrics.period_end.isoformat(),
    )


@router.get(
    "/metrics/by-type",
    summary="Get metrics by task type",
    description="Get statistics grouped by task type",
)
async def get_metrics_by_type(
    service: TaskMonitoringService = Depends(get_monitoring_service),
) -> Dict[str, Any]:
    """Get metrics by task type."""
    return service.get_task_type_stats()


# =============================================================================
# Task Registry Endpoints
# =============================================================================

@router.get(
    "/registered",
    response_model=List[RegisteredTaskResponse],
    summary="Get registered tasks",
    description="Get list of all registered background tasks",
)
async def get_registered_tasks(
    queue: Optional[str] = Query(None, description="Filter by queue"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
) -> List[RegisteredTaskResponse]:
    """Get all registered tasks."""
    tasks = task_registry.list_tasks(queue=queue, tag=tag)
    
    return [
        RegisteredTaskResponse(
            name=t["name"],
            queue=t["queue"],
            description=t["description"],
            tags=t["tags"],
            registered_at=t["registered_at"],
        )
        for t in tasks
    ]


@router.get(
    "/queues/names",
    summary="Get queue names",
    description="Get list of all queue names",
)
async def get_queue_names() -> List[str]:
    """Get all unique queue names."""
    return task_registry.get_all_queues()


# =============================================================================
# Health Check Endpoint
# =============================================================================

@router.get(
    "/health",
    response_model=HealthCheckResponse,
    summary="Task system health check",
    description="Comprehensive health check of the task processing system",
)
async def health_check(
    service: TaskMonitoringService = Depends(get_monitoring_service),
) -> HealthCheckResponse:
    """Perform health check."""
    health = service.health_check()
    
    return HealthCheckResponse(
        status=health["status"],
        broker=health["broker"],
        backend=health.get("backend", {"status": "unknown"}),
        workers=health["workers"],
        checked_at=health["checked_at"],
    )


# =============================================================================
# System Info Endpoint
# =============================================================================

@router.get(
    "/info",
    summary="Get task system info",
    description="Get information about the task processing system",
)
async def get_system_info(
    service: TaskMonitoringService = Depends(get_monitoring_service),
) -> Dict[str, Any]:
    """Get task system information."""
    from src.tasks.celery_app import get_app_info
    
    return {
        "celery": get_app_info(),
        "monitoring_enabled": service.is_enabled,
        "registered_tasks": len(task_registry.list_tasks()),
        "available_queues": task_registry.get_all_queues(),
    }

