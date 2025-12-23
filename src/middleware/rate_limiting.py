"""Rate limiting middleware for API protection."""

import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, Optional, Tuple

from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.middleware.caching import get_cache_client


# =============================================================================
# Rate Limit Configuration
# =============================================================================

class RateLimitTier(str, Enum):
    """Rate limit tiers for different endpoints."""
    
    VALIDATION = "validation"       # Form validation endpoints
    BALANCE = "balance"             # Balance projection endpoints
    SEARCH = "search"               # Search endpoints
    STANDARD = "standard"           # Standard API endpoints
    ADMIN = "admin"                 # Admin endpoints


@dataclass
class RateLimitConfig:
    """Configuration for a rate limit."""
    
    requests_per_minute: int
    burst_capacity: int  # Additional requests allowed for bursts
    window_seconds: int = 60
    
    @property
    def total_allowed(self) -> int:
        """Total requests allowed including burst."""
        return self.requests_per_minute + self.burst_capacity


# Default rate limit configurations
RATE_LIMIT_CONFIGS: Dict[RateLimitTier, RateLimitConfig] = {
    RateLimitTier.VALIDATION: RateLimitConfig(
        requests_per_minute=60,
        burst_capacity=20,  # Extra for initial form loading
    ),
    RateLimitTier.BALANCE: RateLimitConfig(
        requests_per_minute=30,
        burst_capacity=10,
    ),
    RateLimitTier.SEARCH: RateLimitConfig(
        requests_per_minute=100,
        burst_capacity=30,
    ),
    RateLimitTier.STANDARD: RateLimitConfig(
        requests_per_minute=120,
        burst_capacity=40,
    ),
    RateLimitTier.ADMIN: RateLimitConfig(
        requests_per_minute=60,
        burst_capacity=20,
    ),
}


# Endpoint to rate limit tier mapping
ENDPOINT_TIERS: Dict[str, RateLimitTier] = {
    "/api/time-off-requests": RateLimitTier.STANDARD,
    "/api/time-off/balance": RateLimitTier.BALANCE,
    "/api/time-off/validate": RateLimitTier.VALIDATION,
    "/api/employee-directory": RateLimitTier.SEARCH,
    "/api/employees": RateLimitTier.STANDARD,
    "/api/admin": RateLimitTier.ADMIN,
}


# =============================================================================
# Sliding Window Rate Limiter
# =============================================================================

class SlidingWindowRateLimiter:
    """
    Implements sliding window rate limiting.
    
    Uses a sliding window algorithm to provide smooth rate limiting
    without the sudden reset behavior of fixed windows.
    """
    
    def __init__(self):
        self.cache = get_cache_client()
    
    def _get_window_key(self, identifier: str, tier: RateLimitTier) -> str:
        """Generate cache key for rate limit window."""
        return f"ratelimit:{tier.value}:{identifier}"
    
    def _get_current_window(self) -> int:
        """Get current time window (minute)."""
        return int(time.time() // 60)
    
    def check_rate_limit(
        self,
        identifier: str,
        tier: RateLimitTier,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if request is within rate limit.
        
        Args:
            identifier: Unique identifier (employee_id, IP, etc.)
            tier: Rate limit tier
            
        Returns:
            Tuple of (is_allowed, rate_limit_info)
        """
        config = RATE_LIMIT_CONFIGS.get(tier, RATE_LIMIT_CONFIGS[RateLimitTier.STANDARD])
        
        current_window = self._get_current_window()
        prev_window = current_window - 1
        
        current_key = f"{self._get_window_key(identifier, tier)}:{current_window}"
        prev_key = f"{self._get_window_key(identifier, tier)}:{prev_window}"
        
        # Get counts
        current_count = int(self.cache.get(current_key) or 0)
        prev_count = int(self.cache.get(prev_key) or 0)
        
        # Calculate weighted count using sliding window
        seconds_in_window = time.time() % 60
        weight = (60 - seconds_in_window) / 60
        
        weighted_count = current_count + (prev_count * weight)
        
        # Check if within limit
        is_allowed = weighted_count < config.total_allowed
        
        # Calculate remaining
        remaining = max(0, config.total_allowed - int(weighted_count) - 1)
        
        # Calculate reset time
        reset_seconds = 60 - int(seconds_in_window)
        reset_time = datetime.utcnow() + timedelta(seconds=reset_seconds)
        
        # Calculate retry-after for exponential backoff
        retry_after = None
        if not is_allowed:
            # Exponential backoff based on how much over the limit
            over_limit_ratio = (weighted_count - config.total_allowed) / config.total_allowed
            retry_after = min(60, max(1, int(5 * (1 + over_limit_ratio) ** 2)))
        
        rate_limit_info = {
            "limit": config.total_allowed,
            "remaining": remaining,
            "reset": reset_time.isoformat(),
            "reset_seconds": reset_seconds,
            "retry_after": retry_after,
            "tier": tier.value,
        }
        
        return is_allowed, rate_limit_info
    
    def record_request(
        self,
        identifier: str,
        tier: RateLimitTier,
    ) -> None:
        """Record a request for rate limiting."""
        current_window = self._get_current_window()
        key = f"{self._get_window_key(identifier, tier)}:{current_window}"
        
        # Increment counter
        self.cache.incr(key)
        
        # Set expiration (2 minutes to cover sliding window)
        self.cache.set(
            key,
            str(int(self.cache.get(key) or 0)),
            ex=120,
        )


# Global rate limiter instance
_rate_limiter: Optional[SlidingWindowRateLimiter] = None


def get_rate_limiter() -> SlidingWindowRateLimiter:
    """Get or create rate limiter singleton."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = SlidingWindowRateLimiter()
    return _rate_limiter


# =============================================================================
# Helper Functions
# =============================================================================

def get_tier_for_path(path: str) -> RateLimitTier:
    """Determine rate limit tier based on request path."""
    for prefix, tier in ENDPOINT_TIERS.items():
        if path.startswith(prefix):
            return tier
    return RateLimitTier.STANDARD


def get_identifier(request: Request) -> str:
    """
    Get unique identifier for rate limiting.
    
    Prefers employee ID from headers, falls back to IP address.
    """
    # Try to get employee ID from headers
    employee_id = request.headers.get("X-Employee-ID")
    if employee_id:
        return f"employee:{employee_id}"
    
    # Fall back to IP address
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    else:
        ip = request.client.host if request.client else "unknown"
    
    return f"ip:{ip}"


def generate_correlation_id() -> str:
    """Generate a unique correlation ID for debugging."""
    return f"req_{uuid.uuid4().hex[:12]}"


# =============================================================================
# Rate Limit Response Headers
# =============================================================================

def add_rate_limit_headers(
    response: Response,
    rate_limit_info: Dict[str, Any],
    correlation_id: str,
) -> None:
    """Add rate limit headers to response."""
    response.headers["X-RateLimit-Limit"] = str(rate_limit_info["limit"])
    response.headers["X-RateLimit-Remaining"] = str(rate_limit_info["remaining"])
    response.headers["X-RateLimit-Reset"] = rate_limit_info["reset"]
    response.headers["X-RateLimit-Tier"] = rate_limit_info["tier"]
    response.headers["X-Correlation-ID"] = correlation_id
    
    if rate_limit_info.get("retry_after"):
        response.headers["Retry-After"] = str(rate_limit_info["retry_after"])


# =============================================================================
# FastAPI Middleware
# =============================================================================

class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for rate limiting."""
    
    def __init__(self, app, exclude_paths: Optional[list] = None):
        super().__init__(app)
        self.rate_limiter = get_rate_limiter()
        self.exclude_paths = exclude_paths or [
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json",
        ]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with rate limiting."""
        path = request.url.path
        
        # Skip excluded paths
        if any(path.startswith(excluded) for excluded in self.exclude_paths):
            return await call_next(request)
        
        # Generate correlation ID
        correlation_id = generate_correlation_id()
        
        # Get identifier and tier
        identifier = get_identifier(request)
        tier = get_tier_for_path(path)
        
        # Check rate limit
        is_allowed, rate_limit_info = self.rate_limiter.check_rate_limit(
            identifier,
            tier,
        )
        
        if not is_allowed:
            # Return 429 Too Many Requests
            response = JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "rate_limit_exceeded",
                        "message": "Too many requests. Please try again later.",
                        "retry_after": rate_limit_info.get("retry_after"),
                        "correlation_id": correlation_id,
                    }
                },
            )
            add_rate_limit_headers(response, rate_limit_info, correlation_id)
            return response
        
        # Record the request
        self.rate_limiter.record_request(identifier, tier)
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers to successful response
        add_rate_limit_headers(response, rate_limit_info, correlation_id)
        
        return response


# =============================================================================
# Decorator for Route-Level Rate Limiting
# =============================================================================

def rate_limit(
    tier: RateLimitTier = RateLimitTier.STANDARD,
    identifier_func: Optional[Callable[[Request], str]] = None,
):
    """
    Decorator for route-level rate limiting.
    
    Args:
        tier: Rate limit tier to apply
        identifier_func: Custom function to get identifier from request
    """
    def decorator(func: Callable) -> Callable:
        async def wrapper(request: Request, *args, **kwargs):
            limiter = get_rate_limiter()
            correlation_id = generate_correlation_id()
            
            # Get identifier
            if identifier_func:
                identifier = identifier_func(request)
            else:
                identifier = get_identifier(request)
            
            # Check rate limit
            is_allowed, rate_limit_info = limiter.check_rate_limit(identifier, tier)
            
            if not is_allowed:
                raise HTTPException(
                    status_code=429,
                    detail={
                        "code": "rate_limit_exceeded",
                        "message": "Too many requests",
                        "retry_after": rate_limit_info.get("retry_after"),
                        "correlation_id": correlation_id,
                    },
                    headers={
                        "Retry-After": str(rate_limit_info.get("retry_after", 60)),
                        "X-Correlation-ID": correlation_id,
                    },
                )
            
            # Record request
            limiter.record_request(identifier, tier)
            
            # Execute function
            return await func(request, *args, **kwargs)
        
        return wrapper
    return decorator


# =============================================================================
# Rate Limit Statistics
# =============================================================================

def get_rate_limit_stats(identifier: str) -> Dict[str, Any]:
    """Get rate limit statistics for an identifier."""
    limiter = get_rate_limiter()
    
    stats = {}
    for tier in RateLimitTier:
        _, info = limiter.check_rate_limit(identifier, tier)
        stats[tier.value] = info
    
    return {
        "identifier": identifier,
        "tiers": stats,
        "timestamp": datetime.utcnow().isoformat(),
    }

