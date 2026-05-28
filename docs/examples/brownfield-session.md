# Brownfield Session — Example Walkthrough

_A complete brownfield engagement: adding analytics to an existing URL shortener._

---

## What's a Brownfield Session?

A **brownfield** session works within an existing codebase. Agents understand they are constrained by what already exists. Every design decision must consider backward compatibility, integration surface, and existing patterns.

**When to use it:** Adding features to an existing project, extending APIs, integrating new functionality into a live codebase.
**CLI flag:** `--brownfield`
**Detection keywords:** "existing", "add to", "extend", "modify", "on top of", "within"
**Engagement metadata:** `session_type: brownfield`

---

## Example: Add Analytics to URL Shortener

You have a working URL shortener (from the [greenfield example](greenfield-session.md)). Now you need click analytics — per-link hit counts, referrer tracking, daily aggregates.

### 🔷 Step 1: Assess the Baseline

```bash
cd url-shortener

# Run the observer to understand the existing codebase
harness assess . --report baseline.md
```

This gives you a complete picture of what exists: module structure, test coverage, architectural patterns, and any existing integration points. The observer report serves as context for all downstream work.

### 🔷 Step 2: Create a Brownfield Engagement

```bash
harness engagement create "Add click analytics" --brownfield
```

With `--brownfield`, the engagement stores `session_type: brownfield` in `engagement.yaml`. This injects a modified system prompt into every agent:

> "You are working within an **existing codebase**. Respect the existing architecture, patterns, and APIs. Document any compromises you make. Design for backward compatibility wherever possible. Read existing files before writing new ones to avoid duplication."

### 🔷 Step 3: Assess Before Design

Before the research phase, run the observer to baseline the codebase:

```bash
# Already done in step 1 — the report feeds the agent context
```

The engagement context loader (tier 2) automatically surfaces relevant code structure to the agents so they don't design in a vacuum.

### 🔷 Step 4: Run the Session

```bash
harness session
```

#### Phase 1: Requirements
The `requirements-builder` establishes:
- What analytics data to capture (clicks, referrer, user-agent, timestamp)
- Aggregation intervals (realtime vs daily)
- Existing models that need extending vs new models
- Performance constraints on the existing redirect (sub-10ms)

**Brownfield twist:** The agent reads the existing schema and API first. It doesn't ask "what's the data model?" — it already checked.

#### Phase 2: Research
The `researcher` investigates:
- How to add tracking without slowing down redirects (async logging, queue)
- Which existing patterns to follow for data access
- Whether the current storage layer can handle the additional writes
- Trade-offs: in-DB aggregation vs scheduled batch jobs

Output: `docs/research/analytics-options.md`

#### Phase 3: Design
The `architect` produces:
- Extensions to the existing data model (new `click_events` table, existing `url_mappings` untouched)
- Integration points in the existing redirect handler (non-blocking event emission)
- Migration strategy (backward-compatible schema change)

**Brownfield twist:** ADRs explicitly compare against "keep existing as-is" and document integration surface area.

#### Phase 4: Planning
Waves are ordered by dependency — existing code must not break:

| Wave | Title | Dependency | Risk |
|------|-------|-----------|------|
| wave-01 | Click event model + migration | None | Low |
| wave-02 | Event capture in redirect path | wave-01 | Medium |
| wave-03 | Aggregation query + cache | wave-02 | Low |
| wave-04 | Analytics API endpoint | wave-03 | Low |
| wave-05 | Existing tests regression check | After every wave | — |

#### Phase 5: Implementation

```bash
harness wave run wave-01
```

Each wave runs the standard implement → test → verify → commit cycle. Unlike greenfield, the `tester` always validates that existing tests still pass before declaring success.

**Key brownfield behaviours during implementation:**
- The `coder` reads existing files before writing
- Follows existing code style (import conventions, error handling patterns, naming)
- Chooses the simplest integration point (don't rebuild — extend)
- The `tester` runs the full existing test suite plus new tests

#### Phase 6: Review & Finish

```bash
# Gate review — specifically checks for regression
harness review

harness finish
```

### 🔷 Handling Compromises

Brownfield work inevitably involves compromises — you can't always do the ideal thing because of existing constraints. The harness tracks these:

```bash
# After the session, check what compromises were documented
harness engagement show --session-type-details
```

Compromises are logged to `engagement.yaml` under `brownfield_compromises`:

```yaml
session_type: brownfield
brownfield_compromises:
  - area: "analytics aggregation"
    issue: "Current ORM can't batch-upsert efficiently"
    workaround: "Raw SQL for aggregation query"
    resolution: "post-mvp — evaluate ORM upgrade"
```

---

## What Makes Brownfield Different?

| Aspect | Greenfield | Brownfield |
|--------|-----------|------------|
| **Assessment** | Optional (empty project) | **Required** — must understand existing code |
| **Context loading** | Minimal | Tier 2 engagement context (code structure, existing tests) |
| **Design freedom** | Full | Constrained by existing architecture |
| **Backward compat** | N/A | Always a design criterion |
| **Regression testing** | New tests only | Existing + new tests run together |
| **Compromise tracking** | Not needed | Required — every integration trade-off is documented |
| **Agent prompts** | "Build from scratch" | "Work within the existing codebase — read before writing" |

---

## Detecting Brownfield Automatically

If you don't specify `--brownfield`, the harness detects it from the engagement description:

```bash
harness engagement create "Add analytics to existing shortener"
```

The `detect_session_type()` function scans for keywords like "add to", "existing", "extend", "on top of" and suggests brownfield:

```
This looks like a brownfield (work within existing code, document compromises) task.
Start a brownfield session? [Y/n]
```

You can accept, choose a different type, or cancel (defaults to greenfield).

---

## After Brownfield

After the brownfield feature is live, run a new assessment to capture the evolved state:

```bash
harness assess . --report post-analytics-baseline.md
```

The next engagement (perhaps fixing technical debt exposed by the new feature) would use `--refactoring`.

---

_See also:_
- [Greenfield Session](greenfield-session.md)
- [Refactoring Session](refactoring-session.md)
- [Get-Well Session](get-well-session.md)
- `harness assess --help`
- `harness session.types` module
