"""Tests for tracing.py: TraceLogger, set_trace_id, get_trace_id."""

from __future__ import annotations

import logging
import re

import pytest

from harness.tracing import (
    TraceLogger,
    get_trace_id,
    set_trace_id,
    trace_id_var,
)


@pytest.fixture(autouse=True)
def _reset_trace_id() -> None:
    """Reset trace ID before each test."""
    trace_id_var.set("")
    yield


class TestSetGetTraceId:
    """Tests for set_trace_id and get_trace_id."""

    def test_generates_id(self) -> None:
        tid = set_trace_id()
        assert isinstance(tid, str)
        assert len(tid) == 12  # uuid4.hex[:12]

    def test_uses_provided_id(self) -> None:
        tid = set_trace_id("my-trace-123")
        assert tid == "my-trace-123"

    def test_get_after_set(self) -> None:
        set_trace_id("test-abc")
        assert get_trace_id() == "test-abc"

    def test_get_default_empty(self) -> None:
        assert get_trace_id() == ""

    def test_multiple_sets(self) -> None:
        t1 = set_trace_id("first")
        t2 = set_trace_id("second")
        assert t1 != t2
        assert get_trace_id() == "second"

    def test_generates_unique_ids(self) -> None:
        ids = {set_trace_id() for _ in range(100)}
        assert len(ids) == 100  # All unique

    def test_id_format(self) -> None:
        tid = set_trace_id()
        assert re.match(r"^[0-9a-f]{12}$", tid)


class TestTraceLogger:
    """Tests for TraceLogger."""

    def test_info_includes_trace_id(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.INFO)
        set_trace_id("trace-001")
        logger = TraceLogger("test_logger")
        logger.info("Hello world")
        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert "trace-001" in record.getMessage()

    def test_warning_includes_trace_id(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.WARNING)
        set_trace_id("trace-002")
        logger = TraceLogger("test_logger")
        logger.warning("Something is off")
        assert len(caplog.records) == 1
        assert "trace-002" in caplog.records[0].getMessage()

    def test_error_includes_trace_id(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.ERROR)
        set_trace_id("trace-003")
        logger = TraceLogger("test_logger")
        logger.error("Something broke")
        assert len(caplog.records) == 1
        assert "trace-003" in caplog.records[0].getMessage()

    def test_debug_includes_trace_id(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.DEBUG)
        set_trace_id("trace-004")
        logger = TraceLogger("test_logger")
        logger.debug("Debug info")
        assert len(caplog.records) == 1
        assert "trace-004" in caplog.records[0].getMessage()

    def test_empty_trace_id(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.INFO)
        # Don't set a trace ID — should default to ""
        logger = TraceLogger("test_logger")
        logger.info("No trace set")
        assert len(caplog.records) == 1
        # The message should contain "[]" since trace_id is ""
        assert "[]" in caplog.records[0].getMessage()

    def test_trace_id_in_extra(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.INFO)
        set_trace_id("trace-extra")
        logger = TraceLogger("test_logger")
        logger.info("Test", extra={"custom": "value"})
        record = caplog.records[0]
        assert hasattr(record, "trace_id")
        assert record.trace_id == "trace-extra"

    def test_trace_id_across_loggers(self, caplog: pytest.LogCaptureFixture) -> None:
        """Trace ID should be consistent across different TraceLoggers."""
        caplog.set_level(logging.INFO)
        set_trace_id("shared-trace")
        logger1 = TraceLogger("logger.a")
        logger2 = TraceLogger("logger.b")
        logger1.info("From A")
        logger2.info("From B")
        for record in caplog.records:
            assert "shared-trace" in record.getMessage()
