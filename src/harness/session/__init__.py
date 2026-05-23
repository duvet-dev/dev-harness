"""Interactive session module — chat and phase-based agent orchestration.

Provides:
- ``InteractiveClient`` — direct LLM API caller with streaming
- ``SessionClient`` — tool-aware streaming via AgentRunner + ApiBackend
- ``chat_loop`` — interactive terminal prompt loop
- ``session_loop`` — phase-by-phase orchestration flow
- ``resolve_provider`` — reads .harness/providers.yaml and resolves ENV vars
"""

from .client import (
    ChatMessage,
    ChatTranscript,
    InteractiveClient,
    SessionClient,
    resolve_env_vars,
    resolve_provider,
)
from .loop import chat_loop, session_loop
from .types import SessionType, confirm_session_type, detect_session_type

__all__ = [
    "InteractiveClient",
    "SessionClient",
    "ChatMessage",
    "ChatTranscript",
    "resolve_provider",
    "resolve_env_vars",
    "chat_loop",
    "session_loop",
    "SessionType",
    "detect_session_type",
    "confirm_session_type",
]
