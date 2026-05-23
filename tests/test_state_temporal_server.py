"""Tests for harness.state.temporal_server — Temporal dev server lifecycle."""

from __future__ import annotations

import socket
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock, ANY

import pytest

from harness.state.temporal_server import (
    ensure_temporal_server,
    _get_temporal_binary,
    _resolve_binary,
    download_temporal,
    _start_dev_server,
    TEMPORAL_VERSION,
    TEMPORAL_PORT,
    TEMPORAL_DB_PATH,
)


class TestGetTemporalBinary:
    """Tests for _get_temporal_binary()."""

    def test_finds_in_path(self):
        with patch("harness.state.temporal_server.shutil.which", return_value="/usr/local/bin/temporal"):
            result = _get_temporal_binary()
            assert result is not None
            assert str(result) == "/usr/local/bin/temporal"

    def test_returns_none_when_not_found(self):
        with patch("harness.state.temporal_server.shutil.which", return_value=None), \
             patch("harness.state.temporal_server._resolve_binary", return_value=None):
            result = _get_temporal_binary()
            assert result is None

    def test_checks_bundled_scripts(self, tmp_path):
        script_dir = tmp_path / "scripts" / "_temporal"
        script_dir.mkdir(parents=True)
        binary = script_dir / "temporal"
        binary.write_text("#!/bin/sh\necho mock")
        binary.chmod(0o755)

        with patch("harness.state.temporal_server.shutil.which", return_value=None), \
             patch("harness.state.temporal_server._resolve_binary",
                   side_effect=lambda r: binary.resolve() if "scripts/_temporal" in str(r) else None):
            result = _get_temporal_binary()
            assert result is not None


class TestResolveBinary:
    """Tests for _resolve_binary()."""

    def test_finds_in_cwd(self, tmp_path):
        binary = tmp_path / "test_bin"
        binary.write_text("data")
        binary.chmod(0o755)
        with patch.object(Path, "cwd", return_value=tmp_path):
            result = _resolve_binary(Path("test_bin"))
            assert result == binary.resolve()

    def test_returns_none_when_not_found(self, tmp_path):
        with patch.object(Path, "cwd", return_value=tmp_path):
            result = _resolve_binary(Path("nonexistent"))
            assert result is None

    def test_ignores_non_executable(self, tmp_path):
        f = tmp_path / "test_bin"
        f.write_text("data")
        with patch.object(Path, "cwd", return_value=tmp_path):
            result = _resolve_binary(Path("test_bin"))
            # Not executable, should return None
            assert result is None


class TestDownloadTemporal:
    """Tests for download_temporal()."""

    def test_downloads_and_extracts(self, tmp_path):
        import tarfile
        import io

        # Create a fake tar.gz archive containing a 'temporal' binary
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tf:
            info = tarfile.TarInfo(name="temporal")
            info.type = tarfile.REGTYPE
            info.size = 4
            tf.addfile(info, io.BytesIO(b"data"))
        archive_data = buf.getvalue()

        with patch("urllib.request.urlopen") as mock_urlopen, \
             patch("platform.system", return_value="Darwin"), \
             patch("platform.machine", return_value="arm64"):
            mock_response = MagicMock()
            mock_response.read.return_value = archive_data
            mock_urlopen.return_value.__enter__.return_value = mock_response

            result = download_temporal(target_dir=tmp_path)

            assert result is True
            binary = tmp_path / "temporal"
            assert binary.exists()
            assert binary.stat().st_mode & 0o111  # executable

    def test_handles_download_failure(self, tmp_path):
        with patch("urllib.request.urlopen", side_effect=Exception("Network error")), \
             patch("platform.system", return_value="Darwin"), \
             patch("platform.machine", return_value="arm64"):
            result = download_temporal(target_dir=tmp_path)
            assert result is False

    def test_handles_unsupported_platform(self, tmp_path):
        with patch("platform.system", return_value="UnknownOS"):
            result = download_temporal(target_dir=tmp_path)
            assert result is False


class TestStartDevServer:
    """Tests for _start_dev_server()."""

    def test_starts_subprocess(self):
        bin_path = Path("/usr/local/bin/temporal")
        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock(pid=12345)

            result = _start_dev_server(bin_path)

            assert result is True
            mock_popen.assert_called_once_with(
                [
                    "/usr/local/bin/temporal",
                    "server", "start-dev",
                    "--db-filename", TEMPORAL_DB_PATH,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    def test_returns_false_on_filenotfound(self):
        with patch("subprocess.Popen", side_effect=FileNotFoundError):
            result = _start_dev_server(Path("/nonexistent/binary"))
            assert result is False

    def test_returns_false_on_generic_error(self):
        with patch("subprocess.Popen", side_effect=PermissionError("Denied")):
            result = _start_dev_server(Path("/usr/local/bin/temporal"))
            assert result is False


class TestEnsureTemporalServer:
    """Tests for ensure_temporal_server()."""

    def test_returns_true_when_already_running(self):
        """When port 7233 is open, return True without starting anything."""
        with patch("socket.socket") as mock_socket_cls:
            mock_sock = MagicMock()
            mock_socket_cls.return_value = mock_sock
            mock_sock.connect.return_value = None

            result = ensure_temporal_server()

            assert result is True
            mock_sock.connect.assert_called_once_with(("127.0.0.1", TEMPORAL_PORT))
            assert mock_sock.close.call_count >= 1

    def test_starts_dev_server_when_not_running(self):
        """When port 7233 is closed, attempt to start the dev server."""
        with patch("socket.socket") as mock_socket_cls, \
             patch("harness.state.temporal_server._get_temporal_binary") as mock_get, \
             patch("harness.state.temporal_server._start_dev_server") as mock_start:

            mock_sock = MagicMock()
            mock_socket_cls.return_value = mock_sock
            mock_sock.connect.side_effect = ConnectionRefusedError("refused")

            mock_get.return_value = Path("/usr/bin/temporal")
            mock_start.return_value = True

            result = ensure_temporal_server()

            assert result is True
            mock_start.assert_called_once()

    def test_returns_false_when_cli_not_found(self):
        """When temporal CLI is not available, return False."""
        with patch("socket.socket") as mock_socket_cls, \
             patch("harness.state.temporal_server._get_temporal_binary",
                   return_value=None), \
             patch("harness.state.temporal_server.download_temporal",
                   return_value=False):

            mock_sock = MagicMock()
            mock_socket_cls.return_value = mock_sock
            mock_sock.connect.side_effect = ConnectionRefusedError("refused")

            result = ensure_temporal_server()

            assert result is False

    def test_auto_downloads_when_missing(self):
        """When CLI not found, try auto-downloading."""
        temp_bin = Path("/tmp/mock_temporal")
        with patch("socket.socket") as mock_socket_cls, \
             patch("harness.state.temporal_server._get_temporal_binary",
                   return_value=None), \
             patch("harness.state.temporal_server.download_temporal",
                   return_value=True) as mock_dl, \
             patch("harness.state.temporal_server._start_dev_server",
                   return_value=True) as mock_start:

            mock_sock = MagicMock()
            mock_socket_cls.return_value = mock_sock
            mock_sock.connect.side_effect = ConnectionRefusedError("refused")

            result = ensure_temporal_server()

            assert result is True
            mock_dl.assert_called_once()
            mock_start.assert_called_once()

    def test_handles_oserror_on_connect(self):
        """Handle OSError (not just ConnectionRefusedError) gracefully."""
        with patch("socket.socket") as mock_socket_cls, \
             patch("harness.state.temporal_server._get_temporal_binary") as mock_get, \
             patch("harness.state.temporal_server._start_dev_server") as mock_start:

            mock_sock = MagicMock()
            mock_socket_cls.return_value = mock_sock
            mock_sock.connect.side_effect = OSError("Network unreachable")
            mock_get.return_value = Path("/usr/bin/temporal")
            mock_start.return_value = True

            result = ensure_temporal_server()

            assert result is True

    def test_uses_db_filename_param(self):
        """The dev server should be started with --db-filename."""
        with patch("socket.socket") as mock_socket_cls, \
             patch("harness.state.temporal_server._get_temporal_binary") as mock_get, \
             patch("harness.state.temporal_server._start_dev_server") as mock_start:

            mock_sock = MagicMock()
            mock_socket_cls.return_value = mock_sock
            mock_sock.connect.side_effect = ConnectionRefusedError("refused")
            mock_get.return_value = Path("/usr/bin/temporal")
            mock_start.return_value = True

            ensure_temporal_server()

            mock_start.assert_called_once_with(Path("/usr/bin/temporal"))

    def test_stdout_stderr_suppressed(self):
        """The subprocess should suppress stdout/stderr via _start_dev_server."""
        bin_path = Path("/usr/bin/temporal")
        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock(pid=1)
            _start_dev_server(bin_path)
            _, kwargs = mock_popen.call_args
            assert kwargs.get("stdout") == subprocess.DEVNULL
            assert kwargs.get("stderr") == subprocess.DEVNULL

    def test_socket_closed_after_check(self):
        """Socket should always be closed after connection attempt."""
        with patch("socket.socket") as mock_socket_cls, \
             patch("harness.state.temporal_server._get_temporal_binary") as mock_get, \
             patch("harness.state.temporal_server._start_dev_server") as mock_start:

            mock_sock = MagicMock()
            mock_socket_cls.return_value = mock_sock
            mock_sock.connect.side_effect = ConnectionRefusedError("refused")
            mock_get.return_value = Path("/usr/bin/temporal")
            mock_start.return_value = True

            ensure_temporal_server()

            mock_sock.close.assert_called_once()

    def test_idempotent(self):
        """Calling twice should behave the same."""
        with patch("socket.socket") as mock_socket_cls, \
             patch("harness.state.temporal_server._get_temporal_binary") as mock_get, \
             patch("harness.state.temporal_server._start_dev_server") as mock_start:

            mock_sock = MagicMock()
            mock_socket_cls.return_value = mock_sock
            mock_sock.connect.return_value = None
            mock_get.return_value = Path("/usr/bin/temporal")
            mock_start.return_value = True

            r1 = ensure_temporal_server()
            r2 = ensure_temporal_server()

            assert r1 is True
            assert r2 is True
            mock_start.assert_not_called()

class TestGetTemporalBinaryBundled:
    """Tests for _get_temporal_binary bundled binary discovery."""

    def test_finds_pyinstaller_bundled(self, tmp_path):
        """Discover binary in _temporal/temporal (PyInstaller bundle path)."""
        bundle_dir = tmp_path / "_temporal"
        bundle_dir.mkdir(parents=True)
        binary = bundle_dir / "temporal"
        binary.write_text("#!/bin/sh\necho mock")
        binary.chmod(0o755)

        with patch("harness.state.temporal_server.shutil.which", return_value=None), \
             patch("harness.state.temporal_server._resolve_binary",
                   side_effect=lambda r: binary.resolve() if "_temporal" in str(r) else None):
            result = _get_temporal_binary()
            assert result is not None

    def test_download_default_dir(self, tmp_path):
        """download_temporal with default target_dir creates scripts/_temporal/."""
        import io
        import tarfile

        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tf:
            info = tarfile.TarInfo(name="temporal")
            info.type = tarfile.REGTYPE
            info.size = 4
            tf.addfile(info, io.BytesIO(b"data"))
        archive_data = buf.getvalue()

        with patch("urllib.request.urlopen") as mock_urlopen, \
             patch("platform.system", return_value="Darwin"), \
             patch("platform.machine", return_value="arm64"), \
             patch.object(Path, "cwd", return_value=tmp_path):
            mock_response = MagicMock()
            mock_response.read.return_value = archive_data
            mock_urlopen.return_value.__enter__.return_value = mock_response

            result = download_temporal(target_dir=None)

            assert result is True
            expected = tmp_path / "scripts" / "_temporal" / "temporal"
            assert expected.exists()
