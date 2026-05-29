"""Tests for PassThroughContext — unchanged context tracking — V7 §5.17.

Tests mark_passed, was_passed, mark_changed, get_passed_phases,
skip_unless_changed, clear, and error handling.
"""

from __future__ import annotations

import pytest

from harness.context.pass_through_context import PassThroughContext


class TestPassThroughContextCreation:
    """Tests for PassThroughContext initialisation."""

    def test_default_construction(self):
        ptc = PassThroughContext()
        assert ptc.get_passed_phases() == []
        assert ptc.has_any_passes() is False
        assert ptc.has_any_changes() is False
        assert ptc.all_recorded_phases == []

    def test_repr_empty(self):
        ptc = PassThroughContext()
        assert repr(ptc) == "PassThroughContext(passed=0, changed=0, total=0)"

    def test_equality(self):
        p1 = PassThroughContext()
        p2 = PassThroughContext()
        assert p1 == p2

    def test_inequality_with_non_pass_through(self):
        ptc = PassThroughContext()
        assert ptc.__eq__("not a ptc") is NotImplemented


class TestPassThroughContextMarkPassed:
    """Tests for PassThroughContext.mark_passed()."""

    def test_mark_passed_single(self):
        ptc = PassThroughContext()
        ptc.mark_passed("analysis")
        assert ptc.was_passed("analysis") is True
        assert ptc.get_passed_phases() == ["analysis"]
        assert ptc.has_any_passes() is True

    def test_mark_passed_multiple(self):
        ptc = PassThroughContext()
        ptc.mark_passed("analysis")
        ptc.mark_passed("design")
        ptc.mark_passed("implementation")
        assert ptc.get_passed_phases() == [
            "analysis", "design", "implementation",
        ]
        assert ptc.has_any_passes() is True

    def test_mark_passed_then_changed(self):
        ptc = PassThroughContext()
        ptc.mark_passed("analysis")
        ptc.mark_changed("analysis")
        assert ptc.was_passed("analysis") is False
        assert ptc.has_any_passes() is False
        assert ptc.has_any_changes() is True
        assert ptc.get_changed_phases() == ["analysis"]

    def test_mark_passed_twice(self):
        ptc = PassThroughContext()
        ptc.mark_passed("analysis")
        ptc.mark_passed("analysis")  # Should be idempotent
        assert ptc.get_passed_phases() == ["analysis"]

    def test_mark_passed_validation_type_error(self):
        ptc = PassThroughContext()
        with pytest.raises(TypeError, match="Expected str"):
            ptc.mark_passed(42)  # type: ignore

    def test_mark_passed_validation_value_error(self):
        ptc = PassThroughContext()
        with pytest.raises(ValueError, match="must not be empty"):
            ptc.mark_passed("")

    def test_mark_passed_validation_whitespace(self):
        ptc = PassThroughContext()
        with pytest.raises(ValueError, match="must not be empty"):
            ptc.mark_passed("   ")


class TestPassThroughContextMarkChanged:
    """Tests for PassThroughContext.mark_changed()."""

    def test_mark_changed_single(self):
        ptc = PassThroughContext()
        ptc.mark_changed("analysis")
        assert ptc.was_passed("analysis") is False
        assert ptc.has_any_changes() is True
        assert ptc.get_changed_phases() == ["analysis"]

    def test_mark_changed_after_passed(self):
        ptc = PassThroughContext()
        ptc.mark_passed("analysis")
        ptc.mark_changed("analysis")
        assert ptc.was_passed("analysis") is False
        assert ptc.get_passed_phases() == []
        assert ptc.get_changed_phases() == ["analysis"]

    def test_mark_changed_then_passed(self):
        ptc = PassThroughContext()
        ptc.mark_changed("analysis")
        ptc.mark_passed("analysis")
        assert ptc.was_passed("analysis") is True
        assert ptc.get_changed_phases() == []

    def test_mark_changed_validation_type_error(self):
        ptc = PassThroughContext()
        with pytest.raises(TypeError, match="Expected str"):
            ptc.mark_changed(42)  # type: ignore

    def test_mark_changed_validation_value_error(self):
        ptc = PassThroughContext()
        with pytest.raises(ValueError, match="must not be empty"):
            ptc.mark_changed("")


class TestPassThroughContextWasPassed:
    """Tests for PassThroughContext.was_passed()."""

    def test_was_passed_not_recorded(self):
        ptc = PassThroughContext()
        assert ptc.was_passed("analysis") is False

    def test_was_passed_after_mark(self):
        ptc = PassThroughContext()
        ptc.mark_passed("analysis")
        assert ptc.was_passed("analysis") is True

    def test_was_passed_after_clear(self):
        ptc = PassThroughContext()
        ptc.mark_passed("analysis")
        ptc.clear()
        assert ptc.was_passed("analysis") is False

    def test_was_passed_multiple_phases(self):
        ptc = PassThroughContext()
        ptc.mark_passed("analysis")
        ptc.mark_changed("design")
        assert ptc.was_passed("analysis") is True
        assert ptc.was_passed("design") is False
        assert ptc.was_passed("implementation") is False


class TestPassThroughContextGetPassedPhases:
    """Tests for PassThroughContext.get_passed_phases()."""

    def test_get_passed_phases_empty(self):
        ptc = PassThroughContext()
        assert ptc.get_passed_phases() == []

    def test_get_passed_phases_sorted(self):
        ptc = PassThroughContext()
        ptc.mark_passed("z_phase")
        ptc.mark_passed("a_phase")
        ptc.mark_passed("m_phase")
        assert ptc.get_passed_phases() == ["a_phase", "m_phase", "z_phase"]

    def test_get_passed_phases_excludes_changed(self):
        ptc = PassThroughContext()
        ptc.mark_passed("analysis")
        ptc.mark_changed("design")
        assert ptc.get_passed_phases() == ["analysis"]


class TestPassThroughContextGetChangedPhases:
    """Tests for PassThroughContext.get_changed_phases()."""

    def test_get_changed_phases_empty(self):
        ptc = PassThroughContext()
        assert ptc.get_changed_phases() == []

    def test_get_changed_phases_sorted(self):
        ptc = PassThroughContext()
        ptc.mark_changed("z_phase")
        ptc.mark_changed("a_phase")
        assert ptc.get_changed_phases() == ["a_phase", "z_phase"]

    def test_get_changed_phases_excludes_passed(self):
        ptc = PassThroughContext()
        ptc.mark_changed("analysis")
        ptc.mark_passed("design")
        assert ptc.get_changed_phases() == ["analysis"]


class TestPassThroughContextSkipUnlessChanged:
    """Tests for PassThroughContext.skip_unless_changed()."""

    def test_skip_all_passed(self):
        ptc = PassThroughContext()
        ptc.mark_passed("analysis")
        ptc.mark_passed("design")
        result = ptc.skip_unless_changed(
            target_phase="implementation",
            source_phases=["analysis", "design"],
        )
        assert result == []

    def test_include_changed(self):
        ptc = PassThroughContext()
        ptc.mark_changed("analysis")
        ptc.mark_passed("design")
        result = ptc.skip_unless_changed(
            target_phase="implementation",
            source_phases=["analysis", "design"],
        )
        assert result == ["analysis"]

    def test_include_unknown_phases(self):
        ptc = PassThroughContext()
        ptc.mark_passed("analysis")
        # "design" is not recorded at all
        result = ptc.skip_unless_changed(
            target_phase="implementation",
            source_phases=["analysis", "design"],
        )
        assert result == ["design"]  # Unknown phases are included

    def test_mixed_passed_changed_unknown(self):
        ptc = PassThroughContext()
        ptc.mark_passed("analysis")  # passed through
        ptc.mark_changed("design")   # changed
        # "testing" is unknown
        result = ptc.skip_unless_changed(
            target_phase="deploy",
            source_phases=["analysis", "design", "testing"],
        )
        assert result == ["design", "testing"]

    def test_all_changed(self):
        ptc = PassThroughContext()
        ptc.mark_changed("analysis")
        ptc.mark_changed("design")
        result = ptc.skip_unless_changed(
            target_phase="implementation",
            source_phases=["analysis", "design"],
        )
        assert result == ["analysis", "design"]

    def test_empty_source_list(self):
        ptc = PassThroughContext()
        result = ptc.skip_unless_changed(
            target_phase="implementation",
            source_phases=[],
        )
        assert result == []

    def test_skip_validation_type_error_target(self):
        ptc = PassThroughContext()
        with pytest.raises(TypeError, match="Expected str"):
            ptc.skip_unless_changed(42, ["analysis"])  # type: ignore

    def test_skip_validation_value_error_target(self):
        ptc = PassThroughContext()
        with pytest.raises(ValueError, match="must not be empty"):
            ptc.skip_unless_changed("", ["analysis"])

    def test_skip_validation_type_error_source(self):
        ptc = PassThroughContext()
        with pytest.raises(TypeError, match="Expected list"):
            ptc.skip_unless_changed("implementation", "not a list")  # type: ignore

    def test_skip_validation_type_error_source_element(self):
        ptc = PassThroughContext()
        with pytest.raises(TypeError, match="must be a string"):
            ptc.skip_unless_changed("implementation", [42])  # type: ignore

    def test_preserves_order(self):
        ptc = PassThroughContext()
        ptc.mark_changed("phase2")
        result = ptc.skip_unless_changed(
            target_phase="target",
            source_phases=["phase1", "phase2", "phase3"],
        )
        assert result == ["phase1", "phase2", "phase3"]

    def test_skip_unless_changed_mixed_phases(self):
        """Comprehensive test of filtering logic."""
        ptc = PassThroughContext()
        ptc.mark_passed("phase1")  # passed
        ptc.mark_changed("phase2")  # changed
        ptc.mark_passed("phase3")  # passed
        # phase4 is unknown
        result = ptc.skip_unless_changed(
            target_phase="final",
            source_phases=["phase1", "phase2", "phase3", "phase4"],
        )
        assert result == ["phase2", "phase4"]


class TestPassThroughContextClear:
    """Tests for PassThroughContext.clear()."""

    def test_clear_resets_all(self):
        ptc = PassThroughContext()
        ptc.mark_passed("analysis")
        ptc.mark_changed("design")
        ptc.clear()
        assert ptc.has_any_passes() is False
        assert ptc.has_any_changes() is False
        assert ptc.get_passed_phases() == []
        assert ptc.get_changed_phases() == []
        assert ptc.all_recorded_phases == []

    def test_clear_then_reuse(self):
        ptc = PassThroughContext()
        ptc.mark_passed("analysis")
        ptc.clear()
        ptc.mark_changed("design")
        assert ptc.was_passed("design") is False
        assert ptc.has_any_changes() is True

    def test_clear_empty(self):
        ptc = PassThroughContext()
        ptc.clear()  # Should not raise
        assert ptc.has_any_passes() is False


class TestPassThroughContextProperties:
    """Tests for PassThroughContext property accessors."""

    def test_all_recorded_phases_sorted(self):
        ptc = PassThroughContext()
        ptc.mark_passed("z_phase")
        ptc.mark_changed("a_phase")
        ptc.mark_passed("m_phase")
        assert ptc.all_recorded_phases == ["a_phase", "m_phase", "z_phase"]

    def test_all_recorded_phases_includes_both_types(self):
        ptc = PassThroughContext()
        ptc.mark_passed("analysis")
        ptc.mark_changed("design")
        assert "analysis" in ptc.all_recorded_phases
        assert "design" in ptc.all_recorded_phases

    def test_all_recorded_phases_empty(self):
        ptc = PassThroughContext()
        assert ptc.all_recorded_phases == []


class TestPassThroughContextEdgeCases:
    """Edge case tests for PassThroughContext."""

    def test_phase_name_edge_cases(self):
        ptc = PassThroughContext()
        ptc.mark_passed("phase-with-dashes")
        ptc.mark_changed("phase with spaces")
        ptc.mark_passed("Phase123")
        assert ptc.was_passed("phase-with-dashes") is True
        assert ptc.get_changed_phases() == ["phase with spaces"]
        assert ptc.was_passed("Phase123") is True

    def test_mark_passed_same_phase_from_different_agents_is_idempotent(self):
        ptc = PassThroughContext()
        ptc.mark_passed("analysis")
        ptc.mark_passed("analysis")
        assert ptc.get_passed_phases() == ["analysis"]

    def test_has_any_passes_false_when_only_changes(self):
        ptc = PassThroughContext()
        ptc.mark_changed("analysis")
        assert ptc.has_any_passes() is False

    def test_has_any_changes_false_when_only_passes(self):
        ptc = PassThroughContext()
        ptc.mark_passed("analysis")
        assert ptc.has_any_changes() is False

    def test_long_phase_names(self):
        ptc = PassThroughContext()
        long_name = "a" * 1000
        ptc.mark_passed(long_name)
        assert ptc.was_passed(long_name) is True
        assert ptc.get_passed_phases() == [long_name]

    def test_skip_unless_changed_no_phases_recorded(self):
        ptc = PassThroughContext()
        result = ptc.skip_unless_changed(
            target_phase="target",
            source_phases=["phase1", "phase2"],
        )
        # All unrecorded, so all included
        assert result == ["phase1", "phase2"]

    def test_repr_after_changes(self):
        ptc = PassThroughContext()
        ptc.mark_changed("phase1")
        ptc.mark_passed("phase2")
        assert repr(ptc) == "PassThroughContext(passed=1, changed=1, total=2)"


class TestPassThroughContextIntegration:
    """Integration-style tests for PassThroughContext usage patterns."""

    def test_typical_workflow_skip_pattern(self):
        """Simulate a typical workflow with pass-through optimization."""
        ptc = PassThroughContext()

        # Phase 1: Analysis produced changes
        ptc.mark_changed("analysis")

        # Phase 2: Design produced changes
        ptc.mark_changed("design")

        # Phase 3: Implementation — no changes (pass through)
        ptc.mark_passed("implementation")

        # Phase 4: Review needs context from analysis, design, implementation
        sources = ptc.skip_unless_changed(
            target_phase="review",
            source_phases=["analysis", "design", "implementation"],
        )
        # Only analysis and design changed — implementation passed through
        assert sources == ["analysis", "design"]

    def test_all_phases_passed_through(self):
        ptc = PassThroughContext()
        ptc.mark_passed("phase1")
        ptc.mark_passed("phase2")
        ptc.mark_passed("phase3")

        sources = ptc.skip_unless_changed(
            target_phase="final",
            source_phases=["phase1", "phase2", "phase3"],
        )
        assert sources == []

    def test_single_phase_workflow(self):
        ptc = PassThroughContext()
        ptc.mark_changed("analysis")

        sources = ptc.skip_unless_changed(
            target_phase="design",
            source_phases=["analysis"],
        )
        assert sources == ["analysis"]

    def test_clear_between_workflows(self):
        ptc = PassThroughContext()
        ptc.mark_passed("analysis")
        ptc.clear()

        # New workflow
        ptc.mark_changed("design")
        assert ptc.was_passed("analysis") is False
        assert ptc.get_changed_phases() == ["design"]

    def test_changed_then_passed_same_phase(self):
        ptc = PassThroughContext()
        ptc.mark_changed("analysis")
        ptc.mark_passed("analysis")

        # Should now be recorded as passed
        assert ptc.was_passed("analysis") is True
        assert ptc.get_changed_phases() == []

    def test_passed_then_changed_then_passed(self):
        ptc = PassThroughContext()
        ptc.mark_passed("analysis")
        ptc.mark_changed("analysis")
        ptc.mark_passed("analysis")

        assert ptc.was_passed("analysis") is True

    def test_multiple_skip_unless_changed_calls(self):
        ptc = PassThroughContext()
        ptc.mark_changed("phase1")
        ptc.mark_passed("phase2")

        # First call
        r1 = ptc.skip_unless_changed("target", ["phase1", "phase2"])
        assert r1 == ["phase1"]

        # Second call should be same (idempotent)
        r2 = ptc.skip_unless_changed("target", ["phase1", "phase2"])
        assert r2 == ["phase1"]
