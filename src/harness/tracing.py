"""Trace ID infrastructure for structured logging.

Provides trace context via ContextVar for thread/async safety.
Present from Wave 1 — every dispatch, error, and state change
includes a trace ID.
"""

from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar
from typing import Any

trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")


class TraceLogger:
    """Logger that includes trace_id in all log records.

    Usage:
        logger = TraceLogger("harness.phase")
        logger.info("Step dispatched", extra={"step": step.name})
    """

    def __init__(self, name: str) -> None:
        self._logger = logging.getLogger(name)

    def _log(
        self, level: int, msg: str, *args: Any, **kwargs: Any
    ) -> None:
        tid = trace_id_var.get()
        extra = kwargs.pop("extra", {})
        extra["trace_id"] = tid
        self._logger.log(
            level, f"[{tid}] {msg}", *args, extra=extra, **kwargs
        )

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._log(logging.INFO, msg, *args, **kwargs)

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._log(logging.WARNING, msg, *args, **kwargs)

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._log(logging.ERROR, msg, *args, **kwargs)

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._log(logging.DEBUG, msg, *args, **kwargs)


def set_trace_id(trace_id: str | None = None) -> str:
    """Set a new trace ID (or generate one) and return it."""
    tid = trace_id or uuid.uuid4().hex[:12]
    trace_id_var.set(tid)
    return tid


def get_trace_id() -> str:
    """Get the current trace ID."""
    return trace_id_var.get()
