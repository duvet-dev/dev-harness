# Task 3 — Add 8 missing AgentSpec entries

**Status:** 📋 Pending
**Wave:** 32-health-fixes
**Dependencies:** None
**Effort:** 1h

## Description

Eight agent roles are referenced in harness config files but have no corresponding `AgentSpec` entry in `src/harness/agents/agent_registry.py`. The health checker reports them as missing.

## Missing Agents

| Agent | Referenced From |
|---|---|
| `code-critic` | teams.yaml, phases.yaml, skills.yaml, step_templates.yaml |
| `architecture-critic` | teams.yaml, skills.yaml |
| `research-agent` | teams.yaml |
| `dependency-analyser` | teams.yaml |
| `test-coverage-analyser` | teams.yaml, skills.yaml |
| `design-reviewer` | teams.yaml, step_templates.yaml |
| `security-critic` | teams.yaml, skills.yaml, step_templates.yaml |
| `security-auditor` | teams.yaml |

## Fix

Add 8 new `AgentSpec` entries to the `AGENTS` list in `agent_registry.py`. Each should have:
- `role` — matching the referenced role name exactly
- `name` — human-readable title
- `description` — what the agent does
- `sop_summary` — list of standard procedures
- `tags` — relevant category tags
- `tool_permissions` — appropriate permissions (most should be read-only or restricted_write)

Follow the existing AgentSpec pattern (e.g., the `architecture-analyser`, `critical-analyser`, `testing-agent` entries). Place them in a logical section, not the Wave 27 section.

## Acceptance Criteria

- [ ] All 8 agents have AgentSpec entries in agent_registry.py
- [ ] `harness shell` no longer shows "Referenced agent roles not in agent registry: ..."
- [ ] `harness agent list` shows all 8 agents
