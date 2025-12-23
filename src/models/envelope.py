"""SQLAlchemy models for e-signature envelope management."""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base


class EnvelopeStatus(str, Enum):
    """Status of an e-signature envelope."""
    DRAFT = "draft"
    SENT = "sent"
    DELIVERED = "delivered"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DECLINED = "declined"
    VOIDED = "voided"
    EXPIRED = "expired"


class RecipientStatus(str, Enum):
    """Status of an individual recipient."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    VIEWED = "viewed"
    SIGNED = "signed"
    DECLINED = "declined"
    EXPIRED = "expired"


class RecipientType(str, Enum):
    """Type of recipient in the signing workflow."""
    SIGNER = "signer"
    CARBON_COPY = "carbon_copy"
    CERTIFIED_DELIVERY = "certified_delivery"
    IN_PERSON_SIGNER = "in_person_signer"
    APPROVER = "approver"
    EDITOR = "editor"


class FieldType(str, Enum):
    """Types of fields that can be placed on documents."""
    SIGNATURE = "signature"
    INITIAL = "initial"
    DATE_SIGNED = "date_signed"
    TEXT = "text"
    CHECKBOX = "checkbox"
    DROPDOWN = "dropdown"
    RADIO = "radio"
    ATTACHMENT = "attachment"
    COMPANY = "company"
    TITLE = "title"
    FULL_NAME = "full_name"
    EMAIL = "email"


class Envelope(Base):
    """
    E-signature envelope containing documents for signing.
    
    An envelope orchestrates the complete signing workflow, tracking
    recipients, documents, and overall completion status.
    """
    
    __tablename__ = "envelope"
    
    # Primary Key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # External reference ID (UUID for external systems)
    external_id: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        nullable=False,
        index=True,
    )
    
    # Basic Information
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Status
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=EnvelopeStatus.DRAFT.value,
        index=True,
    )
    
    # Sender Information
    sender_employee_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("employee.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    sender_email: Mapped[str] = mapped_column(String(255), nullable=False)
    sender_name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Related HR Entity (if applicable)
    related_entity_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Type: time_off_request, offer_letter, contract, etc."
    )
    related_entity_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    
    # Document Configuration
    document_ids: Mapped[Optional[List[str]]] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
        comment="List of document storage IDs",
    )
    
    # Workflow Configuration
    routing_order_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether recipients sign in order",
    )
    
    # Reminders and Expiration
    reminder_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    reminder_delay_days: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    reminder_frequency_days: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    expires_in_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=30)
    expiration_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Completion Tracking
    completed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_recipients: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_percentage: Mapped[float] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Percentage of recipients who have completed signing",
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        onupdate=func.now(),
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    voided_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Void/Decline Information
    void_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    voided_by_employee_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Relationships
    recipients: Mapped[List["EnvelopeRecipient"]] = relationship(
        "EnvelopeRecipient",
        back_populates="envelope",
        cascade="all, delete-orphan",
        order_by="EnvelopeRecipient.routing_order",
    )
    fields: Mapped[List["EnvelopeField"]] = relationship(
        "EnvelopeField",
        back_populates="envelope",
        cascade="all, delete-orphan",
    )
    audit_trail: Mapped[List["EnvelopeAuditTrail"]] = relationship(
        "EnvelopeAuditTrail",
        back_populates="envelope",
        cascade="all, delete-orphan",
        order_by="EnvelopeAuditTrail.created_at.desc()",
    )
    
    # Indexes
    __table_args__ = (
        Index("idx_envelope_status_created", "status", "created_at"),
        Index("idx_envelope_sender", "sender_employee_id", "created_at"),
        Index("idx_envelope_related", "related_entity_type", "related_entity_id"),
    )
    
    def __repr__(self) -> str:
        return f"<Envelope(id={self.id}, subject={self.subject}, status={self.status})>"


class EnvelopeRecipient(Base):
    """
    Recipient of an e-signature envelope.
    
    Tracks individual recipient progress through the signing workflow.
    """
    
    __tablename__ = "envelope_recipient"
    
    # Primary Key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign Keys
    envelope_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("envelope.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    employee_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("employee.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    
    # Recipient Information
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Recipient Type and Role
    recipient_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=RecipientType.SIGNER.value,
    )
    role_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Logical role name: 'Employee', 'Manager', 'HR Representative'",
    )
    
    # Routing
    routing_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="Order in signing sequence (1-based)",
    )
    
    # Status
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=RecipientStatus.PENDING.value,
        index=True,
    )
    
    # Access Token (for signing link)
    access_token: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        unique=True,
    )
    
    # Decline Information
    decline_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    viewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    signed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    declined_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Signature Data
    signature_data: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Base64 encoded signature image or data",
    )
    signature_ip: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    signature_user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Relationships
    envelope: Mapped["Envelope"] = relationship("Envelope", back_populates="recipients")
    fields: Mapped[List["EnvelopeField"]] = relationship(
        "EnvelopeField",
        back_populates="recipient",
        foreign_keys="EnvelopeField.recipient_id",
    )
    
    # Indexes
    __table_args__ = (
        Index("idx_recipient_envelope_order", "envelope_id", "routing_order"),
        Index("idx_recipient_status", "status", "envelope_id"),
    )
    
    def __repr__(self) -> str:
        return f"<EnvelopeRecipient(id={self.id}, email={self.email}, status={self.status})>"


class EnvelopeField(Base):
    """
    Field placed on an envelope document for signing/filling.
    
    Represents signature fields, text fields, checkboxes, etc.
    """
    
    __tablename__ = "envelope_field"
    
    # Primary Key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign Keys
    envelope_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("envelope.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    recipient_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("envelope_recipient.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Field Configuration
    field_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=FieldType.SIGNATURE.value,
    )
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # Document and Position
    document_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    x_position: Mapped[float] = mapped_column(Integer, nullable=False, default=0)
    y_position: Mapped[float] = mapped_column(Integer, nullable=False, default=0)
    width: Mapped[float] = mapped_column(Integer, nullable=False, default=200)
    height: Mapped[float] = mapped_column(Integer, nullable=False, default=50)
    
    # Field Properties
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    read_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    
    # Field Value
    value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    default_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Validation (for text fields)
    validation_pattern: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    validation_message: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Options (for dropdown/radio)
    options: Mapped[Optional[List[str]]] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
    )
    
    # Completion
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    
    # Relationships
    envelope: Mapped["Envelope"] = relationship("Envelope", back_populates="fields")
    recipient: Mapped["EnvelopeRecipient"] = relationship(
        "EnvelopeRecipient",
        back_populates="fields",
        foreign_keys=[recipient_id],
    )
    
    def __repr__(self) -> str:
        return f"<EnvelopeField(id={self.id}, type={self.field_type}, name={self.field_name})>"


class EnvelopeAuditTrail(Base):
    """
    Audit trail entry for envelope operations.
    
    Tracks all actions taken on an envelope for compliance.
    """
    
    __tablename__ = "envelope_audit_trail"
    
    # Primary Key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign Key
    envelope_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("envelope.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Actor Information
    actor_employee_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    actor_email: Mapped[str] = mapped_column(String(255), nullable=False)
    actor_name: Mapped[str] = mapped_column(String(255), nullable=False)
    actor_role: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Role: sender, recipient, system",
    )
    
    # Action
    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    action_description: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Context
    recipient_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("envelope_recipient.id", ondelete="SET NULL"),
        nullable=True,
    )
    field_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Previous and New Values (for changes)
    previous_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    new_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Request Context
    ip_address: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    
    # Relationships
    envelope: Mapped["Envelope"] = relationship("Envelope", back_populates="audit_trail")
    
    # Indexes
    __table_args__ = (
        Index("idx_audit_envelope_action", "envelope_id", "action"),
        Index("idx_audit_created", "created_at"),
    )
    
    def __repr__(self) -> str:
        return f"<EnvelopeAuditTrail(id={self.id}, action={self.action})>"

