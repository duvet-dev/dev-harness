"""Interactive session module — chat and phase-based agent orchestration.

Provides:
- ``InteractiveClient`` — direct LLM API caller with streaming
- ``SessionClient`` — tool-aware streaming via AgentOrchestrator + ApiBackend
- ``run_chat_session`` — interactive terminal prompt via SessionClient
- ``run_phase_session`` — phase-by-phase orchestration flow
- ``resolve_provider`` — reads .harness/providers.yaml and resolves ENV vars
- ``helpers`` — shared constants and utility functions (was loop.py)
- ``session_orchestrator`` — run_chat_session and run_phase_session entry points
"""

from .client import (
    ChatMessage,
    ChatTranscript,
    InteractiveClient,
    SessionClient,
    resolve_env_vars,
    resolve_provider,
)
from .session_orchestrator import run_chat_session, run_phase_session
from .guidance import SessionGuidanceInjector, get_guidance, should_enforce_boundary_tests
from .helpers import SessionType, confirm_session_type, detect_session_type

__all__ = [
    "InteractiveClient",
    "SessionClient",
    "ChatMessage",
    "ChatTranscript",
    "resolve_provider",
    "resolve_env_vars",
    "run_chat_session",
    "run_phase_session",
    "SessionType",
    "detect_session_type",
    "confirm_session_type",
    "SessionGuidanceInjector",
    "get_guidance",
    "should_enforce_boundary_tests",
]
