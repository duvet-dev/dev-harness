"""Tests for harness.agents.backends.formatters — provider message formats."""

from __future__ import annotations

import pytest

from harness.agents.backends.formatters import (
    InternalMessage,
    ParsedResponse,
    OpenAIFormatter,
    DeepSeekFormatter,
    AnthropicFormatter,
    GoogleFormatter,
    get_formatter,
)


class TestInternalMessage:
    """Tests for the InternalMessage dataclass."""

    def test_user_message(self):
        msg = InternalMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_assistant_tool_call(self):
        msg = InternalMessage(
            role="assistant",
            content=None,
            tool_calls=[{"id": "call_1", "function": {"name": "read"}}],
        )
        assert msg.role == "assistant"
        assert msg.content is None
        assert len(msg.tool_calls) == 1


class TestGetFormatter:
    """Tests for get_formatter() registry."""

    def test_openai(self):
        f = get_formatter("openai-compatible")
        assert isinstance(f, OpenAIFormatter)

    def test_deepseek(self):
        f = get_formatter("deepseek")
        assert isinstance(f, DeepSeekFormatter)

    def test_anthropic(self):
        f = get_formatter("anthropic")
        assert isinstance(f, AnthropicFormatter)

    def test_google(self):
        f = get_formatter("google")
        assert isinstance(f, GoogleFormatter)

    def test_gemini(self):
        f = get_formatter("gemini")
        assert isinstance(f, GoogleFormatter)

    def test_claude_fallback(self):
        f = get_formatter("claude-3")
        assert isinstance(f, AnthropicFormatter)

    def test_deepseek_v4_fallback(self):
        f = get_formatter("deepseek-v4-pro")
        assert isinstance(f, DeepSeekFormatter)

    def test_unknown_falls_to_openai(self):
        f = get_formatter("unknown-provider")
        assert isinstance(f, OpenAIFormatter)


# ═══════════════════════════════════════════════════════════════════════════════
# OpenAIFormatter
# ═══════════════════════════════════════════════════════════════════════════════


class TestOpenAIFormatter:
    def make_formatter(self) -> OpenAIFormatter:
        return OpenAIFormatter()

    def test_format_system_user(self):
        msgs = [
            InternalMessage(role="system", content="Be helpful."),
            InternalMessage(role="user", content="Hello"),
        ]
        result = self.make_formatter().format_messages(msgs)
        assert result[0] == {"role": "system", "content": "Be helpful."}
        assert result[1] == {"role": "user", "content": "Hello"}

    def test_format_assistant_with_tool_calls(self):
        msgs = [
            InternalMessage(
                role="assistant",
                content=None,
                tool_calls=[{"id": "call_1", "function": {"name": "read"}}],
            ),
        ]
        result = self.make_formatter().format_messages(msgs)
        assert result[0]["role"] == "assistant"
        assert result[0]["content"] is None
        assert "tool_calls" in result[0]

    def test_format_tool_result(self):
        msgs = [
            InternalMessage(
                role="tool",
                content='{"result": "ok"}',
                tool_call_id="call_1",
            ),
        ]
        result = self.make_formatter().format_messages(msgs)
        assert result[0]["role"] == "tool"
        assert result[0]["tool_call_id"] == "call_1"

    def test_parse_response_simple(self):
        data = {
            "choices": [{
                "message": {"content": "Hello!"},
                "finish_reason": "stop",
            }],
        }
        parsed = self.make_formatter().parse_response(data)
        assert parsed.assistant_message.content == "Hello!"
        assert parsed.finish_reason == "stop"

    def test_parse_response_with_tool_calls(self):
        data = {
            "choices": [{
                "message": {
                    "content": None,
                    "tool_calls": [{
                        "id": "call_1",
                        "function": {"name": "read"},
                    }],
                },
                "finish_reason": "tool_calls",
            }],
        }
        parsed = self.make_formatter().parse_response(data)
        assert parsed.assistant_message.content is None
        assert len(parsed.assistant_message.tool_calls) == 1
        assert parsed.finish_reason == "tool_calls"

    def test_parse_empty_choices(self):
        parsed = self.make_formatter().parse_response({})
        assert parsed.assistant_message.content == ""
        assert parsed.finish_reason == "error"

    def test_openai_does_not_preserve_reasoning(self):
        msg = InternalMessage(
            role="assistant",
            content="Let me check.",
            reasoning_content="I should read the file first.",
        )
        result = self.make_formatter().format_messages([msg])
        assert "reasoning_content" not in result[0]


# ═══════════════════════════════════════════════════════════════════════════════
# DeepSeekFormatter
# ═══════════════════════════════════════════════════════════════════════════════


class TestDeepSeekFormatter:
    def make_formatter(self) -> DeepSeekFormatter:
        return DeepSeekFormatter()

    def test_preserves_reasoning_content(self):
        """DeepSeek must preserve reasoning_content for thinking mode."""
        msg = InternalMessage(
            role="assistant",
            content="The file contains:\n...",
            reasoning_content="Let me check the imports first...",
        )
        result = self.make_formatter().format_messages([msg])
        assert result[0]["reasoning_content"] == (
            "Let me check the imports first..."
        )

    def test_parse_extracts_reasoning(self):
        data = {
            "choices": [{
                "message": {
                    "content": "Result",
                    "reasoning_content": "I'm thinking...",
                },
                "finish_reason": "stop",
            }],
        }
        parsed = self.make_formatter().parse_response(data)
        assert parsed.assistant_message.reasoning_content == "I'm thinking..."
        assert parsed.assistant_message.content == "Result"

    def test_no_reasoning_when_not_present(self):
        msg = InternalMessage(
            role="assistant",
            content="Just a result.",
        )
        result = self.make_formatter().format_messages([msg])
        assert "reasoning_content" not in result[0]

    def test_format_tool_message_without_reasoning(self):
        """Tool result messages don't have reasoning_content."""
        msgs = [
            InternalMessage(
                role="assistant",
                content=None,
                tool_calls=[{"id": "c1", "function": {"name": "read", "arguments": "{}"}}],
                reasoning_content="Need to check files...",
            ),
            InternalMessage(
                role="tool",
                content='{"content": "file data"}',
                tool_call_id="c1",
            ),
        ]
        result = self.make_formatter().format_messages(msgs)
        assert result[0]["reasoning_content"] == "Need to check files..."
        assert "reasoning_content" not in result[1]


# ═══════════════════════════════════════════════════════════════════════════════
# AnthropicFormatter
# ═══════════════════════════════════════════════════════════════════════════════


class TestAnthropicFormatter:
    def make_formatter(self) -> AnthropicFormatter:
        return AnthropicFormatter()

    def test_format_user_message(self):
        msgs = [InternalMessage(role="user", content="Hello")]
        result = self.make_formatter().format_messages(msgs)
        assert result[0] == {"role": "user", "content": "Hello"}

    def test_format_assistant_with_tool_calls(self):
        msgs = [InternalMessage(
            role="assistant",
            content="Let me check.",
            tool_calls=[{
                "id": "toolu_1",
                "function": {"name": "read", "arguments": '{"path": "x"}'},
            }],
        )]
        result = self.make_formatter().format_messages(msgs)
        content = result[0]["content"]
        assert len(content) == 2
        assert content[0]["type"] == "text"
        assert content[1]["type"] == "tool_use"

    def test_format_tool_result(self):
        msgs = [InternalMessage(
            role="tool",
            content='{"content": "file content"}',
            tool_call_id="toolu_1",
        )]
        result = self.make_formatter().format_messages(msgs)
        assert result[0]["role"] == "user"
        assert result[0]["content"][0]["type"] == "tool_result"

    def test_parse_response_with_text_and_tool(self):
        data = {
            "content": [
                {"type": "text", "text": "I found the issue."},
                {"type": "tool_use", "id": "tu_1", "name": "read", "input": {"path": "x"}},
            ],
            "stop_reason": "tool_use",
        }
        parsed = self.make_formatter().parse_response(data)
        assert parsed.assistant_message.content == "I found the issue."
        assert len(parsed.assistant_message.tool_calls) == 1
        assert parsed.finish_reason == "tool_calls"


# ═══════════════════════════════════════════════════════════════════════════════
# GoogleFormatter
# ═══════════════════════════════════════════════════════════════════════════════


class TestGoogleFormatter:
    def make_formatter(self) -> GoogleFormatter:
        return GoogleFormatter()

    def test_format_user_message(self):
        msgs = [InternalMessage(role="user", content="Hello")]
        result = self.make_formatter().format_messages(msgs)
        assert result[0]["role"] == "user"
        assert result[0]["parts"][0]["text"] == "Hello"

    def test_format_assistant_with_tool_call(self):
        msgs = [InternalMessage(
            role="model",
            content=None,
            tool_calls=[{
                "id": "fc_1",
                "function": {"name": "read", "arguments": '{"path": "x"}'},
            }],
        )]
        result = self.make_formatter().format_messages(msgs)
        assert result[0]["role"] == "model"
        assert "functionCall" in result[0]["parts"][0]

    def test_format_tool_result(self):
        msgs = [InternalMessage(
            role="tool",
            content="file content",
            tool_call_id="fc_1",
            tool_name="read",
        )]
        result = self.make_formatter().format_messages(msgs)
        assert "functionResponse" in result[0]["parts"][0]

    def test_parse_response_with_function_call(self):
        data = {
            "candidates": [{
                "content": {
                    "parts": [
                        {"functionCall": {"name": "read", "args": {"path": "x"}}},
                    ],
                },
                "finishReason": "STOP",
            }],
        }
        parsed = self.make_formatter().parse_response(data)
        assert len(parsed.assistant_message.tool_calls) == 1
        assert parsed.assistant_message.tool_calls[0]["function"]["name"] == "read"
