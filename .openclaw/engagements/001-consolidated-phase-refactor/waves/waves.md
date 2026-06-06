# Dev Harness - Waves Plan

> **Purpose:** Single view of all waves - completed and planned.
> **Engagement:** consolidated-phase-refactor
> **Updated:** 2026-06-07
> **Principle:** Zero legacy/compatibility shims in target state.
> **Source:** Crichton Design Convergence (2026-06-06)

---

## Completed (18 waves)

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
| **10** | Workflow Orchestration Model | ✅ Model (260), orchestrator (526), ripple_engine (633). Workflow registry and phase advancement. **Gap:** Ripple engine unwired (→ Wave 25). |
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

---

## Task Tracking

Each wave has its own directory with:
- `README.md` — wave summary with task table and status
- `tasks/` — individual task files with acceptance criteria and verification
- `artifacts/` — build outputs, reports, design decisions

When a build coordinator works on a wave, it must create and update task files as it progresses. Status per task: 📋 Pending → 🔧 In Progress → ✅ Complete.

---

## Wave Plan: Path to Clean State

11 new waves, ~46-66h total effort. Two foundation waves unblock everything.

### Dependency Flow

```
Milestone 1: Foundation
  Wave 21: Fleet→Team Migration [6-10h] ← FIRST, blocks everything
    ↓
  Wave 22: Phase System Consolidation [5-8h]
    ├──→ Wave 23: Template Format Alignment [4-6h] (can start after 21)
    ├──→ Wave 25: Wire Ripple Engine [3-5h]
    ├──→ Wave 26: Live Artifact Writing [8-12h]
    └──→ Wave 27: Phase-Specific Agents [5-8h]

Milestone 2: Analysis Pipeline
  Wave 24: Wire refactoring-analyser + rename constants [3-5h] ✅
  Wave 31: Findings Registry [3-5h]

Milestone 3: Cleanup (independent of phase changes)
  Wave 28: Command Bus & Presenter Consolidation [5-8h]
  Wave 29: Value Objects & Type Cleanup [2-3h]
  Wave 30: OpenClaw Sync Removal [1.5h]
```

**Critical path:** 21 → 22 → [25, 26, 27] = ~27-38h
**Parallel tracks:** [23, 24, 31, 28, 29, 30] = ~19-29h
**Total:** ~46-66h

---

### Milestone 1: Foundation (Unblock Everything)

#### Wave 21 - Fleet→Team Migration
**Effort:** 6-10h | **Depends on:** None | **Priority:** 🔴 Blocker

The codebase has `fleets.yaml` alongside `teams.yaml`. `session/helpers.py` uses `"fleets"` keys in PHASES dicts. CLI has a `fleet` command group with 6 subcommands. `FleetListCommand` is a registered typed command. All of this must be unified onto the `team` concept.

**Step 1 (3-5h):** Rename `"fleets"` → `"teams"` in helpers.py PHASES dicts (lines 31, 61, 88, 120, 164, 203, 232, 257, 337, 376, 423, 1075). Genuine no-op - lookup already resolves through TeamRegistry.

**Step 2 (1-2h):** Update health service to use TeamRegistry instead of `get_fleets_path()`.

**Step 3 (1h):** Delete `fleets.yaml`, remove `_FLEETS_FILE` and `get_fleets_path()` from `paths.py`. Rename CLI `fleet` group → `team` (6 subcommands). Rename `FleetListCommand`/`FleetListTypedHandler` → `TeamList*`. Update `setup.py` registration.

**Step 4 (1-2h):** Update test references. All ~1,852 tests pass.

**Verification:** `grep -r "fleets" src/ tests/ .harness/` → zero hits (excluding deprecation aliases).

---

#### Wave 22 - Phase System Consolidation
**Effort:** 5-8h | **Depends on:** Wave 21 | **Priority:** 🔴 Blocker

Session orchestrator uses old PHASES dict from `helpers.py` exclusively. `phases.yaml` is loaded for workflow config but not session execution. Two parallel systems - neither fully dominant. This blocks every Doc 1 feature (live artifacts, phase agents, ripple effects).

**Tasks:**
1. Migrate session orchestrator to load phases from `phases.yaml` via `PhaseBuilder` instead of `helpers.py` PHASES dict
2. Add missing fields to `phases.yaml`: `chat_agent`, `reentry`, `system_prompt`
3. Remove old PHASES dict from `helpers.py` (or minimal compatibility shim → delete in cleanup)
4. Wire `session_orchestrator.py:switch_to_phase()` with navigation rails (allowable source→destination transitions)
5. Re-wire ContextLoader calls for phase-level context bundles from `phases.yaml`
6. All ~1,852 tests pass

**Verification:** Session orchestrator has zero references to `helpers.py` PHASES dict. All phase definitions from `phases.yaml`.

---

### Milestone 2: Quick Wins

#### Wave 23 - Template Format Alignment
**Effort:** 4-6h | **Depends on:** After Wave 21 (preferable, not required)

Fix 7 format gaps between `phases.yaml` inline steps and `step_templates.yaml`.

1. **FMT-1 (0.5h):** Add `input:` declarations to all 9 simple templates
2. **FMT-5 (0.5h):** Add `loop:` usage example to `phases.yaml` to exercise the critic loop code path
3. **FMT-2 (0.1h):** Update `Step.role` docstring to document loop-only semantics
4. **FMT-4 (2-3h):** Add `sub_steps: list[Step]` to `LoopConfig` in `phase/model.py`. Remove context-injection hack from `template_registry.py:55` and `step_executor.py:186-195`
5. **P6 (1h):** Deprecate duplicate `input_artifact_names`/`output_artifact_name` on `StepTemplate`

---

### Milestone 3: Analysis Pipeline

#### Wave 24 - Wire Refactoring-Analyser + Rename Constants ✅
**Effort:** 1.5h (tasks 1-4 already done) | **Status:** ✅ Complete

The refactoring-analyser (`P11_REFACTORING_ANALYSER`) was already wired in `assessment.py` — `_run_refactoring_analysis()` existed, scheduled parallel with P10, merged via `_merge_agent_output()`, included in synthesis. All opaque P1/P2/.../P11 constant prefixes renamed to descriptive names throughout the codebase.

**Completed:**
- Tasks 1-4: Already done in assessment.py — verified
- Task 5: All P-constants renamed: `P1_PROJECT_PROFILER`→`PROJECT_PROFILER`, etc. across `agents.py`, `assessment.py`, `__init__.py`, `test_analysis_agents.py`
- Task 6: 1 new refactoring-analyser merge test. All 3,827 tests pass.
- Zero `P1_`/`P2_`/etc. remain in `src/` or `tests/`

#### Wave 31 - Findings Registry
**Effort:** 3-5h | **Depends on:** None | **Independent**

Issues raised by any feedback loop — observer analysis, architecture critic loop, develop-test-validate loop, human review — currently produce one-shot reports with no memory between runs. No issue IDs, no resolution tracking, no regression detection.

**Design:** See `design/design.md §4.4` for full schema and lifecycle.

**Schema:** `findings.yaml` per engagement with `id`, `source`, `severity`, `status`, `description`, `references`, `requires_human_signoff`, `resolution`.

**Lifecycle:** `open → acknowledged → in_progress → resolved → regression`

**Tasks:**
1. Create `FindingsStore` class — reads/writes `findings.yaml` at `.harness/engagements/<slug>/findings/`
2. Wire synthesis agent to persist findings to registry instead of one-shot report
3. Add delta detection: new vs resolved vs regressed vs wont-fix-regression
4. Add `requires_human_signoff` flag — findings stay in `resolved/pending_verification` until confirmed
5. Wire wave-plan to declare resolved findings: wave metadata `resolves: ["F-001", "F-003"]`
6. Tests: persistence across runs, delta detection, regression flags, human sign-off flow

---

#### Wave 25 - Wire Ripple Engine
**Effort:** 3-5h | **Depends on:** Wave 22

`workflow/ripple_engine.py` (633 lines, 21KB) is imported by **nothing**. Dead code.

1. Import `WorkflowRippleEngine` into `workflow/orchestrator.py` or `phase/orchestrator.py`
2. Wire ripple detection into phase transition logic
3. Add `RippleEvent` emission on phase completion
4. Tests for end-to-end detection and event flow

---

### Milestone 4: Architecture Features

#### Wave 26 - Live Artifact Writing
**Effort:** 8-12h | **Depends on:** Wave 22

Phase artifacts are written only at phase END (`_write_phase_artifact()` at `session/helpers.py:608`). Must be written immediately.

1. Build `ArtifactWriter` class - writes immediately, not deferred
2. Wire into session orchestrator - artifacts persist mid-session
3. Wire into phase loop: after each `creator` step in a critic loop
4. Tests: artifact observable mid-phase, not just end-of-phase

---

#### Wave 27 - Phase-Specific Agents
**Effort:** 5-8h | **Depends on:** Wave 22

Session orchestrator uses a single generic `chat_agent`. The design calls for dedicated per-phase agents with phase-specific system prompts and context.

1. Create 5 phase agents: `assessment-agent`, `requirements-agent`, `design-agent`, `planning-agent`, `build-agent`
2. Wire `/assess`, `/requirements`, `/design`, `/plan`, `/build` commands
3. Auto mode loop: creator → critics → convergence → validator
4. Manual override: user can interrupt, review, redirect
5. Incorporate Wave 16b scope: boundary test generation, architecture debt detection

---

### Milestone 5: Command & Presenter Consolidation

#### Wave 28 - Command Bus & Presenter Consolidation
**Effort:** 5-8h | **Depends on:** None | **Independent**

Typed command architecture is half-done. Fresh bus per dispatch (13x). 32/45 commands use old factory dispatch. REPL has COMMAND_MAP + Click fallback. `cli/main.py` is 2,408 lines.

1. Single shared CommandBus - one per app lifetime, remove 13 `create_bus()` calls
2. Move all factory functions from `cli/commands.py` to typed commands
3. Remove `dispatch_cli_command()` - all 45 commands through `bus.dispatch()`
4. Expand `CliPresenter` - type-specific formatting for all result types
5. Expand `ReplPresenter` - ANSI formatting with type-specific logic
6. Remove `COMMAND_MAP` from `repl.py:203`, Click fallback from `repl.py:595-596`
7. Delete `cli/commands.py`
8. **Target:** `cli/main.py` from 2,408 → ~800 lines

---

### Milestone 6: Polish

#### Wave 29 - Value Objects & Type Cleanup
**Effort:** 2-3h | **Depends on:** None | **Independent**

1. Add `PhaseName` value object with validation to `domain/enums.py`
2. Add `EngStatus` enum (`created`, `in_progress`, `completed`, `aborted`)
3. Add `WaveId` value object (`id: str`, `title: str`)
4. Move value objects to `command/values.py` (or keep in `domain/enums.py`)
5. Expand `ReplPresenter` for all result types

---

### Milestone 7: Decontamination

#### Wave 30 - OpenClaw Sync Removal
**Effort:** 1.5h | **Depends on:** None | **Independent**

The harness must not know about OpenClaw. Delete the entire sync module.

**Remove files:**
- `src/harness/sync/` - 5 files, 724 lines
- `src/harness/agents/builtin/sync_agent.py` - 21 lines
- `tests/unit/sync/` - 5 files, 915 lines

**Remove references:**
- `src/harness/cli/main.py:544-560` - `harness agent run sync` command
- `src/harness/agents/__init__.py:28` - sync agent import
- `src/harness/agents/agent_registry.py:384-398` - SYNC_AGENT block

**Total deleted:** ~1,700 lines, zero dependencies to untangle (self-contained module).

**Verification:**
```
grep -r "sync_agent\|SYNC_AGENT\|harness.sync" src/ tests/  → zero hits
grep -r "OpenClaw" src/                                      → zero hits
find src/harness/sync -type f                                → directory gone
```

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
