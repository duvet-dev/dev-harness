# Procedures — Refactor Orchestrator

## Standard Operating Procedure
1. Run intent-discovery: deploy refactoring-agent to understand project
2. Run architecture-proposal: deploy architect + critic loop for target architecture
3. Run migration-assessment: deploy refactoring-agent to estimate effort
4. Run boundary-test-generation: deploy boundary-test-agent for guard-rail tests
5. Execute waves: per-wave refactoring via WaveCycleRunner
6. Run verification: full suite + boundary test integrity check
7. Produce summary: architecture debt delta + remaining debt

## Memory Discipline
- Write to agents/refactor-orchestrator/memory/ at the end of each work cycle
- Memory is engagement-scoped only

## Error Handling
- If ambiguous instructions: flag uncertainty, do not guess
- If output conflicts with constitution: raise as gate block
- If analysis produces contradictory findings: surface both with recommendation
