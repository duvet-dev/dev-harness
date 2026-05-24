# Refactoring Engagement Workflow

_A lifecycle for using the harness to refactor code — going from current state to target state via observer-driven findings._

---

## Overview

Building new features and refactoring existing code are fundamentally different kinds of work. Feature building starts from a **requirements gap** (what users need but don't have). Refactoring starts from a **quality gap** (what the codebase is vs what it should be).

The observer (`harness observe --deep .`) measures the quality gap. The refactoring engagement closes it.

```
Current State                    Target State
     │                               ▲
     │   ┌───────────────────────┐   │
     │   │  Refactoring          │   │
     │   │  Engagement           │   │
     │   │                       │   │
     │   │  Wave 1: Fix critical │   │
     │   │  Wave 2: Extract abs  │   │
     │   │  Wave 3: Split god    │   │
     │   │  Wave 4: Generic run  │   │
     │   └───────────────────────┘   │
     ▼                               │
Baseline                        Re-assess
(observer run)                  (findings gone)
```

---

## The Phase Model

The standard harness phase model is built around feature delivery. Refactoring needs a slightly different lens:

| Standard Phase | Refactoring Equivalent | Key Difference |
|----------------|----------------------|----------------|
| **Requirements** | **Assessment Review** | Requirements = observer findings. No user-facing spec. |
| **Architect** | **Refactoring Design** | Design is WHERE to extract, not WHAT to build. |
| **Plan** | **Wave Planning** | Same — break into sequenced tasks. |
| **Code** | **Implement** | Same — but the code is movement, not creation. |
| **Test** | **Verify** | Tests must still pass. New test: observer re-run. |
| **Review** | **Gate Review** | Same — compare findings before/after. |

### Phase-by-Phase Guide

#### 1. Assessment Review (replaces Requirements)

**Input:** Observer report from `harness observe --deep . --report baseline.md`

**Activity:** Review the findings and categorise them:

| Category | What | Actions |
|----------|------|---------|
| **Fix immediately** | < 2h, no risk, clear fix | Add to current engagement's quick-wins |
| **Fix soon** | 2-8h, structural, low risk | Add to current engagement's main waves |
| **Design debt** | 8+ h, needs discussion | Defer to next engagement |
| **Won't fix** | Intentional trade-off | Document and close |

**Output:** A refined wave plan for the engagement.

**Prompt for the agent:** No special prompt needed — the observer report is self-contained.

#### 2. Refactoring Design (replaces Architect)

**Activity:** Design the extraction identified by the observer. For each wave:

- **What concept is being extracted?** (name it clearly)
- **Where does it live now?** (list all files/instances)
- **Where should it live?** (new module, existing module, shared interface)
- **What's the new interface?** (function/class signatures)
- **What code changes are needed?** (per-file)
- **What tests change?** (existing tests that break, new tests needed)

**Output:** A design doc in `.harness/engagements/<slug>/design/<wave-name>.md`

**Prompt for the Architect agent:**
```
Design a refactoring for wave: <wave-name>

The observer found: <finding-description>

Concept to extract: <concept-name>
Current locations: <files>
Proposed abstraction: <interface>

Design the change such that:
1. The concept has a single home (one module/interface)
2. All current users are updated to import from the new home
3. No behaviour changes — the abstraction should be a pure refactoring
4. Existing tests still pass after the change
```

#### 3. Wave Planning (same as feature)

**Activity:** Break the refactoring into implementation steps.

Each wave should be independent where possible. If waves have dependencies, order them:

```
Wave 1: Fix phantom roles (no deps)
Wave 2: Extract constants (no deps)
Wave 3: Create CycleRunner (depends on understanding current cycle code)
Wave 4: Split CLI module (no deps on Wave 1-3)
```

**Output:** Ordered wave list with dependency notes.

#### 4. Implement (same as Code phase)

**Activity:** Code the refactoring. Key principles:

- **One change at a time.** Extract the concept, update all references, test. Do not mix refactorings.
- **Don't change behaviour.** A refactoring introduces no new features — if you find a bug, log it separately.
- **Keep commits clean.** Each wave should be one commit with a clear message.

**Output:** Code changes with passing tests.

#### 5. Verify (replaces Test phase)

**Two verification layers:**

**Layer 1: Existing tests still pass**
```bash
python3 -m pytest -x -q
```

**Layer 2: Observer re-run confirms the finding is gone**
```bash
harness observe --deep . --report verify-<wave>.md

# Compare to baseline:
# - The specific finding should be missing from the new report
# - Total findings should have decreased
# - No new findings should have appeared
```

If the original finding is still present, the refactoring was incomplete. Revisit the implementation.

**Output:** Verification report showing the finding is resolved.

#### 6. Gate Review (same as feature Review)

**Activity:** Compare baseline to current state.

**Checklist:**
- [ ] All planned waves completed?
- [ ] Each wave verified by observer re-run?
- [ ] No regressions (existing findings not worsened)?
- [ ] Tests pass (existing + new)?
- [ ] Design doc committed?
- [ ] Diffs reviewed?

**Output:** Gate review decision (pass/fail/defer).

---

## Engagement Lifecycle for Refactoring

Unlike feature building (which can be a single engagement), refactoring typically benefits from **multiple sequential engagements**:

```
Engagement 1: Critical Bug Fixes
  ├── Wave 1: Fix phantom roles
  ├── Wave 2: Fix env-var inconsistency
  ├── Wave 3: Add missing tests
  └── Re-assess: findings reduced by ~20%

Engagement 2: Architecture Refactoring
  ├── Wave 1: Split CLI god module
  ├── Wave 2: Generic CycleRunner
  ├── Wave 3: Consolidate formatters
  └── Re-assess: findings reduced by ~40%

Engagement 3: Deep Clean
  ├── Wave 1: Fix concurrency gaps
  ├── Wave 2: Add integration tests
  ├── Wave 3: P11 abstractions
  └── Re-assess: findings reduced by ~70%
```

Each engagement has its own:
- **Baseline** (observer run at engagement creation)
- **Plan** (waves for that engagement's scope)
- **Gate review** (findings closure check)
- **Close** (commit, merge, baseline for next)

---

## Quick-Start: Creating a Refactoring Engagement

```bash
# 0. Prerequisites
cd /path/to/repo
harness init

# 1. Baseline assessment
harness assess . --report baseline.md
# (assess is an alias for observe --deep)

# 2. Read the report, pick your scope
#    For this example: critical bug fixes

# 3. Create the refactoring engagement
harness work "Refactoring: Critical Bug Fixes" --mode auto

# 4. Create waves from observer findings
harness wave create fix-phantom-roles
harness wave create fix-env-vars

# 5. Run a wave (all phases)
harness wave run fix-phantom-roles

# 6. Verify the fix
harness assess . --report verify-fix-phantom-roles.md
# Check: is the finding gone?

# 7. Review and close
harness review
harness finish

# 8. Next engagement
harness work "Refactoring: Architecture" --mode auto
```

---

## Per-Wave Workflow (Detailed)

```
1. Select a finding from the observer report
   ↓
2. Create wave: harness wave create <wave-name>
   ↓
3. Design refactoring: harness phase run architect
   (produces design doc with concept name, locations, new interface)
   ↓
4. Review design: harness phase run review
   (checks: is this the right abstraction? any side effects?)
   ↓
5. Implement: harness phase run code
   (extracts the concept, updates all references)
   ↓
6. Verify tests: python3 -m pytest -x -q
   (all existing tests must still pass)
   ↓
7. Verify observer: harness assess . --report verify.md
   (original finding should be gone)
   ↓
8. If complete: harness phase run review
   (gate check for this wave)
   ↓
9. Next wave
```

---

## When the Standard Phase Model Doesn't Fit

The existing phase model has some friction with refactoring work:

| Friction Point | Description | Workaround | Long-Term Fix |
|---------------|-------------|------------|---------------|
| **"Requirements" phase** | Refactoring has no user-facing requirements. The "requirement" is the observer finding. | Use the Assessment Review prompt (above) instead of a requirements prompt. | Add a `--refactoring` flag to engagement creation that skips requirements and seeds from the observer report. |
| **"Test" phase name** | Testing a refactoring is primarily about verifying no regressions, not adding new tests (though new tests are often valuable). | Use the Verify prompt. The observer re-run is the definitive test. | Rename to "Verify" in the refactoring context. |
| **Architect designs "what"** | For refactoring, the "what" is already known (the observer finding). The architect designs "how to extract". | Clarify in the architect prompt that the design is about extraction mechanics, not feature decisions. | Add a refactoring agent role that understands concept extraction. |
| **Wave independence** | Some refactorings have dependencies (e.g., can't split CLI god module until testing infrastructure is in place). | Order waves by dependency. Document dependencies in plan. | Add a dependency field to wave definitions. |

### Current Recommendations

The harness can handle refactoring work today with these adjustments:

1. **Use the Assessment Review prompt** (shown above) instead of the standard requirements phase prompt
2. **Phase names are labels** — the actual work is the same, just the framing changes
3. **Wave ordering matters** — put foundational waves first (test infra, interfaces) before dependent waves (large refactorings)
4. **The observer is your test oracle** — if the finding is gone, the fix worked

Any phase that feels awkward is a signal, not a blocker. The harness is flexible enough to accommodate refactoring within the existing model. If we find certain frictions are persistent, that indicates a modelling gap worth addressing in the harness itself (see below).

---

## Modelling Gaps to Address

If you find yourself fighting the phase model while doing refactoring work, these are the likely root causes:

### Gap 1: No "Assess" Phase in the Standard Lifecycle

**Symptom:** You're running the observer manually and treating its output as requirements. This works but feels disconnected from the engagement lifecycle.

**Fix:** Add a built-in assess step at engagement creation:
```bash
harness work "Refactoring: ..." --refactoring
# This runs the observer as part of engagement creation,
# stores the baseline in the engagement state,
# and seeds the wave plan from the findings.
```

### Gap 2: No Refactoring Agent Role

**Symptom:** The architect and coder agents default to "build new thing" mode. Their output includes unnecessary features.

**Fix:** Add a "refactoring" agent role with system prompts that:
- Assume no behaviour change
- Focus on extraction mechanics
- Prioritise minimal diffs
- Respect existing interfaces

### Gap 3: No Finding→Wave Mapping

**Symptom:** You manually copy findings from the observer report into wave descriptions.

**Fix:** Add a `harness wave create-from-finding <finding-id>` command that:
- Reads the assessment manifest
- Creates a wave with the finding's description as the wave spec
- Links the wave to the finding for traceability

### Gap 4: No Baseline→Current Comparison

**Symptom:** You manually compare observer run N to observer run N-1.

**Fix:** Add `harness engagement diff` that:
- Compares the baseline assessment to the current state
- Shows which findings are closed, which remain, which are new
- Generates a closure rate metric

---

## Measuring Success

### Per Engagement

| Metric | What It Measures | Target |
|--------|-----------------|--------|
| **Findings closed** | Number of observer findings resolved | All planned for this scope |
| **Findings remaining** | Unresolved findings | Decreasing |
| **New findings** | Regressions introduced by changes | 0 |
| **Effort vs estimate** | How accurate P11's effort estimates were | ±20% |

### Per Project

| Metric | What It Measures | Target |
|--------|-----------------|--------|
| **Total findings** | Running count of observer findings | Decreasing trend |
| **Coverage %** | Test coverage of source modules | Increasing (70%+) |
| **High-risk findings** | Critical issues | 0 |
| **Engagements completed** | Refactoring cycles | N/A (continuous) |

---

## Workflow Reference Card

```bash
# ── START HERE ──
harness assess . --report baseline.md        # Step 1: baseline
# Read the report. Find the high-priority findings.

harness work "Refactoring: <scope>" --mode auto  # Step 2: engagement
harness wave create <finding-name>               # Step 3: wave per finding

# ── PER WAVE ──
harness phase run architect    # Design the extraction
harness phase run planner      # Plan implementation steps
harness phase run coder        # Implement the refactoring
python3 -m pytest -x -q        # Verify tests still pass
harness assess . --report verify.md  # Verify finding closed
harness phase run reviewer      # Gate: is this done?

# ── CLOSE ──
harness review                  # Full engagement review
harness finish                  # Commit and merge
harness assess . --report final.md  # Track overall progress
```

---

_See also: `.harness/patterns/self-improving-workflow.md` — the broader self-review pattern._  
_Created: 2026-05-24 — captures the refactoring-specific lifecycle._
