"""Tests for Wave G handlers: SummaryHandler, InspectHandler, AssessHandler.

These handlers are delegation-thin — they delegate to real business components.
Pattern tests verify importability, registration, and handler interface compliance.
"""
from __future__ import annotations

import pytest

from harness.command.handlers import (
    AssessHandler,
    InspectHandler,
    SummaryHandler,
    register_all_handlers,
)
from harness.command.registry import CommandRegistry
from harness.command.types import CommandHandler

smoke = pytest.mark.smoke


class TestSummaryHandler:
    """Tests for SummaryHandler — pattern verification."""

    def test_importable(self):
        handler = SummaryHandler()
        assert isinstance(handler, SummaryHandler)
        assert isinstance(handler, CommandHandler)

    @smoke
    def test_summary_registered(self):
        registry = CommandRegistry()
        register_all_handlers(registry)
        assert "summary" in registry.list_registered()


class TestInspectHandler:
    """Tests for InspectHandler — pattern verification."""

    def test_importable(self):
        handler = InspectHandler()
        assert isinstance(handler, InspectHandler)
        assert isinstance(handler, CommandHandler)

    @smoke
    def test_inspect_registered(self):
        registry = CommandRegistry()
        register_all_handlers(registry)
        assert "inspect" in registry.list_registered()


class TestAssessHandler:
    """Tests for AssessHandler — pattern verification."""

    def test_importable(self):
        handler = AssessHandler()
        assert isinstance(handler, AssessHandler)
        assert isinstance(handler, CommandHandler)

    @smoke
    def test_assess_registered(self):
        registry = CommandRegistry()
        register_all_handlers(registry)
        assert "assess" in registry.list_registered()
