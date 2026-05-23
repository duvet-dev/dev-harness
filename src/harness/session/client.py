"""LLM API client for interactive chat sessions.

Reads provider configuration from ``.harness/providers.yaml`` in the project
resolves ``${{ENV_VAR}}`` references, and provides a streaming chat
interface.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Optional

import httpx
import yaml

from harness.paths import get_engagement_dir, get_providers_path


# ── Data types ─────────────────────────────────────────────────────────────


@dataclass
class ChatMessage:
    """A single chat message."""

    role: str  # "user" | "assistant" | "system"
    content: str
    timestamp: str = ""


@dataclass
class ChatTranscript:
    """Full conversation transcript."""

    engagement_slug: str
    phase: str
    messages: list[ChatMessage] = field(default_factory=list)
    started_at: str = ""
    ended_at: str = ""

    def save(self, root: Path) -> Path:
        """Write transcript to ``.harness/engagements/<slug>/chat/<timestamp>.md``."""
        chat_dir = get_engagement_dir(root, self.engagement_slug) / "chat"
        chat_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        path = chat_dir / f"{ts}.md"
        lines = [
            f"# Chat — {self.phase} — {ts}",
            "",
            f"Engagement: {self.engagement_slug}",
            f"Phase:      {self.phase}",
            f"Started:    {self.started_at}",
            f"Ended:      {self.ended_at}",
            "",
            "---",
            "",
        ]
        for msg in self.messages:
            lines.append(f"## {msg.role.title()}")
            if msg.timestamp:
                lines.append(f"*{msg.timestamp}*")
            lines.append("")
            lines.append(msg.content)
            lines.append("")
        path.write_text("\n".join(lines))
        return path


# ── Config resolution ──────────────────────────────────────────────────────

_ENV_VAR_RE = re.compile(r"\$\{\{([^}]+)\}\}")


def resolve_env_vars(value: str) -> str:
    """Replace ``${{VAR}}`` placeholders with environment variable values.

    Leaves unresolvable placeholders in place so the user can see what's
    missing.
    """

    def _replace(m: re.Match) -> str:
        var_name = m.group(1)
        return os.environ.get(var_name, m.group(0))

    return _ENV_VAR_RE.sub(_replace, value)


def resolve_provider(
    root: Path, provider_name: str | None = None
) -> dict[str, Any]:
    """Read ``providers.yaml`` and resolve the active provider config.

    Returns a dict with fields: ``api_key``, ``base_url``, ``type``,
    ``model``, and any other provider-specific settings.

    If *provider_name* is not given, uses the ``default_backend``.
    """
    # Project-level .harness/providers.yaml
    local_path = get_providers_path(root)
    if local_path.is_file():
        config = yaml.safe_load(local_path.read_text()) or {}
    else:
        config = {}

    providers = config.get("providers", {})

    if not provider_name:
        # Try to use default_backend as a provider name
        default_backend = config.get("default_backend", "")
        if default_backend and default_backend in providers:
            provider_name = default_backend
        else:
            # Fall back to first available provider
            provider_names = list(providers.keys())
            provider_name = provider_names[0] if provider_names else None

    provider = (
        providers.get(provider_name) if provider_name else None
    )
    if not provider:
        # No provider found in YAML — fall back to env vars
        api_key = os.environ.get("HARNESS_API_KEY", "")
        base_url = os.environ.get(
            "HARNESS_API_BASE", "https://api.deepseek.com"
        )
        model = os.environ.get("HARNESS_MODEL", "deepseek-v4-pro")
        return {
            "type": "openai-compatible",
            "api_key": api_key,
            "base_url": base_url,
            "model": model,
        }

    # Resolve env vars in all string values
    resolved: dict[str, Any] = dict(provider)
    for key, val in list(resolved.items()):
        if isinstance(val, str):
            resolved[key] = resolve_env_vars(val)

    # If models key exists, pick the default model
    models = resolved.pop("models", {})
    resolved.setdefault("model", models.get("default", ""))

    return resolved


# ── Interactive Client ─────────────────────────────────────────────────────


class InteractiveClient:
    """Streaming LLM client for interactive chat.

    Usage::

        client = InteractiveClient(
            api_key="sk-...",
            base_url="https://api.deepseek.com",
            model="deepseek-v4-pro",
        )
        async for chunk in client.stream("Hello!"):
            print(chunk, end="", flush=True)
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-v4-pro",
        provider_type: str = "openai-compatible",
        system_prompt: str | None = None,
        timeout_seconds: int = 300,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        # Strip any "provider/" prefix from model name (safe for all APIs)
        if "/" in model:
            model = model.split("/", 1)[-1]
        self.model = model
        self.provider_type = provider_type
        self.system_prompt = system_prompt
        self.timeout_seconds = timeout_seconds
        self._messages: list[dict[str, str]] = []

        if system_prompt:
            self._messages.append({"role": "system", "content": system_prompt})

    def reload(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        provider_type: str | None = None,
    ) -> None:
        """Reconfigure the client without losing conversation history.

        Preserves all existing messages (including system prompt).
        Useful for switching models/providers mid-session.
        """
        if api_key is not None:
            self.api_key = api_key
        if base_url is not None:
            self.base_url = base_url.rstrip("/")
        if model is not None:
            if "/" in model:
                model = model.split("/", 1)[-1]
            self.model = model
        if provider_type is not None:
            self.provider_type = provider_type

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the conversation history."""
        self._messages.append({"role": role, "content": content})

    @property
    def message_count(self) -> int:
        return len([m for m in self._messages if m["role"] != "system"])

    async def stream(self, user_message: str) -> AsyncIterator[str]:
        """Send a message and stream the response token by token."""
        self._messages.append({"role": "user", "content": user_message})

        # Determine endpoint
        if self.provider_type == "anthropic":
            url = f"{self.base_url}/v1/messages"
        else:
            url = f"{self.base_url}/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        if self.provider_type == "anthropic":
            payload = {
                "model": self.model,
                "messages": [m for m in self._messages if m["role"] != "system"],
                "system": self.system_prompt or "",
                "max_tokens": 8192,
                "stream": True,
            }
        else:
            payload = {
                "model": self.model,
                "messages": list(self._messages),
                "max_tokens": 8192,
                "temperature": 0.7,
                "stream": True,
            }

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout_seconds)
        ) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
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

                    if self.provider_type == "anthropic":
                        if line.startswith("data: "):
                            data_str = line[6:]
                        else:
                            data_str = line
                    else:
                        if not line.startswith("data: "):
                            continue
                        data_str = line[6:]

                    if data_str == "[DONE]":
                        break

                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    if self.provider_type == "anthropic":
                        delta = data.get("delta", {})
                        text = delta.get("text", "")
                    else:
                        choices = data.get("choices", [])
                        if not choices:
                            continue
                        delta = choices[0].get("delta", {})
                        text = delta.get("content", "")

                    if text:
                        full_content.append(text)
                        yield text

                assistant_reply = "".join(full_content)
                self._messages.append(
                    {"role": "assistant", "content": assistant_reply}
                )

    def get_last_response(self) -> str:
        """Get the last assistant response content."""
        for msg in reversed(self._messages):
            if msg["role"] == "assistant":
                return msg["content"]
        return ""

    def conversation_history(self) -> list[dict[str, str]]:
        """Return all messages (excluding system prompt)."""
        return [m for m in self._messages if m["role"] != "system"]



from pathlib import Path
from typing import Any, AsyncIterator



class SessionClient:
    """Tool-aware streaming LLM client for interactive sessions.

    Wraps ``AgentRunner`` + ``ApiBackend`` to provide function-calling
    (RepoTool read/write/list/exists) during interactive chat and
    session loops. Builds a ``ContextPacket`` from session state,
    attaches the RepoTool via the agent runner, and streams the final
    response after tool calls resolve silently.

    Usage::

        client = SessionClient(root, engagement_slug, phase_def)
        async for chunk in client.stream("Hello!"):
            print(chunk, end="", flush=True)
    """

    def __init__(
        self,
        root: Path,
        engagement_slug: str,
        phase_def: dict,
        context_tier: int = 2,
        system_prompt: str | None = None,
    ):
        self.root = root
        self.engagement_slug = engagement_slug
        self.phase_def = phase_def
        self.context_tier = context_tier
        self.system_prompt = system_prompt or self._build_default_prompt()
        self._messages: list[dict[str, str]] = []

        # Resolve the project root (walk up for .git or .harness/providers.yaml)
        self._project_root = self._find_project_root(root)

    def _build_default_prompt(self) -> str:
        """Build the system prompt from the phase definition.

        Includes: domain language preamble, phase prompt,
        engagement context bundle (tiered), and RepoTool usage
        instructions.
        """
        from harness.context.loader import ContextLoader

        domain_preamble = (
            "You are working within the **Dev Harness** - an agent "
            "orchestration system. This engagement follows these naming "
            "conventions:\n"
            "- **Wave**: A PR-sized batch of work.\n"
            "- **Phase**: A task label (requirements, design, build, test).\n"
            "- **Iteration**: A review-feedback cycle within a wave.\n"
        )

        parts = [domain_preamble, self.phase_def.get("prompt", "")]

        # Load engagement context bundle
        engagement_root = (
            get_engagement_dir(self.root, self.engagement_slug)
        )
        if engagement_root.is_dir():
            try:
                loader = ContextLoader(
                    engagement_root, self.root, cache_timeout_seconds=300
                )
                bundle = loader.load_bundle(tier=self.context_tier)
                if bundle:
                    parts.append(
                        "\n---\n"
                        "CURRENT ENGAGEMENT FILES:\n"
                        f"{bundle}\n"
                        "These files already exist. Read them before "
                        "writing to avoid duplication.\n"
                        "---\n"
                    )
            except Exception:
                pass

        # RepoTool usage instructions
        repo_tool_block = (
            "\n---\n"
            "You have access to the **RepoTool** for reading and writing "
            "files in the project directory. Use it to:\n"
            "- **read** files to understand existing code and documents\n"
            "- **write** files to create or update project files\n"
            "- **list** directories to explore the project\n"
            "- **exists** to check if a file path exists\n"
            "\n"
            "Your phase artifacts (requirements, design docs, reviews) "
            "should be written directly using the RepoTool's **write** "
            "operation. Do NOT ask the user to run /apply or /write - you "
            "can write files directly.\n"
            "---\n"
        )
        parts.append(repo_tool_block)

        return "\n".join(parts)

    def _find_project_root(self, start: Path) -> Path:
        """Walk up from start to find the repo/project root."""
        p = start.resolve()
        for parent in [p] + list(p.parents):
            if (parent / ".git").exists() or get_providers_path(parent).exists():
                return parent
        return p

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the conversation history."""
        self._messages.append({"role": role, "content": content})

    def get_last_response(self) -> str:
        """Get the last assistant response content."""
        for msg in reversed(self._messages):
            if msg["role"] == "assistant":
                return msg["content"]
        return ""

    def conversation_history(self) -> list[dict[str, str]]:
        """Return all messages (excluding system prompt)."""
        return [m for m in self._messages if m["role"] != "system"]

    def build_system_prompt(self) -> str:
        """Build the system prompt for the current phase.

        Alias for backward compatibility. Returns the stored
        ``system_prompt`` set at construction time.
        """
        return self.system_prompt

    async def stream(self, user_message: str, agent_role: str = "") -> AsyncIterator[str]:
        """Send a message and stream the response.

        Builds a ContextPacket, runs via AgentRunner > ApiBackend with
        RepoTool attached. Tool calls execute silently (writing files),
        then the final response is streamed token by token.

        Args:
            user_message: The user's prompt / question.
            agent_role: Optional agent role (e.g. "architect", "coder").
                If empty, derived from phase_def.

        Yields:
            Text chunks of the assistant's final response.
        """
        self._messages.append({"role": "user", "content": user_message})

        # Build conversation context
        conv_lines = []
        for m in self._messages:
            if m["role"] == "user":
                conv_lines.append(f"User: {m['content']}")
            elif m["role"] == "assistant":
                conv_lines.append(f"Assistant: {m['content']}")
        conversation_text = "\n---\n".join(conv_lines)

        # Derive agent role from phase_def
        if not agent_role:
            agent_role = self.phase_def.get("agent", "coordinator")

        # Build a ContextPacket
        from harness.agents.context import ContextPacket, OutputContract

        system_prompt = self.build_system_prompt()
        full_spec = f"{system_prompt}\n\n{conversation_text}"

        packet = ContextPacket(
            engagement_id=self.engagement_slug,
            phase_name=self.phase_def.get("name", "chat"),
            task_id=f"{self.engagement_slug}-{len([m for m in self._messages if m['role'] == 'user'])}",
            spec_content=full_spec,
            architecture_rules=[],
            target_directory=self.root,
            output_contract=OutputContract(),
            constraint_section={
                "agent_role": agent_role,
                "temperature": 0.7,
                "max_tokens": 16384,
            },
        )

        # Create runner and backend
        from harness.agents.runner import AgentRunner
        from harness.agents.backends.api_backend import ApiBackend
        from harness.agents.plugin_registry import PluginRegistry

        PluginRegistry.initialize()

        backend = ApiBackend()
        runner = AgentRunner()

        # Prepare invocation
        invocation = await backend.prepare(packet)

        # Set up resolved config from .harness/providers.yaml
        resolved_config = self._resolve_provider_config()
        if resolved_config:
            invocation.resolved_config = resolved_config
        else:
            invocation.resolved_config = {}

        # Set model from config or default
        if resolved_config and resolved_config.get("model"):
            invocation.model = resolved_config["model"]

        # Attach RepoTool via runner
        runner._attach_repo_tool(packet, invocation)

        # Run with streaming
        full_response = ""
        async for chunk in backend.run_stream(invocation):
            full_response += chunk
            yield chunk

        # Store the response in messages for history
        if full_response:
            # Avoid duplicating if stream already stored it
            if (
                not self._messages
                or self._messages[-1].get("role") != "assistant"
                or self._messages[-1].get("content") != full_response
            ):
                self._messages.append({
                    "role": "assistant",
                    "content": full_response,
                })

    def _resolve_provider_config(self) -> dict | None:
        """Resolve provider config from .harness/providers.yaml or env vars."""
        try:
            return resolve_provider(self._project_root)
        except Exception:
            return None

