# Self-Improving Workflow

_A pattern for using the harness to audit, design, and improve itself — no prior analysis required._

---

## The Core Idea

The harness can analyse its own codebase, identify issues, create waves to fix them, verify the fixes, then repeat. Each cycle raises the bar.

You don't need external tools, reviewers, or prior analysis. The observer (`harness inspect --deep .`) is the entry point. It produces a comprehensive report identifying bugs, architectural debt, test gaps, and refactoring opportunities. You then use the harness engagement lifecycle to fix them.

---

## Starting From Scratch

```
                   ┌─────────────────────────┐
                   │  Baseline Assessment    │
                   │  harness assess . --deep │
                   └───────────┬─────────────┘
                               │
                    ┌──────────▼──────────┐
                    │  Review Findings     │
                    │  + Categorise        │
                    │  + Prioritise        │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  Create Engagement   │
                    │  + auto-waves        │
                    │  eng create --refact │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  Execute Each Wave   │
                    │  harness wave run    │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  Compare to Baseline │
                    │  eng diff            │
                    │  (CLOSED / REMAINING)│
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  Finish + Re-Assess  │
                    │  finish --re-assess  │
                    │  (auto-observer,     │
                    │   closure metrics,   │
                    │   history tracked)   │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  Next Engagement     │
                    │  (from NEW baseline, │
                    │   fewer findings)    │
                    └─────────────────────┘
```

---

## Step-by-Step: Your First Self-Review

### Phase 1: Baseline Assessment

```bash
# 1. Run the observer (no prior knowledge needed)
cd /path/to/repo
harness assess . --report baseline-assessment.md
# (assess runs the full deep analysis with structured findings)

# 2. Read the report — it tells you what's wrong
#    The report includes:
#    - Executive summary of codebase health
#    - Prioritised findings table with IDs (finding-001, finding-002, ...)
#    - Cross-connected issues across dimensions
#    - Top 5 concrete recommendations
#    - Effort estimates per finding
#    - The manifest .json file has structured findings for tooling
```

### Phase 2: Categorise Findings

Group the observer findings into three buckets:

| Bucket | Description | Examples |
|--------|-------------|---------|
| **Quick wins** | < 2 hours, clear fix, low risk | Duplicate constants, missing enum values, env-var inconsistencies |
| **Medium refactors** | 2-8 hours, structural change, low-medium risk | Split large files, extract interfaces, add missing tests |
| **Architectural debt** | 8+ hours, design change, requires discussion | God modules, circular dependencies, concurrency models |

Each bucket becomes a separate engagement. Quick wins first, then medium, then architectural.

### Phase 3: Create a Refactoring Engagement (Auto-Waves)

```bash
# Create an engagement that auto-creates waves from high-risk findings
harness engagement create "Self-Review: Critical Bug Fixes" --refactoring --focus high-risk

# This:
# - Creates .harness/engagements/self-review-critical-bug-fixes/
# - Sets up branch eng/self-review-critical-bug-fixes
# - Reads the latest assessment manifest
# - Auto-creates waves for each high-risk finding via PlanManager
# - Stores baseline finding count + manifest reference in engagement.yaml
# - Sets session_type=refactoring for agent context
#
# Result: waves are already defined — no manual wave creation needed.
```

Use `--focus all` to create waves from every finding, or `--focus medium` for errors and warnings.

### Phase 4: Manual Wave Creation (Optional)

If you need to add a wave for a specific finding that wasn't auto-created:

```bash
# Create a wave from a specific assessment finding
harness wave create-from-finding finding-001

# This:
# - Reads the latest assessment manifest
# - Finds finding-001 by ID
# - Creates a wave with the finding as the spec
# - Updates the manifest to track wave→finding association
# - Prevents duplicates (safe to re-run)
```

List all waves to see what was created:

```bash
harness wave list
```

### Phase 5: Execute the Wave

Each wave runs through the standard harness phases:

```bash
# Run the full session for one wave
harness session

# Or use the wave runner for implement→test→verify→commit:
harness wave run wave-01
```

### Phase 6: Verify Improvements (Baseline Comparison)

After executing waves, compare the current state to the engagement's baseline:

```bash
# Compare baseline assessment to current state
harness engagement diff

# Shows:
#   ┌─────────────────────────────────────────────────────────────┐
#   │  Engagement: self-review-critical-bug-fixes                │
#   │  ─────────────────────────────────────────────             │
#   │  CLOSED: 23 findings                                       │
#   │    ✓ finding-001: phantom-roles...                         │
#   │    ✓ finding-002: env-var-inconsistency...                 │
#   │  REMAINING: 48 findings                                    │
#   │    ○ finding-004: cli-god-module...                        │
#   │  NEW: 0 findings ✅                                         │
#   │  ──────────────────────────────                            │
#   │  Closure rate: 32%                                          │
#   └─────────────────────────────────────────────────────────────┘
```

Or run the full observer manually:

```bash
harness assess . --report verify.md
# Compare with baseline: fewer findings, specific finding should be gone
```

### Phase 7: Gate Review

```bash
# Formal review of the engagement
harness review
```

### Phase 8: Finish & Re-Assess

```bash
# Complete the engagement with automatic re-verification
harness finish --re-assess

# This:
# - Commits all changes (opens git editor for commit message)
# - Runs the observer automatically
# - Compares current findings to baseline
# - Shows: findings closed, remaining, closure rate
# - Writes new assessment report to the engagement directory
# - Records metrics in .harness/config.yaml assessment_history
#
# The new baseline becomes the starting point for the next engagement.
```

### Phase 9: Start the Next Engagement

```bash
# Next engagement starts from the NEW baseline (fewer findings)
harness engagement create "Self-Review: Architecture" --refactoring --focus high-risk

# Same cycle: auto-waves → execute → diff → finish --re-assess
```

---

## The Observer Within an Engagement

The observer run can (and should) be used at multiple points in the engagement lifecycle:

| When | What to Run | Why |
|------|-------------|-----|
| **Before engagement** | `harness assess . --deep` | Baseline — establishes what needs fixing |
| **During engagement** | `harness wave create-from-finding finding-N` | Create a wave for a specific finding |
| **After wave execution** | `harness wave list` | See which waves have been completed |
| **At gate review** | `harness engagement diff` | Baseline comparison — closed vs remaining vs new |
| **After finish** | `harness finish --re-assess` | Auto-run observer, compare, update history |

No manual observer re-runs needed. The `diff` and `finish --re-assess` commands handle all comparison automatically.

---

## Multi-Engagement Strategy

For a non-trivial codebase, a single engagement won't cover everything. Use multiple sequential engagements:

### Engagement 1: Critical Bug Fixes
**Scope:** Observer findings with risk=high and effort<2h  
**Waves:** Auto-created from high-risk findings (3-5 waves)  
**Goal:** Clear the easy, impactful items. Build momentum.

### Engagement 2: Test Coverage & Quality
**Scope:** Observer findings about test gaps, dead test infra, low-coverage paths  
**Waves:** Test-focused refactoring (add missing tests, fix infrastructure)  
**Goal:** Raise coverage to a level where refactoring is safe (e.g., 70%+ on critical paths).

### Engagement 3: Architecture Refactoring
**Scope:** Observer findings about architectural debt (god modules, circular deps, concurrency)  
**Waves:** Split large files, resolve cycles, add interfaces, generic implementations  
**Goal:** Make the codebase maintainable and extensible.

### Engagement 4+: Ongoing
**Scope:** Remaining debt, new patterns, continuous improvement  
**Goal:** Each engagement makes the codebase more robust than the last.

---

## The Self-Improving Loop

```
Baseline assessment (harness assess)
       │
       ▼
Create engagement --refactoring ────┐
  (auto-creates waves from findings)  │
       │                               │
       ▼                               │
Execute waves (harness wave run)       │
       │                               │
       ▼                               │
Compare to baseline (eng diff) ────────┤
       │                               │
       ├─ All fixed? ──────────────────┘
       │
       ▼
Finish + re-assess (finish --re-assess)
  (auto-observer, closure metrics,
   history tracked)
       │
       ▼
Next engagement →
  (from NEW baseline,
   fewer findings)
```

Each cycle:
- **Reduces findings count** (total issues in the codebase)
- **Raises the bar** (next observer run has higher standards)
- **Builds confidence** (test coverage + verified fixes)
- **Creates momentum** (each engagement is easier than the last)

---

## Metrics to Track

| Metric | What It Measures | Target Trajectory |
|--------|-----------------|-------------------|
| **Findings count** | Total issues identified by observer | Decreasing per engagement |
| **High-risk findings** | Issues marked risk=high | Target: 0 |
| **Coverage %** | Test coverage of source modules | Increasing (70%+ target) |
| **Waves completed** | Engagements closed | > 0 per week |
| **Findings closure rate** | % of findings resolved per engagement | 80%+ |
| **Time from baseline to gate** | How long fixes take | Decreasing (process improves) |

Use `harness status` and `harness engagement list` to check progress at any time.

---

## Troubleshooting

| Problem | Likely Cause | Fix |
|---------|-------------|-----|
| Observer says "no agents" | Backend API key missing or wrong provider | Check `.harness/providers.yaml` and `$DEEPSEEK_API_KEY` |
| Observer hangs on an agent | API timeout (concurrent calls or slow model) | Wait longer (each agent can take 2-10 min with RepoTool calls) |
| Wave doesn't produce code | Agent roles not in AgentRole enum | Fix phantom roles (run observer first to detect) |
| Test coverage doesn't improve | Tests added to wrong module path | Check coverage path mapping in observer report |
| Engagement state lost | `.harness` not tracked in git | Commit `.harness/` (only transient subdirs ignored) |

---

## Complete Quick-Start (One Command Sequence)

```bash
# ── FIRST TIME ──

# 1. Baseline assessment
harness assess . --report baseline.md

# 2. Create refactoring engagement (auto-creates waves from findings)
harness engagement create "Self-Review: Critical Bug Fixes" --refactoring --focus high-risk

# 3. See what waves were created
harness wave list

# 4. Execute each wave
harness wave run wave-01
harness wave run wave-02

# 5. Compare to baseline
harness engagement diff

# 6. Finish and re-assess
harness finish --re-assess

# ── NEXT ENGAGEMENT ──

# 7. Next engagement from new baseline (fewer findings)
harness engagement create "Self-Review: Architecture" --refactoring --focus high-risk

# 8. Execute waves from the new set of findings
harness wave run wave-01
# ...
harness finish --re-assess
```

---

_See also: `.harness/patterns/README.md` for other patterns._  
_Created: 2026-05-24 — captures the self-improving workflow used on dev-harness itself._
