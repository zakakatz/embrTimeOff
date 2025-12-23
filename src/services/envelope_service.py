"""Service for e-signature envelope management."""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select, func
from sqlalchemy.orm import Session, joinedload

from src.models.employee import Employee
from src.models.envelope import (
    Envelope,
    EnvelopeAuditTrail,
    EnvelopeField,
    EnvelopeRecipient,
    EnvelopeStatus,
    FieldType,
    RecipientStatus,
    RecipientType,
)
from src.schemas.envelope import (
    AuditTrailEntry,
    CreateEnvelopeRequest,
    EnvelopeCreateResponse,
    EnvelopeResponse,
    EnvelopeStatusEnum,
    EnvelopeStatusUpdateResponse,
    FieldPosition,
    FieldResponse,
    FieldTypeEnum,
    RecipientProgress,
    RecipientResponse,
    RecipientStatusEnum,
    RecipientTypeEnum,
    UpdateEnvelopeStatusRequest,
    WorkflowStatus,
)
from src.utils.auth import CurrentUser

logger = logging.getLogger(__name__)


# =============================================================================
# Status Descriptions
# =============================================================================

STATUS_DESCRIPTIONS = {
    EnvelopeStatus.DRAFT: "Draft - not yet sent",
    EnvelopeStatus.SENT: "Sent to recipients",
    EnvelopeStatus.DELIVERED: "Delivered to all recipients",
    EnvelopeStatus.IN_PROGRESS: "Signing in progress",
    EnvelopeStatus.COMPLETED: "All recipients have signed",
    EnvelopeStatus.DECLINED: "Declined by a recipient",
    EnvelopeStatus.VOIDED: "Voided by sender",
    EnvelopeStatus.EXPIRED: "Expired before completion",
}

RECIPIENT_STATUS_DESCRIPTIONS = {
    RecipientStatus.PENDING: "Waiting to be sent",
    RecipientStatus.SENT: "Notification sent",
    RecipientStatus.DELIVERED: "Email delivered",
    RecipientStatus.VIEWED: "Envelope viewed",
    RecipientStatus.SIGNED: "Signed",
    RecipientStatus.DECLINED: "Declined",
    RecipientStatus.EXPIRED: "Expired",
}

# Valid status transitions
VALID_STATUS_TRANSITIONS = {
    EnvelopeStatus.DRAFT: [EnvelopeStatus.SENT, EnvelopeStatus.VOIDED],
    EnvelopeStatus.SENT: [
        EnvelopeStatus.DELIVERED,
        EnvelopeStatus.IN_PROGRESS,
        EnvelopeStatus.COMPLETED,
        EnvelopeStatus.DECLINED,
        EnvelopeStatus.VOIDED,
        EnvelopeStatus.EXPIRED,
    ],
    EnvelopeStatus.DELIVERED: [
        EnvelopeStatus.IN_PROGRESS,
        EnvelopeStatus.COMPLETED,
        EnvelopeStatus.DECLINED,
        EnvelopeStatus.VOIDED,
        EnvelopeStatus.EXPIRED,
    ],
    EnvelopeStatus.IN_PROGRESS: [
        EnvelopeStatus.COMPLETED,
        EnvelopeStatus.DECLINED,
        EnvelopeStatus.VOIDED,
        EnvelopeStatus.EXPIRED,
    ],
    EnvelopeStatus.COMPLETED: [],  # Terminal state
    EnvelopeStatus.DECLINED: [EnvelopeStatus.VOIDED],
    EnvelopeStatus.VOIDED: [],  # Terminal state
    EnvelopeStatus.EXPIRED: [],  # Terminal state
}


class EnvelopeService:
    """Service for managing e-signature envelopes."""

    def __init__(self, session: Session):
        """Initialize with database session."""
        self.session = session

    # =========================================================================
    # Envelope Creation
    # =========================================================================

    def create_envelope(
        self,
        request: CreateEnvelopeRequest,
        current_user: CurrentUser,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> EnvelopeCreateResponse:
        """
        Create a new envelope with recipients and fields.
        
        Validates recipient routing logic and field assignments.
        Generates audit trail entry for creation.
        """
        # Get sender information
        sender = self._get_sender_info(current_user)
        
        # Generate external ID
        external_id = str(uuid.uuid4())
        
        # Calculate expiration date
        expiration_date = None
        if request.expires_in_days:
            expiration_date = datetime.utcnow() + timedelta(days=request.expires_in_days)
        
        # Create envelope
        envelope = Envelope(
            external_id=external_id,
            subject=request.subject,
            message=request.message,
            status=EnvelopeStatus.DRAFT.value,
            sender_employee_id=current_user.employee_id,
            sender_email=sender["email"],
            sender_name=sender["name"],
            related_entity_type=request.related_entity_type,
            related_entity_id=request.related_entity_id,
            document_ids=request.document_ids,
            routing_order_enabled=request.routing_order_enabled,
            reminder_enabled=request.reminder_enabled,
            reminder_delay_days=request.reminder_delay_days,
            reminder_frequency_days=request.reminder_frequency_days,
            expires_in_days=request.expires_in_days,
            expiration_date=expiration_date,
            total_recipients=len(request.recipients),
        )
        
        self.session.add(envelope)
        self.session.flush()  # Get envelope ID
        
        # Create recipients
        recipient_map = {}  # index -> recipient object
        for idx, recipient_def in enumerate(request.recipients):
            recipient = EnvelopeRecipient(
                envelope_id=envelope.id,
                employee_id=recipient_def.employee_id,
                email=recipient_def.email,
                name=recipient_def.name,
                recipient_type=recipient_def.recipient_type.value,
                role_name=recipient_def.role_name,
                routing_order=recipient_def.routing_order,
                status=RecipientStatus.PENDING.value,
                access_token=str(uuid.uuid4()),
            )
            self.session.add(recipient)
            self.session.flush()
            recipient_map[idx] = recipient
        
        # Create fields
        if request.fields:
            for field_def in request.fields:
                recipient = recipient_map.get(field_def.recipient_index)
                if recipient:
                    field = EnvelopeField(
                        envelope_id=envelope.id,
                        recipient_id=recipient.id,
                        field_type=field_def.field_type.value,
                        field_name=field_def.field_name,
                        document_index=field_def.position.document_index,
                        page_number=field_def.position.page_number,
                        x_position=field_def.position.x_position,
                        y_position=field_def.position.y_position,
                        width=field_def.position.width,
                        height=field_def.position.height,
                        required=field_def.required,
                        default_value=field_def.default_value,
                        validation_pattern=field_def.validation_pattern,
                        validation_message=field_def.validation_message,
                        options=field_def.options,
                    )
                    self.session.add(field)
        
        # Create audit entry
        self._create_audit_entry(
            envelope_id=envelope.id,
            actor_employee_id=current_user.employee_id,
            actor_email=sender["email"],
            actor_name=sender["name"],
            actor_role="sender",
            action="envelope_created",
            action_description=f"Envelope created with {len(request.recipients)} recipients",
            ip_address=ip_address,
            user_agent=user_agent,
        )
        
        # Send immediately if requested
        sent = False
        sent_at = None
        if request.send_immediately:
            self._send_envelope(envelope, current_user, ip_address, user_agent)
            sent = True
            sent_at = envelope.sent_at
        
        self.session.commit()
        
        return EnvelopeCreateResponse(
            envelope_id=envelope.id,
            external_id=envelope.external_id,
            status=EnvelopeStatusEnum(envelope.status),
            recipients_count=len(request.recipients),
            message="Envelope created successfully",
            sent=sent,
            sent_at=sent_at,
        )

    def _get_sender_info(self, current_user: CurrentUser) -> Dict[str, str]:
        """Get sender information from current user."""
        if current_user.employee_id:
            employee = self.session.get(Employee, current_user.employee_id)
            if employee:
                return {
                    "email": employee.email,
                    "name": f"{employee.first_name} {employee.last_name}",
                }
        
        # Fallback for system user
        return {
            "email": "system@company.com",
            "name": "System",
        }

    def _send_envelope(
        self,
        envelope: Envelope,
        current_user: CurrentUser,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """Send an envelope to recipients."""
        now = datetime.utcnow()
        
        envelope.status = EnvelopeStatus.SENT.value
        envelope.sent_at = now
        
        # Update first routing order recipients to sent
        min_order = min(r.routing_order for r in envelope.recipients)
        for recipient in envelope.recipients:
            if not envelope.routing_order_enabled or recipient.routing_order == min_order:
                recipient.status = RecipientStatus.SENT.value
                recipient.sent_at = now
        
        # Create audit entry
        sender = self._get_sender_info(current_user)
        self._create_audit_entry(
            envelope_id=envelope.id,
            actor_employee_id=current_user.employee_id,
            actor_email=sender["email"],
            actor_name=sender["name"],
            actor_role="sender",
            action="envelope_sent",
            action_description="Envelope sent to recipients",
            ip_address=ip_address,
            user_agent=user_agent,
        )

    # =========================================================================
    # Envelope Retrieval
    # =========================================================================

    def get_envelope(
        self,
        envelope_id: int,
        current_user: CurrentUser,
    ) -> EnvelopeResponse:
        """
        Get complete envelope details with status and progress.
        
        Returns envelope status, recipient progress, completion rates, workflow status.
        """
        # Load envelope with relationships
        stmt = (
            select(Envelope)
            .where(Envelope.id == envelope_id)
            .options(
                joinedload(Envelope.recipients),
                joinedload(Envelope.fields),
            )
        )
        
        envelope = self.session.execute(stmt).unique().scalar_one_or_none()
        
        if not envelope:
            raise ValueError(f"Envelope {envelope_id} not found")
        
        # Check access (sender or recipient)
        self._check_envelope_access(envelope, current_user)
        
        return self._build_envelope_response(envelope)

    def get_envelope_by_external_id(
        self,
        external_id: str,
        current_user: CurrentUser,
    ) -> EnvelopeResponse:
        """Get envelope by external ID."""
        stmt = (
            select(Envelope)
            .where(Envelope.external_id == external_id)
            .options(
                joinedload(Envelope.recipients),
                joinedload(Envelope.fields),
            )
        )
        
        envelope = self.session.execute(stmt).unique().scalar_one_or_none()
        
        if not envelope:
            raise ValueError(f"Envelope with external ID {external_id} not found")
        
        self._check_envelope_access(envelope, current_user)
        
        return self._build_envelope_response(envelope)

    def _check_envelope_access(
        self,
        envelope: Envelope,
        current_user: CurrentUser,
    ) -> None:
        """Check if user has access to envelope."""
        # Sender always has access
        if envelope.sender_employee_id == current_user.employee_id:
            return
        
        # Check if user is a recipient
        if current_user.employee_id:
            for recipient in envelope.recipients:
                if recipient.employee_id == current_user.employee_id:
                    return
        
        # Admin/HR can access all
        from src.utils.auth import UserRole
        if any(r in current_user.roles for r in [UserRole.ADMIN, UserRole.HR_MANAGER]):
            return
        
        raise PermissionError("Not authorized to access this envelope")

    def _build_envelope_response(self, envelope: Envelope) -> EnvelopeResponse:
        """Build complete envelope response."""
        # Build recipient responses
        recipients = []
        for r in sorted(envelope.recipients, key=lambda x: x.routing_order):
            recipients.append(RecipientResponse(
                id=r.id,
                email=r.email,
                name=r.name,
                recipient_type=RecipientTypeEnum(r.recipient_type),
                role_name=r.role_name,
                routing_order=r.routing_order,
                status=RecipientStatusEnum(r.status),
                employee_id=r.employee_id,
                sent_at=r.sent_at,
                delivered_at=r.delivered_at,
                viewed_at=r.viewed_at,
                signed_at=r.signed_at,
                declined_at=r.declined_at,
                decline_reason=r.decline_reason,
            ))
        
        # Build field responses
        fields = None
        if envelope.fields:
            fields = []
            for f in envelope.fields:
                fields.append(FieldResponse(
                    id=f.id,
                    field_type=FieldTypeEnum(f.field_type),
                    field_name=f.field_name,
                    recipient_id=f.recipient_id,
                    position=FieldPosition(
                        document_index=f.document_index,
                        page_number=f.page_number,
                        x_position=f.x_position,
                        y_position=f.y_position,
                        width=f.width,
                        height=f.height,
                    ),
                    required=f.required,
                    value=f.value,
                    completed=f.completed,
                    completed_at=f.completed_at,
                ))
        
        # Build workflow status
        workflow_status = self._build_workflow_status(envelope)
        
        # Calculate completion
        signers = [r for r in envelope.recipients if r.recipient_type == RecipientType.SIGNER.value]
        completed_signers = [r for r in signers if r.status == RecipientStatus.SIGNED.value]
        completion_pct = (len(completed_signers) / len(signers) * 100) if signers else 0
        
        return EnvelopeResponse(
            id=envelope.id,
            external_id=envelope.external_id,
            subject=envelope.subject,
            message=envelope.message,
            status=EnvelopeStatusEnum(envelope.status),
            status_description=STATUS_DESCRIPTIONS.get(
                EnvelopeStatus(envelope.status),
                envelope.status
            ),
            sender_email=envelope.sender_email,
            sender_name=envelope.sender_name,
            sender_employee_id=envelope.sender_employee_id,
            related_entity_type=envelope.related_entity_type,
            related_entity_id=envelope.related_entity_id,
            recipients=recipients,
            fields=fields,
            document_ids=envelope.document_ids,
            routing_order_enabled=envelope.routing_order_enabled,
            workflow_status=workflow_status,
            completed_count=len(completed_signers),
            total_recipients=len(signers),
            completion_percentage=completion_pct,
            created_at=envelope.created_at,
            updated_at=envelope.updated_at,
            sent_at=envelope.sent_at,
            completed_at=envelope.completed_at,
            expiration_date=envelope.expiration_date,
            voided_at=envelope.voided_at,
            void_reason=envelope.void_reason,
        )

    def _build_workflow_status(self, envelope: Envelope) -> WorkflowStatus:
        """Build workflow status from envelope."""
        signers = [r for r in envelope.recipients if r.recipient_type == RecipientType.SIGNER.value]
        
        if not signers:
            return WorkflowStatus(
                current_routing_order=0,
                total_routing_orders=0,
                waiting_for=[],
                next_recipients=[],
                is_sequential=envelope.routing_order_enabled,
                can_progress=False,
                blocking_reason="No signers in envelope",
            )
        
        # Find current routing order
        routing_orders = sorted(set(r.routing_order for r in signers))
        current_order = routing_orders[0]
        
        for order in routing_orders:
            order_signers = [r for r in signers if r.routing_order == order]
            unsigned = [r for r in order_signers if r.status not in [
                RecipientStatus.SIGNED.value,
                RecipientStatus.DECLINED.value,
            ]]
            if unsigned:
                current_order = order
                break
        
        # Get waiting recipients
        waiting_for = []
        next_recipients = []
        
        for r in signers:
            if r.routing_order == current_order and r.status not in [
                RecipientStatus.SIGNED.value,
                RecipientStatus.DECLINED.value,
            ]:
                waiting_for.append(r.name)
            elif r.routing_order > current_order:
                next_recipients.append(r.name)
        
        # Check if blocked
        can_progress = True
        blocking_reason = None
        
        if envelope.status == EnvelopeStatus.DECLINED.value:
            can_progress = False
            blocking_reason = "Envelope was declined"
        elif envelope.status == EnvelopeStatus.VOIDED.value:
            can_progress = False
            blocking_reason = "Envelope was voided"
        elif envelope.status == EnvelopeStatus.EXPIRED.value:
            can_progress = False
            blocking_reason = "Envelope has expired"
        
        return WorkflowStatus(
            current_routing_order=current_order,
            total_routing_orders=len(routing_orders),
            waiting_for=waiting_for[:5],  # Limit for display
            next_recipients=next_recipients[:5],
            is_sequential=envelope.routing_order_enabled,
            can_progress=can_progress,
            blocking_reason=blocking_reason,
        )

    # =========================================================================
    # Status Update
    # =========================================================================

    def update_envelope_status(
        self,
        envelope_id: int,
        request: UpdateEnvelopeStatusRequest,
        current_user: CurrentUser,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> EnvelopeStatusUpdateResponse:
        """
        Update envelope status with business rule validation.
        
        Validates status transitions and triggers notifications.
        """
        # Get envelope
        envelope = self.session.get(Envelope, envelope_id)
        if not envelope:
            raise ValueError(f"Envelope {envelope_id} not found")
        
        # Check access (only sender can update status)
        if envelope.sender_employee_id != current_user.employee_id:
            # Check for admin
            from src.utils.auth import UserRole
            if UserRole.ADMIN not in current_user.roles:
                raise PermissionError("Only the sender can update envelope status")
        
        # Validate status transition
        current_status = EnvelopeStatus(envelope.status)
        new_status = EnvelopeStatus(request.status.value)
        
        if new_status not in VALID_STATUS_TRANSITIONS.get(current_status, []):
            raise ValueError(
                f"Invalid status transition from {current_status.value} to {new_status.value}"
            )
        
        # Store previous status
        previous_status = envelope.status
        
        # Update status
        envelope.status = new_status.value
        envelope.updated_at = datetime.utcnow()
        
        # Handle specific status changes
        notifications_sent = 0
        
        if new_status == EnvelopeStatus.SENT:
            envelope.sent_at = datetime.utcnow()
            # Update recipient statuses
            min_order = min(r.routing_order for r in envelope.recipients)
            for recipient in envelope.recipients:
                if not envelope.routing_order_enabled or recipient.routing_order == min_order:
                    recipient.status = RecipientStatus.SENT.value
                    recipient.sent_at = datetime.utcnow()
                    notifications_sent += 1
        
        elif new_status == EnvelopeStatus.VOIDED:
            envelope.voided_at = datetime.utcnow()
            envelope.void_reason = request.reason
            envelope.voided_by_employee_id = current_user.employee_id
            # Notify all recipients
            notifications_sent = len(envelope.recipients)
        
        elif new_status == EnvelopeStatus.COMPLETED:
            envelope.completed_at = datetime.utcnow()
        
        # Create audit entry
        sender = self._get_sender_info(current_user)
        audit_entry = self._create_audit_entry(
            envelope_id=envelope.id,
            actor_employee_id=current_user.employee_id,
            actor_email=sender["email"],
            actor_name=sender["name"],
            actor_role="sender",
            action="status_changed",
            action_description=f"Status changed from {previous_status} to {new_status.value}",
            previous_value=previous_status,
            new_value=new_status.value,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        
        self.session.commit()
        
        return EnvelopeStatusUpdateResponse(
            envelope_id=envelope.id,
            previous_status=EnvelopeStatusEnum(previous_status),
            new_status=EnvelopeStatusEnum(envelope.status),
            status_description=STATUS_DESCRIPTIONS.get(new_status, new_status.value),
            notifications_sent=notifications_sent,
            audit_entry_id=audit_entry.id,
            message=f"Status updated to {new_status.value}",
        )

    # =========================================================================
    # Audit Trail
    # =========================================================================

    def _create_audit_entry(
        self,
        envelope_id: int,
        actor_email: str,
        actor_name: str,
        action: str,
        action_description: str,
        actor_employee_id: Optional[int] = None,
        actor_role: Optional[str] = None,
        recipient_id: Optional[int] = None,
        field_id: Optional[int] = None,
        previous_value: Optional[str] = None,
        new_value: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> EnvelopeAuditTrail:
        """Create an audit trail entry."""
        audit = EnvelopeAuditTrail(
            envelope_id=envelope_id,
            actor_employee_id=actor_employee_id,
            actor_email=actor_email,
            actor_name=actor_name,
            actor_role=actor_role,
            action=action,
            action_description=action_description,
            recipient_id=recipient_id,
            field_id=field_id,
            previous_value=previous_value,
            new_value=new_value,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.session.add(audit)
        self.session.flush()
        return audit

    def get_envelope_audit_trail(
        self,
        envelope_id: int,
        current_user: CurrentUser,
    ) -> List[AuditTrailEntry]:
        """Get audit trail for an envelope."""
        # Get envelope to check access
        envelope = self.session.get(Envelope, envelope_id)
        if not envelope:
            raise ValueError(f"Envelope {envelope_id} not found")
        
        self._check_envelope_access(envelope, current_user)
        
        # Query audit trail
        stmt = (
            select(EnvelopeAuditTrail)
            .where(EnvelopeAuditTrail.envelope_id == envelope_id)
            .order_by(EnvelopeAuditTrail.created_at.desc())
        )
        
        entries = self.session.execute(stmt).scalars().all()
        
        return [
            AuditTrailEntry(
                id=e.id,
                action=e.action,
                action_description=e.action_description,
                actor_name=e.actor_name,
                actor_email=e.actor_email,
                actor_role=e.actor_role,
                ip_address=e.ip_address,
                created_at=e.created_at,
            )
            for e in entries
        ]

    # =========================================================================
    # Listing
    # =========================================================================

    def list_envelopes(
        self,
        current_user: CurrentUser,
        status: Optional[EnvelopeStatusEnum] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[EnvelopeResponse], int]:
        """List envelopes for the current user."""
        # Build query
        stmt = (
            select(Envelope)
            .options(
                joinedload(Envelope.recipients),
                joinedload(Envelope.fields),
            )
        )
        
        # Filter by user access (sender or recipient)
        if current_user.employee_id:
            # Get envelopes where user is sender or recipient
            stmt = stmt.where(
                (Envelope.sender_employee_id == current_user.employee_id) |
                (Envelope.id.in_(
                    select(EnvelopeRecipient.envelope_id)
                    .where(EnvelopeRecipient.employee_id == current_user.employee_id)
                ))
            )
        
        # Filter by status
        if status:
            stmt = stmt.where(Envelope.status == status.value)
        
        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.session.execute(count_stmt).scalar() or 0
        
        # Apply pagination and ordering
        stmt = (
            stmt
            .order_by(Envelope.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        
        envelopes = self.session.execute(stmt).unique().scalars().all()
        
        return (
            [self._build_envelope_response(e) for e in envelopes],
            total,
        )

