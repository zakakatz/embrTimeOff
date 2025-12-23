"""
Redis Client Configuration

Provides Redis connectivity with connection pooling, automatic reconnection,
and cluster support for high availability.
"""

import logging
import os
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse

try:
    import redis
    from redis import RedisCluster
    from redis.exceptions import RedisError, ConnectionError as RedisConnectionError
    from redis.sentinel import Sentinel
except ImportError:
    redis = None
    RedisCluster = None
    Sentinel = None

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration Models
# =============================================================================

class RedisConfig(BaseModel):
    """Redis connection configuration."""
    
    # Connection settings
    host: str = Field(default="localhost", description="Redis host")
    port: int = Field(default=6379, description="Redis port")
    password: Optional[str] = Field(default=None, description="Redis password")
    db: int = Field(default=0, description="Redis database number")
    
    # SSL/TLS
    ssl: bool = Field(default=False, description="Enable SSL/TLS")
    ssl_cert_reqs: Optional[str] = Field(default=None)
    
    # Connection pool
    max_connections: int = Field(default=50, description="Max pool connections")
    socket_timeout: float = Field(default=5.0, description="Socket timeout in seconds")
    socket_connect_timeout: float = Field(default=5.0, description="Connect timeout")
    retry_on_timeout: bool = Field(default=True, description="Retry on timeout")
    
    # Cluster settings
    cluster_mode: bool = Field(default=False, description="Use Redis cluster")
    cluster_nodes: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Cluster nodes for cluster mode",
    )
    
    # Sentinel settings
    sentinel_mode: bool = Field(default=False, description="Use Redis Sentinel")
    sentinel_master: str = Field(default="mymaster", description="Sentinel master name")
    sentinel_nodes: List[Dict[str, int]] = Field(
        default_factory=list,
        description="Sentinel nodes [(host, port), ...]",
    )
    
    # Health check
    health_check_interval: int = Field(default=30, description="Health check interval")

    class Config:
        env_prefix = "REDIS_"


# =============================================================================
# Redis Client Manager
# =============================================================================

class RedisClientManager:
    """
    Manages Redis connections with support for:
    - Standalone Redis
    - Redis Cluster
    - Redis Sentinel
    
    Features automatic reconnection, connection pooling, and health monitoring.
    """
    
    _instance: Optional["RedisClientManager"] = None
    
    def __init__(self, config: Optional[RedisConfig] = None):
        self.config = config or self._load_config_from_env()
        self._client: Optional[Any] = None
        self._pool: Optional[Any] = None
        self._is_connected = False
        self._connection_errors = 0
        self._max_retries = 3
    
    @classmethod
    def get_instance(cls, config: Optional[RedisConfig] = None) -> "RedisClientManager":
        """Get singleton instance of RedisClientManager."""
        if cls._instance is None:
            cls._instance = cls(config)
        return cls._instance
    
    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (for testing)."""
        if cls._instance is not None:
            cls._instance.close()
            cls._instance = None
    
    def _load_config_from_env(self) -> RedisConfig:
        """Load Redis configuration from environment variables."""
        redis_url = os.environ.get("REDIS_URL")
        
        if redis_url:
            parsed = urlparse(redis_url)
            return RedisConfig(
                host=parsed.hostname or "localhost",
                port=parsed.port or 6379,
                password=parsed.password,
                db=int(parsed.path.lstrip("/") or 0),
                ssl=parsed.scheme == "rediss",
            )
        
        return RedisConfig(
            host=os.environ.get("REDIS_HOST", "localhost"),
            port=int(os.environ.get("REDIS_PORT", "6379")),
            password=os.environ.get("REDIS_PASSWORD"),
            db=int(os.environ.get("REDIS_DB", "0")),
            ssl=os.environ.get("REDIS_SSL", "").lower() == "true",
            cluster_mode=os.environ.get("REDIS_CLUSTER_MODE", "").lower() == "true",
        )
    
    def connect(self) -> None:
        """Establish connection to Redis."""
        if redis is None:
            logger.warning("Redis package not installed - using mock client")
            self._client = MockRedisClient()
            self._is_connected = True
            return
        
        try:
            if self.config.cluster_mode:
                self._connect_cluster()
            elif self.config.sentinel_mode:
                self._connect_sentinel()
            else:
                self._connect_standalone()
            
            # Test connection
            self._client.ping()
            self._is_connected = True
            self._connection_errors = 0
            logger.info("Successfully connected to Redis")
            
        except Exception as e:
            self._is_connected = False
            self._connection_errors += 1
            logger.error(f"Failed to connect to Redis: {str(e)}")
            raise
    
    def _connect_standalone(self) -> None:
        """Connect to standalone Redis instance."""
        self._pool = redis.ConnectionPool(
            host=self.config.host,
            port=self.config.port,
            password=self.config.password,
            db=self.config.db,
            max_connections=self.config.max_connections,
            socket_timeout=self.config.socket_timeout,
            socket_connect_timeout=self.config.socket_connect_timeout,
            retry_on_timeout=self.config.retry_on_timeout,
            decode_responses=True,
            health_check_interval=self.config.health_check_interval,
        )
        
        self._client = redis.Redis(connection_pool=self._pool)
    
    def _connect_cluster(self) -> None:
        """Connect to Redis Cluster."""
        if not self.config.cluster_nodes:
            self.config.cluster_nodes = [
                {"host": self.config.host, "port": self.config.port}
            ]
        
        startup_nodes = [
            redis.cluster.ClusterNode(node["host"], node["port"])
            for node in self.config.cluster_nodes
        ]
        
        self._client = RedisCluster(
            startup_nodes=startup_nodes,
            password=self.config.password,
            decode_responses=True,
            skip_full_coverage_check=True,
        )
    
    def _connect_sentinel(self) -> None:
        """Connect via Redis Sentinel."""
        if not self.config.sentinel_nodes:
            raise ValueError("Sentinel nodes must be configured for sentinel mode")
        
        sentinel = Sentinel(
            self.config.sentinel_nodes,
            socket_timeout=self.config.socket_timeout,
        )
        
        self._client = sentinel.master_for(
            self.config.sentinel_master,
            socket_timeout=self.config.socket_timeout,
            password=self.config.password,
            decode_responses=True,
        )
    
    @property
    def client(self) -> Any:
        """Get Redis client, connecting if necessary."""
        if not self._is_connected or self._client is None:
            self.connect()
        return self._client
    
    def close(self) -> None:
        """Close Redis connection."""
        if self._client is not None:
            try:
                self._client.close()
            except Exception as e:
                logger.warning(f"Error closing Redis client: {str(e)}")
            finally:
                self._client = None
                self._is_connected = False
        
        if self._pool is not None:
            try:
                self._pool.disconnect()
            except Exception:
                pass
            finally:
                self._pool = None
    
    def is_connected(self) -> bool:
        """Check if Redis is connected."""
        if not self._is_connected or self._client is None:
            return False
        
        try:
            self._client.ping()
            return True
        except Exception:
            self._is_connected = False
            return False
    
    @contextmanager
    def pipeline(self, transaction: bool = True):
        """Get a Redis pipeline for batch operations."""
        pipe = self.client.pipeline(transaction=transaction)
        try:
            yield pipe
            pipe.execute()
        except Exception:
            raise
        finally:
            pass
    
    def health_check(self, timeout_seconds: float = 3.0) -> Dict[str, Any]:
        """
        Perform health check on Redis connection.
        
        Returns status within the specified timeout.
        """
        import time
        
        start_time = time.time()
        result = {
            "status": "unknown",
            "latency_ms": None,
            "connected": False,
            "cluster_mode": self.config.cluster_mode,
            "error": None,
        }
        
        try:
            # Ping with timeout
            ping_start = time.time()
            pong = self.client.ping()
            ping_end = time.time()
            
            elapsed = time.time() - start_time
            if elapsed > timeout_seconds:
                result["status"] = "degraded"
                result["error"] = f"Health check took {elapsed:.2f}s (limit: {timeout_seconds}s)"
            else:
                result["status"] = "healthy"
            
            result["connected"] = pong
            result["latency_ms"] = round((ping_end - ping_start) * 1000, 2)
            
            # Get additional info
            info = self.client.info("server")
            result["redis_version"] = info.get("redis_version")
            result["uptime_seconds"] = info.get("uptime_in_seconds")
            
        except Exception as e:
            result["status"] = "unhealthy"
            result["connected"] = False
            result["error"] = str(e)
        
        return result


# =============================================================================
# Mock Redis Client (for development without Redis)
# =============================================================================

class MockRedisClient:
    """Mock Redis client for development and testing."""
    
    def __init__(self):
        self._data: Dict[str, Any] = {}
        self._expiry: Dict[str, float] = {}
    
    def ping(self) -> bool:
        return True
    
    def get(self, key: str) -> Optional[str]:
        import time
        if key in self._expiry and time.time() > self._expiry[key]:
            del self._data[key]
            del self._expiry[key]
            return None
        return self._data.get(key)
    
    def set(
        self,
        key: str,
        value: Any,
        ex: Optional[int] = None,
        px: Optional[int] = None,
        nx: bool = False,
        xx: bool = False,
    ) -> bool:
        import time
        
        if nx and key in self._data:
            return False
        if xx and key not in self._data:
            return False
        
        self._data[key] = str(value)
        
        if ex:
            self._expiry[key] = time.time() + ex
        elif px:
            self._expiry[key] = time.time() + (px / 1000)
        
        return True
    
    def setex(self, key: str, seconds: int, value: Any) -> bool:
        return self.set(key, value, ex=seconds)
    
    def delete(self, *keys: str) -> int:
        count = 0
        for key in keys:
            if key in self._data:
                del self._data[key]
                self._expiry.pop(key, None)
                count += 1
        return count
    
    def exists(self, *keys: str) -> int:
        return sum(1 for key in keys if key in self._data)
    
    def expire(self, key: str, seconds: int) -> bool:
        import time
        if key in self._data:
            self._expiry[key] = time.time() + seconds
            return True
        return False
    
    def ttl(self, key: str) -> int:
        import time
        if key not in self._data:
            return -2
        if key not in self._expiry:
            return -1
        ttl = int(self._expiry[key] - time.time())
        return max(ttl, 0)
    
    def incr(self, key: str) -> int:
        value = int(self._data.get(key, 0)) + 1
        self._data[key] = str(value)
        return value
    
    def incrby(self, key: str, amount: int) -> int:
        value = int(self._data.get(key, 0)) + amount
        self._data[key] = str(value)
        return value
    
    def hget(self, name: str, key: str) -> Optional[str]:
        hash_data = self._data.get(name, {})
        if isinstance(hash_data, dict):
            return hash_data.get(key)
        return None
    
    def hset(self, name: str, key: str = None, value: Any = None, mapping: Dict = None) -> int:
        if name not in self._data or not isinstance(self._data[name], dict):
            self._data[name] = {}
        
        count = 0
        if key is not None and value is not None:
            self._data[name][key] = str(value)
            count += 1
        
        if mapping:
            for k, v in mapping.items():
                self._data[name][k] = str(v)
                count += 1
        
        return count
    
    def hgetall(self, name: str) -> Dict[str, str]:
        return self._data.get(name, {})
    
    def hdel(self, name: str, *keys: str) -> int:
        if name not in self._data:
            return 0
        
        count = 0
        for key in keys:
            if key in self._data[name]:
                del self._data[name][key]
                count += 1
        return count
    
    def keys(self, pattern: str = "*") -> List[str]:
        import fnmatch
        return [k for k in self._data.keys() if fnmatch.fnmatch(k, pattern)]
    
    def flushdb(self) -> bool:
        self._data.clear()
        self._expiry.clear()
        return True
    
    def info(self, section: str = None) -> Dict[str, Any]:
        return {
            "redis_version": "mock-7.0.0",
            "uptime_in_seconds": 0,
        }
    
    def pipeline(self, transaction: bool = True) -> "MockPipeline":
        return MockPipeline(self)
    
    def close(self) -> None:
        pass


class MockPipeline:
    """Mock Redis pipeline."""
    
    def __init__(self, client: MockRedisClient):
        self._client = client
        self._commands: List[tuple] = []
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
    
    def get(self, key: str) -> "MockPipeline":
        self._commands.append(("get", key))
        return self
    
    def set(self, key: str, value: Any, **kwargs) -> "MockPipeline":
        self._commands.append(("set", key, value, kwargs))
        return self
    
    def delete(self, *keys: str) -> "MockPipeline":
        self._commands.append(("delete", keys))
        return self
    
    def execute(self) -> List[Any]:
        results = []
        for cmd in self._commands:
            if cmd[0] == "get":
                results.append(self._client.get(cmd[1]))
            elif cmd[0] == "set":
                results.append(self._client.set(cmd[1], cmd[2], **cmd[3]))
            elif cmd[0] == "delete":
                results.append(self._client.delete(*cmd[1]))
        self._commands.clear()
        return results


# =============================================================================
# Convenience Functions
# =============================================================================

def get_redis_client() -> Any:
    """Get the Redis client instance."""
    return RedisClientManager.get_instance().client


def get_redis_manager() -> RedisClientManager:
    """Get the Redis client manager instance."""
    return RedisClientManager.get_instance()


def redis_health_check() -> Dict[str, Any]:
    """Perform a Redis health check."""
    return RedisClientManager.get_instance().health_check()

