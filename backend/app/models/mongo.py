"""
MongoDB document models via Beanie ODM.
Used for high-volume, variable-schema data: transcripts, summaries, session state.
"""

from datetime import UTC, datetime
from typing import Annotated, Any

from beanie import Document, Indexed
from pydantic import BaseModel, Field

# Typed aliases for indexed fields
IndexedStr = Annotated[str, Indexed()]

class TranscriptTurn(BaseModel):
    """A single turn in the conversation."""
    speaker: str                  # "ai" | "caller"
    text: str
    timestamp_ms: int             # ms from call start
    confidence: float | None = None   # STT confidence score


class IntentDetection(BaseModel):
    intent: str                   # CallResult value
    confidence: float
    detected_at_ms: int


class CallSession(Document):
    """
    Live session state for an active call.
    Written during the call; read by Dialogue Manager.
    Deleted or archived after post-call processing.
    """
    class Settings:
        name = "call_sessions"
        indexes = ["call_log_id", "tenant_id", "status"]

    call_log_id: IndexedStr             # FK → PostgreSQL CallLog.id (as str)
    tenant_id: IndexedStr
    campaign_id: str
    phone_number: str

    status: str = "active"             # active | ended
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    ended_at: datetime | None = None

    # Dialogue state machine current position
    current_stage: str = "intro"
    stage_history: list[str] = Field(default_factory=list)

    # Running transcript buffer (last N turns for LLM context window)
    turns: list[TranscriptTurn] = Field(default_factory=list)

    # Detected intents so far
    intents: list[IntentDetection] = Field(default_factory=list)

    # Metadata
    extra: dict[str, Any] = Field(default_factory=dict)


class CallTranscript(Document):
    """
    Full conversation transcript stored after call ends.
    Immutable — never modified after creation.
    """
    class Settings:
        name = "call_transcripts"
        indexes = ["call_log_id", "tenant_id", "campaign_id"]

    call_log_id: IndexedStr
    tenant_id: IndexedStr
    campaign_id: str
    phone_number: str

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    duration_seconds: int = 0

    turns: list[TranscriptTurn] = Field(default_factory=list)
    final_intent: str | None = None


class CallSummary(Document):
    """
    AI-generated summary and classification of a completed call.
    Sent to Party B via dashboard and webhook.
    """
    class Settings:
        name = "call_summaries"
        indexes = ["call_log_id", "tenant_id", "campaign_id", "result"]

    call_log_id: IndexedStr
    tenant_id: IndexedStr
    campaign_id: str
    phone_number: str
    caller_name: str | None = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # Classification
    result: IndexedStr               # CallResult value
    confidence: float = 0.0

    # LLM-generated summary
    summary: str = ""
    key_points: list[str] = Field(default_factory=list)
    collected_info: dict[str, Any] = Field(default_factory=dict)

    # Callback scheduling (if requested)
    callback_requested_at: str | None = None  # e.g. "tomorrow morning"

    # Webhook delivery
    webhook_payload: dict[str, Any] = Field(default_factory=dict)
    webhook_delivered: bool = False