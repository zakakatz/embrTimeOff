"""Middleware package for API performance and security."""

from src.middleware.caching import (
    cached,
    cache_balance,
    cache_policy_data,
    cache_validation_result,
    compute_validation_hash,
    get_cache_client,
    get_cached_balance,
    get_cached_policy,
    get_cached_validation,
    get_cache_stats,
    invalidate_cache,
    invalidate_employee_cache,
    invalidate_org_cache,
    invalidate_policy_cache,
    CacheTTL,
)

from src.middleware.rate_limiting import (
    rate_limit,
    get_rate_limiter,
    get_rate_limit_stats,
    RateLimitMiddleware,
    RateLimitTier,
    RateLimitConfig,
    RATE_LIMIT_CONFIGS,
)

__all__ = [
    # Caching
    "cached",
    "cache_balance",
    "cache_policy_data",
    "cache_validation_result",
    "compute_validation_hash",
    "get_cache_client",
    "get_cached_balance",
    "get_cached_policy",
    "get_cached_validation",
    "get_cache_stats",
    "invalidate_cache",
    "invalidate_employee_cache",
    "invalidate_org_cache",
    "invalidate_policy_cache",
    "CacheTTL",
    # Rate Limiting
    "rate_limit",
    "get_rate_limiter",
    "get_rate_limit_stats",
    "RateLimitMiddleware",
    "RateLimitTier",
    "RateLimitConfig",
    "RATE_LIMIT_CONFIGS",
]

