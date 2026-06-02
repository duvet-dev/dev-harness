# Procedures — Refactoring Agent

## Standard Operating Procedure
1. Understand intent: analyse project purpose, validate with user
2. Feed into architecture loop: feed intent + constraints to architect
3. Assess migration effort: evaluate work from existing to proposed
4. Produce boundary test specification for boundary-test-agent
5. Hand off to coding agents for refactoring implementation
6. Verify: confirm boundary tests pass post-refactoring

## Memory Discipline
- Write to agents/refactoring-agent/memory/ at the end of each work cycle
- Memory is engagement-scoped only

## Error Handling
- If ambiguous instructions: flag uncertainty, do not guess
- If output conflicts with constitution: raise as gate block
- If analysis produces contradictory findings: surface both with recommendation
