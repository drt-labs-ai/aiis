"""Kafka ES-sink consumer — reads from aiis.observability and writes to Elasticsearch."""
from __future__ import annotations
import asyncio
import json
import logging
import os

from .topics import OBSERVABILITY

logger = logging.getLogger(__name__)


async def _run_consumer() -> None:
    servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "")
    if not servers:
        return

    try:
        from aiokafka import AIOKafkaConsumer  # type: ignore[import]
        consumer = AIOKafkaConsumer(
            OBSERVABILITY,
            bootstrap_servers=servers,
            group_id="aiis-es-sink",
            auto_offset_reset="latest",
            value_deserializer=lambda v: json.loads(v.decode()),
            enable_auto_commit=True,
        )
        await consumer.start()
        logger.info("Kafka ES-sink consumer started (topic=%s, group=aiis-es-sink)", OBSERVABILITY)
        try:
            async for msg in consumer:
                try:
                    from src.observability.events import ObservabilityEvent
                    from src.observability.elasticsearch_client import ingest_event_direct
                    event = ObservabilityEvent.model_validate(msg.value)
                    await ingest_event_direct(event)
                except Exception as exc:
                    logger.warning("ES sink failed for Kafka message: %s", exc)
        finally:
            await consumer.stop()
    except Exception as exc:
        logger.warning("Kafka consumer failed to start: %s", exc)


async def start_consumer() -> None:
    """Start the Kafka→ES sink consumer as a background task."""
    if not os.getenv("KAFKA_BOOTSTRAP_SERVERS", ""):
        logger.debug("KAFKA_BOOTSTRAP_SERVERS not set; Kafka consumer skipped")
        return
    asyncio.create_task(_run_consumer())
    logger.info("Kafka ES-sink consumer task scheduled")
