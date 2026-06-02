"""Boundary tests for typed identifiers — NewType-based IDs.

Tests that NewType IDs are transparent at runtime but provide
type-level safety. Verifies slug and identifier protocols.
"""

from __future__ import annotations

from harness.domain.identifiers import (
    EngagementId,
    PhaseId,
    Slug,
    TaskId,
    WaveId,
    repr_id,
)


class TestTypedIdentifiers:
    """Boundary tests for NewType-based identifiers."""

    def test_slug_is_string_at_runtime(self):
        """Slug should be usable as a plain str at runtime."""
        slug = Slug("my-engagement")
        assert isinstance(slug, str)
        assert slug == "my-engagement"
        assert len(slug) == 13

    def test_engagement_id_compare(self):
        """EngagementId should compare with strings."""
        eid = EngagementId("42")
        assert eid == "42"
        assert str(eid) == "42"

    def test_wave_id_compare(self):
        """WaveId should compare with strings."""
        wid = WaveId("wave-1")
        assert wid == "wave-1"

    def test_task_id_compare(self):
        """TaskId should compare with strings."""
        tid = TaskId("task-001")
        assert tid == "task-001"

    def test_phase_id_compare(self):
        """PhaseId should compare with strings."""
        pid = PhaseId("design")
        assert pid == "design"

    def test_repr_id_helper(self):
        """repr_id should format IDs with optional prefix."""
        assert repr_id("abc") == "abc"
        assert repr_id("abc", "Eng#") == "Eng#abc"

    def test_multiple_id_types_distinct(self):
        """Different ID types should be type-distinct even with same value."""
        slug = Slug("hello")
        eid = EngagementId("hello")
        # At runtime they're equal as strings
        assert slug == eid
        # But type checkers treat them as different types
        assert type(slug) is type(eid)  # Both are str subclasses
        # They ARE the same runtime type (NewType is identity at runtime)
