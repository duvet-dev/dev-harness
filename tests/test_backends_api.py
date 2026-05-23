"""Tests for harness.agents.backends.api_backend — API backend.

Tests ApiBackendConfig, prepare, run with mocked HTTP calls,
tool execution, streaming, and format conversion.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from harness.agents.backends.api_backend import (
    ApiBackend,
    ApiBackendConfig,
    MAX_TOOL_ROUNDS,
    _HttpResult,
)
from harness.agents.backends.base import (
    AbstractBackend,
    BackendResult,
    Invocation,
)
from harness.agents.backends.api_backend import _HttpResult
from harness.agents.context import ContextPacket, OutputContract


class TestApiBackendConfig:
    """Tests for ApiBackendConfig."""

    def test_default_config(self):
        config = ApiBackendConfig()
        assert config.default_model == "deepseek-v4-pro"
        assert config.timeout_seconds == 600
        assert config.max_retries == 3
        assert config.retry_delay_seconds == 2.0
        assert config.api_key_env == "DEEPSEEK_API_KEY"
        assert config.max_tool_rounds == 25

    def test_from_dict(self):
        config = ApiBackendConfig.from_dict({
            "default_model": "gpt-4",
            "timeout_seconds": "120",
            "max_retries": "1",
            "api_key_env": "OPENAI_API_KEY",
            "max_tool_rounds": "5",
        })
        assert config.default_model == "gpt-4"
        assert config.timeout_seconds == 120
        assert config.max_retries == 1
        assert config.api_key_env == "OPENAI_API_KEY"
        assert config.max_tool_rounds == 5

    def test_from_dict_partial(self):
        config = ApiBackendConfig.from_dict({"default_model": "gpt-4"})
        assert config.default_model == "gpt-4"
        assert config.max_retries == 3  # default preserved


class TestApiBackend:
    """Tests for ApiBackend."""

    def test_name(self):
        assert ApiBackend.name == "api"

    @pytest.mark.asyncio
    async def test_prepare_basic(self):
        """prepare() creates an Invocation from a ContextPacket."""
        backend = ApiBackend()
        packet = ContextPacket(
            engagement_id="test",
            phase_name="analysis",
            task_id="t1",
            spec_content="Analyse this code",
            architecture_rules=["follow SOLID"],
        )
        invocation = await backend.prepare(packet)

        assert invocation.command == "https://api.deepseek.com/chat/completions"
        assert invocation.model == "deepseek-v4-pro"
        assert invocation.input_packet == packet
        assert invocation.available_tools == []

        payload = json.loads(invocation.args[0])
        assert payload["model"] == "deepseek-v4-pro"
        assert len(payload["messages"]) == 2
        assert payload["messages"][1]["content"] == "Analyse this code"

    @pytest.mark.asyncio
    async def test_prepare_with_model_override(self):
        """Model from constraint_section overrides default."""
        backend = ApiBackend()
        packet = ContextPacket(
            engagement_id="test",
            phase_name="analysis",
            task_id="t1",
            spec_content="Analyse",
            constraint_section={"model": "gpt-4", "temperature": 0.5},
        )
        invocation = await backend.prepare(packet)
        payload = json.loads(invocation.args[0])
        assert payload["model"] == "gpt-4"
        assert payload["temperature"] == 0.5

    @pytest.mark.asyncio
    async def test_prepare_with_tools(self):
        """Tools from constraints are passed to invocation."""
        backend = ApiBackend()
        tools = [{
            "function": {
                "name": "repo_tool",
                "description": "File access",
                "parameters": {"type": "object"},
            }
        }]
        packet = ContextPacket(
            engagement_id="test",
            phase_name="analysis",
            task_id="t1",
            spec_content="Analyse",
            constraint_section={"available_tools": tools},
        )
        invocation = await backend.prepare(packet)
        assert invocation.available_tools == tools

    @pytest.mark.asyncio
    async def test_run_no_api_key(self):
        """run() returns failure when API key is not set."""
        backend = ApiBackend()
        # Ensure env var is not set
        with patch.dict("os.environ", {}, clear=True):
            packet = ContextPacket(
                engagement_id="test", phase_name="analysis",
                task_id="t1", spec_content="test",
            )
            invocation = await backend.prepare(packet)
            result = await backend.run(invocation)
            assert result.status == "failure"
            assert any("API key" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_run_successful(self):
        """run() returns success with response content."""
        backend = ApiBackend()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "Here is the analysis.",
                    }
                }
            ],
            "usage": {"total_tokens": 150},
        }

        with patch.dict("os.environ", {"DEEPSEEK_API_KEY": "sk-test"}):
            with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_response)):
                packet = ContextPacket(
                    engagement_id="test", phase_name="analysis",
                    task_id="t1", spec_content="Analyse this",
                )
                invocation = await backend.prepare(packet)
                result = await backend.run(invocation)
                assert result.status == "success"
                assert "_response" in result.artifacts
                assert "Here is the analysis" in result.artifacts["_response"]

    @pytest.mark.asyncio
    async def test_run_with_tool_calls(self):
        """run() handles tool call loop."""
        backend = ApiBackend()

        tool_registry = {"repo_tool": MagicMock()}
        tool_registry["repo_tool"].read.return_value = "file content"
        tool_registry["repo_tool"].write.return_value = MagicMock(relative_to=lambda r: "path")
        tool_registry["repo_tool"].repo_root = MagicMock()

        tool_spec = {
            "function": {
                "name": "repo_tool",
                "description": "File tool",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "operation": {"type": "string"},
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                    },
                    "required": ["operation", "path"],
                },
            }
        }

        # Mock _send_request to return tool call response then content
        first_data = MagicMock(spec=_HttpResult)
        first_data.status = "success"
        first_data.metadata = {
            "choices": [{
                "message": {
                    "content": None,
                    "tool_calls": [{
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "repo_tool",
                            "arguments": json.dumps({
                                "operation": "read", "path": "src/main.py",
                            }),
                        },
                    }],
                }
            }],
            "usage": {"total_tokens": 200},
        }
        first_data.errors = []
        second_data = MagicMock(spec=_HttpResult)
        second_data.status = "success"
        second_data.metadata = {
            "choices": [{"message": {"content": "Final analysis complete."}}],
            "usage": {"total_tokens": 250},
        }
        second_data.errors = []

        with patch.dict("os.environ", {"DEEPSEEK_API_KEY": "sk-test"}):
            with patch.object(backend, "_send_request",
                              side_effect=[first_data, second_data]):
                packet = ContextPacket(
                    engagement_id="test", phase_name="analysis",
                    task_id="t1", spec_content="Analyse this code with the repo tool",
                    constraint_section={
                        "available_tools": [tool_spec],
                    },
                )
                invocation = await backend.prepare(packet)
                invocation.tool_registry = tool_registry
                result = await backend.run(invocation)
                assert result.status == "success"
                assert "Final analysis complete" in result.artifacts["_response"]
                assert result.metrics.get("tool_calls", 0) >= 1

    @pytest.mark.asyncio
    async def test_run_http_error(self):
        """run() returns failure on HTTP error."""
        backend = ApiBackend()

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch.dict("os.environ", {"DEEPSEEK_API_KEY": "sk-test"}):
            with patch("httpx.AsyncClient.post",
                       new=AsyncMock(return_value=mock_response)):
                packet = ContextPacket(
                    engagement_id="test", phase_name="analysis",
                    task_id="t1", spec_content="Analyse",
                )
                invocation = await backend.prepare(packet)
                result = await backend.run(invocation)
                assert result.status == "failure"
                assert any("500" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_run_timeout(self):
        """run() returns timeout on httpx.TimeoutException."""
        import httpx
        backend = ApiBackend()

        with patch.dict("os.environ", {"DEEPSEEK_API_KEY": "sk-test"}):
            with patch("httpx.AsyncClient.post",
                       side_effect=httpx.TimeoutException("Request timed out")):
                packet = ContextPacket(
                    engagement_id="test", phase_name="analysis",
                    task_id="t1", spec_content="Analyse",
                )
                invocation = await backend.prepare(packet)
                result = await backend.run(invocation)
                # Should handle the exception gracefully
                assert result.status in ("failure", "timeout")


class TestToolConversion:
    """Tests for tool format converters."""

    def test_to_openai_tools(self):
        internal = [{
            "function": {
                "name": "repo_tool",
                "description": "File tool",
                "parameters": {"type": "object"},
            }
        }]
        result = ApiBackend._to_openai_tools(internal)
        assert len(result) == 1
        assert result[0]["type"] == "function"
        assert result[0]["function"]["name"] == "repo_tool"

    def test_to_anthropic_tools(self):
        internal = [{
            "function": {
                "name": "repo_tool",
                "description": "File tool",
                "parameters": {"type": "object"},
            }
        }]
        result = ApiBackend._to_anthropic_tools(internal)
        assert len(result) == 1
        assert result[0]["name"] == "repo_tool"
        assert "input_schema" in result[0]

    def test_to_google_tools(self):
        internal = [{
            "function": {
                "name": "repo_tool",
                "description": "File tool",
                "parameters": {"type": "object"},
            }
        }]
        result = ApiBackend._to_google_tools(internal)
        assert len(result) == 1
        assert "function_declarations" in result[0]

    def test_convert_tools_default_openai(self):
        backend = ApiBackend()
        internal = [{
            "function": {
                "name": "repo_tool",
                "description": "File tool",
                "parameters": {"type": "object"},
            }
        }]
        result = backend._convert_tools(internal, "deepseek")
        assert result[0]["type"] == "function"

    def test_convert_tools_anthropic(self):
        backend = ApiBackend()
        internal = [{
            "function": {
                "name": "repo_tool",
                "description": "File tool",
                "parameters": {"type": "object"},
            }
        }]
        result = backend._convert_tools(internal, "anthropic")
        assert result[0]["name"] == "repo_tool"

    def test_convert_tools_google(self):
        backend = ApiBackend()
        internal = [{
            "function": {
                "name": "repo_tool",
                "description": "File tool",
                "parameters": {"type": "object"},
            }
        }]
        result = backend._convert_tools(internal, "google")
        assert "function_declarations" in result[0]


class TestValidateConfig:
    """Tests for validate_config()."""

    def test_valid_config(self):
        backend = ApiBackend()
        errors = backend.validate_config({"timeout_seconds": 30, "max_retries": 2})
        assert errors == []

    def test_invalid_timeout(self):
        backend = ApiBackend()
        errors = backend.validate_config({"timeout_seconds": 5})
        assert any("timeout_seconds" in e for e in errors)

    def test_invalid_retries(self):
        backend = ApiBackend()
        errors = backend.validate_config({"max_retries": -1})
        assert any("max_retries" in e for e in errors)


class TestResolveEndpointAndModel:
    """Tests for _resolve_endpoint_and_model()."""

    def test_default_endpoint(self):
        invocation = Invocation(
            command="https://api.deepseek.com/chat/completions",
            model="deepseek-v4-pro",
        )
        url, model = ApiBackend._resolve_endpoint_and_model(invocation)
        assert url == "https://api.deepseek.com/chat/completions"
        assert model == "deepseek-v4-pro"

    def test_overridden_by_resolved_config(self):
        invocation = Invocation(
            command="https://api.deepseek.com/chat/completions",
            model="",  # model comes from resolved_config when invocation model is empty
            resolved_config={
                "base_url": "https://openai.com/v1",
                "model": "gpt-4",
            },
        )
        url, model = ApiBackend._resolve_endpoint_and_model(invocation)
        assert "openai.com" in url
        assert model == "gpt-4"

    def test_base_url_with_chat_completions(self):
        invocation = Invocation(
            command="https://api.deepseek.com/chat/completions",
            model="deepseek-v4-pro",
            resolved_config={
                "base_url": "https://openai.com/v1/chat/completions",
            },
        )
        url, _ = ApiBackend._resolve_endpoint_and_model(invocation)
        assert url == "https://openai.com/v1/chat/completions"
