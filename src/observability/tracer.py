"""Distributed tracing utilities."""
from __future__ import annotations
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field

@dataclass
class TraceContext:
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    workflow_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    span_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_span_id: str | None = None

    def child_span(self) -> "TraceContext":
        return TraceContext(
            trace_id=self.trace_id,
            workflow_id=self.workflow_id,
            span_id=str(uuid.uuid4()),
            parent_span_id=self.span_id,
        )


_current_trace: ContextVar[TraceContext | None] = ContextVar("_current_trace", default=None)


def set_trace_context(ctx: TraceContext) -> None:
    _current_trace.set(ctx)


def get_trace_context() -> TraceContext:
    ctx = _current_trace.get()
    if ctx is None:
        ctx = TraceContext()
        _current_trace.set(ctx)
    return ctx


def new_trace_context(workflow_id: str | None = None) -> TraceContext:
    ctx = TraceContext(workflow_id=workflow_id or str(uuid.uuid4()))
    _current_trace.set(ctx)
    return ctx
