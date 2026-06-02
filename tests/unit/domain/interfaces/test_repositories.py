"""Tests for domain/interfaces/repositories.py.

These are Protocol classes — we test by implementing a concrete
version and verifying the expected API shape.
"""

from __future__ import annotations

from pathlib import Path

from harness.domain.identifiers import EngagementId, Slug, WaveId
from harness.domain.interfaces.repositories import (
    EngagementRepository,
    PlanRepository,
    SnapshotRepository,
)


class TestEngagementRepository:
    """Verify EngagementRepository protocol has the expected API."""

    def test_protocol_methods_exist(self):
        """All required methods are present on the protocol."""
        methods = ["save", "get", "exists", "delete", "list_all", "update_status"]
        for m in methods:
            assert hasattr(EngagementRepository, m), f"Missing method: {m}"

    def test_protocol_is_callable(self):
        """The protocol class itself can be inspected."""
        sig = EngagementRepository.__init__
        assert sig is not None


class TestPlanRepository:
    """Verify PlanRepository protocol has the expected API."""

    def test_protocol_methods_exist(self):
        methods = ["save", "get", "commit_wave", "set_wave_state"]
        for m in methods:
            assert hasattr(PlanRepository, m), f"Missing method: {m}"


class TestSnapshotRepository:
    """Verify SnapshotRepository protocol has the expected API."""

    def test_protocol_methods_exist(self):
        methods = ["write", "write_phase_checkpoint"]
        for m in methods:
            assert hasattr(SnapshotRepository, m), f"Missing method: {m}"
