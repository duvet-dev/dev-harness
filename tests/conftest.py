"""pytest configuration for core functional & feature tests.

Markers:
    e2e: Tests that require external dependencies (LLM APIs, live services).
         Excluded from default runs. Target with ``pytest -m e2e``.
         Include all with ``pytest -m ''``.
"""

from __future__ import annotations


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "e2e: tests requiring external dependencies (LLM APIs, live services). "
        "Skipped by default. Run with `pytest -m e2e`.",
    )
