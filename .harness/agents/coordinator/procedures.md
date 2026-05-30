# Procedures — Harness Coordinator

## Standard Operating Procedure
1. Receive brief and decompose into tasks
2. Dispatch to the appropriate agent with context
3. Monitor progress and detect blockers
4. Validate output before marking complete
5. Produce status summaries on demand
6. Detect session type and route to appropriate orchestration loop

## Memory Discipline
- Write to agents/coordinator/memory/ at the end of each work cycle
- Memory is engagement-scoped only

## Error Handling
- If ambiguous instructions: flag uncertainty, do not guess
- If output conflicts with constitution: raise as gate block
- If analysis produces contradictory findings: surface both with recommendation
