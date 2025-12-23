"""
S3 Object Storage Service

Comprehensive S3 storage service with Boto3 integration, presigned URLs,
file validation, metadata management, and health checks.
"""

import hashlib
import logging
import mimetypes
import os
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any, BinaryIO, Dict, List, Optional, Tuple
from uuid import uuid4

try:
    import boto3
    from botocore.config import Config
    from botocore.exceptions import ClientError, BotoCoreError
except ImportError:
    boto3 = None
    Config = None
    ClientError = Exception
    BotoCoreError = Exception

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

class StorageConfig(BaseModel):
    """S3 storage configuration."""
    
    # AWS settings
    region: str = Field(
        default_factory=lambda: os.environ.get("AWS_REGION", "us-east-1"),
    )
    
    # Bucket configuration
    bucket_name: str = Field(
        default_factory=lambda: os.environ.get("S3_BUCKET_NAME", "embi-storage"),
    )
    bucket_documents: str = Field(
        default_factory=lambda: os.environ.get("S3_BUCKET_DOCUMENTS", "embi-documents"),
    )
    bucket_images: str = Field(
        default_factory=lambda: os.environ.get("S3_BUCKET_IMAGES", "embi-images"),
    )
    bucket_artifacts: str = Field(
        default_factory=lambda: os.environ.get("S3_BUCKET_ARTIFACTS", "embi-artifacts"),
    )
    
    # Upload settings
    max_file_size: int = Field(default=50 * 1024 * 1024)  # 50MB
    upload_expiry_seconds: int = Field(default=3600)  # 1 hour
    download_expiry_seconds: int = Field(default=900)  # 15 minutes
    
    # File type restrictions
    allowed_document_types: List[str] = Field(default_factory=lambda: [
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/csv",
        "text/plain",
    ])
    
    allowed_image_types: List[str] = Field(default_factory=lambda: [
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
        "image/svg+xml",
    ])
    
    # Retry configuration
    max_retries: int = Field(default=3)
    retry_delay_seconds: float = Field(default=1.0)
    
    # Health check
    health_check_timeout_seconds: int = Field(default=5)


class FileCategory(str, Enum):
    """Categories of stored files."""
    
    DOCUMENT = "document"
    IMAGE = "image"
    ARTIFACT = "artifact"
    GENERAL = "general"


# =============================================================================
# Models
# =============================================================================

class FileMetadata(BaseModel):
    """Metadata for a stored file."""
    
    key: str
    bucket: str
    original_filename: str
    file_size: int
    content_type: str
    upload_timestamp: datetime
    etag: Optional[str] = None
    checksum_md5: Optional[str] = None
    category: FileCategory = FileCategory.GENERAL
    uploader_id: Optional[str] = None
    custom_metadata: Dict[str, str] = Field(default_factory=dict)


class PresignedUploadUrl(BaseModel):
    """Presigned URL for file upload."""
    
    upload_url: str
    file_url: str
    key: str
    bucket: str
    expires_in: int
    fields: Dict[str, str] = Field(default_factory=dict)


class PresignedDownloadUrl(BaseModel):
    """Presigned URL for file download."""
    
    download_url: str
    key: str
    bucket: str
    expires_in: int
    filename: Optional[str] = None


class StorageHealthStatus(BaseModel):
    """Health status of storage service."""
    
    status: str  # healthy, degraded, unhealthy
    latency_ms: Optional[float] = None
    buckets_accessible: Dict[str, bool] = Field(default_factory=dict)
    error: Optional[str] = None
    checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UploadResult(BaseModel):
    """Result of a file upload operation."""
    
    success: bool
    key: Optional[str] = None
    bucket: Optional[str] = None
    file_url: Optional[str] = None
    metadata: Optional[FileMetadata] = None
    error: Optional[str] = None


# =============================================================================
# S3 Storage Service
# =============================================================================

class S3StorageService:
    """
    Comprehensive S3 storage service.
    
    Features:
    - Multiple bucket support for different file categories
    - Presigned URL generation for uploads and downloads
    - File validation with size and type restrictions
    - Metadata storage and retrieval
    - Health checks with timeout
    - Retry logic for network failures
    """
    
    def __init__(self, config: Optional[StorageConfig] = None):
        self.config = config or StorageConfig()
        self._client = None
        self._initialize_client()
    
    def _initialize_client(self) -> None:
        """Initialize the Boto3 S3 client."""
        if boto3 is None:
            logger.warning("boto3 not installed - using mock S3 client")
            return
        
        try:
            # Configure retry behavior
            boto_config = Config(
                retries={
                    "max_attempts": self.config.max_retries,
                    "mode": "adaptive",
                },
                connect_timeout=5,
                read_timeout=30,
            )
            
            self._client = boto3.client(
                "s3",
                region_name=self.config.region,
                config=boto_config,
            )
            
            logger.info(f"S3 client initialized for region: {self.config.region}")
            
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {str(e)}")
            self._client = None
    
    # =========================================================================
    # Bucket Selection
    # =========================================================================
    
    def _get_bucket_for_category(self, category: FileCategory) -> str:
        """Get the appropriate bucket for a file category."""
        bucket_map = {
            FileCategory.DOCUMENT: self.config.bucket_documents,
            FileCategory.IMAGE: self.config.bucket_images,
            FileCategory.ARTIFACT: self.config.bucket_artifacts,
            FileCategory.GENERAL: self.config.bucket_name,
        }
        return bucket_map.get(category, self.config.bucket_name)
    
    def _determine_category(self, content_type: str) -> FileCategory:
        """Determine file category from content type."""
        if content_type in self.config.allowed_image_types:
            return FileCategory.IMAGE
        if content_type in self.config.allowed_document_types:
            return FileCategory.DOCUMENT
        return FileCategory.GENERAL
    
    # =========================================================================
    # File Validation
    # =========================================================================
    
    def validate_file(
        self,
        filename: str,
        content_type: str,
        file_size: int,
        category: Optional[FileCategory] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate file before upload.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check file size
        if file_size > self.config.max_file_size:
            return False, f"File size {file_size} exceeds maximum {self.config.max_file_size} bytes"
        
        if file_size <= 0:
            return False, "File size must be greater than 0"
        
        # Check content type based on category
        category = category or self._determine_category(content_type)
        
        if category == FileCategory.IMAGE:
            if content_type not in self.config.allowed_image_types:
                return False, f"Image type '{content_type}' not allowed"
        elif category == FileCategory.DOCUMENT:
            if content_type not in self.config.allowed_document_types:
                return False, f"Document type '{content_type}' not allowed"
        
        # Basic filename validation
        if not filename or len(filename) > 255:
            return False, "Invalid filename"
        
        return True, None
    
    # =========================================================================
    # Presigned URLs
    # =========================================================================
    
    def generate_upload_url(
        self,
        filename: str,
        content_type: str,
        file_size: int,
        category: Optional[FileCategory] = None,
        uploader_id: Optional[str] = None,
        custom_metadata: Optional[Dict[str, str]] = None,
        expiry_seconds: Optional[int] = None,
    ) -> PresignedUploadUrl:
        """
        Generate a presigned URL for file upload.
        
        Args:
            filename: Original filename
            content_type: MIME type
            file_size: Expected file size in bytes
            category: File category for bucket selection
            uploader_id: ID of user uploading the file
            custom_metadata: Additional metadata to store
            expiry_seconds: URL expiration time (default: 1 hour)
        
        Returns:
            PresignedUploadUrl with upload details
        """
        # Validate file
        is_valid, error = self.validate_file(filename, content_type, file_size, category)
        if not is_valid:
            raise ValueError(error)
        
        # Determine category and bucket
        if category is None:
            category = self._determine_category(content_type)
        bucket = self._get_bucket_for_category(category)
        
        # Generate unique key
        timestamp = datetime.now(timezone.utc).strftime("%Y/%m/%d")
        unique_id = str(uuid4())
        extension = self._get_extension(filename)
        key = f"{category.value}s/{timestamp}/{unique_id}{extension}"
        
        expiry = expiry_seconds or self.config.upload_expiry_seconds
        
        if self._client:
            try:
                # Prepare metadata
                metadata = {
                    "original-filename": filename,
                    "upload-timestamp": datetime.now(timezone.utc).isoformat(),
                    "file-size": str(file_size),
                    "category": category.value,
                }
                if uploader_id:
                    metadata["uploader-id"] = uploader_id
                if custom_metadata:
                    metadata.update(custom_metadata)
                
                # Generate presigned URL
                presigned_url = self._client.generate_presigned_url(
                    "put_object",
                    Params={
                        "Bucket": bucket,
                        "Key": key,
                        "ContentType": content_type,
                        "Metadata": metadata,
                    },
                    ExpiresIn=expiry,
                )
                
            except ClientError as e:
                logger.error(f"Failed to generate presigned URL: {str(e)}")
                raise RuntimeError("Failed to generate upload URL")
        else:
            # Mock URL for development
            presigned_url = f"https://{bucket}.s3.{self.config.region}.amazonaws.com/{key}?mock=true"
        
        file_url = f"https://{bucket}.s3.{self.config.region}.amazonaws.com/{key}"
        
        return PresignedUploadUrl(
            upload_url=presigned_url,
            file_url=file_url,
            key=key,
            bucket=bucket,
            expires_in=expiry,
        )
    
    def generate_download_url(
        self,
        key: str,
        bucket: Optional[str] = None,
        filename: Optional[str] = None,
        expiry_seconds: Optional[int] = None,
    ) -> PresignedDownloadUrl:
        """
        Generate a presigned URL for file download.
        
        Args:
            key: S3 object key
            bucket: Bucket name (defaults to main bucket)
            filename: Optional filename for Content-Disposition
            expiry_seconds: URL expiration time (default: 15 minutes)
        
        Returns:
            PresignedDownloadUrl with download details
        """
        bucket = bucket or self.config.bucket_name
        expiry = expiry_seconds or self.config.download_expiry_seconds
        
        if self._client:
            try:
                params = {
                    "Bucket": bucket,
                    "Key": key,
                }
                
                if filename:
                    params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'
                
                presigned_url = self._client.generate_presigned_url(
                    "get_object",
                    Params=params,
                    ExpiresIn=expiry,
                )
                
            except ClientError as e:
                logger.error(f"Failed to generate download URL: {str(e)}")
                raise RuntimeError("Failed to generate download URL")
        else:
            presigned_url = f"https://{bucket}.s3.{self.config.region}.amazonaws.com/{key}?download=true&mock=true"
        
        return PresignedDownloadUrl(
            download_url=presigned_url,
            key=key,
            bucket=bucket,
            expires_in=expiry,
            filename=filename,
        )
    
    # =========================================================================
    # Direct Upload/Download
    # =========================================================================
    
    def upload_file(
        self,
        file_data: BinaryIO,
        filename: str,
        content_type: str,
        category: Optional[FileCategory] = None,
        uploader_id: Optional[str] = None,
        custom_metadata: Optional[Dict[str, str]] = None,
    ) -> UploadResult:
        """
        Upload a file directly to S3.
        
        Args:
            file_data: File-like object with file content
            filename: Original filename
            content_type: MIME type
            category: File category
            uploader_id: ID of uploader
            custom_metadata: Additional metadata
        
        Returns:
            UploadResult with upload status and metadata
        """
        # Get file size
        file_data.seek(0, 2)  # Seek to end
        file_size = file_data.tell()
        file_data.seek(0)  # Seek back to start
        
        # Validate
        is_valid, error = self.validate_file(filename, content_type, file_size, category)
        if not is_valid:
            return UploadResult(success=False, error=error)
        
        # Determine category and bucket
        if category is None:
            category = self._determine_category(content_type)
        bucket = self._get_bucket_for_category(category)
        
        # Generate key
        timestamp = datetime.now(timezone.utc).strftime("%Y/%m/%d")
        unique_id = str(uuid4())
        extension = self._get_extension(filename)
        key = f"{category.value}s/{timestamp}/{unique_id}{extension}"
        
        # Calculate checksum
        md5_hash = hashlib.md5()
        for chunk in iter(lambda: file_data.read(8192), b""):
            md5_hash.update(chunk)
        checksum = md5_hash.hexdigest()
        file_data.seek(0)
        
        if self._client:
            try:
                # Prepare metadata
                s3_metadata = {
                    "original-filename": filename,
                    "upload-timestamp": datetime.now(timezone.utc).isoformat(),
                    "checksum-md5": checksum,
                    "category": category.value,
                }
                if uploader_id:
                    s3_metadata["uploader-id"] = uploader_id
                if custom_metadata:
                    s3_metadata.update(custom_metadata)
                
                # Upload with retry
                for attempt in range(self.config.max_retries):
                    try:
                        response = self._client.put_object(
                            Bucket=bucket,
                            Key=key,
                            Body=file_data,
                            ContentType=content_type,
                            Metadata=s3_metadata,
                        )
                        break
                    except (ClientError, BotoCoreError) as e:
                        if attempt == self.config.max_retries - 1:
                            raise
                        time.sleep(self.config.retry_delay_seconds * (attempt + 1))
                        file_data.seek(0)
                
                etag = response.get("ETag", "").strip('"')
                
            except Exception as e:
                logger.error(f"Upload failed: {str(e)}")
                return UploadResult(success=False, error=str(e))
        else:
            etag = checksum
        
        file_url = f"https://{bucket}.s3.{self.config.region}.amazonaws.com/{key}"
        
        metadata = FileMetadata(
            key=key,
            bucket=bucket,
            original_filename=filename,
            file_size=file_size,
            content_type=content_type,
            upload_timestamp=datetime.now(timezone.utc),
            etag=etag,
            checksum_md5=checksum,
            category=category,
            uploader_id=uploader_id,
            custom_metadata=custom_metadata or {},
        )
        
        return UploadResult(
            success=True,
            key=key,
            bucket=bucket,
            file_url=file_url,
            metadata=metadata,
        )
    
    def get_file_metadata(self, key: str, bucket: Optional[str] = None) -> Optional[FileMetadata]:
        """Get metadata for a stored file."""
        bucket = bucket or self.config.bucket_name
        
        if not self._client:
            return None
        
        try:
            response = self._client.head_object(Bucket=bucket, Key=key)
            
            s3_metadata = response.get("Metadata", {})
            
            return FileMetadata(
                key=key,
                bucket=bucket,
                original_filename=s3_metadata.get("original-filename", key.split("/")[-1]),
                file_size=response.get("ContentLength", 0),
                content_type=response.get("ContentType", "application/octet-stream"),
                upload_timestamp=response.get("LastModified", datetime.now(timezone.utc)),
                etag=response.get("ETag", "").strip('"'),
                checksum_md5=s3_metadata.get("checksum-md5"),
                category=FileCategory(s3_metadata.get("category", "general")),
                uploader_id=s3_metadata.get("uploader-id"),
                custom_metadata={
                    k: v for k, v in s3_metadata.items()
                    if k not in ["original-filename", "upload-timestamp", "checksum-md5", "category", "uploader-id"]
                },
            )
            
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return None
            logger.error(f"Failed to get metadata: {str(e)}")
            raise
    
    def delete_file(self, key: str, bucket: Optional[str] = None) -> bool:
        """Delete a file from S3."""
        bucket = bucket or self.config.bucket_name
        
        if not self._client:
            return True
        
        try:
            self._client.delete_object(Bucket=bucket, Key=key)
            return True
        except ClientError as e:
            logger.error(f"Failed to delete file: {str(e)}")
            return False
    
    # =========================================================================
    # Health Check
    # =========================================================================
    
    def health_check(self) -> StorageHealthStatus:
        """
        Check health of S3 storage service.
        
        Verifies bucket accessibility within timeout.
        """
        start_time = time.time()
        buckets_status = {}
        error_message = None
        
        buckets_to_check = [
            self.config.bucket_name,
            self.config.bucket_documents,
            self.config.bucket_images,
            self.config.bucket_artifacts,
        ]
        
        if not self._client:
            return StorageHealthStatus(
                status="unhealthy",
                error="S3 client not initialized",
                buckets_accessible={b: False for b in buckets_to_check},
            )
        
        try:
            for bucket in buckets_to_check:
                elapsed = time.time() - start_time
                if elapsed > self.config.health_check_timeout_seconds:
                    error_message = "Health check timeout exceeded"
                    break
                
                try:
                    self._client.head_bucket(Bucket=bucket)
                    buckets_status[bucket] = True
                except ClientError:
                    buckets_status[bucket] = False
        
        except Exception as e:
            error_message = str(e)
        
        latency_ms = (time.time() - start_time) * 1000
        
        all_accessible = all(buckets_status.values()) if buckets_status else False
        
        if error_message:
            status = "unhealthy"
        elif not all_accessible:
            status = "degraded"
        else:
            status = "healthy"
        
        return StorageHealthStatus(
            status=status,
            latency_ms=round(latency_ms, 2),
            buckets_accessible=buckets_status,
            error=error_message,
        )
    
    # =========================================================================
    # Utility Methods
    # =========================================================================
    
    def _get_extension(self, filename: str) -> str:
        """Get file extension from filename."""
        if "." in filename:
            return "." + filename.rsplit(".", 1)[1].lower()
        return ""
    
    def list_files(
        self,
        bucket: Optional[str] = None,
        prefix: str = "",
        max_keys: int = 1000,
    ) -> List[Dict[str, Any]]:
        """List files in a bucket with optional prefix."""
        bucket = bucket or self.config.bucket_name
        
        if not self._client:
            return []
        
        try:
            response = self._client.list_objects_v2(
                Bucket=bucket,
                Prefix=prefix,
                MaxKeys=max_keys,
            )
            
            return [
                {
                    "key": obj["Key"],
                    "size": obj["Size"],
                    "last_modified": obj["LastModified"],
                    "etag": obj["ETag"].strip('"'),
                }
                for obj in response.get("Contents", [])
            ]
            
        except ClientError as e:
            logger.error(f"Failed to list files: {str(e)}")
            return []


# =============================================================================
# Singleton
# =============================================================================

_storage_service: Optional[S3StorageService] = None


def get_storage_service() -> S3StorageService:
    """Get the S3 storage service singleton."""
    global _storage_service
    if _storage_service is None:
        _storage_service = S3StorageService()
    return _storage_service

