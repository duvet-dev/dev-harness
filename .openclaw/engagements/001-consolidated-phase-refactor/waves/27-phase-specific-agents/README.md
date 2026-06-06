# Wave 27 — Phase-Specific Agents

**Milestone:** 4 — Architecture Features
**Effort:** 5-8h
**Status:** 📋 Pending
**Depends on:** Wave 22
**Blocks:** Nothing

## Summary

The session orchestrator currently uses a single generic `chat_agent`. Create dedicated per-phase agents with phase-specific system prompts and context. Each phase becomes a distinct conversation the user enters via `/assess`, `/requirements`, `/design`, `/plan`, or `/build`.

## Tasks

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Create 5 phase agents in agent_registry.py | 📋 Pending | assessment-agent, requirements-agent, design-agent, planning-agent, build-agent |
| 2 | Wire /assess, /requirements, /design, /plan, /build commands | 📋 Pending | Phase-entry commands that instantiate the correct agent |
| 3 | Auto mode loop | 📋 Pending | creator → critics → convergence → validator |
| 4 | Manual override | 📋 Pending | User can interrupt, review, redirect at any point |
| 5 | Incorporate Wave 16b scope | 📋 Pending | Boundary test generation, architecture debt detection |
| 6 | Tests | 📋 Pending | |

## Verification

`harness session` → `/assess` → user talks to assessment-agent. Phase-specific system prompt loaded with correct context.
