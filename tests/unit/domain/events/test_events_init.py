"""Tests for domain/events/__init__.py."""

from harness.domain.events import EventBus, EventHandler
from harness.domain.events.event_bus import Event


class TestDomainEventsInit:
    def test_event_base_class_accessible(self):
        """Event base class is importable from event_bus module."""
        assert Event is not None

    def test_event_bus_exported(self):
        """EventBus is re-exported."""
        assert EventBus is not None

    def test_event_handler_exported(self):
        """EventHandler is re-exported."""
        assert EventHandler is not None
