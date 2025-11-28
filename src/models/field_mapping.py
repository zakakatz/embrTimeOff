"""FieldMappingRule model for managing custom field mapping configurations."""

import enum
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from src.models.base import Base


class DataType(enum.Enum):
    """Supported data types for field mapping."""
    
    STRING = "string"
    INTEGER = "integer"
    DECIMAL = "decimal"
    DATE = "date"
    DATETIME = "datetime"
    BOOLEAN = "boolean"
    ENUM = "enum"


class FieldMappingRule(Base):
    """
    Model for defining custom field mapping rules.
    
    Organizations can define how source columns from import files
    map to target employee attributes, including data type conversion,
    validation rules, and transformation logic.
    """
    
    __tablename__ = "field_mapping_rules"
    
    # Primary Key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    
    # Organization reference
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    
    # Rule identification
    rule_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    
    # Mapping definition
    source_column: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    target_attribute: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    
    # Data type specification
    data_type: Mapped[DataType] = mapped_column(
        Enum(DataType, name="data_type"),
        nullable=False,
        default=DataType.STRING,
    )
    
    # Required field flag
    is_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    
    # JSONB fields for flexible configuration
    validation_rules: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
        comment="Custom validation rules (e.g., regex patterns, min/max values)",
    )
    transformation_rules: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
        comment="Data transformation rules (e.g., date format conversion, case normalization)",
    )
    auto_detection_patterns: Mapped[Optional[List[str]]] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
        comment="Patterns for automatic column detection",
    )
    
    # Default value when source is empty
    default_value: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    
    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    
    # Table constraints and indexes
    __table_args__ = (
        # Prevent duplicate active mappings for the same target attribute within an organization
        UniqueConstraint(
            "organization_id",
            "target_attribute",
            "is_active",
            name="uq_active_target_attribute_per_org",
        ),
        # Index for looking up rules by organization and target
        Index("ix_field_mapping_org_target", "organization_id", "target_attribute"),
        # Index for looking up rules by source column
        Index("ix_field_mapping_source", "organization_id", "source_column"),
    )
    
    def __repr__(self) -> str:
        return (
            f"<FieldMappingRule("
            f"id={self.id}, "
            f"rule={self.rule_name}, "
            f"source={self.source_column} -> target={self.target_attribute}"
            f")>"
        )

