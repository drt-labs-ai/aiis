"""A2A message contracts using Pydantic."""
from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import uuid
from pydantic import BaseModel, Field


class MessageType(str, Enum):
    INVESTIGATION_REQUEST = "InvestigationRequest"
    INVESTIGATION_RESULT = "InvestigationResult"
    ERROR = "Error"


class Domain(str, Enum):
    PRE_PURCHASE = "pre-purchase"
    POST_PURCHASE = "post-purchase"


class InvestigationStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class InvestigationRequest(BaseModel):
    message_type: MessageType = MessageType.INVESTIGATION_REQUEST
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    workflow_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    issue_id: int
    title: str
    description: str
    labels: list[str] = Field(default_factory=list)
    assigned_domain: Domain
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidenceItem(BaseModel):
    source: str
    content: str
    relevance_score: float = 0.0
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class InvestigationResult(BaseModel):
    message_type: MessageType = MessageType.INVESTIGATION_RESULT
    trace_id: str
    workflow_id: str
    issue_id: int
    status: InvestigationStatus
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    summary: str = ""
    root_cause: str = ""
    recommended_actions: list[str] = Field(default_factory=list)
    investigation_steps: list[str] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    knowledge_retrieved: list[str] = Field(default_factory=list)
    error_message: str | None = None
    duration_ms: int = 0
    iterations: int = 0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


