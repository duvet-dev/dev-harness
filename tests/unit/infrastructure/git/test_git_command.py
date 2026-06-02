"""Tests for ``harness.infrastructure.git.git_command``."""

from pathlib import Path
from unittest.mock import ANY, patch

import pytest

from harness.infrastructure.git.git_command import GitCommandRunner
from harness.scm.git_types import GitOperationError


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def runner():
    return GitCommandRunner()


# ── Successful execution ────────────────────────────────────────────────────


class TestRun:
    """Verify basic command execution."""

    def test_returns_stdout(self, runner, tmp_path):
        result = runner.run(["version"], cwd=tmp_path)
        assert "git version" in result

    def test_preserves_trailing_newline(self, runner, tmp_path):
        """The runner returns stdout as-is, including trailing newline."""
        result = runner.run(["version"], cwd=tmp_path)
        assert result.endswith("\n")

    def test_passes_args_correctly(self, runner, tmp_path):
        """Verify that args are forwarded to the subprocess."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "hello\n"
            result = runner.run(["status", "--porcelain"], cwd=tmp_path)
            assert result == "hello\n"
            mock_run.assert_called_once_with(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                cwd=str(tmp_path),
                timeout=30,
            )

    def test_uses_custom_timeout(self, runner, tmp_path):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "ok\n"
            runner.run(["status"], cwd=tmp_path, timeout=5)
            mock_run.assert_called_once_with(
                ["git", "status"],
                capture_output=True,
                text=True,
                cwd=str(tmp_path),
                timeout=5,
            )


# ── Error handling ──────────────────────────────────────────────────────────


class TestRunErrors:
    """Verify error handling on non-zero exit and timeouts."""

    def test_raises_on_nonzero_exit(self, runner, tmp_path):
        """Running git in a non-repo dir raises GitOperationError."""
        with pytest.raises(GitOperationError) as excinfo:
            runner.run(["rev-parse", "--git-dir"], cwd=tmp_path)
        assert "rev-parse" in str(excinfo.value)
        assert excinfo.value.exit_code != 0

    def test_raises_on_timeout(self, runner, tmp_path):
        """Simulate a timeout to verify GitOperationError is raised."""
        with patch("subprocess.run") as mock_run:
            import subprocess
            mock_run.side_effect = subprocess.TimeoutExpired(
                cmd="git log", timeout=1, output=""
            )
            with pytest.raises(GitOperationError) as excinfo:
                runner.run(["log"], cwd=tmp_path, timeout=1)
            assert excinfo.value.exit_code == -1
            assert "timed out" in str(excinfo.value).lower()


# ── GitOperationError details ──────────────────────────────────────────────


class TestGitOperationError:
    """Verify GitOperationError reporting."""

    def test_stores_cmd_and_exit_code(self):
        err = GitOperationError(cmd="git status", exit_code=1, stderr="error")
        assert err.cmd == "git status"
        assert err.exit_code == 1
        assert err.stderr == "error"
        assert "git status" in str(err)

    def test_strips_stderr_whitespace(self):
        err = GitOperationError(cmd="git diff", exit_code=128, stderr="  fatal: not a repo  ")
        assert "fatal: not a repo" in str(err)
