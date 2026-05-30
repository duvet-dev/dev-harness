"""Tests for command errors module."""

from __future__ import annotations

import pytest

from harness.command.errors import HandlerError


class TestHandlerError:
    """Tests for HandlerError."""

    def test_default(self):
        err = HandlerError()
        assert str(err) == ""

    def test_with_message(self):
        err = HandlerError("custom error")
        assert str(err) == "custom error"

    def test_is_exception(self):
        assert issubclass(HandlerError, Exception)
