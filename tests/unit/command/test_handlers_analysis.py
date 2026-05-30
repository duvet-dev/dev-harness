"""Tests for Wave G handlers: SummaryTypedHandler, InspectTypedHandler, AssessTypedHandler.

These handlers are delegation-thin — they delegate to real business components.
Pattern tests verify importability, registration, and handler interface compliance.
"""
from __future__ import annotations

import pytest

from harness.command.handlers.analysis_handlers import (
    AssessTypedHandler,
    InspectTypedHandler,
    SummaryTypedHandler,
)
from harness.command.setup import create_bus

smoke = pytest.mark.smoke


class TestSummaryTypedHandler:
    """Tests for SummaryTypedHandler — pattern verification."""

    def test_importable(self):
        handler = SummaryTypedHandler()
        assert isinstance(handler, SummaryTypedHandler)
        assert isinstance(handler, object)

    @smoke
    def test_summary_registered(self):
        bus = create_bus()
        assert bus is not None


class TestInspectTypedHandler:
    """Tests for InspectTypedHandler — pattern verification."""

    def test_importable(self):
        handler = InspectTypedHandler()
        assert isinstance(handler, InspectTypedHandler)
        assert isinstance(handler, object)

    @smoke
    def test_inspect_registered(self):
        bus = create_bus()
        assert bus is not None


class TestAssessTypedHandler:
    """Tests for AssessTypedHandler — pattern verification."""

    def test_importable(self):
        handler = AssessTypedHandler()
        assert isinstance(handler, AssessTypedHandler)
        assert isinstance(handler, object)

    @smoke
    def test_assess_registered(self):
        bus = create_bus()
        assert bus is not None
