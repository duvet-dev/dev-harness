"""Tests for harness.session.helpers — PHASES, PHASE_ALIASES, phase resolution.

Tests cover:
- PHASES list contains all required phases
- analyse phase definition is present
- PHASE_ALIASES dict is correctly defined
- resolve_phase resolves aliased names correctly
- get_phase_definition resolves aliases and returns definitions
- get_phase_definition returns None for unknown phases
- PHASES_BY_WORKFLOW is initialized as empty dict
- get_phases_for_workflow falls back to PHASES for unknown workflows
"""

from __future__ import annotations

from harness.session.helpers import (
    PHASES,
    PHASE_ALIASES,
    PHASES_BY_WORKFLOW,
    get_phases_for_workflow,
    resolve_phase,
    get_phase_definition,
)


class TestPhases:
    """Tests for the PHASES list."""

    def test_phases_contains_required_phases(self) -> None:
        """PHASES list contains all required phase names."""
        names = {p["name"] for p in PHASES}
        required = {
            "requirements", "design", "planning", "implementation",
            "testing", "review", "analyse",
        }
        assert required.issubset(names), f"Missing phases: {required - names}"

    def test_analyse_phase_definition(self) -> None:
        """Analyse phase has correct structure."""
        analyse = next((p for p in PHASES if p["name"] == "analyse"), None)
        assert analyse is not None
        assert analyse["title"] == "Analyse & Understand"
        assert analyse["agent"] == "purpose-decoder"
        assert analyse["teams"] == ["analysis"]
        assert analyse["artifact"] == "analysis.md"
        assert "analysis.md" in str(analyse["artifact"])

    def test_planning_phase_exists(self) -> None:
        """Planning phase exists in PHASES list."""
        planning = next((p for p in PHASES if p["name"] == "planning"), None)
        assert planning is not None
        assert planning["agent"] == "planning-agent"


class TestPhaseAliases:
    """Tests for PHASE_ALIASES."""

    def test_alias_build_to_implementation(self) -> None:
        assert PHASE_ALIASES["build"] == "implementation"

    def test_alias_test_to_testing(self) -> None:
        assert PHASE_ALIASES["test"] == "testing"

    def test_alias_discover_to_requirements(self) -> None:
        assert PHASE_ALIASES["discover"] == "requirements"

    def test_alias_fix_to_implementation(self) -> None:
        assert PHASE_ALIASES["fix"] == "implementation"

    def test_alias_plan_to_planning(self) -> None:
        assert PHASE_ALIASES["plan"] == "planning"

    def test_alias_execute_to_implementation(self) -> None:
        assert PHASE_ALIASES["execute"] == "implementation"

    def test_alias_count(self) -> None:
        """Verify all expected aliases are present."""
        assert set(PHASE_ALIASES.keys()) == {
            "build", "plan", "execute", "test", "fix", "discover",
        }
        assert set(PHASE_ALIASES.values()) == {
            "implementation", "planning", "testing", "requirements",
        }


class TestResolvePhase:
    """Tests for resolve_phase()."""

    def test_resolves_build(self) -> None:
        assert resolve_phase("build") == "implementation"

    def test_resolves_test(self) -> None:
        assert resolve_phase("test") == "testing"

    def test_resolves_unknown_returns_original(self) -> None:
        assert resolve_phase("unknown-phase") == "unknown-phase"

    def test_resolves_canonical_returns_self(self) -> None:
        assert resolve_phase("planning") == "planning"
        assert resolve_phase("requirements") == "requirements"


class TestGetPhaseDefinition:
    """Tests for get_phase_definition()."""

    def test_get_implementation_via_build_alias(self) -> None:
        ph = get_phase_definition("build")
        assert ph is not None
        assert ph["name"] == "implementation"

    def test_get_testing_via_test_alias(self) -> None:
        ph = get_phase_definition("test")
        assert ph is not None
        assert ph["name"] == "testing"

    def test_get_planning_direct(self) -> None:
        ph = get_phase_definition("planning")
        assert ph is not None
        assert ph["name"] == "planning"

    def test_get_analyse_direct(self) -> None:
        ph = get_phase_definition("analyse")
        assert ph is not None
        assert ph["name"] == "analyse"

    def test_get_unknown_returns_none(self) -> None:
        assert get_phase_definition("nonexistent") is None


class TestPhasesByWorkflow:
    """Tests for PHASES_BY_WORKFLOW and get_phases_for_workflow()."""

    def test_default_empty(self) -> None:
        """PHASES_BY_WORKFLOW starts as empty dict."""
        assert PHASES_BY_WORKFLOW == {}

    def test_get_workflow_falls_back_to_phases(self) -> None:
        """get_phases_for_workflow falls back to full PHASES."""
        result = get_phases_for_workflow("brownfield")
        assert result == PHASES

    def test_get_workflow_for_standard(self) -> None:
        """get_phases_for_workflow for standard also falls back."""
        result = get_phases_for_workflow("standard")
        assert result == PHASES
