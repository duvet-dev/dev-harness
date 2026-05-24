# Refactoring Engagement Workflow

_A lifecycle for using the harness to refactor code — going from current state to target state via observer-driven findings._

---

## Overview

Building new features and refactoring existing code are fundamentally different kinds of work. Feature building starts from a **requirements gap** (what users need but don't have). Refactoring starts from a **quality gap** (what the codebase is vs what it should be).

The observer (`harness inspect --deep .`) measures the quality gap. The refactoring engagement closes it.

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

**Input:** Observer report from `harness inspect --deep . --report baseline.md`

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
harness inspect --deep . --report verify-<wave>.md

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

# 1. Baseline assessment (produces findings with IDs)
harness assess . --report baseline.md

# 2. Create refactoring engagement — auto-creates waves from findings
harness engagement create "Refactoring: Critical Bug Fixes" --refactoring --focus high-risk
# → Reads latest assessment manifest (e.g., 71 findings)
# → Creates engagement at .harness/engagements/.../
# → Auto-creates waves for each high-risk finding
# → Stores baseline reference + finding count in engagement.yaml

# 3. See what waves were created
harness wave list

# 4. Run a wave (implement a fix)
harness wave run wave-01

# 5. Compare to baseline — how many findings are closed?
harness engagement diff
# Shows: CLOSED 5 findings, REMAINING 3, NEW 0

# 6. Finish and auto-re-assess
harness finish --re-assess
# → Commits changes
# → Runs observer automatically
# → Compares to baseline, shows closure rate
# → Records metrics in assessment_history

# 7. Next engagement from NEW baseline
harness engagement create "Refactoring: Architecture" --refactoring --focus high-risk
# → Starts from 48 findings, not 71
```

### Adding a wave manually (optional)

For findings that weren't auto-created, create a wave from a specific finding ID:

```bash
harness wave create-from-finding finding-004
# Creates wave with the finding as spec, tracks association in manifest
```

---

## Per-Wave Workflow (Detailed)

```
1. Waves are auto-created by: harness engagement create --refactoring
   ↓
2. List waves: harness wave list
   ↓
3. Run a wave: harness wave run wave-01
   (runs implement → test → verify → commit cycle)
   ↓
4. Verify tests still pass: python3 -m pytest -x -q
   ↓
5. Check progress: harness engagement diff
   (doesn't re-run observer — just compares current to baseline)
   ↓
6. Next wave
```

Or with more granular control:

```bash
harness wave create-from-finding finding-001   # Create wave from specific finding
harness phase run architect                    # Design the extraction
harness phase run coder                        # Implement the refactoring
python3 -m pytest -x -q                        # Verify tests
harness engagement diff                         # Compare to baseline
harness wave run wave-01                        # Commit the wave
```

---

## When the Standard Phase Model Doesn't Fit

The existing phase model has some friction with refactoring work:

| Friction Point | Description | Workaround | Long-Term Fix |
|---------------|-------------|------------|---------------|
| **"Requirements" phase** | Refactoring has no user-facing requirements. The "requirement" is the observer finding. | Use `--refactoring` flag on engagement create — it seeds waves from the observer report. | ✅ **Resolved in Wave 2** — `harness engagement create --refactoring` auto-creates waves from assessment findings. |
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

## Modelling Gaps — Resolution Status

All four original gaps have been addressed in Waves 1-3:

### Gap 1: No "Assess" Phase — ✅ Resolved (Wave 2)

`harness engagement create --refactoring` reads the latest assessment manifest and seeds waves from findings. No separate assess step needed.

### Gap 2: No Refactoring Agent Role — 🔶 Partial (prompts not yet automated)

`--refactoring` engagements store `session_type: refactoring` in engagement.yaml. Agent prompt overrides to switch to "extraction mode" are planned but not yet implemented. In the meantime, wave descriptions are seeded from finding descriptions which naturally frame the work as refactoring.

### Gap 3: No Finding→Wave Mapping — ✅ Resolved (Waves 1+2)

Two approaches:
- **Auto-created:** `harness engagement create --refactoring` creates waves from all findings (optionally filtered by `--focus`).
- **Manual:** `harness wave create-from-finding finding-001` creates a wave from a specific finding.

Both store the finding→wave association in the assessment manifest (wave_slug + wave_status fields).

### Gap 4: No Baseline→Current Comparison — ✅ Resolved (Wave 3)

`harness engagement diff` loads the baseline manifest from engagement creation, runs a fresh assessment, and shows closed/remaining/new findings with a closure rate.

`harness finish --re-assess` combines committing, re-assessment, and baseline comparison into a single command, and records metrics to `.harness/config.yaml assessment_history` for tracking across engagements.

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
harness assess . --report baseline.md        # Step 1: baseline (produces findings with IDs)

# ── ENGAGEMENT (auto-waves from findings) ──
harness engagement create "Refactoring: <scope>" --refactoring --focus high-risk
harness wave list                              # See auto-created waves

# ── PER WAVE ──
harness wave run wave-01                       # implement → test → verify → commit
# or with granular control:
#   harness phase run architect
#   harness phase run coder
#   python3 -m pytest -x -q
#   harness engagement diff

# ── VERIFY ──
harness engagement diff                        # baseline comparison
# Shows: CLOSED N / REMAINING M / NEW 0

# ── CLOSE ──
harness finish --re-assess                     # Commit + auto-observer + metrics

# ── NEXT ──
harness engagement create "Refactoring: Next" --refactoring --focus high-risk
# Starts from NEW baseline (fewer findings)
```

### Quick Reference: All Refactoring Commands

| Command | Purpose |
|---------|---------|
| `harness assess . --deep` | Run baseline assessment (produces findings with IDs) |
| `harness engagement create "..." --refactoring --focus high-risk` | Create engagement with auto-waves from high-risk findings |
| `harness wave create-from-finding finding-001` | Add a wave for a specific finding manually |
| `harness wave list` | See all waves in the plan |
| `harness wave run wave-01` | Execute a wave through the full cycle |
| `harness engagement diff` | Compare baseline to current state |
| `harness finish --re-assess` | Commit, re-run observer, compare, track history |

---

_See also: `.harness/patterns/self-improving-workflow.md` — the broader self-review pattern._  
_Created: 2026-05-24 — captures the refactoring-specific lifecycle._
