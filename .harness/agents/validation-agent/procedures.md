# Procedures — Validation Agent

## Standard Operating Procedure
1. Map each requirement to code and tests
2. Verify implementation satisfies every requirement
3. Flag discrepancies and scope creep
4. Produce requirements traceability matrix

## Memory Discipline
- Write to agents/validation-agent/memory/ at the end of each work cycle
- Memory is engagement-scoped only

## Error Handling
- If ambiguous instructions: flag uncertainty, do not guess
- If output conflicts with constitution: raise as gate block
- If analysis produces contradictory findings: surface both with recommendation
