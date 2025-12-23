"""
Redis Health Check API Endpoints

Provides health check endpoints for Redis connectivity and cache performance.
"""

from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.infrastructure.redis.redis_client import redis_health_check, get_redis_manager
from src.infrastructure.redis.caching_service import get_cache_service

router = APIRouter(prefix="/health/redis", tags=["Health"])


# =============================================================================
# Response Models
# =============================================================================

class RedisHealthResponse(BaseModel):
    """Response model for Redis health check."""
    
    status: str = Field(..., description="Health status: healthy, degraded, unhealthy")
    connected: bool = Field(..., description="Whether Redis is connected")
    latency_ms: float | None = Field(None, description="Ping latency in milliseconds")
    cluster_mode: bool = Field(False, description="Whether running in cluster mode")
    redis_version: str | None = Field(None, description="Redis server version")
    uptime_seconds: int | None = Field(None, description="Redis uptime in seconds")
    error: str | None = Field(None, description="Error message if unhealthy")
    checked_at: str = Field(..., description="ISO timestamp of health check")


class CacheMetricsResponse(BaseModel):
    """Response model for cache metrics."""
    
    hits: int = Field(..., description="Number of cache hits")
    misses: int = Field(..., description="Number of cache misses")
    sets: int = Field(..., description="Number of cache sets")
    deletes: int = Field(..., description="Number of cache deletes")
    errors: int = Field(..., description="Number of cache errors")
    hit_ratio: float = Field(..., description="Cache hit ratio percentage")
    total_operations: int = Field(..., description="Total cache operations")


class CombinedHealthResponse(BaseModel):
    """Combined health status for Redis and cache."""
    
    redis: RedisHealthResponse
    cache_metrics: CacheMetricsResponse
    overall_status: str = Field(..., description="Overall health status")


# =============================================================================
# Endpoints
# =============================================================================

@router.get(
    "",
    response_model=RedisHealthResponse,
    summary="Check Redis health",
    description="Verify Redis connectivity and return status within 3 seconds",
)
async def check_redis_health() -> RedisHealthResponse:
    """
    Perform Redis health check.
    
    Returns status within 3 seconds as per requirements.
    """
    health = redis_health_check()
    
    return RedisHealthResponse(
        status=health.get("status", "unknown"),
        connected=health.get("connected", False),
        latency_ms=health.get("latency_ms"),
        cluster_mode=health.get("cluster_mode", False),
        redis_version=health.get("redis_version"),
        uptime_seconds=health.get("uptime_seconds"),
        error=health.get("error"),
        checked_at=datetime.now(timezone.utc).isoformat(),
    )


@router.get(
    "/metrics",
    response_model=CacheMetricsResponse,
    summary="Get cache metrics",
    description="Get cache performance metrics including hit/miss ratio",
)
async def get_cache_metrics() -> CacheMetricsResponse:
    """
    Get cache performance metrics.
    
    Returns hit/miss ratios and operation counts.
    """
    cache_service = get_cache_service()
    metrics = cache_service.get_metrics_summary()
    
    return CacheMetricsResponse(
        hits=metrics["hits"],
        misses=metrics["misses"],
        sets=metrics["sets"],
        deletes=metrics["deletes"],
        errors=metrics["errors"],
        hit_ratio=metrics["hit_ratio"],
        total_operations=metrics["total_operations"],
    )


@router.get(
    "/full",
    response_model=CombinedHealthResponse,
    summary="Get full Redis health status",
    description="Get combined Redis health and cache metrics",
)
async def get_full_health() -> CombinedHealthResponse:
    """
    Get combined health status for Redis and cache.
    """
    # Get Redis health
    redis_health = await check_redis_health()
    
    # Get cache metrics
    cache_metrics = await get_cache_metrics()
    
    # Determine overall status
    if redis_health.status == "unhealthy":
        overall_status = "unhealthy"
    elif redis_health.status == "degraded" or cache_metrics.hit_ratio < 50:
        overall_status = "degraded"
    else:
        overall_status = "healthy"
    
    return CombinedHealthResponse(
        redis=redis_health,
        cache_metrics=cache_metrics,
        overall_status=overall_status,
    )


@router.post(
    "/metrics/reset",
    summary="Reset cache metrics",
    description="Reset cache performance metrics counters",
)
async def reset_cache_metrics() -> Dict[str, str]:
    """Reset cache metrics counters."""
    cache_service = get_cache_service()
    cache_service.reset_metrics()
    
    return {
        "status": "success",
        "message": "Cache metrics reset successfully",
        "reset_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get(
    "/connection",
    summary="Get connection info",
    description="Get Redis connection configuration (non-sensitive)",
)
async def get_connection_info() -> Dict[str, Any]:
    """Get Redis connection information (non-sensitive data only)."""
    manager = get_redis_manager()
    config = manager.config
    
    return {
        "host": config.host,
        "port": config.port,
        "db": config.db,
        "cluster_mode": config.cluster_mode,
        "sentinel_mode": config.sentinel_mode,
        "ssl_enabled": config.ssl,
        "max_connections": config.max_connections,
        "socket_timeout": config.socket_timeout,
        "health_check_interval": config.health_check_interval,
    }

