"""In-memory event bus for domain events.

Provides a simple publish/subscribe mechanism. In production, this
could be replaced with a message queue or event store.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class Event:
    """Base class for all domain events."""

    pass


EventHandler = Callable[[Event], None]
"""Type alias for event handler functions."""


class EventBus:
    """Simple in-memory event bus.

    Supports synchronous publish/subscribe. Event handlers are called
    in order of registration.

    Usage::

        bus = EventBus()
        bus.register(EngagementCreated, my_handler)
        bus.publish(EngagementCreated(slug="test"))
    """

    def __init__(self) -> None:
        self._handlers: dict[type[Event], list[EventHandler]] = {}

    def register(self, event_type: type[Event], handler: EventHandler) -> None:
        """Register a handler for an event type.

        Args:
            event_type: The event class to subscribe to.
            handler: Callable that accepts an event instance.
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def unregister(self, event_type: type[Event], handler: EventHandler) -> None:
        """Unregister a handler from an event type.

        Args:
            event_type: The event class to unsubscribe from.
            handler: The handler to remove.
        """
        if event_type in self._handlers:
            self._handlers[event_type] = [
                h for h in self._handlers[event_type] if h is not handler
            ]

    def publish(self, event: Event) -> None:
        """Publish an event to all registered handlers.

        Args:
            event: The event instance to publish.
        """
        handlers = self._handlers.get(type(event), [])
        for handler in handlers:
            handler(event)

    def clear(self) -> None:
        """Remove all registered handlers."""
        self._handlers.clear()

    def has_handlers(self, event_type: type[Event]) -> bool:
        """Check if any handlers are registered for an event type.

        Args:
            event_type: The event class to check.

        Returns:
            True if at least one handler is registered.
        """
        return bool(self._handlers.get(event_type))
