# Dev Harness — Waves Plan (Template Mirroring)

> **Purpose:** Single view of all waves — completed and planned.
> **Engagement:** 006-template-mirroring
> **Updated:** 2026-06-07

---

## Wave Plan

Skeleton plan — awaiting architect refinement.

| Wave | Name | Effort | Depends On |
|------|------|--------|------------|
| 1 | Template mirroring + sync test | 1h | None |
| 2 | EngagementDocWriter | 2h | Wave 1 |
| 3 | Wire doc writer into /assess, /requirements, /design | 1.5h | Wave 2 |

### Wave Details

#### Wave 1 — Template Mirroring + Sync Test
**Effort:** 1h

Tasks:
1. Copy `.openclaw/templates/{assessment,requirements,design}.md` to `.harness/templates/`
2. Add sync test asserting matching file names and section structure

#### Wave 2 — EngagementDocWriter
**Effort:** 2h

Tasks:
1. Create `EngagementDocWriter` class
2. `write_assessment()`, `write_requirements()`, `write_design()` methods
3. Read template, populate sections, output to `.harness/engagements/<slug>/`

#### Wave 3 — Wire doc writer into commands
**Effort:** 1.5h

Tasks:
1. Call `EngagementDocWriter` from `/assess` handler
2. Call `EngagementDocWriter` from `/requirements` handler
3. Call `EngagementDocWriter` from `/design` handler
4. Tests
