"""Tests for infrastructure/yaml/shell.py."""

from __future__ import annotations

import pytest

from harness.infrastructure.yaml.shell import ShellResult, RealShell


# ── ShellResult ────────────────────────────────────────────────────────────


class TestShellResult:
    def test_success_true_when_returncode_zero(self):
        sr = ShellResult(returncode=0)
        assert sr.success is True

    def test_success_false_when_nonzero(self):
        sr = ShellResult(returncode=1)
        assert sr.success is False

    def test_stores_stdout_and_stderr(self):
        sr = ShellResult(returncode=0, stdout="out", stderr="err")
        assert sr.stdout == "out"
        assert sr.stderr == "err"

    def test_defaults(self):
        sr = ShellResult(returncode=0)
        assert sr.stdout == ""
        assert sr.stderr == ""


# ── Shell protocol ─────────────────────────────────────────────────────────


class TestShellProtocol:
    def test_protocol_methods_exist(self):
        from harness.infrastructure.yaml.shell import Shell
        assert hasattr(Shell, "run")


# ── RealShell ──────────────────────────────────────────────────────────────


class TestRealShell:
    @pytest.fixture
    def shell(self) -> RealShell:
        return RealShell()

    def test_run_success(self, shell):
        result = shell.run(["echo", "hello"])
        assert result.success
        assert "hello" in result.stdout

    def test_run_failure(self, shell):
        result = shell.run(["false"])
        assert not result.success
        assert result.returncode != 0

    def test_run_with_cwd(self, shell, tmp_path):
        result = shell.run(["pwd"], cwd=str(tmp_path))
        assert result.success
        assert str(tmp_path) in result.stdout

    def test_run_command_not_found(self, shell):
        result = shell.run(["nonexistent_command_xyz"])
        assert not result.success
        assert "not found" in result.stderr

    def test_run_with_env(self, shell):
        result = shell.run(
            ["sh", "-c", "echo $MY_VAR"],
            env={"MY_VAR": "test_value"},
        )
        assert result.success
        assert "test_value" in result.stdout

    def test_run_timeout(self, shell):
        """Timeout results in a failure with -1 returncode."""
        result = shell.run(["sleep", "10"], timeout=1)
        assert not result.success
        assert result.returncode == -1
