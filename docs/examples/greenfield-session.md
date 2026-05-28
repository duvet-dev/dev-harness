# Greenfield Session — Example Walkthrough

_A complete end-to-end greenfield engagement: building a URL shortener from scratch._

---

## What's a Greenfield Session?

A **greenfield** session builds from scratch. No existing-code constraints. The agents are told there's nothing yet — they have full creative freedom within the agreed architecture.

**When to use it:** New projects, brand-new microservices, prototypes, POCs.
**CLI flag:** `--greenfield` (this is also the default when no session type matches.)
**Engagement metadata:** `session_type: greenfield`

---

## Example: URL Shortener Service

### 🔷 Step 1: Init the Project

```bash
# Create and init a new harness project
harness init url-shortener --template backend-service
```

This scaffolds the constitution, agent profiles, `.harness/` state directory, and a `.gitignore`. The `backend-service` template also creates the recommended directory structure.

### 🔷 Step 2: Create the Engagement

```bash
cd url-shortener

harness engagement create "URL Shortener Service" --greenfield
```

Without `--greenfield`, the harness would try to detect the session type from your description. But since we're starting from scratch, we set it explicitly. This stores `session_type: greenfield` in the engagement's `engagement.yaml`, which tells all agents: "No prior code — build from scratch."

### 🔷 Step 3: Run the Full Session

```bash
harness session
```

The session runs through all phases:

#### Phase 1: Requirements
The `requirements-builder` agent interviews you about:
- What the service should do (create, redirect, expire URLs)
- Non-functional requirements (latency, throughput, storage)
- Constraints (short alias length, allowed characters)
- Success criteria

The agent writes `docs/requirements.md` to the project.

#### Phase 2: Research
The `researcher` agent investigates:
- Hashing vs encoding approaches (base62, UUID, custom)
- Storage options (Postgres, Redis, SQLite)
- Deployment strategies for a simple service
- Competition patterns

Output: `docs/research.md` with pros/cons matrix.

#### Phase 3: Design
The `architect` agent produces:
- Component diagram (API layer → service layer → storage)
- Data model (URL mapping entity, click stats)
- API contracts (POST /shorten, GET /{alias})
- ADR for the alias generation strategy

Output in `docs/arch/001-adr-alias-strategy.md` and `docs/arch/data-model.md`.

#### Phase 4: Planning
The `planning-agent` decomposes into waves:
| Wave | Title | Effort |
|------|-------|--------|
| wave-01 | Data model + repository | S |
| wave-02 | Create endpoint | M |
| wave-03 | Redirect endpoint | S |
| wave-04 | Click tracking | M |
| wave-05 | Expiry + cleanup | L |
| wave-06 | API docs + polishing | S |

#### Phase 5: Implementation (per-wave)

```bash
# Each wave runs: implement → test → verify → commit
harness wave run wave-01
harness wave run wave-02
# ...
```

The `coder` agent writes production code guided by the design spec. The `tester` agent writes tests as part of each wave.

#### Phase 6: Review & Finish

```bash
# Gate review
harness review

# Final commit + close
harness finish
```

### 🔷 Full One-Shot (Auto-Pilot)

For a well-understood task where you trust the harness:

```bash
harness work "URL Shortener Service" --mode auto --greenfield
```

This runs all phases autonomously with auto-pilot mode. At each semi-permeable gate, you can either let it through or pause for review.

---

## What Makes Greenfield Different?

| Aspect | Greenfield Behaviour |
|--------|---------------------|
| **Assessment** | No baseline needed — the observer runs to check structure, not regressions |
| **Context** | Agents see an empty project; no "existing code" constraints in prompts |
| **Design** | Full design freedom — no need to retrofit into an existing architecture |
| **Implementation** | Everything is new — no merge conflicts with existing work |
| **Refactoring** | Not a priority — you'd set up a separate refactoring engagement post-launch |
| **Session type prompt injection** | `You are building from scratch. No existing codebase constraints. You have full design freedom within the constitution scope.` |

---

## After First Release

Once the greenfield project is live, future work should use **brownfield** or **refactoring** sessions. The first greenfield establishes the baseline; everything else works within it.

```
  Greenfield           Brownfield             Refactoring
   (create)     →      (enhance)       →      (improve)
      │                                        │
      └────────────────────────────────────────┘
                     (then assess/refactor)
```

Next steps after v1.0:

```bash
harness assess . --report v1-baseline.md
harness engagement create "Add analytics" --brownfield
harness session
```

---

_See also:_
- [Brownfield Session](brownfield-session.md)
- [Refactoring Session](refactoring-session.md)
- [Get-Well Session](get-well-session.md)
- `harness session --help`
- `harness engagement create --help`
