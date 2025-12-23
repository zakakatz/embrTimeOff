"""API endpoints for e-signature envelope management."""

import logging
import uuid
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.schemas.envelope import (
    AuditTrailEntry,
    CreateEnvelopeRequest,
    EnvelopeCreateResponse,
    EnvelopeListResponse,
    EnvelopeResponse,
    EnvelopeStatusEnum,
    EnvelopeStatusUpdateResponse,
    EnvelopeValidationError,
    EnvelopeValidationErrorResponse,
    UpdateEnvelopeStatusRequest,
)
from src.services.envelope_service import EnvelopeService
from src.utils.auth import CurrentUser, UserRole, get_mock_current_user

logger = logging.getLogger(__name__)


# =============================================================================
# Router Setup
# =============================================================================

envelope_router = APIRouter(
    prefix="/api/e-signature/envelopes",
    tags=["E-Signature Envelopes"],
)


# =============================================================================
# Dependencies
# =============================================================================

def get_current_user(
    request: Request,
    x_user_id: Annotated[Optional[str], Header(alias="X-User-ID")] = None,
    x_employee_id: Annotated[Optional[int], Header(alias="X-Employee-ID")] = None,
    x_user_role: Annotated[Optional[str], Header(alias="X-User-Role")] = None,
) -> CurrentUser:
    """
    Get current user from request headers.
    
    In production, this would verify JWT tokens or session cookies.
    For development, it uses headers to simulate different users/roles.
    """
    user_id = None
    if x_user_id:
        try:
            user_id = uuid.UUID(x_user_id)
        except ValueError:
            pass
    
    roles = [UserRole.EMPLOYEE]
    if x_user_role:
        try:
            roles = [UserRole(x_user_role)]
        except ValueError:
            pass
    
    return get_mock_current_user(
        user_id=user_id,
        employee_id=x_employee_id or 1,  # Default for development
        roles=roles,
    )


def get_envelope_service(
    session: Annotated[Session, Depends(get_db)],
) -> EnvelopeService:
    """Get envelope service instance."""
    return EnvelopeService(session)


def get_client_info(request: Request) -> tuple:
    """Extract client IP and user agent from request."""
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return ip_address, user_agent


# =============================================================================
# Endpoints
# =============================================================================

@envelope_router.post(
    "",
    response_model=EnvelopeCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new envelope",
    description="""
    Create a new e-signature envelope with recipients and field configuration.
    
    **Recipient Routing:**
    - Recipients can be configured with routing orders for sequential signing
    - When `routing_order_enabled` is true, recipients sign in order
    - Recipients with the same routing order can sign in parallel
    
    **Field Mapping:**
    - Fields are assigned to specific recipients by index
    - Supported field types: signature, initial, date_signed, text, checkbox, etc.
    - Field positions are specified in points from document origin
    
    **Validation:**
    - At least one signer is required
    - Recipient emails must be unique within the envelope
    - Field recipient indices must be valid
    
    **Response:**
    - Returns envelope ID and external reference ID on success
    - If `send_immediately` is true, envelope is sent to recipients
    """,
    responses={
        201: {
            "description": "Envelope created successfully",
            "content": {
                "application/json": {
                    "example": {
                        "envelope_id": 1,
                        "external_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                        "status": "draft",
                        "recipients_count": 2,
                        "message": "Envelope created successfully",
                        "sent": False,
                    }
                }
            },
        },
        400: {
            "description": "Validation error",
            "model": EnvelopeValidationErrorResponse,
        },
        401: {"description": "Authentication required"},
    },
)
async def create_envelope(
    request_body: CreateEnvelopeRequest,
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[EnvelopeService, Depends(get_envelope_service)],
) -> EnvelopeCreateResponse:
    """
    Create a new e-signature envelope.
    
    Creates envelope with recipients and optional field definitions.
    Validates recipient routing logic and field assignments.
    Generates audit trail entry for compliance tracking.
    """
    ip_address, user_agent = get_client_info(request)
    
    try:
        response = service.create_envelope(
            request=request_body,
            current_user=current_user,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        
        logger.info(
            f"Envelope {response.envelope_id} created by employee {current_user.employee_id}"
        )
        
        return response
        
    except ValueError as e:
        logger.error(f"Validation error creating envelope: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Validation failed",
                "errors": [{"field": "request", "message": str(e), "code": "validation_error"}],
            },
        )
    except Exception as e:
        logger.exception(f"Error creating envelope: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating the envelope",
        )


@envelope_router.get(
    "/{envelope_id}",
    response_model=EnvelopeResponse,
    summary="Get envelope details",
    description="""
    Get complete envelope details including status, recipients, and workflow progress.
    
    **Response Includes:**
    - Envelope metadata (subject, message, dates)
    - Current status with human-readable description
    - All recipients with individual status and timestamps
    - Field definitions and completion status
    - Workflow status (current position, waiting recipients, blockers)
    - Completion percentage
    
    **Access Control:**
    - Sender can always access their envelopes
    - Recipients can access envelopes they are part of
    - Admin/HR can access all envelopes
    """,
    responses={
        200: {"description": "Envelope details retrieved"},
        401: {"description": "Authentication required"},
        403: {"description": "Not authorized to access this envelope"},
        404: {"description": "Envelope not found"},
    },
)
async def get_envelope(
    envelope_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[EnvelopeService, Depends(get_envelope_service)],
) -> EnvelopeResponse:
    """
    Get envelope status, recipient progress, and workflow status.
    
    Returns complete envelope information including all recipients,
    their individual statuses, completion rates, and current workflow position.
    """
    try:
        response = service.get_envelope(
            envelope_id=envelope_id,
            current_user=current_user,
        )
        
        logger.info(
            f"Envelope {envelope_id} retrieved by employee {current_user.employee_id}"
        )
        
        return response
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except Exception as e:
        logger.exception(f"Error retrieving envelope: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving the envelope",
        )


@envelope_router.get(
    "/external/{external_id}",
    response_model=EnvelopeResponse,
    summary="Get envelope by external ID",
    description="Get envelope details using the external reference ID (UUID).",
    responses={
        200: {"description": "Envelope details retrieved"},
        401: {"description": "Authentication required"},
        403: {"description": "Not authorized to access this envelope"},
        404: {"description": "Envelope not found"},
    },
)
async def get_envelope_by_external_id(
    external_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[EnvelopeService, Depends(get_envelope_service)],
) -> EnvelopeResponse:
    """Get envelope by external reference ID."""
    try:
        response = service.get_envelope_by_external_id(
            external_id=external_id,
            current_user=current_user,
        )
        return response
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )


@envelope_router.put(
    "/{envelope_id}/status",
    response_model=EnvelopeStatusUpdateResponse,
    summary="Update envelope status",
    description="""
    Update the status of an envelope with business rule validation.
    
    **Valid Status Transitions:**
    - draft → sent, voided
    - sent → delivered, in_progress, completed, declined, voided, expired
    - delivered → in_progress, completed, declined, voided, expired
    - in_progress → completed, declined, voided, expired
    - completed → (terminal state)
    - declined → voided
    - voided → (terminal state)
    - expired → (terminal state)
    
    **Status Change Effects:**
    - `sent`: Sends notifications to first routing order recipients
    - `voided`: Requires reason, notifies all recipients
    - `completed`: Records completion timestamp
    
    **Audit Trail:**
    - All status changes are logged with timestamps, IP, and user info
    """,
    responses={
        200: {"description": "Status updated successfully"},
        400: {
            "description": "Invalid status transition",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Invalid status transition from draft to completed"
                    }
                }
            },
        },
        401: {"description": "Authentication required"},
        403: {"description": "Not authorized to update this envelope"},
        404: {"description": "Envelope not found"},
    },
)
async def update_envelope_status(
    envelope_id: int,
    request_body: UpdateEnvelopeStatusRequest,
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[EnvelopeService, Depends(get_envelope_service)],
) -> EnvelopeStatusUpdateResponse:
    """
    Update envelope status with validation and notifications.
    
    Validates status change against business rules.
    Triggers appropriate notifications to affected recipients.
    Creates audit trail entry for compliance.
    """
    ip_address, user_agent = get_client_info(request)
    
    try:
        response = service.update_envelope_status(
            envelope_id=envelope_id,
            request=request_body,
            current_user=current_user,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        
        logger.info(
            f"Envelope {envelope_id} status updated to {response.new_status.value} "
            f"by employee {current_user.employee_id}"
        )
        
        return response
        
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except Exception as e:
        logger.exception(f"Error updating envelope status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while updating the envelope status",
        )


@envelope_router.get(
    "/{envelope_id}/audit-trail",
    response_model=List[AuditTrailEntry],
    summary="Get envelope audit trail",
    description="""
    Get the complete audit trail for an envelope.
    
    Returns all actions taken on the envelope including:
    - Creation
    - Status changes
    - Recipient actions (view, sign, decline)
    - Field completions
    
    Each entry includes timestamp, actor information, IP address, and action details.
    """,
    responses={
        200: {"description": "Audit trail retrieved"},
        401: {"description": "Authentication required"},
        403: {"description": "Not authorized to access this envelope"},
        404: {"description": "Envelope not found"},
    },
)
async def get_envelope_audit_trail(
    envelope_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[EnvelopeService, Depends(get_envelope_service)],
) -> List[AuditTrailEntry]:
    """Get audit trail for compliance tracking."""
    try:
        return service.get_envelope_audit_trail(
            envelope_id=envelope_id,
            current_user=current_user,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )


@envelope_router.get(
    "",
    response_model=EnvelopeListResponse,
    summary="List envelopes",
    description="""
    List envelopes for the current user.
    
    Returns envelopes where the user is either:
    - The sender
    - A recipient
    
    Supports filtering by status and pagination.
    """,
    responses={
        200: {"description": "Envelopes listed successfully"},
        401: {"description": "Authentication required"},
    },
)
async def list_envelopes(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[EnvelopeService, Depends(get_envelope_service)],
    status_filter: Annotated[
        Optional[EnvelopeStatusEnum],
        Query(alias="status", description="Filter by status"),
    ] = None,
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
) -> EnvelopeListResponse:
    """List envelopes for the current user."""
    envelopes, total = service.list_envelopes(
        current_user=current_user,
        status=status_filter,
        page=page,
        page_size=page_size,
    )
    
    return EnvelopeListResponse(
        envelopes=envelopes,
        total=total,
        page=page,
        page_size=page_size,
    )


@envelope_router.post(
    "/{envelope_id}/send",
    response_model=EnvelopeStatusUpdateResponse,
    summary="Send an envelope",
    description="Send a draft envelope to its recipients.",
    responses={
        200: {"description": "Envelope sent successfully"},
        400: {"description": "Envelope is not in draft status"},
        401: {"description": "Authentication required"},
        403: {"description": "Not authorized to send this envelope"},
        404: {"description": "Envelope not found"},
    },
)
async def send_envelope(
    envelope_id: int,
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[EnvelopeService, Depends(get_envelope_service)],
) -> EnvelopeStatusUpdateResponse:
    """Send a draft envelope to recipients."""
    ip_address, user_agent = get_client_info(request)
    
    update_request = UpdateEnvelopeStatusRequest(status=EnvelopeStatusEnum.SENT)
    
    try:
        return service.update_envelope_status(
            envelope_id=envelope_id,
            request=update_request,
            current_user=current_user,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )


@envelope_router.post(
    "/{envelope_id}/void",
    response_model=EnvelopeStatusUpdateResponse,
    summary="Void an envelope",
    description="Void an envelope, preventing any further signing.",
    responses={
        200: {"description": "Envelope voided successfully"},
        400: {"description": "Invalid void request or envelope already voided"},
        401: {"description": "Authentication required"},
        403: {"description": "Not authorized to void this envelope"},
        404: {"description": "Envelope not found"},
    },
)
async def void_envelope(
    envelope_id: int,
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[EnvelopeService, Depends(get_envelope_service)],
    reason: Annotated[str, Query(min_length=10, description="Reason for voiding")],
) -> EnvelopeStatusUpdateResponse:
    """Void an envelope with required reason."""
    ip_address, user_agent = get_client_info(request)
    
    update_request = UpdateEnvelopeStatusRequest(
        status=EnvelopeStatusEnum.VOIDED,
        reason=reason,
    )
    
    try:
        return service.update_envelope_status(
            envelope_id=envelope_id,
            request=update_request,
            current_user=current_user,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )

