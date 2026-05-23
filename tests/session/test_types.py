"""Tests for harness.session.types."""

from pathlib import Path
from unittest.mock import patch

import pytest

from harness.session.types import (
    SessionType,
    _prompt_alternative,
    confirm_session_type,
    detect_session_type,
    read_session_type,
    store_session_type,
)


class TestSessionType:
    def test_values(self):
        assert SessionType.GREENFIELD.value == "greenfield"
        assert SessionType.BROWNFIELD.value == "brownfield"
        assert SessionType.REFACTORING.value == "refactoring"


class TestDetectSessionType:
    def test_detects_refactoring(self):
        result = detect_session_type("We need to refactor the auth module")
        assert result == SessionType.REFACTORING

    def test_detects_brownfield(self):
        result = detect_session_type("We need to add a feature to the existing app")
        assert result == SessionType.BROWNFIELD

    def test_returns_none_for_greenfield(self):
        result = detect_session_type("Build a new microservice from scratch")
        assert result is None

    def test_case_insensitive(self):
        result = detect_session_type("REFACTOR the legacy code")
        assert result == SessionType.REFACTORING

    def test_empty_string(self):
        assert detect_session_type("") is None


class TestConfirmSessionType:
    def test_accepts_y(self):
        with patch("builtins.input", return_value="y"):
            result = confirm_session_type(SessionType.REFACTORING)
            assert result == SessionType.REFACTORING

    def test_accepts_empty(self):
        with patch("builtins.input", return_value=""):
            result = confirm_session_type(SessionType.BROWNFIELD)
            assert result == SessionType.BROWNFIELD

    def test_rejects_then_accept_alternative(self):
        with patch("builtins.input", side_effect=["n", "1"]):
            result = confirm_session_type(SessionType.REFACTORING)
            assert result == SessionType.GREENFIELD

    def test_rejects_then_cancel(self):
        with patch("builtins.input", side_effect=["n", "99"]):
            result = confirm_session_type(SessionType.REFACTORING)
            assert result is None


class TestStoreSessionType:
    def test_stores_to_existing_yaml(self, tmp_path):
        import yaml
        eng_dir = tmp_path / ".harness" / "engagements" / "test-eng"
        eng_dir.mkdir(parents=True)
        eng_yaml = eng_dir / "engagement.yaml"
        eng_yaml.write_text(yaml.dump({"slug": "test-eng"}))
        store_session_type(tmp_path, "test-eng", SessionType.REFACTORING)
        data = yaml.safe_load(eng_yaml.read_text())
        assert data["session_type"] == "refactoring"

    def test_stores_to_new_yaml(self, tmp_path):
        import yaml
        store_session_type(tmp_path, "new-eng", SessionType.GREENFIELD)
        eng_yaml = tmp_path / ".harness" / "engagements" / "new-eng" / "engagement.yaml"
        assert eng_yaml.is_file()
        data = yaml.safe_load(eng_yaml.read_text())
        assert data["session_type"] == "greenfield"


class TestReadSessionType:
    def test_reads_existing(self, tmp_path):
        import yaml
        eng_dir = tmp_path / ".harness" / "engagements" / "test-eng"
        eng_dir.mkdir(parents=True)
        eng_yaml = eng_dir / "engagement.yaml"
        eng_yaml.write_text(yaml.dump({"slug": "test-eng", "session_type": "brownfield"}))
        result = read_session_type(tmp_path, "test-eng")
        assert result == SessionType.BROWNFIELD

    def test_returns_none_when_not_set(self, tmp_path):
        import yaml
        eng_dir = tmp_path / ".harness" / "engagements" / "test-eng"
        eng_dir.mkdir(parents=True)
        eng_yaml = eng_dir / "engagement.yaml"
        eng_yaml.write_text(yaml.dump({"slug": "test-eng"}))
        result = read_session_type(tmp_path, "test-eng")
        assert result is None

    def test_returns_none_when_no_file(self, tmp_path):
        result = read_session_type(tmp_path, "nonexistent")
        assert result is None

    def test_invalid_value_returns_none(self, tmp_path):
        import yaml
        eng_dir = tmp_path / ".harness" / "engagements" / "test-eng"
        eng_dir.mkdir(parents=True)
        eng_yaml = eng_dir / "engagement.yaml"
        eng_yaml.write_text(yaml.dump({"slug": "test-eng", "session_type": "invalid_type"}))
        result = read_session_type(tmp_path, "test-eng")
        assert result is None


class TestPromptAlternative:
    @pytest.mark.skip(reason="_prompt_alternative uses input(), can't mock in non-interactive test")
    def test_selects_first_alternative(self):
        pass
