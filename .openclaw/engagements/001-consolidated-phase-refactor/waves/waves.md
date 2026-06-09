# Dev Harness - Waves Plan

> **Purpose:** Single view of all waves - completed and planned.
> **Engagement:** consolidated-phase-refactor
> **Updated:** 2026-06-07 (Wave 26 added)
> **Principle:** Zero legacy/compatibility shims in target state.
> **Source:** Crichton Design Convergence (2026-06-06)

---

## Completed (21 waves)

| Wave | Name | Notes |
|------|------|-------|
| **1** | Project Foundation | ✅ Scaffold, pyproject.toml, conftest, .gitignore |
| **2** | Core Models & Interfaces | ✅ Constitution models, GitRepo adapter, ContextPacket, 7 CLI commands |
| **3** | Domain Logic Modules | ✅ Constitution loader, template registry, spec validator, state management |
| **4** | Integration | ✅ `harness init` full implementation |
| **5** | Quality Gate | ✅ 93.74% coverage gate, .gitignore generation, venv |
| **6** | Temporal State Infrastructure | ✅ ~972 lines. Adapter, server, worker, store, freshness, reconciliation. Wired for gate reviews. Narrow scope - not "sole runtime source." |
| **7** | Agent Runner & Backends | ✅ 4 backends (API 877, CLI 271, Editor 163, Formatters 524). AgentRunner dispatches correctly. |
| **8** | Analysis Suite | ✅ All 8 modules (3,770 lines). 10 analysis agents. Deep/fast pipelines. Refactoring-analyser wired. |
| **9** | Branch Management (SCM) | ✅ git.py (504 lines). Full branch ops, merge detection. Used by 15+ modules. **Genuinely complete.** |
| **10** | Workflow Orchestration Model | ✅ Model (260), orchestrator (526), ripple_engine (633). Workflow registry and phase advancement. |
| **11** | Independent Assessment (R22) | ✅ P1-P5 agents, parallel dispatch, JSON extraction, 476 tests |
| **12** | Interactive Shell (REPL) | ✅ Click introspection, `/command` dispatch, tab complete, 789 tests |
| **13** | Agent Read/Write Tool (RepoTool) | ✅ Sandboxed filesystem ops, path escape, file locks, 857 tests |
| **14** | Engagement Context Loading (R23) | ✅ ContextLoader, 3-tier bundles, manifest caching, 50KB limit |
| **16c** | Engagement Rename & Generate-Docs | ✅ `harness engagement rename`, `harness generate-docs` |
| **18** | Consultation System (Option G) | ✅ CycleRunner, ConsultationOrchestrator, `/consult`, 1767 tests |
| **19** | Tools and Agents | ✅ Web Search Tool, Self-Test Loop, 1852 tests |
| **20** | Analysis Convergence (R27) | ✅ project-profiler→documentation-reviewer sequential, critical-reviewer+refactoring-analyser parallel, synthesis output. |
| **21** | Fleet→Team Migration | ✅ 7/7 tasks. 3,812 tests. `b2e91df` |
| **22** | Phase System Consolidation | ✅ 6/6 tasks. 3,826 tests + 7 new navigation rail tests. `2a6fca5` |
| **23** | Template Format Alignment | ✅ 6/6 tasks. 3,826 tests. `ed86bae` |
| **24** | Wire Refactoring-Analyser + Rename Constants | ✅ All P-constants renamed. Refactoring-analyser wired. 3,827 tests. `4e072e9` |
| **28** | Command Bus & Presenter Consolidation | ✅ Single shared bus, all typed dispatch, presenters expanded, commands.py deleted, 3,827 tests. |
| **30** | OpenClaw Sync Removal | ✅ Sync module deleted. Zero OpenClaw references in src/ or tests/. 3,757 tests. |
| **25** | Wire Ripple Engine | ✅ RippleEvent created. WorkflowRippleEngine wired into WorkflowOrchestrator. Events emitted on phase completion. 3,747 tests. |
| **26** | Live Artifact Writing | ✅ ArtifactWriter class writes immediately to `.harness/engagements/<slug>/artifacts/`. Wired into session orchestrator (mid-phase), StepExecutor (post-agent-dispatch), and InteractiveSession (post-LLM). Atomic writes, YAML frontmatter, iteration versioning, 31 new tests, 3,787 passing. |
| **27** | Phase-Specific Agents | ✅ 5 phase agents, phase-entry commands, auto mode loop, manual override. 2,684 lines. `697c33d` |
| **29** | Value Objects & Type Cleanup | ✅ PhaseName, EngStatus, WaveId value objects + type-specific ReplPresenter. `bf510a0`, `0c3b7aa` |
| **32** | Health Check & Startup Fixes | ✅ 4 startup warnings fixed, 8 missing agents added. Build 69. `a99a672` |

---

## Task Tracking

Each wave has its own directory with:
- `README.md` — wave summary with task table and status
- `tasks/` — individual task files with acceptance criteria and verification
- `artifacts/` — build outputs, reports, design decisions

When a build coordinator works on a wave, it must create and update task files as it progresses. Status per task: 📋 Pending → 🔧 In Progress → ✅ Complete.

---

## Wave Plan: Current Status

**13 of 13 waves completed.** ✅ All waves complete.

### ✓ Completed (12 waves)

| Wave | Name | Commit | Build |
|------|------|--------|-------|
| 21 | Fleet→Team Migration | `b2e91df` | — |
| 22 | Phase System Consolidation | `2a6fca5` | — |
| 23 | Template Format Alignment | `ed86bae` | — |
| 24 | Wire Refactoring-Analyser + Rename Constants | `4e072e9` | — |
| 25 | Wire Ripple Engine | `ebc650a` | — |
| 26 | Live Artifact Writing | `f3396b9` | — |
| 27 | Phase-Specific Agents | `697c33d` | 68 |
| 28 | Command Bus & Presenter Consolidation | `f3c14cb` | — |
| 29 | Value Objects & Type Cleanup | `bf510a0` | — |
| 30 | OpenClaw Sync Removal | `7d6e86e` | — |
| 32 | Health Check & Startup Fixes | `a99a672` | 69 |
| 31 | Findings Registry | _current_ | 70 |

### ✅ All Waves Complete

All 13 waves for engagement 001 (consolidated-phase-refactor) are now complete.

#### Wave 31 - Findings Registry
**Status:** ✅ Complete | **Commit:** _current_ | **Build:** _next_

FindingsStore with CRUD, delta detection, lifecycle management, human sign-off, and wave-resolution linking. 42 tests passing.

---

## Target State

When all waves are complete:

### Architecture - Single Unified System

```
phases.yaml (canonical phase definitions)
  ├── Session Orchestrator (uses phases.yaml)
  ├── Workflow Orchestrator (uses phases.yaml)
  └── Phase Orchestrator (uses phases.yaml)
        ├── Phase-Specific Agents (dedicated per phase)
        ├── Ripple Engine (wired into transitions)
        └── Live Artifact Writer (writes mid-phase)

Shared CommandBus (one per lifetime)
  ├── CLI (~800 lines, all commands through bus)
  └── REPL (~500 lines, bus-only, no COMMAND_MAP)

Teams Registry (teams.yaml only - fleets.yaml gone)

No OpenClaw references anywhere in harness source
```

### What's Gone

| Removed | Why |
|---------|-----|
| `session/helpers.py` PHASES dict | Replaced by `phases.yaml` |
| `.harness/fleets.yaml` | Replaced by `teams.yaml` |
| `cli/commands.py` factory functions | All commands typed |
| `repl.py` COMMAND_MAP + Click fallback | Bus-only dispatch |
| `src/harness/sync/` (entire module) | Harness must not know OpenClaw |
| `sync_agent` builtin | No OpenClaw references |
| `FleetList*` commands | Renamed to `TeamList*` |
| `dispatch_cli_command()` | All through `bus.dispatch()` |
| Multiple `create_bus()` calls | Single shared instance |
| Legacy `Command` + `CommandResult` | `TypedCommand` + `TypedResult` only |
| Dead code: P11 unwired, ripple engine unwired | Both wired (Wave 24 + Wave 25) |

### Zero Legacy/Compatibility Shims

No `"fleets"` keys, no `.old` files, no dual encoding, no backward compat layers, no OpenClaw references, no factory dispatch paths, no COMMAND_MAP, no dead code.
