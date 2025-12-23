"""
File Upload API Endpoints

Provides presigned URL generation for S3 uploads.
"""

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    boto3 = None

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/uploads", tags=["Uploads"])


# =============================================================================
# Configuration
# =============================================================================

class S3Config:
    """S3 configuration."""
    
    bucket_name: str = os.environ.get("S3_BUCKET_NAME", "embi-uploads")
    region: str = os.environ.get("AWS_REGION", "us-east-1")
    presigned_url_expiry: int = 3600  # 1 hour
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    allowed_types: set = {
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/csv",
    }


# =============================================================================
# Models
# =============================================================================

class PresignedUrlRequest(BaseModel):
    """Request for presigned upload URL."""
    
    fileName: str = Field(..., min_length=1, max_length=255)
    fileType: str = Field(..., description="MIME type of the file")
    fileSize: int = Field(..., gt=0, description="File size in bytes")


class PresignedUrlResponse(BaseModel):
    """Response with presigned upload URL."""
    
    uploadUrl: str = Field(..., description="Presigned URL for PUT upload")
    fileUrl: str = Field(..., description="Final URL of the uploaded file")
    key: str = Field(..., description="S3 object key")
    expiresIn: int = Field(..., description="URL expiration in seconds")


# =============================================================================
# S3 Client
# =============================================================================

class S3Client:
    """S3 client for presigned URL generation."""
    
    def __init__(self, config: Optional[S3Config] = None):
        self.config = config or S3Config()
        
        if boto3:
            self._client = boto3.client(
                "s3",
                region_name=self.config.region,
            )
        else:
            self._client = None
            logger.warning("boto3 not installed - using mock S3 client")
    
    def generate_presigned_url(
        self,
        file_name: str,
        file_type: str,
        file_size: int,
    ) -> PresignedUrlResponse:
        """
        Generate a presigned URL for file upload.
        
        Args:
            file_name: Original file name
            file_type: MIME type
            file_size: Size in bytes
        
        Returns:
            PresignedUrlResponse with upload URL and file info
        """
        # Validate file type
        if file_type not in self.config.allowed_types:
            raise ValueError(f"File type '{file_type}' not allowed")
        
        # Validate file size
        if file_size > self.config.max_file_size:
            raise ValueError(
                f"File size {file_size} exceeds maximum "
                f"{self.config.max_file_size} bytes"
            )
        
        # Generate unique key
        timestamp = datetime.now(timezone.utc).strftime("%Y/%m/%d")
        unique_id = str(uuid.uuid4())
        extension = self._get_extension(file_name)
        key = f"uploads/{timestamp}/{unique_id}{extension}"
        
        if self._client:
            # Generate presigned URL
            try:
                presigned_url = self._client.generate_presigned_url(
                    "put_object",
                    Params={
                        "Bucket": self.config.bucket_name,
                        "Key": key,
                        "ContentType": file_type,
                    },
                    ExpiresIn=self.config.presigned_url_expiry,
                )
            except ClientError as e:
                logger.error(f"Failed to generate presigned URL: {str(e)}")
                raise RuntimeError("Failed to generate upload URL")
            
            file_url = f"https://{self.config.bucket_name}.s3.{self.config.region}.amazonaws.com/{key}"
        else:
            # Mock response for development
            presigned_url = f"https://{self.config.bucket_name}.s3.{self.config.region}.amazonaws.com/{key}?mock=true"
            file_url = f"https://{self.config.bucket_name}.s3.{self.config.region}.amazonaws.com/{key}"
        
        return PresignedUrlResponse(
            uploadUrl=presigned_url,
            fileUrl=file_url,
            key=key,
            expiresIn=self.config.presigned_url_expiry,
        )
    
    def _get_extension(self, file_name: str) -> str:
        """Extract file extension from name."""
        if "." in file_name:
            return "." + file_name.rsplit(".", 1)[1].lower()
        return ""


# =============================================================================
# Dependencies
# =============================================================================

_s3_client: Optional[S3Client] = None


def get_s3_client() -> S3Client:
    """Get S3 client singleton."""
    global _s3_client
    if _s3_client is None:
        _s3_client = S3Client()
    return _s3_client


# =============================================================================
# Endpoints
# =============================================================================

@router.post(
    "/presigned-url",
    response_model=PresignedUrlResponse,
    summary="Get presigned URL for file upload",
    description="Generate a presigned URL for direct S3 upload",
)
async def get_presigned_url(
    request: PresignedUrlRequest,
    s3_client: S3Client = Depends(get_s3_client),
) -> PresignedUrlResponse:
    """
    Generate a presigned URL for uploading a file to S3.
    
    The client can use the returned URL to PUT the file directly to S3.
    """
    try:
        return s3_client.generate_presigned_url(
            file_name=request.fileName,
            file_type=request.fileType,
            file_size=request.fileSize,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/config",
    summary="Get upload configuration",
    description="Get file upload configuration and limits",
)
async def get_upload_config() -> dict:
    """Get upload configuration."""
    config = S3Config()
    
    return {
        "maxFileSize": config.max_file_size,
        "maxFileSizeFormatted": f"{config.max_file_size / (1024 * 1024):.0f}MB",
        "allowedTypes": list(config.allowed_types),
        "presignedUrlExpiry": config.presigned_url_expiry,
    }

