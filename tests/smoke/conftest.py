"""Shared fixtures for smoke tests."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Iterator

import pytest


@pytest.fixture
def tmp_harness_project() -> Iterator[Path]:
    """Create a temporary directory and initialise it as a harness project.

    Yields the project root Path. Cleans up after the test.
    """
    tmp = Path(tempfile.mkdtemp(prefix="harness-smoke-"))
    try:
        from harness.cli.main import main
        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(main, ["init", str(tmp)])
        assert result.exit_code == 0, f"harness init failed: {result.output}"
        yield tmp
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
