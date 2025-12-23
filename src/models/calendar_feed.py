"""Database schema for personal calendar feeds.

This module defines the complete database schema for personal calendar feeds
including feed configurations, access tokens, sync history, and event caching.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base


# =============================================================================
# Enums
# =============================================================================

class FeedType(str, Enum):
    """Type of calendar feed."""
    
    ICS = "ics"                       # iCalendar format
    GOOGLE_CALENDAR = "google_calendar"
    OUTLOOK = "outlook"
    APPLE_CALENDAR = "apple_calendar"


class PrivacyLevel(str, Enum):
    """Privacy level for calendar events."""
    
    FULL = "full"                     # Show all event details
    LIMITED = "limited"               # Show only busy/free status
    PRIVATE = "private"               # Hide all details, show as busy


class SyncType(str, Enum):
    """Type of synchronization."""
    
    FULL = "full"                     # Complete sync of all events
    INCREMENTAL = "incremental"       # Only changed events
    MANUAL = "manual"                 # User-triggered sync


class SyncStatus(str, Enum):
    """Status of a synchronization operation."""
    
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"               # Some events synced, some failed


class EventSourceType(str, Enum):
    """Source type for calendar events."""
    
    TIME_OFF = "time_off"             # Time-off requests
    MEETING = "meeting"               # Calendar meetings
    HOLIDAY = "holiday"               # Company holidays
    BLOCK = "block"                   # Time blocks
    CUSTOM = "custom"                 # Custom events


# =============================================================================
# PersonalCalendarFeed Table
# =============================================================================

class PersonalCalendarFeed(Base):
    """
    Personal calendar feed configuration for an employee.
    
    Stores feed settings, preferences, and status information.
    """
    
    __tablename__ = "personal_calendar_feed"
    
    # Primary key
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    
    # Employee relationship
    employee_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("employee.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Feed configuration
    feed_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    
    feed_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=FeedType.ICS.value,
    )
    
    feed_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    
    # Privacy and visibility
    privacy_level: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=PrivacyLevel.LIMITED.value,
    )
    
    include_time_off: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    
    include_holidays: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    
    include_meetings: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    
    # Sync settings
    auto_sync_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    
    sync_interval_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=60,
    )
    
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )
    
    next_sync_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )
    
    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    
    is_public: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    
    # Event range
    days_past: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=30,
    )
    
    days_future: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=365,
    )
    
    # Audit timestamps
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
    
    # Relationships
    employee: Mapped["Employee"] = relationship(
        "Employee",
        back_populates="calendar_feeds",
    )
    
    tokens: Mapped[list["CalendarFeedToken"]] = relationship(
        "CalendarFeedToken",
        back_populates="feed",
        cascade="all, delete-orphan",
    )
    
    sync_history: Mapped[list["CalendarFeedSyncHistory"]] = relationship(
        "CalendarFeedSyncHistory",
        back_populates="feed",
        cascade="all, delete-orphan",
    )
    
    access_logs: Mapped[list["CalendarFeedAccess"]] = relationship(
        "CalendarFeedAccess",
        back_populates="feed",
        cascade="all, delete-orphan",
    )
    
    event_cache: Mapped[list["CalendarEventCache"]] = relationship(
        "CalendarEventCache",
        back_populates="feed",
        cascade="all, delete-orphan",
    )
    
    # Constraints
    __table_args__ = (
        CheckConstraint(
            "feed_type IN ('ics', 'google_calendar', 'outlook', 'apple_calendar')",
            name="ck_calendar_feed_type",
        ),
        CheckConstraint(
            "privacy_level IN ('full', 'limited', 'private')",
            name="ck_calendar_privacy_level",
        ),
        CheckConstraint(
            "sync_interval_minutes >= 15",
            name="ck_calendar_sync_interval_min",
        ),
        CheckConstraint(
            "days_past >= 0 AND days_past <= 365",
            name="ck_calendar_days_past_range",
        ),
        CheckConstraint(
            "days_future >= 1 AND days_future <= 730",
            name="ck_calendar_days_future_range",
        ),
        Index("ix_calendar_feed_employee_active", "employee_id", "is_active"),
    )
    
    def __repr__(self) -> str:
        return f"<PersonalCalendarFeed(id={self.id}, employee_id={self.employee_id}, name={self.feed_name})>"


# =============================================================================
# CalendarFeedToken Table
# =============================================================================

class CalendarFeedToken(Base):
    """
    Secure access tokens for calendar feeds.
    
    Stores hashed tokens with usage tracking and revocation management.
    """
    
    __tablename__ = "calendar_feed_token"
    
    # Primary key
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    
    # Feed relationship
    feed_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("personal_calendar_feed.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Token security
    token_hash: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
        unique=True,
        index=True,
    )
    
    token_prefix: Mapped[str] = mapped_column(
        String(8),
        nullable=False,
    )
    
    token_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    
    # Expiration
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )
    
    never_expires: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    
    # Usage statistics
    usage_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    
    last_used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )
    
    last_used_ip: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    
    # Revocation
    is_revoked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )
    
    revoked_reason: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    
    # Audit timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    
    # Relationships
    feed: Mapped["PersonalCalendarFeed"] = relationship(
        "PersonalCalendarFeed",
        back_populates="tokens",
    )
    
    # Constraints
    __table_args__ = (
        Index("ix_token_feed_active", "feed_id", "is_revoked"),
        Index("ix_token_expiration", "expires_at"),
    )
    
    def __repr__(self) -> str:
        return f"<CalendarFeedToken(id={self.id}, prefix={self.token_prefix})>"


# =============================================================================
# CalendarFeedSyncHistory Table
# =============================================================================

class CalendarFeedSyncHistory(Base):
    """
    Synchronization history for calendar feeds.
    
    Tracks sync events with performance metrics and error logging.
    """
    
    __tablename__ = "calendar_feed_sync_history"
    
    # Primary key
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    
    # Feed relationship
    feed_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("personal_calendar_feed.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Sync details
    sync_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    
    sync_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    
    # Timing
    started_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )
    
    duration_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    
    # Performance metrics
    events_processed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    
    events_created: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    
    events_updated: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    
    events_deleted: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    
    events_failed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    
    # Error tracking
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    
    error_details: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    
    # Trigger info
    triggered_by: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    
    # Relationships
    feed: Mapped["PersonalCalendarFeed"] = relationship(
        "PersonalCalendarFeed",
        back_populates="sync_history",
    )
    
    # Constraints
    __table_args__ = (
        CheckConstraint(
            "sync_type IN ('full', 'incremental', 'manual')",
            name="ck_sync_type",
        ),
        CheckConstraint(
            "sync_status IN ('pending', 'in_progress', 'completed', 'failed', 'partial')",
            name="ck_sync_status",
        ),
        Index("ix_sync_history_feed_time", "feed_id", "started_at"),
        Index("ix_sync_history_status", "sync_status"),
    )
    
    def __repr__(self) -> str:
        return f"<CalendarFeedSyncHistory(id={self.id}, feed_id={self.feed_id}, status={self.sync_status})>"


# =============================================================================
# CalendarFeedAccess Table
# =============================================================================

class CalendarFeedAccess(Base):
    """
    Access logging for calendar feeds.
    
    Comprehensive logging including IP, user agent, and calendar app detection.
    """
    
    __tablename__ = "calendar_feed_access"
    
    # Primary key
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    
    # Feed relationship
    feed_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("personal_calendar_feed.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Token used (optional - might be direct access)
    token_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("calendar_feed_token.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # Request details
    access_time: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    
    user_agent: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    
    # Calendar application detection
    calendar_app: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    
    calendar_app_version: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    
    # Response metrics
    response_status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=200,
    )
    
    response_time_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    
    response_size_bytes: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    
    events_returned: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    
    # Request type
    request_method: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
    )
    
    is_cached_response: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    
    # Error info
    error_code: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    
    # Relationships
    feed: Mapped["PersonalCalendarFeed"] = relationship(
        "PersonalCalendarFeed",
        back_populates="access_logs",
    )
    
    # Constraints
    __table_args__ = (
        Index("ix_access_feed_time", "feed_id", "access_time"),
        Index("ix_access_ip", "ip_address"),
    )
    
    def __repr__(self) -> str:
        return f"<CalendarFeedAccess(id={self.id}, feed_id={self.feed_id}, time={self.access_time})>"


# =============================================================================
# CalendarEventCache Table
# =============================================================================

class CalendarEventCache(Base):
    """
    Cached calendar events for efficient retrieval.
    
    Stores events with source tracking and cache expiration controls.
    """
    
    __tablename__ = "calendar_event_cache"
    
    # Primary key
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    
    # Feed relationship
    feed_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("personal_calendar_feed.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # ICS UID for deduplication
    ics_uid: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    
    # Source tracking
    event_source_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    
    source_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    
    # Event details
    event_title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    
    event_description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    
    event_location: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    
    # Timing
    start_time: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        index=True,
    )
    
    end_time: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )
    
    is_all_day: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    
    timezone: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    
    # Status
    event_status: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )
    
    # ICS content
    ics_data: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    
    # Cache management
    cached_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        index=True,
    )
    
    last_modified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )
    
    # Versioning
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
    
    # Relationships
    feed: Mapped["PersonalCalendarFeed"] = relationship(
        "PersonalCalendarFeed",
        back_populates="event_cache",
    )
    
    # Constraints
    __table_args__ = (
        CheckConstraint(
            "event_source_type IN ('time_off', 'meeting', 'holiday', 'block', 'custom')",
            name="ck_event_source_type",
        ),
        UniqueConstraint("feed_id", "ics_uid", name="uq_feed_ics_uid"),
        Index("ix_event_cache_feed_dates", "feed_id", "start_time", "end_time"),
        Index("ix_event_cache_source", "event_source_type", "source_id"),
    )
    
    def __repr__(self) -> str:
        return f"<CalendarEventCache(id={self.id}, feed_id={self.feed_id}, title={self.event_title})>"

