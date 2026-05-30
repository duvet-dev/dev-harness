"""Tests for pure logic functions extracted from session/loop.py.

These functions involve no IO, no async — pure string parsing, state
transitions, and formatting. Testing them directly validates the
business logic without mocking the interactive session REPL.
"""

from __future__ import annotations

import pytest

from harness.session.helpers import (
    _extract_file_blocks,
    _parse_consult_flags,
    _init_phase_jump_counts,
    _check_phase_jump_limit,
    _format_jump_marker,
    _check_for_phase_jump_from_content,
    MAX_PHASE_JUMPS_PER_PHASE,
    DOMAIN_LANGUAGE_PREAMBLE,
)


# ═══════════════════════════════════════════════════════════════════════════════
# _extract_file_blocks
# ═══════════════════════════════════════════════════════════════════════════════


class TestExtractFileBlocks:
    """Tests for _extract_file_blocks() — pure string parsing."""

    def test_empty_text(self):
        assert _extract_file_blocks("") == {}

    def test_file_heading_block(self):
        text = "## File: src/main.py\nprint('hello')\n"
        result = _extract_file_blocks(text)
        assert "src/main.py" in result
        assert "print('hello')" in result["src/main.py"]

    def test_multiple_file_blocks(self):
        text = (
            "## File: src/main.py\nprint('hello')\n\n"
            "## File: src/utils.py\ndef util(): pass\n"
        )
        result = _extract_file_blocks(text)
        assert "src/main.py" in result
        assert "src/utils.py" in result
        assert "print('hello')" in result["src/main.py"]
        assert "def util(): pass" in result["src/utils.py"]

    def test_annotated_code_block(self):
        text = "```python\n// src/main.py\nprint('hello')\n```\n"
        result = _extract_file_blocks(text)
        assert "src/main.py" in result
        assert "print('hello')" in result["src/main.py"]

    def test_annotated_code_block_with_hash(self):
        text = "```\n# src/main.py\nprint('hello')\n```\n"
        result = _extract_file_blocks(text)
        assert "src/main.py" in result

    def test_no_blocks(self):
        text = "Just some regular text without any file blocks."
        result = _extract_file_blocks(text)
        assert result == {}

    def test_code_block_without_path_annotation(self):
        text = "```python\nprint('no path')\n```\n"
        result = _extract_file_blocks(text)
        assert result == {}

    def test_file_heading_captures_block_content(self):
        """File heading captures content until end of text."""
        text = (
            "## File: src/main.py\nprint('hello')\n"
        )
        result = _extract_file_blocks(text)
        assert "src/main.py" in result
        assert "print('hello')" in result["src/main.py"]


# ═══════════════════════════════════════════════════════════════════════════════
# _parse_consult_flags
# ═══════════════════════════════════════════════════════════════════════════════


class TestParseConsultFlags:
    """Tests for _parse_consult_flags() — pure flag parsing."""

    def test_no_flags(self):
        result = _parse_consult_flags("check this design")
        assert result["question"] == "check this design"
        assert result["fleet_filter"] is None
        assert result["mode"] is None

    def test_fleet_flag(self):
        result = _parse_consult_flags("--fleet architecture check this")
        assert result["question"] == "check this"
        assert result["fleet_filter"] == "architecture"

    def test_mode_flag(self):
        result = _parse_consult_flags("--mode blocking check this")
        assert result["mode"] == "blocking"
        assert result["question"] == "check this"

    def test_both_flags(self):
        result = _parse_consult_flags("--fleet infra --mode advisory check the database")
        assert result["fleet_filter"] == "infra"
        assert result["mode"] == "advisory"
        assert result["question"] == "check the database"

    def test_flags_without_values(self):
        result = _parse_consult_flags("--fleet")
        assert result["fleet_filter"] is None
        assert result["question"] == "--fleet"

    def test_empty_string(self):
        result = _parse_consult_flags("")
        assert result["question"] == ""
        assert result["fleet_filter"] is None
        assert result["mode"] is None

    def test_flag_at_end(self):
        result = _parse_consult_flags("review this --mode blocking")
        assert result["mode"] == "blocking"
        assert result["question"] == "review this"


# ═══════════════════════════════════════════════════════════════════════════════
# _init_phase_jump_counts / _check_phase_jump_limit
# ═══════════════════════════════════════════════════════════════════════════════


class TestPhaseJumpLimits:
    """Tests for phase jump counter logic."""

    def test_init_returns_empty(self):
        counts = _init_phase_jump_counts()
        assert counts == {}

    def test_first_jump_allowed(self):
        counts = _init_phase_jump_counts()
        assert _check_phase_jump_limit(counts, "build", "requirements") is True
        assert counts.get("build→requirements") == 1

    def test_jump_increments_counter(self):
        counts = _init_phase_jump_counts()
        _check_phase_jump_limit(counts, "a", "b")
        _check_phase_jump_limit(counts, "a", "b")
        assert counts["a→b"] == 2

    def test_jump_limit_exceeded(self):
        counts = _init_phase_jump_counts()
        for _ in range(MAX_PHASE_JUMPS_PER_PHASE):
            assert _check_phase_jump_limit(counts, "x", "y") is True
        # One more should fail
        assert _check_phase_jump_limit(counts, "x", "y") is False

    def test_different_jumps_independent(self):
        counts = _init_phase_jump_counts()
        for _ in range(MAX_PHASE_JUMPS_PER_PHASE):
            _check_phase_jump_limit(counts, "build", "design")
        # Different source→target should still work
        assert _check_phase_jump_limit(counts, "build", "test") is True
        # Same pair should be blocked
        assert _check_phase_jump_limit(counts, "build", "design") is False


# ═══════════════════════════════════════════════════════════════════════════════
# _format_jump_marker
# ═══════════════════════════════════════════════════════════════════════════════


class TestFormatJumpMarker:
    """Tests for _format_jump_marker() — pure formatting."""

    def test_no_jump_returns_empty(self):
        from harness.agents.cycle import CycleResult
        result = CycleResult(status="complete")
        assert _format_jump_marker(result) == ""

    def test_with_jump_target(self):
        from harness.agents.cycle import CycleResult
        result = CycleResult(
            status="phase_jump:design",
            summary="Architecture review needed",
        )
        marker = _format_jump_marker(result)
        assert "design" in marker
        assert "Architecture review needed" in marker

    def test_without_summary(self):
        from harness.agents.cycle import CycleResult
        result = CycleResult(status="phase_jump:test")
        marker = _format_jump_marker(result)
        assert "test" in marker
        assert "No reason given" in marker


# ═══════════════════════════════════════════════════════════════════════════════
# _check_for_phase_jump_from_content
# ═══════════════════════════════════════════════════════════════════════════════


class TestCheckForPhaseJumpFromContent:
    """Tests for _check_for_phase_jump_from_content() — pure regex matching."""

    def test_no_marker(self):
        assert _check_for_phase_jump_from_content("Some regular output") is None

    def test_phase_jump_marker(self):
        result = _check_for_phase_jump_from_content("PHASE_JUMP:design")
        assert result == "design"

    def test_phase_jump_with_whitespace(self):
        result = _check_for_phase_jump_from_content("PHASE_JUMP:  test")
        assert result == "test"

    def test_phase_jump_in_context(self):
        result = _check_for_phase_jump_from_content(
            "We need to go back.\nPHASE_JUMP:requirements\n"
        )
        assert result == "requirements"

    def test_empty_content(self):
        assert _check_for_phase_jump_from_content("") is None

    def test_none_content(self):
        assert _check_for_phase_jump_from_content(None) is None

    def test_multiple_markers_returns_first(self):
        result = _check_for_phase_jump_from_content(
            "PHASE_JUMP:design\nPHASE_JUMP:implement"
        )
        assert result == "design"


# ═══════════════════════════════════════════════════════════════════════════════
# _build_system_prompt (effects injected as data parameters)
# ═══════════════════════════════════════════════════════════════════════════════


class TestBuildSystemPrompt:
    """Tests for _build_system_prompt() — prompt construction logic.

    All IO dependencies (engagement context, fleet data, patterns) are
    injected as pre-loaded strings. This tests the pure assembly logic
    without needing a real filesystem.
    """

    def make_phase(self, prompt: str = "You are a test agent.", fleets=None):
        phase = {"name": "test", "prompt": prompt, "fleets": fleets or []}
        return phase

    def test_basic_prompt_with_phase(self):
        from harness.session.helpers import _build_system_prompt
        phase = self.make_phase()
        result = _build_system_prompt(phase)
        assert "You are a test agent." in result
        assert DOMAIN_LANGUAGE_PREAMBLE in result

    def test_with_engagement_context(self):
        from harness.session.helpers import _build_system_prompt
        phase = self.make_phase()
        result = _build_system_prompt(
            phase,
            engagement_context="src/main.py (3KB, modified)\nsrc/utils.py (1KB)",
        )
        assert "CURRENT ENGAGEMENT FILES" in result
        assert "src/main.py" in result

    def test_with_prior_artifacts(self):
        from harness.session.helpers import _build_system_prompt
        phase = self.make_phase()
        result = _build_system_prompt(
            phase,
            context="Design doc:\n- Component A\n- Component B",
        )
        assert "PRIOR ARTIFACTS" in result
        assert "Component A" in result

    def test_with_conversation_history(self):
        from harness.session.helpers import _build_system_prompt
        phase = self.make_phase()
        result = _build_system_prompt(
            phase,
            conversation="User asked about the architecture.",
        )
        assert "CONVERSATION HISTORY" in result
        assert "architecture" in result

    def test_with_fleet_section(self):
        from harness.session.helpers import _build_system_prompt
        phase = self.make_phase(fleets=["architecture"])
        result = _build_system_prompt(
            phase,
            fleet_section="## Architecture Fleet\nFollow the onion architecture.",
        )
        assert "Architecture Fleet" in result
        assert "onion architecture" in result

    def test_with_patterns_section(self):
        from harness.session.helpers import _build_system_prompt
        phase = self.make_phase(fleets=["testing"])
        result = _build_system_prompt(
            phase,
            patterns_section="## Testing Patterns\nArrange-Act-Assert",
        )
        assert "Testing Patterns" in result
        assert "Arrange-Act-Assert" in result

    def test_injection_order(self):
        """Verify the parts appear in the correct order."""
        from harness.session.helpers import _build_system_prompt
        phase = self.make_phase()
        result = _build_system_prompt(
            phase,
            engagement_context="[ENGAGEMENT_CONTEXT]",
            fleet_section="[FLEET]",
            patterns_section="[PATTERNS]",
            context="[ARTIFACTS]",
            conversation="[CONVERSATION]",
        )

        # Find positions of each section
        pos_preamble = result.find(DOMAIN_LANGUAGE_PREAMBLE)
        pos_context = result.find("[ENGAGEMENT_CONTEXT]")
        pos_prompt = result.find("You are a test agent.")
        pos_fleet = result.find("[FLEET]")
        pos_patterns = result.find("[PATTERNS]")
        pos_artifacts = result.find("[ARTIFACTS]")
        pos_conversation = result.find("[CONVERSATION]")

        assert pos_preamble < pos_context, "preamble before context"
        assert pos_context < pos_prompt, "context before phase prompt"
        assert pos_prompt < pos_fleet or pos_fleet == -1, "prompt before fleet"
        assert pos_fleet < pos_patterns or pos_patterns == -1 or pos_fleet == -1, "fleet before patterns"
        assert pos_artifacts > pos_patterns, "artifacts after everything"
        assert pos_conversation > pos_artifacts, "conversation last"

    def test_empty_engagement_context_omitted(self):
        """Empty/injected context should not add the current-files section."""
        from harness.session.helpers import _build_system_prompt
        phase = self.make_phase()
        result = _build_system_prompt(phase, engagement_context="")
        assert "CURRENT ENGAGEMENT FILES" not in result

    def test_without_any_injected_data(self):
        """Without injecting anything, the function should not attempt IO."""
        from harness.session.helpers import _build_system_prompt
        phase = self.make_phase()
        result = _build_system_prompt(phase)
        assert "You are a test agent." in result
        assert "CURRENT ENGAGEMENT FILES" not in result
        assert "PRIOR ARTIFACTS" not in result


# ═══════════════════════════════════════════════════════════════════════════════
# Coverage gap: _check_and_handle_phase_jump (limit-exceeded branch)
# ═══════════════════════════════════════════════════════════════════════════════


class TestCheckAndHandlePhaseJump:
    """Tests for _check_and_handle_phase_jump() — pure orchestration."""

    def test_no_marker_returns_none(self):
        from harness.session.helpers import _check_and_handle_phase_jump
        result = _check_and_handle_phase_jump("no marker here", "build", {})
        assert result is None

    def test_jump_allowed(self):
        from harness.session.helpers import _check_and_handle_phase_jump
        result = _check_and_handle_phase_jump("PHASE_JUMP:requirements", "build", {})
        assert result == "requirements"

    def test_jump_exceeds_limit_returns_none(self):
        """The limit-exceeded branch was uncovered lines 1000-1006."""
        from harness.session.helpers import (
            _check_and_handle_phase_jump,
            MAX_PHASE_JUMPS_PER_PHASE,
        )
        counts = {}
        # Exhaust the limit
        for _ in range(MAX_PHASE_JUMPS_PER_PHASE):
            _check_and_handle_phase_jump("PHASE_JUMP:design", "build", counts)
        # One more should be blocked
        result = _check_and_handle_phase_jump("PHASE_JUMP:design", "build", counts)
        assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# Coverage gap: _format_consult_result with error
# ═══════════════════════════════════════════════════════════════════════════════


class TestFormatConsultResult:
    """Tests for _format_consult_result() — pure formatting."""

    def test_format_error_result(self):
        """Error branch at line 871 needs a result with an error message."""
        from harness.session.helpers import _format_consult_result
        from harness.agents.consultation import ConsultationResult
        result = _format_consult_result(
            ConsultationResult(
                question="test",
                fleet_name="test",
                status="error",
                error="Something went wrong",
            )
        )
        assert "Something went wrong" in result


# ═══════════════════════════════════════════════════════════════════════════════
# Coverage gap: _apply_file_blocks path escape branch
# ═══════════════════════════════════════════════════════════════════════════════


class TestApplyFileBlocks:
    """Tests for _apply_file_blocks() — error handling branches."""

    def test_path_escape_returns_error(self, tmp_path):
        """Path escape should produce an 'error:' status (lines 465-468)."""
        from harness.session.helpers import _apply_file_blocks
        # A path outside the root should be flagged
        text = "## File: ../../etc/passwd\nroot:x:0:0\n"
        results = _apply_file_blocks(tmp_path, text)
        assert any("error:" in status for _, status in results)

    def test_valid_path_creates_file(self, tmp_path):
        from harness.session.helpers import _apply_file_blocks
        text = "## File: src/output.py\nprint('hello')\n"
        results = _apply_file_blocks(tmp_path, text)
        assert len(results) >= 1
        assert any(status == "created" for _, status in results)
        assert (tmp_path / "src/output.py").exists()

    def test_overwrite_existing_file(self, tmp_path):
        from harness.session.helpers import _apply_file_blocks
        existing = tmp_path / "existing.py"
        existing.parent.mkdir(parents=True, exist_ok=True)
        existing.write_text("old content")
        text = "## File: existing.py\nnew content\n"
        results = _apply_file_blocks(tmp_path, text)
        assert any(status == "overwritten" for _, status in results)
        assert existing.read_text() == "new content"
