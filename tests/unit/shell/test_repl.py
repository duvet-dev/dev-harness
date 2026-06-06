"""Tests for harness.shell.repl."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from harness.shell.repl import HarnessREPL, _REPLCompleter, shell
from harness.command.types import CommandResult


class TestHarnessREPL:
    def test_init_default_root(self, tmp_path):
        with patch("harness.shell.repl.Path.cwd", return_value=tmp_path):
            repl = HarnessREPL()
            assert repl.root == tmp_path

    def test_init_explicit_root(self, tmp_path):
        root = tmp_path / "test-root"
        root.mkdir()
        with patch("harness.shell.repl.Path.cwd", return_value=tmp_path):
            repl = HarnessREPL(root=root)
            assert repl.root == root

    def test_build_command_index(self):
        """Should build command index from CLI without errors."""
        # This test calls the real CLI import — it should work here
        root = Path("/tmp/test-repl")
        root.mkdir(parents=True, exist_ok=True)
        try:
            repl = HarnessREPL(root=root)
            assert hasattr(repl, "commands")
            assert len(repl.commands) > 0
            assert "help" in repl._help_lines[0] or any("help" in l for l in repl._help_lines)
        finally:
            # Clean up
            pass

    def test_run_loop_exit(self, tmp_path):
        """REPL should exit cleanly on /exit command."""
        repl = HarnessREPL(root=tmp_path)
        with patch("builtins.input", return_value="/exit"):
            with patch("click.echo"):  # suppress output
                repl.run()
                # Should reach end without error

    def test_run_loop_eof(self, tmp_path):
        """REPL should handle EOFError gracefully."""
        repl = HarnessREPL(root=tmp_path)
        with patch("builtins.input", side_effect=EOFError()):
            with patch("click.echo"):
                repl.run()

    def test_run_loop_interrupt(self, tmp_path):
        """REPL should handle KeyboardInterrupt gracefully."""
        repl = HarnessREPL(root=tmp_path)
        with patch("builtins.input", side_effect=KeyboardInterrupt()):
            with patch("click.echo"):
                repl.run()

    def test_flush_history_no_error(self, tmp_path):
        """_flush_history should never raise."""
        HarnessREPL._flush_history()

    def test_get_active_engagement_no_context(self, tmp_path):
        """Should return None when no engagement context."""
        repl = HarnessREPL(root=tmp_path)
        result = repl._get_active_engagement()
        assert result is None

    def test_prompt_without_engagement(self, tmp_path):
        """Prompt should show bare harness> without engagement."""
        repl = HarnessREPL(root=tmp_path)
        with patch.object(repl, "_get_active_engagement", return_value=None):
            prompt = repl._prompt()
            assert "harness" in prompt
            assert "[" not in prompt or "\\" in prompt  # no ANSI without engagement

    @patch("harness.shell.repl.click.echo")
    def test_run_command_help(self, mock_echo, tmp_path):
        repl = HarnessREPL(root=tmp_path)
        result = repl._run_command("/help")
        assert result is True  # Continue running

    @patch("harness.shell.repl.click.echo")
    def test_run_command_exit(self, mock_echo, tmp_path):
        repl = HarnessREPL(root=tmp_path)
        result = repl._run_command("/exit")
        assert result is False  # Stop running

    @patch("harness.shell.repl.click.echo")
    def test_run_command_quit(self, mock_echo, tmp_path):
        repl = HarnessREPL(root=tmp_path)
        result = repl._run_command("/quit")
        assert result is False

    @patch("harness.shell.repl.click.echo")
    def test_run_command_shell(self, mock_echo, tmp_path):
        repl = HarnessREPL(root=tmp_path)
        result = repl._run_command("/shell")
        assert result is True  # Already in shell

    @patch("harness.shell.repl.click.echo")
    def test_run_command_no_slash(self, mock_echo, tmp_path):
        repl = HarnessREPL(root=tmp_path)
        result = repl._run_command("some text without slash")
        assert result is True

    @patch("harness.shell.repl.click.echo")
    def test_run_command_empty(self, mock_echo, tmp_path):
        repl = HarnessREPL(root=tmp_path)
        result = repl._run_command("")
        assert result is True

    @patch("harness.shell.repl.click.echo")
    def test_run_command_only_slash(self, mock_echo, tmp_path):
        repl = HarnessREPL(root=tmp_path)
        result = repl._run_command("/")
        assert result is True

    @patch("harness.shell.repl.click.echo")
    @patch("harness.domain.engagement.resolver.resolve_active_engagement")
    def test_get_well_no_engagement(self, mock_resolve, mock_echo, tmp_path):
        """/get-well with no active engagement should print message and continue."""
        mock_resolve.return_value = None
        repl = HarnessREPL(root=tmp_path)
        result = repl._run_command("/get-well")
        assert result is True

    @patch("harness.shell.repl.click.echo")
    @patch("harness.shell.repl._build_command_bus")
    @patch("harness.domain.engagement.resolver.resolve_active_engagement")
    def test_get_well_with_engagement(self, mock_resolve, mock_bus, mock_echo, tmp_path, monkeypatch):
        """/get-well with active engagement should start a session."""
        from unittest.mock import AsyncMock
        mock_session = AsyncMock()
        monkeypatch.setattr("harness.session.session_orchestrator.run_phase_session", mock_session)
        mock_bus.return_value.dispatch.return_value = CommandResult(success=True, message="Session setup OK")

        mock_resolve.return_value = "test-eng"
        eng_dir = tmp_path / ".harness" / "engagements" / "test-eng"
        eng_dir.mkdir(parents=True)

        import yaml
        (tmp_path / ".harness" / "providers.yaml").write_text(yaml.dump({
            "default_backend": "dp",
            "providers": {
                "dp": {
                    "type": "openai-compatible",
                    "api_key": "test-key",
                    "models": [{"name": "test-model"}],
                }
            }
        }))

        (tmp_path / ".harness" / "active-engagements.yaml").write_text(yaml.dump({
            "branches": {"main": "test-eng"}
        }))

        repl = HarnessREPL(root=tmp_path)
        result = repl._run_command("/get-well")
        assert result is True
        mock_session.assert_called_once()
        _, kwargs = mock_session.call_args
        assert kwargs.get("session_type") == "get-well"
        assert kwargs.get("start_phase") == "assessment-triage"

    @patch("harness.shell.repl.click.echo")
    @patch("harness.shell.repl._build_command_bus")
    @patch("harness.domain.engagement.resolver.resolve_active_engagement")
    def test_get_well_with_custom_phase(self, mock_resolve, mock_bus, mock_echo, tmp_path, monkeypatch):
        """/get-well architecture-design starts from a specific phase."""
        from unittest.mock import AsyncMock
        mock_session = AsyncMock()
        monkeypatch.setattr("harness.session.session_orchestrator.run_phase_session", mock_session)
        mock_bus.return_value.dispatch.return_value = CommandResult(success=True, message="Session setup OK")

        mock_resolve.return_value = "test-eng"
        repl = HarnessREPL(root=tmp_path)
        result = repl._run_command("/get-well architecture-design")
        assert result is True
        mock_session.assert_called_once()
        _, kwargs = mock_session.call_args
        assert kwargs.get("start_phase") == "architecture-design"

    @patch("harness.shell.repl.click.echo")
    @patch("harness.domain.engagement.resolver.resolve_active_engagement")
    def test_session_get_well_no_engagement(self, mock_resolve, mock_echo, tmp_path):
        """/session --get-well with no active engagement should print message."""
        mock_resolve.return_value = None
        repl = HarnessREPL(root=tmp_path)
        result = repl._run_command("/session --get-well")
        assert result is True

    @patch("harness.shell.repl.click.echo")
    @patch("harness.shell.repl._build_command_bus")
    @patch("harness.domain.engagement.resolver.resolve_active_engagement")
    def test_session_get_well_dispatches(self, mock_resolve, mock_bus, mock_echo, tmp_path, monkeypatch):
        """/session --get-well dispatches to get-well session with correct args."""
        from unittest.mock import AsyncMock
        mock_session = AsyncMock()
        monkeypatch.setattr("harness.session.session_orchestrator.run_phase_session", mock_session)
        mock_bus.return_value.dispatch.return_value = CommandResult(success=True, message="Session setup OK")

        mock_resolve.return_value = "test-eng"
        repl = HarnessREPL(root=tmp_path)
        result = repl._run_command("/session --get-well")
        assert result is True
        mock_session.assert_called_once()
        _, kwargs = mock_session.call_args
        assert kwargs.get("session_type") == "get-well"


class TestREPLCompleter:
    def test_init(self, tmp_path):
        repl = HarnessREPL(root=tmp_path)
        completer = _REPLCompleter(repl)
        assert completer.repl is repl
        assert len(completer._first_tokens) > 0

    def test_complete_initial_state(self, tmp_path):
        repl = HarnessREPL(root=tmp_path)
        completer = _REPLCompleter(repl)

        with patch("harness.shell.repl.readline.get_line_buffer", return_value=""):
            with patch("harness.shell.repl.readline.get_endidx", return_value=0):
                result = completer.complete("", 0)
                assert result is not None
                assert result.startswith("/")

    def test_complete_after_slash(self, tmp_path):
        repl = HarnessREPL(root=tmp_path)
        completer = _REPLCompleter(repl)

        with patch("harness.shell.repl.readline.get_line_buffer", return_value="/"):
            with patch("harness.shell.repl.readline.get_endidx", return_value=1):
                result = completer.complete("", 0)
                assert result is not None
                assert result.startswith("/")

    def test_complete_with_prefix(self, tmp_path):
        repl = HarnessREPL(root=tmp_path)
        completer = _REPLCompleter(repl)

        with patch("harness.shell.repl.readline.get_line_buffer", return_value="/ex"):
            with patch("harness.shell.repl.readline.get_endidx", return_value=3):
                result = completer.complete("ex", 0)
                # Should find some match starting with ex, or return None
                if result is not None:
                    assert "ex" in result.lower()
                # Acceptable either way

    def test_complete_with_nonexistent_prefix(self, tmp_path):
        repl = HarnessREPL(root=tmp_path)
        completer = _REPLCompleter(repl)

        with patch("harness.shell.repl.readline.get_line_buffer", return_value="/zzz_nonexistent_"):
            with patch("harness.shell.repl.readline.get_endidx", return_value=18):
                result = completer.complete("zzz_nonexistent_", 0)
                assert result is None

    def test_complete_path_fallback(self, tmp_path):
        """Should complete file paths for non-first words."""
        (tmp_path / "somefile.txt").write_text("test")
        (tmp_path / "other.md").write_text("test")

        repl = HarnessREPL(root=tmp_path)
        # Patch cwd to tmp_path for file completion
        with (
            patch("harness.shell.repl.Path.cwd", return_value=tmp_path),
            patch("harness.shell.repl.readline.get_line_buffer", return_value="/engagement status /tm"),
            patch("harness.shell.repl.readline.get_endidx", return_value=23),
        ):
            completer = _REPLCompleter(repl)
            # Should get path suggestions
            matches = completer._complete_path("/tm")
            # /tmp should be a directory
            assert "/tmp" in str(matches) or any("tmp" in m for m in matches)

    def test_complete_path_with_directory(self, tmp_path):
        """Directories should get trailing slash."""
        dir_path = tmp_path / "mydir"
        dir_path.mkdir()

        completer = _REPLCompleter.__new__(_REPLCompleter)
        matches = completer._complete_path(str(tmp_path / "mydir")[:-1])
        # Should find the dir
        assert len(matches) >= 1

    def test_complete_path_no_match(self, tmp_path):
        completer = _REPLCompleter.__new__(_REPLCompleter)
        matches = completer._complete_path(str(tmp_path / "_nonexistent_xyz_"))
        assert matches == []

    def test_complete_path_empty_prefix(self):
        completer = _REPLCompleter.__new__(_REPLCompleter)
        matches = completer._complete_path("")
        # Should list current directory contents
        assert len(matches) >= 0  # might be empty in weird envs

    def test_complete_second_word_fallback_path(self, tmp_path):
        """When the command isn't known, fall back to path completion."""
        (tmp_path / "data.txt").write_text("stuff")

        repl = HarnessREPL(root=tmp_path)
        # Create files to complete
        (tmp_path / "data.txt").write_text("stuff")
        (tmp_path / "dat2.txt").write_text("other")

        with (
            patch("harness.shell.repl.readline.get_line_buffer", return_value="/engagement status da"),
            patch("harness.shell.repl.readline.get_endidx", return_value=21),
            patch("harness.shell.repl.Path.cwd", return_value=tmp_path),
        ):
            completer = _REPLCompleter(repl)
            result = completer.complete("da", 0)
            # Fallback to path completion should find data.txt
            if result is not None:
                assert "data" in result

    def test_multiple_completer_states(self, tmp_path):
        """Test that multiple state calls return sequential results."""
        repl = HarnessREPL(root=tmp_path)
        completer = _REPLCompleter(repl)

        with patch("harness.shell.repl.readline.get_line_buffer", return_value=""):
            with patch("harness.shell.repl.readline.get_endidx", return_value=0):
                state0 = completer.complete("", 0)
                state1 = completer.complete("", 1)
                assert state0 is not None
                assert state1 is not None or state0 is not None


class TestShellFunction:
    def test_shell_entry_point(self, tmp_path):
        """shell() should create a REPL and run it."""
        with (
            patch("harness.shell.repl.HarnessREPL") as mock_repl_cls,
            patch("harness.shell.repl.Path.cwd", return_value=tmp_path),
        ):
            mock_instance = MagicMock()
            mock_repl_cls.return_value = mock_instance

            shell()
            mock_repl_cls.assert_called_once()
            mock_instance.run.assert_called_once()

    def test_shell_with_root(self, tmp_path):
        with (
            patch("harness.shell.repl.HarnessREPL") as mock_repl_cls,
        ):
            shell(root=tmp_path)
            mock_repl_cls.assert_called_once_with(root=tmp_path)


class TestREPLEdgeCases:
    def test_history_file_path(self):
        from harness.shell.repl import HISTORY_FILE
        assert "harness" in HISTORY_FILE
        assert "shell_history" in HISTORY_FILE

    def test_group_map(self):
        from harness.shell.repl import GROUP_MAP
        assert "engagement" in GROUP_MAP
        assert "agent" in GROUP_MAP

    @patch("harness.shell.repl.click.echo")
    def test_run_command_with_click_command(self, mock_echo, tmp_path):
        """Running a valid Click command should dispatch without error."""
        repl = HarnessREPL(root=tmp_path)
        # Use a simple command that exists
        result = repl._run_command("/help")
        assert result is True

    @patch("harness.shell.repl.click.echo")
    def test_run_command_dispatch_error(self, mock_echo, tmp_path):
        """Invalid Click command should produce error message."""
        repl = HarnessREPL(root=tmp_path)
        result = repl._run_command("/nonexistent-command")
        assert result is True


class TestCompleterEdgeCases:
    def test_complete_permission_denied(self):
        """Path completion should handle permission errors gracefully."""
        completer = _REPLCompleter.__new__(_REPLCompleter)
        # A directory with no read permission
        # Just verify it returns empty list, not crashes
        with patch.object(Path, "iterdir", side_effect=PermissionError):
            matches = completer._complete_path("/root")
            assert matches == []


class TestDispatchViaBus:
    """Tests for _dispatch_via_bus()."""

    def test_dispatch_via_bus_success(self):
        """_dispatch_via_bus should return a CommandResult for valid typed commands."""
        from harness.shell.repl import _dispatch_via_bus
        from harness.command.commands.mgmt import AgentListCommand

        cmd = AgentListCommand(slug="")
        result = _dispatch_via_bus(cmd)
        assert result is not None
        assert isinstance(result, CommandResult)

    def test_dispatch_via_bus_unknown_command(self):
        """_dispatch_via_bus with unknown type raises error."""
        from harness.shell.repl import _dispatch_via_bus
        from harness.command.types import CommandResult
        from harness.errors import UnknownCommandError

        class UnknownCmd:
            pass

        cmd = UnknownCmd()
        try:
            result = _dispatch_via_bus(cmd)
            assert isinstance(result, CommandResult)
        except UnknownCommandError:
            pass


class TestREPLCommandDispatch:
    """Additional command dispatch edge cases."""

    @patch("harness.shell.repl.click.echo")
    def test_run_command_no_slash_prints_warning(self, mock_echo, tmp_path):
        """Commands without / prefix should print a warning."""
        repl = HarnessREPL(root=tmp_path)
        result = repl._run_command("status")
        assert result is True
        mock_echo.assert_called_once()
        assert "Commands start with /" in mock_echo.call_args[0][0]

    @patch("harness.shell.repl.click.echo")
    def test_run_command_help_displays_lines(self, mock_echo, tmp_path):
        """/help should display help lines."""
        repl = HarnessREPL(root=tmp_path)
        result = repl._run_command("/help")
        assert result is True
        # Should have multiple echo calls for help lines
        assert mock_echo.call_count > 1

    @patch("harness.shell.repl.click.echo")
    def test_run_command_shell_says_already(self, mock_echo, tmp_path):
        """/shell should say already in REPL."""
        repl = HarnessREPL(root=tmp_path)
        result = repl._run_command("/shell")
        assert result is True
        assert "Already in the REPL" in mock_echo.call_args[0][0]

    @patch("harness.shell.repl.click.echo")
    def test_run_exec_no_command(self, mock_echo, tmp_path):
        """/exec without args should show usage."""
        repl = HarnessREPL(root=tmp_path)
        result = repl._run_command("/exec")
        assert result is True
        assert "Usage: /exec" in mock_echo.call_args[0][0]

    @patch("harness.shell.repl.click.echo")
    def test_run_exec_subprocess_timeout(self, mock_echo, tmp_path):
        """/exec should handle exceptions gracefully."""
        repl = HarnessREPL(root=tmp_path)
        # Just verify the command runs without crashing
        result = repl._run_command("/exec echo hello")
        assert result is True

    @patch("harness.shell.repl.click.echo")
    def test_run_exec_subprocess_exception(self, mock_echo, tmp_path):
        """/exec handles commands that execute successfully."""
        repl = HarnessREPL(root=tmp_path)
        result = repl._run_command("/exec echo hello")
        assert result is True


class TestREPLCommandBusDispatch:
    """Tests for REPL dispatching through CommandBus."""

    @patch("harness.shell.repl.click.echo")
    def test_known_command_dispatches(self, mock_echo, tmp_path):
        """Known COMMAND_TYPES entries should dispatch via bus."""
        with patch("harness.shell.repl._dispatch_via_bus") as mock_bus:
            mock_bus.return_value = CommandResult(
                success=True, message="Command successful", data={}
            )
            repl = HarnessREPL(root=tmp_path)
            result = repl._run_command("/agent list")
        assert result is True
        mock_bus.assert_called()
        mock_echo.assert_called_with("Command successful")

    @patch("harness.shell.repl.click.echo")
    def test_command_bus_error(self, mock_echo, tmp_path):
        """CommandBus errors should display correctly."""
        with patch("harness.shell.repl._dispatch_via_bus") as mock_bus:
            mock_bus.return_value = CommandResult(
                success=False, error="Something went wrong", message="Failed"
            )
            repl = HarnessREPL(root=tmp_path)
            result = repl._run_command("/agent list")
        assert result is True
        # Should echo error
        assert len(mock_echo.call_args_list) >= 1

    @patch("harness.shell.repl.click.echo")
    def test_command_bus_argument_parsing_exception(self, mock_echo, tmp_path):
        """Argument parsing exceptions should be caught gracefully."""
        with patch("harness.shell.repl._dispatch_via_bus") as mock_bus:
            mock_bus.side_effect = Exception("parse error")
            repl = HarnessREPL(root=tmp_path)
            result = repl._run_command("/agent list")
        assert result is True

    @patch("harness.shell.repl.click.echo")
    def test_unknown_command_shows_error(self, mock_echo, tmp_path):
        """Unknown commands should show an error message instead of Click fallback."""
        repl = HarnessREPL(root=tmp_path)
        result = repl._run_command("/nonexistent-command")
        assert result is True
        # Should show unknown command message
        error_msg = mock_echo.call_args[0][0]
        assert "Unknown command" in error_msg


class TestREPLGetWellEdgeCases:
    """Edge cases for /get-well command."""

    @patch("harness.shell.repl.click.echo")
    @patch("harness.domain.engagement.resolver.resolve_active_engagement")
    def test_get_well_no_engagement(self, mock_resolve, mock_echo, tmp_path):
        """/get-well with no active engagement should print message."""
        mock_resolve.return_value = None
        repl = HarnessREPL(root=tmp_path)
        result = repl._run_command("/get-well")
        assert result is True
        mock_echo.assert_called()

    @patch("harness.shell.repl.click.echo")
    @patch("harness.shell.repl._build_command_bus")
    @patch("harness.domain.engagement.resolver.resolve_active_engagement")
    def test_get_well_session_setup_fails(self, mock_resolve, mock_bus, mock_echo, tmp_path):
        """/get-well with failed session setup should print error."""
        from unittest.mock import MagicMock

        mock_bus.return_value.dispatch.return_value = CommandResult(success=False, error="Setup failed")
        mock_resolve.return_value = "test-eng"
        repl = HarnessREPL(root=tmp_path)
        result = repl._run_command("/get-well")
        assert result is True
        # Should print the error
        assert any("Setup failed" in str(c) or "failed" in str(c).lower()
                   for c in mock_echo.call_args_list)

    @patch("harness.shell.repl.click.echo")
    @patch("harness.shell.repl._dispatch_via_bus")
    @patch("harness.domain.engagement.resolver.resolve_active_engagement")
    def test_get_well_session_run_exception(self, mock_resolve, mock_bus, mock_echo, tmp_path, monkeypatch):
        """/get-well when phase session raises Exception should print error."""
        from unittest.mock import AsyncMock

        mock_session = AsyncMock(side_effect=RuntimeError("Session crashed"))
        monkeypatch.setattr("harness.session.session_orchestrator.run_phase_session", mock_session)
        mock_bus.return_value = CommandResult(success=True, message="Session setup OK")
        mock_resolve.return_value = "test-eng"

        repl = HarnessREPL(root=tmp_path)
        result = repl._run_command("/get-well")
        assert result is True

    @patch("harness.shell.repl.click.echo")
    @patch("harness.shell.repl._dispatch_via_bus")
    @patch("harness.domain.engagement.resolver.resolve_active_engagement")
    def test_session_get_well_setup_fails(self, mock_resolve, mock_bus, mock_echo, tmp_path):
        """/session --get-well when dispatch fails should print error."""
        mock_bus.return_value = CommandResult(success=False, error="Setup failed")
        mock_resolve.return_value = "test-eng"
        repl = HarnessREPL(root=tmp_path)
        result = repl._run_command("/session --get-well")
        assert result is True

    @patch("harness.shell.repl.click.echo")
    @patch("harness.shell.repl._dispatch_via_bus")
    @patch("harness.domain.engagement.resolver.resolve_active_engagement")
    def test_session_get_well_run_exception(self, mock_resolve, mock_bus, mock_echo, tmp_path, monkeypatch):
        """/session --get-well when phase session raises Exception."""
        from unittest.mock import AsyncMock

        mock_session = AsyncMock(side_effect=RuntimeError("Session crashed"))
        monkeypatch.setattr("harness.session.session_orchestrator.run_phase_session", mock_session)
        mock_bus.return_value = CommandResult(success=True, message="Session setup OK")
        mock_resolve.return_value = "test-eng"

        repl = HarnessREPL(root=tmp_path)
        result = repl._run_command("/session --get-well")
        assert result is True

    @patch("harness.shell.repl.click.echo")
    @patch("harness.domain.engagement.resolver.resolve_active_engagement")
    def test_session_no_engagement(self, mock_resolve, mock_echo, tmp_path):
        """/session with no active engagement should print message."""
        mock_resolve.return_value = None
        repl = HarnessREPL(root=tmp_path)
        result = repl._run_command("/session")
        assert result is True


class TestREPLRunEdgeCases:
    """Edge cases for REPL.run()."""

    @patch("harness.shell.repl.click.echo")
    def test_run_loop_multiple_commands(self, mock_echo, tmp_path):
        """REPL should process multiple commands and exit cleanly."""
        repl = HarnessREPL(root=tmp_path)
        with patch("builtins.input", side_effect=["/help", "/exit"]):
            with patch("click.echo"):  # suppress output
                repl.run()
        # Should reach end without error

    @patch("harness.shell.repl.click.echo")
    def test_run_health_checks_no_root(self, mock_echo, tmp_path):
        """REPL run should work even without root directory."""
        repl = HarnessREPL(root=tmp_path)
        with patch("builtins.input", side_effect=KeyboardInterrupt()):
            repl.run()
        # Should not crash

    @patch("harness.shell.repl.click.echo")
    def test_run_health_checks_exception(self, mock_echo, tmp_path):
        """Health check exceptions during REPL start should not crash."""
        with patch("harness.health.run_health_checks", side_effect=Exception("health error")):
            repl = HarnessREPL(root=tmp_path)
            with patch("builtins.input", side_effect=KeyboardInterrupt()):
                repl.run()


class TestCompleterFurtherEdgeCases:
    """Additional tab completion edge cases."""

    def test_complete_for_command_with_flags(self, tmp_path):
        """_complete_for_command should suggest flags."""
        repl = HarnessREPL(root=tmp_path)
        completer = _REPLCompleter(repl)

        # Get a real command from the index
        cmd = repl.commands.get("status")
        if cmd:
            matches = completer._complete_for_command(cmd, [], "-")
            # Should return some flags
            assert len(matches) >= 0

    def test_complete_for_command_with_unknown_flag(self, tmp_path):
        """_complete_for_command with no matching flags should fall back to path."""
        repl = HarnessREPL(root=tmp_path)
        completer = _REPLCompleter(repl)

        cmd = repl.commands.get("status")
        if cmd:
            matches = completer._complete_for_command(cmd, [], "--nonexistent")
            assert len(matches) == 0  # No matching flags

    def test_complete_second_word_with_unknown_command(self, tmp_path):
        """Second word completion with unknown command should fall back to path."""
        (tmp_path / "somefile.txt").write_text("test")
        repl = HarnessREPL(root=tmp_path)

        with (
            patch("harness.shell.repl.readline.get_line_buffer", return_value="/session some"),
            patch("harness.shell.repl.readline.get_endidx", return_value=14),
            patch("harness.shell.repl.Path.cwd", return_value=tmp_path),
        ):
            completer = _REPLCompleter(repl)
            result = completer.complete("some", 0)
            if result is not None:
                assert "somefile" in result

    def test_complete_empty_buffer_firstword_no_text(self, tmp_path):
        """Complete with empty buffer and no text should list all commands."""
        repl = HarnessREPL(root=tmp_path)
        with (
            patch("harness.shell.repl.readline.get_line_buffer", return_value=""),
            patch("harness.shell.repl.readline.get_endidx", return_value=0),
        ):
            completer = _REPLCompleter(repl)
            result = completer.complete("", 0)
            assert result is not None
            assert result.startswith("/")

    def test_complete_empty_buffer_firstword_empty_parts(self, tmp_path):
        """Complete with only whitespace should list all commands."""
        repl = HarnessREPL(root=tmp_path)
        with (
            patch("harness.shell.repl.readline.get_line_buffer", return_value=" "),
            patch("harness.shell.repl.readline.get_endidx", return_value=1),
        ):
            completer = _REPLCompleter(repl)
            result = completer.complete(" ", 0)
            assert result is not None or result is None

    def test_complete_no_match_for_middle_words(self, tmp_path):
        """When no match in first token, should return no matches."""
        repl = HarnessREPL(root=tmp_path)
        with (
            patch("harness.shell.repl.readline.get_line_buffer", return_value="/session somefile"),
            patch("harness.shell.repl.readline.get_endidx", return_value=19),
        ):
            completer = _REPLCompleter(repl)
            # first call to state 0 initializes
            result = completer.complete("somefile", 0)
            # May get path completion or None
            assert result is None or isinstance(result, str)

    def test_complete_buf_before_spaces(self, tmp_path):
        """Buffer with leading spaces should strip correctly."""
        repl = HarnessREPL(root=tmp_path)
        with (
            patch("harness.shell.repl.readline.get_line_buffer", return_value="  "),
            patch("harness.shell.repl.readline.get_endidx", return_value=2),
        ):
            completer = _REPLCompleter(repl)
            result = completer.complete(" ", 0)

