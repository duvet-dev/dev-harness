"""API backend — direct LLM API calls with function-calling support.

Calls LLM providers (DeepSeek, OpenAI, Anthropic) via their REST APIs
using the ContextPacket content as input. Supports model override,
streaming responses to files, configurable timeouts, and function-
calling via the Agent Read/Write Tool (Wave 13).

When ``Invocation.available_tools`` is populated, the backend:

1. Includes tool definitions in the API request
2. Handles ``tool_calls`` responses — executes each tool via the
   provided tool registry, feeds results back to the LLM
3. Loops until the LLM returns a content message (no more tool calls)
4. Returns the final text response as the agent's output

Backend name: 'api'
"""

from __future__ import annotations

import asyncio  # noqa: E402 (imported after class for clarity)
import json
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

import httpx

from harness.agents.context import ContextPacket
from harness.agents.backends.base import (
    AbstractBackend,
    BackendConfigError,
    BackendError,
    BackendResult,
    BackendTimeoutError,
    Invocation,
)

# Max rounds of tool calling to prevent infinite loops
MAX_TOOL_ROUNDS = 25


@dataclass
class ApiBackendConfig:
    """Configuration for the API backend.

    These are *fallback* defaults. When the runner provides a resolved
    provider config via ``Invocation.resolved_config``, those values
    take precedence.
    """

    default_model: str = "deepseek-v4-pro"
    default_endpoint: str = "https://api.deepseek.com/chat/completions"
    timeout_seconds: int = 600
    max_retries: int = 3
    retry_delay_seconds: float = 2.0
    api_key_env: str = "DEEPSEEK_API_KEY"
    max_tool_rounds: int = MAX_TOOL_ROUNDS

    @classmethod
    def from_dict(cls, config: dict) -> ApiBackendConfig:
        c = cls()
        if "default_model" in config:
            c.default_model = config["default_model"]
        if "default_endpoint" in config:
            c.default_endpoint = config["default_endpoint"]
        if "timeout_seconds" in config:
            c.timeout_seconds = int(config["timeout_seconds"])
        if "max_retries" in config:
            c.max_retries = int(config["max_retries"])
        if "api_key_env" in config:
            c.api_key_env = config["api_key_env"]
        if "max_tool_rounds" in config:
            c.max_tool_rounds = int(config["max_tool_rounds"])
        return c


class ApiBackend(AbstractBackend):
    """Backend that calls LLM APIs via HTTP."""

    name = "api"

    def __init__(self, config: dict | None = None):
        self._config = ApiBackendConfig.from_dict(config or {})

    # ------------------------------------------------------------------
    # prepare() — build the invocation
    # ------------------------------------------------------------------

    async def prepare(self, packet: ContextPacket) -> Invocation:
        """Prepare an API invocation from the context packet.

        Builds the request payload from the packet's spec_content and
        any additional context. Sets model from packet constraints or
        default. Attaches available tools from the packet constraints
        (if any) for function-calling support.
        """
        model = packet.constraint_section.get(
            "model", self._config.default_model
        )

        system_prompt = (
            "You are an expert software engineer. Follow the architecture "
            "rules and produce the required artifacts. "
            f"Architecture rules: {'; '.join(packet.architecture_rules)}"
        )

        user_content = packet.spec_content

        if packet.input_artifacts:
            user_content += "\n\nInput artifacts:"
            for name, path in packet.input_artifacts.items():
                user_content += f"\n- {name}: {path}"

        # Extract any available_tools from packet constraints
        tools = packet.constraint_section.get("available_tools", [])

        max_tokens = packet.constraint_section.get(
            "max_tokens", 8192
        )

        return Invocation(
            command=self._config.default_endpoint,
            args=[
                json.dumps({
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content},
                    ],
                    "max_tokens": max_tokens,
                    "temperature": packet.constraint_section.get(
                        "temperature", 0.7
                    ),
                    "stream": False,  # no streaming when tools are present
                }),
            ],
            env={},
            work_dir=packet.target_directory,
            input_packet=packet,
            model=model,
            available_tools=tools,
            timeout_seconds=self._config.timeout_seconds,
        )

    # ------------------------------------------------------------------
    # run() — execute the API call with optional tool loop
    # ------------------------------------------------------------------

    async def run(self, invocation: Invocation) -> BackendResult:
        """Execute the API call and collect results.

        If the invocation has ``available_tools``, runs a multi-round
        tool-calling loop: the LLM may request tool executions, the
        backend executes them and feeds results back, continuing until
        the LLM produces a final text response.
        """
        start_time = time.monotonic()

        # ── Resolve api_key ──────────────────────────────────────────────
        api_key: str = ""
        if invocation.resolved_config:
            api_key = invocation.resolved_config.get("api_key", "")
        if not api_key:
            api_key = os.environ.get(self._config.api_key_env, "")

        if not api_key:
            return BackendResult(
                status="failure",
                errors=[f"API key not set: {self._config.api_key_env}"],
                metrics={"duration_ms": 0},
            )

        # ── Resolve endpoint URL and model ───────────────────────────────
        url, model_key = self._resolve_endpoint_and_model(invocation)

        # ── Build the initial payload ────────────────────────────────────
        payload = json.loads(invocation.args[0]) if invocation.args else {}
        payload["model"] = model_key
        payload.pop("stream", None)  # function-calling needs streaming=False

        # ── Attach tools ─────────────────────────────────────────────────
        tools: list[dict[str, Any]] = []
        if invocation.available_tools:
            if invocation.resolved_config:
                # Convert to provider-specific format
                provider = invocation.resolved_config.get("provider", "")
                tools = self._convert_tools(
                    invocation.available_tools, provider
                )
            else:
                # Passthrough — assume OpenAI-compatible tools format
                tools = invocation.available_tools

        # ── Main execution ───────────────────────────────────────────────
        has_tools = bool(tools)
        max_rounds = (
            self._config.max_tool_rounds if has_tools else 1
        )
        all_messages = payload.get("messages", [])
        errors: list[str] = []
        final_content = ""
        total_tool_calls = 0

        for round_idx in range(max_rounds):
            round_payload = {
                **payload,
                "messages": all_messages,
            }
            if has_tools:
                round_payload["tools"] = tools

            # --- Send request ---
            result = await self._send_request(
                url, api_key, round_payload, invocation, start_time
            )
            if result.status == "failure" or result.status == "timeout":
                # Carry through the artifacts from earlier rounds
                errors.extend(result.errors)
                return result

            data: dict = result.metadata  # contains parsed response

            # --- Extract assistant message ---
            choices = data.get("choices", [])
            if not choices:
                errors.append("API response missing 'choices'")
                break

            assistant_msg = choices[0].get("message", {})

            # --- Check for tool_calls ---
            tool_calls = assistant_msg.get("tool_calls")
            if not tool_calls:
                # Normal content response — we're done
                final_content = assistant_msg.get("content", "")
                break

            # --- Process tool_calls ---
            total_tool_calls += len(tool_calls)

            # Add the assistant message to history
            assistant_msg_for_history = {
                "role": "assistant",
                "content": assistant_msg.get("content") or None,
            }
            if tool_calls:
                # Convert tool_calls to serializable format
                serialized_calls = []
                for tc in tool_calls:
                    serialized_calls.append({
                        "id": tc.get("id"),
                        "type": tc.get("type", "function"),
                        "function": {
                            "name": tc.get("function", {}).get("name"),
                            "arguments": tc.get("function", {}).get("arguments"),
                        },
                    })
                assistant_msg_for_history["tool_calls"] = serialized_calls

            all_messages.append(assistant_msg_for_history)

            # Execute each tool call
            for tc in tool_calls:
                tc_id = tc.get("id", "call_unknown")
                function_info = tc.get("function", {})
                func_name = function_info.get("name", "")
                raw_args = function_info.get("arguments", "{}")

                # Parse arguments
                try:
                    func_args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except json.JSONDecodeError:
                    func_args = {}

                # Execute via tool registry
                tool_output = self._execute_tool(
                    invocation, func_name, func_args
                )

                # Add tool response to message history
                all_messages.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "content": json.dumps(tool_output),
                })

        # --- Extract final result ---
        duration_ms = int((time.monotonic() - start_time) * 1000)

        if not final_content and not errors:
            errors.append("Model produced no output after tool calling")

        artifacts = self._parse_code_blocks(final_content)

        return BackendResult(
            status="success" if not errors else "failure",
            output_dir=invocation.work_dir if invocation.work_dir else "",
            artifacts=artifacts,
            errors=errors,
            metrics={
                "duration_ms": duration_ms,
                "token_count": data.get("usage", {}).get(
                    "total_tokens", 0
                ) if "data" in locals() else 0,
                "model": model_key,
                "tool_calls": total_tool_calls,
                "tool_rounds": round_idx + 1 if has_tools else 0,
            },
        )

    # ------------------------------------------------------------------
        # ------------------------------------------------------------------
    # Streaming tool loop + response
    # ------------------------------------------------------------------

    async def run_stream(
        self, invocation: Invocation
    ) -> AsyncIterator[str]:
        """Run the tool loop silently, then stream the final response.

        For interactive sessions where the user wants streaming output.
        Tool calls execute silently (writes files), then the final
        text response is streamed token by token.

        Yields:
            Text chunks of the final assistant response.
        """
        start_time = time.monotonic()

        # ── Resolve api_key ──────────────────────────────────────────────
        api_key: str = ""
        if invocation.resolved_config:
            api_key = invocation.resolved_config.get("api_key", "")
        if not api_key:
            api_key = os.environ.get(self._config.api_key_env, "")

        if not api_key:
            yield "\n[Error: API key not set]\n"
            return

        # ── Resolve endpoint URL and model ───────────────────────────────
        url, model_key = self._resolve_endpoint_and_model(invocation)

        # ── Build the initial payload ────────────────────────────────────
        payload = json.loads(invocation.args[0]) if invocation.args else {}
        payload["model"] = model_key
        payload.pop("stream", None)

        # ── Attach tools ─────────────────────────────────────────────────
        tools: list[dict[str, Any]] = []
        if invocation.available_tools:
            if invocation.resolved_config:
                provider = invocation.resolved_config.get("provider", "")
                tools = self._convert_tools(
                    invocation.available_tools, provider
                )
            else:
                tools = invocation.available_tools

        has_tools = bool(tools)
        all_messages = payload.get("messages", [])
        errors: list[str] = []

        # Phase 1: Tool-calling loop (non-streaming, silent)
        if has_tools:
            for round_idx in range(self._config.max_tool_rounds):
                round_payload = {
                    **payload,
                    "messages": all_messages,
                    "tools": tools,
                }

                result = await self._send_request(
                    url, api_key, round_payload, invocation, start_time
                )
                if result.status in ("failure", "timeout"):
                    errors.extend(result.errors)
                    yield f"\n[Error during tool execution: {result.errors[-1]}]\n"
                    return

                data: dict = result.metadata
                choices = data.get("choices", [])
                if not choices:
                    errors.append("API response missing 'choices'")
                    break

                assistant_msg = choices[0].get("message", {})
                tool_calls = assistant_msg.get("tool_calls")

                if not tool_calls:
                    # No more tool calls — save final content
                    all_messages.append({
                        "role": "assistant",
                        "content": assistant_msg.get("content", ""),
                    })
                    break

                # Add assistant message with tool calls to history
                msg_for_history = {
                    "role": "assistant",
                    "content": assistant_msg.get("content") or None,
                }
                serialized_calls = []
                for tc in tool_calls:
                    serialized_calls.append({
                        "id": tc.get("id"),
                        "type": tc.get("type", "function"),
                        "function": {
                            "name": tc.get("function", {}).get("name"),
                            "arguments": tc.get("function", {}).get("arguments"),
                        },
                    })
                msg_for_history["tool_calls"] = serialized_calls
                all_messages.append(msg_for_history)

                # Execute each tool call
                for tc in tool_calls:
                    tc_id = tc.get("id", "call_unknown")
                    function_info = tc.get("function", {})
                    func_name = function_info.get("name", "")
                    raw_args = function_info.get("arguments", "{}")

                    try:
                        func_args = (
                            json.loads(raw_args)
                            if isinstance(raw_args, str)
                            else raw_args
                        )
                    except json.JSONDecodeError:
                        func_args = {}

                    tool_output = self._execute_tool(
                        invocation, func_name, func_args
                    )

                    all_messages.append({
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "content": json.dumps(tool_output),
                    })

        # Phase 2: Stream the final response
        stream_payload = {
            **payload,
            "messages": all_messages,
            "stream": True,
        }
        stream_payload.pop("tools", None)

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(invocation.timeout_seconds)
        ) as client:
            async with client.stream(
                "POST", url, headers=headers, json=stream_payload
            ) as response:
                if response.status_code != 200:
                    error_body = await response.aread()
                    yield (
                        f"\n[Error {response.status_code}: "
                        f"{error_body.decode()[:500]}]\n"
                    )
                    return

                full_content: list[str] = []
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break

                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    choices = data.get("choices", [])
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {})
                    text = delta.get("content", "")
                    if text:
                        full_content.append(text)
                        yield text

                # Store complete response for history
                assistant_reply = "".join(full_content)
                all_messages.append({
                    "role": "assistant",
                    "content": assistant_reply,
                })

        # Keep message history on invocation for later queries
        invocation._stream_messages = all_messages

# Tool execution
    # ------------------------------------------------------------------

    def _execute_tool(
        self,
        invocation: Invocation,
        func_name: str,
        func_args: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a tool call from the LLM.

        Looks up the tool in ``invocation.tool_registry`` by name,
        and dispatches to the appropriate executor.
        """
        if func_name == "repo_tool":
            return self._execute_repo_tool(invocation, func_args)

        if func_name == "web_search":
            return self._execute_web_search_tool(invocation, func_args)

        return {"error": f"Unknown tool: {func_name}"}

    def _execute_web_search_tool(
        self,
        invocation: Invocation,
        args: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a web_search tool operation."""
        web_tool = invocation.tool_registry.get("web_search")
        if web_tool is None:
            return {"error": "WebSearchTool not configured for this invocation"}

        try:
            return web_tool.execute(args)
        except Exception as exc:
            return {"error": str(exc), "type": type(exc).__name__}

    def _execute_repo_tool(
        self,
        invocation: Invocation,
        args: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a repo_tool operation."""
        operation = args.get("operation", "")
        path = args.get("path", "")
        content = args.get("content", "")

        repo_tool = invocation.tool_registry.get("repo_tool")
        if repo_tool is None:
            return {"error": "RepoTool not configured for this invocation"}

        try:
            if operation == "read":
                return {"content": repo_tool.read(path)}
            elif operation == "write":
                written_path = repo_tool.write(path, content)
                return {
                    "success": True,
                    "path": str(written_path.relative_to(repo_tool.repo_root)),
                }
            elif operation == "list":
                return {"entries": repo_tool.list(path)}
            elif operation == "exists":
                return {"exists": repo_tool.exists(path)}
            else:
                return {"error": f"Unknown operation: {operation}"}
        except Exception as exc:
            return {"error": str(exc), "type": type(exc).__name__}

    # ------------------------------------------------------------------
    # HTTP request
    # ------------------------------------------------------------------

    async def _send_request(
        self,
        url: str,
        api_key: str,
        payload: dict[str, Any],
        invocation: Invocation,
        start_time: float,
    ) -> BackendResult | _HttpResult:
        """Send a single HTTP request to the LLM API.

        Returns either a BackendResult (on failure) or an _HttpResult
        with the parsed response data.
        """
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        max_retries = self._config.max_retries
        last_error = ""

        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(invocation.timeout_seconds)
                ) as client:
                    response = await client.post(
                        url, headers=headers, json=payload
                    )

                if response.status_code == 200:
                    try:
                        data = response.json()
                    except json.JSONDecodeError as exc:
                        return BackendResult(
                            status="failure",
                            errors=[f"Invalid JSON response: {exc}"],
                            metrics={
                                "duration_ms": int(
                                    (time.monotonic() - start_time) * 1000
                                ),
                            },
                        )
                    return _HttpResult(status="success", metadata=data)

                if response.status_code in (429, 502, 503, 504):
                    if attempt < max_retries - 1:
                        wait = self._config.retry_delay_seconds * (
                            2**attempt
                        )
                        await asyncio.sleep(wait)
                        last_error = (
                            f"HTTP {response.status_code}: "
                            f"{response.text[:200]}"
                        )
                        continue
                    else:
                        return BackendResult(
                            status="failure",
                            errors=[f"HTTP {response.status_code} after {max_retries} retries"],
                            metrics={
                                "duration_ms": int(
                                    (time.monotonic() - start_time) * 1000
                                ),
                            },
                        )
                if response.status_code in (401, 403):
                    return BackendResult(
                        status="failure",
                        errors=[
                            f"API auth error ({response.status_code}): "
                            f"{response.text[:200]}"
                        ],
                        metrics={
                            "duration_ms": int(
                                (time.monotonic() - start_time) * 1000
                            ),
                            "http_status": response.status_code,
                        },
                    )
                # Non-retryable error
                return BackendResult(
                    status="failure",
                    errors=[
                        f"API error ({response.status_code}): "
                        f"{response.text[:200]}"
                    ],
                    metrics={
                        "duration_ms": int(
                            (time.monotonic() - start_time) * 1000
                        ),
                        "http_status": response.status_code,
                    },
                )
            except httpx.TimeoutException:
                last_error = f"Request timed out (>{invocation.timeout_seconds}s)"
                if attempt >= max_retries - 1:
                    return BackendResult(
                        status="timeout",
                        errors=[last_error],
                        metrics={
                            "duration_ms": invocation.timeout_seconds * 1000,
                        },
                    )
                continue
            except httpx.RequestError as exc:
                last_error = f"Request failed: {exc}"
                if attempt >= max_retries - 1:
                    return BackendResult(
                        status="failure",
                        errors=[last_error],
                        metrics={
                            "duration_ms": int(
                                (time.monotonic() - start_time) * 1000
                            ),
                        },
                    )
                await asyncio.sleep(self._config.retry_delay_seconds)
        else:
            return BackendResult(
                status="failure",
                errors=[
                    f"API call failed after {max_retries} retries: "
                    f"{last_error}"
                ],
                metrics={
                    "duration_ms": int(
                        (time.monotonic() - start_time) * 1000
                    ),
                },
            )

    # ------------------------------------------------------------------
    # Tool format converters
    # ------------------------------------------------------------------

    def _convert_tools(
        self,
        internal_tools: list[dict[str, Any]],
        provider: str,
    ) -> list[dict[str, Any]]:
        """Convert internal tool specs to provider-specific format.

        Args:
            internal_tools: List of internal tool specs (from
                ``RepoTool.tool_spec()`` and similar).
            provider: Provider identifier string (e.g. ``"openai"``,
                ``"anthropic"``, ``"google"``).

        Returns:
            List of tool definitions in the provider's format.
        """
        provider_lower = (provider or "").lower().rstrip("/")

        if "anthropic" in provider_lower:
            return self._to_anthropic_tools(internal_tools)
        if "google" in provider_lower or "gemini" in provider_lower:
            return self._to_google_tools(internal_tools)

        # Default: OpenAI-compatible (DeepSeek, OpenAI, others)
        return self._to_openai_tools(internal_tools)

    @staticmethod
    def _to_openai_tools(
        internal_tools: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Convert internal tool specs to OpenAI tools format.

        The internal format is already close to OpenAI's, so this is
        largely a passthrough.
        """
        result = []
        for tool in internal_tools:
            func = tool.get("function", {})
            result.append({
                "type": "function",
                "function": {
                    "name": func.get("name", ""),
                    "description": func.get("description", ""),
                    "parameters": func.get("parameters", {}),
                },
            })
        return result

    @staticmethod
    def _to_anthropic_tools(
        internal_tools: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Convert internal tool specs to Anthropic tools format."""
        result = []
        for tool in internal_tools:
            func = tool.get("function", {})
            result.append({
                "name": func.get("name", ""),
                "description": func.get("description", ""),
                "input_schema": func.get("parameters", {}),
            })
        return result

    @staticmethod
    def _to_google_tools(
        internal_tools: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Convert internal tool specs to Google/Gemini tools format."""
        result = []
        for tool in internal_tools:
            func = tool.get("function", {})
            result.append({
                "function_declarations": [
                    {
                        "name": func.get("name", ""),
                        "description": func.get("description", ""),
                        "parameters": func.get("parameters", {}),
                    }
                ],
            })
        return result

    # ------------------------------------------------------------------
    # URL / model resolution
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_endpoint_and_model(
        invocation: Invocation,
    ) -> tuple[str, str]:
        """Resolve the endpoint URL and model string."""
        url: str = invocation.command

        if invocation.resolved_config:
            base_url = invocation.resolved_config.get("base_url")
            if base_url:
                base_url = base_url.rstrip("/")
                if not base_url.endswith("/chat/completions"):
                    url = f"{base_url}/chat/completions"
                else:
                    url = base_url

        model: str = invocation.model
        if not model and invocation.resolved_config:
            model = invocation.resolved_config.get("model", "")

        return url, model

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_config(self, config: dict) -> list[str]:
        """Validate API backend configuration."""
        errors: list[str] = []
        bc = ApiBackendConfig.from_dict(config)
        if bc.timeout_seconds < 10:
            errors.append("timeout_seconds must be >= 10")
        if bc.max_retries < 0:
            errors.append("max_retries must be >= 0")
        return errors

    # ------------------------------------------------------------------
    # Artifact extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_code_blocks(text: str) -> dict[str, str]:
        """Extract code blocks from LLM response as artifacts.

        Parses markdown code fences like ```filename:path
        into an artifacts dict. Falls back to capturing all code blocks
        if no filenames are provided.
        """
        artifacts: dict[str, str] = {}
        # Match ```<lang>:<path> or ```<path>
        pattern = re.compile(
            r"```(?:[a-zA-Z_]*:)?([^\n]+?)\n(.*?)```", re.DOTALL
        )
        matches = pattern.findall(text)
        for filename, content in matches:
            fn = filename.strip()
            if fn:
                artifacts[fn] = content.strip()
        # If no code blocks but content exists, preserve it
        if not artifacts and text.strip():
            artifacts["_response"] = text.strip()

        return artifacts


# ------------------------------------------------------------------
# Internal types
# ------------------------------------------------------------------

@dataclass
class _HttpResult:
    """Internal result wrapper for HTTP requests without artifacts."""

    status: str = "failure"
    metadata: dict[str, Any] = field(default_factory=dict)
