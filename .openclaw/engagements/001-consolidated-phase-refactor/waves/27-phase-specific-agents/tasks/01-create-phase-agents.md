# Task 1 — Create 5 phase agents in agent_registry.py

**Status:** 📋 Pending
**Wave:** 27-phase-specific-agents
**Dependencies:** Wave 22
**Effort:** 1-2h

## Description

Create 5 dedicated phase agents: `assessment-agent`, `requirements-agent`, `design-agent`, `planning-agent`, `build-agent`. Each with phase-specific system prompts and tool permissions (restricted_write to their engagement artifact directories).

## Acceptance Criteria

- [ ] 5 new AgentSpec entries in agent_registry.py
- [ ] Each has appropriate system prompt, tool permissions, tags
- [ ] Registered in setup.py or equivalent
