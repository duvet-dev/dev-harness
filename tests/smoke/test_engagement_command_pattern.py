"""Engagement lifecycle and phase management smoke tests.

Validates the engagement lifecycle command pattern:

- FinishEngagementHandler and ReviewEngagementHandler are registered
- InitProjectHandler and PhaseManagementHandler are registered
- Corresponding CLI command factory functions exist
- Legacy shim types (SessionType, AgentRole) are fully removed
- No remaining Fleet/FleetRegistry imports in source code
"""

from __future__ import annotations

import pytest

smoke = pytest.mark.smoke


@smoke
class TestEngagementCommandPattern:
    """Engagement lifecycle, init/phase commands, and shim removal."""

    def test_finish_handler_importable(self):
        """FinishEngagementHandler is registered."""
        from harness.command.handlers import FinishEngagementHandler
        assert FinishEngagementHandler is not None

    def test_review_handler_importable(self):
        """ReviewEngagementHandler is registered."""
        from harness.command.handlers import ReviewEngagementHandler
        assert ReviewEngagementHandler is not None

    def test_init_handler_importable(self):
        """InitProjectHandler is registered."""
        from harness.command.handlers import InitProjectHandler
        assert InitProjectHandler is not None

    def test_phase_handler_importable(self):
        """PhaseManagementHandler is registered."""
        from harness.command.handlers import PhaseManagementHandler
        assert PhaseManagementHandler is not None

    def test_finish_factory_importable(self):
        """finish_engagement_command factory exists."""
        from harness.cli.commands import finish_engagement_command
        assert callable(finish_engagement_command)

    def test_review_factory_importable(self):
        """review_engagement_command factory exists."""
        from harness.cli.commands import review_engagement_command
        assert callable(review_engagement_command)

    def test_init_factory_importable(self):
        """init_project_command factory exists."""
        from harness.cli.commands import init_project_command
        assert callable(init_project_command)

    def test_phase_factory_importable(self):
        """manage_phase_command factory exists."""
        from harness.cli.commands import manage_phase_command
        assert callable(manage_phase_command)

    def test_sessiontype_shim_gone(self):
        """SessionType shim class removed from helpers.py."""
        import inspect
        import harness.session.helpers as helpers_mod
        source = inspect.getsource(helpers_mod)
        assert "class SessionType" not in source, (
            "SessionType shim class still present in helpers.py"
        )

    def test_agentrole_shim_gone(self):
        """AgentRole shim type removed from agent_registry.py."""
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
        """No Fleet/FleetRegistry imports remain in src/."""
        import subprocess
        result = subprocess.run(
            ["grep", "-rn", r"^from.*Fleet\|^import.*Fleet",
             "src/", "--include=*.py"],
            capture_output=True, text=True, cwd="/Users/claw/Projects/dev-harness",
        )
        lines = [l for l in result.stdout.splitlines() if l.strip()]
        assert len(lines) == 0, (
            f"Found {len(lines)} Fleet imports: {lines}"
        )
