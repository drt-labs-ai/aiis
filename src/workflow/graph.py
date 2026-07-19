"""LangGraph workflow definition."""
from __future__ import annotations
import logging
import uuid
from typing import Any, Literal

from langgraph.graph import StateGraph, END

from src.agents.state import WorkflowState
from src.agents.supervisor.agent import get_supervisor
from src.github_client import get_issue
from src.mcp_server.tools.github_tools import add_comment
from src.observability.elasticsearch_client import ingest_event
from src.observability.events import EventType, ObservabilityEvent
from src.observability.tracer import get_trace_context, new_trace_context

logger = logging.getLogger(__name__)


# ─── Node functions ───────────────────────────────────────────────────────────

async def node_start(state: WorkflowState) -> WorkflowState:
    """Initialize tracing and fetch issue details."""
    ctx = new_trace_context(workflow_id=state.workflow_id or str(uuid.uuid4()))
    state.trace_id = ctx.trace_id
    state.workflow_id = ctx.workflow_id
    state.span_id = ctx.span_id

    await ingest_event(ObservabilityEvent(
        trace_id=ctx.trace_id,
        span_id=ctx.span_id,
        workflow_id=ctx.workflow_id,
        issue_id=state.issue_id,
        agent="workflow",
        event_type=EventType.WORKFLOW_STARTED,
        status="STARTED",
        message=f"Workflow started for issue #{state.issue_id}",
    ))

    # If we don't have a title yet, fetch from GitHub
    if not state.title and state.issue_id:
        try:
            issue = await get_issue(state.issue_id)
            if issue:
                state.title = issue.title
                state.description = issue.body
                state.labels = issue.labels
                state.author = issue.author
        except Exception as exc:
            logger.warning(f"Could not fetch issue from GitHub: {exc}")

    return state


async def node_triage(state: WorkflowState) -> WorkflowState:
    """Supervisor triage: classify and assign."""
    supervisor = get_supervisor()
    return await supervisor.triage(state)


async def node_delegate(state: WorkflowState) -> WorkflowState:
    """Supervisor delegation: send A2A request to domain agent."""
    supervisor = get_supervisor()
    return await supervisor.delegate(state)


async def node_update_github(state: WorkflowState) -> WorkflowState:
    """Post investigation result as GitHub comment."""
    result = state.investigation_result
    if not result:
        logger.warning("No investigation result; skipping GitHub update")
        return state

    ctx = get_trace_context()

    comment = _format_github_comment(state)
    try:
        resp = await add_comment(state.issue_id, comment)
        state.github_comment_posted = True
        state.github_comment_url = resp.get("html_url", "")
        logger.info(f"GitHub comment posted for issue #{state.issue_id}")
    except Exception as exc:
        logger.error(f"Failed to post GitHub comment: {exc}")
        state.error = str(exc)

    await ingest_event(ObservabilityEvent(
        trace_id=ctx.trace_id,
        span_id=str(uuid.uuid4()),
        workflow_id=state.workflow_id,
        issue_id=state.issue_id,
        agent="workflow",
        event_type=EventType.GITHUB_UPDATED,
        status="SUCCESS" if state.github_comment_posted else "ERROR",
        message=f"GitHub issue #{state.issue_id} updated",
        metadata={"comment_url": state.github_comment_url},
    ))

    return state


async def node_complete(state: WorkflowState) -> WorkflowState:
    """Mark workflow as complete."""
    ctx = get_trace_context()
    state.completed = True

    result = state.investigation_result
    await ingest_event(ObservabilityEvent(
        trace_id=ctx.trace_id,
        span_id=str(uuid.uuid4()),
        workflow_id=state.workflow_id,
        issue_id=state.issue_id,
        agent="workflow",
        event_type=EventType.WORKFLOW_COMPLETED,
        status="SUCCESS",
        message=f"Workflow completed for issue #{state.issue_id}",
        metadata={
            "domain": state.assigned_domain,
            "confidence": result.confidence if result else 0,
            "github_updated": state.github_comment_posted,
        },
    ))
    return state


async def node_error(state: WorkflowState) -> WorkflowState:
    """Handle workflow errors."""
    ctx = get_trace_context()
    await ingest_event(ObservabilityEvent(
        trace_id=ctx.trace_id,
        span_id=str(uuid.uuid4()),
        workflow_id=state.workflow_id,
        issue_id=state.issue_id,
        agent="workflow",
        event_type=EventType.WORKFLOW_FAILED,
        status="ERROR",
        message=f"Workflow failed: {state.error}",
        error_details=state.error,
    ))
    state.completed = True
    return state


def _format_github_comment(state: WorkflowState) -> str:
    result = state.investigation_result
    if not result:
        return "Investigation failed to produce a result."

    confidence_pct = f"{result.confidence:.0%}"
    domain_label = state.assigned_domain.replace("-", " ").title() if state.assigned_domain else "Unknown"

    lines = [
        "## 🤖 AI Investigation Report",
        "",
        f"**Assigned Domain:** {domain_label}  ",
        f"**Routing Reason:** {state.routing_reason}  ",
        f"**Confidence Score:** {confidence_pct}  ",
        f"**Investigation Iterations:** {result.iterations}  ",
        f"**Trace ID:** `{result.trace_id}`  ",
        "",
        "---",
        "",
        "### Summary",
        "",
        result.summary,
        "",
        "---",
        "",
        "### Root Cause Analysis",
        "",
        result.root_cause,
        "",
        "---",
        "",
        "### Investigation Steps",
        "",
    ]
    for i, step in enumerate(result.investigation_steps, 1):
        lines.append(f"{i}. {step}")

    lines += [
        "",
        "---",
        "",
        "### Knowledge Base Documents Referenced",
        "",
    ]
    for doc in result.knowledge_retrieved:
        lines.append(f"- `{doc}`")

    lines += [
        "",
        "---",
        "",
        "### Evidence Gathered",
        "",
    ]
    for ev in result.evidence[:5]:
        lines.append(f"**[{ev.source}]** (relevance: {ev.relevance_score:.2f})")
        lines.append(f"> {ev.content[:200]}...")
        lines.append("")

    lines += [
        "---",
        "",
        "### Recommended Next Steps",
        "",
    ]
    for action in result.recommended_actions:
        lines.append(f"- [ ] {action}")

    lines += [
        "",
        "---",
        "",
        f"*Generated by AIIS (Agentic Issue Investigation System) · Workflow `{state.workflow_id}`*",
    ]

    return "\n".join(lines)


# ─── Route functions ──────────────────────────────────────────────────────────

def route_after_triage(state: WorkflowState) -> Literal["delegate", "error"]:
    if state.error or not state.assigned_domain:
        return "error"
    return "delegate"


def route_after_delegate(state: WorkflowState) -> Literal["update_github", "error"]:
    if state.error or not state.investigation_result:
        return "error"
    return "update_github"


# ─── Build graph ─────────────────────────────────────────────────────────────

def build_workflow() -> StateGraph:
    graph = StateGraph(WorkflowState)

    graph.add_node("start", node_start)
    graph.add_node("triage", node_triage)
    graph.add_node("delegate", node_delegate)
    graph.add_node("update_github", node_update_github)
    graph.add_node("complete", node_complete)
    graph.add_node("error", node_error)

    graph.set_entry_point("start")
    graph.add_edge("start", "triage")
    graph.add_conditional_edges("triage", route_after_triage, {"delegate": "delegate", "error": "error"})
    graph.add_conditional_edges("delegate", route_after_delegate, {"update_github": "update_github", "error": "error"})
    graph.add_edge("update_github", "complete")
    graph.add_edge("complete", END)
    graph.add_edge("error", END)

    return graph.compile()


_compiled_workflow = None


def get_workflow():
    global _compiled_workflow
    if _compiled_workflow is None:
        _compiled_workflow = build_workflow()
    return _compiled_workflow
