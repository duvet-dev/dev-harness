"""Tests for harness.session.helpers — phase resolution, aliases, workflow phases.

Tests cover:
- PHASE_ALIASES dict is correctly defined
- resolve_phase resolves aliased names correctly
- get_phase_definition resolves aliases and returns definitions
- get_phase_definition returns None for unknown phases
- PHASES_BY_WORKFLOW is initialized as empty dict
- get_phases_for_workflow falls back to get_phases() for unknown workflows
- get_phases returns phases from phases.yaml
"""

from __future__ import annotations

from harness.session.helpers import (
    PHASE_ALIASES,
    PHASES_BY_WORKFLOW,
    get_phases_for_workflow,
    resolve_phase,
    get_phase_definition,
)
from harness.session.phase_source import get_phases, find_phase, is_transition_allowed


class TestPhaseAliases:
    """Tests for PHASE_ALIASES."""

    def test_alias_build_to_build(self) -> None:
        assert PHASE_ALIASES["build"] == "build"

    def test_alias_test_to_test(self) -> None:
        assert PHASE_ALIASES["test"] == "test"

    def test_alias_discover_to_discover(self) -> None:
        assert PHASE_ALIASES["discover"] == "discover"

    def test_alias_fix_to_fix(self) -> None:
        assert PHASE_ALIASES["fix"] == "fix"

    def test_alias_plan_to_design(self) -> None:
        assert PHASE_ALIASES["plan"] == "design"

    def test_alias_execute_to_build(self) -> None:
        assert PHASE_ALIASES["execute"] == "build"

    def test_alias_requirements_to_discover(self) -> None:
        assert PHASE_ALIASES["requirements"] == "discover"

    def test_alias_implementation_to_build(self) -> None:
        assert PHASE_ALIASES["implementation"] == "build"

    def test_alias_count(self) -> None:
        """Verify all expected aliases are present."""
        assert set(PHASE_ALIASES.keys()) == {
            "build", "plan", "execute", "test", "fix", "discover",
            "requirements", "implementation", "planning", "research",
        }


class TestResolvePhase:
    """Tests for resolve_phase()."""

    def test_resolves_build(self) -> None:
        assert resolve_phase("build") == "build"

    def test_resolves_test(self) -> None:
        assert resolve_phase("test") == "test"

    def test_resolves_requirements(self) -> None:
        assert resolve_phase("requirements") == "discover"

    def test_resolves_unknown_returns_original(self) -> None:
        assert resolve_phase("unknown-phase") == "unknown-phase"

    def test_resolves_canonical_returns_self(self) -> None:
        assert resolve_phase("design") == "design"
        assert resolve_phase("build") == "build"


class TestGetPhaseDefinition:
    """Tests for get_phase_definition()."""

    def test_get_build(self) -> None:
        ph = get_phase_definition("build")
        assert ph is not None
        assert ph["name"] == "build"

    def test_get_test(self) -> None:
        ph = get_phase_definition("test")
        assert ph is not None
        assert ph["name"] == "test"

    def test_get_design_direct(self) -> None:
        ph = get_phase_definition("design")
        assert ph is not None
        assert ph["name"] == "design"

    def test_get_discover_direct(self) -> None:
        ph = get_phase_definition("discover")
        assert ph is not None
        assert ph["name"] == "discover"

    def test_get_discover_via_requirements_alias(self) -> None:
        ph = get_phase_definition("requirements")
        assert ph is not None
        assert ph["name"] == "discover"

    def test_get_build_via_implementation_alias(self) -> None:
        ph = get_phase_definition("implementation")
        assert ph is not None
        assert ph["name"] == "build"

    def test_get_unknown_returns_none(self) -> None:
        assert get_phase_definition("nonexistent") is None


class TestGetPhases:
    """Tests for get_phases() from phase_source."""

    def test_get_phases_returns_list(self) -> None:
        phases = get_phases()
        assert isinstance(phases, list)
        assert len(phases) > 0

    def test_get_phases_has_required_names(self) -> None:
        phases = get_phases()
        names = {p["name"] for p in phases}
        required = {
            "discover", "design", "build", "review", "test",
            "validate", "deliver", "assess", "refactor", "fix",
            "triage", "audit", "report",
        }
        assert required.issubset(names), f"Missing phases: {required - names}"

    def test_each_phase_has_required_keys(self) -> None:
        required = {"name", "title", "agent", "teams", "prompt", "artifact"}
        for p in get_phases():
            missing = required - set(p.keys())
            assert not missing, f"Phase {p['name']} missing keys: {missing}"

    def test_design_phase_structure(self) -> None:
        ph = find_phase("design")
        assert ph is not None
        assert ph["title"] == "Architecture & Design"
        assert ph["agent"] == "design-coordinator"

    def test_discover_phase_structure(self) -> None:
        ph = find_phase("discover")
        assert ph is not None
        assert ph["title"] == "Requirements Gathering"
        assert ph["agent"] == "discovery-agent"


class TestNavigationRails:
    """Tests for is_transition_allowed() navigation rail validation."""

    def test_forward_transition_allowed(self) -> None:
        """Moving forward to next phase is allowed."""
        allowed, reason = is_transition_allowed("discover", "design")
        assert allowed, f"Should allow discover → design: {reason}"

    def test_backward_transition_allowed(self) -> None:
        """Moving backward to previous phase is allowed (feedback flow)."""
        allowed, reason = is_transition_allowed("build", "design")
        assert allowed, f"Should allow build → design: {reason}"

    def test_same_phase_allowed(self) -> None:
        """Staying in the same phase is allowed."""
        allowed, reason = is_transition_allowed("design", "design")
        assert allowed, f"Should allow design → design: {reason}"

    def test_multi_step_backward_allowed(self) -> None:
        """Jumping multiple phases backward is allowed."""
        allowed, reason = is_transition_allowed("test", "discover")
        assert allowed, f"Should allow test → discover: {reason}"

    def test_multi_step_forward_allowed(self) -> None:
        """Jumping multiple phases forward is allowed."""
        allowed, reason = is_transition_allowed("build", "validate")
        assert allowed, f"Should allow build → validate: {reason}"

    def test_unknown_source_returns_false(self) -> None:
        """Unknown source phase returns False."""
        allowed, reason = is_transition_allowed("nonexistent", "design")
        assert not allowed
        assert "Unknown source" in reason

    def test_unknown_target_returns_false(self) -> None:
        """Unknown target phase returns False."""
        allowed, reason = is_transition_allowed("design", "nonexistent")
        assert not allowed
        assert "Unknown target" in reason


class TestPhasesByWorkflow:
    """Tests for PHASES_BY_WORKFLOW and get_phases_for_workflow()."""

    def test_default_empty(self) -> None:
        """PHASES_BY_WORKFLOW starts as empty dict."""
        assert PHASES_BY_WORKFLOW == {}

    def test_get_workflow_falls_back_to_phases(self) -> None:
        """get_phases_for_workflow falls back to get_phases()."""
        result = get_phases_for_workflow("brownfield")
        expected = get_phases()
        assert result == expected

    def test_get_workflow_for_standard(self) -> None:
        """get_phases_for_workflow for standard also falls back."""
        result = get_phases_for_workflow("standard")
        expected = get_phases()
        assert result == expected
