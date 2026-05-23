"""Temporal server lifecycle — start and check the dev server.

Handles automatic discovery, download, and lifecycle of the Temporal
CLI dev server binary. Supports:

1. ``temporal`` in PATH (already installed)
2. Bundled binary at ``scripts/_temporal/temporal`` (development)
3. Bundled binary at ``_temporal/temporal`` (PyInstaller single executable)
4. Auto-download to ``scripts/_temporal/temporal`` on first use
"""

from __future__ import annotations

import logging
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────

TEMPORAL_VERSION = "0.12.0"
"""Pin the Temporal CLI version — update when new releases are tested."""

TEMPORAL_PORT = 7233
"""Default Temporal dev server port."""

TEMPORAL_DB_PATH = "/tmp/temporal-dev.db"
"""Default SQLite database path for the dev server."""


def _get_temporal_binary() -> Optional[Path]:
    """Locate the ``temporal`` CLI binary.

    Search order:
    1. ``temporal`` in PATH
    2. ``scripts/_temporal/temporal`` — development source tree
    3. ``_temporal/temporal`` — bundled with PyInstaller single exe

    Returns:
        Absolute path to the binary, or ``None`` if not found.
    """
    # 1. Check PATH
    path_in_env = shutil.which("temporal")
    if path_in_env:
        return Path(path_in_env).resolve()

    # 2. Check development location
    script_rel = Path("scripts/_temporal/temporal")
    exe = _resolve_binary(script_rel)
    if exe:
        return exe

    # 3. Check PyInstaller bundled location
    bundle_rel = Path("_temporal/temporal")
    exe = _resolve_binary(bundle_rel)
    if exe:
        return exe

    return None


def _resolve_binary(rel: Path) -> Optional[Path]:
    """Resolve a relative path against several possible roots.

    Checks:
    - Current working directory
    - The directory containing this module (src/harness/state/)
    - The parent of this module's directory (src/harness/)
    - The project root
    """
    source_dir = Path(__file__).resolve().parent  # src/harness/state/
    candidates = [
        Path.cwd(),
        source_dir,
        source_dir.parent,        # src/harness/
        source_dir.parent.parent,  # src/
        source_dir.parent.parent.parent,  # project root
    ]

    for base in candidates:
        candidate = (base / rel).resolve()
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate

    return None


def download_temporal(target_dir: Optional[Path] = None) -> bool:
    """Download the Temporal CLI dev server binary.

    Downloads the platform-appropriate archive from GitHub releases
    and extracts just the ``temporal`` (or ``temporal.exe``) binary.

    Args:
        target_dir: Directory to download into. Defaults to
            ``scripts/_temporal/`` relative to the project root.

    Returns:
        ``True`` if successful, ``False`` on failure.
    """
    import io
    import tarfile
    import urllib.request
    import zipfile

    if target_dir is None:
        # Default: scripts/_temporal/ relative to project root
        target_dir = Path.cwd() / "scripts" / "_temporal"

    target_dir.mkdir(parents=True, exist_ok=True)

    # Determine platform
    system_map = {"Darwin": "darwin", "Linux": "linux", "Windows": "windows"}
    arch_map = {
        "arm64": "arm64", "x86_64": "amd64", "AMD64": "amd64",
        "aarch64": "arm64",
    }

    os_name = system_map.get(platform.system())
    arch = arch_map.get(platform.machine().lower())

    if not os_name or not arch:
        logger.error(
            "Unsupported platform: %s / %s",
            platform.system(), platform.machine(),
        )
        return False

    is_windows = os_name == "windows"
    ext = "zip" if is_windows else "tar.gz"
    binary_name = "temporal.exe" if is_windows else "temporal"
    url = (
        f"https://github.com/temporalio/cli/releases/download/"
        f"v{TEMPORAL_VERSION}/temporal_cli_{TEMPORAL_VERSION}"
        f"_{os_name}_{arch}.{ext}"
    )

    try:
        logger.info("Downloading Temporal CLI v%s from %s", TEMPORAL_VERSION, url)

        with urllib.request.urlopen(url, timeout=60) as response:
            data = response.read()

        if is_windows:
            import zipfile
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                zf.extract(binary_name, str(target_dir))
        else:
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
                tf.extract(binary_name, path=str(target_dir))

        binary_path = target_dir / binary_name
        binary_path.chmod(0o755)

        logger.info("Temporal CLI downloaded to %s", binary_path)
        return True

    except Exception as exc:
        logger.warning(
            "Failed to download Temporal CLI: %s. "
            "Install manually: temporal server start-dev",
            exc,
        )
        return False


def _start_dev_server(temporal_bin: Path) -> bool:
    """Start the Temporal dev server as a background process.

    Args:
        temporal_bin: Path to the ``temporal`` binary.

    Returns:
        ``True`` if the server was started, ``False`` otherwise.
    """
    try:
        proc = subprocess.Popen(
            [
                str(temporal_bin),
                "server", "start-dev",
                "--db-filename", TEMPORAL_DB_PATH,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logger.info(
            "Started Temporal dev server (PID %d) on port %d",
            proc.pid, TEMPORAL_PORT,
        )
        return True

    except FileNotFoundError:
        logger.warning("temporal binary not found at %s", temporal_bin)
        return False
    except Exception as exc:
        logger.warning("Failed to start Temporal dev server: %s", exc)
        return False


def ensure_temporal_server() -> bool:
    """Start Temporal dev server if not already running. Returns True if available.

    Checks port 7233. If unreachable, tries to start the dev server using
    the ``temporal`` CLI binary. The binary is resolved via:

    1. PATH
    2. Bundled location (``scripts/_temporal/`` or ``_temporal/``)
    3. Auto-downloaded to ``scripts/_temporal/``

    Idempotent — safe to call multiple times.
    """
    import socket

    # 1. Check if already running
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect(("127.0.0.1", TEMPORAL_PORT))
        s.close()
        return True  # Already running
    except (ConnectionRefusedError, OSError):
        pass
    finally:
        s.close()

    # 2. Locate or download the temporal binary
    temporal_bin = _get_temporal_binary()

    if temporal_bin is None:
        # Try auto-downloading
        logger.info("Temporal CLI not found — attempting auto-download...")
        download_dir = Path.cwd() / "scripts" / "_temporal"
        if download_temporal(download_dir):
            temporal_bin = download_dir / ("temporal.exe" if platform.system() == "Windows" else "temporal")

    if temporal_bin is None:
        logger.warning("Temporal CLI not found — cannot start dev server")
        return False

    # 3. Start the dev server
    return _start_dev_server(temporal_bin)
