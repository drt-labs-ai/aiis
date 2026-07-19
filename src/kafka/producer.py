"""Async Kafka producer — singleton, lazy-connect, silent on unavailability."""
from __future__ import annotations
import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_producer = None
_kafka_available: bool | None = None  # None=untried, True=up, False=down


def _bootstrap_servers() -> str:
    return os.getenv("KAFKA_BOOTSTRAP_SERVERS", "")


async def get_producer():
    global _producer, _kafka_available
    if _kafka_available is False:
        return None
    if _producer is not None:
        return _producer

    servers = _bootstrap_servers()
    if not servers:
        _kafka_available = False
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
        _kafka_available = True
        logger.info("Kafka producer connected to %s", servers)
        return _producer
    except Exception as exc:
        _kafka_available = False
        logger.warning("Kafka unavailable (%s); observability events go directly to ES", exc)
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
