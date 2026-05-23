"""Tests for pure logic functions extracted from session/loop.py.

These functions involve no IO, no async — pure string parsing, state
transitions, and formatting. Testing them directly validates the
business logic without mocking the interactive session REPL.
"""

from __future__ import annotations

import pytest

from harness.session.loop import (
    _extract_file_blocks,
    _parse_consult_flags,
    _init_phase_jump_counts,
    _check_phase_jump_limit,
    _format_jump_marker,
    _check_for_phase_jump_from_content,
    MAX_PHASE_JUMPS_PER_PHASE,
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
