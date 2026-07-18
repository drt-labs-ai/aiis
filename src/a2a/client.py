"""A2A client used by the supervisor to send investigation requests."""
from __future__ import annotations
import logging
import time
from .messages import (
    Domain,
    InvestigationRequest,
    InvestigationResult,
    InvestigationStatus,
)
from .registry import get_registry
from .transport import get_transport

logger = logging.getLogger(__name__)


class A2AClient:
    def __init__(self) -> None:
        self._transport = get_transport()
        self._registry = get_registry()

    async def send_investigation_request(
        self, request: InvestigationRequest
    ) -> InvestigationResult:
        agent_id = self._registry.resolve(request.assigned_domain)
        if not agent_id:
            raise RuntimeError(
                f"No agent registered for domain '{request.assigned_domain}'"
            )

        logger.info(
            f"A2A: sending InvestigationRequest to '{agent_id}' "
            f"(issue={request.issue_id}, trace={request.trace_id})"
        )

        start = time.monotonic()
        raw_response = await self._transport.send(
            recipient=agent_id,
            payload=request.model_dump(mode="json"),
        )
        duration_ms = int((time.monotonic() - start) * 1000)

        result = InvestigationResult.model_validate(raw_response)
        result.duration_ms = duration_ms
        logger.info(
            f"A2A: received InvestigationResult from '{agent_id}' "
            f"(status={result.status}, confidence={result.confidence:.2f}, "
            f"duration={duration_ms}ms)"
        )
        return result


_client = A2AClient()


def get_a2a_client() -> A2AClient:
    return _client
