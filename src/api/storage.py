"""
Storage API Endpoints

Provides file storage operations via S3 with presigned URLs.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.infrastructure.storage.s3_storage import (
    S3StorageService,
    FileCategory,
    FileMetadata,
    PresignedUploadUrl,
    PresignedDownloadUrl,
    StorageHealthStatus,
    get_storage_service,
)

router = APIRouter(prefix="/api/v1/storage", tags=["Storage"])


# =============================================================================
# Request/Response Models
# =============================================================================

class UploadUrlRequest(BaseModel):
    """Request for presigned upload URL."""
    
    filename: str = Field(..., min_length=1, max_length=255)
    contentType: str = Field(..., description="MIME type")
    fileSize: int = Field(..., gt=0, description="File size in bytes")
    category: Optional[str] = Field(None, description="File category: document, image, artifact")
    metadata: Optional[Dict[str, str]] = Field(None, description="Custom metadata")


class DownloadUrlRequest(BaseModel):
    """Request for presigned download URL."""
    
    key: str = Field(..., description="S3 object key")
    bucket: Optional[str] = Field(None, description="Bucket name")
    filename: Optional[str] = Field(None, description="Filename for download")


class UploadUrlResponse(BaseModel):
    """Response with presigned upload URL."""
    
    uploadUrl: str
    fileUrl: str
    key: str
    bucket: str
    expiresIn: int


class DownloadUrlResponse(BaseModel):
    """Response with presigned download URL."""
    
    downloadUrl: str
    key: str
    bucket: str
    expiresIn: int
    filename: Optional[str] = None


class FileMetadataResponse(BaseModel):
    """Response with file metadata."""
    
    key: str
    bucket: str
    originalFilename: str
    fileSize: int
    contentType: str
    uploadTimestamp: datetime
    category: str
    etag: Optional[str] = None
    checksum: Optional[str] = None
    uploaderId: Optional[str] = None
    customMetadata: Dict[str, str] = Field(default_factory=dict)


class StorageHealthResponse(BaseModel):
    """Storage health check response."""
    
    status: str
    latencyMs: Optional[float] = None
    bucketsAccessible: Dict[str, bool]
    error: Optional[str] = None
    checkedAt: datetime


# =============================================================================
# Endpoints
# =============================================================================

@router.post(
    "/upload-url",
    response_model=UploadUrlResponse,
    summary="Get presigned upload URL",
    description="Generate a presigned URL for direct file upload to S3",
)
async def get_upload_url(
    request: UploadUrlRequest,
    storage: S3StorageService = Depends(get_storage_service),
) -> UploadUrlResponse:
    """
    Generate a presigned URL for file upload.
    
    The client can use the returned URL to PUT the file directly to S3.
    """
    try:
        category = None
        if request.category:
            try:
                category = FileCategory(request.category)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid category: {request.category}"
                )
        
        result = storage.generate_upload_url(
            filename=request.filename,
            content_type=request.contentType,
            file_size=request.fileSize,
            category=category,
            custom_metadata=request.metadata,
        )
        
        return UploadUrlResponse(
            uploadUrl=result.upload_url,
            fileUrl=result.file_url,
            key=result.key,
            bucket=result.bucket,
            expiresIn=result.expires_in,
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/download-url",
    response_model=DownloadUrlResponse,
    summary="Get presigned download URL",
    description="Generate a presigned URL for file download from S3",
)
async def get_download_url(
    request: DownloadUrlRequest,
    storage: S3StorageService = Depends(get_storage_service),
) -> DownloadUrlResponse:
    """
    Generate a presigned URL for file download.
    
    The URL will be valid for 15 minutes by default.
    """
    try:
        result = storage.generate_download_url(
            key=request.key,
            bucket=request.bucket,
            filename=request.filename,
        )
        
        return DownloadUrlResponse(
            downloadUrl=result.download_url,
            key=result.key,
            bucket=result.bucket,
            expiresIn=result.expires_in,
            filename=result.filename,
        )
        
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/files/{key:path}/metadata",
    response_model=FileMetadataResponse,
    summary="Get file metadata",
    description="Retrieve metadata for a stored file",
)
async def get_file_metadata(
    key: str,
    bucket: Optional[str] = Query(None),
    storage: S3StorageService = Depends(get_storage_service),
) -> FileMetadataResponse:
    """Get metadata for a specific file."""
    metadata = storage.get_file_metadata(key, bucket)
    
    if not metadata:
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileMetadataResponse(
        key=metadata.key,
        bucket=metadata.bucket,
        originalFilename=metadata.original_filename,
        fileSize=metadata.file_size,
        contentType=metadata.content_type,
        uploadTimestamp=metadata.upload_timestamp,
        category=metadata.category.value,
        etag=metadata.etag,
        checksum=metadata.checksum_md5,
        uploaderId=metadata.uploader_id,
        customMetadata=metadata.custom_metadata,
    )


@router.delete(
    "/files/{key:path}",
    summary="Delete file",
    description="Delete a file from storage",
)
async def delete_file(
    key: str,
    bucket: Optional[str] = Query(None),
    storage: S3StorageService = Depends(get_storage_service),
) -> Dict[str, Any]:
    """Delete a file from storage."""
    success = storage.delete_file(key, bucket)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete file")
    
    return {
        "success": True,
        "key": key,
        "deletedAt": datetime.now(timezone.utc).isoformat(),
    }


@router.get(
    "/files",
    summary="List files",
    description="List files in storage with optional prefix filter",
)
async def list_files(
    prefix: str = Query("", description="Filter by key prefix"),
    bucket: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    storage: S3StorageService = Depends(get_storage_service),
) -> Dict[str, Any]:
    """List files in storage."""
    files = storage.list_files(bucket=bucket, prefix=prefix, max_keys=limit)
    
    return {
        "files": files,
        "count": len(files),
        "prefix": prefix,
    }


@router.get(
    "/health",
    response_model=StorageHealthResponse,
    summary="Storage health check",
    description="Check health of storage service within 5 seconds",
)
async def storage_health_check(
    storage: S3StorageService = Depends(get_storage_service),
) -> StorageHealthResponse:
    """
    Check storage health.
    
    Verifies bucket accessibility and returns status within 5 seconds.
    """
    status = storage.health_check()
    
    return StorageHealthResponse(
        status=status.status,
        latencyMs=status.latency_ms,
        bucketsAccessible=status.buckets_accessible,
        error=status.error,
        checkedAt=status.checked_at,
    )


@router.get(
    "/config",
    summary="Get storage configuration",
    description="Get storage configuration and limits",
)
async def get_storage_config(
    storage: S3StorageService = Depends(get_storage_service),
) -> Dict[str, Any]:
    """Get storage configuration."""
    config = storage.config
    
    return {
        "maxFileSize": config.max_file_size,
        "maxFileSizeMB": config.max_file_size / (1024 * 1024),
        "uploadExpirySeconds": config.upload_expiry_seconds,
        "downloadExpirySeconds": config.download_expiry_seconds,
        "allowedDocumentTypes": config.allowed_document_types,
        "allowedImageTypes": config.allowed_image_types,
        "categories": [c.value for c in FileCategory],
    }

