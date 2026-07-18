"""LangGraph shared state definition."""
from __future__ import annotations
from typing import Any, Annotated
from pydantic import BaseModel, Field
import operator
from src.a2a.messages import Domain, InvestigationResult, InvestigationRequest


class WorkflowState(BaseModel):
    """Shared state passed through the LangGraph workflow nodes."""

    # Issue data
    issue_id: int = 0
    title: str = ""
    description: str = ""
    labels: list[str] = Field(default_factory=list)
    author: str = ""

    # Tracing
    trace_id: str = ""
    workflow_id: str = ""
    span_id: str = ""

    # Routing
    assigned_domain: Domain | None = None
    routing_reason: str = ""
    assignees: list[str] = Field(default_factory=list)
    applied_labels: list[str] = Field(default_factory=list)

    # A2A
    investigation_request: InvestigationRequest | None = None
    investigation_result: InvestigationResult | None = None

    # GitHub update
    github_comment_posted: bool = False
    github_comment_url: str = ""

    # Control
    error: str | None = None
    completed: bool = False

    model_config = {"arbitrary_types_allowed": True}
