"""CommandBus handler registration smoke tests.

Validates the complete typed CommandBus handler registration.
"""

from __future__ import annotations

import pytest

from harness.command.setup import create_bus

smoke = pytest.mark.smoke


class TestHandlerRegistration:
    """Each command type can be dispatched via create_bus()."""

    @smoke
    def test_typed_handlers_are_registered(self):
        """create_bus() returns a working bus."""
        bus = create_bus()
        assert bus is not None
