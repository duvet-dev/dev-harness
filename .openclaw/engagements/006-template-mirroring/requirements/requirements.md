# Dev Harness — Requirements (Template Mirroring)

> **Purpose:** Single view of all requirements, from original capture through detailed specs.
> **Engagement:** 006-template-mirroring
> **Updated:** 2026-06-07

---

## 0. Domain Language

| Term | Definition |
|------|------------|
| `.openclaw/templates/` | Document templates used by OpenClaw agents for engagement docs |
| `.harness/templates/` | Mirror of templates used by the harness for engagement docs |
| Harness engagement doc | Persistent document at `.harness/engagements/<slug>/{assessments,requirements,design}/` |

## 1. Core Requirements

| # | Requirement | Status | Wave |
|---|-------------|--------|------|
| R1 | `.harness/templates/` mirrors `.openclaw/templates/` directory structure and content | Pending | TBD |
| R2 | `/assess` outputs to `.harness/engagements/<slug>/assessments/assessment.md` in template format | Pending | TBD |
| R3 | `/requirements` outputs to `.harness/engagements/<slug>/requirements/requirements.md` in template format | Pending | TBD |
| R4 | `/design` outputs to `.harness/engagements/<slug>/design/design.md` in template format | Pending | TBD |
| R5 | Sync test validates template consistency between `.openclaw/templates/` and `.harness/templates/` | Pending | TBD |
| R6 | The boundary is maintained: OpenClaw writes to `.openclaw/`, harness writes to `.harness/` | Pending | TBD |

## 2. Detailed Specs

### R1 — Template Mirroring

Copy `.openclaw/templates/{assessment,requirements,design}.md` to `.harness/templates/`. The templates are the same files — they define the canonical format for each document type.

### R2-R4 — Harness Output

Each harness command should:
1. Read the template from `.harness/templates/<type>.md`
2. Populate the template with session output
3. Write to `.harness/engagements/<slug>/<type>/<type>.md`
4. Create parent directories if they don't exist

### R5 — Sync Test

Add a test in `tests/unit/` that:
1. Reads `.openclaw/templates/*.md`
2. Reads `.harness/templates/*.md`
3. Asserts matching file names exist in both
4. Asserts matching frontmatter and section structure

### R6 — Boundary

OpenClaw agents never write to `.harness/`. Harness agents never write to `.openclaw/`. The `CONVENTIONS.md` boundary rule is the foundation.

## 3. Coverage Map

| Requirement | Status | Wave(s) |
|-------------|--------|---------|
| R1 — Template mirroring | Pending | TBD |
| R2 — `/assess` output | Pending | TBD |
| R3 — `/requirements` output | Pending | TBD |
| R4 — `/design` output | Pending | TBD |
| R5 — Sync test | Pending | TBD |
| R6 — Boundary maintained | Pending | TBD |
