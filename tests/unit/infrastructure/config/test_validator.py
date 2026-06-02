"""Tests for ``harness.infrastructure.config.validator``."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from harness.infrastructure.config.validator import ConfigValidator


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_yaml_reader():
    reader = MagicMock()
    return reader


@pytest.fixture
def mock_env_provider():
    provider = MagicMock()
    # Default: no env vars set
    provider.get.return_value = None
    return provider


@pytest.fixture
def validator(mock_yaml_reader, mock_env_provider):
    return ConfigValidator(mock_yaml_reader, mock_env_provider)


# ── check_providers_yaml ────────────────────────────────────────────────────


class TestCheckProvidersYaml:
    """Verify providers.yaml check behavior."""

    def test_missing_providers_yaml(self, validator, tmp_path):
        result = validator.check_providers_yaml(tmp_path)
        assert result.name == "providers-yaml"
        assert result.status == "fail"
        assert result.severity == "CRITICAL"
        assert "not found" in result.message

    def test_invalid_yaml(self, validator, mock_yaml_reader, tmp_path):
        self._create_providers_yaml(tmp_path, "invalid: [")
        mock_yaml_reader.read.side_effect = ValueError("Invalid YAML")
        result = validator.check_providers_yaml(tmp_path)
        assert result.status == "fail"
        assert "not valid YAML" in result.message

    def test_no_providers_key(self, validator, mock_yaml_reader, tmp_path):
        self._create_providers_yaml(tmp_path, "key: value")
        mock_yaml_reader.read.return_value = {"key": "value"}
        result = validator.check_providers_yaml(tmp_path)
        assert result.status == "fail"
        assert "no providers" in result.message

    def test_empty_providers(self, validator, mock_yaml_reader, tmp_path):
        self._create_providers_yaml(tmp_path, "providers: {}\n")
        mock_yaml_reader.read.return_value = {"providers": {}}
        result = validator.check_providers_yaml(tmp_path)
        assert result.status == "fail"

    def test_valid_providers(self, validator, mock_yaml_reader, tmp_path):
        self._create_providers_yaml(tmp_path, "providers:\n  openai:\n    api_key: test\n")
        mock_yaml_reader.read.return_value = {
            "providers": {"openai": {"api_key": "test"}},
        }
        result = validator.check_providers_yaml(tmp_path)
        assert result.status == "pass"
        assert "openai" in result.message

    def test_multiple_providers(self, validator, mock_yaml_reader, tmp_path):
        self._create_providers_yaml(
            tmp_path,
            "providers:\n  openai:\n    api_key: k1\n  anthropic:\n    api_key: k2\n",
        )
        mock_yaml_reader.read.return_value = {
            "providers": {"openai": {"api_key": "k1"}, "anthropic": {"api_key": "k2"}},
        }
        result = validator.check_providers_yaml(tmp_path)
        assert result.status == "pass"
        assert "openai" in result.message
        assert "anthropic" in result.message
        assert "2" in result.message

    @staticmethod
    def _create_providers_yaml(root: Path, content: str) -> None:
        harness_dir = root / ".harness"
        harness_dir.mkdir(parents=True, exist_ok=True)
        (harness_dir / "providers.yaml").write_text(content)


# ── check_api_keys ──────────────────────────────────────────────────────────


class TestCheckApiKeys:
    """Verify API key check behavior."""

    def test_missing_providers_yaml(self, validator, tmp_path):
        """No providers.yaml means we warn but don't fail."""
        result = validator.check_api_keys(tmp_path)
        assert result.name == "api-keys"
        assert result.status == "warn"
        assert "skipping" in result.message

    def test_invalid_yaml(self, validator, mock_yaml_reader, tmp_path):
        self._create_providers_yaml(tmp_path, "invalid: [")
        mock_yaml_reader.read.side_effect = ValueError("bad yaml")
        result = validator.check_api_keys(tmp_path)
        assert result.status == "warn"
        assert "skipping" in result.message

    def test_no_providers_in_yaml(self, validator, mock_yaml_reader, tmp_path):
        self._create_providers_yaml(tmp_path, "other: data\n")
        mock_yaml_reader.read.return_value = {"other": "data"}
        result = validator.check_api_keys(tmp_path)
        assert result.status == "pass"

    def test_all_keys_resolved(self, validator, mock_yaml_reader, mock_env_provider, tmp_path):
        self._create_providers_yaml(tmp_path, "providers:\n  openai:\n    api_key: ${OPENAI_KEY}\n")
        mock_yaml_reader.read.return_value = {
            "providers": {"openai": {"api_key": "${OPENAI_KEY}"}},
        }
        mock_env_provider.get.return_value = "sk-xxx"
        result = validator.check_api_keys(tmp_path)
        assert result.status == "pass"
        assert "1" in result.message

    def test_missing_keys(self, validator, mock_yaml_reader, mock_env_provider, tmp_path):
        self._create_providers_yaml(
            tmp_path,
            "providers:\n  openai:\n    api_key: ${OPENAI_KEY}\n  anthropic:\n    api_key: ${ANTHROPIC_KEY}\n",
        )
        mock_yaml_reader.read.return_value = {
            "providers": {
                "openai": {"api_key": "${OPENAI_KEY}"},
                "anthropic": {"api_key": "${ANTHROPIC_KEY}"},
            },
        }
        mock_env_provider.get.return_value = None  # both missing
        result = validator.check_api_keys(tmp_path)
        assert result.status == "fail"
        assert "OPENAI_KEY" in result.message
        assert "ANTHROPIC_KEY" in result.message
        assert result.severity == "CRITICAL"

    def test_mixed_resolved_and_missing(self, validator, mock_yaml_reader, mock_env_provider, tmp_path):
        self._create_providers_yaml(
            tmp_path,
            "providers:\n  openai:\n    api_key: ${OPENAI_KEY}\n  anthropic:\n    api_key: ${ANTHROPIC_KEY}\n",
        )
        mock_yaml_reader.read.return_value = {
            "providers": {
                "openai": {"api_key": "${OPENAI_KEY}"},
                "anthropic": {"api_key": "${ANTHROPIC_KEY}"},
            },
        }

        def env_get(name):
            return "sk-xxx" if name == "OPENAI_KEY" else None

        mock_env_provider.get.side_effect = env_get
        result = validator.check_api_keys(tmp_path)
        assert result.status == "fail"
        assert "ANTHROPIC_KEY" in result.message
        assert "OPENAI_KEY" not in result.message

    def test_no_var_refs_in_api_key(self, validator, mock_yaml_reader, mock_env_provider, tmp_path):
        self._create_providers_yaml(
            tmp_path,
            "providers:\n  openai:\n    api_key: literal-key\n",
        )
        mock_yaml_reader.read.return_value = {
            "providers": {"openai": {"api_key": "literal-key"}},
        }
        result = validator.check_api_keys(tmp_path)
        assert result.status == "pass"
        assert "0" in result.message

    @staticmethod
    def _create_providers_yaml(root: Path, content: str) -> None:
        harness_dir = root / ".harness"
        harness_dir.mkdir(parents=True, exist_ok=True)
        (harness_dir / "providers.yaml").write_text(content)
