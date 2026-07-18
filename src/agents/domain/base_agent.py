"""Base class for domain investigation agents."""
from __future__ import annotations
import logging
import os
import time
import uuid
from abc import ABC, abstractmethod
from typing import Any

from src.a2a.messages import (
    Domain, EvidenceItem, InvestigationRequest, InvestigationResult, InvestigationStatus
)
from src.mcp_server.server import get_mcp_server
from src.observability.elasticsearch_client import ingest_event
from src.observability.events import EventType, ObservabilityEvent
from src.observability.tracer import get_trace_context
from src.rag.retriever import get_retriever

logger = logging.getLogger(__name__)

MAX_ITERATIONS = int(os.getenv("MAX_INVESTIGATION_ITERATIONS", "4"))
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.75"))


class BaseDomainAgent(ABC):
    domain: Domain
    agent_id: str

    @property
    @abstractmethod
    def service_areas(self) -> list[str]:
        """Areas this agent covers, used in MCP tool calls."""
        ...

    @property
    @abstractmethod
    def primary_services(self) -> list[str]:
        """Service names to check health/logs for."""
        ...

    async def investigate(self, request: InvestigationRequest) -> InvestigationResult:
        ctx = get_trace_context()
        start_time = time.monotonic()
        evidence: list[EvidenceItem] = []
        steps: list[str] = []
        knowledge_retrieved: list[str] = []
        iteration = 0
        confidence = 0.0
        root_cause = ""
        summary = ""
        recommended_actions: list[str] = []

        await ingest_event(ObservabilityEvent(
            trace_id=request.trace_id,
            span_id=str(uuid.uuid4()),
            workflow_id=request.workflow_id,
            issue_id=request.issue_id,
            agent=self.agent_id,
            event_type=EventType.INVESTIGATION_STARTED,
            status="STARTED",
            message=f"Investigation started for issue #{request.issue_id}",
        ))

        mcp = get_mcp_server()
        retriever = get_retriever()

        while iteration < MAX_ITERATIONS and confidence < CONFIDENCE_THRESHOLD:
            iteration += 1
            iter_start = time.monotonic()
            steps.append(f"Iteration {iteration}: gathering evidence")

            await ingest_event(ObservabilityEvent(
                trace_id=request.trace_id,
                span_id=str(uuid.uuid4()),
                workflow_id=request.workflow_id,
                issue_id=request.issue_id,
                agent=self.agent_id,
                event_type=EventType.INVESTIGATION_ITERATION,
                status="IN_PROGRESS",
                message=f"Iteration {iteration}/{MAX_ITERATIONS}",
                metadata={"iteration": iteration, "confidence": confidence},
            ))

            # Step 1: RAG search
            rag_start = time.monotonic()
            await ingest_event(ObservabilityEvent(
                trace_id=request.trace_id,
                span_id=str(uuid.uuid4()),
                workflow_id=request.workflow_id,
                issue_id=request.issue_id,
                agent=self.agent_id,
                event_type=EventType.RAG_SEARCH,
                status="STARTED",
                message=f"RAG search: '{request.title[:60]}'",
            ))

            rag_query = request.title if iteration == 1 else f"{request.title} {request.description[:200]}"
            rag_docs = retriever.search(query=rag_query, domain=self.domain.value, top_k=3)
            rag_duration = int((time.monotonic() - rag_start) * 1000)

            for doc in rag_docs:
                evidence.append(EvidenceItem(
                    source=f"RAG:{doc.source}",
                    content=doc.content[:400],
                    relevance_score=doc.relevance_score,
                ))
                if doc.filename not in knowledge_retrieved:
                    knowledge_retrieved.append(doc.filename)

            top_score = f"{rag_docs[0].relevance_score:.2f}" if rag_docs else "0"
            steps.append(f"RAG: retrieved {len(rag_docs)} docs (top score: {top_score})")

            await ingest_event(ObservabilityEvent(
                trace_id=request.trace_id,
                span_id=str(uuid.uuid4()),
                workflow_id=request.workflow_id,
                issue_id=request.issue_id,
                agent=self.agent_id,
                event_type=EventType.RAG_DOCUMENTS_RETRIEVED,
                status="SUCCESS",
                duration_ms=rag_duration,
                message=f"Retrieved {len(rag_docs)} documents",
                metadata={"doc_count": len(rag_docs), "sources": [d.source for d in rag_docs]},
            ))

            # Step 2: MCP tool calls
            tools_to_call = self._select_tools(iteration, request)
            for tool_name, tool_args in tools_to_call:
                tool_start = time.monotonic()
                await ingest_event(ObservabilityEvent(
                    trace_id=request.trace_id,
                    span_id=str(uuid.uuid4()),
                    workflow_id=request.workflow_id,
                    issue_id=request.issue_id,
                    agent=self.agent_id,
                    event_type=EventType.MCP_TOOL_CALL,
                    status="STARTED",
                    message=f"Calling MCP tool: {tool_name}",
                    metadata={"tool": tool_name, "args": tool_args},
                ))

                result = await mcp.call_tool(tool_name, tool_args)
                tool_duration = int((time.monotonic() - tool_start) * 1000)

                event_type = EventType.MCP_TOOL_COMPLETED if not result.is_error else EventType.MCP_TOOL_FAILED
                await ingest_event(ObservabilityEvent(
                    trace_id=request.trace_id,
                    span_id=str(uuid.uuid4()),
                    workflow_id=request.workflow_id,
                    issue_id=request.issue_id,
                    agent=self.agent_id,
                    event_type=event_type,
                    status="ERROR" if result.is_error else "SUCCESS",
                    duration_ms=tool_duration,
                    message=f"MCP tool '{tool_name}' {'failed' if result.is_error else 'completed'}",
                    metadata={"tool": tool_name, "duration_ms": tool_duration},
                ))

                if not result.is_error and result.content:
                    content_text = result.content[0].get("text", "") if result.content else ""
                    evidence.append(EvidenceItem(
                        source=f"MCP:{tool_name}",
                        content=content_text[:400],
                        relevance_score=0.7,
                    ))
                    steps.append(f"MCP tool '{tool_name}': {content_text[:100]}...")

            # Step 3: Evaluate confidence
            confidence = self._evaluate_confidence(iteration, evidence, rag_docs)
            iter_duration = int((time.monotonic() - iter_start) * 1000)
            logger.info(
                f"{self.agent_id}: iteration {iteration} complete "
                f"(confidence={confidence:.2f}, evidence={len(evidence)}, duration={iter_duration}ms)"
            )

        # Generate summary
        summary, root_cause, recommended_actions = self._synthesize(
            request, evidence, knowledge_retrieved, iteration, confidence
        )
        total_duration = int((time.monotonic() - start_time) * 1000)

        status = InvestigationStatus.COMPLETED if confidence >= CONFIDENCE_THRESHOLD else InvestigationStatus.COMPLETED

        result = InvestigationResult(
            trace_id=request.trace_id,
            workflow_id=request.workflow_id,
            issue_id=request.issue_id,
            status=status,
            confidence=confidence,
            summary=summary,
            root_cause=root_cause,
            recommended_actions=recommended_actions,
            investigation_steps=steps,
            evidence=evidence,
            knowledge_retrieved=knowledge_retrieved,
            duration_ms=total_duration,
            iterations=iteration,
        )

        await ingest_event(ObservabilityEvent(
            trace_id=request.trace_id,
            span_id=str(uuid.uuid4()),
            workflow_id=request.workflow_id,
            issue_id=request.issue_id,
            agent=self.agent_id,
            event_type=EventType.INVESTIGATION_FINISHED,
            status="SUCCESS",
            duration_ms=total_duration,
            message=f"Investigation complete (confidence={confidence:.2f}, iterations={iteration})",
            metadata={"confidence": confidence, "iterations": iteration, "evidence_count": len(evidence)},
        ))

        return result

    def _select_tools(self, iteration: int, request: InvestigationRequest) -> list[tuple[str, dict]]:
        """Select MCP tools to call based on iteration and issue content."""
        tools = []
        text = (request.title + " " + request.description).lower()

        if iteration == 1:
            # Always search for similar issues and check service health first
            tools.append(("search_issues", {"query": request.title}))
            if self.primary_services:
                tools.append(("service_health", {"service_name": self.primary_services[0]}))

        elif iteration == 2:
            # Check logs
            service = self.primary_services[0] if self.primary_services else "commerce-service"
            tools.append(("get_kibana_logs", {"service": service, "time_range_minutes": 60, "log_level": "ERROR"}))
            tools.append(("search_knowledge_base", {"query": request.title, "domain": self.domain.value, "top_k": 3}))

        elif iteration == 3:
            # Check traces and config
            service = self.primary_services[0] if self.primary_services else "commerce-service"
            tools.append(("get_dynatrace_traces", {"service": service}))
            # Look for feature flag or config mentions
            if any(kw in text for kw in ["feature", "flag", "config"]):
                tools.append(("configuration_lookup", {"key": "feature.checkout.new_flow"}))

        elif iteration == 4:
            # Retrieve runbook
            area = self.service_areas[0] if self.service_areas else "general"
            tools.append(("retrieve_runbook", {"runbook_name": area, "domain": self.domain.value}))

        return tools

    def _evaluate_confidence(self, iteration: int, evidence: list[EvidenceItem], rag_docs) -> float:
        base = min(0.3 + iteration * 0.15, 0.85)
        rag_boost = sum(d.relevance_score for d in rag_docs[:3]) / max(len(rag_docs[:3]), 1) * 0.15
        evidence_boost = min(len(evidence) * 0.03, 0.1)
        return min(round(base + rag_boost + evidence_boost, 2), 0.97)

    def _synthesize(
        self,
        request: InvestigationRequest,
        evidence: list[EvidenceItem],
        knowledge_retrieved: list[str],
        iterations: int,
        confidence: float,
    ) -> tuple[str, str, list[str]]:
        domain_label = self.domain.value.replace("-", " ").title()
        top_sources = [e.source for e in sorted(evidence, key=lambda x: x.relevance_score, reverse=True)[:3]]

        summary = (
            f"**{domain_label} Agent Investigation Summary**\n\n"
            f"Issue: {request.title}\n\n"
            f"After {iterations} investigation iteration(s) with confidence {confidence:.0%}, "
            f"the {domain_label} agent analyzed this issue using RAG knowledge retrieval and "
            f"{len([e for e in evidence if e.source.startswith('MCP')])} MCP tool calls.\n\n"
            f"**Key findings:**\n"
        )
        for e in evidence[:3]:
            summary += f"- [{e.source}] {e.content[:150]}...\n"

        root_cause = (
            f"Based on historical issues and current service state, this appears related to "
            f"{self.domain.value} service behavior. "
            f"Evidence gathered from: {', '.join(top_sources[:3])}."
        )

        recommended_actions = [
            f"Review {self.domain.value} service logs in Kibana for error patterns",
            f"Check service health dashboard for {', '.join(self.primary_services[:2])}",
            f"Reference runbook: {self.service_areas[0] if self.service_areas else 'general'} troubleshooting",
            f"Verify feature flags and configuration for impacted services",
            f"Escalate to {self.domain.value} team if issue persists > 2 hours",
        ]

        return summary, root_cause, recommended_actions

    async def handle_a2a_message(self, payload: dict) -> dict:
        """Handle incoming A2A messages (registered as transport handler)."""
        request = InvestigationRequest.model_validate(payload)
        result = await self.investigate(request)
        return result.model_dump(mode="json")
