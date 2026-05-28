# Get-Well Session — Example Walkthrough

_A complete get-well engagement: diagnosing and fixing a codebase that won't build, pass tests, or deploy._

---

## What's a Get-Well Session?

A **get-well** session fixes a broken or regressed state. The codebase exists but it's not working — failing tests, compilation errors, dependency conflicts, misconfiguration, or deployment failures. The goal is not to add features or refactor; it's to **restore health**.

**When to use it:**
- CI pipeline is red (failing tests, lint errors)
- Dependencies are incompatible after an upgrade
- A merge broke critical paths
- Environment config is misaligned (wrong API keys, outdated env vars)
- After a failed migration that left the codebase in an inconsistent state
- The build hasn't been green in days

**CLI flag:** `--get-well` _(provided as a convention — see below)_
**Detection keywords:** "broken", "fix", "failing", "doesn't work", "won't build", "compilation error", "regression", "red CI", "restore"
**Engagement metadata:** `session_type: get_well`

> **Note:** `get_well` is not yet in the `SessionType` enum. Add it to `src/harness/session/types.py` when ready:
> ```python
> class SessionType(str, enum.Enum):
>     GREENFIELD = "greenfield"
>     BROWNFIELD = "brownfield"
>     REFACTORING = "refactoring"
>     GET_WELL = "get_well"    # ← add this
> ```

---

## Example: Fix a Broken Integration Branch

Your team merged a large dependency upgrade (Python 3.9 → 3.11, new ORM version). The `integration` branch has 47 failing tests, 3 modules that won't import, and CI has been red for two days. Nobody knows where to start.

### 🔷 Step 1: Triage with `harness inspect`

```bash
cd broken-project

# Fast scan — what's obviously wrong?
harness inspect . --deep
```

The observer runs a diagnostics-focused scan that flags:

- **Compilation/import errors:** `ModuleNotFoundError: sqlalchemy.orm.session`
- **Deprecation warnings:** 23 deprecation warnings related to the ORM API change
- **Failing tests:** 47 failures across 3 test files
- **Config drift:** `providers.yaml` references keys that don't exist in the project
- **Dependency conflicts:** `requirements.txt` pins a version incompatible with Python 3.11

Output:

```
── Triage Report ──

CRITICAL (blocking):
  ⚠ import-error: src/models.py — sqlalchemy.orm.session API removed in 2.0
  ⚠ import-error: src/migrations/env.py — alembic.operations ops API changed
  ⚠ config-miss: .harness/providers.yaml — references $API_KEY (unset)

HIGH (must fix for build):
  ⚠ deprecation: 23 warnings across test_suite — ORM query API deprecated
  ⚠ test-failure: tests/test_integration.py — 31/31 tests fail (setup error)
  ⚠ test-failure: tests/test_api.py — 12/12 tests fail (broken mock path)

MEDIUM (blocking deployments, not compilation):
  ⚠ docker-config: Dockerfile references python:3.9-slim (should be 3.11)
  ⚠ ci-config: .github/workflows/test.yml has stale python-version: '3.9'
```

### 🔷 Step 2: Create a Get-Well Engagement

```bash
harness engagement create "Fix integration after dep upgrade" --get-well
```

With `--get-well`, the engagement:
- Stores `session_type: get_well` in `engagement.yaml`
- Uses the triage report as the baseline (not a normal assessment)
- Disables feature work — waves can only fix or revert, not add
- Injects a recovery-oriented system prompt:

> "You are in a **get-well** engagement. The codebase is currently broken. Your job is to restore it to health. Every change must move toward a working state. Do not add features, refactor for elegance, or optimise performance. Fix what's broken. If the fastest path to working involves reverting recent changes, do that. Restore health first; improvement comes after."

### 🔷 Step 3: Waves Are Ordered by Impact

The auto-created waves are ordered by **blocking-chain** — fix the root cause first, watch cascading fixes resolve downstream failures:

```bash
harness wave list
```

Output:

```
  Wave ID      Title                                                   State
  ───────────  ──────────────────────────────────────────────────────  ─────────
  * wave-01    Fix import errors in src/models.py (sqlalchemy 2.0)    open
  * wave-02    Fix import errors in src/migrations/env.py             open
  * wave-03    Update .harness/providers.yaml to resolve $API_KEY     open
  * wave-04    Fix ORM deprecation warnings and update query API      open
  * wave-05    Fix test_integration.py setup (broken ORM session)     open
  * wave-06    Fix test_api.py mocks (outdated import paths)          open
  * wave-07    Update Dockerfile from python:3.9 → python:3.11       open
  * wave-08    Update CI config python-version to 3.11                open
```

Wave-01 fixes the line causing `ModuleNotFoundError`. Once that resolves, waves 04+05 may auto-resolve because the underlying cause was the import error.

### 🔷 Step 4: Execute Waves — Fix, Don't Improve

```bash
# Fix the import error — the root cause of ~40 test failures
harness wave run wave-01
```

Each wave is a focused fix. The agent is explicitly told:

- **Do not** rewrite the module — just fix the import/invocation
- **Do not** upgrade to a different ORM — just make the existing code work
- **Do not** add tests — just get existing tests passing
- **Do not** optimise — just fix

If the fix involves reverting a change, that's valid:

> "The safest fix is to revert the session import to the 1.4-compatible API. We can discuss adopting the 2.0 API in a separate refactoring engagement."

```bash
harness wave run wave-02
harness wave run wave-03
harness wave run wave-04
```

### 🔷 Step 5: Verify After Each Fix

```bash
# Quick check — are fewer tests failing?
harness inspect . 

# Or run the test suite to see progress
pytest tests/ --tb=short -q
```

Each wave should reduce the failure count:

| After wave | Test failures | Improvement |
|-----------|--------------|-------------|
| Baseline | 47 | — |
| wave-01 (import fix) | 41 | -6 |
| wave-02 (migrations) | 39 | -2 |
| wave-03 (config) | 39 | 0 (non-test fix) |
| wave-04 (ORM deprecation) | 12 | -27 |
| wave-05 (integration setup) | 3 | -9 |
| wave-06 (mock paths) | 0 | -3 |

### 🔷 Step 6: Full Verification

```bash
# Run the full test suite
pytest

# Deep observer check — no new issues
harness inspect . --deep

# Compare get-well baseline to current state
harness engagement diff
```

The diff should show all get-well findings as CLOSED and zero new findings.

### 🔷 Step 7: Finish

```bash
harness finish
```

The engagement records:
- All 8 get-well waves closed
- 47 test failures → 0 test failures
- 3 critical import errors resolved
- 23 deprecation warnings resolved
- Elapsed time: ~45 minutes

---

## Get-Well Without an Engagement (Fast Fixes)

For a single broken thing that you can describe in one sentence:

```bash
# Run a specific fix agent
harness agent run fixer "The providers.yaml has an unresolved $API_KEY env var"
```

Or use the session's interactive chat:

```bash
harness chat
> The Dockerfile still references python:3.9 but we upgraded to 3.11. Fix it.
```

But for anything multi-symptom, always use a full get-well engagement — the triage report and wave ordering are the whole point.

---

## What Makes Get-Well Different?

| Aspect | Normal Sessions | Get-Well |
|--------|----------------|----------|
| **Primary entry point** | `harness session` or `harness work` | **`harness inspect --deep`** (triage first) |
| **Assessment focus** | Architecture, coverage, quality | **Compilation, imports, test failures, config drift** |
| **Wave content** | Features, refactors, designs | **Targeted fixes, reverts, config corrections** |
| **Agent directive** | "Build" / "Extend" / "Restructure" | **"Fix. Do not add. Do not refactor. Restore health."** |
| **Wave ordering** | By dependency | **By blocking-chain** (fix root cause first) |
| **Test strategy** | Write new tests | **Get existing tests green** — don't add until everything works |
| **Reverts allowed** | No (would break the plan) | **Yes — reverting is the fastest path to health** |
| **Success metric** | Feature works / code improved | **Zero failures, clean build, green CI** |
| **Session flag** | `--greenfield / --brownfield / --refactoring` | **`--get-well`** |
| **Detect keywords** | Feature-oriented | "broken", "fix", "failing", "regression", "won't build" |

---

## Get-Well Progression

```
  GET-WELL                  BROWNFIELD               REFACTORING
   (fix the broken)     →    (add feature)      →     (restructure)
        │                       │                        │
        ▼                       ▼                        ▼
   health restored         feature works            code is clean
```

Don't combine get-well with other session types. If the codebase is broken, fix it first. Features and refactoring come after a green baseline.

---

## Edge Cases

### Case 1: The regression was a feature change
Sometimes the "fix" is to revert a feature commit that introduced side effects. That's fine — get-well engagements can create a "revert commit X" wave. The feature can be re-attempted in a brownfield engagement later.

### Case 2: You need a temporary patch to unblock the team
Create a wave-01 that applies the minimal fix (e.g., pin a dependency version), get CI green, then do a proper fix in a subsequent wave. Don't let perfect be the enemy of working.

### Case 3: The broken state has no test coverage
Use get-well to at least make the build green. Then create a separate brownfield engagement to add the missing tests. Don't try to add coverage in a get-well — that's scope creep.

### Case 4: The codebase won't even import
Fall back to `harness inspect .` for a file-based scan. If Python can't import, the observer falls through to structural analysis (file system scan, pattern matching, config review).

---

_See also:_
- [Greenfield Session](greenfield-session.md)
- [Brownfield Session](brownfield-session.md)
- [Refactoring Session](refactoring-session.md)
- `harness inspect --help`
- `harness assess --help`
- `src/harness/session/types.py` (SessionType enum — add `GET_WELL` here)
