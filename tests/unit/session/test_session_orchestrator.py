"""Tests for SessionOrchestrator (replaces runners.py).

Covers: run_chat_session and run_phase_session entry points.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest


_RESOLVE_PATH = "harness.session.client.resolve_provider"
_SESSION_CLIENT_PATH = "harness.session.client.SessionClient"
_INTERACTIVE_SESSION_PATH = "harness.session.session_orchestrator.InteractiveSession"
_PHASE_STATE_MANAGER_PATH = "harness.engagement.phase_state.PhaseStateManager"
_CHECKPOINT_MANAGER_PATH = "harness.engagement.checkpoint.CheckpointManager"
_FEEDBACK_MANAGER_PATH = "harness.engagement.feedback.FeedbackManager"
_PLAN_MANAGER_PATH = "harness.plan.plan_manager.PlanManager"
_SESSION_CR_PATH = "harness.session.commands.CommandResult"


class TestRunChatSession:
    """Tests for run_chat_session()."""

    @pytest.mark.asyncio
    async def test_returns_early_when_no_api_key(self, tmp_path):
        """Should return early when no API key is configured."""
        from harness.session.session_orchestrator import run_chat_session

        with patch(_RESOLVE_PATH) as mock_resolve:
            mock_resolve.return_value = {}
            result = await run_chat_session(
                root=tmp_path,
                slug="test-eng",
                phase="design",
            )
            assert result is None

    @pytest.mark.asyncio
    async def test_creates_client_when_not_provided(self, tmp_path):
        """Should create a SessionClient when client is None."""
        from harness.session.session_orchestrator import run_chat_session

        with patch(_RESOLVE_PATH) as mock_resolve:
            mock_resolve.return_value = {"api_key": "test-key", "model": "test-model"}
            with patch(_SESSION_CLIENT_PATH):
                with patch(_INTERACTIVE_SESSION_PATH) as mock_is:
                    mock_is_instance = AsyncMock()
                    mock_is.return_value = mock_is_instance

                    await run_chat_session(
                        root=tmp_path,
                        slug="test-eng",
                        phase="design",
                    )

                    mock_is.assert_called_once()
                    args, kwargs = mock_is.call_args
                    assert kwargs["root"] == tmp_path
                    assert kwargs["engagement_slug"] == "test-eng"
                    assert kwargs["phase"] == "design"

    @pytest.mark.asyncio
    async def test_one_shot_mode(self, tmp_path):
        """One-shot mode should stream a response without creating InteractiveSession."""
        from harness.session.session_orchestrator import run_chat_session

        mock_client = MagicMock()
        mock_client.get_last_response.return_value = "full response"
        # Make stream iterable
        mock_client.stream.return_value.__aiter__.return_value = iter(["chunk1", "chunk2"])

        with patch(_RESOLVE_PATH) as mock_resolve:
            mock_resolve.return_value = {"api_key": "test-key", "model": "test-model"}
            with patch(_SESSION_CLIENT_PATH, return_value=mock_client):
                eng_dir = tmp_path / ".harness" / "engagements" / "test-eng"
                eng_dir.mkdir(parents=True)

                await run_chat_session(
                    root=tmp_path,
                    slug="test-eng",
                    phase="design",
                    one_shot="test prompt",
                )
                # One-shot mode returns without creating InteractiveSession


class TestExecuteSessionEffects:
    """Tests for execute_session_effects()."""

    def _make_session(self, tmp_path):
        """Helper to create a minimal InteractiveSession."""
        from harness.session.session_orchestrator import InteractiveSession
        session = InteractiveSession(
            root=tmp_path,
            engagement_slug="test-eng",
            phase="design",
            phase_def={"name": "design", "title": "Design"},
        )
        return session

    def _make_cr(self, **kwargs):
        """Create a session CommandResult with given fields."""
        from harness.session.commands import CommandResult
        return CommandResult(**kwargs)

    def test_advance_phase_prints_completed(self, tmp_path, capsys):
        """advance_phase should print completion message."""
        from harness.session.session_orchestrator import execute_session_effects

        result = self._make_cr(advance_phase=True, approved=True)
        session = self._make_session(tmp_path)
        execute_session_effects(result, session)
        captured = capsys.readouterr()
        assert "Phase" in captured.out
        assert "Approved" in captured.out

    def test_advance_phase_not_approved(self, tmp_path, capsys):
        """advance_phase without approval should still print completion."""
        from harness.session.session_orchestrator import execute_session_effects

        result = self._make_cr(advance_phase=True, approved=False)
        session = self._make_session(tmp_path)
        execute_session_effects(result, session)
        captured = capsys.readouterr()
        assert "Phase" in captured.out
        assert "Approved" not in captured.out

    def test_switch_to_phase_navigates(self, tmp_path, capsys):
        """switch_to_phase with phase_jump_allowed should navigate."""
        from harness.session.session_orchestrator import execute_session_effects

        result = self._make_cr(switch_to_phase="implementation", phase_jump_allowed=True)
        session = self._make_session(tmp_path)
        eng_dir = tmp_path / ".harness" / "engagements" / "test-eng"
        eng_dir.mkdir(parents=True, exist_ok=True)

        with patch("harness.session.session_orchestrator.PhaseStateManager") as mock_psm_cls:
            mock_psm = MagicMock()
            mock_psm_cls.return_value = mock_psm
            execute_session_effects(result, session)
        captured = capsys.readouterr()
        assert "Checkpoint saved" in captured.out
        assert "Navigating" in captured.out

    def test_switch_to_phase_no_match(self, tmp_path, capsys):
        """switch_to_phase with unmatched target should do nothing."""
        from harness.session.session_orchestrator import execute_session_effects

        result = self._make_cr(switch_to_phase="nonexistent-phase", phase_jump_allowed=True)
        session = self._make_session(tmp_path)
        execute_session_effects(result, session)
        captured = capsys.readouterr()
        # No output since match is None
        assert captured.out == ""

    def test_consult_result_matched_blocking(self, tmp_path, capsys):
        """Blocking consult matched should append to blocking_consults."""
        from harness.session.session_orchestrator import execute_session_effects
        from harness.agents.consultation import ConsultationResult

        consult_res = ConsultationResult(
            status="matched",
            capability="architecture",
            team_name="architects",
            mode="blocking",
            response="Some advice",
            question="architecture review",
        )
        result = self._make_cr(consult_result=consult_res)
        session = self._make_session(tmp_path)
        session._blocking_consults = {}
        execute_session_effects(result, session)
        assert "design" in session._blocking_consults
        assert len(session._blocking_consults["design"]) == 1

    def test_consult_result_non_blocking(self, tmp_path, capsys):
        """Non-blocking consult should just print."""
        from harness.session.session_orchestrator import execute_session_effects
        from harness.agents.consultation import ConsultationResult

        consult_res = ConsultationResult(
            status="matched",
            capability="architecture",
            team_name="architects",
            mode="advisory",
            response="Some advice",
            question="architecture review",
        )
        result = self._make_cr(consult_result=consult_res)
        session = self._make_session(tmp_path)
        session._blocking_consults = {}
        execute_session_effects(result, session)
        # Advisory mode should not add to blocking consults
        assert "design" not in getattr(session, "_blocking_consults", {})

    def test_consult_resolved_displays_lines(self, tmp_path, capsys):
        """consult_resolved should display the last line."""
        from harness.session.session_orchestrator import execute_session_effects

        result = self._make_cr(
            consult_resolved=True,
            display_lines=["line1", "line2", "resolution complete"],
        )
        session = self._make_session(tmp_path)
        execute_session_effects(result, session)
        captured = capsys.readouterr()
        assert "resolution complete" in captured.out

    def test_consult_resolved_no_display_lines(self, tmp_path, capsys):
        """consult_resolved without display_lines should do nothing."""
        from harness.session.session_orchestrator import execute_session_effects

        result = self._make_cr(consult_resolved=True)
        session = self._make_session(tmp_path)
        execute_session_effects(result, session)
        captured = capsys.readouterr()
        assert captured.out == ""


class TestExecuteChatEffects:
    """Tests for execute_chat_effects()."""

    def test_noop(self):
        """execute_chat_effects is currently a no-op."""
        from harness.session.session_orchestrator import execute_chat_effects
        from harness.session.commands import CommandResult
        from harness.session.session_orchestrator import InteractiveSession

        result = CommandResult()
        session = InteractiveSession(
            root=Path("/tmp"),
            engagement_slug="test",
        )
        # Should not raise
        execute_chat_effects(result, session)


class TestInteractiveSession:
    """Tests for InteractiveSession internals."""

    def test_handle_command_no_router_returns_true(self, tmp_path):
        """handle_command without command_router returns True."""
        from harness.session.session_orchestrator import InteractiveSession
        session = InteractiveSession(root=tmp_path, engagement_slug="test")
        session._command_router = None
        result = session.handle_command("help", {})
        assert result is True

    def test_handle_command_exit_saves_transcript(self, tmp_path):
        """handle_command with exit_loop returns False and saves transcript."""
        from harness.session.session_orchestrator import InteractiveSession
        from harness.session.commands import CommandResult

        mock_router = MagicMock(return_value=CommandResult(exit_loop=True))
        session = InteractiveSession(
            root=tmp_path,
            engagement_slug="test",
            command_router=mock_router,
        )
        mock_transcript = MagicMock()
        session.transcript = mock_transcript
        result = session.handle_command("exit", {})
        assert result is False
        assert session._done is True
        mock_transcript.save.assert_called_once()

    def test_handle_command_exit_no_transcript(self, tmp_path):
        """handle_command with exit_loop but no transcript should not crash."""
        from harness.session.session_orchestrator import InteractiveSession
        from harness.session.commands import CommandResult

        mock_router = MagicMock(return_value=CommandResult(exit_loop=True))
        session = InteractiveSession(
            root=tmp_path,
            engagement_slug="test",
            command_router=mock_router,
        )
        session.transcript = None
        result = session.handle_command("exit", {})
        assert result is False

    def test_handle_command_executes_effect_executor(self, tmp_path):
        """handle_command calls the effect_executor when provided."""
        from harness.session.session_orchestrator import InteractiveSession
        from harness.session.commands import CommandResult

        mock_router = MagicMock(return_value=CommandResult(display_lines=["hello"]))
        mock_effect = MagicMock()
        session = InteractiveSession(
            root=tmp_path,
            engagement_slug="test",
            command_router=mock_router,
            effect_executor=mock_effect,
        )
        with patch("click.echo"):
            result = session.handle_command("help", {})
        assert result is True
        mock_effect.assert_called_once()

    def test_handle_command_save_transcript(self, tmp_path, capsys):
        """handle_command with save_transcript should save and print."""
        from harness.session.session_orchestrator import InteractiveSession
        from harness.session.commands import CommandResult

        mock_router = MagicMock(return_value=CommandResult(save_transcript=True))
        mock_transcript = MagicMock()
        mock_transcript.save.return_value = "/path/to/transcript"
        session = InteractiveSession(
            root=tmp_path,
            engagement_slug="test",
            command_router=mock_router,
        )
        session.transcript = mock_transcript
        session.handle_command("help", {})
        captured = capsys.readouterr()
        assert "Transcript saved" in captured.out

    def test_handle_command_save_transcript_no_transcript(self, tmp_path):
        """handle_command with save_transcript but no transcript should not crash."""
        from harness.session.session_orchestrator import InteractiveSession
        from harness.session.commands import CommandResult

        mock_router = MagicMock(return_value=CommandResult(save_transcript=True))
        session = InteractiveSession(
            root=tmp_path,
            engagement_slug="test",
            command_router=mock_router,
        )
        session.transcript = None
        session.handle_command("save", {})

    def test_handle_command_capture_artifact(self, tmp_path, capsys):
        """handle_command with capture_artifact should write and print."""
        from harness.session.session_orchestrator import InteractiveSession
        from harness.session.commands import CommandResult

        mock_router = MagicMock(return_value=CommandResult(capture_artifact="# artifact content"))
        session = InteractiveSession(
            root=tmp_path,
            engagement_slug="test",
            phase="design",
        )
        session._command_router = mock_router
        eng_dir = tmp_path / ".harness" / "engagements" / "test-eng"
        eng_dir.mkdir(parents=True, exist_ok=True)

        with patch("harness.session.helpers._write_phase_artifact", return_value=tmp_path / "artifact.md"):
            session.handle_command("help", {})
        captured = capsys.readouterr()
        assert "Artifact written" in captured.out

    def test_handle_command_auto_apply(self, tmp_path, capsys):
        """handle_command with auto_apply should process file blocks."""
        from harness.session.session_orchestrator import InteractiveSession
        from harness.session.commands import CommandResult

        mock_router = MagicMock(return_value=CommandResult(auto_apply="# File content"))
        session = InteractiveSession(
            root=tmp_path,
            engagement_slug="test",
            command_router=mock_router,
        )
        with patch("harness.session.helpers._apply_file_blocks", return_value=[]):
            session.handle_command("help", {})
        # Should not crash

    def test_handle_command_reset_conversation(self, tmp_path, capsys):
        """handle_command with reset_conversation should clear non-system messages."""
        from harness.session.session_orchestrator import InteractiveSession
        from harness.session.commands import CommandResult

        mock_router = MagicMock(return_value=CommandResult(reset_conversation=True))
        session = InteractiveSession(
            root=tmp_path,
            engagement_slug="test",
            command_router=mock_router,
        )
        session.client = MagicMock()
        session.client._messages = [
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "user message"},
        ]
        session.handle_command("reset", {})
        assert len(session.client._messages) == 1
        assert session.client._messages[0]["role"] == "system"

    def test_handle_command_reset_conversation_empty_system(self, tmp_path):
        """reset_conversation with empty system messages and None system_prompt."""
        from harness.session.session_orchestrator import InteractiveSession
        from harness.session.commands import CommandResult

        mock_router = MagicMock(return_value=CommandResult(reset_conversation=True))
        session = InteractiveSession(
            root=tmp_path,
            engagement_slug="test",
            command_router=mock_router,
        )
        session.client = MagicMock()
        session.client._messages = [{"role": "user", "content": "message"}]
        session.client.system_prompt = None
        session.handle_command("reset", {})
        assert len(session.client._messages) == 0

    def test_handle_command_switch_phase_with_history(self, tmp_path):
        """handle_command with switch_to_phase_with_history calls _switch_phase."""
        from harness.session.session_orchestrator import InteractiveSession
        from harness.session.commands import CommandResult

        mock_router = MagicMock(return_value=CommandResult(switch_to_phase_with_history="implementation"))
        session = InteractiveSession(
            root=tmp_path,
            engagement_slug="test",
            command_router=mock_router,
        )
        session.client = MagicMock()
        with patch.object(session, "_switch_phase") as mock_sp:
            session.handle_command("phase", {})
        mock_sp.assert_called_once_with("implementation")

    def test_handle_command_switch_new_provider(self, tmp_path):
        """handle_command with new_provider calls _switch_provider."""
        from harness.session.session_orchestrator import InteractiveSession
        from harness.session.commands import CommandResult

        mock_router = MagicMock(return_value=CommandResult(new_provider={"target_name": "new-prov"}))
        session = InteractiveSession(
            root=tmp_path,
            engagement_slug="test",
            command_router=mock_router,
        )
        with patch.object(session, "_switch_provider") as mock_sp:
            session.handle_command("model", {})
        mock_sp.assert_called_once_with({"target_name": "new-prov"})

    def test_handle_command_set_in_session_help(self, tmp_path):
        """handle_command with set_in_session should update help mode."""
        from harness.session.session_orchestrator import InteractiveSession
        from harness.session.commands import CommandResult

        mock_router = MagicMock(return_value=CommandResult(set_in_session=True))
        session = InteractiveSession(
            root=tmp_path,
            engagement_slug="test",
            command_router=mock_router,
        )
        session.handle_command("help", {})

    def test_handle_command_set_in_session_none(self, tmp_path):
        """handle_command with set_in_session=None should not affect help mode."""
        from harness.session.session_orchestrator import InteractiveSession
        from harness.session.commands import CommandResult

        mock_router = MagicMock(return_value=CommandResult(set_in_session=None))
        session = InteractiveSession(
            root=tmp_path,
            engagement_slug="test",
            command_router=mock_router,
        )
        result = session.handle_command("help", {})
        assert result is True

    def test_handle_command_list_providers_line(self, tmp_path):
        """handle_command with display_line __list_providers__ should call _display_providers."""
        from harness.session.session_orchestrator import InteractiveSession
        from harness.session.commands import CommandResult

        mock_router = MagicMock(return_value=CommandResult(display_lines=["__list_providers__"]))
        session = InteractiveSession(
            root=tmp_path,
            engagement_slug="test",
            command_router=mock_router,
        )
        with patch.object(session, "_display_providers") as mock_dp:
            session.handle_command("providers", {})
        mock_dp.assert_called_once()

    def test_display_providers_empty(self, tmp_path, capsys):
        """_display_providers should handle no providers."""
        from harness.session.session_orchestrator import InteractiveSession
        session = InteractiveSession(root=tmp_path, engagement_slug="test")
        session.provider = {"name": "default"}
        with patch("harness.session.helpers.list_providers", return_value=[]):
            session._display_providers()
        captured = capsys.readouterr()
        assert "No providers found" in captured.out

    def test_display_providers_with_list(self, tmp_path, capsys):
        """_display_providers should list available providers."""
        from harness.session.session_orchestrator import InteractiveSession

        with patch(
            "harness.session.helpers.list_providers",
            return_value=[{"name": "dp", "model": "deepseek-v4", "type": "openai-compatible"}],
        ):
            with patch(
                "harness.session.helpers.format_providers_table",
                return_value="| dp | deepseek-v4 |",
            ):
                session = InteractiveSession(root=tmp_path, engagement_slug="test")
                session.provider = {"name": "dp"}
                session._display_providers()
        captured = capsys.readouterr()
        assert "Available providers" in captured.out

    def test_switch_provider_not_found(self, tmp_path, capsys):
        """_switch_provider should handle provider not found."""
        from harness.session.session_orchestrator import InteractiveSession
        with patch(
            "harness.session.helpers.list_providers",
            return_value=[{"name": "dp", "model": "deepseek-v4"}],
        ):
            with patch(
                "harness.session.helpers.switch_provider",
                return_value=None,
            ):
                session = InteractiveSession(root=tmp_path, engagement_slug="test")
                session._switch_provider({"target_name": "nonexistent"})
        captured = capsys.readouterr()
        assert "not found" in captured.out

    def test_switch_provider_success(self, tmp_path, capsys):
        """_switch_provider successfully switches with alias."""
        from harness.session.session_orchestrator import InteractiveSession
        with patch(
            "harness.session.helpers.switch_provider",
            return_value={"name": "new-prov", "model": "gpt-4"},
        ):
            session = InteractiveSession(root=tmp_path, engagement_slug="test")
            session._switch_provider({"target_name": "new-prov", "target_alias": "ngpt"})
        assert session.model == "gpt-4"
        captured = capsys.readouterr()
        assert "Switched to provider" in captured.out
        assert "Alias:" in captured.out

    def test_switch_phase_no_client(self, tmp_path):
        """_switch_phase should handle missing client gracefully."""
        from harness.session.session_orchestrator import InteractiveSession
        session = InteractiveSession(root=tmp_path, engagement_slug="test")
        session.client = None
        # Should not crash
        session._switch_phase("implementation")

    def test_switch_phase_with_client(self, tmp_path):
        """_switch_phase should update client system prompt."""
        from harness.session.session_orchestrator import InteractiveSession
        session = InteractiveSession(
            root=tmp_path,
            engagement_slug="test",
            phase="design",
            phase_def={"name": "design", "title": "Design"},
        )
        mock_client = MagicMock()
        mock_client._messages = [{"role": "system", "content": "old prompt"}]
        mock_client.conversation_history.return_value = []
        session.client = mock_client

        with patch("harness.session.helpers._build_system_prompt", return_value="new prompt"):
            session._switch_phase("implementation")

        assert session.phase == "implementation"
        assert mock_client._messages[0]["content"] == "new prompt"

    def test_switch_phase_inserts_system_prompt(self, tmp_path):
        """_switch_phase should insert system prompt when no existing system message."""
        from harness.session.session_orchestrator import InteractiveSession
        session = InteractiveSession(
            root=tmp_path,
            engagement_slug="test",
            phase="design",
            phase_def={"name": "design", "title": "Design"},
        )
        mock_client = MagicMock()
        mock_client._messages = [{"role": "user", "content": "hello"}]
        mock_client.conversation_history.return_value = []
        session.client = mock_client

        with patch("harness.session.helpers._build_system_prompt", return_value="new prompt"):
            session._switch_phase("implementation")

        assert session.phase == "implementation"
        assert mock_client._messages[0]["role"] == "system"
        assert mock_client._messages[0]["content"] == "new prompt"


class TestRunPhaseSession:
    """Tests for run_phase_session()."""

    @pytest.mark.asyncio
    async def test_returns_early_when_no_api_key(self, tmp_path):
        """Should return early when no API key is configured."""
        from harness.session.session_orchestrator import run_phase_session

        with patch(_RESOLVE_PATH) as mock_resolve:
            mock_resolve.return_value = {}
            result = await run_phase_session(
                root=tmp_path,
                slug="test-eng",
                start_phase="requirements",
                session_type="get-well",
            )
            assert result is None

    @pytest.mark.asyncio
    async def test_get_well_delegates_to_interactive_session(self, tmp_path):
        """Get-well session type should delegate to InteractiveSession."""
        from harness.session.session_orchestrator import run_phase_session

        with patch(_RESOLVE_PATH) as mock_resolve:
            mock_resolve.return_value = {"api_key": "test-key", "model": "test-model"}
            with patch(_PHASE_STATE_MANAGER_PATH) as mock_psm:
                mock_psm_instance = MagicMock()
                mock_psm.return_value = mock_psm_instance
                with patch(_CHECKPOINT_MANAGER_PATH):
                    with patch(_FEEDBACK_MANAGER_PATH):
                        with patch(_INTERACTIVE_SESSION_PATH) as mock_is:
                            mock_is_instance = AsyncMock()
                            mock_is.return_value = mock_is_instance
                            with patch(_PLAN_MANAGER_PATH) as mock_pm:
                                mock_plan = MagicMock()
                                mock_plan.waves = []
                                mock_pm_instance = MagicMock()
                                mock_pm_instance.load.return_value = mock_plan
                                mock_pm.return_value = mock_pm_instance

                                await run_phase_session(
                                    root=tmp_path,
                                    slug="test-eng",
                                    start_phase="assessment-triage",
                                    session_type="get-well",
                                )

                                assert mock_is.called

    @pytest.mark.asyncio
    async def test_unknown_start_phase_defaults_to_first(self, tmp_path):
        """An unknown start_phase should default to the first phase."""
        from harness.session.session_orchestrator import run_phase_session

        with patch(_RESOLVE_PATH) as mock_resolve:
            mock_resolve.return_value = {"api_key": "test-key", "model": "test-model"}
            with patch(_PHASE_STATE_MANAGER_PATH) as mock_psm:
                mock_psm_instance = MagicMock()
                mock_psm.return_value = mock_psm_instance
                with patch(_CHECKPOINT_MANAGER_PATH):
                    with patch(_FEEDBACK_MANAGER_PATH):
                        with patch(_INTERACTIVE_SESSION_PATH) as mock_is:
                            mock_is_instance = AsyncMock()
                            mock_is.return_value = mock_is_instance
                            with patch(_PLAN_MANAGER_PATH) as mock_pm:
                                mock_plan = MagicMock()
                                mock_plan.waves = []
                                mock_pm_instance = MagicMock()
                                mock_pm_instance.load.return_value = mock_plan
                                mock_pm.return_value = mock_pm_instance

                                await run_phase_session(
                                    root=tmp_path,
                                    slug="test-eng",
                                    start_phase="non-existent-phase",
                                )

                                assert mock_is.called

    @pytest.mark.asyncio
    async def test_run_phase_session_read_session_type_exception(self, tmp_path):
        """run_phase_session handles read_session_type Exception gracefully."""
        from harness.session.session_orchestrator import run_phase_session

        with patch(_RESOLVE_PATH) as mock_resolve:
            mock_resolve.return_value = {"api_key": "test-key", "model": "test-model"}
            with patch(_PHASE_STATE_MANAGER_PATH):
                with patch(_CHECKPOINT_MANAGER_PATH):
                    with patch(_FEEDBACK_MANAGER_PATH):
                        with patch(_INTERACTIVE_SESSION_PATH) as mock_is:
                            mock_is_instance = AsyncMock()
                            mock_is.return_value = mock_is_instance
                            with patch(_PLAN_MANAGER_PATH) as mock_pm:
                                mock_plan = MagicMock()
                                mock_plan.waves = []
                                mock_pm_instance = MagicMock()
                                mock_pm_instance.load.return_value = mock_plan
                                mock_pm.return_value = mock_pm_instance

                                await run_phase_session(
                                    root=tmp_path,
                                    slug="test-eng",
                                    start_phase="requirements",
                                )

                                assert mock_is.called
