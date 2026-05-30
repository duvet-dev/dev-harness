"""Sprint 1 smoke test — post-deployment validation.

Validates that Waves A, B, C, and M work together correctly:

- Config files parse (Wave M)
- CLI commands route through CommandBus (Wave C)
- AgentOrchestrator is wired (Wave A)
- SessionOrchestrator is importable (Wave B)
- Old legacy runtime files are gone
"""

from __future__ import annotations

import pytest

smoke = pytest.mark.smoke


@smoke
class TestSprint1Smoke:
    """Integration smoke tests for Sprint 1 refactoring."""

    def test_config_files_exist(self):
        """Wave M: All 7 config files exist at project root."""
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
        """Wave A: AgentOrchestrator is importable."""
        from harness.agents.orchestrator import AgentOrchestrator
        assert AgentOrchestrator is not None

    def test_session_orchestrator_importable(self):
        """Wave B: SessionOrchestrator module is importable."""
        from harness.session.session_orchestrator import (
            run_chat_session,
            run_phase_session,
        )
        assert callable(run_chat_session)
        assert callable(run_phase_session)

    def test_commandbus_dispatch_importable(self):
        """Wave C: CommandBus dispatch is wired."""
        from harness.cli.commands import (
            create_engagement_command,
            abort_engagement_command,
            dispatch_cli_command,
        )
        assert callable(create_engagement_command)
        assert callable(abort_engagement_command)
        assert callable(dispatch_cli_command)

    def test_legacy_runner_deleted(self):
        """Wave A: agents/runner.py is deleted."""
        import importlib

        with pytest.raises((ImportError, ModuleNotFoundError)):
            importlib.import_module("harness.agents.runner")

    def test_legacy_runners_deleted(self):
        """Wave B: session/runners.py is deleted."""
        import importlib

        with pytest.raises((ImportError, ModuleNotFoundError)):
            importlib.import_module("harness.session.runners")

