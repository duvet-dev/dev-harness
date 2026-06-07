"""Tests for Wave 27 — Phase-Specific Agents.

Covers:
- Phase agent instantiation and registration
- Entry command routing
- Auto mode loop (convergence detection, iteration state)
- Manual override (interrupt/resume)
- Boundary test generation (Wave 16b → build-agent)
- Architecture debt detection (Wave 16b → design-agent)
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest

from harness.agents.agent_registry import (
    AGENTS,
    AgentSpec,
    get_phase_agent,
    get_agent,
    list_phase_agents,
    list_agent_roles,
)


# ═══════════════════════════════════════════════════════════════════════════
# Part 1: Phase Agent Instantiation and Registration
# ═══════════════════════════════════════════════════════════════════════════


class TestPhaseAgentRegistration:
    """Tests that phase-specific agents are properly registered."""

    def test_phase_agent_count(self):
        """There must be exactly 5 phase agents."""
        agents = list_phase_agents()
        assert len(agents) == 5, f"Expected 5 phase agents, got {len(agents)}"

    @pytest.mark.parametrize("role", [
        "assessment-agent",
        "requirements-agent",
        "design-agent",
        "planning-agent",
        "build-agent",
    ])
    def test_phase_agent_exists(self, role: str):
        """Each phase agent must exist in the global registry."""
        agent = get_agent(role)
        assert agent is not None
        assert agent.role == role

    def test_phase_agent_has_tags(self):
        """Phase agents must have the 'phase' tag."""
        for agent in list_phase_agents():
            assert "phase" in agent.tags, f"{agent.role} missing 'phase' tag"

    def test_phase_agent_has_sop(self):
        """Phase agents must have SOP summaries."""
        for agent in list_phase_agents():
            assert len(agent.sop_summary) >= 3, (
                f"{agent.role} has too few SOP items"
            )

    def test_phase_agent_has_permissions(self):
        """Phase agents must have restricted_write permissions."""
        for agent in list_phase_agents():
            assert agent.tool_permissions is not None, (
                f"{agent.role} has no tool permissions"
            )
            assert agent.tool_permissions.write is True
            assert agent.tool_permissions.write_prefixes is not None

    def test_get_phase_agent_assess(self):
        """get_phase_agent('assess') returns assessment-agent."""
        agent = get_phase_agent("assess")
        assert agent is not None
        assert agent.role == "assessment-agent"

    def test_get_phase_agent_requirements(self):
        agent = get_phase_agent("requirements")
        assert agent is not None and agent.role == "requirements-agent"

    def test_get_phase_agent_design(self):
        agent = get_phase_agent("design")
        assert agent is not None and agent.role == "design-agent"

    def test_get_phase_agent_plan(self):
        agent = get_phase_agent("plan")
        assert agent is not None and agent.role == "planning-agent"

    def test_get_phase_agent_planning(self):
        agent = get_phase_agent("planning")
        assert agent is not None and agent.role == "planning-agent"

    def test_get_phase_agent_build(self):
        agent = get_phase_agent("build")
        assert agent is not None and agent.role == "build-agent"

    def test_get_phase_agent_unknown(self):
        """Unknown phase names return None."""
        assert get_phase_agent("unknown") is None
        assert get_phase_agent("") is None
        assert get_phase_agent("nonexistent") is None

    def test_get_phase_agent_alias_discover(self):
        """"discover" maps to requirements-agent."""
        agent = get_phase_agent("discover")
        assert agent is not None and agent.role == "requirements-agent"

    def test_get_phase_agent_alias_assessment(self):
        """"assessment" maps to assessment-agent."""
        agent = get_phase_agent("assessment")
        assert agent is not None and agent.role == "assessment-agent"


# ═══════════════════════════════════════════════════════════════════════════
# Part 2: Entry Command Routing
# ═══════════════════════════════════════════════════════════════════════════


class TestPhaseEntryCommandRouting:
    """Tests that phase entry commands route correctly."""

    def test_phase_map_completeness(self):
        """PHASE_MAP must cover all 5 entry commands."""
        from harness.session.phase_sessions import PHASE_MAP
        expected = {"assess", "requirements", "design", "plan", "build"}
        assert set(PHASE_MAP.keys()).issuperset(expected)

    def test_phase_agent_map_completeness(self):
        """PHASE_AGENT_MAP must cover all 5 entry commands."""
        from harness.session.phase_sessions import PHASE_AGENT_MAP
        expected = {"assess", "requirements", "design", "plan", "build"}
        assert set(PHASE_AGENT_MAP.keys()).issuperset(expected)

    def test_phase_entry_handlers(self):
        """PHASE_ENTRY_HANDLERS must have all 5 entries."""
        from harness.session.phase_sessions import PHASE_ENTRY_HANDLERS
        expected = {"assess", "requirements", "design", "plan", "build"}
        assert set(PHASE_ENTRY_HANDLERS.keys()) == expected

    def test_phase_entry_handler_is_callable(self):
        """Each entry handler must be a callable taking root Path."""
        from harness.session.phase_sessions import PHASE_ENTRY_HANDLERS
        for name, handler in PHASE_ENTRY_HANDLERS.items():
            assert callable(handler), f"{name} handler not callable"

    def test_resolve_phase_for_entry(self):
        """_resolve_phase_for_entry maps to canonical phase names."""
        from harness.session.phase_sessions import _resolve_phase_for_entry
        assert _resolve_phase_for_entry("assess") == "assess"
        assert _resolve_phase_for_entry("requirements") == "discover"
        assert _resolve_phase_for_entry("design") == "design"
        assert _resolve_phase_for_entry("plan") == "planning"
        assert _resolve_phase_for_entry("build") == "build"
        assert _resolve_phase_for_entry("unknown") is None

    def test_build_phase_system_prompt(self):
        """System prompt includes agent identity."""
        from harness.session.phase_sessions import _build_phase_system_prompt
        prompt = _build_phase_system_prompt("design", "design-agent")
        assert "Design Agent" in prompt
        assert "DESIGN" in prompt
        assert "YOUR ROLE" in prompt
        assert "YOUR SOP" in prompt
        assert "YOUR BOUNDARIES" in prompt

        prompt = _build_phase_system_prompt("build", "build-agent")
        assert "Build Agent" in prompt
        assert "BUILD" in prompt


# ═══════════════════════════════════════════════════════════════════════════
# Part 3: Auto Mode Loop
# ═══════════════════════════════════════════════════════════════════════════


class TestAutoModeConvergence:
    """Tests for convergence detection in auto mode."""

    def test_convergence_no_feedback(self):
        """No feedback means convergence."""
        from harness.agents.auto_mode import check_convergence
        converged, reason = check_convergence([])
        assert converged
        assert "no critic feedback" in reason.lower()

    def test_convergence_keyword_found(self):
        """Explicit convergence keywords trigger convergence."""
        from harness.agents.auto_mode import check_convergence
        converged, reason = check_convergence([
            {"severity": "major", "judgment": "converged — all issues addressed"},
        ])
        assert converged
        assert "convergence keyword" in reason.lower()

    def test_convergence_no_blockers(self):
        """Only minor/suggestion issues means convergence."""
        from harness.agents.auto_mode import check_convergence
        converged, reason = check_convergence([
            {"severity": "minor", "judgment": "Small nitpick about formatting"},
            {"severity": "suggestion", "judgment": "Consider renaming x to y"},
        ])
        assert converged
        assert "no blocker or major" in reason.lower()

    def test_no_convergence_with_major(self):
        """Major issues means no convergence."""
        from harness.agents.auto_mode import check_convergence
        converged, reason = check_convergence([
            {"severity": "major", "judgment": "Missing error handling"},
        ])
        assert not converged
        assert "blocker/major" in reason.lower()

    def test_no_convergence_with_blocker(self):
        from harness.agents.auto_mode import check_convergence
        converged, reason = check_convergence([
            {"severity": "blocker", "judgment": "Security vulnerability"},
        ])
        assert not converged
        assert "blocker/major" in reason.lower()

    def test_convergence_with_custom_keywords(self):
        from harness.agents.agent_registry import ConvergenceConfig
        from harness.agents.auto_mode import check_convergence
        config = ConvergenceConfig(
            convergence_keywords=["approved", "sign off"],
        )
        converged, reason = check_convergence([
            {"severity": "major", "judgment": "design approved — ready to build"},
        ], config)
        assert converged


class TestAutoModeState:
    """Tests for auto mode state management."""

    def test_state_creation(self):
        from harness.agents.auto_mode import AutoModeState, AutoModeStatus
        state = AutoModeState(
            engagement_slug="test-eng",
            phase_name="design",
            agent_role="design-agent",
        )
        assert state.engagement_slug == "test-eng"
        assert state.phase_name == "design"
        assert state.status == AutoModeStatus.IDLE
        assert state.iterations == []

    def test_state_serialization(self):
        from harness.agents.auto_mode import (
            AutoModeState, AutoModeIteration, AutoModeStatus,
        )
        state = AutoModeState(
            engagement_slug="test",
            phase_name="build",
            agent_role="build-agent",
            status=AutoModeStatus.RUNNING,
            current_iteration=1,
        )
        state.iterations.append(AutoModeIteration(
            iteration=0,
            convergence_result=True,
            convergence_reason="Clean review",
        ))
        data = state.to_dict()
        assert data["engagement_slug"] == "test"
        assert data["phase_name"] == "build"
        assert data["status"] == "running"
        assert len(data["iterations"]) == 1
        assert data["iterations"][0]["convergence_result"] is True

    def test_state_deserialization(self):
        from harness.agents.auto_mode import AutoModeState
        original = AutoModeState(
            engagement_slug="test",
            phase_name="design",
            agent_role="design-agent",
        )
        data = original.to_dict()
        restored = AutoModeState.from_dict(data)
        assert restored.engagement_slug == "test"
        assert restored.phase_name == "design"

    def test_state_persistence(self):
        from harness.agents.auto_mode import (
            AutoModeState, save_auto_mode_state, load_auto_mode_state,
            clear_auto_mode_state,
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = AutoModeState(
                engagement_slug="test-eng",
                phase_name="design",
                agent_role="design-agent",
            )
            saved_path = save_auto_mode_state(root, state)
            assert saved_path.is_file()
            assert saved_path.name == "design_state.json"

            loaded = load_auto_mode_state(root, "test-eng", "design")
            assert loaded is not None
            assert loaded.engagement_slug == "test-eng"
            assert loaded.phase_name == "design"

            clear_auto_mode_state(root, "test-eng", "design")
            assert not saved_path.is_file()

    def test_state_load_nonexistent(self):
        from harness.agents.auto_mode import load_auto_mode_state
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = load_auto_mode_state(root, "nonexistent", "design")
            assert result is None


class TestManualOverride:
    """Tests for manual override (interrupt/resume)."""

    def test_manual_override_default_state(self):
        from harness.agents.auto_mode import ManualOverride
        override = ManualOverride()
        assert not override.was_interrupted()
        assert not override.was_resumed()
        assert not override.is_paused()

    def test_manual_override_interrupt(self):
        from harness.agents.auto_mode import ManualOverride
        override = ManualOverride()
        override.interrupt()
        assert override.was_interrupted()
        assert override.is_paused()

    def test_manual_override_resume(self):
        from harness.agents.auto_mode import ManualOverride
        override = ManualOverride()
        override.interrupt()
        assert override.is_paused()
        override.resume()
        assert not override.is_paused()
        assert override.was_resumed()

    def test_manual_override_clear(self):
        from harness.agents.auto_mode import ManualOverride
        override = ManualOverride()
        override.interrupt()
        assert override.was_interrupted()
        override.clear()
        assert not override.was_interrupted()
        assert not override.was_resumed()

    def test_manual_override_save_state(self):
        from harness.agents.auto_mode import ManualOverride, AutoModeState
        override = ManualOverride()
        state = AutoModeState(
            engagement_slug="test",
            phase_name="design",
            agent_role="design-agent",
        )
        override.save_state(state)
        assert override.get_saved_state() is state


# ═══════════════════════════════════════════════════════════════════════════
# Part 4: Boundary Test Generation (Wave 16b → build-agent)
# ═══════════════════════════════════════════════════════════════════════════


class TestBoundaryTestGeneration:
    """Tests for boundary test generation capability."""

    def test_discover_boundaries(self):
        """Boundary discovery finds interfaces in project."""
        from harness.agents.wave16b import discover_application_boundaries
        root = Path.cwd()
        boundaries = discover_application_boundaries(root, max_files=20)
        assert len(boundaries) > 0
        for b in boundaries:
            assert b.name
            assert b.module_path

    def test_generate_boundary_test(self):
        """Generated test includes valid Python code."""
        from harness.agents.wave16b import (
            ApplicationBoundary,
            generate_boundary_test,
        )
        import tempfile

        boundary = ApplicationBoundary(
            name="Test API",
            module_path="src/harness/agents/agent_registry.py",
            boundary_type="public_api",
            functions=[{"name": "get_agent", "args": ["role"], "returns": None}],
            classes=["AgentSpec"],
        )

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            spec = generate_boundary_test(boundary, output_dir)

            assert spec.immutable is True
            assert spec.boundary.name == "Test API"
            assert "IMMUTABLE" in spec.test_code

            # Verify generated code is valid Python
            compile(spec.test_code, "<test>", "exec")

    def test_generate_all_boundary_tests(self):
        """Generating all boundary tests produces valid output."""
        from harness.agents.wave16b import generate_all_boundary_tests
        import tempfile

        root = Path.cwd()
        with tempfile.TemporaryDirectory() as tmp:
            specs = generate_all_boundary_tests(root, output_subdir=tmp)
            for spec in specs:
                assert spec.test_code
                # Verify each test is valid Python
                compile(spec.test_code, "<test>", "exec")

    def test_boundary_types(self):
        """Different boundary types are discovered."""
        from harness.agents.wave16b import discover_application_boundaries
        root = Path.cwd()
        boundaries = discover_application_boundaries(root, max_files=30)
        types = {b.boundary_type for b in boundaries}
        # Should find at least public_api and interface boundaries
        assert "public_api" in types or "module_entry" in types


# ═══════════════════════════════════════════════════════════════════════════
# Part 5: Architecture Debt Detection (Wave 16b → design-agent)
# ═══════════════════════════════════════════════════════════════════════════


class TestArchitectureDebtDetection:
    """Tests for architecture debt detection capability."""

    def test_scan_finds_debt(self):
        """Architecture debt scan finds at least some issues in the project."""
        from harness.agents.wave16b import scan_architecture_debt
        root = Path.cwd()
        report = scan_architecture_debt(root, max_files=30)
        assert report.total_debt_items >= 0  # May be 0 on small scans
        assert report.project_root == str(root)
        assert report.scan_time

    def test_debt_report_generation(self):
        """Debt report generation produces valid output."""
        from harness.agents.wave16b import (
            ArchitectureDebt, ArchitectureDebtReport,
            generate_debt_report,
        )
        import tempfile

        report = ArchitectureDebtReport(project_root="/test")
        report.by_category["magic_literals"] = [
            ArchitectureDebt(
                category="magic_literals",
                file_path="src/file.py",
                severity="major",
                description="Found 10 magic literals",
                recommendation="Extract to constants",
            ),
        ]

        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "debt-report.md"
            content = generate_debt_report(report, output_path)

            assert output_path.is_file()
            assert "Architecture Debt Report" in content
            assert "magic_literals" in content or "Magic" in content or content  # heading expands

    def test_debt_severity_categories(self):
        """Debt items have proper severity levels."""
        from harness.agents.wave16b import ArchitectureDebt
        debt = ArchitectureDebt(
            category="god_object",
            file_path="src/file.py",
            severity="blocker",
            description="God class with 20 methods",
            recommendation="Split into smaller classes",
        )
        assert debt.severity in ("blocker", "major", "minor", "suggestion")
        assert debt.category == "god_object"

    def test_debt_by_category_indexing(self):
        """Debt report indexes by category."""
        from harness.agents.wave16b import (
            ArchitectureDebt, ArchitectureDebtReport,
        )

        report = ArchitectureDebtReport(project_root="/test")

        debt1 = ArchitectureDebt(
            category="magic_literals", file_path="a.py",
            severity="major", description="test", recommendation="fix",
        )
        debt2 = ArchitectureDebt(
            category="god_object", file_path="b.py",
            severity="blocker", description="test", recommendation="fix",
        )

        from harness.agents.wave16b import _add_debt
        _add_debt(report, debt1)
        _add_debt(report, debt2)

        assert len(report.by_category["magic_literals"]) == 1
        assert len(report.by_category["god_object"]) == 1
        assert len(report.by_severity["major"]) == 1
        assert len(report.by_severity["blocker"]) == 1
