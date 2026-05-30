"""Tests for FinishEngagementTypedHandler and ReviewEngagementTypedHandler.

Wave D: Engagement lifecycle handlers (typed versions).
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from harness.command.handlers.review_handlers import FinishEngagementTypedHandler, ReviewEngagementTypedHandler
from harness.command.commands.review import FinishEngagementCommand, ReviewEngagementCommand
from harness.command.results.review import FinishEngagementResult, ReviewEngagementResult

_HARNESS_SNAPSHOT = Path("harness-state.yaml")


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """Minimal project with .harness state dir."""
    (tmp_path / ".harness").mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def finish_handler() -> FinishEngagementTypedHandler:
    return FinishEngagementTypedHandler()


@pytest.fixture
def review_handler() -> ReviewEngagementTypedHandler:
    return ReviewEngagementTypedHandler()


@pytest.fixture
def with_snapshot(tmp_project: Path) -> Path:
    """Create snapshot with one active engagement."""
    from harness.state.snapshot import (
        EngagementSnapshot,
        ProjectSnapshot,
        SnapshotWriter,
    )
    eng = EngagementSnapshot(
        id="my-eng", description="Test",
        status="active", gate_mode="auto", phase="design",
    )
    SnapshotWriter.write(
        ProjectSnapshot(project_name="test", version="0.1.0",
                        current_engagement="my-eng", engagements=[eng]),
        tmp_project / _HARNESS_SNAPSHOT,
    )
    return tmp_project


# ═══════════════════════════════════════════════════════════════════════
# FinishEngagementTypedHandler Tests
# ═══════════════════════════════════════════════════════════════════════


class TestFinishEngagementTypedHandler:
    """Tests for FinishEngagementTypedHandler — git stage/commit, snapshot, re-assessment."""

    def test_completes_engagement(self, finish_handler, with_snapshot):
        """Happy path: stages, commits, updates snapshot, saves freshness."""
        from harness.cli.helpers import load_project_snapshot

        snap_path = with_snapshot / _HARNESS_SNAPSHOT
        pre = load_project_snapshot(snap_path)
        assert pre.engagements[0].status == "active"

        with patch("harness.state.freshness.load_freshness",
                   return_value=MagicMock(stale=False)):
            with patch("harness.state.freshness.save_freshness"):
                with patch("harness.cli.helpers.get_head_sha",
                           return_value="abc123def456"):
                    with patch("harness.scm.git.GitRepo") as mr:
                        mr.return_value.branch.return_value = "main"
                        with patch("subprocess.run") as msubp:
                            msubp.return_value = MagicMock(returncode=0)
                            cmd = FinishEngagementCommand(
                                slug="my-eng",
                                root=str(with_snapshot),
                                re_assess=False,
                            )
                            result = finish_handler.handle(cmd)

        assert result.success, f"Expected success, got: {result.error}"
        assert "Engagement finished" in result.message
        assert result.head_sha == "abc123def456"
        assert result.slug == "my-eng"

        post = load_project_snapshot(snap_path)
        assert post.engagements[0].status == "complete"

    def test_stale_state_prevents_finish(self, finish_handler, with_snapshot):
        """Stale freshness record blocks finish."""
        with patch("harness.state.freshness.load_freshness",
                   return_value=MagicMock(stale=True)):
            cmd = FinishEngagementCommand(
                slug="my-eng",
                root=str(with_snapshot),
                re_assess=False,
            )
            result = finish_handler.handle(cmd)

        assert result.success is False
        assert "stale" in result.error.lower()

    def test_no_freshness_record_allows_finish(self, finish_handler,
                                                with_snapshot):
        """No freshness record (None) does not block finish."""
        with patch("harness.state.freshness.load_freshness",
                   return_value=None):
            with patch("harness.state.freshness.save_freshness"):
                with patch("harness.cli.helpers.get_head_sha",
                           return_value="abc"):
                    with patch("harness.scm.git.GitRepo") as mr:
                        mr.return_value.branch.return_value = "main"
                        with patch("subprocess.run") as msubp:
                            msubp.return_value = MagicMock(returncode=0)
                            cmd = FinishEngagementCommand(
                                slug="my-eng",
                                root=str(with_snapshot),
                                re_assess=False,
                            )
                            result = finish_handler.handle(cmd)

        assert result.success, f"Expected success, got: {result.error}"

    def test_git_add_failure(self, finish_handler, with_snapshot):
        """If git add fails, handler returns error."""
        with patch("harness.state.freshness.load_freshness",
                   return_value=MagicMock(stale=False)):
            with patch("harness.scm.git.GitRepo") as mr:
                mr.return_value.branch.return_value = "main"
                with patch("harness.cli.helpers.get_head_sha",
                           return_value="abc"):
                    with patch("subprocess.run") as msubp:
                        msubp.return_value = MagicMock(
                            returncode=1, stderr="mock git error"
                        )
                        cmd = FinishEngagementCommand(
                            slug="my-eng",
                            root=str(with_snapshot),
                            re_assess=False,
                        )
                        result = finish_handler.handle(cmd)

        assert result.success is False
        assert "Git add failed" in result.message

    def test_commit_aborted(self, finish_handler, with_snapshot):
        """If commit returns non-zero, handler returns error."""
        from unittest.mock import call
        with patch("harness.state.freshness.load_freshness",
                   return_value=MagicMock(stale=False)):
            with patch("harness.state.freshness.save_freshness"):
                with patch("harness.cli.helpers.get_head_sha",
                           return_value="abc"):
                    with patch("harness.scm.git.GitRepo") as mr:
                        mr.return_value.branch.return_value = "main"
                        # Git add succeeds, but git commit fails
                        def _side_effect(*a, **kw):
                            runs = []
                            for item in a:
                                if isinstance(item, list):
                                    runs.append(item)
                            if not runs:
                                runs = kw.get('args', kw.get('cmd', []))
                                if isinstance(runs, list):
                                    runs = [runs]
                            if any("add" in (r if isinstance(r, str) else "") for r in (runs[0] if runs else [])):
                                return MagicMock(returncode=0)
                            return MagicMock(returncode=1)
                        with patch("subprocess.run") as msubp:
                            msubp.side_effect = _side_effect
                            cmd = FinishEngagementCommand(
                                slug="my-eng",
                                root=str(with_snapshot),
                                re_assess=False,
                            )
                            result = finish_handler.handle(cmd)

        assert result.success is False
        assert "Commit aborted" in result.message

    def test_re_assessment(self, finish_handler, with_snapshot):
        """re_assess=True runs observer analysis."""
        with patch("harness.state.freshness.load_freshness",
                   return_value=MagicMock(stale=False)):
            with patch("harness.state.freshness.save_freshness"):
                with patch("harness.cli.helpers.get_head_sha",
                           return_value="abc123"):
                    with patch("harness.scm.git.GitRepo") as mr:
                        mr.return_value.branch.return_value = "main"
                        with patch("subprocess.run") as msubp:
                            msubp.return_value = MagicMock(returncode=0)
                            with patch(
                                "harness.analysis.observer.analyse",
                                return_value={"status": "error",
                                              "message": "mock error"},
                            ):
                                cmd = FinishEngagementCommand(
                                    slug="my-eng",
                                    root=str(with_snapshot),
                                    re_assess=True,
                                )
                                result = finish_handler.handle(cmd)

        assert result.success, f"Expected success, got: {result.error}"

    def test_exception_returns_error(self, finish_handler, tmp_project):
        """Unexpected exception returns error."""
        (tmp_project / ".harness").mkdir(parents=True, exist_ok=True)
        with patch("harness.scm.git.GitRepo"):
            with patch("harness.state.freshness.load_freshness",
                       side_effect=RuntimeError("boom")):
                cmd = FinishEngagementCommand(
                    slug="my-eng",
                    root=str(tmp_project),
                    re_assess=False,
                )
                result = finish_handler.handle(cmd)

        assert result.success is False
        assert "boom" in result.error


# ═══════════════════════════════════════════════════════════════════════
# ReviewEngagementTypedHandler Tests
# ═══════════════════════════════════════════════════════════════════════


class TestReviewEngagementTypedHandler:
    """Tests for ReviewEngagementTypedHandler — gate review decisions."""

    def _patch_snapshot(self, path: Path, decision: str):
        """Apply patches and return the command/result."""
        from harness.state.snapshot import (
            EngagementSnapshot,
            ProjectSnapshot,
            SnapshotWriter,
        )
        eng = EngagementSnapshot(
            id="my-eng", description="Test",
            status="active", gate_mode="auto", phase="design",
        )
        SnapshotWriter.write(
            ProjectSnapshot(project_name="test", version="0.1.0",
                            current_engagement="my-eng", engagements=[eng]),
            path / _HARNESS_SNAPSHOT,
        )

    def test_approve_updates_snapshot(self, review_handler, with_snapshot):
        """Approved decision updates snapshot to complete."""
        cmd = ReviewEngagementCommand(
            slug="my-eng",
            decision="approved",
            root=str(with_snapshot),
        )
        result = review_handler.handle(cmd)

        assert result.success, f"Expected success, got: {result.error}"
        assert result.decision == "approved"
        assert result.snapshot_updated is True

        from harness.cli.helpers import load_project_snapshot
        post = load_project_snapshot(with_snapshot / _HARNESS_SNAPSHOT)
        assert post.engagements[0].status == "complete"

    def test_reject_updates_snapshot(self, review_handler, with_snapshot):
        """Rejected decision updates snapshot to blocked."""
        cmd = ReviewEngagementCommand(
            slug="my-eng",
            decision="rejected",
            root=str(with_snapshot),
        )
        result = review_handler.handle(cmd)

        assert result.success
        assert result.decision == "rejected"

        from harness.cli.helpers import load_project_snapshot
        post = load_project_snapshot(with_snapshot / _HARNESS_SNAPSHOT)
        assert post.engagements[0].status == "blocked"

    def test_request_changes_updates_snapshot(self, review_handler, with_snapshot):
        """Request_changes updates snapshot to changes_requested."""
        cmd = ReviewEngagementCommand(
            slug="my-eng",
            decision="request_changes",
            root=str(with_snapshot),
        )
        result = review_handler.handle(cmd)

        assert result.success
        assert result.decision == "request_changes"

        from harness.cli.helpers import load_project_snapshot
        post = load_project_snapshot(with_snapshot / _HARNESS_SNAPSHOT)
        assert post.engagements[0].status == "changes_requested"

    def test_no_decision_returns_error(self, review_handler, with_snapshot):
        """Empty decision returns error."""
        cmd = ReviewEngagementCommand(
            slug="my-eng",
            decision="",
            root=str(with_snapshot),
        )
        result = review_handler.handle(cmd)

        assert result.success is False
        assert "No decision" in result.error

    def test_with_temporal_available(self, review_handler, with_snapshot):
        """When Temporal is available, gate review is sent and flag set."""
        with patch("harness.state.temporal_server.ensure_temporal_server",
                   return_value=True):
            with patch("harness.state.temporal_adapter.send_gate_review"):
                cmd = ReviewEngagementCommand(
                    slug="my-eng",
                    decision="approved",
                    root=str(with_snapshot),
                )
                result = review_handler.handle(cmd)

        assert result.success
        assert result.temporal_ok is True

    def test_temporal_failure_falls_through(self, review_handler, with_snapshot):
        """Temporal failure does not block the review."""
        with patch("harness.state.temporal_server.ensure_temporal_server",
                   side_effect=Exception("temporal unavailable")):
            cmd = ReviewEngagementCommand(
                slug="my-eng",
                decision="approved",
                root=str(with_snapshot),
            )
            result = review_handler.handle(cmd)

        assert result.success
        assert result.temporal_ok is False

    def test_exception_returns_error(self, review_handler, with_snapshot):
        """Unexpected exception returns error."""
        with patch("harness.cli.helpers.load_project_snapshot",
                   side_effect=RuntimeError("boom")):
            cmd = ReviewEngagementCommand(
                slug="my-eng",
                decision="approved",
                root=str(with_snapshot),
            )
            result = review_handler.handle(cmd)

        assert result.success is False
        assert "boom" in result.error
