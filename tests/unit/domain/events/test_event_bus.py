"""Tests for domain/events/event_bus.py: Event, EventBus."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from harness.domain.events.event_bus import Event, EventBus


# ── Fixtures ────────────────────────────────────────────────────────────────


@dataclass
class SampleEvent(Event):
    """A simple test event."""
    name: str
    value: int = 0


@dataclass
class OtherEvent(Event):
    """Another event type for testing filtering."""
    label: str = ""


@pytest.fixture
def bus() -> EventBus:
    return EventBus()


# ── Event base class ────────────────────────────────────────────────────────


class TestEventBase:
    def test_event_equality_by_type(self):
        """Events are compared by type, not by __eq__."""
        e1 = SampleEvent(name="a")
        e2 = SampleEvent(name="b")
        assert type(e1) is type(e2)  # same type

    def test_event_data(self):
        e = SampleEvent(name="hello", value=42)
        assert e.name == "hello"
        assert e.value == 42

    def test_event_repr(self):
        e = SampleEvent(name="x")
        r = repr(e)
        assert "SampleEvent" in r
        assert "name=" in r


# ── EventBus: subscribe / publish / unsubscribe ─────────────────────────────


class TestEventBusSubscribe:
    def test_subscribe_and_publish(self, bus: EventBus):
        """A subscriber receives events published to the bus."""
        received: list[Event] = []

        bus.register(SampleEvent, received.append)
        bus.publish(SampleEvent(name="hello", value=1))

        assert len(received) == 1
        assert received[0].name == "hello"

    def test_subscribe_only_receives_matching_type(self, bus: EventBus):
        """Subscribers only get events of the type they subscribed to."""
        test_events: list[SampleEvent] = []
        other_events: list[OtherEvent] = []

        bus.register(SampleEvent, test_events.append)
        bus.register(OtherEvent, other_events.append)

        bus.publish(SampleEvent(name="only-test"))
        bus.publish(OtherEvent(label="only-other"))

        assert len(test_events) == 1
        assert len(other_events) == 1
        assert test_events[0].name == "only-test"
        assert other_events[0].label == "only-other"

    def test_multiple_subscribers_same_type(self, bus: EventBus):
        """Multiple subscribers for the same event type all receive events."""
        received_a: list[SampleEvent] = []
        received_b: list[SampleEvent] = []

        bus.register(SampleEvent, received_a.append)
        bus.register(SampleEvent, received_b.append)

        bus.publish(SampleEvent(name="both"))

        assert len(received_a) == 1
        assert len(received_b) == 1

    def test_publish_no_subscribers(self, bus: EventBus):
        """Publishing with no subscribers does nothing."""
        bus.publish(SampleEvent(name="ghost"))  # no error

    def test_unregister(self, bus: EventBus):
        """Unregistering removes the handler."""
        received: list[SampleEvent] = []

        handler = received.append
        bus.register(SampleEvent, handler)
        bus.unregister(SampleEvent, handler)
        bus.publish(SampleEvent(name="gone"))

        assert len(received) == 0

    def test_unregister_nonexistent_handler(self, bus: EventBus):
        """Unregistering a handler that was never added is a no-op."""
        def handler(event: Event) -> None:
            pass
        bus.unregister(SampleEvent, handler)  # no error

    def test_publish_multiple_events(self, bus: EventBus):
        """Multiple publishes all reach subscribers."""
        received: list[SampleEvent] = []

        bus.register(SampleEvent, received.append)

        for i in range(5):
            bus.publish(SampleEvent(name=f"e{i}", value=i))

        assert len(received) == 5
        assert received[-1].value == 4

    def test_handler_called_with_event_object(self, bus: EventBus):
        """The handler receives the actual event object."""
        events: list[SampleEvent] = []

        bus.register(SampleEvent, lambda e: events.append(e))
        original = SampleEvent(name="orig", value=99)
        bus.publish(original)

        assert events[0] is original  # same object


# ── Edge cases ──────────────────────────────────────────────────────────────


class TestEventBusEdgeCases:
    def test_register_same_handler_twice(self, bus: EventBus):
        """Registering the same handler twice results in double delivery."""
        received: list[SampleEvent] = []
        handler = received.append

        bus.register(SampleEvent, handler)
        bus.register(SampleEvent, handler)
        bus.publish(SampleEvent(name="double"))

        assert len(received) == 2  # called twice

    def test_unregister_removes_all_copies(self, bus: EventBus):
        """Unregistering removes all copies of a duplicate handler."""
        received: list[SampleEvent] = []
        handler = received.append

        bus.register(SampleEvent, handler)
        bus.register(SampleEvent, handler)
        bus.unregister(SampleEvent, handler)
        bus.publish(SampleEvent(name="one"))

        assert len(received) == 0  # all copies removed

    def test_handler_raises_error(self, bus: EventBus):
        """A handler that raises doesn't prevent other handlers from running."""
        received: list[SampleEvent] = []

        def failing_handler(event: Event) -> None:
            raise RuntimeError("Handler failed")

        bus.register(SampleEvent, failing_handler)
        bus.register(SampleEvent, received.append)

        with pytest.raises(RuntimeError):
            bus.publish(SampleEvent(name="fail"))
        # The second handler should NOT have been called because the
        # first handler's exception propagates immediately.
        # (This is the current design — synchronous, no error isolation.)

    def test_clear_removes_all_handlers(self, bus: EventBus):
        """Clear removes all registered handlers."""
        received: list[SampleEvent] = []
        bus.register(SampleEvent, received.append)
        bus.clear()
        bus.publish(SampleEvent(name="after_clear"))
        assert len(received) == 0

    def test_has_handlers_true_when_registered(self, bus: EventBus):
        """has_handlers returns True when handlers are registered."""
        bus.register(SampleEvent, lambda e: None)
        assert bus.has_handlers(SampleEvent) is True

    def test_has_handlers_false_when_none(self, bus: EventBus):
        """has_handlers returns False when no handlers registered."""
        assert bus.has_handlers(SampleEvent) is False

    def test_has_handlers_after_clear(self, bus: EventBus):
        """has_handlers returns False after clear()."""
        bus.register(SampleEvent, lambda e: None)
        bus.clear()
        assert bus.has_handlers(SampleEvent) is False

    def test_has_handlers_unregistered_type(self, bus: EventBus):
        """has_handlers returns False for a type that was never registered."""
        assert bus.has_handlers(OtherEvent) is False

    def test_is_empty_init(self, bus: EventBus):
        """New EventBus has no handlers."""
        assert bus._handlers == {}
