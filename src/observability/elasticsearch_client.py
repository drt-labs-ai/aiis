"""Elasticsearch client for ingesting observability events."""
from __future__ import annotations
import logging
import os
from datetime import datetime, timezone
from .events import ObservabilityEvent

logger = logging.getLogger(__name__)

_ES_AVAILABLE = False
_es_client = None
_es_reachable: bool | None = None  # None = unknown, True/False = probed

try:
    from elasticsearch import AsyncElasticsearch
    _ES_AVAILABLE = True
except ImportError:
    pass


async def _get_client():
    global _es_client, _es_reachable
    if not _ES_AVAILABLE:
        return None
    # Once confirmed unreachable, skip silently
    if _es_reachable is False:
        return None
    if _es_client is None:
        url = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
        _es_client = AsyncElasticsearch(
            [url],
            max_retries=0,
            retry_on_timeout=False,
            request_timeout=2,
        )
    return _es_client


INDEX_PREFIX = "aiis-events"


def _index_name() -> str:
    date = datetime.now(timezone.utc).strftime("%Y.%m.%d")
    return f"{INDEX_PREFIX}-{date}"


async def ingest_event_direct(event: ObservabilityEvent) -> None:
    """Write an event directly to Elasticsearch (used by the Kafka ES-sink consumer)."""
    global _es_reachable, _es_client
    client = await _get_client()
    if client is None:
        logger.debug("ES unavailable; event dropped: %s | %s", event.event_type, event.message)
        return
    try:
        doc = event.model_dump(mode="json")
        await client.index(index=_index_name(), document=doc)
        _es_reachable = True
    except Exception as exc:
        # Reset to None (retry-eligible) rather than permanently disabling.
        # A transient timeout should not silence all future observability writes.
        _es_reachable = None
        _es_client = None
        logger.debug("ES ingest failed (will retry on next event): %s", exc)


async def ingest_event(event: ObservabilityEvent) -> None:
    """Publish event to Kafka topic aiis.observability. Events are dropped if Kafka is unavailable."""
    from src.kafka.producer import publish
    from src.kafka.topics import OBSERVABILITY
    published = await publish(OBSERVABILITY, event.model_dump(mode="json"))
    if not published:
        logger.warning("Kafka unavailable; observability event dropped: %s | %s", event.event_type, event.message)


async def ensure_index_template() -> None:
    global _es_reachable
    client = await _get_client()
    if client is None:
        return
    template = {
        "index_patterns": [f"{INDEX_PREFIX}-*"],
        "template": {
            "mappings": {
                "properties": {
                    "timestamp": {"type": "date"},
                    "trace_id": {"type": "keyword"},
                    "span_id": {"type": "keyword"},
                    "parent_span_id": {"type": "keyword"},
                    "workflow_id": {"type": "keyword"},
                    "issue_id": {"type": "integer"},
                    "agent": {"type": "keyword"},
                    "event_type": {"type": "keyword"},
                    "status": {"type": "keyword"},
                    "duration_ms": {"type": "integer"},
                    "message": {"type": "text"},
                    "error_details": {"type": "text"},
                    "metadata": {"type": "object", "dynamic": True},
                    "payload": {"type": "object", "dynamic": True},
                }
            }
        },
    }
    try:
        # ES 8.x: pass template fields as keyword args instead of body=
        await client.indices.put_index_template(
            name="aiis-template",
            index_patterns=template["index_patterns"],
            template=template["template"],
        )
        _es_reachable = True
        logger.info("Elasticsearch index template created/updated")
    except Exception as exc:
        # Template failure is non-fatal — events can still be ingested without it
        logger.info("ES template setup skipped (%s); events will still be ingested", type(exc).__name__)
