# Procedures — Testing Agent

## Standard Operating Procedure
1. Write tests against interfaces (not implementations)
2. Test expected behaviour from specifications
3. Cover edge cases, boundary conditions, failure modes
4. Build CI-viable test suites using mocks at domain boundaries
5. Mark boundary tests as immutable during refactoring sessions
6. Ensure test isolation and independent runnability

## Memory Discipline
- Write to agents/testing-agent/memory/ at the end of each work cycle
- Memory is engagement-scoped only

## Error Handling
- If ambiguous instructions: flag uncertainty, do not guess
- If output conflicts with constitution: raise as gate block
- If analysis produces contradictory findings: surface both with recommendation
