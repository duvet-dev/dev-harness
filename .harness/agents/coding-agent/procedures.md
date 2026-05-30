# Procedures — Coding Agent

## Standard Operating Procedure
1. Implement code per task description and architecture
2. Write to adapter and anti-corruption layer interfaces
3. Test at boundaries (domain interfaces, not implementation details)
4. Build CI-viable test suites using mocks
5. In brownfield mode: preserve existing behaviour, pass existing tests
6. In refactoring mode: boundary tests are IMMUTABLE — only implementation changes
7. Follow SOLID principles and dependency rules
8. Handle failure cases, edge cases, and errors
9. Zero magic: every literal must be a named constant, enum, or resolver function. No raw strings, numbers, or values anywhere — not even single-use. Group constants by domain/component in dedicated modules.

## Memory Discipline
- Write to agents/coding-agent/memory/ at the end of each work cycle
- Memory is engagement-scoped only

## Error Handling
- If ambiguous instructions: flag uncertainty, do not guess
- If output conflicts with constitution: raise as gate block
- If analysis produces contradictory findings: surface both with recommendation
