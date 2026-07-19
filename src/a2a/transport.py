"""In-memory async transport layer for A2A communication."""
from __future__ import annotations
import asyncio
import logging
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)

MessageHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class InMemoryTransport:
    """
    In-memory transport that mimics a distributed message bus.
    Replace with Kafka/NATS/HTTP for production deployment.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, MessageHandler] = {}
        self._message_log: list[dict[str, Any]] = []

    def register_handler(self, agent_id: str, handler: MessageHandler) -> None:
        self._handlers[agent_id] = handler
        logger.info(f"Transport: registered handler for agent '{agent_id}'")

    async def send(self, recipient: str, payload: dict[str, Any]) -> dict[str, Any]:
        if recipient not in self._handlers:
            raise ValueError(f"No handler registered for agent '{recipient}'")
        self._message_log.append({"to": recipient, "payload": payload})
        logger.debug(f"Transport: sending message to '{recipient}', type={payload.get('message_type')}")
        response = await self._handlers[recipient](payload)
        return response

    @property
    def message_log(self) -> list[dict[str, Any]]:
        return list(self._message_log)


# Singleton transport instance
_transport = InMemoryTransport()


def get_transport() -> InMemoryTransport:
    return _transport
