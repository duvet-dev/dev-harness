"""Tests for skills errors module."""

from __future__ import annotations

import pytest


class TestSkillErrors:
    """Tests for harness.skills.errors module."""

    def test_skill_execution_error(self):
        from harness.skills.errors import SkillExecutionError
        err = SkillExecutionError("test error")
        assert str(err) == "test error"
        assert isinstance(err, Exception)

    def test_all_exports(self):
        import harness.skills.errors
        assert "SkillExecutionError" in harness.skills.errors.__all__
        assert "UnknownSkillError" in harness.skills.errors.__all__
        assert "WebSearchUnavailableError" in harness.skills.errors.__all__

    def test_unknown_skill_error(self):
        from harness.errors import UnknownSkillError
        err = UnknownSkillError("unknown skill")
        assert str(err) == "unknown skill"
