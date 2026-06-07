# Task 4 — Fix /chat command provider keyword argument

**Status:** 📋 Pending
**Wave:** 32-health-fixes
**Dependencies:** None
**Effort:** 0.5h

## Description

`ChatTypedHandler.handle()` at `session_handlers.py:85` calls:

```python
provider = resolve_provider(root)
SessionClient(root, provider=provider, verbose=True)
```

But neither `SessionClient` (line 334) nor `InteractiveClient` (line 163) accept `provider=` or `verbose=` keyword arguments:
- `InteractiveClient.__init__` takes `api_key`, `base_url`, `model`, `provider_type`, `system_prompt`, `timeout_seconds`
- `SessionClient.__init__` takes `root`, `engagement_slug`, `phase_def`, `context_tier`, `system_prompt`

## Fix

Option A: Use low-level `InteractiveClient` — extract fields from provider dict:
```python
provider = resolve_provider(root)
client = InteractiveClient(
    api_key=provider["api_key"],
    base_url=provider.get("base_url", "https://api.deepseek.com"),
    model=provider.get("model", "deepseek-v4-pro"),
)
```

Option B: Use high-level `SessionClient` — load phase definition from `phases.yaml`:
```python
from harness.session.phase_source import get_phases
phases = get_phases(root)
phase_def = next((p for p in phases if p["name"] == command.phase), phases[0])
client = SessionClient(root, command.slug, phase_def, context_tier=command.context_tier)
```

Prefer Option B since the command is supposed to open a full interactive session. But since the handler returns a `ChatResult` immediately (not streaming), and the actual session runs elsewhere, Option A may be simpler for validation. Either way, the keyword error must be fixed.

## Acceptance Criteria

- [ ] `/chat` in `harness shell` no longer produces "Error: __init__() got an unexpected keyword argument 'provider'"
- [ ] Session still opens correctly (or returns appropriate error for missing engagements)
