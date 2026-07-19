"""
Supervisor / Issue Triage Agent.

Responsibilities: Observe → Reason → Route → Delegate.
The supervisor NEVER investigates; it only triages and orchestrates.
"""
from __future__ import annotations
import logging
import os
import time
import uuid
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from src.a2a.client import get_a2a_client
from src.a2a.messages import Domain, InvestigationRequest, InvestigationStatus
from src.agents.state import WorkflowState
from src.mcp_server.tools.github_tools import add_comment, add_labels, assign_issue
from src.observability.events import EventType, ObservabilityEvent
from src.observability.elasticsearch_client import ingest_event
from src.observability.tracer import TraceContext, get_trace_context

logger = logging.getLogger(__name__)

PRE_PURCHASE_KEYWORDS = {
    "search", "plp", "pdp", "price", "pricing", "promotion", "cart",
    "checkout", "availability", "product", "catalog", "facet", "filter",
    "add to cart", "stock", "inventory", "browse",
}

POST_PURCHASE_KEYWORDS = {
    "order", "fulfillment", "shipping", "delivery", "return", "refund",
    "notification", "email", "tracking", "cancel", "invoice", "receipt",
    "payment failed", "dispatch", "warehouse",
}

SUPERVISOR_SYSTEM_PROMPT = """You are an Issue Triage Agent for an e-commerce platform.
Your sole responsibility is to analyze GitHub issues and determine:
1. Which domain owns this issue (pre-purchase or post-purchase)
2. Why you made that routing decision

Pre-purchase domain covers: search, product listing pages (PLP), product detail pages (PDP),
pricing, promotions, cart, checkout, availability, catalog browsing.

Post-purchase domain covers: orders, fulfillment, shipping, delivery, returns, refunds,
notifications, tracking, cancellations.

Respond with a JSON object:
{
  "domain": "pre-purchase" or "post-purchase",
  "reasoning": "one sentence explanation",
  "confidence": 0.0-1.0,
  "suggested_labels": ["label1", "label2"],
  "suggested_assignees": ["team-pre-purchase" or "team-post-purchase"]
}"""


def _keyword_classify(title: str, description: str) -> tuple[Domain, float]:
    text = (title + " " + description).lower()
    pre_score = sum(1 for kw in PRE_PURCHASE_KEYWORDS if kw in text)
    post_score = sum(1 for kw in POST_PURCHASE_KEYWORDS if kw in text)

    if pre_score > post_score:
        return Domain.PRE_PURCHASE, min(0.5 + pre_score * 0.05, 0.85)
    elif post_score > pre_score:
        return Domain.POST_PURCHASE, min(0.5 + post_score * 0.05, 0.85)
    else:
        return Domain.PRE_PURCHASE, 0.5  # default


def _get_llm():
    from src.llm.factory import get_llm, LLMRole
    return get_llm(LLMRole.SUPERVISOR, max_tokens=512)


async def _llm_classify(title: str, description: str) -> dict[str, Any] | None:
    llm = _get_llm()
    if llm is None:
        return None
    try:
        response = await llm.ainvoke([
            SystemMessage(content=SUPERVISOR_SYSTEM_PROMPT),
            HumanMessage(content=f"Issue Title: {title}\n\nDescription:\n{description[:2000]}"),
        ])
        import json, re
        text = response.content
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception as exc:
        logger.warning(f"LLM classification failed, falling back to keywords: {exc}")
    return None


class SupervisorAgent:
    async def triage(self, state: WorkflowState) -> WorkflowState:
        ctx = get_trace_context()
        await ingest_event(ObservabilityEvent(
            trace_id=ctx.trace_id,
            span_id=str(uuid.uuid4()),
            parent_span_id=ctx.span_id,
            workflow_id=state.workflow_id,
            issue_id=state.issue_id,
            agent="supervisor",
            event_type=EventType.SUPERVISOR_DECISION,
            status="STARTED",
            message=f"Triage started for issue #{state.issue_id}: {state.title[:80]}",
        ))

        start = time.monotonic()

        # Try LLM first, fall back to keyword matching
        llm_result = await _llm_classify(state.title, state.description)

        if llm_result:
            domain_str = llm_result.get("domain", "pre-purchase")
            domain = Domain.PRE_PURCHASE if "pre" in domain_str else Domain.POST_PURCHASE
            routing_reason = llm_result.get("reasoning", "LLM classification")
            suggested_labels = llm_result.get("suggested_labels", [domain_str])
            raw_assignees = llm_result.get("suggested_assignees", [f"team-{domain_str}"])
            assignees = raw_assignees if isinstance(raw_assignees, list) else [str(raw_assignees)]
            raw_labels = llm_result.get("suggested_labels", [domain_str])
            suggested_labels = raw_labels if isinstance(raw_labels, list) else [str(raw_labels)]
            confidence = llm_result.get("confidence", 0.7)
        else:
            domain, confidence = _keyword_classify(state.title, state.description)
            routing_reason = f"Keyword-based classification (pre={sum(1 for kw in PRE_PURCHASE_KEYWORDS if kw in (state.title + state.description).lower())}, post={sum(1 for kw in POST_PURCHASE_KEYWORDS if kw in (state.title + state.description).lower())})"
            suggested_labels = [domain.value, "auto-triaged"]
            assignees = [f"team-{domain.value}"]

        state.assigned_domain = domain
        state.routing_reason = routing_reason
        state.applied_labels = suggested_labels
        state.assignees = assignees

        logger.info(
            f"Supervisor routed issue #{state.issue_id} → {domain} "
            f"(confidence={confidence:.2f}, reason='{routing_reason}')"
        )

        # Apply GitHub labels and assignees via MCP
        try:
            await add_labels(state.issue_id, suggested_labels)
            await assign_issue(state.issue_id, assignees)
        except Exception as exc:
            logger.warning(f"GitHub update partially failed: {exc}")

        duration_ms = int((time.monotonic() - start) * 1000)
        await ingest_event(ObservabilityEvent(
            trace_id=ctx.trace_id,
            span_id=str(uuid.uuid4()),
            parent_span_id=ctx.span_id,
            workflow_id=state.workflow_id,
            issue_id=state.issue_id,
            agent="supervisor",
            event_type=EventType.SUPERVISOR_DECISION,
            status="SUCCESS",
            duration_ms=duration_ms,
            message=f"Routed to {domain}: {routing_reason}",
            metadata={"domain": domain, "confidence": confidence, "assignees": assignees},
            payload={
                "domain": str(domain),
                "routing_reason": routing_reason,
                "confidence": confidence,
                "suggested_labels": suggested_labels,
                "assignees": assignees,
                "llm_result": llm_result,
            },
        ))

        return state

    async def delegate(self, state: WorkflowState) -> WorkflowState:
        """Send A2A investigation request to the appropriate domain agent."""
        if not state.assigned_domain:
            state.error = "No domain assigned; cannot delegate"
            return state

        ctx = get_trace_context()
        request = InvestigationRequest(
            trace_id=state.trace_id,
            workflow_id=state.workflow_id,
            issue_id=state.issue_id,
            title=state.title,
            description=state.description,
            labels=state.labels,
            assigned_domain=state.assigned_domain,
        )
        state.investigation_request = request

        await ingest_event(ObservabilityEvent(
            trace_id=ctx.trace_id,
            span_id=str(uuid.uuid4()),
            workflow_id=state.workflow_id,
            issue_id=state.issue_id,
            agent="supervisor",
            event_type=EventType.A2A_REQUEST,
            status="SENT",
            message=f"Sending A2A request to {state.assigned_domain} agent",
            metadata={"domain": state.assigned_domain, "trace_id": state.trace_id},
            payload=request.model_dump(mode="json"),
        ))

        client = get_a2a_client()
        result = await client.send_investigation_request(request)
        state.investigation_result = result

        await ingest_event(ObservabilityEvent(
            trace_id=ctx.trace_id,
            span_id=str(uuid.uuid4()),
            workflow_id=state.workflow_id,
            issue_id=state.issue_id,
            agent="supervisor",
            event_type=EventType.A2A_RESPONSE,
            status="RECEIVED",
            duration_ms=result.duration_ms,
            message=f"Investigation result received: status={result.status}, confidence={result.confidence:.2f}",
            metadata={"status": result.status, "confidence": result.confidence},
            payload=result.model_dump(mode="json"),
        ))

        return state


_supervisor = SupervisorAgent()


def get_supervisor() -> SupervisorAgent:
    return _supervisor
