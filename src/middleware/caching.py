"""Redis caching middleware for API performance optimization."""

import hashlib
import json
import time
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Callable, Dict, Optional, Union

# Mock Redis client for development (would use real redis in production)
class MockRedisClient:
    """In-memory mock Redis client for development."""
    
    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}
    
    def get(self, key: str) -> Optional[str]:
        """Get value from cache."""
        if key in self._store:
            entry = self._store[key]
            if entry["expires_at"] and datetime.utcnow() > entry["expires_at"]:
                del self._store[key]
                return None
            return entry["value"]
        return None
    
    def set(
        self,
        key: str,
        value: str,
        ex: Optional[int] = None,
        px: Optional[int] = None,
    ) -> bool:
        """Set value in cache with optional expiration."""
        expires_at = None
        if ex:
            expires_at = datetime.utcnow() + timedelta(seconds=ex)
        elif px:
            expires_at = datetime.utcnow() + timedelta(milliseconds=px)
        
        self._store[key] = {
            "value": value,
            "expires_at": expires_at,
            "created_at": datetime.utcnow(),
        }
        return True
    
    def delete(self, *keys: str) -> int:
        """Delete keys from cache."""
        deleted = 0
        for key in keys:
            if key in self._store:
                del self._store[key]
                deleted += 1
        return deleted
    
    def keys(self, pattern: str = "*") -> list:
        """Get keys matching pattern."""
        if pattern == "*":
            return list(self._store.keys())
        
        # Simple pattern matching for common cases
        if pattern.endswith("*"):
            prefix = pattern[:-1]
            return [k for k in self._store.keys() if k.startswith(prefix)]
        
        return [k for k in self._store.keys() if k == pattern]
    
    def exists(self, key: str) -> bool:
        """Check if key exists."""
        return self.get(key) is not None
    
    def ttl(self, key: str) -> int:
        """Get TTL for key in seconds."""
        if key in self._store:
            entry = self._store[key]
            if entry["expires_at"]:
                remaining = (entry["expires_at"] - datetime.utcnow()).total_seconds()
                return max(0, int(remaining))
            return -1  # No expiration
        return -2  # Key doesn't exist
    
    def incr(self, key: str) -> int:
        """Increment value."""
        current = self.get(key)
        new_value = int(current or 0) + 1
        
        # Preserve TTL if exists
        if key in self._store:
            self._store[key]["value"] = str(new_value)
        else:
            self.set(key, str(new_value))
        
        return new_value


# Global cache instance
_cache_client: Optional[MockRedisClient] = None


def get_cache_client() -> MockRedisClient:
    """Get or create cache client singleton."""
    global _cache_client
    if _cache_client is None:
        _cache_client = MockRedisClient()
    return _cache_client


# =============================================================================
# Cache Key Generators
# =============================================================================

def generate_cache_key(prefix: str, *args, **kwargs) -> str:
    """Generate a cache key from prefix and arguments."""
    key_parts = [prefix]
    
    for arg in args:
        key_parts.append(str(arg))
    
    for k, v in sorted(kwargs.items()):
        key_parts.append(f"{k}={v}")
    
    key_string = ":".join(key_parts)
    return key_string


def generate_hash_key(prefix: str, data: Dict[str, Any]) -> str:
    """Generate a hash-based cache key for complex data."""
    data_string = json.dumps(data, sort_keys=True, default=str)
    hash_value = hashlib.md5(data_string.encode()).hexdigest()[:12]
    return f"{prefix}:{hash_value}"


# =============================================================================
# TTL Configuration
# =============================================================================

class CacheTTL:
    """Cache TTL configuration values in seconds."""
    
    # Balance calculations - short TTL, refreshed frequently
    BALANCE_CALCULATION = 300  # 5 minutes
    
    # Policy data - longer TTL, invalidated on change
    POLICY_DATA = 3600  # 1 hour
    
    # Validation results - medium TTL
    VALIDATION_RESULT = 600  # 10 minutes
    
    # Employee profile data
    EMPLOYEE_PROFILE = 1800  # 30 minutes
    
    # Organizational data
    ORG_STRUCTURE = 3600  # 1 hour
    
    # Directory search results
    DIRECTORY_SEARCH = 300  # 5 minutes
    
    # Configuration data - long TTL
    CONFIGURATION = 7200  # 2 hours


# =============================================================================
# Cache Decorators
# =============================================================================

def cached(
    prefix: str,
    ttl: int = CacheTTL.BALANCE_CALCULATION,
    key_builder: Optional[Callable] = None,
):
    """
    Decorator for caching function results.
    
    Args:
        prefix: Cache key prefix
        ttl: Time to live in seconds
        key_builder: Optional function to build cache key from args
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            cache = get_cache_client()
            
            # Build cache key
            if key_builder:
                cache_key = key_builder(prefix, *args, **kwargs)
            else:
                cache_key = generate_cache_key(prefix, *args[1:], **kwargs)  # Skip self
            
            # Try to get from cache
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                return json.loads(cached_value)
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Store in cache
            if result is not None:
                cache.set(cache_key, json.dumps(result, default=str), ex=ttl)
            
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            cache = get_cache_client()
            
            # Build cache key
            if key_builder:
                cache_key = key_builder(prefix, *args, **kwargs)
            else:
                cache_key = generate_cache_key(prefix, *args[1:], **kwargs)
            
            # Try to get from cache
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                return json.loads(cached_value)
            
            # Execute function
            result = func(*args, **kwargs)
            
            # Store in cache
            if result is not None:
                cache.set(cache_key, json.dumps(result, default=str), ex=ttl)
            
            return result
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


# =============================================================================
# Cache Management Functions
# =============================================================================

def invalidate_cache(pattern: str) -> int:
    """
    Invalidate cache entries matching pattern.
    
    Args:
        pattern: Key pattern to match (e.g., "balance:employee:123:*")
        
    Returns:
        Number of keys deleted
    """
    cache = get_cache_client()
    keys = cache.keys(pattern)
    if keys:
        return cache.delete(*keys)
    return 0


def invalidate_employee_cache(employee_id: int) -> int:
    """Invalidate all cache entries for an employee."""
    patterns = [
        f"balance:employee:{employee_id}:*",
        f"profile:employee:{employee_id}",
        f"validation:employee:{employee_id}:*",
    ]
    
    total_deleted = 0
    for pattern in patterns:
        total_deleted += invalidate_cache(pattern)
    
    return total_deleted


def invalidate_policy_cache() -> int:
    """Invalidate all policy-related cache entries."""
    return invalidate_cache("policy:*")


def invalidate_org_cache() -> int:
    """Invalidate all organizational structure cache entries."""
    return invalidate_cache("org:*")


# =============================================================================
# Balance Caching
# =============================================================================

def get_balance_cache_key(employee_id: int, balance_type: str) -> str:
    """Generate cache key for balance calculation."""
    return f"balance:employee:{employee_id}:{balance_type}"


def cache_balance(
    employee_id: int,
    balance_type: str,
    balance_data: Dict[str, Any],
    ttl: int = CacheTTL.BALANCE_CALCULATION,
) -> None:
    """Cache balance calculation result."""
    cache = get_cache_client()
    key = get_balance_cache_key(employee_id, balance_type)
    cache.set(key, json.dumps(balance_data, default=str), ex=ttl)


def get_cached_balance(
    employee_id: int,
    balance_type: str,
) -> Optional[Dict[str, Any]]:
    """Get cached balance calculation."""
    cache = get_cache_client()
    key = get_balance_cache_key(employee_id, balance_type)
    cached = cache.get(key)
    if cached:
        return json.loads(cached)
    return None


# =============================================================================
# Validation Result Caching
# =============================================================================

def cache_validation_result(
    request_hash: str,
    result: Dict[str, Any],
    ttl: int = CacheTTL.VALIDATION_RESULT,
) -> None:
    """Cache validation result for identical requests."""
    cache = get_cache_client()
    key = f"validation:{request_hash}"
    cache.set(key, json.dumps(result, default=str), ex=ttl)


def get_cached_validation(request_hash: str) -> Optional[Dict[str, Any]]:
    """Get cached validation result."""
    cache = get_cache_client()
    key = f"validation:{request_hash}"
    cached = cache.get(key)
    if cached:
        return json.loads(cached)
    return None


def compute_validation_hash(request_data: Dict[str, Any]) -> str:
    """Compute hash for validation request parameters."""
    return generate_hash_key("validation", request_data)


# =============================================================================
# Policy Data Caching
# =============================================================================

def cache_policy_data(
    policy_id: str,
    policy_data: Dict[str, Any],
    ttl: int = CacheTTL.POLICY_DATA,
) -> None:
    """Cache policy constraint data."""
    cache = get_cache_client()
    key = f"policy:{policy_id}"
    cache.set(key, json.dumps(policy_data, default=str), ex=ttl)


def get_cached_policy(policy_id: str) -> Optional[Dict[str, Any]]:
    """Get cached policy data."""
    cache = get_cache_client()
    key = f"policy:{policy_id}"
    cached = cache.get(key)
    if cached:
        return json.loads(cached)
    return None


# =============================================================================
# Cache Statistics
# =============================================================================

def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics."""
    cache = get_cache_client()
    all_keys = cache.keys("*")
    
    stats = {
        "total_keys": len(all_keys),
        "by_prefix": {},
    }
    
    for key in all_keys:
        prefix = key.split(":")[0]
        stats["by_prefix"][prefix] = stats["by_prefix"].get(prefix, 0) + 1
    
    return stats

