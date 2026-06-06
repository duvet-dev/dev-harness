# Dev Harness — Combined Design

> **Purpose:** Single evolving design document for the Dev Harness platform. Updated through review cycles.
> **Engagement:** consolidated-phase-refactor
> **Status:** Active
> **Last reviewed:** 2026-06-02 (Workflow Architecture v3)
> **Next review:** TBD

---

## 0. Executive Summary

The Dev Harness is an agent orchestration CLI tool that coordinates AI-backed development workflows. It embeds philosophical principles (Domain-Driven Design, Clean Architecture, agile iteration) into the development process itself — not as guidelines but as enforced/guided patterns.

**Core philosophy:** An agent orchestration system where the process itself is the product. The harness guides agents through phases (requirements → understand → design → build → review → test) using a constitution, agent fleet, and analysis pipeline.

**Tech stack:** Python 3.12+, Click CLI, DeepSeek V4 Pro (primary model), Temporal (workflow engine).

---

## 1. Architecture Overview

### 1.1 High-Level Process Flow

```
 INITIATION      GATE       GATE        GATE        GATE
 ┌─────────┐    ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
 │REQUIREMENTS│──→│UNDERSTAND│→│DESIGN/  │→│BUILD   │→│REVIEW/ │
 │GATHERING │    │ & DOMAIN│ │ARCHITECT│ │(PHASED)│ │MERGE   │
 └─────────┘    └─────────┘ └─────────┘ └─────────┘ └─────────┘
      │               │           │           │           │
      ↓               ↓           ↓           ↓           ↓
 ┌───────────┐ ┌──────────┐ ┌─────────┐ ┌────────┐ ┌──────────┐
 │• Research │ │• Domain  │ │• DDD    │ │• Stories│ │• Tests  │
 │• Challenge│ │ analysis │ │  aggrs. │ │ →tasks │ │• Docs   │
 │• Stories  │ │• Ubiquit.│ │• Entities│ │• CI/CD │ │• Demo   │
 │• Accept.  │ │ language │ │• Value   │ │• TDD   │ │• Sign-off│
 │  criteria │ │• Context │ │  objects │ │• Iterate│ │         │
 │           │ │  mapping │ │• Services│ │• Peer  │ │         │
 │           │ │• Event   │ │• Hex arch│ │  review│ │         │
 │           │ │  storming│ │• Bounds  │ │        │ │         │
 └───────────┘ └──────────┘ └─────────┘ └────────┘ └──────────┘
         │            │          │            │           │
         └────────────┴──────────┴────────────┴───────────┘
                              │
                         ┌────┴────┐
                         │SUMMARY &│
                         │ANALYSIS │
                         │ (Two-Tier)│
                         └─────────┘
```

### 1.2 Core Modules

| Module | Purpose | Status |
|--------|---------|--------|
| `harness/cli.py` | Click CLI — all user-facing commands | ✅ Built (needs splitting) |
| `harness/agents/` | Agent registry, runner, backends (API/CLI/Editor) | ✅ Built |
| `harness/analysis/` | Fast/deep scan, observer, assessment pipeline (10 analysis agents) | ✅ Built |
| `harness/plan/` | Wave model, plan management | ✅ Built |
| `harness/session/` | Chat/session loops, interactive client | ✅ Built |
| `harness/shell/` | REPL (`harness shell`) | ✅ Built |
| `harness/engagement/` | Lifecycle commands, rename | ✅ Built |
| `harness/context/` | ContextLoader — 3-tier engagement context bundles | ✅ Built |
| `harness/state/` | State management, Temporal integration | ✅ Built |
| `harness/config/` | Configuration manager, provider registry | ✅ Built |
| `harness/constitution/` | Constitution models, loader, templates | ✅ Built |
| `harness/workflows/` | Temporal workflows, activities, signals | ✅ Built |
| `harness/refactor/` | Refactoring loop, suggestions, verification | ✅ Built |
| `harness/tools/` | Web search, RepoTool | ✅ Built |
| `harness/scm/` | Git adapter, .gitignore management | ✅ Built |
| `harness/sync/` | OpenClaw sync (extract, map, apply, pipeline) | ✅ Built |

### 1.3 Module Tree

```
harness/
├── __init__.py
├── cli.py                        # Click CLI (2800 lines — needs splitting)
├── entry.py                      # Entry point
├── agents/
│   ├── agent_registry.py         # 12+ agent roles, AgentSpec, ToolPermissions
│   ├── runner.py                 # AgentRunner — critic loop, tool injection
│   ├── detectors.py              # Project type, language, framework detection
│   ├── backends/                 # API, CLI, Editor backends
│   │   ├── base.py               # Abstract backend interface + tool registry
│   │   ├── api_backend.py        # Direct LLM API calls (function-calling loop)
│   │   ├── cli_backend.py        # Subprocess CLI tools (Claude Code, Aider)
│   │   ├── editor_backend.py     # Spec files for editors
│   │   └── formatters.py         # Tool format converters
│   ├── builtin/sync_agent.py     # Synchronous agent execution
│   ├── conformance_reviewer.py
│   ├── context_builder.py
│   ├── domain_tester.py
│   ├── governance.py
│   ├── pattern.py
│   └── validator.py
├── analysis/
│   ├── agents.py                 # All analysis agent definitions (project-profiler through refactoring-analyser)
│   ├── assessment.py             # Async assessment runner, scoring, synthesis
│   ├── observer.py               # Observer mode entry point
│   ├── base.py                   # Base analysis types
│   ├── fast.py                   # Fast scan (structure, git diff)
│   ├── deep.py                   # Deep analysis (arch conformance, coverage, dead code)
│   └── summary.py                # Summary formatting
├── plan/                         # WavePlan, Task, Phase task model + plan manager
├── session/                      # Main session loop, client, interactive, commands
├── shell/                        # REPL — Click introspection
├── engagement/                   # Lifecycle commands, rename
├── context/                      # ContextLoader — 3-tier bundle, cache, sandbox
├── state/                        # Store, snapshot, freshness, reconciliation, Temporal
├── config/                       # Config manager, provider registry
├── constitution/                 # Constitution models, loader, templates
├── workflows/                    # Temporal workflows, activities, signals
├── tools/                        # RepoTool, web search
├── refactor/                     # Refactoring loop, suggestions, verification
├── scm/                          # Git adapter, .gitignore management
├── sync/                         # OpenClaw sync pipeline
├── docs/                         # Changelog, documentation generator
├── wave/                         # Wave cycle runner
└── templates/                    # Agent definition templates
```

---

## 2. Data Model

### 2.1 Engagement Hierarchy
```
Engagement (top-level chunk of work)
  └── Milestones (logical grouping, externally meaningful)
       └── Waves (phase-agnostic, PR-sized)
            └── Tasks (with phase labels)
```

### 2.2 Key Entities

**`Engagement`** — `.harness/engagements/<slug>/engagement.json`
- slug, name, created/closed dates, milestones[], session-type override, refactoring-suggestions override

**`Wave`** — `plan.yaml` (within engagement directory)
- Phase-agnostic batch. Labels: name, description, tasks[], status

**`Task`** — element within Wave
- `phase` label: requirements/understand/design/build/review/test

**`Constitution`** — `constitution.yaml`
- Purpose, rules, guiding principles, flag settings

**`Plan`** — structured wave + task hierarchy in `plan.yaml`

### 2.3 Phase State Model

```
NOT_STARTED → ACTIVE → COMPLETED
              ↓ (feedback)
         FEEDBACK_SENT → FEEDBACK_WAIT → ACTIVE (revised)
```

Cross-phase navigation has pause/checkpoint semantics with structured feedback packets.

---

## 3. Agent System

### 3.1 Agent Registry

**12+ registered roles** in `agent_registry.py`:

| Role | Backend | Tools | Tags |
|------|---------|-------|------|
| `coordinator` | API | read-only | meta |
| `requirements-builder` | API | read-only | requirements |
| `architect` | API | read+write (design/) | architecture |
| `architecture-analyser` | API | read-only | architecture,review |
| `planning-agent` | API | read+write (plan/) | planning |
| `coding-agent` | API | read+write unrestricted | coding |
| `testing-agent` | API | read+write (tests/) | testing |
| `critical-analyser` | API | read+write (reviews/) | review |
| `validation-agent` | API | read-only | review |
| `documentation-agent` | API | read+write (docs/) | docs |
| `example-scenarios-agent` | API | read+write (docs/examples/) | docs |
| `discovery-agent` | API | read-only | research |

### 3.2 Tool System

**RepoTool** — sandboxed filesystem tool (4 operations):
- `read(path)` — Read file relative to repo root (1 MB limit)
- `write(path, content)` — Write content (500 KB limit)
- `list(path)` — List directory contents
- `exists(path)` — Check if path exists

Sandboxed to repo root via `_resolve()` with symlink prevention. Per-file `threading.Lock` for concurrent writes. 3 permission constructors: `read_only()`, `restricted_write(prefixes)`, `unrestricted()`.

### 3.3 Backends

| Backend | Mode | Use Case |
|---------|------|----------|
| `ApiBackend` | Direct LLM API | Primary — function-calling loop, tool execution |
| `CliBackend` | Subprocess | Claude Code, Aider — CLI tool integration |
| `EditorBackend` | Spec files | Cursor, VS Code — structured spec output |

### 3.4 Session Loops

| Loop | Purpose |
|------|---------|
| `chat_loop` | Direct user ↔ agent conversation |
| `session_loop` | Structured engagement execution with phase navigation |

SessionClient wraps AgentRunner + ApiBackend for tool-aware streaming in both loops.

### 3.5 REPL

`harness shell` — Click introspection auto-registers all CLI commands as `/command-name [args]`. Tab auto-complete. History persisted.

---

## 4. Analysis Pipeline

### 4.1 Pipeline Architecture

```
harness observe --deep <path>
  │
  ├─ Fast scan (static)
  │   └─ structure, git diff, arch conformance, coverage, dead code
  │
  ├─ Primary analysis agents (sequential, LLM, static context snapshot)
  │   ├─ project-profiler
  │   ├─ responsibility-decoder
  │   ├─ architecture-critic
  │   ├─ code-critic
  │   ├─ test-auditor
  │   ├─ security-auditor
  │   ├─ dependency-analyser
  │   └─ documentation-reviewer
  │
  ├─ Deep analysis agents (parallel, RepoTool access, deep reads)
  │   ├─ critical-reviewer — cross-cutting issues, contract violations
  │   └─ refactoring-analyser — duplication, missing abstractions
  │
  └─ synthesis — unified report with cross-dimension linking
      └─ Writes to Findings Registry (§4.4)
```

### 4.2 Key Design Decisions

1. **Sequential agent execution** — Primary agents run one at a time, not concurrent. Prevents API rate limiting and timeout degradation.
2. **Static context snapshot for primary agents** — 20 files, ~80 KB snapshot. Agents navigate via RepoTool for deeper access.
3. **Deep analysis agents run after primary agents** with full RepoTool access. Read primary analysis outputs for cross-referencing.
4. **Deep analysis agents run in parallel** — critical-reviewer focuses on cross-cutting issues, refactoring-analyser on abstraction/duplication.
5. **Synthesis** — Combines all findings, links across dimensions, persists to Findings Registry.

### 4.3 Analysis Agents

| Agent | Focus |
|-------|-------|
| **project-profiler** | Codebase structure, language, dependencies |
| **responsibility-decoder** | Purpose, what the software does |
| **architecture-critic** | Module structure, boundary violations |
| **code-critic** | Code quality, naming, complexity |
| **test-auditor** | Coverage gaps, test quality |
| **security-auditor** | Vulnerabilities, supply chain risks |
| **dependency-analyser** | Dead deps, circular deps, version conflicts |
| **documentation-reviewer** | Doc quality, coverage, consistency |
| **critical-reviewer** | Cross-cutting: contract violations, phantom roles, concurrency gaps, stub implementations, test quality, version/platform gaps, effort estimation, regression risk |
| **refactoring-analyser** | Duplication, missing abstractions, boundary clarity, cross-module leakage, layering violations |

### 4.4 Findings Registry (Cross-Cutting)

Issues raised by any feedback loop — observer analysis, architecture critic loop, develop-test-validate loop, or human review — must be persisted in a **Findings Registry** at the engagement level. This replaces the current one-shot analysis report with a durable, diffable issue tracker.

#### Schema

```yaml
findings:
  - id: "F-001"
    source: "architecture-critic"      # Which agent/loop raised it
    scope: "observer"                  # observer / critic-loop / dev-test-loop / human
    description: "CLI god module — 2,408 lines, 17% coverage"
    severity: "critical"               # critical / high / medium / low / info
    status: "open"                     # open / acknowledged / in_progress / resolved / wont_fix / regression
    references:
      file: "src/harness/cli/main.py"
      line: 1
    requires_human_signoff: true        # Whether closure needs human confirmation
    resolution:
      wave: "wave-28"
      notes: "Split into per-domain CLI modules"
    raised_at: "2026-06-06T19:00:00Z"
    resolved_at: null
```

#### Lifecycle

```
open → acknowledged (human seen it) → in_progress → resolved
  ↓                                                     ↓
  └→ wont_fix (accepted as intentional)           regression (reappears on re-analysis)
```

#### Delta Detection

On each analysis run, the findings registry is compared against the current state:
- **New**: Finding detected that wasn't in the registry → added as `open`
- **Resolved**: Previously `open` finding no longer detected → auto-marked `resolved`
- **Regression**: Previously `resolved` finding detected again → marked `regression`
- **Wont-fix regression**: Previously `wont_fix` finding detected → flagged for human review
- **Human sign-off required**: Findings with `requires_human_signoff: true` stay `resolved` but show a `pending_verification` marker until confirmed

#### Storage

`.harness/engagements/<slug>/findings/findings.yaml` — engagement-level, persistent across analysis runs.

#### Cross-Loop Integration

The Findings Registry is not limited to the observer pipeline:
- **Architecture critic loop**: critic agent raises findings directly into the registry
- **Develop-test-validate loop**: issues found during implementation/testing go into the registry
- **Human review**: reviewers can add findings manually via CLI or by editing the findings file
- **Wave tracking**: a wave can declare which findings it resolves: `resolves: ["F-001", "F-003"]`

---

## 5. Engagement Lifecycle

### 5.1 Commands

| Command | Purpose |
|---------|---------|
| `harness engagement create <name>` | Create engagement, switch branch |
| `harness engagement set-active <slug>` | Set active engagement |
| `harness engagement list` | List all engagements |
| `harness engagement status` | Show current engagement details |
| `harness engagement close <slug>` | Finalise engagement |
| `harness engagement rename <old> <new>` | Rename engagement with branch strategy |
| `harness work <description>` | Start autonomous work session |
| `harness wave create <name>` | Create wave in current engagement |
| `harness shell` | Interactive REPL |

**Storage:** Active engagements tracked in `.harness/active-engagements.yaml` (branch→slug mapping).

### 5.2 Design: Phase State & Navigation
- Extended state model with PAUSED, FEEDBACK_SENT, FEEDBACK_WAIT
- Bidirectional navigation with checkpoint/restore
- Structured feedback packets from build back to design

### 5.3 Design: Commit Strategy
- Writes to engagement directories (`.openclaw/engagements/<slug>/`)
- Plans to support auto-commit on phase transitions
- Rollback to previous commit via hash

### 5.4 Design: Fleet Architecture
- 4 fleets: Architecture, Coding, Review, Testing
- Fleet guidelines define input/output protocols, cooperation rules, phase participation
- Pattern injection from `.harness/patterns/`
- 3 governance levels: exploration, standard, strict

### 5.5 Design: Refactoring Session Type
- Separate session loop with its own phase sequence:
  1. intent-discovery
  2. architecture-proposal
  3. migration-assessment
  4. boundary-test-generation
  5. refactoring
  6. verification
- Boundary test generation at application interfaces
- Architecture debt detection with rule-based scanning

---

## 6. Build Rules & Standards

| Rule | Value |
|------|-------|
| Language | Python 3.9+ (3.12+ target) |
| Orchestration | Temporal (Wave 6+) |
| Primary Model | DeepSeek V4 Pro |
| Sub-agent timeout | 30 min per task |
| Max retries per feedback loop | 5 |
| End-of-wave coverage | 90%+ |
| Tests | Every component |
| Documentation | Every wave |
| Example scenarios | Every wave |
| Decision log | Per wave |
| Language agnosticism | Default for all analysis/generation |

---

## 7. Design Review History

| Date | Document | Reviewer | Outcome |
|------|----------|----------|---------|
| 2026-05-17 | Wave 11 Design | architecture-analyser | 3 blockers found, resolved |
| 2026-05-19 | Wave 13 RepoTool Design | architecture-analyser | Approved |
| 2026-05-20 | Wave 14 Context Loading | architecture-analyser | Approved |
| 2026-05-22 | Wave 16c Engagement Rename | architecture-analyser | Approved |
| 2026-05-22 | Wave 17 Fleet Expansion | architect | Drafted |
| 2026-05-24 | P10/P11 Pipeline Integration | Crichton | Approved |
| 2026-05-27 | CV v10 Requirements (external) | Pending Crichton | — |
| 2026-05-30 | Refactoring Plan V1-V3 | Crichton 🎯 | Accept w/ caveats |
| 2026-06-02 | Workflow Architecture v3 | architecture-analyser | ✅ Verified in code |
| 2026-06-06 | Design Convergence Analysis | Crichton 🎯 | **Migration stalled at halfway** (see §8) |

---

## 8. Crichton Convergence Analysis (2026-06-06)

**Worksheet:** `Research/Dev Harness/build/deliverables/crichton-design-convergence-worksheet.md`
**Five docs analysed:** Session-Phase-Architecture-Redesign, Typed Command Architecture Design, Refactoring-Abstraction-Analyser, Architect Step Template Migration Plan, Crichton Step Template Format Review

### 8.1 Core Finding: Two Parallel Systems

The codebase runs **two parallel systems** and the migration from old to new is stuck at the halfway point:

| Old System | New System | Status |
|-----------|------------|--------|
| `session/helpers.py` PHASES dict with `"fleets"` keys | `phases.yaml` with `team:` references | ❌ Both active, no migration done |
| `fleets.yaml` | `teams.yaml` + TeamRegistry | ❌ `fleets.yaml` still has live code refs |
| Legacy `Command` + `CommandResult` | `TypedCommand` + `TypedResult` | 🔧 **Parallel addition**, not clean replacement |
| `cli/commands.py` factory fns (32 uses) | `bus.dispatch(cmd)` (13 uses) | ❌ Both used, old dominates |
| `session/commands.py` internal CommandResult | `command/results/*.py` typed results | ❌ Session has own independent type |

### 8.2 Key Findings

**BLOCKERS:**
1. **`fleets.yaml` has live code references** — `paths.py`, `health_service.py`, `session/helpers.py`, CLI fleet group. Can't delete without migration. Both `fleets.yaml` and `teams.yaml` coexist. **(Doc 4/5, 6-10h)**
2. **Two parallel phase systems** — Session orchestrator uses old PHASES dict exclusively. `phases.yaml` is used by workflow but not sessions. Every Doc 1 proposal (live artifacts, phase-specific agents, ripple effects) depends on unification. **(5-8h)**

**DEAD CODE:**
- **P11 agent** defined at `analysis/agents.py:792` but never wired into assessment pipeline
- **Ripple engine** (`workflow/ripple_engine.py`, 21KB) not imported by any orchestrator

**IMPLEMENTATION STATUS:**
- Typed command architecture: built **bottom-up** (types, bus, handlers) but **top-down wiring never finished** (session integration, presenter consolidation, factory removal)
- Doc 4 migration plan (dated 2026-06-02): **0/7 items executed**
- CLI `main.py`: **2,408 lines** (design target: ~500) — grew 1.8x
- REPL: **787 lines** (design target: ~300) — grew 1.7x
- **13 fresh `create_bus()` calls** in CLI instead of 1 shared bus

### 8.3 Cross-Doc Inconsistencies

| Conflict | Details |
|----------|---------|
| CI-1 | Doc 2 proposed clean break from legacy types; code added `TypedCommand` alongside old `Command`. Bus wraps typed results in legacy `CommandResult` wrappers. |
| CI-2 | Doc 2 proposed `SessionCommandFacade` for typed session integration; session has its own separate `CommandResult` type in `session/commands.py`. |
| CI-3 | Docs 4 and 5 agree on fleet→team rename; code has **zero progress** on the migration. |
| CI-4 | Doc 1 assumes `phases.yaml` is canonical; session orchestrator uses old PHASES dict exclusively. |
| CI-5 | Doc 2 claimed all Click commands use `CliPresenter`; 32/45 commands bypass presenters entirely. |
| CI-6 | Value objects (`EngStatus`, `WaveId`, `PhaseName`) from Doc 2 don't exist in domain enums. |
| CI-8 | Doc 2 predicted CLI at ~500 lines; actual is 2,408 lines. REPL predicted ~300; actual 787. |

### 8.4 Next Step Recommended

**Complete the fleet→team migration first (Doc 4, Phases A-D, 6-10h).**
1. Rename `"fleets"` → `"teams"` in helpers.py PHASES dicts (no-op rename, 3-5h)
2. Update health service to use TeamRegistry (1-2h)
3. Delete `fleets.yaml`, update `paths.py`, add deprecation warning to CLI fleet group (1h)
4. Update tests (1-2h)

Then consolidate on `phases.yaml` (B2, 5-8h), then fix format gaps, then implement Doc 1 features.

---

> **Note:** This document is the single source of truth for design intent. Individual wave design docs in the vault serve as detailed supplements and review artifacts. Update this document when designs change rather than creating standalone files.
