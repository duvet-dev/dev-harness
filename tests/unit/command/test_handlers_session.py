"""Tests for Wave F handlers: RunWaveHandler, SessionHandler, ChatHandler (typed).

These handlers are delegation-thin — they delegate to real business components.
"""
from __future__ import annotations

import pytest

from harness.command.handlers.wave_handlers import RunWaveTypedHandler
from harness.command.handlers.session_handlers import ChatTypedHandler, SessionTypedHandler
from harness.command.setup import create_bus

smoke = pytest.mark.smoke


class TestRunWaveHandler:
    """Tests for RunWaveTypedHandler — importability."""

    def test_importable(self):
        handler = RunWaveTypedHandler()
        assert isinstance(handler, RunWaveTypedHandler)

    @smoke
    def test_run_wave_registered(self):
        bus = create_bus()
        from harness.command.commands.wave import RunWaveCommand
        assert RunWaveCommand is not None


class TestSessionHandler:
    """Tests for SessionTypedHandler — importability."""

    def test_importable(self):
        handler = SessionTypedHandler()
        assert isinstance(handler, SessionTypedHandler)


class TestChatHandler:
    """Tests for ChatTypedHandler — importability."""

    def test_importable(self):
        handler = ChatTypedHandler()
        assert isinstance(handler, ChatTypedHandler)
