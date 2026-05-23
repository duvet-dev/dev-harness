"""Temporal server lifecycle — start and check the dev server.

Extracted from ``temporal_adapter.py`` so both ``temporal_adapter`` and
``temporal_worker`` can use it without a circular import.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def ensure_temporal_server() -> bool:
    """Start Temporal dev server if not already running. Returns True if available.

    Checks port 7233. If unreachable and ``temporal server start-dev`` is
    available, starts the dev server as a background process. Idempotent.
    """
    import socket
    import subprocess

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect(("127.0.0.1", 7233))
        s.close()
        return True  # Already running
    except (ConnectionRefusedError, OSError):
        pass
    finally:
        s.close()

    # Try to start it
    try:
        subprocess.Popen(
            ["temporal", "server", "start-dev", "--db-filename",
             "/tmp/temporal-dev.db"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logger.info("Started Temporal dev server on port 7233")
        return True
    except FileNotFoundError:
        logger.warning("temporal CLI not found — cannot start dev server")
        return False
