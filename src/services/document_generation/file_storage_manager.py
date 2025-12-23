"""File storage manager for secure file handling and temporary file management."""

import hashlib
import logging
import os
import shutil
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional, Union
import threading

logger = logging.getLogger(__name__)


class StorageBackend(str, Enum):
    """Storage backend types."""
    LOCAL = "local"
    S3 = "s3"
    MEMORY = "memory"


class StorageError(Exception):
    """Exception raised for storage operations."""
    pass


@dataclass
class StoredFile:
    """Represents a stored file."""
    id: str
    filename: str
    content_type: str
    size_bytes: int
    storage_path: str
    hash_value: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at


@dataclass
class StorageConfig:
    """Configuration for file storage."""
    backend: StorageBackend = StorageBackend.LOCAL
    base_path: str = ""
    temp_path: str = ""
    max_file_size: int = 100 * 1024 * 1024  # 100MB
    default_ttl_hours: int = 24
    cleanup_interval_minutes: int = 60
    s3_bucket: Optional[str] = None
    s3_prefix: str = "uploads/"
    
    def __post_init__(self):
        if not self.base_path:
            self.base_path = os.path.join(tempfile.gettempdir(), "file_storage")
        if not self.temp_path:
            self.temp_path = os.path.join(self.base_path, "temp")


class FileStorageManager:
    """
    Service for managing file storage with secure upload, download, and cleanup.
    
    Features:
    - Secure file storage with hash verification
    - Temporary file management with automatic cleanup
    - Support for local and S3 storage backends
    - File expiration and TTL management
    - Atomic file operations
    """
    
    def __init__(self, config: Optional[StorageConfig] = None):
        """
        Initialize the file storage manager.
        
        Args:
            config: Storage configuration
        """
        self.config = config or StorageConfig()
        self._files: Dict[str, StoredFile] = {}
        self._memory_store: Dict[str, bytes] = {}
        self._lock = threading.Lock()
        self._cleanup_thread: Optional[threading.Thread] = None
        self._running = False
        
        # Initialize storage directories
        self._init_storage()
    
    def _init_storage(self) -> None:
        """Initialize storage directories."""
        if self.config.backend == StorageBackend.LOCAL:
            os.makedirs(self.config.base_path, exist_ok=True)
            os.makedirs(self.config.temp_path, exist_ok=True)
            logger.info(f"Initialized local storage at {self.config.base_path}")
    
    def start_cleanup_worker(self) -> None:
        """Start background cleanup worker."""
        if self._cleanup_thread is not None:
            return
        
        self._running = True
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_thread.start()
        logger.info("Started cleanup worker")
    
    def stop_cleanup_worker(self) -> None:
        """Stop background cleanup worker."""
        self._running = False
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5)
            self._cleanup_thread = None
        logger.info("Stopped cleanup worker")
    
    def _cleanup_loop(self) -> None:
        """Background cleanup loop."""
        while self._running:
            try:
                self.cleanup_expired()
            except Exception as e:
                logger.error(f"Cleanup error: {e}")
            
            # Wait for next cleanup interval
            import time
            time.sleep(self.config.cleanup_interval_minutes * 60)
    
    def store(
        self,
        content: Union[bytes, BinaryIO],
        filename: str,
        content_type: str = "application/octet-stream",
        ttl_hours: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> StoredFile:
        """
        Store a file.
        
        Args:
            content: File content as bytes or file-like object
            filename: Original filename
            content_type: MIME type
            ttl_hours: Time-to-live in hours (None for permanent)
            metadata: Optional metadata to store with file
            
        Returns:
            StoredFile object
            
        Raises:
            StorageError: If storage operation fails
        """
        # Read content if file-like object
        if hasattr(content, 'read'):
            content = content.read()
        
        # Validate size
        if len(content) > self.config.max_file_size:
            raise StorageError(
                f"File exceeds maximum size of {self.config.max_file_size} bytes"
            )
        
        # Generate file ID and hash
        file_id = str(uuid.uuid4())
        file_hash = hashlib.sha256(content).hexdigest()
        
        # Calculate expiration
        ttl = ttl_hours if ttl_hours is not None else self.config.default_ttl_hours
        expires_at = datetime.utcnow() + timedelta(hours=ttl) if ttl > 0 else None
        
        # Determine storage path
        storage_path = self._get_storage_path(file_id, filename)
        
        # Store file
        if self.config.backend == StorageBackend.LOCAL:
            self._store_local(storage_path, content)
        elif self.config.backend == StorageBackend.S3:
            self._store_s3(storage_path, content, content_type)
        elif self.config.backend == StorageBackend.MEMORY:
            self._store_memory(file_id, content)
        
        # Create stored file record
        stored_file = StoredFile(
            id=file_id,
            filename=filename,
            content_type=content_type,
            size_bytes=len(content),
            storage_path=storage_path,
            hash_value=file_hash,
            expires_at=expires_at,
            metadata=metadata or {},
        )
        
        with self._lock:
            self._files[file_id] = stored_file
        
        logger.info(f"Stored file: {filename} ({file_id})")
        return stored_file
    
    def store_temp(
        self,
        content: Union[bytes, BinaryIO],
        filename: str,
        content_type: str = "application/octet-stream",
        ttl_hours: int = 1
    ) -> StoredFile:
        """
        Store a temporary file with short TTL.
        
        Args:
            content: File content
            filename: Original filename
            content_type: MIME type
            ttl_hours: Time-to-live (default 1 hour)
            
        Returns:
            StoredFile object
        """
        return self.store(
            content=content,
            filename=filename,
            content_type=content_type,
            ttl_hours=ttl_hours,
            metadata={"temp": True}
        )
    
    def retrieve(self, file_id: str) -> Optional[bytes]:
        """
        Retrieve file content.
        
        Args:
            file_id: File identifier
            
        Returns:
            File content as bytes or None if not found
        """
        stored_file = self.get_file_info(file_id)
        if not stored_file:
            return None
        
        if stored_file.is_expired:
            self.delete(file_id)
            return None
        
        if self.config.backend == StorageBackend.LOCAL:
            return self._retrieve_local(stored_file.storage_path)
        elif self.config.backend == StorageBackend.S3:
            return self._retrieve_s3(stored_file.storage_path)
        elif self.config.backend == StorageBackend.MEMORY:
            return self._retrieve_memory(file_id)
        
        return None
    
    def retrieve_stream(self, file_id: str) -> Optional[BinaryIO]:
        """
        Retrieve file as a stream.
        
        Args:
            file_id: File identifier
            
        Returns:
            File stream or None if not found
        """
        content = self.retrieve(file_id)
        if content:
            import io
            return io.BytesIO(content)
        return None
    
    def get_file_info(self, file_id: str) -> Optional[StoredFile]:
        """
        Get file information without retrieving content.
        
        Args:
            file_id: File identifier
            
        Returns:
            StoredFile or None if not found
        """
        with self._lock:
            return self._files.get(file_id)
    
    def delete(self, file_id: str) -> bool:
        """
        Delete a stored file.
        
        Args:
            file_id: File identifier
            
        Returns:
            True if deleted, False if not found
        """
        with self._lock:
            stored_file = self._files.pop(file_id, None)
        
        if not stored_file:
            return False
        
        try:
            if self.config.backend == StorageBackend.LOCAL:
                self._delete_local(stored_file.storage_path)
            elif self.config.backend == StorageBackend.S3:
                self._delete_s3(stored_file.storage_path)
            elif self.config.backend == StorageBackend.MEMORY:
                self._delete_memory(file_id)
            
            logger.info(f"Deleted file: {stored_file.filename} ({file_id})")
            return True
        except Exception as e:
            logger.error(f"Error deleting file {file_id}: {e}")
            return False
    
    def cleanup_expired(self) -> int:
        """
        Remove all expired files.
        
        Returns:
            Number of files cleaned up
        """
        expired_ids = []
        
        with self._lock:
            for file_id, stored_file in self._files.items():
                if stored_file.is_expired:
                    expired_ids.append(file_id)
        
        for file_id in expired_ids:
            self.delete(file_id)
        
        if expired_ids:
            logger.info(f"Cleaned up {len(expired_ids)} expired files")
        
        return len(expired_ids)
    
    def list_files(
        self,
        include_expired: bool = False,
        prefix: Optional[str] = None
    ) -> List[StoredFile]:
        """
        List stored files.
        
        Args:
            include_expired: Include expired files
            prefix: Filter by filename prefix
            
        Returns:
            List of StoredFile objects
        """
        with self._lock:
            files = list(self._files.values())
        
        if not include_expired:
            files = [f for f in files if not f.is_expired]
        
        if prefix:
            files = [f for f in files if f.filename.startswith(prefix)]
        
        return files
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """
        Get storage statistics.
        
        Returns:
            Dictionary with storage statistics
        """
        with self._lock:
            files = list(self._files.values())
        
        total_size = sum(f.size_bytes for f in files)
        expired_count = sum(1 for f in files if f.is_expired)
        
        return {
            "total_files": len(files),
            "total_size_bytes": total_size,
            "expired_files": expired_count,
            "backend": self.config.backend.value,
            "base_path": self.config.base_path,
        }
    
    def _get_storage_path(self, file_id: str, filename: str) -> str:
        """Generate storage path for a file."""
        # Use first 2 chars of ID for directory sharding
        shard_dir = file_id[:2]
        safe_filename = self._sanitize_filename(filename)
        
        if self.config.backend == StorageBackend.LOCAL:
            return os.path.join(self.config.base_path, shard_dir, f"{file_id}_{safe_filename}")
        elif self.config.backend == StorageBackend.S3:
            return f"{self.config.s3_prefix}{shard_dir}/{file_id}_{safe_filename}"
        else:
            return file_id
    
    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for storage."""
        # Remove path components
        filename = os.path.basename(filename)
        # Replace unsafe characters
        safe_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-_"
        return "".join(c if c in safe_chars else "_" for c in filename)
    
    def _store_local(self, path: str, content: bytes) -> None:
        """Store file locally."""
        # Create directory if needed
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        # Write atomically using temp file
        temp_path = f"{path}.tmp"
        try:
            with open(temp_path, 'wb') as f:
                f.write(content)
            shutil.move(temp_path, path)
        except Exception:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise
    
    def _retrieve_local(self, path: str) -> Optional[bytes]:
        """Retrieve file from local storage."""
        if not os.path.exists(path):
            return None
        with open(path, 'rb') as f:
            return f.read()
    
    def _delete_local(self, path: str) -> None:
        """Delete file from local storage."""
        if os.path.exists(path):
            os.remove(path)
    
    def _store_s3(self, path: str, content: bytes, content_type: str) -> None:
        """Store file in S3."""
        try:
            import boto3
            s3 = boto3.client('s3')
            s3.put_object(
                Bucket=self.config.s3_bucket,
                Key=path,
                Body=content,
                ContentType=content_type,
            )
        except ImportError:
            raise StorageError("boto3 not installed for S3 storage")
        except Exception as e:
            raise StorageError(f"S3 upload failed: {e}")
    
    def _retrieve_s3(self, path: str) -> Optional[bytes]:
        """Retrieve file from S3."""
        try:
            import boto3
            s3 = boto3.client('s3')
            response = s3.get_object(
                Bucket=self.config.s3_bucket,
                Key=path,
            )
            return response['Body'].read()
        except ImportError:
            raise StorageError("boto3 not installed for S3 storage")
        except Exception as e:
            logger.error(f"S3 retrieval failed: {e}")
            return None
    
    def _delete_s3(self, path: str) -> None:
        """Delete file from S3."""
        try:
            import boto3
            s3 = boto3.client('s3')
            s3.delete_object(
                Bucket=self.config.s3_bucket,
                Key=path,
            )
        except ImportError:
            raise StorageError("boto3 not installed for S3 storage")
        except Exception as e:
            logger.error(f"S3 deletion failed: {e}")
    
    def _store_memory(self, file_id: str, content: bytes) -> None:
        """Store file in memory."""
        self._memory_store[file_id] = content
    
    def _retrieve_memory(self, file_id: str) -> Optional[bytes]:
        """Retrieve file from memory."""
        return self._memory_store.get(file_id)
    
    def _delete_memory(self, file_id: str) -> None:
        """Delete file from memory."""
        self._memory_store.pop(file_id, None)
    
    def verify_integrity(self, file_id: str) -> bool:
        """
        Verify file integrity by comparing hash.
        
        Args:
            file_id: File identifier
            
        Returns:
            True if file integrity is valid
        """
        stored_file = self.get_file_info(file_id)
        if not stored_file:
            return False
        
        content = self.retrieve(file_id)
        if not content:
            return False
        
        current_hash = hashlib.sha256(content).hexdigest()
        return current_hash == stored_file.hash_value
    
    def copy(self, file_id: str, new_filename: Optional[str] = None) -> Optional[StoredFile]:
        """
        Create a copy of a stored file.
        
        Args:
            file_id: Source file identifier
            new_filename: New filename (optional)
            
        Returns:
            New StoredFile or None if source not found
        """
        stored_file = self.get_file_info(file_id)
        if not stored_file:
            return None
        
        content = self.retrieve(file_id)
        if not content:
            return None
        
        return self.store(
            content=content,
            filename=new_filename or stored_file.filename,
            content_type=stored_file.content_type,
            metadata=stored_file.metadata.copy(),
        )
    
    def move_to_permanent(self, file_id: str) -> Optional[StoredFile]:
        """
        Move a temporary file to permanent storage.
        
        Args:
            file_id: File identifier
            
        Returns:
            Updated StoredFile or None if not found
        """
        with self._lock:
            stored_file = self._files.get(file_id)
            if stored_file:
                stored_file.expires_at = None
                stored_file.metadata.pop("temp", None)
                return stored_file
        return None

