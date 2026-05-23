"""Tests for harness.state.temporal_server — Temporal dev server lifecycle."""

from __future__ import annotations

import socket
import subprocess
from unittest.mock import patch, MagicMock

import pytest

from harness.state.temporal_server import ensure_temporal_server


class TestEnsureTemporalServer:
    """Tests for ensure_temporal_server()."""

    def test_returns_true_when_already_running(self):
        """When port 7233 is open, return True without starting anything."""
        with patch("socket.socket") as mock_socket_cls:
            mock_sock = MagicMock()
            mock_socket_cls.return_value = mock_sock
            mock_sock.connect.return_value = None  # no error = connected

            result = ensure_temporal_server()

            assert result is True
            mock_sock.connect.assert_called_once_with(("127.0.0.1", 7233))
            # close() is called in both try and finally blocks
            assert mock_sock.close.call_count >= 1

    def test_starts_dev_server_when_not_running(self):
        """When port 7233 is closed, attempt to start the dev server."""
        with patch("socket.socket") as mock_socket_cls, \
             patch("subprocess.Popen") as mock_popen:

            mock_sock = MagicMock()
            mock_socket_cls.return_value = mock_sock
            mock_sock.connect.side_effect = ConnectionRefusedError("Connection refused")

            result = ensure_temporal_server()

            assert result is True
            mock_popen.assert_called_once()
            args, kwargs = mock_popen.call_args
            assert "temporal" in args[0]
            assert "server" in args[0]
            assert "start-dev" in args[0]

    def test_returns_false_when_cli_not_found(self):
        """When temporal CLI is not available, return False."""
        with patch("socket.socket") as mock_socket_cls, \
             patch("subprocess.Popen") as mock_popen:

            mock_sock = MagicMock()
            mock_socket_cls.return_value = mock_sock
            mock_sock.connect.side_effect = ConnectionRefusedError("refused")

            # Simulate FileNotFoundError when binary missing
            mock_popen.side_effect = FileNotFoundError("temporal not found")

            result = ensure_temporal_server()

            assert result is False

    def test_handles_oserror_on_connect(self):
        """Handle OSError (not just ConnectionRefusedError) gracefully."""
        with patch("socket.socket") as mock_socket_cls, \
             patch("subprocess.Popen") as mock_popen:

            mock_sock = MagicMock()
            mock_socket_cls.return_value = mock_sock
            mock_sock.connect.side_effect = OSError("Network unreachable")

            result = ensure_temporal_server()

            assert result is True  # Still tries to start

    def test_uses_db_filename_param(self):
        """The dev server should be started with --db-filename."""
        with patch("socket.socket") as mock_socket_cls, \
             patch("subprocess.Popen") as mock_popen:

            mock_sock = MagicMock()
            mock_socket_cls.return_value = mock_sock
            mock_sock.connect.side_effect = ConnectionRefusedError("refused")

            ensure_temporal_server()

            args, kwargs = mock_popen.call_args
            assert "--db-filename" in args[0]
            idx = args[0].index("--db-filename")
            assert "/tmp/temporal-dev.db" in args[0][idx + 1]

    def test_stdout_stderr_suppressed(self):
        """The subprocess should suppress stdout/stderr."""
        with patch("socket.socket") as mock_socket_cls, \
             patch("subprocess.Popen") as mock_popen:

            mock_sock = MagicMock()
            mock_socket_cls.return_value = mock_sock
            mock_sock.connect.side_effect = ConnectionRefusedError("refused")

            ensure_temporal_server()

            _, kwargs = mock_popen.call_args
            assert kwargs.get("stdout") == subprocess.DEVNULL
            assert kwargs.get("stderr") == subprocess.DEVNULL

    def test_socket_closed_after_check(self):
        """Socket should always be closed after connection attempt."""
        with patch("socket.socket") as mock_socket_cls, \
             patch("subprocess.Popen") as mock_popen:

            mock_sock = MagicMock()
            mock_socket_cls.return_value = mock_sock
            mock_sock.connect.side_effect = ConnectionRefusedError("refused")

            ensure_temporal_server()

            mock_sock.close.assert_called_once()

    def test_idempotent(self):
        """Calling twice should behave the same."""
        with patch("socket.socket") as mock_socket_cls, \
             patch("subprocess.Popen") as mock_popen:

            mock_sock = MagicMock()
            mock_socket_cls.return_value = mock_sock
            mock_sock.connect.return_value = None  # running

            r1 = ensure_temporal_server()
            r2 = ensure_temporal_server()

            assert r1 is True
            assert r2 is True
            # Should not have tried to start a subprocess
            mock_popen.assert_not_called()
