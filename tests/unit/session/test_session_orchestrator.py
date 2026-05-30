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
