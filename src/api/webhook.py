"""FastAPI webhook receiver for GitHub issue events."""
from __future__ import annotations
import hashlib
import hmac
import logging
import os
import uuid
from typing import Any

from dotenv import load_dotenv
load_dotenv()  # load .env before any module reads os.getenv at import time

from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel

from src.agents.state import WorkflowState
from src.agents.domain import create_pre_purchase_agent, create_post_purchase_agent
from src.observability.logger import configure_logging
from src.observability.elasticsearch_client import ensure_index_template
from src.kafka.consumer import start_consumer as start_kafka_consumer
from src.rag.indexer import index_knowledge_base
from src.workflow.graph import get_workflow

logger = logging.getLogger(__name__)

configure_logging(os.getenv("LOG_LEVEL", "INFO"))

app = FastAPI(title="AIIS - Agentic Issue Investigation System", version="1.0.0")

_initialized = False


@app.on_event("startup")
async def startup():
    global _initialized
    if _initialized:
        return
    # Register domain agents
    create_pre_purchase_agent()
    create_post_purchase_agent()
    # Ensure ES template
    await ensure_index_template()
    # Start Kafka→ES sink consumer (no-op if KAFKA_BOOTSTRAP_SERVERS not set)
    await start_kafka_consumer()
    # Index knowledge base
    try:
        counts = index_knowledge_base(os.getenv("KNOWLEDGE_BASE_DIR", "./knowledge-base"))
        logger.info(f"Knowledge base indexed: {counts}")
    except Exception as exc:
        logger.warning(f"Knowledge base indexing failed (non-fatal): {exc}")
    _initialized = True
    logger.info("AIIS startup complete")


class GitHubIssuePayload(BaseModel):
    action: str
    issue: dict[str, Any]
    repository: dict[str, Any] | None = None
    sender: dict[str, Any] | None = None


def _verify_signature(body: bytes, secret: str, signature: str | None) -> bool:
    if not secret or not signature:
        return True  # Allow if not configured
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@app.post("/webhook/github")
async def github_webhook(
    request: Request,
    x_github_event: str | None = Header(None),
    x_hub_signature_256: str | None = Header(None),
):
    body = await request.body()
    secret = os.getenv("GITHUB_WEBHOOK_SECRET", "")

    if not _verify_signature(body, secret, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    if x_github_event != "issues":
        return {"status": "ignored", "event": x_github_event}

    payload = GitHubIssuePayload.model_validate(await request.json())
    if payload.action != "opened":
        return {"status": "ignored", "action": payload.action}

    issue = payload.issue
    workflow_id = str(uuid.uuid4())

    state = WorkflowState(
        issue_id=issue["number"],
        title=issue.get("title", ""),
        description=issue.get("body") or "",
        labels=[l["name"] for l in issue.get("labels", [])],
        author=issue.get("user", {}).get("login", "unknown"),
        workflow_id=workflow_id,
    )

    logger.info(f"Received GitHub issue #{state.issue_id}: {state.title[:80]}")

    import asyncio
    asyncio.create_task(_run_workflow(state))

    return {"status": "accepted", "workflow_id": workflow_id, "issue_id": state.issue_id}


@app.post("/investigate")
async def investigate_issue(payload: dict[str, Any]):
    """Direct trigger endpoint for testing without a webhook."""
    workflow_id = str(uuid.uuid4())
    state = WorkflowState(
        issue_id=payload.get("issue_id", 0),
        title=payload.get("title", ""),
        description=payload.get("description", ""),
        labels=payload.get("labels", []),
        workflow_id=workflow_id,
    )
    result_state = await _run_workflow(state)
    return {
        "workflow_id": workflow_id,
        "issue_id": state.issue_id,
        "domain": result_state.assigned_domain,
        "confidence": result_state.investigation_result.confidence if result_state.investigation_result else 0,
        "completed": result_state.completed,
        "github_updated": result_state.github_comment_posted,
        "summary": result_state.investigation_result.summary[:500] if result_state.investigation_result else "",
    }


@app.get("/health")
async def health():
    return {"status": "ok", "service": "aiis"}


async def _run_workflow(state: WorkflowState) -> WorkflowState:
    workflow = get_workflow()
    try:
        raw = await workflow.ainvoke(state)
        # LangGraph returns a dict when Pydantic is the state schema
        return WorkflowState.model_validate(raw) if isinstance(raw, dict) else raw
    except Exception as exc:
        logger.exception(f"Workflow failed for issue #{state.issue_id}: {exc}")
        state.error = str(exc)
        state.completed = True
        return state
