"""
Caching Service

High-performance caching layer for balance calculations, session management,
and general-purpose caching with TTL management and cache invalidation.
"""

import hashlib
import json
import logging
import time
from datetime import datetime, timedelta, timezone
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union

from pydantic import BaseModel, Field

from src.infrastructure.redis.redis_client import get_redis_client, get_redis_manager

logger = logging.getLogger(__name__)

T = TypeVar("T")


# =============================================================================
# Configuration
# =============================================================================

class CachePrefix(str, Enum):
    """Cache key prefixes for different data types."""
    
    BALANCE = "balance"
    SESSION = "session"
    POLICY = "policy"
    EMPLOYEE = "employee"
    VALIDATION = "validation"
    RATE_LIMIT = "ratelimit"
    TEMP = "temp"


class CacheTTL:
    """Default TTL values for different cache types."""
    
    # Balance cache - refreshes when data changes
    BALANCE_SUMMARY = 300  # 5 minutes
    BALANCE_DETAIL = 600  # 10 minutes
    BALANCE_PROJECTION = 900  # 15 minutes
    
    # Session management
    SESSION_DEFAULT = 86400  # 24 hours
    SESSION_REMEMBER_ME = 604800  # 7 days
    
    # Policy cache
    POLICY_CONFIG = 3600  # 1 hour
    POLICY_CONSTRAINTS = 1800  # 30 minutes
    
    # Employee data
    EMPLOYEE_PROFILE = 300  # 5 minutes
    EMPLOYEE_PERMISSIONS = 600  # 10 minutes
    
    # Validation cache
    VALIDATION_RESULT = 1800  # 30 minutes
    
    # Short-lived
    TEMPORARY = 60  # 1 minute


class CacheMetrics(BaseModel):
    """Cache performance metrics."""
    
    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    errors: int = 0
    
    @property
    def hit_ratio(self) -> float:
        """Calculate cache hit ratio."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


# =============================================================================
# Caching Service
# =============================================================================

class CachingService:
    """
    High-performance caching service with TTL management,
    cache invalidation, and performance monitoring.
    """
    
    def __init__(self, prefix: str = "embi"):
        self.prefix = prefix
        self._metrics = CacheMetrics()
        self._metrics_key = f"{prefix}:cache:metrics"
    
    @property
    def redis(self):
        """Get Redis client."""
        return get_redis_client()
    
    def _make_key(self, cache_type: CachePrefix, key: str) -> str:
        """Generate a cache key with proper namespace."""
        return f"{self.prefix}:{cache_type.value}:{key}"
    
    def _serialize(self, value: Any) -> str:
        """Serialize value for storage."""
        if isinstance(value, BaseModel):
            return value.model_dump_json()
        return json.dumps(value, default=str)
    
    def _deserialize(self, data: str) -> Any:
        """Deserialize stored value."""
        try:
            return json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return data
    
    # =========================================================================
    # Core Cache Operations
    # =========================================================================
    
    def get(
        self,
        cache_type: CachePrefix,
        key: str,
        default: Any = None,
    ) -> Any:
        """
        Get a value from cache.
        
        Args:
            cache_type: Type of cached data
            key: Cache key
            default: Default value if not found
        
        Returns:
            Cached value or default
        """
        full_key = self._make_key(cache_type, key)
        
        try:
            data = self.redis.get(full_key)
            
            if data is not None:
                self._metrics.hits += 1
                return self._deserialize(data)
            
            self._metrics.misses += 1
            return default
            
        except Exception as e:
            self._metrics.errors += 1
            logger.error(f"Cache get error for {full_key}: {str(e)}")
            return default
    
    def set(
        self,
        cache_type: CachePrefix,
        key: str,
        value: Any,
        ttl_seconds: Optional[int] = None,
    ) -> bool:
        """
        Set a value in cache.
        
        Args:
            cache_type: Type of cached data
            key: Cache key
            value: Value to cache
            ttl_seconds: Time-to-live in seconds
        
        Returns:
            True if successful
        """
        full_key = self._make_key(cache_type, key)
        
        try:
            serialized = self._serialize(value)
            
            if ttl_seconds:
                result = self.redis.setex(full_key, ttl_seconds, serialized)
            else:
                result = self.redis.set(full_key, serialized)
            
            self._metrics.sets += 1
            return bool(result)
            
        except Exception as e:
            self._metrics.errors += 1
            logger.error(f"Cache set error for {full_key}: {str(e)}")
            return False
    
    def delete(self, cache_type: CachePrefix, key: str) -> bool:
        """Delete a value from cache."""
        full_key = self._make_key(cache_type, key)
        
        try:
            result = self.redis.delete(full_key)
            self._metrics.deletes += 1
            return result > 0
            
        except Exception as e:
            self._metrics.errors += 1
            logger.error(f"Cache delete error for {full_key}: {str(e)}")
            return False
    
    def exists(self, cache_type: CachePrefix, key: str) -> bool:
        """Check if key exists in cache."""
        full_key = self._make_key(cache_type, key)
        
        try:
            return self.redis.exists(full_key) > 0
        except Exception:
            return False
    
    def invalidate_pattern(self, cache_type: CachePrefix, pattern: str) -> int:
        """
        Invalidate all keys matching a pattern.
        
        Args:
            cache_type: Type of cached data
            pattern: Key pattern (supports * wildcard)
        
        Returns:
            Number of keys invalidated
        """
        full_pattern = self._make_key(cache_type, pattern)
        
        try:
            keys = self.redis.keys(full_pattern)
            if keys:
                return self.redis.delete(*keys)
            return 0
            
        except Exception as e:
            logger.error(f"Cache invalidate pattern error: {str(e)}")
            return 0
    
    # =========================================================================
    # Balance Cache Operations
    # =========================================================================
    
    def get_balance(self, employee_id: int) -> Optional[Dict[str, Any]]:
        """Get cached balance summary for an employee."""
        return self.get(CachePrefix.BALANCE, f"summary:{employee_id}")
    
    def set_balance(
        self,
        employee_id: int,
        balance_data: Dict[str, Any],
        ttl_seconds: int = CacheTTL.BALANCE_SUMMARY,
    ) -> bool:
        """
        Cache balance summary for an employee.
        
        Balance is automatically invalidated when:
        - Time-off request is submitted
        - Time-off request is approved/denied
        - Accrual runs
        - Manual adjustment made
        """
        return self.set(
            CachePrefix.BALANCE,
            f"summary:{employee_id}",
            balance_data,
            ttl_seconds,
        )
    
    def invalidate_balance(self, employee_id: int) -> bool:
        """Invalidate all balance cache for an employee."""
        patterns = [
            f"summary:{employee_id}",
            f"detail:{employee_id}*",
            f"projection:{employee_id}*",
        ]
        
        count = 0
        for pattern in patterns:
            count += self.invalidate_pattern(CachePrefix.BALANCE, pattern)
        
        logger.info(f"Invalidated {count} balance cache entries for employee {employee_id}")
        return count > 0
    
    def get_balance_projection(
        self,
        employee_id: int,
        projection_key: str,
    ) -> Optional[Dict[str, Any]]:
        """Get cached balance projection."""
        key = f"projection:{employee_id}:{projection_key}"
        return self.get(CachePrefix.BALANCE, key)
    
    def set_balance_projection(
        self,
        employee_id: int,
        projection_key: str,
        projection_data: Dict[str, Any],
        ttl_seconds: int = CacheTTL.BALANCE_PROJECTION,
    ) -> bool:
        """Cache balance projection."""
        key = f"projection:{employee_id}:{projection_key}"
        return self.set(CachePrefix.BALANCE, key, projection_data, ttl_seconds)
    
    # =========================================================================
    # Policy Cache Operations
    # =========================================================================
    
    def get_policy_constraints(self, policy_id: int) -> Optional[Dict[str, Any]]:
        """Get cached policy constraints."""
        return self.get(CachePrefix.POLICY, f"constraints:{policy_id}")
    
    def set_policy_constraints(
        self,
        policy_id: int,
        constraints: Dict[str, Any],
        ttl_seconds: int = CacheTTL.POLICY_CONSTRAINTS,
    ) -> bool:
        """Cache policy constraints."""
        return self.set(
            CachePrefix.POLICY,
            f"constraints:{policy_id}",
            constraints,
            ttl_seconds,
        )
    
    def invalidate_policy(self, policy_id: int) -> bool:
        """Invalidate all cache for a policy."""
        return self.invalidate_pattern(CachePrefix.POLICY, f"*:{policy_id}*") > 0
    
    # =========================================================================
    # Validation Cache
    # =========================================================================
    
    def get_validation_result(
        self,
        validation_type: str,
        validation_key: str,
    ) -> Optional[Dict[str, Any]]:
        """Get cached validation result."""
        key = f"{validation_type}:{validation_key}"
        return self.get(CachePrefix.VALIDATION, key)
    
    def set_validation_result(
        self,
        validation_type: str,
        validation_key: str,
        result: Dict[str, Any],
        ttl_seconds: int = CacheTTL.VALIDATION_RESULT,
    ) -> bool:
        """Cache validation result."""
        key = f"{validation_type}:{validation_key}"
        return self.set(CachePrefix.VALIDATION, key, result, ttl_seconds)
    
    # =========================================================================
    # Performance Metrics
    # =========================================================================
    
    def get_metrics(self) -> CacheMetrics:
        """Get cache performance metrics."""
        return self._metrics
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get metrics summary with hit ratio."""
        return {
            "hits": self._metrics.hits,
            "misses": self._metrics.misses,
            "sets": self._metrics.sets,
            "deletes": self._metrics.deletes,
            "errors": self._metrics.errors,
            "hit_ratio": round(self._metrics.hit_ratio * 100, 2),
            "total_operations": (
                self._metrics.hits +
                self._metrics.misses +
                self._metrics.sets +
                self._metrics.deletes
            ),
        }
    
    def reset_metrics(self) -> None:
        """Reset cache metrics."""
        self._metrics = CacheMetrics()


# =============================================================================
# Session Management
# =============================================================================

class SessionManager:
    """
    Redis-based session management with configurable timeouts.
    
    Features:
    - Secure session storage
    - Configurable TTL (default 24 hours)
    - Session data encryption support
    - Activity-based expiration extension
    """
    
    def __init__(
        self,
        prefix: str = "embi",
        default_ttl: int = CacheTTL.SESSION_DEFAULT,
    ):
        self.prefix = prefix
        self.default_ttl = default_ttl
    
    @property
    def redis(self):
        """Get Redis client."""
        return get_redis_client()
    
    def _session_key(self, session_id: str) -> str:
        """Generate session key."""
        return f"{self.prefix}:session:{session_id}"
    
    def _user_sessions_key(self, user_id: str) -> str:
        """Generate user sessions tracking key."""
        return f"{self.prefix}:user_sessions:{user_id}"
    
    def create_session(
        self,
        session_id: str,
        user_id: str,
        data: Dict[str, Any],
        ttl_seconds: Optional[int] = None,
    ) -> bool:
        """
        Create a new session.
        
        Args:
            session_id: Unique session identifier
            user_id: User identifier
            data: Session data
            ttl_seconds: Session lifetime (default: 24 hours)
        
        Returns:
            True if session was created
        """
        ttl = ttl_seconds or self.default_ttl
        session_key = self._session_key(session_id)
        
        session_data = {
            "user_id": user_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_activity": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }
        
        try:
            # Store session
            self.redis.setex(
                session_key,
                ttl,
                json.dumps(session_data),
            )
            
            # Track user's sessions
            user_sessions_key = self._user_sessions_key(user_id)
            self.redis.hset(user_sessions_key, session_id, datetime.now(timezone.utc).isoformat())
            self.redis.expire(user_sessions_key, ttl * 2)  # Keep tracking a bit longer
            
            logger.debug(f"Created session {session_id} for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create session: {str(e)}")
            return False
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data."""
        session_key = self._session_key(session_id)
        
        try:
            data = self.redis.get(session_key)
            if data:
                return json.loads(data)
            return None
            
        except Exception as e:
            logger.error(f"Failed to get session: {str(e)}")
            return None
    
    def update_session(
        self,
        session_id: str,
        data: Dict[str, Any],
        extend_ttl: bool = True,
    ) -> bool:
        """
        Update session data.
        
        Args:
            session_id: Session identifier
            data: New session data
            extend_ttl: Whether to extend session lifetime
        
        Returns:
            True if session was updated
        """
        session_key = self._session_key(session_id)
        
        try:
            existing = self.get_session(session_id)
            if not existing:
                return False
            
            existing["data"].update(data)
            existing["last_activity"] = datetime.now(timezone.utc).isoformat()
            
            if extend_ttl:
                ttl = self.redis.ttl(session_key)
                if ttl > 0:
                    self.redis.setex(session_key, max(ttl, self.default_ttl), json.dumps(existing))
                else:
                    self.redis.setex(session_key, self.default_ttl, json.dumps(existing))
            else:
                # Keep existing TTL
                ttl = self.redis.ttl(session_key)
                if ttl > 0:
                    self.redis.setex(session_key, ttl, json.dumps(existing))
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update session: {str(e)}")
            return False
    
    def touch_session(self, session_id: str) -> bool:
        """Extend session TTL based on activity."""
        session_key = self._session_key(session_id)
        
        try:
            existing = self.get_session(session_id)
            if not existing:
                return False
            
            existing["last_activity"] = datetime.now(timezone.utc).isoformat()
            self.redis.setex(session_key, self.default_ttl, json.dumps(existing))
            return True
            
        except Exception as e:
            logger.error(f"Failed to touch session: {str(e)}")
            return False
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        session_key = self._session_key(session_id)
        
        try:
            # Get user ID before deleting
            session = self.get_session(session_id)
            
            # Delete session
            result = self.redis.delete(session_key) > 0
            
            # Remove from user's sessions tracking
            if session and result:
                user_sessions_key = self._user_sessions_key(session["user_id"])
                self.redis.hdel(user_sessions_key, session_id)
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to delete session: {str(e)}")
            return False
    
    def delete_user_sessions(self, user_id: str) -> int:
        """Delete all sessions for a user."""
        user_sessions_key = self._user_sessions_key(user_id)
        
        try:
            sessions = self.redis.hgetall(user_sessions_key)
            count = 0
            
            for session_id in sessions.keys():
                if self.delete_session(session_id):
                    count += 1
            
            self.redis.delete(user_sessions_key)
            
            logger.info(f"Deleted {count} sessions for user {user_id}")
            return count
            
        except Exception as e:
            logger.error(f"Failed to delete user sessions: {str(e)}")
            return 0
    
    def get_user_sessions(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all active sessions for a user."""
        user_sessions_key = self._user_sessions_key(user_id)
        
        try:
            session_ids = self.redis.hgetall(user_sessions_key)
            sessions = []
            
            for session_id in session_ids.keys():
                session = self.get_session(session_id)
                if session:
                    session["session_id"] = session_id
                    sessions.append(session)
            
            return sessions
            
        except Exception as e:
            logger.error(f"Failed to get user sessions: {str(e)}")
            return []


# =============================================================================
# Cache Decorator
# =============================================================================

def cached(
    cache_type: CachePrefix,
    ttl_seconds: int = 300,
    key_builder: Optional[Callable[..., str]] = None,
):
    """
    Decorator for caching function results.
    
    Args:
        cache_type: Type of cache to use
        ttl_seconds: Cache TTL
        key_builder: Optional function to build cache key from args
    
    Example:
        @cached(CachePrefix.BALANCE, ttl_seconds=300)
        def get_employee_balance(employee_id: int):
            # ... expensive calculation
            return balance
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        cache_service = CachingService()
        
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            # Build cache key
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                key_parts = [func.__name__]
                key_parts.extend(str(arg) for arg in args)
                key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
                cache_key = ":".join(key_parts)
            
            # Try to get from cache
            cached_value = cache_service.get(cache_type, cache_key)
            if cached_value is not None:
                return cached_value
            
            # Call function and cache result
            result = func(*args, **kwargs)
            cache_service.set(cache_type, cache_key, result, ttl_seconds)
            
            return result
        
        return wrapper
    return decorator


# =============================================================================
# Convenience Functions
# =============================================================================

_cache_service: Optional[CachingService] = None
_session_manager: Optional[SessionManager] = None


def get_cache_service() -> CachingService:
    """Get the caching service singleton."""
    global _cache_service
    if _cache_service is None:
        _cache_service = CachingService()
    return _cache_service


def get_session_manager() -> SessionManager:
    """Get the session manager singleton."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager

