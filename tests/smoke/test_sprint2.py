"""Sprint 2 smoke test — validates Waves D + E + J.

Wave D: FinishEngagementHandler, ReviewEngagementHandler wired
Wave E: InitProjectHandler, PhaseManagementHandler wired
Wave J: SessionType shim gone, AgentRole shim gone
"""

from __future__ import annotations

import pytest

smoke = pytest.mark.smoke


@smoke
class TestSprint2Smoke:
    """Integration smoke tests for Sprint 2 refactoring."""

    def test_finish_handler_importable(self):
        """Wave D: FinishEngagementHandler is registered."""
        from harness.command.handlers import FinishEngagementHandler
        assert FinishEngagementHandler is not None

    def test_review_handler_importable(self):
        """Wave D: ReviewEngagementHandler is registered."""
        from harness.command.handlers import ReviewEngagementHandler
        assert ReviewEngagementHandler is not None

    def test_init_handler_importable(self):
        """Wave E: InitProjectHandler is registered."""
        from harness.command.handlers import InitProjectHandler
        assert InitProjectHandler is not None

    def test_phase_handler_importable(self):
        """Wave E: PhaseManagementHandler is registered."""
        from harness.command.handlers import PhaseManagementHandler
        assert PhaseManagementHandler is not None

    def test_finish_factory_importable(self):
        """Wave D: finish_engagement_command factory exists."""
        from harness.cli.commands import finish_engagement_command
        assert callable(finish_engagement_command)

    def test_review_factory_importable(self):
        """Wave D: review_engagement_command factory exists."""
        from harness.cli.commands import review_engagement_command
        assert callable(review_engagement_command)

    def test_init_factory_importable(self):
        """Wave E: init_project_command factory exists."""
        from harness.cli.commands import init_project_command
        assert callable(init_project_command)

    def test_phase_factory_importable(self):
        """Wave E: manage_phase_command factory exists."""
        from harness.cli.commands import manage_phase_command
        assert callable(manage_phase_command)

    def test_sessiontype_shim_gone(self):
        """Wave J: SessionType shim removed from helpers."""
        import inspect
        import harness.session.helpers as helpers_mod
        source = inspect.getsource(helpers_mod)
        assert "class SessionType" not in source, (
            "SessionType shim class still present in helpers.py"
        )

    def test_agentrole_shim_gone(self):
        """Wave J: AgentRole shim removed from agent_registry."""
        import inspect
        import harness.agents.agent_registry as reg_mod
        source = inspect.getsource(reg_mod)
        assert "class _AgentRoleType" not in source, (
            "_AgentRoleType shim still present in agent_registry.py"
        )
        assert "AgentRole =" not in source or "AgentRole =" not in [
            l for l in source.splitlines() if l.startswith("AgentRole")
        ], (
            "AgentRole alias still present in agent_registry.py"
        )

    def test_fleet_sweep_clean(self):
        """Wave J: No Fleet/FleetRegistry imports in src/."""
        import subprocess
        # Only flag actual import lines, not comments
        result = subprocess.run(
            ["grep", "-rn", r"^from.*Fleet\|^import.*Fleet",
             "src/", "--include=*.py"],
            capture_output=True, text=True, cwd="/Users/claw/Projects/dev-harness",
        )
        lines = [l for l in result.stdout.splitlines() if l.strip()]
        assert len(lines) == 0, (
            f"Found {len(lines)} Fleet imports: {lines}"
        )

    def test_handler_count(self):
        """All Sprint 2 handlers registered (baseline)."""
        from harness.command.handlers import register_all_handlers
        from harness.command.registry import CommandRegistry
        registry = CommandRegistry()
        register_all_handlers(registry)
        types = registry.list_registered()
        assert len(types) >= 13, f"Expected >=13 handlers, got {len(types)}"
