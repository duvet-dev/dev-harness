# Dev Harness — Combined Requirements

> **Purpose:** Single view of all requirements, from original capture through detailed specs.
> **Engagement:** consolidated-phase-refactor
> **Updated:** 2026-06-06

---

## 0. Domain Language

| Term | Definition |
|------|------------|
| **Engagement** | A top-level chunk of work aimed for completion. The fundamental unit of work tracking. |
| **Milestone** | A logical grouping within an engagement (e.g. MVP, v1, v2). Externally meaningful. |
| **Wave** | A PR-sized batch of tasks. **Phase-agnostic** — a single wave can span multiple phases to deliver a coherent feature. Each wave opens its own PR, merges independently. |
| **Task (Work Item)** | A single unit of work scoped to a phase. ~1-2h of agent time. |
| **Phase** | An execution stage label on tasks. Not a container for waves. |
| **Constitution** | Per-project document defining philosophy, rules, guiding principles. |
| **Project** | A codebase managed by the harness. |
| **Artifact** | Any persisted output from a phase — documents, models, decisions. Not code. |
| **Iteration** | A review-feedback cycle within a wave. |

**Engagement hierarchy:**
```
Engagement (top-level chunk of work)
  ├── Milestone (logical grouping, externally meaningful)
  │    └── Waves (phase-agnostic, each PR-sized)
  │         └── Tasks (with phase labels: requirements, understand, design, build, review, test)
```

---

## 1. Core Requirements (R1-R21) — Original Capture

_Source: Andy voice notes, 2026-05-15. 3 messages, ~15 min total._

### R1 — Runnable Status Summaries 🔴 (Wave 5)

The harness must produce on-demand project state summaries at any point.

**R1.1:** Summary must include completed items, in-progress items (with %), open items, risks (prioritised), blockers.

**R1.2:** Priority flagging — higher-level concepts affecting build work must be highlighted.

**R1.3:** Runnable before, during, and after work.

### R2 — Autonomous Operation 🔴 (Wave 5)

**R2.1:** Self-directed execution — select and build portions of plan without manual intervention.

**R2.2:** Parallelisation of build activities where possible.

### R3 — Agent Community & Custom Agents 🔴 (Wave 7)

**R3.1:** Agent community — mix of built-in and custom agents.

**R3.2:** Agent-to-agent network — agents spawn and coordinate with other agents.

**R3.3:** Custom agent injection via `AGENTS.md` files.

**R3.4:** YAML-based agent injection into phases.

**R3.5:** Phase-triggered agent dispatch.

### R4 — Project Constitution 🔴 (Wave 1-5)

**R4.1:** `harness init` creates `constitution.yaml` with purpose, rules, flags.

**R4.2:** Existing repo init supported.

**R4.3:** Per-project constitutions in mono-repos — supported at init.

**R4.4:** Auto-run critical analysis on init.

### R5 — Critical Analysis 🔴 (Wave 8)

**R5.1:** Types — raw codebase analysis (observer), code vs architecture (deep), test coverage (coverage scan).

**R5.2:** Multi-tier: fast scan → deep analysis → full assessment.

**R5.3:** Agent vs skill distinction — resolved as skills.

### R6 — Test Strategy & Coverage 🔴 (Wave 8+)

**R6.1:** Test pyramid: business/feature > integration > unit.

**R6.2:** Test isolation rules (community standards §9).

**R6.3:** Coverage monitoring against business interfaces.

**R6.4:** Dead code detection.

**R6.5:** Lean code — aspirational.

### R7 — Flexible Workflow 🔴 (Wave 10)

**R7.1:** Gate modes: auto/manual.

**R7.2:** Full spec vs shortcut — gate mode choice.

### R8 — Cross-Cutting Concerns

**R8.1:** Review by exception — severity-filtered reports.

**R8.2:** Constraint awareness — not yet implemented.

### R9 — Design Decisions (Wave 6+9)

### R10 — Outline Audit (Waves 1-10)

### R11 — Observer Mode (Wave 8)

### R12 — Side-Channel Coding (Wave 9)

### R13 — Domain Language (Wave 1)

### R14 — Specs as Point-in-Time (Wave 9)

### R15 — Branch Management (Wave 9)

### R16 — Chat Agent / NL Interface (Wave 10)

### R17 — Configurable Project Scaffolding (Wave 5, Updated)

### R18 — Single Executable Build (Wave 10)

### R19 — Dynamic .gitignore Management (Wave 5)

### R20 — Standard Document Format / Phase Contract (Wave 2+4)

### R21 — Discovery Agent (Wave 11)

---

## 2. Expanded Requirements (R22-R27) — Detailed Specs

### R22 — Independent Repository Assessment ✅ (Wave 11)

**Source:** Andy design session, 2026-05-16

**Two-tier analysis model:**
1. **Engagement Analyser** (existing) — "Am I on track?" — needs harness state, constitution, git diff
2. **Independent Analyser** (new) — "What is this codebase?" — filesystem only, no harness state needed

**Five components:**
| Component | Name | Purpose |
|-----------|------|---------|
| P1 | Project Profiler | Codebase structure, language, dependencies |
| P2 | Responsibility Decoder | Purpose, what the software does |
| P3 | Architecture Critic | Module structure, boundary violations |
| P4 | Code Critic | Code quality, naming, complexity |
| P5 | Test Auditor | Coverage gaps, test quality |

**Invocation:** `harness summary --assess` (inside project) or `harness observe --deep` (standalone).

**Architecture critic on --deep mode** can invoke Architecture Analyser agent.
**Code critic on --deep mode** can invoke Coding Agent or Crichton.

### R23 — Engagement File Context Loading ✅ (Wave 14)

**Source:** Andy, 2026-05-19

**Requirement:** Harness agents need awareness of engagement files without filling context with entire content.

**3-tier context bundle:**
- **Tier 1 (1-2 KB):** File path tree only
- **Tier 2 (5-10 KB):** Inventory + summaries with size/mtime/headings (default)
- **Tier 3 (10-25 KB):** Full with content snippets

**Key decisions:**
- Cache with mtime-based invalidation in `.harness/engagements/<slug>/context/`
- Injected as system prompt preamble
- CLI: `--context-tier` option on `chat` and `session` commands

### R24 — Cross-Phase Navigation & Feedback Loops 📋 (Wave 15)

**Source:** Andy, 2026-05-19

**Problem:** During implementation, agents discover new constraints that should feed back into design/planning. Current linear phase model makes this awkward.

**Requirements:**
- Bidirectional phase transitions (forward AND backward)
- Structured feedback — "here's what we learned during implementation that changes the design"
- Pause/checkpoint semantics — mark progress, create context snapshot, resume after design update
- Phase state model: NOT_STARTED, ACTIVE, PAUSED, COMPLETED, FEEDBACK_SENT, FEEDBACK_WAIT
- Feedback loop protocol with structured packets and checkpoint/restore
- Design-critic loop: architect writes → critic reviews → architect revises
- Commands: `harness phase navigate`, `harness phase feedback`, `harness phase resume`, `harness phase status`
- Safety: max iterations, single-level feedback chains, checkpoint expiry

### R25 — Engagement Commit Frequency & Snapshots 🔜 (Future wave)

**Source:** Andy, 2026-05-19

**Requirement:** Automatic or semi-automatic committing as agents modify files during an engagement. Major changes/updates should create commit checkpoints.

**Considerations:**
- Commit granularity — per write? per wave? per milestone?
- Auto-commit on phase transitions
- Auto-generated commit messages from wave/phase context
- Rollback to previous commit hash
- Batch/coalesce writes into periodic commits

### R26 — Agent Fleet & SDLC 🔜 (Waves 16a/16b/17)

**Source:** Andy voice note, 2026-05-22

**New Agent Types:**
- **Refactoring Agent** — SOP: understand intent → architecture loop → migration effort → boundary tests → execute → verify
- **Refactor Orchestrator** — Top-level orchestrator for refactoring workflow

**Architecture Principles (all agents):**
- Minimise complexity
- Clean design and architecture
- Increase test coverage, particularly CI-viable mocks
- Adapters and anti-corruption layers
- Hexagonal/clean architecture as default output

**Session Types:**
- **Greenfield session** (existing) — build from scratch
- **Brownfield session** (new) — work on existing project, constrained by existing code
- **Refactoring session** (new) — restructure toward ideal architecture

**Fleet Architecture:**
| Fleet | Lead | Sub-agents |
|-------|------|-----------|
| Architecture | architecture-agent | DDD sub-agent, CLI tooling sub-agent, API design sub-agent |
| Coding | coding-agent | Language-specific coders |
| Review | review-agent | Security, performance, style reviewers |
| Testing | testing-agent | Specialised test generators |

**Governance Levels:**
- `exploration` — POC, lead agent only
- `standard` — lead + relevant sub-agents
- `strict` — full fleet + extra reviewers

**Pattern Injection:**
- Language-idiomatic patterns per language
- Company-specific architecture standards
- External resources and style guides
- Injected via `.harness/patterns/` in project repo

**Config:**
- `constitution.yaml`: `project.allow-refactoring-suggestions` (default: true)
- Engagement-level override in `engagement.yaml`

### R27 — Comprehensive Analysis & Observer Enhancement 🛠️ (Wave 20)

**Source:** Andy, 2026-05-23 — real-time session directive after Crichton comparison

**Problem:** Observer mode (`harness observe --deep`) produces a useful but limited report. Far from human-quality review.

**Requirements:**
1. **Run ALL analysis commands non-destructively** — output to directory, no repo modifications
2. **Comprehensive, actionable report** — executive summary, architecture, code quality, testing, security, documentation, prioritised findings
3. **Dual mode** — standalone observer (no harness state) + native engagement mode
4. **Self-analysis** — harness must analyse its own repo
5. **Output directory structure:**
   ```
   analysis-output/
     report.md           # Human-readable report
     findings.json       # Machine-readable findings
     per-agent/          # Per-agent raw outputs
     artifacts/          # Generated diagrams, dependency graphs
   ```

**Extended Analysis Agents:**
| Agent | Name | Status |
|-------|------|--------|
| P1 | Project Profiler | ✅ Live |
| P2 | Responsibility Decoder | ✅ Live |
| P3 | Architecture Critic | ✅ Live |
| P4 | Code Critic | ✅ Fixed (sequential execution) |
| P5 | Test Auditor | ✅ Live |
| P6 | Security Auditor | ✅ Live |
| P7 | Dependency Analyser | ✅ Live |
| P8 | Documentation Reviewer | ✅ Live |
| P9 | Synthesis | ✅ Live |
| P10 | Critical Reviewer | ✅ Live — 10 cross-cutting check types |
| P11 | Refactoring & Abstraction Analyser | ✅ Live — 8 analysis types |

---

## 3. Wave Requirements Coverage Map

| Requirement | Status | Wave(s) |
|-------------|--------|---------|
| **R1** Runnable Summaries | ✅ Built | 1-5 |
| **R2** Autonomous Operation | ✅ Built | 1-6 |
| **R3** Agent Community | 🔧 Partial | 7+ |
| **R4** Project Constitution | ✅ Built | 1-4 |
| **R5** Critical Analysis | ✅ Built | 8, 11 |
| **R6** Test Strategy | 📋 Spec'd | 8+ |
| **R7** Flexible Workflow | ✅ Built | 10 |
| **R8** Cross-Cutting | ⚡ Arch | 6+7 |
| **R9** Design Decisions | ✅ Built | 6+9 |
| **R10** Outline Audit | ✅ Built | 1-10 |
| **R11** Observer Mode | ✅ Built | 8 |
| **R12** Side-Channel Coding | ✅ Built | 9 |
| **R13** Domain Language | ✅ Built | 1 |
| **R14** Specs as Point-in-Time | ✅ Built | 9 |
| **R15** Branch Management | ✅ Built | 9 |
| **R16** Chat Agent / NL Interface | ✅ Built | 10 |
| **R17** Configurable Scaffolding | ✅ Built | 5 |
| **R18** Single Executable Build | ✅ Built | 10 |
| **R19** Dynamic .gitignore | ✅ Built | 5 |
| **R20** Standard Document Format | ✅ Built | 2+4 |
| **R21** Discovery Agent | ✅ Built | 11 |
| **R22** Independent Analysis | ✅ Built | 11 |
| **R23** Context Loading | ✅ Built | 14 |
| **R24** Cross-Phase Navigation | 📋 Drafted | 15 |
| **R25** Commit Frequency & Snapshots | 🗺️ Future | TBD |
| **R26** Agent Fleet & SDLC | 📋 Spec'd | 16a/16b/17 |
| **R27** Comprehensive Analysis | ✅ Built (P1-P11) | 20 |

**Status Legend:** ✅ Built → 🔧 In Progress → 📋 Spec'd → 🗺️ Design needed → 🔜 Planned → ⚡ Arch/Principle
