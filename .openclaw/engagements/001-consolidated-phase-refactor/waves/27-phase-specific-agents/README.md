# Wave 27 — Phase-Specific Agents

**Milestone:** 4 — Architecture Features
**Effort:** 5-8h
**Status:** ✅ Complete
**Depends on:** Wave 22
**Blocks:** Nothing

## Summary

The session orchestrator currently uses a single generic `chat_agent`. Create dedicated per-phase agents with phase-specific system prompts and context. Each phase becomes a distinct conversation the user enters via `/assess`, `/requirements`, `/design`, `/plan`, or `/build`.

## Tasks

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Create 5 phase agents in agent_registry.py | ✅ Complete | assessment-agent, requirements-agent, design-agent, planning-agent, build-agent |
| 2 | Wire /assess, /requirements, /design, /plan, /build commands | ✅ Complete | Phase-entry commands that instantiate the correct agent |
| 3 | Auto mode loop | ✅ Complete | creator → critics → convergence → validator |
| 4 | Manual override | ✅ Complete | User can interrupt, review, redirect at any point |
| 5 | Incorporate Wave 16b scope | ✅ Complete | Boundary test generation, architecture debt detection |
| 6 | Tests | ✅ Complete | 2,684 lines of code, 519 lines of tests, all 3,820 tests passing | |

## Verification

`harness session` → `/assess` → user talks to assessment-agent. Phase-specific system prompt loaded with correct context.
