# Self-Improving Workflow

_A pattern for using the harness to audit, design, and improve itself — no prior analysis required._

---

## The Core Idea

The harness can analyse its own codebase, identify issues, create waves to fix them, verify the fixes, then repeat. Each cycle raises the bar.

You don't need external tools, reviewers, or prior analysis. The observer (`harness observe --deep .`) is the entry point. It produces a comprehensive report identifying bugs, architectural debt, test gaps, and refactoring opportunities. You then use the harness engagement lifecycle to fix them.

---

## Starting From Scratch

```
                   ┌─────────────────────────┐
                   │  Initial Observer Run   │
                   │  harness observe --deep  │
                   └───────────┬─────────────┘
                               │
                    ┌──────────▼──────────┐
                    │  Review Findings     │
                    │  Categorise +        │
                    │  Prioritise          │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  Create Engagement   │
                    │  harness work "..."  │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  Plan Waves          │
                    │  (3-5 per engagement)│
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  Execute Each Wave   │
                    │  harness wave run    │
                    │  harness phase ...   │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  Verify + Re-Assess  │
                    │  harness observe     │
                    │  Compare findings    │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  Finish / Next       │
                    │  Engagement          │
                    └─────────────────────┘
```

---

## Step-by-Step: Your First Self-Review

### Phase 1: Baseline Assessment

```bash
# 1. Run the observer (no prior knowledge needed)
cd /path/to/repo
harness observe --deep . --output baseline-assessment.md

# 2. Read the report — it tells you what's wrong
#    The report includes:
#    - Executive summary of codebase health
#    - Prioritised findings table
#    - Cross-connected issues across dimensions
#    - Top 5 concrete recommendations
#    - Effort estimates per finding
```

### Phase 2: Categorise Findings

Group the observer findings into three buckets:

| Bucket | Description | Examples |
|--------|-------------|---------|
| **Quick wins** | < 2 hours, clear fix, low risk | Duplicate constants, missing enum values, env-var inconsistencies |
| **Medium refactors** | 2-8 hours, structural change, low-medium risk | Split large files, extract interfaces, add missing tests |
| **Architectural debt** | 8+ hours, design change, requires discussion | God modules, circular dependencies, concurrency models |

Each bucket becomes a separate engagement. Quick wins first, then medium, then architectural.

### Phase 3: Create the First Engagement

```bash
# Create an engagement for quick wins
harness work "Self-Review: Critical Bug Fixes" --mode auto

# This:
# - Creates .harness/engagements/self-review-critical-bug-fixes/
# - Sets up branch eng/self-review-critical-bug-fixes
# - Populates an initial plan from the architecture goal
# - Starts tracking state and freshness
```

### Phase 4: Define Waves

For each finding in the engagement scope, create a wave:

```bash
# From the observer report's "fix immediately" items:
harness wave create fix-phantom-roles
harness wave create fix-env-var-inconsistency
harness wave create add-e2e-tests

# Each wave creates:
# - A requirements section
# - Design space
# - Code + test targets
# - Acceptance criteria (the finding that should be gone)
```

### Phase 5: Execute the Wave

Each wave runs through the standard harness phases:

```bash
# Run the full session for one wave
harness session

# This triggers:
# 1. Requirements Builder — expands the wave into detailed spec
# 2. Architect — designs the change
# 3. Architect Critic — reviews the design
# 4. Planner — plans implementation steps
# 5. Coder — implements the change
# 6. Tester — writes/updates tests
# 7. Reviewer — reviews the result
```

Or run phases individually for more control:

```bash
harness phase run requirements
harness phase run architect
harness phase run plan
harness phase run code
harness phase run test
harness phase run review
```

### Phase 6: Verify Improvements

After each wave (or the full engagement), re-run the observer and compare:

```bash
# Run after fixing one wave's findings
harness observe --deep . --output wave-verification.md

# Compare: findings count should be LOWER than baseline
# Compare: specific finding should be GONE
# Compare: no regressions should appear

# If the specific finding is gone → wave successful
# If new issues appeared → adjust approach
# If nothing changed → fix didn't work, iterate
```

### Phase 7: Gate Review

```bash
# Formal review of the engagement
harness review

# Reviews:
# - Are all planned fixes complete?
# - Did the observer confirm improvements?
# - Are there regressions?
# - Is the engagement ready to close?
```

### Phase 8: Finish & Next

```bash
# Complete the engagement
harness finish

# This:
# - Commits all changes
# - Records the engagement artifact
# - Cleans up state
# - Merges back to main
```

### Phase 9: Start the Next Engagement

```bash
# Medium refactors
harness work "Self-Review: Architecture Refactoring" --mode auto

# Same cycle: define waves → execute → verify → review → finish
```

---

## The Observer Within an Engagement

The observer run can (and should) be used at multiple points in the engagement lifecycle:

| When | What to Run | Why |
|------|-------------|-----|
| **Before engagement** | `harness observe --deep .` | Baseline — establishes what needs fixing |
| **After each wave** | `harness observe --deep .` | Verify the wave's fix actually resolved the issue |
| **At gate review** | `harness observe --deep .` | Full health check before merging |
| **After finish** | `harness observe --deep .` | Final comparison to baseline — track improvement trajectory |

The observer output is saved to the engagement's assessments directory, building a history of how the codebase has improved over time.

---

## Multi-Engagement Strategy

For a non-trivial codebase, a single engagement won't cover everything. Use multiple sequential engagements:

### Engagement 1: Critical Bug Fixes
**Scope:** Observer findings with risk=high and effort<2h  
**Waves:** 3-5 quick fixes  
**Goal:** Clear the easy, impactful items. Build momentum.

### Engagement 2: Test Coverage & Quality
**Scope:** Observer findings about test gaps, dead test infra, low-coverage paths  
**Waves:** Add missing tests, fix test infrastructure, improve coverage  
**Goal:** Raise coverage to a level where refactoring is safe (e.g., 70%+ on critical paths).

### Engagement 3: Architecture Refactoring
**Scope:** Observer findings about architectural debt (god modules, circular deps, concurrency)  
**Waves:** Split large files, resolve cycles, add interfaces, generic implementations  
**Goal:** Make the codebase maintainable and extensible. Only safe to do after test coverage is solid.

### Engagement 4+: Ongoing
**Scope:** Remaining debt, new patterns, continuous improvement  
**Goal:** Each engagement makes the codebase more robust than the last.

---

## The Self-Improving Loop

```
Baseline observer run
       │
       ▼
Create engagement ←──┐
       │              │
       ▼              │
Define waves          │
       │              │
       ▼              │
Execute wave          │
       │              │
       ▼              │
Re-run observer ──────┤
       │              │
       ├─ All fixed? ─┘
       │
       ▼
Gate review
       │
       ▼
Finish engagement
       │
       ▼
Next engagement →
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
# 1. Baseline
harness observe --deep . --output baseline.md

# 2. Read findings, pick the critical ones

# 3. First engagement
harness work "Self-Review: Critical Bug Fixes" --mode auto
harness wave create fix-phantom-roles
harness wave create fix-env-vars
harness wave create add-e2e-tests

# 4. Execute each wave (or run full session for all)
harness wave run fix-phantom-roles
harness observe --deep . --output verify-1.md

harness wave run fix-env-vars
harness observe --deep . --output verify-2.md

harness wave run add-e2e-tests
harness observe --deep . --output verify-3.md

# 5. Review and close
harness review
harness finish

# 6. Next engagement
harness work "Self-Review: Architecture Refactoring" --mode auto
harness wave create split-cli-god-module
harness wave create extract-cycle-runner
# ...repeat
```

---

_See also: `.harness/patterns/README.md` for other patterns._  
_Created: 2026-05-24 — captures the self-improving workflow used on dev-harness itself._
