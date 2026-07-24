"""
PostgreSQL models — ERD:

  Tenant ──< TenantUser
     │
     ├──< Document
     ├──< VoiceProfile
     ├──< CallScript
     │        │
     └──< Campaign ──< CampaignContact
               │
               └──< CallLog

Tenant is the root of all data isolation (Party B).
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


# Mixins

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class UUIDPrimaryKeyMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )


# Enums

class TenantPlan(str, enum.Enum):
    STARTER = "starter"       # up to 1,000 min/month
    BUSINESS = "business"     # up to 10,000 min/month
    ENTERPRISE = "enterprise" # unlimited


class UserRole(str, enum.Enum):
    ADMIN = "admin"       # full access
    MANAGER = "manager"   # manage campaigns, view reports
    VIEWER = "viewer"     # view reports only


class DocumentStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class CampaignStatus(str, enum.Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ContactStatus(str, enum.Enum):
    PENDING = "pending"
    CALLING = "calling"
    COMPLETED = "completed"
    NO_ANSWER = "no_answer"
    FAILED = "failed"
    SKIPPED = "skipped"    # in DNC list


class CallResult(str, enum.Enum):
    INTERESTED = "interested"
    NOT_INTERESTED = "not_interested"
    CALLBACK_REQUESTED = "callback_requested"
    NEEDS_HUMAN = "needs_human"
    NO_ANSWER = "no_answer"
    BUSY = "busy"
    FAILED = "failed"
    UNKNOWN = "unknown"


# Tenant (Party B)

class Tenant(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Party B — each tenant is a fully isolated business client."""
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    plan: Mapped[TenantPlan] = mapped_column(
        Enum(TenantPlan), default=TenantPlan.STARTER, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Usage limits
    monthly_minutes_limit: Mapped[int] = mapped_column(Integer, default=1000)
    monthly_minutes_used: Mapped[int] = mapped_column(Integer, default=0)
    max_concurrent_calls: Mapped[int] = mapped_column(Integer, default=5)

    # Contact info
    contact_email: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_phone: Mapped[str | None] = mapped_column(String(20))

    # Webhook for pushing results back to Party B's CRM
    webhook_url: Mapped[str | None] = mapped_column(String(500))
    webhook_secret: Mapped[str | None] = mapped_column(String(200))

    # Relationships
    users: Mapped[list["TenantUser"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    documents: Mapped[list["Document"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    voice_profiles: Mapped[list["VoiceProfile"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    scripts: Mapped[list["CallScript"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    campaigns: Mapped[list["Campaign"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    dnc_entries: Mapped[list["DNCList"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")


# Tenant User

class TenantUser(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Users belonging to a tenant (Party B staff)."""
    __tablename__ = "tenant_users"
    __table_args__ = (UniqueConstraint("tenant_id", "email"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole), default=UserRole.VIEWER, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # MFA
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_secret: Mapped[str | None] = mapped_column(String(100))

    tenant: Mapped["Tenant"] = relationship(back_populates="users")


# Document (Knowledge Base)

class Document(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Internal documents uploaded by Party B for RAG."""
    __tablename__ = "documents"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant_users.id"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)

    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus), default=DocumentStatus.PENDING, nullable=False
    )
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)

    # Version tracking
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Qdrant collection name for this tenant's embeddings
    qdrant_collection: Mapped[str | None] = mapped_column(String(200))

    tenant: Mapped["Tenant"] = relationship(back_populates="documents")


# Voice Profile

class VoiceProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Cloned voice profile for a tenant (XTTS v2 speaker embedding)."""
    __tablename__ = "voice_profiles"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    # Path to the ~6s sample audio for XTTS v2 cloning
    sample_audio_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Consent tracking (required for voice cloning)
    consent_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consent_confirmed_by: Mapped[str | None] = mapped_column(String(255))

    tenant: Mapped["Tenant"] = relationship(back_populates="voice_profiles")
    campaigns: Mapped[list["Campaign"]] = relationship(back_populates="voice_profile")


# Call Script

class CallScript(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    Conversation script for a campaign.
    Stored as JSON — defines the state machine branches for the Dialogue Manager.

    Example structure:
    {
      "goal": "Introduce Product X and collect interest",
      "greeting": "Xin chào, tôi là AI trợ lý của {company}...",
      "stages": [
        { "id": "intro", "prompt": "...", "next": ["main", "end"] },
        { "id": "main",  "prompt": "...", "next": ["cta", "objection"] },
        ...
      ],
      "intents": {
        "not_interested": { "response": "...", "action": "end" },
        "callback":       { "response": "...", "action": "schedule_callback" },
        ...
      }
    }
    """
    __tablename__ = "call_scripts"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1)

    tenant: Mapped["Tenant"] = relationship(back_populates="scripts")
    campaigns: Mapped[list["Campaign"]] = relationship(back_populates="script")


# Campaign

class Campaign(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An outbound calling campaign created by Party B."""
    __tablename__ = "campaigns"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    script_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("call_scripts.id"), nullable=False
    )
    voice_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("voice_profiles.id"), nullable=False
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant_users.id"), nullable=False
    )

    name: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[CampaignStatus] = mapped_column(
        Enum(CampaignStatus), default=CampaignStatus.DRAFT, nullable=False
    )

    # Scheduling
    scheduled_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scheduled_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    call_window_start: Mapped[str] = mapped_column(String(5), default="08:00")  # "HH:MM"
    call_window_end: Mapped[str] = mapped_column(String(5), default="20:00")
    max_retries: Mapped[int] = mapped_column(Integer, default=2)
    retry_delay_minutes: Mapped[int] = mapped_column(Integer, default=60)

    # Stats (denormalized for fast dashboard queries)
    total_contacts: Mapped[int] = mapped_column(Integer, default=0)
    completed_calls: Mapped[int] = mapped_column(Integer, default=0)
    answered_calls: Mapped[int] = mapped_column(Integer, default=0)
    total_duration_seconds: Mapped[int] = mapped_column(Integer, default=0)

    # Timestamps
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    tenant: Mapped["Tenant"] = relationship(back_populates="campaigns")
    script: Mapped["CallScript"] = relationship(back_populates="campaigns")
    voice_profile: Mapped["VoiceProfile"] = relationship(back_populates="campaigns")
    contacts: Mapped[list["CampaignContact"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan"
    )
    call_logs: Mapped[list["CallLog"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan"
    )


# Campaign Contact

class CampaignContact(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A single phone number in a campaign's contact list."""
    __tablename__ = "campaign_contacts"

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False
    )
    phone_number: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str | None] = mapped_column(String(200))
    metadata: Mapped[dict] = mapped_column(JSONB, default=dict)  # extra CSV columns

    status: Mapped[ContactStatus] = mapped_column(
        Enum(ContactStatus), default=ContactStatus.PENDING, nullable=False
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    campaign: Mapped["Campaign"] = relationship(back_populates="contacts")
    call_logs: Mapped[list["CallLog"]] = relationship(back_populates="contact")


# Call Log

class CallLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Record of a single call attempt. One contact may have multiple call logs."""
    __tablename__ = "call_logs"

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaign_contacts.id"), nullable=False
    )

    # Telephony identifiers
    sip_call_id: Mapped[str | None] = mapped_column(String(200), unique=True)
    twilio_call_sid: Mapped[str | None] = mapped_column(String(100))

    result: Mapped[CallResult] = mapped_column(
        Enum(CallResult), default=CallResult.UNKNOWN, nullable=False
    )

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)

    # Storage path for the full call recording
    recording_path: Mapped[str | None] = mapped_column(String(1000))

    # MongoDB reference for transcript + summary
    mongo_session_id: Mapped[str | None] = mapped_column(String(100))

    # Webhook delivery status
    webhook_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    webhook_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    campaign: Mapped["Campaign"] = relationship(back_populates="call_logs")
    contact: Mapped["CampaignContact"] = relationship(back_populates="call_logs")


# DNC List

class DNCList(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Do-Not-Call list per tenant. Contacts matching these numbers are skipped."""
    __tablename__ = "dnc_list"
    __table_args__ = (UniqueConstraint("tenant_id", "phone_number"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    phone_number: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500))
    added_by: Mapped[str | None] = mapped_column(String(255))  # email or "system"

    tenant: Mapped["Tenant"] = relationship(back_populates="dnc_entries")


# Audit Log

class AuditLog(UUIDPrimaryKeyMixin, Base):
    """Immutable log of all actions performed by Party B users."""
    __tablename__ = "audit_logs"

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    action: Mapped[str] = mapped_column(String(200), nullable=False)  # e.g. "campaign.create"
    resource_type: Mapped[str | None] = mapped_column(String(100))    # e.g. "campaign"
    resource_id: Mapped[str | None] = mapped_column(String(100))
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )