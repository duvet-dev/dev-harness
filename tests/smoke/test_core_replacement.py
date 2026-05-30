"""Core infrastructure smoke tests — post-deployment validation.

Validates that the core harness infrastructure is correctly wired:

- Config files exist and are parseable
- AgentOrchestrator is importable (replaced legacy AgentRunner)
- SessionOrchestrator is importable (replaced legacy session_loop)
- CommandBus dispatch works for engagement lifecycle commands
- Legacy runtime files (agents/runner.py, session/runners.py) are fully removed
"""

from __future__ import annotations

import pytest

smoke = pytest.mark.smoke


@smoke
class TestCoreInfrastructure:
    """Core harness wiring and legacy removal verification."""

    def test_config_files_exist(self):
        """All 7 harness config files exist at project root."""
        from pathlib import Path
        root = Path.cwd()
        config_files = [
            "constitution.yaml",
            "teams.yaml",
            "workflows.yaml",
            "phases.yaml",
            "step_templates.yaml",
            "skills.yaml",
            "settings.yaml",
        ]
        for fname in config_files:
            if fname == "constitution.yaml":
                fpath = root / fname
            else:
                fpath = root / ".harness" / fname
            assert fpath.is_file(), f"Missing: {fname} at {fpath}"

    def test_agent_orchestrator_importable(self):
        """AgentOrchestrator replaces legacy AgentRunner."""
        from harness.agents.orchestrator import AgentOrchestrator
        assert AgentOrchestrator is not None

    def test_session_orchestrator_importable(self):
        """SessionOrchestrator replaces legacy session_loop."""
        from harness.session.session_orchestrator import (
            run_chat_session,
            run_phase_session,
        )
        assert callable(run_chat_session)
        assert callable(run_phase_session)

    def test_commandbus_dispatch_importable(self):
        """CLI commands route through CommandBus."""
        from harness.cli.commands import (
            create_engagement_command,
            abort_engagement_command,
            dispatch_cli_command,
        )
        assert callable(create_engagement_command)
        assert callable(abort_engagement_command)
        assert callable(dispatch_cli_command)

    def test_legacy_runner_deleted(self):
        """agents/runner.py (legacy AgentRunner) is fully removed."""
        import importlib

        with pytest.raises((ImportError, ModuleNotFoundError)):
            importlib.import_module("harness.agents.runner")

    def test_legacy_runners_deleted(self):
        """session/runners.py (legacy session_loop) is fully removed."""
        import importlib

        with pytest.raises((ImportError, ModuleNotFoundError)):
            importlib.import_module("harness.session.runners")
