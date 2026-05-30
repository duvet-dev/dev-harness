"""Tests for Wave F handlers: RunWaveHandler, SessionHandler, ChatHandler.

These handlers are delegation-thin — they delegate to real business components.
Pattern tests verify importability, registration, and handler interface compliance.
Full integration behavior requires a harness project and is covered by smoke tests.
"""
from __future__ import annotations

import pytest

from harness.command.handlers import (
    ChatHandler,
    RunWaveHandler,
    SessionHandler,
    register_all_handlers,
)
from harness.command.registry import CommandRegistry
from harness.command.types import CommandHandler

smoke = pytest.mark.smoke


class TestRunWaveHandler:
    """Tests for RunWaveHandler — pattern verification."""

    def test_importable(self):
        handler = RunWaveHandler()
        assert isinstance(handler, RunWaveHandler)
        assert isinstance(handler, CommandHandler)

    @smoke
    def test_run_wave_registered(self):
        registry = CommandRegistry()
        register_all_handlers(registry)
        assert "run_wave" in registry.list_registered()


class TestSessionHandler:
    """Tests for SessionHandler — pattern verification."""

    def test_importable(self):
        handler = SessionHandler()
        assert isinstance(handler, SessionHandler)
        assert isinstance(handler, CommandHandler)

    @smoke
    def test_session_registered(self):
        registry = CommandRegistry()
        register_all_handlers(registry)
        assert "session" in registry.list_registered()


class TestChatHandler:
    """Tests for ChatHandler — pattern verification."""

    def test_importable(self):
        handler = ChatHandler()
        assert isinstance(handler, ChatHandler)
        assert isinstance(handler, CommandHandler)

    @smoke
    def test_chat_registered(self):
        registry = CommandRegistry()
        register_all_handlers(registry)
        assert "chat" in registry.list_registered()
