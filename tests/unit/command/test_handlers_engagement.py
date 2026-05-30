"""Tests for FinishEngagementHandler and ReviewEngagementHandler.

Wave D: Engagement lifecycle handlers.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from harness.command.handlers import (
    FinishEngagementHandler,
    ReviewEngagementHandler,
    register_all_handlers,
)
from harness.command.registry import CommandRegistry
from harness.command.types import Command, CommandResult

# The handler uses get_harness_state_path() which returns
# ".harness/harness-state.yaml" (not state.json).
# get_harness_state_path() returns root/harness-state.yaml (no .harness/ prefix)
_HARNESS_SNAPSHOT = Path("harness-state.yaml")


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """Minimal project with .harness state dir."""
    (tmp_path / ".harness").mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def finish_handler() -> FinishEngagementHandler:
    return FinishEngagementHandler()


@pytest.fixture
def review_handler() -> ReviewEngagementHandler:
    return ReviewEngagementHandler()


@pytest.fixture
def with_snapshot(tmp_project: Path) -> Path:
    """Create snapshot with one active engagement at the correct path."""
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
# FinishEngagementHandler Tests
# ═══════════════════════════════════════════════════════════════════════


class TestFinishEngagementHandler:
    """Tests for FinishEngagementHandler — git stage/commit, snapshot, re-assessment."""

    def _patch_all_finish(self, freshness=None, stale=False):
        """Return nested patch context for FinishEngagementHandler deps."""
        # Use direct nesting instead of ExitStack for reliability
        pass

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
                            cmd = Command(
                                slug="my-eng",
                                command_type="finish_engagement",
                                data={"root": str(with_snapshot),
                                      "re_assess": False},
                            )
                            result = finish_handler.handle(cmd)

        assert result.success, f"Expected success, got: {result.error}"
        assert "Engagement finished" in result.message
        assert result.data["head_sha"] == "abc123def456"
        assert result.data["slug"] == "my-eng"

        post = load_project_snapshot(snap_path)
        assert post.engagements[0].status == "complete"

    def test_stale_state_prevents_finish(self, finish_handler, with_snapshot):
        """Stale freshness record blocks finish."""
        with patch("harness.state.freshness.load_freshness",
                   return_value=MagicMock(stale=True)):
            cmd = Command(
                slug="my-eng",
                command_type="finish_engagement",
                data={"root": str(with_snapshot), "re_assess": False},
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
                            cmd = Command(
                                slug="my-eng",
                                command_type="finish_engagement",
                                data={"root": str(with_snapshot),
                                      "re_assess": False},
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
                            returncode=1, stderr="permission denied"
                        )
                        cmd = Command(
                            slug="my-eng",
                            command_type="finish_engagement",
                            data={"root": str(with_snapshot),
                                  "re_assess": False},
                        )
                        result = finish_handler.handle(cmd)

        assert result.success is False
        assert "Git add failed" in result.message

    def test_commit_aborted(self, finish_handler, with_snapshot):
        """If commit returns non-zero, handler returns error."""
        with patch("harness.state.freshness.load_freshness",
                   return_value=MagicMock(stale=False)):
            with patch("harness.scm.git.GitRepo") as mr:
                mr.return_value.branch.return_value = "main"
                with patch("harness.cli.helpers.get_head_sha",
                           return_value="abc"):
                    with patch("subprocess.run") as msubp:
                        msubp.side_effect = [
                            MagicMock(returncode=0),
                            MagicMock(returncode=1, stderr="commit error"),
                        ]
                        cmd = Command(
                            slug="my-eng",
                            command_type="finish_engagement",
                            data={"root": str(with_snapshot),
                                  "re_assess": False},
                        )
                        result = finish_handler.handle(cmd)

        assert result.success is False
        assert "Commit aborted" in result.message

    def test_re_assessment(self, finish_handler, with_snapshot):
        """With re_assess=True, runs observer analysis and records history."""
        eng_dir = with_snapshot / ".harness" / "engagements" / "my-eng"
        eng_dir.mkdir(parents=True, exist_ok=True)
        (eng_dir / "assessments").mkdir(parents=True, exist_ok=True)

        import json
        import yaml
        (eng_dir / "manifest.json").write_text(
            json.dumps({"findings": [
                {"message": "Old A"}, {"message": "Old B"},
            ]})
        )
        (eng_dir / "engagement.yaml").write_text(
            yaml.dump({
                "baseline_finding_count": 2,
                "session_type": "greenfield",
                "baseline_manifest": "manifest.json",
            })
        )
        (with_snapshot / ".harness" / "config.yaml").write_text(
            yaml.dump({})
        )

        with patch("harness.state.freshness.load_freshness",
                   return_value=MagicMock(stale=False)):
            with patch("harness.state.freshness.save_freshness"):
                with patch("harness.scm.git.GitRepo") as mr:
                    mr.return_value.branch.return_value = "main"
                    with patch("harness.cli.helpers.get_head_sha",
                               side_effect=["abc", "def"]):
                        with patch("subprocess.run") as msubp:
                            msubp.return_value = MagicMock(returncode=0)
                            with patch(
                                "harness.analysis.observer.analyse"
                            ) as ma:
                                ma.return_value = {
                                    "status": "ok",
                                    "report": "# Assessment\n\nFindings...",
                                    "assessment": {
                                        "assessment": {
                                            "score": "B+",
                                            "findings": [{
                                                "id": "finding-001",
                                                "message": "New finding",
                                                "severity": "warning",
                                            }],
                                        }
                                    },
                                }
                                with patch(
                                    "harness.cli.helpers."
                                    "write_assessment_report"
                                ) as mw:
                                    mw.return_value = str(
                                        eng_dir / "assessments" / "r.md"
                                    )
                                    cmd = Command(
                                        slug="my-eng",
                                        command_type="finish_engagement",
                                        data={"root": str(with_snapshot),
                                              "re_assess": True},
                                    )
                                    result = finish_handler.handle(cmd)

        assert result.success, f"Expected success, got: {result.error}"
        assert "re_assessment" in result.data
        ra = result.data["re_assessment"]
        assert "baseline_count" in ra
        assert "current_findings" in ra
        assert "closed_count" in ra

        config = yaml.safe_load(
            (with_snapshot / ".harness" / "config.yaml").read_text()
        )
        assert "assessment_history" in config
        assert len(config["assessment_history"]) == 1

    def test_exception_returns_error(self, finish_handler, with_snapshot):
        """Unexpected exception is caught and returned as error."""
        # Patch both freshness AND GitRepo to isolate the exception path
        # Without GitRepo mock, construction happens before load_freshness call
        with patch("harness.state.freshness.load_freshness",
                   return_value=MagicMock(stale=False)):
            with patch("harness.scm.git.GitRepo") as mr:
                mr.side_effect = RuntimeError("unexpected error")
                cmd = Command(
                    slug="my-eng",
                    command_type="finish_engagement",
                    data={"root": str(with_snapshot), "re_assess": False},
                )
                result = finish_handler.handle(cmd)

        assert result.success is False
        assert "unexpected error" in result.error


# ═══════════════════════════════════════════════════════════════════════
# ReviewEngagementHandler Tests
# ═══════════════════════════════════════════════════════════════════════


class TestReviewEngagementHandler:
    """Tests for ReviewEngagementHandler — gate review + snapshot update."""

    def _snap_path(self, root):
        return root / _HARNESS_SNAPSHOT

    def _assert_status(self, root, expected_status):
        from harness.cli.helpers import load_project_snapshot
        post = load_project_snapshot(self._snap_path(root))
        assert post.engagements, "No engagements in snapshot"
        assert post.engagements[0].status == expected_status, \
            f"Expected {expected_status}, got {post.engagements[0].status}"

    def test_approve_updates_snapshot(self, review_handler, with_snapshot):
        """Approved engagement updates snapshot to complete."""
        from harness.cli.helpers import load_project_snapshot
        pre = load_project_snapshot(self._snap_path(with_snapshot))
        assert pre.engagements[0].status == "active"

        with patch("harness.state.temporal_server.ensure_temporal_server",
                   return_value=False):
            cmd = Command(
                slug="my-eng",
                command_type="review_engagement",
                data={"decision": "approved", "root": str(with_snapshot)},
            )
            result = review_handler.handle(cmd)

        assert result.success, f"Got: {result.error}"
        assert "Gate approved" in result.message
        assert "local" in result.message
        assert result.data["decision"] == "approved"
        assert result.data["snapshot_updated"] is True
        assert result.data["temporal_ok"] is False
        self._assert_status(with_snapshot, "complete")

    def test_reject_updates_snapshot(self, review_handler, with_snapshot):
        """Rejected engagement updates snapshot to blocked."""
        with patch("harness.state.temporal_server.ensure_temporal_server",
                   return_value=False):
            cmd = Command(
                slug="my-eng",
                command_type="review_engagement",
                data={"decision": "rejected", "root": str(with_snapshot)},
            )
            result = review_handler.handle(cmd)

        assert result.success, f"Got: {result.error}"
        assert "Gate rejected" in result.message
        assert result.data["snapshot_updated"] is True
        self._assert_status(with_snapshot, "blocked")

    def test_request_changes_updates_snapshot(self, review_handler,
                                               with_snapshot):
        """Request changes updates snapshot to changes_requested."""
        with patch("harness.state.temporal_server.ensure_temporal_server",
                   return_value=False):
            cmd = Command(
                slug="my-eng",
                command_type="review_engagement",
                data={"decision": "request_changes",
                      "root": str(with_snapshot)},
            )
            result = review_handler.handle(cmd)

        assert result.success, f"Got: {result.error}"
        assert "Gate request_changes" in result.message
        assert result.data["snapshot_updated"] is True
        self._assert_status(with_snapshot, "changes_requested")

    def test_no_decision_returns_error(self, review_handler, with_snapshot):
        """Missing decision returns error."""
        cmd = Command(
            slug="my-eng",
            command_type="review_engagement",
            data={"root": str(with_snapshot)},
        )
        result = review_handler.handle(cmd)
        assert result.success is False
        assert "No decision" in result.error

    def test_with_temporal_available(self, review_handler, with_snapshot):
        """When Temporal is available, temporal_ok is True."""
        with patch("harness.state.temporal_server.ensure_temporal_server",
                   return_value=True):
            with patch("harness.state.temporal_adapter.send_gate_review",
                       return_value=None):
                cmd = Command(
                    slug="my-eng",
                    command_type="review_engagement",
                    data={"decision": "approved",
                          "root": str(with_snapshot)},
                )
                result = review_handler.handle(cmd)

        assert result.success, f"Got: {result.error}"
        assert result.data["temporal_ok"] is True
        assert "temporal" in result.message

    def test_temporal_failure_falls_through(self, review_handler,
                                             with_snapshot):
        """Temporal failure doesn't prevent local snapshot update."""
        with patch("harness.state.temporal_server.ensure_temporal_server",
                   return_value=True):
            with patch("harness.state.temporal_adapter.send_gate_review",
                       side_effect=RuntimeError("Temporal down")):
                cmd = Command(
                    slug="my-eng",
                    command_type="review_engagement",
                    data={"decision": "rejected",
                          "root": str(with_snapshot)},
                )
                result = review_handler.handle(cmd)

        assert result.success, f"Got: {result.error}"
        assert "local" in result.message
        assert result.data["temporal_ok"] is False

    def test_exception_returns_error(self, review_handler, with_snapshot):
        """Unexpected exception returns error.

        Temporal inner try/except catches ensure_temporal_server
        exceptions, so we raise from load_project_snapshot instead
        (called in the snapshot-update section outside the inner try).
        """
        with patch(
            "harness.state.temporal_server.ensure_temporal_server",
            return_value=False,
        ):
            with patch(
                "harness.cli.helpers.load_project_snapshot",
                side_effect=RuntimeError("unexpected"),
            ):
                cmd = Command(
                    slug="my-eng",
                    command_type="review_engagement",
                    data={"decision": "approved",
                          "root": str(with_snapshot)},
                )
                result = review_handler.handle(cmd)

        assert result.success is False
        assert "unexpected" in result.error


# ═══════════════════════════════════════════════════════════════════════
# Registration Tests
# ═══════════════════════════════════════════════════════════════════════


class TestRegistration:
    """Verify that engagement handlers are registered correctly."""

    def test_handlers_are_registered(self):
        registry = CommandRegistry()
        register_all_handlers(registry)
        assert registry.get_handler("finish_engagement") is not None
        assert registry.get_handler("review_engagement") is not None

    def test_registration_includes_sprint2_handlers(self):
        registry = CommandRegistry()
        register_all_handlers(registry)
        types = registry.list_registered()
        assert "finish_engagement" in types
        assert "review_engagement" in types
