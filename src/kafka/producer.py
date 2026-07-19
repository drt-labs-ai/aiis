"""Async Kafka producer — singleton, lazy-connect, retries on each call after failure."""
from __future__ import annotations
import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_producer = None


def _bootstrap_servers() -> str:
    return os.getenv("KAFKA_BOOTSTRAP_SERVERS", "")


async def get_producer():
    """Return the singleton Kafka producer, connecting if not yet connected.

    Unlike the old implementation, a previous connection failure does NOT
    permanently disable Kafka — each call attempts to reconnect so that a
    transient Kafka unavailability at startup does not silently kill all
    observability for the lifetime of the process.
    """
    global _producer
    if _producer is not None:
        return _producer

    servers = _bootstrap_servers()
    if not servers:
        return None

    try:
        from aiokafka import AIOKafkaProducer  # type: ignore[import]
        p = AIOKafkaProducer(
            bootstrap_servers=servers,
            value_serializer=lambda v: json.dumps(v, default=str).encode(),
            request_timeout_ms=5000,
        )
        await p.start()
        _producer = p
        logger.info("Kafka producer connected to %s", servers)
        return _producer
    except Exception as exc:
        # Do NOT set a permanent failure flag — the next publish call will retry.
        logger.warning("Kafka unavailable (%s); event will be dropped", exc)
        return None


async def publish(topic: str, message: dict[str, Any]) -> bool:
    """Publish a JSON message to a Kafka topic. Returns False if Kafka is down."""
    producer = await get_producer()
    if producer is None:
        return False
    try:
        await producer.send_and_wait(topic, message)
        return True
    except Exception as exc:
        global _producer
        # Reset the singleton so the next call retries the connection rather
        # than reusing a broken producer indefinitely.
        _producer = None
        logger.warning("Kafka publish failed: %s", exc)
        return False


async def close_producer() -> None:
    global _producer
    if _producer is not None:
        try:
            await _producer.stop()
        except Exception:
            pass
        _producer = None
