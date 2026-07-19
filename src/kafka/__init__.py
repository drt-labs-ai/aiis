"""Kafka integration — event bus for AIIS observability."""
from .producer import publish, close_producer
from .consumer import start_consumer
from .topics import OBSERVABILITY

__all__ = ["publish", "close_producer", "start_consumer", "OBSERVABILITY"]
