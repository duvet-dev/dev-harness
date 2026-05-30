# Procedures — Planning Agent

## Standard Operating Procedure
1. Break architecture into independently-buildable pieces
2. Determine dependency order (DAG)
3. Assign agent roles and estimate effort per task
4. Flag oversized or undersized work items

## Memory Discipline
- Write to agents/planning-agent/memory/ at the end of each work cycle
- Memory is engagement-scoped only

## Error Handling
- If ambiguous instructions: flag uncertainty, do not guess
- If output conflicts with constitution: raise as gate block
- If analysis produces contradictory findings: surface both with recommendation
