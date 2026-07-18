"""A2A server that wraps a domain agent's handler."""
from __future__ import annotations
import logging
from typing import Any, Callable, Awaitable
from .registry import get_registry, AgentRegistration
from .transport import get_transport
from .messages import Domain

logger = logging.getLogger(__name__)

AgentHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class A2AServer:
    """Register a domain agent so it can receive A2A messages."""

    def __init__(self, agent_id: str, domain: Domain | None, description: str, capabilities: list[str]) -> None:
        self.agent_id = agent_id
        self._registry = get_registry()
        self._transport = get_transport()
        self._registration: AgentRegistration | None = None
        self._domain = domain
        self._description = description
        self._capabilities = capabilities

    def serve(self, handler: AgentHandler) -> None:
        self._registration = self._registry.register(
            agent_id=self.agent_id,
            domain=self._domain,
            description=self._description,
            capabilities=self._capabilities,
        )
        self._transport.register_handler(self.agent_id, handler)
        logger.info(f"A2AServer: '{self.agent_id}' is now serving")
