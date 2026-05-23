"""Provider-specific message formatters for the API backend.

Each formatter:
- Converts internal messages (role, content, tool_calls) to
  provider-specific wire format
- Parses provider-specific responses back to internal format
- Handles provider quirks: reasoning_content, different tool formats, etc.
- Tool formatting is delegated to the existing _to_*_tools methods

Usage::
    formatter = get_formatter("openai-compatible")
    response = formatter.parse_response(api_response)  # → InternalMessage
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class InternalMessage:
    """Canonical internal message format.

    All formatters convert to/from this format. The tool-calling loop
    works exclusively with InternalMessage — provider quirks are handled
    at the format boundary.
    """

    role: str
    """Message role: system, user, assistant, or tool."""

    content: str | None = None
    """Text content of the message. May be None for tool-call messages."""

    tool_calls: list[dict[str, Any]] | None = None
    """Tool calls requested by the assistant, if any.

    Internal format::
        [{"id": "call_xxx", "type": "function",
          "function": {"name": "foo", "arguments": "{\\"key\\": \\"val\\"}"}}]
    """

    tool_call_id: str | None = None
    """ID of the tool call this result is for (role='tool' only)."""

    tool_name: str | None = None
    """Name of the tool that was called (role='tool' only)."""

    reasoning_content: str | None = None
    """Provider-specific reasoning/thinking content (e.g. DeepSeek).
    Must be preserved when round-tripping assistant messages back to
    the API for models that use a thinking mode.
    """


@dataclass
class FormattedRequest:
    """A fully formatted request payload ready for the API."""

    messages: list[dict[str, Any]]
    """Messages list in provider-specific format."""

    tools: list[dict[str, Any]] | None = None
    """Tool definitions in provider-specific format, if any."""

    extra_body: dict[str, Any] = field(default_factory=dict)
    """Any additional provider-specific body fields."""


@dataclass
class ParsedResponse:
    """A parsed API response chunk."""

    assistant_message: InternalMessage
    """The assistant's response message."""

    finish_reason: str | None = None
    """Reason why the response finished: stop, tool_calls, length, etc."""


# ═══════════════════════════════════════════════════════════════════════════════
# Abstract base
# ═══════════════════════════════════════════════════════════════════════════════


class MessageFormatter(ABC):
    """Base class for provider-specific message formatters."""

    @abstractmethod
    def format_messages(
        self, messages: list[InternalMessage]
    ) -> list[dict[str, Any]]:
        """Convert internal messages to provider-specific wire format."""
        ...

    @abstractmethod
    def parse_response(self, data: dict[str, Any]) -> ParsedResponse:
        """Parse a provider API response into internal format.

        Args:
            data: The parsed JSON body of the API response
                  (typically ``choices[0].message``).

        Returns:
            A ``ParsedResponse`` with the assistant's message.
        """
        ...

    @abstractmethod
    def format_initial_payload(
        self,
        system_prompt: str,
        user_content: str,
        model: str,
        max_tokens: int,
        temperature: float,
    ) -> FormattedRequest:
        """Build the initial request payload.

        This is the first request in a conversation. Subsequent requests
        add messages via ``format_messages()``.
        """
        ...


# ═══════════════════════════════════════════════════════════════════════════════
# OpenAI-compatible (standard)
# ═══════════════════════════════════════════════════════════════════════════════


class OpenAIFormatter(MessageFormatter):
    """Standard OpenAI-compatible message format.

    Used by: OpenAI, and any provider that follows OpenAI's message format
    without additional quirks (e.g. Together AI, Fireworks, Groq).
    """

    def format_messages(
        self, messages: list[InternalMessage]
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for msg in messages:
            entry: dict[str, Any] = {"role": msg.role}

            if msg.role == "tool":
                entry["content"] = msg.content or ""
                entry["tool_call_id"] = msg.tool_call_id or ""
            elif msg.role == "assistant":
                entry["content"] = msg.content or None
                if msg.tool_calls:
                    entry["tool_calls"] = msg.tool_calls
            else:
                entry["content"] = msg.content or ""

            result.append(entry)
        return result

    def parse_response(self, data: dict[str, Any]) -> ParsedResponse:
        choices = data.get("choices", [])
        if not choices:
            return ParsedResponse(
                assistant_message=InternalMessage(role="assistant", content=""),
                finish_reason="error",
            )

        choice = choices[0]
        msg = choice.get("message", {})

        return ParsedResponse(
            assistant_message=self._parse_message(msg),
            finish_reason=choice.get("finish_reason"),
        )

    def _parse_message(self, msg: dict[str, Any]) -> InternalMessage:
        return InternalMessage(
            role="assistant",
            content=msg.get("content") or None,
            tool_calls=msg.get("tool_calls"),
            # No reasoning_content for standard OpenAI
        )

    def format_initial_payload(
        self,
        system_prompt: str,
        user_content: str,
        model: str,
        max_tokens: int,
        temperature: float,
    ) -> FormattedRequest:
        return FormattedRequest(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
        )


# ═══════════════════════════════════════════════════════════════════════════════
# DeepSeek — preserves reasoning_content (thinking mode)
# ═══════════════════════════════════════════════════════════════════════════════


class DeepSeekFormatter(OpenAIFormatter):
    """DeepSeek API format — OpenAI-compatible but preserves reasoning_content.

    DeepSeek V4 Pro uses a thinking mode where the API returns
    ``reasoning_content`` alongside ``content`` in assistant messages.
    The API requires ``reasoning_content`` to be included in subsequent
    requests' messages array. This formatter preserves it.
    """

    def _parse_message(self, msg: dict[str, Any]) -> InternalMessage:
        return InternalMessage(
            role="assistant",
            content=msg.get("content") or None,
            tool_calls=msg.get("tool_calls"),
            reasoning_content=msg.get("reasoning_content"),
        )

    def format_messages(
        self, messages: list[InternalMessage]
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for msg in messages:
            entry: dict[str, Any] = {"role": msg.role}

            if msg.role == "tool":
                entry["content"] = msg.content or ""
                entry["tool_call_id"] = msg.tool_call_id or ""
            elif msg.role == "assistant":
                entry["content"] = msg.content or None
                if msg.tool_calls:
                    entry["tool_calls"] = msg.tool_calls
                # Preserve reasoning_content for thinking mode
                if msg.reasoning_content is not None:
                    entry["reasoning_content"] = msg.reasoning_content
            else:
                entry["content"] = msg.content or ""

            result.append(entry)
        return result


# ═══════════════════════════════════════════════════════════════════════════════
# Anthropic (Claude) format
# ═══════════════════════════════════════════════════════════════════════════════


class AnthropicFormatter(MessageFormatter):
    """Anthropic Claude message format.

    Uses content blocks instead of the OpenAI string-based format.
    Tool calls are ``tool_use`` content blocks, tool results are
    ``tool_result`` blocks.
    """

    def format_messages(
        self, messages: list[InternalMessage]
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for msg in messages:
            if msg.role == "system":
                result.append({"role": "system", "content": msg.content or ""})
            elif msg.role == "user":
                result.append({"role": "user", "content": msg.content or ""})
            elif msg.role == "assistant":
                entry: dict[str, Any] = {"role": "assistant"}
                content_blocks: list[dict[str, Any]] = []
                if msg.content:
                    content_blocks.append({
                        "type": "text",
                        "text": msg.content,
                    })
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        func = tc.get("function", {})
                        try:
                            args = json.loads(func.get("arguments", "{}"))
                        except (json.JSONDecodeError, TypeError):
                            args = {}
                        content_blocks.append({
                            "type": "tool_use",
                            "id": tc.get("id", ""),
                            "name": func.get("name", ""),
                            "input": args,
                        })
                entry["content"] = content_blocks
                result.append(entry)
            elif msg.role == "tool":
                result.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": msg.tool_call_id or "",
                        "content": msg.content or "",
                    }],
                })
        return result

    def parse_response(self, data: dict[str, Any]) -> ParsedResponse:
        # Anthropic response format: content array of blocks
        content_blocks = data.get("content", [])
        text_content = ""
        tool_calls: list[dict[str, Any]] = []

        for block in content_blocks:
            if block.get("type") == "text":
                text_content = block.get("text", "")
            elif block.get("type") == "tool_use":
                tool_calls.append({
                    "id": block.get("id", ""),
                    "type": "function",
                    "function": {
                        "name": block.get("name", ""),
                        "arguments": json.dumps(block.get("input", {})),
                    },
                })

        stop_reason = data.get("stop_reason")
        finish_reason = {
            "end_turn": "stop",
            "tool_use": "tool_calls",
            "max_tokens": "length",
        }.get(stop_reason, stop_reason)

        return ParsedResponse(
            assistant_message=InternalMessage(
                role="assistant",
                content=text_content or None,
                tool_calls=tool_calls if tool_calls else None,
            ),
            finish_reason=finish_reason,
        )

    def format_initial_payload(
        self,
        system_prompt: str,
        user_content: str,
        model: str,
        max_tokens: int,
        temperature: float,
    ) -> FormattedRequest:
        return FormattedRequest(
            messages=[
                {"role": "user", "content": user_content},
            ],
            extra_body={
                "system": system_prompt,
                "max_tokens": max_tokens,
            },
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Google / Gemini format
# ═══════════════════════════════════════════════════════════════════════════════


class GoogleFormatter(MessageFormatter):
    """Google Gemini message format.

    Uses ``contents[]`` array instead of ``messages[]``.
    System instruction is a separate top-level field.
    """

    def format_messages(
        self, messages: list[InternalMessage]
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for msg in messages:
            if msg.role == "system":
                continue  # Google uses separate system_instruction field
            entry: dict[str, Any] = {
                "role": "user" if msg.role in ("user", "tool") else "model",
            }
            parts: list[dict[str, Any]] = []
            if msg.content:
                parts.append({"text": msg.content})
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    func = tc.get("function", {})
                    parts.append({
                        "functionCall": {
                            "name": func.get("name", ""),
                            "args": json.loads(
                                func.get("arguments", "{}")
                            ),
                        },
                    })
            if msg.role == "tool":
                parts = [{
                    "functionResponse": {
                        "name": msg.tool_name or "",
                        "response": {"result": msg.content or ""},
                    },
                }]
            entry["parts"] = parts
            result.append(entry)
        return result

    def parse_response(self, data: dict[str, Any]) -> ParsedResponse:
        candidates = data.get("candidates", [])
        if not candidates:
            return ParsedResponse(
                assistant_message=InternalMessage(role="model", content=""),
                finish_reason="error",
            )

        content = candidates[0].get("content", {})
        parts = content.get("parts", [])
        text_content = ""
        tool_calls: list[dict[str, Any]] = []

        for part in parts:
            if "text" in part:
                text_content = part["text"]
            if "functionCall" in part:
                fc = part["functionCall"]
                tool_calls.append({
                    "id": fc.get("name", "unknown"),
                    "type": "function",
                    "function": {
                        "name": fc.get("name", ""),
                        "arguments": json.dumps(fc.get("args", {})),
                    },
                })

        return ParsedResponse(
            assistant_message=InternalMessage(
                role="model",
                content=text_content or None,
                tool_calls=tool_calls if tool_calls else None,
            ),
            finish_reason=candidates[0].get("finishReason"),
        )

    def format_initial_payload(
        self,
        system_prompt: str,
        user_content: str,
        model: str,
        max_tokens: int,
        temperature: float,
    ) -> FormattedRequest:
        return FormattedRequest(
            messages=[],
            extra_body={
                "system_instruction": {
                    "parts": [{"text": system_prompt}],
                },
                "contents": [{
                    "role": "user",
                    "parts": [{"text": user_content}],
                }],
            },
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Formatter registry
# ═══════════════════════════════════════════════════════════════════════════════

_FORMATTERS: dict[str, type[MessageFormatter]] = {
    "openai-compatible": OpenAIFormatter,
    "deepseek": DeepSeekFormatter,
    "anthropic": AnthropicFormatter,
    "google": GoogleFormatter,
    "gemini": GoogleFormatter,
}


def get_formatter(provider_type: str) -> MessageFormatter:
    """Get the appropriate formatter for a provider type.

    Args:
        provider_type: Provider type string, e.g. ``"openai-compatible"``,
            ``"deepseek"``, ``"anthropic"``, ``"google"``, ``"gemini"``.

    Returns:
        A ``MessageFormatter`` instance.

    Raises:
        ValueError: If no formatter is registered for the provider type.
    """
    key = provider_type.lower().strip()
    # Try exact match first
    if key in _FORMATTERS:
        return _FORMATTERS[key]()

    # Fall back to generic heuristics
    if "anthropic" in key or "claude" in key:
        return _FORMATTERS["anthropic"]()
    if "google" in key or "gemini" in key:
        return _FORMATTERS["google"]()
    if "deepseek" in key:
        return _FORMATTERS["deepseek"]()

    # Default to OpenAI-compatible
    return _FORMATTERS["openai-compatible"]()
