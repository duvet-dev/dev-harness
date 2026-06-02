# Procedures — Domain Interface Tester

## Standard Operating Procedure
1. Discover domain interfaces (ABCs, Protocols, abstract classes)
2. Parse method signatures: parameters, types, return types
3. Generate probe tests with valid, invalid, and boundary inputs
4. Check: does the method handle all branches implied by its signature?
5. Check: documented exceptions that never get thrown
6. Check: states the method can enter that the interface doesn't document
7. Check return type shape matches expectations
8. Write probes to tests/domain-interface/ (auto-generated, not assertions)
9. Produce conformance report with score, mismatches, recommendations

## Memory Discipline
- Write to agents/domain-interface-tester/memory/ at the end of each work cycle
- Memory is engagement-scoped only

## Error Handling
- If ambiguous instructions: flag uncertainty, do not guess
- If output conflicts with constitution: raise as gate block
- If analysis produces contradictory findings: surface both with recommendation
