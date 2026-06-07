# Dev Harness — Design (Template Mirroring)

> **Purpose:** Single evolving design document. Updated through review cycles.
> **Engagement:** 006-template-mirroring
> **Status:** Draft
> **Last reviewed:** Not yet

---

## 0. Executive Summary

OpenClaw agents write engagement documents to `.openclaw/engagements/` using templates at `.openclaw/templates/`. The harness needs to produce equivalent documents in `.harness/engagements/` using mirrored templates at `.harness/templates/`. This keeps the two systems aligned while maintaining the boundary rule: OpenClaw owns `.openclaw/`, harness owns `.harness/`.

## 1. Architecture Overview

### 1.1 High-Level Flow

```
.openclaw/templates/              .harness/templates/
  assessment.md  ──mirror──►        assessment.md
  requirements.md ──mirror──►       requirements.md
  design.md      ──mirror──►       design.md

Harness /assess command:
  reads .harness/templates/assessment.md
  runs analysis
  writes .harness/engagements/<slug>/assessments/assessment.md

Harness /requirements command:
  reads .harness/templates/requirements.md
  runs requirements gathering
  writes .harness/engagements/<slug>/requirements/requirements.md

Harness /design command:
  reads .harness/templates/design.md
  runs design session
  writes .harness/engagements/<slug>/design/design.md
```

### 1.2 Core Modules

```
src/harness/
  templates/                        # Read template files
  engagement/
    doc_writer.py                   # Write engagement documents using templates
```

## 2. Key Systems

### 2.1 Template Mirroring

A one-time copy: same files, same format. Maintained by a sync test that checks for drift.

### 2.2 Engagement Doc Writer

```python
class EngagementDocWriter:
    """Writes structured engagement documents to .harness/engagements/<slug>/."""

    def __init__(self, root: Path):
        self.root = root

    def write_assessment(self, slug: str, content: dict) -> Path:
        """Write assessment.md from template."""
        ...

    def write_requirements(self, slug: str, content: dict) -> Path:
        """Write requirements.md from template."""
        ...

    def write_design(self, slug: str, content: dict) -> Path:
        """Write design.md from template."""
        ...
```

Each method:
1. Reads template from `.harness/templates/<type>.md`
2. Populates sections from session output
3. Creates `.harness/engagements/<slug>/<type>/`
4. Writes file

### 2.3 Command Integration

The `/assess`, `/requirements`, `/design` typed handlers call `EngagementDocWriter` after completing their analysis, writing results alongside their current stdout output.

## 3. Design Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | Template files are mirrors, not symlinks | Symlinks break on some filesystems and are invisible to git diff. |
| D2 | Templates are plain markdown with section headers | No template engine — reduces complexity. Commands know the section structure. |
| D3 | No retroactive writing | Only future command invocations write docs. Existing `.openclaw/` docs are not duplicated. |
| D4 | Boundary is enforced by convention, not code | The `CONVENTIONS.md` rule is sufficient. Adding runtime guards against cross-boundary writes is over-engineering. |

## 4. Review History

| Date | Scope | Reviewer | Outcome |
|------|-------|----------|---------|
| — | Not yet reviewed | — | — |
