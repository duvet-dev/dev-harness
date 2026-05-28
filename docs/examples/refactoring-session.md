# Refactoring Session — Example Walkthrough

_A complete refactoring engagement: cleaning up a cluttered URL shortener handler._

---

## What's a Refactoring Session?

A **refactoring** session restructures existing code toward an ideal architecture without changing external behaviour. Agent roles shift from "build features" to "extract, simplify, consolidate." Every change is guarded by behaviour-preserving tests.

**When to use it:** Technical debt reduction, module decomposition, pattern consolidation, API cleanup, migration from one pattern to another.
**CLI flag:** `--refactoring`
**Detection keywords:** "refactor", "restructure", "migrate", "extract", "decouple", "untangle", "clean up", "technical debt"
**Engagement metadata:** `session_type: refactoring`

---

## Example: Decompose a God Handler

Your URL shortener has a `handlers.py` with a 400+ line "redirect" function that handles:
- URL lookup
- Click tracking
- User-agent parsing
- Referrer logging
- Rate limiting
- Analytics aggregation

You want to extract responsibilities into focused modules while keeping the endpoint working.

### 🔷 Step 1: Baseline Assessment

```bash
cd url-shortener

# Run the full observer — it will flag the god module
harness assess . --report baseline.md --deep
```

The observer report includes a **refactoring analysis** section (P11) that:
- Identifies concept clusters within the file
- Suggests extraction candidates with effort estimates
- Flags duplicated patterns across modules
- Estimates interface surface area for each extracted module
- Ranks by risk (highest coupling = highest risk)

Expected output:

```
── P11: Refactoring & Abstraction Analysis ──

Concept clusters in src/handlers.py:
  ├─ Click tracking (12 funcs) → extract to analytics/events.py  [S]
  ├─ Rate limiting (4 funcs) → extract to middleware/rate.py      [S]
  ├─ URL resolution (8 funcs) → extract to core/resolver.py       [M]
  ├─ User-agent parsing (3 funcs) → extract to utils/ua.py        [XS]
  └─ Analytics aggregation (6 funcs) → extract to analytics/agg.py [S]

─────────────────────────────────────────────
Total estimated effort: 4-6 hours across 5 extraction candidates.
Risk: MEDIUM (click tracking has highest coupling — do last)
```

### 🔷 Step 2: Create a Refactoring Engagement

```bash
# Auto-creates waves from high-risk findings
harness engagement create "Decompose redirect handler" --refactoring
```

With `--refactoring`, the engagement:
- Stores `session_type: refactoring` in `engagement.yaml`
- Reads the latest assessment manifest
- Auto-creates waves for each P11 extraction candidate
- Sets `allow_refactoring_suggestions: true` (agents can propose additional refactorings)
- Stores the baseline finding count for closure measurement

### 🔷 Step 3: Review Auto-Created Waves

```bash
harness wave list
```

Output:

```
  Wave ID      Title                                     Type          State
  ───────────  ────────────────────────────────────────  ────────────  ──────────────
  * wave-01    Extract user-agent parsing → utils/ua.py  refactor      open
  * wave-02    Extract rate limiting → middleware/rate.py refactor      open
  * wave-03    Extract URL resolution → core/resolver.py  refactor      open
  * wave-04    Extract click tracking → analytics/events   refactor      open
  * wave-05    Extract analytics aggregation → analytics   refactor      open
```

The waves are ordered from lowest risk (XS, isolated utility) to highest (M, highest coupling). This means even if you stop midway, the easy wins are done.

### 🔷 Step 4: Execute Waves

Each wave runs through a **behaviour-preserving cycle**:

```bash
# Wave 1 — simplest extraction
harness wave run wave-01
```

#### What happens during `wave run`:

1. **Read phase:** The `coder` reads `handlers.py` and the target utilities
2. **Extraction:** Extracts UA parsing into `src/utils/ua.py` with clean interface
3. **Redirect:** Updates `handlers.py` to import from the new module
4. **Test phase:** The `tester` runs the full test suite — no behaviour change expected
5. **Verify:** `harness assess . --focus refactoring` checks that the P11 finding is resolved
6. **Commit:** Committed if and only if ALL existing tests pass

```bash
# Wave 2 — rate limiting
harness wave run wave-02

# Wave 3 — URL resolution (the tricky one)
harness wave run wave-03

# Continue through remaining waves...
```

**Safety nets during refactoring:**
- At least one test must cover each extracted function (even if the original was untested — any gap triggers a "write missing tests" sub-task)
- The full test suite runs after every extraction to confirm zero regressions
- If a wave is blocked by missing test coverage, the wave auto-plans a "write tests first" sub-task
- The `tester` writes **behavioural boundary tests** — tests that verify the refactored module behaves identically to the original code path

### 🔷 Step 5: Check Progress Mid-Engagement

```bash
# Compare current state to baseline
harness engagement diff
```

Output:

```
  Engagement: decompose-redirect-handler
  ────────────────────────────────────────────
  CLOSED: 3 findings
    ✓ concept-extraction: user-agent-parsing → utils/ua.py
    ✓ concept-extraction: rate-limiting → middleware/rate.py
    ✓ concept-extraction: url-resolution → core/resolver.py
  REMAINING: 2 findings
    ○ concept-extraction: click-tracking → analytics/events
    ○ concept-extraction: analytics-aggregation → analytics/agg
  NEW: 0 findings ✅
  ──────────────────────────────
  Closure rate: 60%
```

### 🔷 Step 6: Gate Review (Optional)

```bash
harness review
```

The review checks:
- Each extracted module has clean interface boundaries
- Original module is simpler (line count, cyclomatic complexity)
- No duplicated logic between old and new modules
- All existing behaviour is preserved (test suite passes)

### 🔷 Step 7: Finish & Re-Assess

```bash
harness finish --re-assess
```

This:
- Commits remaining waves
- Runs the observer auto-magically
- Compares new findings to the engagement baseline
- Writes closure metrics to engagement history

```bash
# Later — see what was achieved
harness engagement show decompose-redirect-handler --metrics
```

---

## Manual Wave Creation from Findings

If you didn't use `--refactoring` at creation time, or want to add specific findings:

```bash
# Create a wave for a single observer finding
harness wave create-from-finding finding-012

# Batch-import high-risk findings as waves
harness wave create-from-assessment --high-risk

# Batch with limit
harness wave create-from-assessment --focus medium --limit 5
```

---

## What Makes Refactoring Different?

| Aspect | Brownfield | Refactoring |
|--------|-----------|-------------|
| **Primary assessment** | Code understanding | **P11 Refactoring Analysis** — concept extraction + effort estimates |
| **Starting point** | Add new code | Change existing code without changing behaviour |
| **Wave content** | Features, integrations | Extractions, consolidations, deletions |
| **Testing** | New + existing | **Behaviour-preserving boundary tests** — same in/out per function |
| **Success metric** | Feature works | Baseline findings closed, no regression, complexity reduced |
| **Wave ordering** | By dependency | **Lowest risk first** — isolated utilities before high-coupling |
| **Agent guidance** | "Backward compat" | "Behaviour-preserving — test before and after" |
| **Finished state** | Evolved codebase | Cleaner architecture, baseline improvement |

---

## P11 Refactoring Analysis Types

The observer's P11 analyses eight dimensions:

1. **Concept clusters** — groups of related functions that belong together
2. **God objects** — overloaded modules/classes with too many responsibilities
3. **Duplicated logic** — identical or near-identical code paths
4. **Interface surface** — public API of each suggested extraction
5. **Coupling score** — how tightly a cluster is bound to the rest of the system
6. **Effort estimate** — small / medium / large
7. **Risk level** — low (isolated utility) / medium (depends on other modules) / high (deeply coupled, needs careful sequencing)
8. **Pre-requisite waves** — what must be extracted before this can be safely moved

The full analysis lives in `assessment-manifest.json` under `refactoring_analysis.extraction_candidates`.

---

## Advanced: Multi-Engagement Refactoring

For large-scale debt, split across engagements:

```bash
# Engagement 1: Low-hanging fruit (isolated utilities, easy wins)
harness engagement create "Extract utilities" --refactoring
# ... run waves, finish

# Engagement 2: Medium refactor (cross-module extractions)
harness engagement create "Extract middleware layer" --refactoring
# ... run waves, finish

# Engagement 3: Hard refactor (core architecture)
harness engagement create "Split god handler" --refactoring
# ... run waves, finish
```

Each engagement begins with an assessment, so you always see progress.

---

_See also:_
- [Greenfield Session](greenfield-session.md)
- [Brownfield Session](brownfield-session.md)
- [Get-Well Session](get-well-session.md)
- `.harness/patterns/refactoring-workflow.md` — the refactoring workflow pattern
- `.harness/patterns/self-improving-workflow.md` — using refactoring for self-improvement
- `harness wave create-from-finding --help`
- `harness wave create-from-assessment --help`
