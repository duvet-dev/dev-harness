# Procedures — Dead Code Analyser

## Standard Operating Procedure
1. Scan project for potential dead code indicators
2. Check each candidate: is it exported/referenced anywhere?
3. Check for duplicate logic blocks
4. Flag commented-out code blocks (size-based threshold, >5 lines)
5. Check for unreachable branches (constant-condition guards)
6. Identify business-layer tests (domain/application/integration/feature)
7. Run coverage twice: all tests vs business-layer tests only
8. Find delta: code covered by unit tests but NOT by business tests
9. Categorise uncovered code: business-logic gap vs expected infrastructure
10. Produce structured report with static + coverage findings

## Memory Discipline
- Write to agents/dead-code-analyser/memory/ at the end of each work cycle
- Memory is engagement-scoped only

## Error Handling
- If ambiguous instructions: flag uncertainty, do not guess
- If output conflicts with constitution: raise as gate block
- If analysis produces contradictory findings: surface both with recommendation
