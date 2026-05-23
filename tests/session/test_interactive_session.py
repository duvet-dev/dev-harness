"""Tests for InteractiveSession — shared REPL loop."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from harness.session.interactive import InteractiveSession
from harness.session.commands import CommandResult


class TestInteractiveSessionInit:
    """Tests for basic construction."""

    def test_minimal_init(self):
        session = InteractiveSession(
            root=Path("/tmp"),
            engagement_slug="test",
        )
        assert session.root == Path("/tmp")
        assert session.engagement_slug == "test"
        assert session._done is False
        assert session.client is None
        assert session.transcript is None


class TestInteractiveSessionHandleCommand:
    """Tests for handle_command() — command routing + effect execution."""

    def make_session(self, **overrides) -> InteractiveSession:
        kwargs = {
            "root": Path("/tmp"),
            "engagement_slug": "test",
            "command_router": lambda cmd, state: CommandResult(),
            "effect_executor": None,
        }
        kwargs.update(overrides)
        return InteractiveSession(**kwargs)

    def test_unknown_command_returns_true(self):
        session = self.make_session()
        result = session.handle_command("unknown", {})
        assert result is True
        assert session._done is False

    def test_exit_command_saves_transcript(self):
        session = self.make_session(
            command_router=lambda cmd, state: CommandResult(exit_loop=True),
        )
        result = session.handle_command("exit", {})
        assert result is False
        assert session._done is True

    def test_display_lines_are_echoed(self):
        lines = []
        session = self.make_session(
            command_router=lambda cmd, state: CommandResult(
                display_lines=["Hello", "World"],
            ),
        )
        with patch("click.echo") as mock_echo:
            session.handle_command("version", {})
            assert mock_echo.call_count == 2
            mock_echo.assert_any_call("Hello")
            mock_echo.assert_any_call("World")

    def test_save_transcript_echoes(self):
        session = self.make_session(
            command_router=lambda cmd, state: CommandResult(
                save_transcript=True,
            ),
        )
        session.transcript = MagicMock()
        session.transcript.save.return_value = "/tmp/transcript.md"

        with patch("click.echo") as mock_echo:
            session.handle_command("save", {})
            assert mock_echo.called
            assert "Transcript saved" in mock_echo.call_args[0][0]

    def test_effect_executor_called(self):
        effects = []

        def executor(result, session):
            effects.append(result)

        session = self.make_session(
            command_router=lambda cmd, state: CommandResult(
                advance_phase=True,
            ),
            effect_executor=executor,
        )
        session.handle_command("next", {})
        assert len(effects) == 1
        assert effects[0].advance_phase is True

    def test_reset_conversation(self):
        session = self.make_session(
            command_router=lambda cmd, state: CommandResult(
                reset_conversation=True,
            ),
        )
        session.client = MagicMock()
        session.client._messages = [{"role": "system", "content": "be helpful"}]
        session.client.system_prompt = "be helpful"

        with patch("click.echo"):
            session.handle_command("new", {})
            assert len(session.client._messages) == 1
            assert session.client._messages[0]["role"] == "system"


class TestInteractiveSessionSendToLLM:
    """Tests for _send_to_llm()."""

    @pytest.mark.asyncio
    async def test_sends_and_streams(self):
        session = InteractiveSession(
            root=Path("/tmp"),
            engagement_slug="test",
        )
        session.client = MagicMock()
        session.transcript = MagicMock()
        session.client.stream.return_value = async_iter(["Hello", " ", "world"])
        session.client.get_last_response.return_value = "Hello world"

        with patch("click.echo") as mock_echo:
            await session._send_to_llm("Hello")

        mock_echo.assert_any_call("Hello", nl=False)
        mock_echo.assert_any_call("world", nl=False)
        assert session.transcript.messages.append.called


def async_iter(items):
    """Helper to create an async iterator from a list."""
    class _AsyncIter:
        def __init__(self, items):
            self._items = iter(items)
        def __aiter__(self):
            return self
        async def __anext__(self):
            try:
                return next(self._items)
            except StopIteration:
                raise StopAsyncIteration
    return _AsyncIter(items)
