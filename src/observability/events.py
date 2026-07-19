"""Structured event definitions for Elasticsearch."""
from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import uuid
from pydantic import BaseModel, Field


class EventType(str, Enum):
    WORKFLOW_STARTED = "WORKFLOW_STARTED"
    WORKFLOW_COMPLETED = "WORKFLOW_COMPLETED"
    WORKFLOW_FAILED = "WORKFLOW_FAILED"
    SUPERVISOR_DECISION = "SUPERVISOR_DECISION"
    A2A_REQUEST = "A2A_REQUEST"
    A2A_RESPONSE = "A2A_RESPONSE"
    A2A_ERROR = "A2A_ERROR"
    MCP_TOOL_CALL = "MCP_TOOL_CALL"
    MCP_TOOL_COMPLETED = "MCP_TOOL_COMPLETED"
    MCP_TOOL_FAILED = "MCP_TOOL_FAILED"
    RAG_SEARCH = "RAG_SEARCH"
    RAG_DOCUMENTS_RETRIEVED = "RAG_DOCUMENTS_RETRIEVED"
    INVESTIGATION_STARTED = "INVESTIGATION_STARTED"
    INVESTIGATION_ITERATION = "INVESTIGATION_ITERATION"
    INVESTIGATION_FINISHED = "INVESTIGATION_FINISHED"
    GITHUB_UPDATED = "GITHUB_UPDATED"
    GITHUB_ASSIGNED = "GITHUB_ASSIGNED"
    ERROR = "ERROR"
    RETRY = "RETRY"


class ObservabilityEvent(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    span_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    parent_span_id: str | None = None
    workflow_id: str = ""
    issue_id: int | None = None
    agent: str = ""
    event_type: EventType
    status: str = "SUCCESS"
    duration_ms: int | None = None
    message: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    payload: dict[str, Any] | None = None
    error_details: str | None = None
