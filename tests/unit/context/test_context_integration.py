"""Integration tests for DeltaContext + PassThroughContext — V7 §5.16–§5.17.

Tests the interaction between DeltaContext and PassThroughContext in
realistic workflow scenarios, including RippleEngine integration patterns.
"""

from __future__ import annotations

import pytest

from harness.context.delta_context import DeltaContext
from harness.context.pass_through_context import PassThroughContext


class TestDeltaAndPassThroughIntegration:
    """Tests combining DeltaContext and PassThroughContext."""

    def test_parallel_usage(self):
        """DeltaContext and PassThroughContext can be used independently."""
        delta = DeltaContext()
        ptc = PassThroughContext()

        assert delta.is_empty() is True
        assert ptc.has_any_passes() is False

    def test_phase_skips_based_on_delta_empty(self):
        """If DeltaContext is empty, the phase can be passed through."""
        delta = DeltaContext()
        ptc = PassThroughContext()

        # Phase completes with no context changes
        delta.add("analysis", {})
        if delta.is_empty():
            ptc.mark_passed("analysis")

        assert ptc.was_passed("analysis") is True

    def test_phase_not_skipped_when_delta_has_changes(self):
        """If DeltaContext has changes, the phase should NOT be passed through."""
        delta = DeltaContext()
        ptc = PassThroughContext()

        # Phase produces new artifacts
        delta.add("analysis", {"requirements.md": "new"})
        if not delta.is_empty():
            ptc.mark_changed("analysis")

        assert ptc.was_passed("analysis") is False
        assert ptc.get_changed_phases() == ["analysis"]

    def test_skip_unless_changed_with_delta_awareness(self):
        """Simulate the full pattern: delta tracks changes, ptc tracks passes."""
        delta = DeltaContext()
        ptc = PassThroughContext()

        # Phase 1: Analysis produces artifacts
        delta.add("analysis", {"requirements.md": "new"})
        ptc.mark_changed("analysis")

        # Phase 2: Design produces artifacts
        delta.add("design", {"architecture.md": "new"})
        ptc.mark_changed("design")

        # Phase 3: Implementation — no changes
        delta.add("implementation", {})
        ptc.mark_passed("implementation")

        # Phase 4: Review — needs context from analysis, design, implementation
        # But implementation had no changes, so skip it
        sources = ptc.skip_unless_changed(
            target_phase="review",
            source_phases=["analysis", "design", "implementation"],
        )
        assert sources == ["analysis", "design"]

        # Delta should show cumulative context from all three phases
        assert "requirements.md" in delta.get_delta()["new"]
        assert "architecture.md" in delta.get_delta()["new"]

    def test_clear_and_reuse_both(self):
        """Both contexts can be cleared and reused."""
        delta = DeltaContext()
        ptc = PassThroughContext()

        # First workflow
        delta.add("phase1", {"a.md": "new"})
        ptc.mark_changed("phase1")

        # Clear for second workflow
        delta.clear()
        ptc.clear()

        assert delta.is_empty() is True
        assert ptc.has_any_passes() is False
        assert ptc.has_any_changes() is False

    def test_delta_change_type_determines_pass_through(self):
        """Test that all three delta change types correctly prevent pass-through."""
        ptc = PassThroughContext()

        # New artifact
        delta_new = DeltaContext()
        delta_new.add("phase1", {"a.md": "new"})
        if not delta_new.is_empty():
            ptc.mark_changed("phase1")

        # Modified artifact
        delta_mod = DeltaContext()
        delta_mod.add("phase2", {"b.md": "modified"})
        if not delta_mod.is_empty():
            ptc.mark_changed("phase2")

        # Removed artifact
        delta_rem = DeltaContext()
        delta_rem.add("phase3", {"c.md": "removed"})
        if not delta_rem.is_empty():
            ptc.mark_changed("phase3")

        # Only passed-through phases should be excluded
        sources = ptc.skip_unless_changed(
            target_phase="final",
            source_phases=["phase1", "phase2", "phase3"],
        )
        assert set(sources) == {"phase1", "phase2", "phase3"}

    def test_incremental_delta_with_pass_through(self):
        """Simulate iterative refinement pattern."""
        delta = DeltaContext()
        ptc = PassThroughContext()

        # Iteration 1: Foundational work
        delta.add("iteration1", {"base.md": "new", "config.md": "new"})
        ptc.mark_changed("iteration1")

        # Iteration 2: Refines config — no new files
        delta.add("iteration2", {"config.md": "modified"})
        ptc.mark_changed("iteration2")

        # Iteration 3: Cleanup — no changes at all
        delta.add("iteration3", {})
        ptc.mark_passed("iteration3")

        # Iteration 4: Final review
        sources = ptc.skip_unless_changed(
            target_phase="iteration4",
            source_phases=["iteration1", "iteration2", "iteration3"],
        )
        assert sources == ["iteration1", "iteration2"]

        # Delta shows accumulated state
        full = delta.get_delta()
        assert "base.md" in full["new"]
        assert "config.md" in full["modified"]  # latest state wins: new → modified

    def test_empty_phase_is_pass_through(self):
        """A phase with no delta changes is automatically pass-through."""
        delta = DeltaContext()
        ptc = PassThroughContext()

        # Phase runs but produces no changes
        delta.add("empty_phase", {})
        if delta.is_empty():
            ptc.mark_passed("empty_phase")

        assert ptc.was_passed("empty_phase") is True

    def test_removing_delta_clears_pass_through(self):
        """When delta is cleared, pass-through should be re-evaluated."""
        delta = DeltaContext()
        ptc = PassThroughContext()

        # Phase 1 with changes
        delta.add("phase1", {"a.md": "new"})
        ptc.mark_changed("phase1")

        # Clear delta to simulate reset
        delta.clear()

        # Pass-Through Context still remembers phase1 as changed
        assert ptc.was_passed("phase1") is False

        # But delta is now empty
        assert delta.is_empty() is True

    def test_merge_delta_updates_pass_through_pattern(self):
        """Merging deltas should correctly reflect in pass-through logic."""
        delta = DeltaContext()
        ptc = PassThroughContext()

        # Phase 1
        delta.add("phase1", {"a.md": "new"})
        ptc.mark_changed("phase1")

        # Phase 2 — merged delta
        other = DeltaContext()
        other.add("phase2", {"b.md": "new"})
        delta.merge(other)
        ptc.mark_changed("phase2")

        sources = ptc.skip_unless_changed(
            target_phase="phase3",
            source_phases=["phase1", "phase2"],
        )
        assert sources == ["phase1", "phase2"]
